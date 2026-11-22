"""A02: bounded, privacy-safe GitHub weekly history tests."""
from __future__ import annotations

import json
from datetime import datetime, timezone
import pytest
from mcp_trendpulse.mjau_v2 import github_stars as gh

NOW = datetime(2026, 11, 21, 12, tzinfo=timezone.utc)
WEEK = 7 * 86400
SUN = int(datetime(2026, 11, 15, tzinfo=timezone.utc).timestamp())


def week(i: int, total: int = 21):
    return {"week": SUN - WEEK * i, "total": total,
            "days": [total, 0, 0, 0, 0, 0, 0]}


class Store:
    def __init__(self):
        self.data = {}
        self.used = 0
        self.cooldowns = []
        self.block = False
        self.fail = None

    def cached(self, key):
        return self.data.get(key)

    def blocked(self, source):
        return self.block

    def reserve(self, source, cap, *, guard_cooldown):
        if self.fail:
            raise self.fail
        assert source == gh.SOURCE and cap == gh.CAP and guard_cooldown
        self.used += 1

    def cool_down(self, source, seconds):
        self.cooldowns.append((source, seconds))

    def save(self, key, out, ttl):
        assert ttl == gh.TTL_SECONDS
        self.data[key] = out

UNSET = object()

def run(*, rows=UNSET, status=200, store=None, limit=10):
    called = []
    cache = store or Store()
    def get(url, params):
        called.append((url, params))
        return status, rows if rows is not UNSET else [week(i, 14 + i) for i in range(limit)]
    out = gh.github_star_history(owner="AKzar1el", repo="mcp-trendpulse", limit=limit,
                                 execute=True, cache=cache, fetcher=get, observed_at=NOW)
    return out, cache, called


def test_preview_does_not_access_cache_or_network():
    def fail(*a):
        raise RuntimeError("unexpected")
    out = gh.github_star_history(owner="AKzar1el", repo="mcp-trendpulse",
                                 observed_at=NOW, fetcher=fail)
    assert out["status"] == "planned" and out["requests_attempted"] == 0
    assert not out["individual_stargazer_data_collected"]


@pytest.mark.parametrize("owner,repo", [("", "repo"), ("x" * 40, "repo"),
                                      ("abc-", "repo"), ("x", "."), ("x", ".."),
                                      ("x", "foo/bar"), ("x", "name.git"),
                                      ("x", "a" * 101), (None, "repo"), ("abc", None)])
def test_owner_repo_validation(owner, repo):
    with pytest.raises(ValueError):
        gh.github_star_history(owner=owner, repo=repo)


@pytest.mark.parametrize("limit", [0, 13, -1, True, 2.1, "2"])
def test_page_limit_validation(limit):
    with pytest.raises(ValueError):
        gh.github_star_history(owner="x", repo="ok", limit=limit)


def test_bool_execute_and_timezone_required():
    with pytest.raises(ValueError):
        gh.github_star_history(owner="x", repo="ok", execute="yes")
    with pytest.raises(ValueError):
        gh.github_star_history(owner="x", repo="ok", observed_at=datetime(2026, 11, 21))


def test_privacy_labeled_single_page_and_source_details():
    out, store, calls = run()
    assert out["status"] == "observed_partial"
    assert out["returned_week_count"] == 10 and len(calls) == 1 and store.used == 1
    assert calls[0][1] == {"per_page": "10", "page": "1"}
    assert out["weeks"][0]["weekly_active_star_events"] == 14
    assert out["provider_week_day_timezone"] == "not_guaranteed_utc"
    assert out["has_historical_unstar_events"] is False
    assert not out["individual_stargazer_data_collected"]
    assert "username" not in json.dumps(out).lower()


def test_descriptive_comparable_four_week_windows():
    out, _, _ = run()
    v = out["comparison"]
    assert v["status"] == "descriptive_cohort_window_comparison"
    assert v["recent_4wk"] == sum(14 + i for i in range(2, 6))
    assert v["previous_4wk"] == sum(14 + i for i in range(6, 10))
    assert not v["is_forecast_or_inferred_actual_historical_interest"]


def test_short_response_insufficient_for_growth_comparison():
    out, _, _ = run(limit=4)
    assert out["comparison"]["status"] == "insufficient_eligible_history"
    assert out["comparison"]["percent_change"] is None


def test_observed_zero_is_distinct_from_empty_source():
    a, _, _ = run(rows=[week(0, 0)])
    b, _, _ = run(rows=[])
    assert a["status"] == "observed_partial" and a["weeks"][0]["weekly_active_star_events"] == 0
    assert b["status"] == "no_data" and b["weeks"] == []


def test_zero_baseline_does_not_invent_infinite_growth():
    rows = [week(i, 12) for i in range(6)] + [week(i, 0) for i in range(6, 10)]
    out, _, _ = run(rows=rows)
    assert out["comparison"]["previous_4wk"] == 0
    assert out["comparison"]["percent_change"] is None


@pytest.mark.parametrize("bad", [None, {}, [{"week": 123}],
                                 [{"week": SUN, "total": True, "days": [0] * 7}],
                                 [{"week": SUN, "total": 0, "days": [False] * 7}],
                                 [{"week": SUN + WEEK * 50, "total": 0, "days": [0] * 7}],
                                 [week(1), week(1)], [week(2), week(0)],
                                 [week(0) for _ in range(13)]])
def test_invalid_envelopes_fail_closed(bad):
    out, _, _ = run(rows=bad)
    assert out["status"] == "invalid_source_shape" and out["weeks"] == []


def test_source_week_gap_not_fabricated_as_complete_history():
    out, _, _ = run(rows=[week(0), week(1), week(3)])
    assert out["status"] == "invalid_source_shape"
    assert out["comparison"]["status"] == "insufficient_eligible_history"


def test_zero_network_cache_repeat_and_revalidation():
    store = Store()
    first, _, called1 = run(store=store)
    second, _, called2 = run(store=store, status=503)
    assert first["status"] == second["status"] == "observed_partial"
    assert len(called1) == 1 and called2 == [] and store.used == 1
    assert second["cache_hit"] and not second["network_performed"]
    assert second["comparison"] == first["comparison"]


def test_cached_provider_rows_fail_closed_on_poisoning():
    store = Store()
    run(store=store)
    saved = next(iter(store.data.values()))
    saved["source_rows"][0]["days"] = [999] * 7
    out, _, called = run(store=store)
    assert out["status"] == "observed_partial" and not out["cache_hit"]
    assert len(called) == 1 and store.used == 2


def test_cache_identity_repository_mismatch_is_rejected():
    store = Store()
    run(store=store)
    saved = next(iter(store.data.values()))
    saved["repo"] = "another-owner/another-repo"
    out, _, called = run(store=store)
    assert out["status"] == "observed_partial" and not out["cache_hit"]
    assert len(called) == 1


@pytest.mark.parametrize("status,reason", [(401, "provider_response_error"),
                                           (403, "provider_response_error"),
                                           (404, "provider_response_error"),
                                           (429, "http_429"), (503, "http_503")])
def test_http_errors_are_not_zero_stars(status, reason):
    out, store, _ = run(status=status)
    assert out["status"] == "unavailable" and out["reason"] == reason
    assert not out["weeks"] and out["comparison"]["recent_4wk"] is None
    assert len(store.cooldowns) == (1 if status in (429, 503) else 0)


def test_existing_cooldown_is_zero_network():
    store = Store()
    store.block = True
    out, _, called = run(store=store)
    assert out["reason"] == "provider_cooldown" and out["status"] == "unavailable"
    assert not called and store.used == 0


def test_source_transport_is_fixed_host_and_no_proxy(monkeypatch):
    requests = pytest.importorskip("requests")
    class Response:
        status_code = 200
        headers = {"Content-Type": "application/json"}
        class raw:
            @staticmethod
            def read(n, *, decode_content=False):
                assert decode_content and n == gh.MAX_RESPONSE_BYTES + 1
                return json.dumps([week(0)]).encode()
        def __enter__(self): return self
        def __exit__(self, *args): return None
    class Session:
        def __init__(self): self.trust_env = True
        def get(self, url, **kw):
            assert not self.trust_env and url.startswith(gh.API)
            assert not kw["allow_redirects"] and kw["stream"]
            assert kw["headers"]["X-GitHub-Api-Version"] == "2026-03-10"
            assert kw["timeout"] == (4, 10)
            return Response()
        def close(self): pass
    monkeypatch.setattr(requests, "Session", Session)
    status, raw = gh._fetch(gh._request_url("AKzar1el", "mcp-trendpulse"),
                            {"per_page": "1", "page": "1"})
    assert status == 200 and raw[0]["total"] == 21
    with pytest.raises(ValueError):
        gh._fetch("https://evil.example/repos/owner/repo/stargazers/history",
                  {"per_page": "1", "page": "1"})


def test_upstream_exceptions_do_not_leak_secret_or_fabricate_data():
    def fail(*args):
        raise RuntimeError("token=SECRET")
    out = gh.github_star_history(owner="owner", repo="repo", cache=Store(),
                                 execute=True, fetcher=fail, observed_at=NOW)
    assert out["status"] == "unavailable" and "SECRET" not in json.dumps(out)


def test_oversized_source_response_is_invalid_not_empty():
    def fail(*args):
        raise gh.SourceTooLarge("unsafe oversized content")
    out = gh.github_star_history(owner="owner", repo="repo", cache=Store(),
                                 execute=True, fetcher=fail, observed_at=NOW)
    assert out["status"] == "invalid_source_shape"


def test_local_budget_exhaustion_no_network_and_no_leak():
    class DailyBudgetExceeded(Exception):
        pass
    cache = Store()
    cache.fail = DailyBudgetExceeded("SECRET")
    out, _, called = run(store=cache)
    assert out["reason"] == "local_daily_budget_exceeded"
    assert out["requests_attempted"] == 0 and not called
    assert "SECRET" not in json.dumps(out)
