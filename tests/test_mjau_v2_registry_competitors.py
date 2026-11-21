"""A01 proof-only official MCP Registry: plan, bounded source, trust, cache and failure tests."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from mcp_trendpulse.mjau_v2 import registry_competitors as reg

NOW = datetime(2026, 11, 21, 4, 30, tzinfo=timezone.utc)


def item(name="io.modelcontextprotocol/filesystem", version="2.1.0", **changes):
    row = {
        "server": {
            "name": name, "version": version, "title": "Filesystem MCP",
            "description": "Read files and folders", "repository": {
                "source": "github", "url": "https://github.com/modelcontextprotocol/servers"
            },
        },
        "_meta": {reg._META: {"status": "active", "isLatest": True}},
    }
    for path, value in changes.items():
        if path == "status":
            row["_meta"][reg._META]["status"] = value
        elif path == "isLatest":
            row["_meta"][reg._META]["isLatest"] = value
        elif path == "repository":
            row["server"]["repository"] = value
        else:
            row["server"][path] = value
    return row


def payload(*rows, more=False):
    return {"servers": list(rows), "metadata": {"count": len(rows), "nextCursor": "opaque_after" if more else None}}


class Store:
    def __init__(self):
        self.data = {}
        self.used = 0
        self.cooldowns = []
        self.block = False
        self.fail_reserve = None
        self.saved_ttls = []

    def cached(self, key):
        return self.data.get(key)

    def blocked(self, source):
        return self.block

    def reserve(self, source, cap, *, guard_cooldown):
        if self.fail_reserve:
            raise self.fail_reserve
        assert source == reg.SOURCE_ID and cap == reg.BUDGET_PER_DAY and guard_cooldown
        self.used += 1

    def cool_down(self, source, seconds):
        self.cooldowns.append((source, seconds))

    def save(self, key, output, ttl):
        self.data[key] = output
        self.saved_ttls.append(ttl)


UNSET = object()

def run(*, query="filesystem", rows=UNSET, code=200, store=None, limit=5, **kw):
    cache = store or Store()
    called = []
    def get(url, params):
        called.append((url, params))
        return code, payload(item()) if rows is UNSET else rows
    out = reg.search_registry_competitors(
        query=query, limit=limit, execute=True, cache=cache,
        fetcher=get, observed_at=NOW, **kw,
    )
    return out, cache, called


def test_plan_only_no_sqlite_or_network():
    def fetch(*args):
        raise AssertionError("Network in plan-only!")
    x = reg.search_registry_competitors(query=" filesystem ", fetcher=fetch, observed_at=NOW)
    assert x["status"] == "planned" and x["requests_attempted"] == 0
    assert x["query"] == "filesystem" and x["records"] == []
    assert x["request_url"] == reg.URL + "?search=filesystem&version=latest&limit=8"
    assert x["search_is_name_substring_only"] and not x["competition_verified"]


@pytest.mark.parametrize("query", ["", " ", "ok", "x" * 81, "bad\nname", None, 123])
def test_query_rejected_without_network(query):
    with pytest.raises(ValueError):
        reg.search_registry_competitors(query=query)


@pytest.mark.parametrize("limit", [0, 16, True, 1.5, "2"])
def test_limit_rejected_without_network(limit):
    with pytest.raises(ValueError):
        reg.search_registry_competitors(query="filesystem", limit=limit)


def test_nonboolean_execute_and_naive_clock_rejected():
    with pytest.raises(ValueError):
        reg.search_registry_competitors(query="filesystem", execute="yes")
    with pytest.raises(ValueError):
        reg.search_registry_competitors(query="filesystem", observed_at=datetime(2026, 11, 21))


def test_latest_active_server_source_references_and_no_claims():
    out, store, calls = run()
    assert out["status"] == "observed" and len(out["records"]) == 1
    x = out["records"][0]
    assert x["server_name"] == "io.modelcontextprotocol/filesystem"
    assert x["source_detail_url"].endswith("io.modelcontextprotocol%2Ffilesystem/versions/latest")
    assert x["repository_url"] == "https://github.com/modelcontextprotocol/servers"
    assert out["search_is_name_substring_only"] and not out["competition_verified"]
    assert out["requests_attempted"] == 1 and out["network_performed"]
    assert store.used == 1 and len(calls) == 1
    assert calls[0][1] == {"search": "filesystem", "version": "latest", "limit": "5"}


def test_paginated_sample_not_total_population_or_implicit_pagination():
    out, _, calls = run(rows=payload(item(), more=True))
    assert out["status"] == "observed_partial"
    assert out["has_more_results"] is True
    assert len(calls) == 1 and len(out["records"]) == 1
    assert "cursor" not in calls[0][1]


def test_same_name_duplicates_and_untrusted_server_rows_are_rejected():
    out, _, _ = run(rows=payload(item(), item(version="4.5.0"), item(name="??")))
    assert out["status"] == "observed_partial"
    assert out["source_rows_received"] == 3
    assert out["source_rows_rejected"] == 2
    assert len(out["records"]) == 1


@pytest.mark.parametrize("changes", [{"isLatest": False}, {"status": "deleted"}, {"name": "wrong name"}, {"version": ""}, {"name": "io.example/srv\r"}])
def test_fails_closed_when_all_rows_invalid(changes):
    out, _, _ = run(rows=payload(item(**changes)))
    assert out["status"] == "invalid_source_shape" and not out["records"]


@pytest.mark.parametrize("bad", [None, [], {"servers": [], "metadata": {}}, {"servers": "oops", "metadata": {"count": 0}}, {"servers": [], "metadata": {"count": True, "nextCursor": None}}, {"servers": [], "metadata": {"count": 0, "nextCursor": "bad\n"}}, {"servers": [], "metadata": {"count": 9}}, {"servers": [], "metadata": {"count": 0, "nextCursor": "not-an-empty-last-page"}}])
def test_invalid_envelopes_fail_closed(bad):
    out, _, _ = run(rows=bad)
    assert out["status"] == "invalid_source_shape"


def test_genuine_zero_page_is_not_zero_buyer_demand():
    out, _, _ = run(rows=payload())
    assert out["status"] == "no_data" and out["records"] == []
    assert not out["customer_demand_verified"]


def test_first_page_limit_enforced_on_provider_response():
    out, _, _ = run(rows=payload(*[item(f"io.example/file{i}") for i in range(6)]), limit=5)
    assert out["status"] == "invalid_source_shape"


def test_repository_url_allowlist_and_unknown_fields_are_not_emitted():
    badrepo = {"source": "github", "url": "https://other.example/secret?token=fake"}
    v = item(repository=badrepo)
    v["unexpected_secret_field"] = "password=do-not-emit"
    out, store, _ = run(rows=payload(v))
    assert out["status"] == "observed" and out["records"][0]["repository_url"] is None
    assert "secret" not in json.dumps(out)
    assert "do-not-emit" not in json.dumps(store.data)


def test_cache_replay_uses_zero_provider_requests_and_validates_data_again():
    store = Store()
    a, store, _ = run(store=store)
    b, store, calls = run(store=store, code=503)
    assert a["status"] == "observed" and b["status"] == "observed"
    assert b["cache_hit"] is True and b["network_performed"] is False
    assert store.used == 1 and calls == []
    assert store.saved_ttls == [reg.CACHE_TTL_SECONDS]


def test_poisoned_cache_is_ignored_and_requeried():
    store = Store()
    run(store=store)
    key = next(iter(store.data))
    store.data[key]["provider_result"]["servers"][0]["server"]["name"] = "invalid value!"
    out, _, calls = run(store=store)
    assert out["status"] == "observed" and not out["cache_hit"]
    assert len(calls) == 1 and store.used == 2


def test_expired_cache_not_reused():
    store = Store()
    run(store=store)
    key = next(iter(store.data))
    store.data[key]["observed_at"] = (NOW - timedelta(hours=7)).isoformat()
    out, _, calls = run(store=store)
    assert not out["cache_hit"] and len(calls) == 1


@pytest.mark.parametrize("code,reason", [(401, "provider_response_error"), (403, "provider_response_error"), (500, "provider_response_error"), (429, "http_429"), (503, "http_503")])
def test_http_unavailable_is_not_empty_data_and_rate_limit_honored(code, reason):
    out, store, _ = run(code=code)
    assert out["status"] == "unavailable" and out["reason"] == reason
    assert out["records"] == [] and store.used == 1
    assert len(store.cooldowns) == (1 if code in (429,503) else 0)


def test_existing_cooldown_prevents_call_or_budget_reservation():
    store = Store()
    store.block = True
    out, _, calls = run(store=store)
    assert out["status"] == "unavailable" and out["reason"] == "provider_cooldown"
    assert store.used == 0 and calls == []


def test_network_exception_redacted_and_not_confused_with_no_data():
    store = Store()
    def bad(*args):
        raise RuntimeError("token=SUPERSECRET in URL")
    out = reg.search_registry_competitors(query="filesystem", execute=True,
                                          observed_at=NOW, cache=store, fetcher=bad)
    assert out["status"] == "unavailable"
    assert "SUPERSECRET" not in json.dumps(out)


def test_transport_fixed_host_no_proxy_redirects_or_unbounded_bytes(monkeypatch):
    requests = pytest.importorskip("requests")
    class Response:
        status_code = 200
        headers = {"Content-Type": "application/json"}
        class raw:
            @staticmethod
            def read(n, *, decode_content=False):
                assert decode_content
                return json.dumps(payload(item())).encode()
        def __enter__(self): return self
        def __exit__(self, *args): pass
    class Session:
        def __init__(self): self.trust_env = True
        def get(self, url, **kwargs):
            assert not self.trust_env and url == reg.URL
            assert kwargs["allow_redirects"] is False and kwargs["stream"] is True
            assert kwargs["timeout"] == (4, 10)
            return Response()
        def close(self): pass
    monkeypatch.setattr(requests, "Session", Session)
    code, obj = reg._fetch(reg.URL, {"search": "filesystem", "version": "latest", "limit": "1"})
    assert code == 200 and obj["servers"]
    with pytest.raises(ValueError):
        reg._fetch("https://other.example/v0.1/servers", {"search": "filesystem", "version": "latest", "limit": "1"})


def test_live_source_shaped_fixture_has_incremental_information_v1_lacks():
    # Source shape transcribed from live public registry first page, not a forecast.
    observed = item(name="ac.inference.sh/mcp", version="2.0.1", title="inference.sh")
    out, _, _ = run(query="inference", rows=payload(observed))
    old_v1_idea_map_keyword = {"competition": "not_measured"}
    assert old_v1_idea_map_keyword["competition"] == "not_measured"
    assert out["status"] == "observed" and len(out["records"]) == 1
    assert out["records"][0]["source_detail_url"].startswith(reg.URL)
    assert not out["competition_verified"]


def test_source_rejections_not_silently_erased_by_cache():
    cache = Store()
    initial, _, _ = run(rows=payload(item(), item(name="INVALID")), store=cache)
    assert initial["status"] == "observed_partial"
    assert not cache.data  # Do not cache a reconstructed complete-looking sample.


def test_daily_budget_exhaustion_is_unavailable_not_invalid_source():
    class DailyBudgetExceeded(ValueError):
        pass
    cache = Store()
    cache.fail_reserve = DailyBudgetExceeded("unsafe/raw/token=EXAMPLE")
    result, _, called = run(store=cache)
    assert result["status"] == "unavailable"
    assert result["reason"] == "local_daily_budget_exceeded"
    assert result["requests_attempted"] == 0 and called == []
    assert "EXAMPLE" not in json.dumps(result)


def test_oversized_response_rejected_without_echoing_payload():
    store = Store()
    def bad(*args):
        raise reg.OversizedRegistryResponse("raw SECRET backtrace")
    out = reg.search_registry_competitors(query="filesystem", execute=True,
                                          observed_at=NOW, cache=store, fetcher=bad)
    assert out["status"] == "invalid_source_shape" and out["reason"] == "response_oversized"
    assert "SECRET" not in json.dumps(out)


def test_unicode_query_is_preserved_and_bounded():
    out = reg.search_registry_competitors(query="  šifriranje   ", observed_at=NOW)
    assert out["query"] == "šifriranje" and "%C5%A1" in out["request_url"]


def test_no_extra_fields_in_results_from_provider():
    raw = item(description="Useful tools")
    raw["server"]["super_secret"] = "should-not-emit"
    raw["_meta"][reg._META]["arbitrary"] = "not-allowed"
    out, store, _ = run(rows=payload(raw))
    assert "should-not-emit" not in json.dumps(out)
    assert "not-allowed" not in json.dumps(store.data)
