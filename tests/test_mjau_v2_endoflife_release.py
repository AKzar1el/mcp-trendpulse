"""B02 free endoflife.date v1 source: dates, states, failure and cache cases."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from mcp_trendpulse.mjau_v2 import endoflife_release as eol

NOW = datetime(2026, 11, 21, 4, 50, tzinfo=timezone.utc)


def payload(cycle="22", generated="2026-11-21T00:08:00+00:00"):
    return {"schema_version": "1.2.1", "generated_at": generated,
            "last_modified": None, "result": {
                "name": cycle, "releaseDate": "2024-04-24",
                "isLts": True, "ltsFrom": "2024-10-29",
                "isEoas": True, "eoasFrom": "2025-10-21",
                "isEol": False, "eolFrom": "2027-04-30",
                "isEoes": None, "eoesFrom": None,
                "isMaintained": True, "latest": {"name": "22.17.0"},
                "internal_unsupported_custom": "SECRET_NOTE",
            }}


class Cache:
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
        assert source == eol.SOURCE and cap == eol.CAP_PER_DAY and guard_cooldown
        if self.fail:
            raise self.fail
        self.used += 1

    def cool_down(self, source, seconds):
        self.cooldowns.append((source, seconds))

    def save(self, key, value, ttl):
        assert ttl == eol.TTL_SECONDS
        self.data[key] = value


UNSET = object()

def run(*, product="nodejs", release="22", obj=UNSET, code=200, cache=None,
        now=NOW):
    store = cache if cache is not None else Cache()
    called = []
    def fetch(url):
        called.append(url)
        return code, payload() if obj is UNSET else obj
    out = eol.observe_release_support(
        product=product, release=release, execute=True, cache=store,
        fetcher=fetch, observed_at=now)
    return out, store, called


def test_plan_only_no_io():
    def fail(_url): raise AssertionError("network!")
    out = eol.observe_release_support(product="nodejs", release="22", fetcher=fail)
    assert out["status"] == "planned" and out["requests_attempted"] == 0
    assert out["is_eol"] is None and out["calendar_days_until_reported_eol"] is None


@pytest.mark.parametrize("product", ["", "Node.js", "no/repo", "a?x", ".", "..", "abc--_", None, 1, "x"*81])
def test_invalid_product_refused(product):
    with pytest.raises(ValueError):
        eol.observe_release_support(product=product, release="22")


@pytest.mark.parametrize("release", ["", "a/b", "with space", "a?x=1", "..", 1, None, "a"*81])
def test_invalid_release_refused(release):
    with pytest.raises(ValueError):
        eol.observe_release_support(product="nodejs", release=release)


def test_wrong_execute_or_naive_clock_rejected():
    with pytest.raises(ValueError):
        eol.observe_release_support(product="nodejs", release="22", execute="yes")
    with pytest.raises(ValueError):
        eol.observe_release_support(product="nodejs", release="22", observed_at=datetime(2026,11,21))


def test_real_source_semantics_end_of_active_support_is_not_eol():
    out, store, called = run()
    assert out["status"] == "observed" and len(called) == 1 and store.used == 1
    assert out["release"] == "22" and out["is_eoas"] is True and out["is_eol"] is False
    assert out["is_maintained"] is True
    assert out["eoas_from"] == "2025-10-21"
    assert out["eol_from"] == "2027-04-30"
    assert out["calendar_days_until_reported_eol"] > 0
    assert out["community_curated_not_vendor_certified"]
    assert not out["commercial_migration_budget_verified"]


def test_date_future_and_past_scopes_are_distinct():
    obj=payload()
    obj["result"]["isEol"] = True
    obj["result"]["eolFrom"] = "2025-01-01"
    obj["result"]["isMaintained"] = False
    out, _, _=run(obj=obj)
    assert out["status"] == "observed"
    assert out["calendar_days_until_reported_eol"] < 0 and out["is_eol"] is True


def test_unknown_date_is_not_zero_or_unmaintained():
    obj=payload()
    obj["result"]["eolFrom"] = None
    obj["result"]["isEoas"] = None
    out, _, _=run(obj=obj)
    assert out["status"] == "observed"
    assert out["eol_from"] is None and out["calendar_days_until_reported_eol"] is None
    assert out["is_maintained"] is True and out["unknown_date_is_not_zero_or_no_support"]


@pytest.mark.parametrize("bad", [
    None, [], {}, {"schema_version":"1.2.1"},
    dict(payload(), result={}),
    dict(payload(), generated_at="2026-11-21"),
    dict(payload(), generated_at="2027-01-01T00:00:00Z"),
    dict(payload(), schema_version=None),
    dict(payload(), result=dict(payload()["result"], name="20")),
    dict(payload(), result=dict(payload()["result"], isEol="false")),
    dict(payload(), result=dict(payload()["result"], isMaintained=None)),
    dict(payload(), result=dict(payload()["result"], eolFrom="2026-02-30")),
    dict(payload(), result=dict(payload()["result"], eoasFrom="not-a-date")),
    dict(payload(), result=dict(payload()["result"], isEoas="true")),
])
def test_bad_provider_payload_is_not_valid_eol_evidence(bad):
    out, store, _ = run(obj=bad)
    assert out["status"] == "invalid_source_shape"
    assert store.data == {}


def test_provider_duplicate_custom_metadata_not_stored():
    obj=payload()
    obj["provider_secret"]="do-not-cache"
    out, store, _=run(obj=obj)
    assert out["status"] == "observed"
    assert "do-not-cache" not in json.dumps(out)
    assert "do-not-cache" not in json.dumps(store.data)
    assert "SECRET_NOTE" not in json.dumps(store.data)


def test_stale_generation_is_visibly_stale_not_current():
    out, store, _=run(obj=payload(generated="2026-09-01T00:00:00Z"))
    assert out["status"] == "observed_stale" and out["source_age_days"] > 30
    assert store.data == {}


def test_cache_replay_uses_no_network_and_keeps_dates():
    store=Cache()
    first, store, called=run(cache=store)
    second, store, again=run(cache=store, code=503)
    assert first["status"] == second["status"] == "observed"
    assert len(called) == 1 and again == [] and store.used == 1
    assert second["cache_hit"] is True and not second["network_performed"]
    assert first["eol_from"] == second["eol_from"]


def test_cache_poisoned_cycle_is_rejected():
    store=Cache()
    run(cache=store)
    cached=next(iter(store.data.values()))
    cached["payload"]["result"]["name"]="20"
    out, _, called=run(cache=store)
    assert out["status"] == "observed" and not out["cache_hit"]
    assert len(called) == 1 and store.used == 2


def test_expired_cache_refetched():
    store=Cache()
    run(cache=store)
    v=next(iter(store.data.values()))
    v["observed_at"]=(NOW-timedelta(hours=26)).isoformat()
    out, _, called=run(cache=store)
    assert out["status"]=="observed" and not out["cache_hit"] and len(called)==1


def test_http_404_unknown_not_zero_market_or_expired():
    out, _, _=run(code=404)
    assert out["status"]=="not_found" and out["is_eol"] is None
    assert out["reason"]=="unknown_product_or_release"


@pytest.mark.parametrize("code,reason", [(301,"rename_redirect_not_followed"),
                                          (401,"provider_response_error"),
                                          (403,"provider_response_error"),
                                          (429,"http_429"),
                                          (500,"provider_response_error"),
                                          (503,"http_503")])
def test_transport_failures_not_fake_eol(code,reason):
    out, store, _=run(code=code)
    assert out["status"]=="unavailable" and out["reason"]==reason
    assert out["is_eol"] is None
    assert len(store.cooldowns)==(1 if code in (429,503) else 0)


def test_provider_cooldown_no_network():
    store=Cache()
    store.block=True
    out, _, called=run(cache=store)
    assert out["status"]=="unavailable" and out["reason"]=="provider_cooldown"
    assert not called and store.used == 0


def test_budget_cap_prevents_call():
    class DailyBudgetExceeded(Exception):pass
    store=Cache()
    store.fail=DailyBudgetExceeded("secret")
    out, _, called=run(cache=store)
    assert out["status"]=="unavailable"
    assert out["reason"]=="local_daily_budget_exceeded"
    assert out["requests_attempted"]==0 and not called
    assert "secret" not in json.dumps(out)


def test_transport_exception_redacted():
    def fail(_url):raise RuntimeError("token=PRIVATE")
    out=eol.observe_release_support(product="nodejs",release="22",execute=True,
        cache=Cache(),fetcher=fail,observed_at=NOW)
    assert out["status"]=="unavailable" and "PRIVATE" not in json.dumps(out)


def test_oversized_response_fails_closed():
    def fail(_url):raise eol.ResponseTooLarge("raw danger")
    out=eol.observe_release_support(product="nodejs",release="22",execute=True,
        cache=Cache(),fetcher=fail,observed_at=NOW)
    assert out["status"]=="invalid_source_shape" and out["reason"]=="response_oversized"


def test_requests_transport_fixed_host_no_redirect_or_proxy(monkeypatch):
    requests=pytest.importorskip("requests")
    class Response:
        status_code=200
        headers={"Content-Type":"application/json"}
        class raw:
            @staticmethod
            def read(n,*,decode_content=False):
                assert n==eol.MAX_BYTES+1 and decode_content
                return json.dumps(payload()).encode()
        def __enter__(self):return self
        def __exit__(self,*args):return None
    class Session:
        def __init__(self):self.trust_env=True
        def get(self,url,**kw):
            assert not self.trust_env and url==eol._url("nodejs","22")
            assert kw["allow_redirects"] is False and kw["stream"] is True
            assert kw["timeout"]==(4,12)
            return Response()
        def close(self):pass
    monkeypatch.setattr(requests,"Session",Session)
    code,data=eol._fetch(eol._url("nodejs","22"))
    assert code==200 and data["result"]["name"]=="22"
    with pytest.raises(ValueError):
        eol._fetch("https://evil.example/api/v1/products/nodejs/releases/22")
