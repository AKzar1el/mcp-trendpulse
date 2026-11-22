"""Fifth-pass cache integrity, Retry-After semantics and quota stress checks.

Only synthetic source envelopes and temporary SQLite stores are used.
No real internet connection or production cache is touched.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import json
import sqlite3
import threading
import time
from urllib.error import HTTPError

import pytest

from mcp_trendpulse.intelligence_core import BudgetCache
from mcp_trendpulse.mjau_v3 import budgeted_sources as api


def _osv_payload():
    return {"results": [{"vulns": [{
        "id": "GHSA-1234-5678-9012",
        "modified": "2026-11-21T00:00:00Z",
    }]}]}


def _wiki_payload():
    return {"success": 1, "entities": {"Q64": {
        "id": "Q64", "type": "item",
        "labels": {"en": {"language": "en", "value": "Berlin"}},
        "aliases": {}, "descriptions": {},
    }}}


def _change_cached_body(cache, update):
    with sqlite3.connect(str(cache.db)) as conn:
        rows = conn.execute("SELECT id, body FROM cache").fetchall()
        assert len(rows) == 1
        key, raw = rows[0]
        conn.execute(
            "UPDATE cache SET body=? WHERE id=?",
            (update(raw), key),
        )


@pytest.mark.parametrize("corruption", [
    "invalid-json",
    "wrong-request",
    "license-override",
    "advisory-prose",
    "wrong-type",
    "json-null",
    "duplicate-json-key",
    "oversized-json-row",
])
def test_poisoned_osv_cache_must_fail_closed_without_network(tmp_path, monkeypatch, corruption):
    cache = BudgetCache(tmp_path)
    monkeypatch.setattr(api, "_request_json", lambda **_: _osv_payload())
    original = api.osv_package_ids("npm", "lodash", "4.17.11", cache=cache, execute=True)
    assert original["status"] == "source_advisories_returned"

    def change(raw):
        if corruption == "invalid-json":
            return "{bad"
        if corruption == "json-null":
            return "null"
        if corruption == "duplicate-json-key":
            return raw.replace('"status":', '"status":"source_unavailable","status":', 1)
        if corruption == "oversized-json-row":
            return raw + " " * 200_000
        result = json.loads(raw)
        if corruption == "wrong-request":
            result["package"] = "unrelated-project"
        elif corruption == "license-override":
            result["commercial_bulk_redistribution_approved"] = True
        elif corruption == "advisory-prose":
            result["advisories"][0]["description"] = "fabricated unsafe text"
        elif corruption == "wrong-type":
            return json.dumps(["not-a-validated-tool-response"])
        return json.dumps(result)

    _change_cached_body(cache, change)
    monkeypatch.setattr(api, "_request_json", lambda **_: pytest.fail(
        "A corrupted local cache must never trigger an unplanned provider request"
    ))
    output = api.osv_package_ids("npm", "lodash", "4.17.11", cache=cache, execute=True)
    assert output["status"] == "source_unavailable"
    assert output["reason"] == "local_cache_integrity_failure"
    assert output["not_a_zero_result"] is True
    assert output["network_performed"] is False


def test_poisoned_wikidata_cache_cannot_confirm_identity(tmp_path, monkeypatch):
    cache = BudgetCache(tmp_path)
    monkeypatch.setattr(api, "_request_json", lambda **_: _wiki_payload())
    original = api.wikidata_identity(["Q64"], ["en"], cache=cache, execute=True)
    assert original["status"] == "source_entities_observed"

    def change(raw):
        data = json.loads(raw)
        data["identity_verified"] = True
        return json.dumps(data)

    _change_cached_body(cache, change)
    monkeypatch.setattr(api, "_request_json", lambda **_: pytest.fail("no network"))
    result = api.wikidata_identity(["Q64"], ["en"], cache=cache, execute=True)
    assert result["status"] == "source_unavailable"
    assert result["reason"] == "local_cache_integrity_failure"
    assert result["not_a_zero_result"] is True


def test_http_date_retry_after_is_respected_for_provider_503(tmp_path, monkeypatch):
    cache = BudgetCache(tmp_path)
    retry = format_datetime(
        datetime.now(timezone.utc) + timedelta(hours=1), usegmt=True,
    )
    def unavailable(**kw):
        raise HTTPError(kw["url"], 503, "busy", {"Retry-After": retry}, None)
    monkeypatch.setattr(api, "_request_json", unavailable)
    result = api.osv_package_ids("npm", "lodash", "4.17.11", cache=cache, execute=True)
    assert result["reason"] == "provider_http_503"
    with sqlite3.connect(str(cache.db)) as conn:
        row = conn.execute(
            "SELECT until FROM cooldown WHERE source=?", (api.OSV_BUDGET_KEY,),
        ).fetchone()
    assert row is not None
    assert row[0] - time.time() > 3200, "RFC HTTP-date cooldown must not be shortened"


def test_twenty_distinct_concurrent_queries_use_at_most_ten_osv_budget(tmp_path, monkeypatch):
    cache = BudgetCache(tmp_path)
    count = 0
    mutex = threading.Lock()
    def fake(**kwargs):
        nonlocal count
        with mutex:
            count += 1
        return {"results": [{}]}
    monkeypatch.setattr(api, "_request_json", fake)

    def call(i):
        return api.osv_package_ids("npm", f"package-{i}", "1.0", cache=cache, execute=True)

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(call, range(20)))
    successful = [r for r in results if r["status"] == "no_returned_advisories"]
    denied = [r for r in results if r.get("reason") == "local_utc_daily_budget_exhausted"]
    assert len(successful) == api.OSV_DAILY_CAP
    assert len(denied) == 20 - api.OSV_DAILY_CAP
    assert count == api.OSV_DAILY_CAP
    assert all(r["no_advisory_not_equivalent_to_safe_package"] for r in successful)


def test_twenty_independent_store_instances_share_one_utc_day_cap(tmp_path, monkeypatch):
    stores = [BudgetCache(tmp_path) for _ in range(20)]
    observed = 0
    mutex = threading.Lock()

    def fake(**_kwargs):
        nonlocal observed
        with mutex:
            observed += 1
        return {"results": [{}]}

    monkeypatch.setattr(api, "_request_json", fake)

    def exercise(i):
        return api.osv_package_ids(
            "npm", f"workload-{i}", "1.0", cache=stores[i], execute=True,
        )

    with ThreadPoolExecutor(max_workers=10) as pool:
        rows = list(pool.map(exercise, range(20)))
    assert observed == api.OSV_DAILY_CAP
    assert sum(row["status"] == "no_returned_advisories" for row in rows) == 10
    assert sum(row.get("reason") == "local_utc_daily_budget_exhausted" for row in rows) == 10


def test_empty_result_survives_cache_without_claiming_safe(tmp_path, monkeypatch):
    cache = BudgetCache(tmp_path)
    monkeypatch.setattr(api, "_request_json", lambda **_: {"results": [{}]})
    first = api.osv_package_ids("npm", "react", "18.2.0", cache=cache, execute=True)
    assert first["status"] == "no_returned_advisories"
    assert first["no_advisory_not_equivalent_to_safe_package"] is True
    monkeypatch.setattr(api, "_request_json", lambda **_: pytest.fail("cache expected"))
    second = api.osv_package_ids("npm", "react", "18.2.0", cache=cache, execute=True)
    assert second["cache_hit"] is True
    assert second["no_advisory_not_equivalent_to_safe_package"] is True


def test_missing_wikidata_qid_is_still_unknown_on_cache_hit(tmp_path, monkeypatch):
    cache = BudgetCache(tmp_path)
    monkeypatch.setattr(api, "_request_json", lambda **_: {
        "success": 1, "entities": {"Q42": {"id": "Q42", "missing": ""}},
    })
    first = api.wikidata_identity(["Q42"], ["en"], cache=cache, execute=True)
    assert first["status"] == "source_entities_partially_observed"
    monkeypatch.setattr(api, "_request_json", lambda **_: pytest.fail("cache expected"))
    second = api.wikidata_identity(["Q42"], ["en"], cache=cache, execute=True)
    assert second["status"] == "source_entities_partially_observed"
    assert second["source_coverage_complete"] is False
    assert second["results"][0]["status"] == "unknown_missing_entity"


def test_unavailable_local_sqlite_store_fails_closed_without_provider_request(tmp_path, monkeypatch):
    cache = BudgetCache(tmp_path)
    def raise_sqlite_error():
        raise sqlite3.OperationalError("private database path must not be leaked")
    monkeypatch.setattr(cache, "_connect", raise_sqlite_error)
    monkeypatch.setattr(api, "_request_json", lambda **_: pytest.fail("no network"))
    result = api.osv_package_ids("npm", "lodash", "4.17.11", cache=cache, execute=True)
    assert result["status"] == "source_unavailable"
    assert result["reason"] == "local_cache_integrity_failure"
    assert "private database path" not in repr(result)


def test_unusual_provider_http_status_is_cached_without_changing_reason(tmp_path, monkeypatch):
    cache = BudgetCache(tmp_path)
    def unavailable(**kw):
        raise HTTPError(kw["url"], 418, "teapot", {}, None)
    monkeypatch.setattr(api, "_request_json", unavailable)
    first = api.osv_package_ids("npm", "lodash", "4.17.11", cache=cache, execute=True)
    assert first["reason"] == "provider_http_418"
    monkeypatch.setattr(api, "_request_json", lambda **_: pytest.fail("cache expected"))
    second = api.osv_package_ids("npm", "lodash", "4.17.11", cache=cache, execute=True)
    assert second["reason"] == "provider_http_418"
    assert second["cache_hit"] is True
