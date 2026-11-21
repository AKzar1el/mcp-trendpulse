"""A07 Hub catalog metadata: bounded, keyless, current snapshot evidence."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from mcp_trendpulse.mjau_v2 import hf_catalog as hf

NOW = datetime(2026, 11, 21, 6, 0, tzinfo=timezone.utc)


def model(name="example/alpha-2", score=113.5):
    return {"id": name, "modelId": name, "private": False,
            "trendingScore": score, "downloads": 60, "likes": 11,
            "createdAt": "2026-11-20T00:00:00Z", "gated": None,
            "untrusted": "TOKEN_NEVER_COPY"}


def dataset(name="example/fixture"):
    return {"id": name, "private": False, "trendingScore": 23,
            "downloads": 340, "likes": 18, "createdAt": "2026-10-10T12:00:00Z",
            "lastModified": "2026-11-20T10:00:00Z", "gated": "auto",
            "description": "not emitted", "tags": ["security", "example"]}


class Cache:
    def __init__(self):
        self.data = {}
        self.used = 0
        self.block = False
        self.cooldowns = []
        self.fail = None

    def cached(self, key):
        return self.data.get(key)

    def blocked(self, source):
        assert source == hf.SOURCE
        return self.block

    def reserve(self, source, cap, *, guard_cooldown):
        assert source == hf.SOURCE and cap == hf.CAP_PER_DAY and guard_cooldown
        if self.fail:
            raise self.fail
        self.used += 1

    def cool_down(self, source, seconds):
        self.cooldowns.append((source, seconds))

    def save(self, key, value, ttl):
        assert ttl == hf.TTL_SECONDS
        self.data[key] = value


UNSET = object()


def run(*, kind="models", result=UNSET, code=200, cache=None,
        limit=3, search="", now=NOW):
    c = cache if cache is not None else Cache()
    called = []
    def fetch(url, params):
        called.append((url, params))
        return code, ([model()] if kind == "models" else [dataset()]) if result is UNSET else result
    out = hf.discover_hf_catalog(kind=kind, limit=limit, search=search,
                                  execute=True, cache=c, fetcher=fetch,
                                  observed_at=now)
    return out, c, called


def test_plan_only_never_uses_network_or_sqlite():
    def fail(*_):
        raise AssertionError("Unexpected network")
    out=hf.discover_hf_catalog(kind="models",limit=2,fetcher=fail)
    assert out["status"] == "planned" and not out["network_performed"]
    assert out["records"] == [] and out["requests_attempted"] == 0
    assert "trendingScore" in out["request_url"] and not out["customer_demand_verified"]


@pytest.mark.parametrize("kind", ["", "model", "Spaces", "datasets/secret", None, 3])
def test_source_kind_must_be_models_or_datasets(kind):
    with pytest.raises(ValueError):
        hf.discover_hf_catalog(kind=kind)


@pytest.mark.parametrize("limit", [-1, 0, 9, True, 2.0, "3"])
def test_page_size_is_strictly_bounded(limit):
    with pytest.raises(ValueError):
        hf.discover_hf_catalog(kind="models",limit=limit)


@pytest.mark.parametrize("search", ["x", "bad\nquery", "bad?token", "../../hidden",
                                     "a"*65, None, 123])
def test_search_is_bounded_safe_phrase(search):
    with pytest.raises(ValueError):
        hf.discover_hf_catalog(kind="models",search=search)


def test_nonboolean_execute_or_naive_clock_rejected():
    with pytest.raises(ValueError):
        hf.discover_hf_catalog(kind="models",execute="yes")
    with pytest.raises(ValueError):
        hf.discover_hf_catalog(kind="models",observed_at=datetime(2026,11,21))


def test_model_snapshot_is_source_scoped_not_trend_growth():
    out,cache,called=run()
    assert out["status"]=="observed_partial" and len(called)==1 and cache.used==1
    row=out["records"][0]
    assert row["repository_id"]=="example/alpha-2"
    assert row["source_detail_url"]=="https://huggingface.co/example/alpha-2"
    assert row["provider_trending_score"]==113.5
    assert row["provider_downloads"]==60 and row["provider_likes"]==11
    assert out["comparative_time_series_provided"] is False
    assert out["model_quality_verified"] is False and out["buyer_demand_verified"] is False
    assert out["scope"].startswith("one_bounded_page")


def test_dataset_gated_is_labeled_but_no_download():
    out,_,_=run(kind="datasets")
    assert out["status"]=="observed_partial"
    assert out["records"][0]["gated"]=="auto"
    assert out["records"][0]["source_detail_url"]=="https://huggingface.co/datasets/example/fixture"
    assert out["records"][0]["created_at"].endswith("+00:00")
    assert out["records"][0]["last_modified_at"].endswith("+00:00")
    assert out["model_weights_or_dataset_files_downloaded"] is False


def test_search_is_passthrough_name_filter_not_semantic_pain_research():
    out, _, called = run(search="example",result=[model()])
    assert len(called)==1 and called[0][1]["search"]=="example"
    assert len(out["records"])==1 and not out["customer_demand_verified"]


def test_unnamed_or_other_topic_rows_are_not_misclassified_as_matches():
    out,cache,_=run(search="alpha",result=[model("someone/unrelated")])
    assert out["status"]=="invalid_source_shape" and out["records"]==[]
    assert not cache.data


def test_hidden_private_items_rejected_not_persisted():
    p=model()
    p["private"]=True
    out,cache,_=run(result=[p])
    assert out["status"]=="invalid_source_shape"
    assert not cache.data


def test_mixed_valid_and_private_is_partial_and_not_cached():
    bad=model("other/private")
    bad["private"]=True
    out,cache,_=run(result=[model(),bad])
    assert out["status"]=="observed_partial" and out["rejected_rows"]==1
    assert len(out["records"])==1 and not cache.data


def test_duplicate_repo_ids_do_not_double_count():
    out,cache,_=run(result=[model(),model()])
    assert out["status"]=="observed_partial" and out["rejected_rows"]==1
    assert not cache.data


def test_empty_list_is_no_catalog_matches_not_zero_adoption():
    out,_,_=run(result=[])
    assert out["status"]=="no_data" and out["records"]==[]
    assert not out["customer_demand_verified"]


@pytest.mark.parametrize("bad", [
    None, {}, "hello", [None], [[1]], [model()] * 9,
    [{"id":"bad name","private":False}],
    [{"id":"example/secret","private":True}],
    [{"id":"example/alpha-2","modelId":"example/different","private":False}],
    [dict(model(), downloads=-1)],
    [dict(model(), downloads=True)],
    [dict(model(), likes=1.5)],
    [dict(model(), trendingScore=-1)],
    [dict(model(), trendingScore=float("nan"))],
    [dict(model(), createdAt="2028-01-01T00:00:00Z")],
    [dict(model(), createdAt="2026-11-21")],
    [dict(model(), gated=0)],
    [dict(model(), gated="unexpected-string")],
])
def test_invalid_records_fail_closed(bad):
    out,cache,_=run(result=bad)
    assert out["status"]=="invalid_source_shape" and out["records"]==[]
    assert not cache.data


def test_missing_metrics_are_unknown_not_zero():
    m=model()
    for k in ("likes","downloads","trendingScore","createdAt"):
        del m[k]
    out,_,_=run(result=[m])
    assert out["status"]=="observed_partial"
    row=out["records"][0]
    assert row["provider_likes"] is None
    assert row["provider_downloads"] is None
    assert row["provider_trending_score"] is None
    assert row["created_at"] is None


def test_cache_hit_is_zero_network_and_no_secret_leak():
    c=Cache()
    out,c,first_called=run(cache=c)
    cached,c,called=run(cache=c,code=503)
    assert out["status"]==cached["status"]=="observed_partial"
    assert cached["cache_hit"] and not cached["network_performed"]
    assert not called and len(first_called)==1 and c.used==1
    assert cached["records"]==out["records"]
    assert "TOKEN_NEVER_COPY" not in json.dumps(c.data)
    assert "TOKEN_NEVER_COPY" not in json.dumps(out)


def test_poisoned_cache_refetched_not_emitted():
    c=Cache()
    run(cache=c)
    k=next(iter(c.data))
    c.data[k]["payload"][0]["id"]="bad path/hidden"
    out,c,called=run(cache=c)
    assert out["status"]=="observed_partial" and not out["cache_hit"]
    assert len(called)==1 and c.used==2


def test_expired_cache_does_not_hide_provider_failure():
    c=Cache()
    run(cache=c)
    k=next(iter(c.data))
    c.data[k]["observed_at"]=(NOW-timedelta(hours=7)).isoformat()
    out,c,called=run(cache=c,code=503)
    assert out["status"]=="unavailable" and len(called)==1


@pytest.mark.parametrize("code,reason", [(401,"provider_response_error"),
                                          (403,"provider_response_error"),
                                          (429,"http_429"), (500,"provider_response_error"),
                                          (503,"http_503")])
def test_bad_http_no_false_empty_adoption(code,reason):
    out,c,called=run(code=code)
    assert out["status"]=="unavailable" and out["reason"]==reason
    assert out["records"]==[] and len(called)==1
    assert len(c.cooldowns)==(1 if code in (429,503) else 0)


def test_existing_cooldown_skips_network():
    c=Cache()
    c.block=True
    out,c,called=run(cache=c)
    assert out["status"]=="unavailable" and out["reason"]=="provider_cooldown"
    assert not called and c.used==0


def test_budget_exhaustion_leaks_no_credentials():
    class DailyBudgetExceeded(Exception):
        pass
    c=Cache()
    c.fail=DailyBudgetExceeded("SECRET_A07")
    out,c,called=run(cache=c)
    assert out["status"]=="unavailable" and out["reason"]=="local_daily_budget_exceeded"
    assert out["requests_attempted"]==0 and not called
    assert "SECRET_A07" not in json.dumps(out)


def test_provider_exception_cannot_leak_sensitive_url():
    def fail(*_):raise RuntimeError("Bearer SECRET")
    out=hf.discover_hf_catalog(kind="models",execute=True,cache=Cache(),
                               fetcher=fail,observed_at=NOW)
    assert out["status"]=="unavailable" and "SECRET" not in json.dumps(out)


def test_oversized_response_is_invalid_not_empty():
    def fail(*_):raise hf.ResponseTooLarge("raw SOURCE SECRET")
    out=hf.discover_hf_catalog(kind="models",execute=True,cache=Cache(),
                               fetcher=fail,observed_at=NOW)
    assert out["status"]=="invalid_source_shape"
    assert out["reason"]=="response_oversized"


def test_transport_fixed_host_no_redirect_or_proxy(monkeypatch):
    requests=pytest.importorskip("requests")
    class Resp:
        status_code=200
        headers={"Content-Type":"application/json"}
        class raw:
            @staticmethod
            def read(n,*,decode_content=False):
                assert n==hf.MAX_BYTES+1 and decode_content
                return json.dumps([model()]).encode()
        def __enter__(self):return self
        def __exit__(self,*_):return None
    class Sess:
        def __init__(self):self.trust_env=True
        def get(self,url,**kw):
            assert not self.trust_env and url==hf._url("models")
            assert kw["allow_redirects"] is False and kw["stream"] is True
            return Resp()
        def close(self):pass
    monkeypatch.setattr(requests,"Session",Sess)
    status,body=hf._fetch(hf._url("models"),hf._params(3,""))
    assert status==200 and body[0]["id"]=="example/alpha-2"
    with pytest.raises(ValueError):
        hf._fetch("https://evil.example/api/models",hf._params(3,""))
