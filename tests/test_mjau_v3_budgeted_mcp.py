"""MJAU v3 fixed-origin budgeted opt-in MCP: security and source contracts.

All execute=True tests inject provider responses before any transport and use
a temporary SQLite budget store. No live OSV/Wikidata API calls in pytest.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
import threading
import time
from urllib.error import HTTPError

from fastmcp import Client
import pytest

from mcp_trendpulse.intelligence_core import BudgetCache
from mcp_trendpulse.mjau_v3 import budgeted_sources as api
from mcp_trendpulse.mjau_v3.mcp import mjau_v3_mcp

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "mjau_v3"
WIKIDATA = json.loads(
    (FIXTURE_ROOT / "wikidata_q42_q64_q30_20261121.json").read_text("utf-8")
)
DJANGO = json.loads(
    (FIXTURE_ROOT / "osv_django_compact_20261121.json").read_text("utf-8")
)["one_query_envelope"]
QIDS = ["Q42", "Q64", "Q30"]
LANGS = ["en", "de", "fr", "es", "sl", "it"]


def _usage(store: BudgetCache, key: str) -> int:
    day = datetime.now(timezone.utc).date().isoformat()
    with sqlite3.connect(str(store.db)) as conn:
        row = conn.execute(
            "SELECT used FROM budget WHERE source=? AND day=?", (key, day),
        ).fetchone()
    return row[0] if row is not None else 0


def _no_network(*_args, **_kwargs):
    raise AssertionError("Plan-only MUST NOT make any provider requests")


def _source_response(*, url, method, body, timeout):
    assert timeout == 8
    if method == "GET":
        assert url.startswith("https://www.wikidata.org/w/api.php?")
        assert body is None
        return WIKIDATA
    assert url == "https://api.osv.dev/v1/querybatch"
    assert method == "POST"
    assert len(body["queries"]) == 1
    return DJANGO


def test_mcp_export_contains_only_two_new_tools_not_regular_server():
    from mcp_trendpulse.intelligence_mcp import intel_mcp
    from mcp_trendpulse.mjau_v3.mcp import (
        mjau_v3_osv_advisory_ids, mjau_v3_wikidata_names,
    )
    import inspect

    assert inspect.signature(mjau_v3_wikidata_names).parameters["execute"].default is False
    assert inspect.signature(mjau_v3_osv_advisory_ids).parameters["execute"].default is False
    assert intel_mcp is not mjau_v3_mcp


def test_plan_only_does_not_touch_budget_cache_or_network(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "_request_json", _no_network)
    monkeypatch.setattr(api, "BudgetCache", _no_network)
    result = api.wikidata_identity(["Q64"], ["en"], execute=False)
    assert result["status"] == "planned"
    assert result["network_performed"] is False
    assert result["max_response_bytes"] == 192_000
    assert result["timeout_seconds"] == 8
    assert result["daily_request_cap"] == api.WIKIDATA_DAILY_CAP
    second = api.osv_package_ids("npm", "lodash", "4.17.11")
    assert second["status"] == "planned"
    assert second["body"]["queries"][0]["package"]["name"] == "lodash"
    assert second["daily_request_cap"] == api.OSV_DAILY_CAP
    assert not list(tmp_path.iterdir())


def test_shared_budget_and_cache_two_sources_never_persist_provider_bodies(
    tmp_path, monkeypatch,
):
    cache = BudgetCache(tmp_path)
    calls = []
    def fake_provider(**kwargs):
        calls.append(kwargs["method"])
        return _source_response(**kwargs)
    monkeypatch.setattr(api, "_request_json", fake_provider)

    a = api.wikidata_identity(QIDS, LANGS, name="Berlin", cache=cache, execute=True)
    assert a["status"] == "source_entities_observed"
    assert a["source_payload_validated_offline"] is True
    assert a["name_candidates"]["candidate_qids"] == ["Q64"]
    assert a["identity_verified"] is False
    assert a["license"] == "CC0-1.0"
    assert a["network_performed"]
    assert "OFFLINE" not in a["status"]
    assert not a["cache_hit"]
    assert _usage(cache, api.WIKIDATA_BUDGET_KEY) == 1

    # Different caller comparison MUST use the same cached QID response but
    # must never reuse the earlier Berlin name_candidates on the new query.
    usa = api.wikidata_identity(QIDS, LANGS, name="United States", cache=cache, execute=True)
    assert usa["cache_hit"] is True
    assert usa["network_performed"] is False
    assert usa["name_candidates"]["candidate_qids"] == ["Q30"]
    assert usa["name_candidates"]["query"] == "United States"
    assert _usage(cache, api.WIKIDATA_BUDGET_KEY) == 1
    no_name = api.wikidata_identity(QIDS, LANGS, cache=cache, execute=True)
    assert "name_candidates" not in no_name

    out = api.osv_package_ids("PyPI", "Django", "2.2.0", cache=cache, execute=True)
    assert out["status"] == "source_advisories_returned"
    assert out["advisory_count_projected"] == 75
    assert len(out["advisories"]) == 75
    assert out["commercial_bulk_redistribution_approved"] is False
    assert out["raw_advisory_redistribution_authorized"] is False
    assert out["source_specific_license_review_required"] is True
    assert out["source_attribution"]["aggregator"] == "OSV.dev"
    assert out["source_attribution"]["original_per_record_feed_verified"] is False
    assert "Filtered original OSV" in out["source_attribution"]["transformation_notice"]
    assert out["source_attribution"]["cc_by_4_license"] == (
        "https://creativecommons.org/licenses/by/4.0/"
    )
    assert "exact version" in out["third_party_request_notice"]
    assert out["network_performed"] is True
    assert _usage(cache, api.OSV_BUDGET_KEY) == 1
    cached = api.osv_package_ids("PyPI", "Django", "2.2.0", cache=cache, execute=True)
    assert cached["cache_hit"] is True
    assert cached["network_performed"] is False
    assert _usage(cache, api.OSV_BUDGET_KEY) == 1
    assert calls == ["GET", "POST"]

    # Intentionally inject a source blob containing a forbidden field and
    # ensure only minimal validated metadata, not the source blob, is cached.
    saved = cache.db.read_bytes()
    assert b"vulns" not in saved
    assert b'"details"' not in saved
    assert b"raw_advisory_bodies" not in saved


def test_failed_http_429_stops_future_source_operations(tmp_path, monkeypatch):
    cache = BudgetCache(tmp_path)
    called = 0
    def rate_limit(**kwargs):
        nonlocal called
        called += 1
        raise HTTPError(
            kwargs["url"], 429, "Rate limited", {"Retry-After": "120"}, None,
        )
    monkeypatch.setattr(api, "_request_json", rate_limit)
    first = api.osv_package_ids(
        "PyPI", "Django", "2.2.0", cache=cache, execute=True,
    )
    assert first["status"] == "source_unavailable"
    assert first["reason"] == "provider_http_429"
    assert first["network_performed"] is True
    assert first["retry_automatically"] is False
    assert cache.blocked(api.OSV_BUDGET_KEY)
    assert _usage(cache, api.OSV_BUDGET_KEY) == 1
    different = api.osv_package_ids(
        "npm", "lodash", "4.17.11", cache=cache, execute=True,
    )
    assert different["status"] == "source_unavailable"
    assert different["reason"] == "persisted_provider_cooldown"
    assert different["network_performed"] is False
    assert _usage(cache, api.OSV_BUDGET_KEY) == 1
    assert called == 1


def test_atomic_daily_cap_rejection_and_zero_network(tmp_path, monkeypatch):
    cache = BudgetCache(tmp_path)
    monkeypatch.setattr(api, "_request_json", _no_network)
    for _ in range(api.OSV_DAILY_CAP):
        cache.reserve(api.OSV_BUDGET_KEY, api.OSV_DAILY_CAP)
    denied = api.osv_package_ids(
        "npm", "minimist", "0.0.8", execute=True, cache=cache,
    )
    assert denied["status"] == "source_unavailable"
    assert denied["reason"] == "local_utc_daily_budget_exhausted"
    assert denied["network_performed"] is False
    assert denied["not_a_zero_result"] is True


def test_wikidata_eight_call_daily_limit_persists_across_store_instances(
    tmp_path, monkeypatch,
):
    original = BudgetCache(tmp_path)
    monkeypatch.setattr(api, "_request_json", _no_network)
    for _ in range(api.WIKIDATA_DAILY_CAP):
        original.reserve(api.WIKIDATA_BUDGET_KEY, api.WIKIDATA_DAILY_CAP)
    # A new server process with the same SQLite directory cannot bypass the
    # earlier UTC-day reservations.
    reopened = BudgetCache(tmp_path)
    result = api.wikidata_identity(
        ["Q64"], ["en"], execute=True, cache=reopened,
    )
    assert result["status"] == "source_unavailable"
    assert result["reason"] == "local_utc_daily_budget_exhausted"
    assert result["not_a_zero_result"] is True
    assert result["network_performed"] is False
    assert _usage(reopened, api.WIKIDATA_BUDGET_KEY) == 8


def test_long_retry_after_503_enforces_no_more_queries_across_store_reopen(
    tmp_path, monkeypatch,
):
    cache = BudgetCache(tmp_path)
    called = 0

    def overload(**kwargs):
        nonlocal called
        called += 1
        raise HTTPError(
            kwargs["url"], 503, "Temporarily unavailable",
            {"Retry-After": "3600"}, None,
        )

    monkeypatch.setattr(api, "_request_json", overload)
    response = api.osv_package_ids(
        "PyPI", "Django", "2.2.0", cache=cache, execute=True,
    )
    assert response["reason"] == "provider_http_503"
    assert response["not_a_zero_result"]
    reopened = BudgetCache(tmp_path)
    assert reopened.blocked(api.OSV_BUDGET_KEY)
    response2 = api.osv_package_ids(
        "npm", "lodash", "4.17.11", cache=reopened, execute=True,
    )
    assert response2["reason"] == "persisted_provider_cooldown"
    assert response2["network_performed"] is False
    assert called == 1


def test_bad_plan_arguments_do_not_consume_quota(tmp_path, monkeypatch):
    cache = BudgetCache(tmp_path)
    monkeypatch.setattr(api, "_request_json", _no_network)
    with pytest.raises(ValueError):
        api.osv_package_ids([], "Django", "2.2.0", execute=True, cache=cache)
    with pytest.raises(ValueError):
        api.wikidata_identity(["Q64"], ["en"], name="Berlin", match_language="fr",
                              execute=True, cache=cache)
    with pytest.raises(ValueError, match="boolean"):
        api.osv_package_ids("npm", "lodash", "1.0", execute="yes", cache=cache)
    assert _usage(cache, api.WIKIDATA_BUDGET_KEY) == 0
    assert _usage(cache, api.OSV_BUDGET_KEY) == 0


def test_untrusted_provider_body_is_rejected_and_never_persisted(
    tmp_path, monkeypatch,
):
    cache = BudgetCache(tmp_path)
    injected = {
        "results": [{"vulns": [
            {"id": "GHSA-1234-5678-9012", "modified": "2026-11-22T00:00:00Z",
             "details": "must-not-persist-private-demo-string"},
        ]}],
    }
    monkeypatch.setattr(api, "_request_json", lambda **_: injected)
    failed = api.osv_package_ids(
        "PyPI", "Django", "2.2.0", cache=cache, execute=True,
    )
    assert failed["status"] == "source_unavailable"
    assert failed["reason"] == "invalid_or_oversized_source_shape"
    assert failed["not_a_zero_result"] is True
    data = cache.db.read_bytes()
    assert b"must-not-persist-private-demo-string" not in data
    assert b"GHSA-1234-5678-9012" not in data


def test_singleflight_requests_across_parallel_clients(tmp_path, monkeypatch):
    cache = BudgetCache(tmp_path)
    counter = 0
    lock = threading.Lock()
    def fake(**kwargs):
        nonlocal counter
        with lock:
            counter += 1
        time.sleep(0.1)
        return _source_response(**kwargs)
    monkeypatch.setattr(api, "_request_json", fake)
    def call():
        return api.osv_package_ids(
            "PyPI", "Django", "2.2.0", cache=cache, execute=True,
        )
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: call(), range(8)))
    assert counter == 1
    assert sum(not r["cache_hit"] for r in results) == 1
    assert all(r["advisory_count_projected"] == 75 for r in results)
    assert _usage(cache, api.OSV_BUDGET_KEY) == 1


def test_mcp_tool_call_plan_and_execute_with_fixture_injection(tmp_path, monkeypatch):
    import asyncio
    store = BudgetCache(tmp_path)
    monkeypatch.setattr(api, "BudgetCache", lambda: store)
    monkeypatch.setattr(api, "_request_json", _source_response)

    async def exercise():
        async with Client(mjau_v3_mcp) as client:
            tools = await client.list_tools()
            assert sorted(x.name for x in tools) == [
                "mjau_v3_osv_advisory_ids", "mjau_v3_wikidata_names",
            ]
            p = await client.call_tool(
                "mjau_v3_wikidata_names",
                {"qids": QIDS, "languages": LANGS, "name": "Berlin"},
            )
            assert p.structured_content["status"] == "planned"
            a = await client.call_tool(
                "mjau_v3_wikidata_names", {
                    "qids": QIDS, "languages": LANGS, "name": "Berlin",
                    "execute": True,
                },
            )
            assert a.structured_content["name_candidates"]["candidate_qids"] == ["Q64"]
            cached = await client.call_tool(
                "mjau_v3_wikidata_names", {
                    "qids": QIDS, "languages": LANGS, "name": "United States",
                    "execute": True,
                },
            )
            assert cached.structured_content["name_candidates"]["candidate_qids"] == ["Q30"]
            assert cached.structured_content["cache_hit"] is True
            osv = await client.call_tool(
                "mjau_v3_osv_advisory_ids", {
                    "ecosystem": "PyPI", "package": "Django",
                    "version": "2.2.0", "execute": True,
                },
            )
            assert osv.structured_content["advisory_count_projected"] == 75
            assert not osv.structured_content["commercial_bulk_redistribution_approved"]
            bad = await client.call_tool(
                "mjau_v3_osv_advisory_ids", {
                    "ecosystem": "invalid", "package": "Django",
                    "version": "2.2.0", "execute": True,
                }, raise_on_error=False,
            )
            assert bad.is_error
    asyncio.run(exercise())
    assert _usage(store, api.WIKIDATA_BUDGET_KEY) == 1
    assert _usage(store, api.OSV_BUDGET_KEY) == 1
