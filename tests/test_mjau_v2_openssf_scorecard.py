"""B01 OpenSSF published Scorecard: planning, dated evidence, privacy, failures."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from mcp_trendpulse.mjau_v2 import openssf_scorecard as sc

NOW = datetime(2026, 11, 21, 4, 30, tzinfo=timezone.utc)


def payload(name="github.com/ossf/scorecard", scan="2026-11-20T12:00:00Z"):
    return {
        "date": scan,
        "repo": {"name": name, "commit": "a" * 40},
        "scorecard": {"version": "v5.7.0"},
        "score": 8.8,
        "checks": [
            {"name": "Code-Review", "score": 4, "reason": "UNTRUSTED_DETAIL"},
            {"name": "Maintained", "score": 10},
            {"name": "Token-Permissions", "score": -1},
        ],
        "external-secret": "SHOULD_NOT_APPEAR",
    }


class Store:
    def __init__(self):
        self.items = {}
        self.used = 0
        self.block = False
        self.fail = None
        self.cooldowns = []

    def cached(self, key):
        return self.items.get(key)

    def blocked(self, source):
        return self.block

    def reserve(self, source, cap, *, guard_cooldown):
        assert source == sc.SOURCE and cap == sc.CAP_PER_DAY and guard_cooldown
        if self.fail:
            raise self.fail
        self.used += 1

    def cool_down(self, source, seconds):
        self.cooldowns.append((source, seconds))

    def save(self, key, value, ttl):
        assert ttl == sc.TTL_SECONDS
        self.items[key] = value


UNSET = object()

def run(*, obj=UNSET, code=200, store=None, owner="ossf", repo="scorecard", now=NOW):
    cache = Store() if store is None else store
    called = []
    def fetch(url):
        called.append(url)
        return code, payload() if obj is UNSET else obj
    out = sc.inspect_openssf_scorecard(owner=owner, repo=repo, execute=True,
                                      cache=cache, fetcher=fetch, observed_at=now)
    return out, cache, called


def test_plan_only_zero_network_or_cache():
    def fail(_url): raise AssertionError("Unexpected network")
    out = sc.inspect_openssf_scorecard(owner="ossf", repo="scorecard", fetcher=fail)
    assert out["status"] == "planned" and out["requests_attempted"] == 0
    assert not out["network_performed"] and out["aggregate_score"] is None


@pytest.mark.parametrize("owner", ["", ".", "bad name", "abc-", "-abc", "a" * 40, None, 1])
def test_invalid_owner_rejected(owner):
    with pytest.raises(ValueError):
        sc.inspect_openssf_scorecard(owner=owner, repo="valid")


@pytest.mark.parametrize("repo", ["", ".", "..", "f/oo", "f?token=x", "a" * 101, None])
def test_invalid_repo_rejected(repo):
    with pytest.raises(ValueError):
        sc.inspect_openssf_scorecard(owner="ossf", repo=repo)


def test_execute_and_clock_validated_before_network():
    with pytest.raises(ValueError):
        sc.inspect_openssf_scorecard(owner="ossf", repo="scorecard", execute="yes")
    with pytest.raises(ValueError):
        sc.inspect_openssf_scorecard(owner="ossf", repo="scorecard", observed_at=datetime(2026, 11, 21))


def test_source_result_preserves_checks_and_inconclusive():
    out, store, called = run()
    assert out["status"] == "observed" and out["aggregate_score"] == 8.8
    assert out["reported_check_count"] == 3 and out["inconclusive_check_count"] == 1
    assert out["checks"] == [
        {"name": "Code-Review", "score": 4, "inconclusive": False},
        {"name": "Maintained", "score": 10, "inconclusive": False},
        {"name": "Token-Permissions", "score": None, "inconclusive": True},
    ]
    assert not out["verified_exploits"] and not out["revenue_or_customer_demand_verified"]
    assert out["repo_commit_scanned"] == "a"*40
    assert len(called) == 1 and store.used == 1
    assert "UNTRUSTED_DETAIL" not in json.dumps(out)
    assert "SHOULD_NOT_APPEAR" not in json.dumps(store.items)


def test_score_zero_is_valid_if_source_measures_zero():
    obj=payload()
    obj["checks"][0]["score"] = 0
    out, _, _ = run(obj=obj)
    assert out["status"] == "observed"
    assert out["checks"][0]["score"] == 0


def test_aggregate_inconclusive_is_not_zero():
    obj=payload()
    obj["score"] = -1
    out, _, _ = run(obj=obj)
    assert out["status"] == "observed" and out["aggregate_inconclusive"]
    assert out["aggregate_score"] is None


def test_unscored_repo_is_not_scored_zero():
    out, _, _ = run(code=404)
    assert out["status"] == "not_covered" and out["aggregate_score"] is None
    assert out["reason"] == "no_published_scorecard" and out["no_score_is_not_insecure"]


@pytest.mark.parametrize("bad", [
    None, [], {},
    {"repo":{}},
    dict(payload(), checks=[]),
    dict(payload(), checks=[{"name":"Maintained","score":True}]),
    dict(payload(), checks=[{"name":"Maintained","score":-2}]),
    dict(payload(), checks=[{"name":"Maintained","score":11}]),
    dict(payload(), score=True),
    dict(payload(), score=11),
    dict(payload(), date="2027-01-01T00:00:00Z"),
    dict(payload(), date="invalid"),
    dict(payload(), date="2026-11-20"),
    dict(payload(), checks=[{"name":"!!","score":5}]),
    dict(payload(), checks=[{"name":"A","score":5},{"name":"A","score":9}]),
])
def test_bad_source_envelopes_fail_closed(bad):
    out, store, _ = run(obj=bad)
    assert out["status"] == "invalid_source_shape" and out["aggregate_score"] is None
    assert store.items == {}


def test_wrong_repo_and_commit_rejected():
    out, _, _ = run(obj=payload(name="github.com/other/repo"))
    assert out["status"] == "invalid_source_shape"
    obj=payload()
    obj["repo"]["commit"] = "not-a-sha"
    out, _, _ = run(obj=obj)
    assert out["status"] == "invalid_source_shape"


def test_stale_assessment_does_not_look_fresh():
    out, store, _ = run(obj=payload(scan="2026-09-01T00:00:00Z"))
    assert out["status"] == "observed_stale"
    assert out["scan_age_days"] > 30
    assert store.items == {}


def test_cache_replay_zero_network_and_same_check_scores():
    store = Store()
    first, _, called = run(store=store)
    second, _, again = run(store=store, code=503)
    assert first["status"] == second["status"] == "observed"
    assert second["cache_hit"] and not second["network_performed"]
    assert len(called) == 1 and again == [] and store.used == 1
    assert second["checks"] == first["checks"]


def test_poisoned_cache_rejected_and_refetched():
    store = Store()
    run(store=store)
    saved = next(iter(store.items.values()))
    saved["payload"]["repo"]["name"] = "github.com/another/repo"
    out, _, called = run(store=store)
    assert out["status"] == "observed" and not out["cache_hit"]
    assert len(called) == 1 and store.used == 2


def test_expired_cache_refetched():
    store=Store()
    run(store=store)
    saved=next(iter(store.items.values()))
    saved["observed_at"]=(NOW-timedelta(hours=25)).isoformat()
    out, _, called=run(store=store)
    assert out["status"] == "observed" and not out["cache_hit"]
    assert len(called)==1


@pytest.mark.parametrize("code,reason", [
    (401,"provider_response_error"),(403,"provider_response_error"),
    (429,"http_429"),(500,"provider_response_error"),(503,"http_503"),
])
def test_http_unavailable_no_insecure_inference(code,reason):
    out, store, called = run(code=code)
    assert out["status"] == "unavailable" and out["reason"] == reason
    assert out["aggregate_score"] is None and len(called)==1
    assert len(store.cooldowns) == (1 if code in (429,503) else 0)


def test_cooldown_prevents_network():
    store=Store()
    store.block=True
    out, _, called=run(store=store)
    assert out["status"]=="unavailable" and out["reason"]=="provider_cooldown"
    assert not called and store.used == 0


def test_budget_exhaustion_redacted_without_request():
    class DailyBudgetExceeded(Exception): pass
    store=Store()
    store.fail=DailyBudgetExceeded("TOKENSECRET")
    out, _, called=run(store=store)
    assert out["reason"]=="local_daily_budget_exceeded"
    assert out["requests_attempted"]==0 and not called
    assert "TOKENSECRET" not in json.dumps(out)


def test_raw_error_not_exposed_to_user():
    def fail(_url): raise RuntimeError("password=SECRET")
    out=sc.inspect_openssf_scorecard(owner="ossf",repo="scorecard",execute=True,
                                    cache=Store(),fetcher=fail,observed_at=NOW)
    assert out["status"]=="unavailable" and "SECRET" not in json.dumps(out)


def test_body_limit_cannot_be_treated_as_no_score():
    def fail(_url): raise sc.ResponseTooLarge("secret body")
    out=sc.inspect_openssf_scorecard(owner="ossf",repo="scorecard",execute=True,
                                    cache=Store(),fetcher=fail,observed_at=NOW)
    assert out["status"]=="invalid_source_shape"


def test_transport_fixed_host_no_redirects_or_proxy(monkeypatch):
    requests=pytest.importorskip("requests")
    class Resp:
        status_code=200
        headers={"Content-Type":"application/json"}
        class raw:
            @staticmethod
            def read(n,*,decode_content=False):
                assert n==sc.MAX_BODY_BYTES+1 and decode_content
                return json.dumps(payload()).encode()
        def __enter__(self):return self
        def __exit__(self,*_args):return None
    class Session:
        def __init__(self):self.trust_env=True
        def get(self,url,**kw):
            assert not self.trust_env and url==sc._url("ossf","scorecard")
            assert kw["allow_redirects"] is False and kw["stream"] is True
            return Resp()
        def close(self):pass
    monkeypatch.setattr(requests,"Session",Session)
    status,data=sc._fetch(sc._url("ossf","scorecard"))
    assert status==200 and "checks" in data
    with pytest.raises(ValueError):
        sc._fetch("https://bad.example/projects/github.com/ossf/scorecard")
