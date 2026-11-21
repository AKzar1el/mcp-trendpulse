"""A03 deps.dev v3 proof: no-network plans, source envelope, cache, quota, errors."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from mcp_trendpulse.mjau_v2 import depsdev_graph as dep

NOW = datetime(2026, 11, 21, 4, 45, tzinfo=timezone.utc)


def node(name, version="1.0.0", *, system="NPM", relation="DIRECT",
         bundled=False, errors=None):
    return {"versionKey": {"system": system, "name": name, "version": version},
            "relation": relation, "bundled": bundled, "errors": [] if errors is None else errors}


def graph(*dependencies, error="", edges=None):
    arr = [node("is-odd", version="3.0.1", relation="SELF"), *dependencies]
    if edges is None:
        edges = [{"fromNode": 0, "toNode": i} for i in range(1, len(arr))]
    return {"nodes": arr, "edges": edges, "error": error}


class Cache:
    def __init__(self):
        self.items = {}
        self.block = False
        self.used = 0
        self.cooldowns = []
        self.fail = None
        self.ttls = []

    def cached(self, key):
        return self.items.get(key)

    def blocked(self, source):
        assert source == dep.SOURCE
        return self.block

    def reserve(self, source, cap, *, guard_cooldown):
        assert source == dep.SOURCE and cap == dep.DAILY_CAP and guard_cooldown
        if self.fail:
            raise self.fail
        self.used += 1

    def cool_down(self, source, seconds):
        self.cooldowns.append((source, seconds))

    def save(self, key, value, ttl):
        assert ttl == dep.TTL_SECONDS
        self.items[key] = value
        self.ttls.append(ttl)


UNSET = object()


def run(*, package="is-odd", version="3.0.1", system="npm",
        payload=UNSET, code=200, cache=None):
    c = cache if cache is not None else Cache()
    called = []
    def fetch(url):
        called.append(url)
        return code, (graph(node("is-number", version="6.0.0"))
                      if payload is UNSET else payload)
    out = dep.inspect_package_dependencies(
        ecosystem=system, package=package, version=version,
        execute=True, cache=c, fetcher=fetch, observed_at=NOW)
    return out, c, called


def test_plan_only_never_network_or_cache():
    x = dep.inspect_package_dependencies(ecosystem="npm", package="is-odd", version="3.0.1")
    assert x["status"] == "planned" and not x["network_performed"]
    assert x["source_url"].endswith("/is-odd/versions/3.0.1:dependencies")
    assert x["summary"] is None and not x["download_count_verified"]


@pytest.mark.parametrize("system", ["", "go", "rubyGems", 6, None])
def test_reject_unsupported_resolved_graph_ecosystems(system):
    with pytest.raises(ValueError):
        dep.inspect_package_dependencies(ecosystem=system, package="abc", version="1.0")


@pytest.mark.parametrize("package", ["", ".", "..", "invalid name", "foo?token=1",
                                      "%2f", "bad\nname", "a/../b", "a//b", "a"*161, None])
def test_reject_invalid_package_names(package):
    with pytest.raises(ValueError):
        dep.inspect_package_dependencies(ecosystem="npm", package=package, version="1.0")


@pytest.mark.parametrize("version", ["", ".", "..", "1/2", "1?x", "1\n2", "1"*101, None])
def test_reject_bad_concrete_versions(version):
    with pytest.raises(ValueError):
        dep.inspect_package_dependencies(ecosystem="npm", package="abc", version=version)


def test_execute_flag_and_clock_must_be_valid():
    with pytest.raises(ValueError):
        dep.inspect_package_dependencies(ecosystem="npm", package="abc",
                                         version="1", execute="yes")
    with pytest.raises(ValueError):
        dep.inspect_package_dependencies(ecosystem="npm", package="abc",
                                         version="1", observed_at=datetime(2026, 11, 21))


def test_scoped_npm_url_is_encoded_not_path_injection():
    url = dep._url("NPM", "@scope/pkg", "1.2.3+beta")
    assert "/packages/%40scope%2Fpkg/" in url
    assert "/versions/1.2.3%2Bbeta:dependencies" in url


def test_valid_graph_provides_new_distinct_relationship_evidence():
    out, store, calls = run()
    assert out["status"] == "observed" and len(calls) == 1 and store.used == 1
    assert out["root"] == {"ecosystem":"NPM", "package":"is-odd", "version":"3.0.1"}
    assert out["summary"]["distinct_direct_dependency_versions"] == 1
    assert out["direct_preview"] == [{"ecosystem":"NPM","package":"is-number","version":"6.0.0"}]
    assert out["summary"]["graph_edge_count"] == 1
    assert not out["customer_demand_verified"] and not out["download_count_verified"]
    assert out["graph_scope"] == "provider_resolved_generic_64bit_linux_single_version"
    assert out["requests_attempted"] == 1 and out["network_performed"]


def test_no_dependencies_is_observed_zero_not_no_data():
    out, _, _ = run(payload=graph())
    assert out["status"] == "observed"
    assert out["summary"]["root_only_zero_dependencies_observed"]
    assert out["summary"]["distinct_resolved_dependency_versions"] == 0


def test_distinguish_duplicate_version_keys_from_graph_nodes():
    out, _, _ = run(payload=graph(node("is-number"), node("is-number")))
    assert out["status"] == "observed"
    assert out["summary"]["resolved_dependency_node_instances"] == 2
    assert out["summary"]["distinct_direct_dependency_versions"] == 1


def test_indirect_and_bundled_counts_are_source_scoped():
    out, _, _ = run(payload=graph(node("one"), node("two", relation="INDIRECT", bundled=True)))
    s = out["summary"]
    assert s["direct_dependency_node_instances"] == 1
    assert s["indirect_dependency_node_instances"] == 1
    assert s["bundled_node_instances"] == 1


def test_graph_with_resolution_errors_is_partial_not_success_and_not_cached():
    store = Cache()
    out, _, _ = run(payload=graph(node("one", errors=["transitive resolution failure"])), cache=store)
    assert out["status"] == "observed_partial"
    assert out["summary"]["graph_has_resolution_errors"]
    assert not store.items
    out, _, _ = run(payload=graph(node("one"), error="incomplete graph"), cache=Cache())
    assert out["status"] == "observed_partial"


@pytest.mark.parametrize("bad", [
    None, "invalid", {}, {"nodes": [], "edges": []},
    {"nodes": [node("abc", relation="SELF")], "edges": "oops"},
    {"nodes": [node("abc", relation="SELF")], "edges": [], "error": 42},
    {"nodes": [node("abc", relation="SELF")], "edges": [], "error": "x"*4097},
    {"nodes": [node("abc", relation="SELF")]*513, "edges":[]},
    {"nodes": [node("abc", relation="SELF")], "edges":[{}]},
    {"nodes": [node("abc", relation="SELF")], "edges":[{"fromNode":0,"toNode":True}]},
    {"nodes": [node("abc", relation="SELF")], "edges":[{"fromNode":0,"toNode":5}]},
    {"nodes": [node("abc", relation="SELF")], "edges":[{"fromNode":-1,"toNode":0}]},
    {"nodes": [node("abc", relation="SELF"), node("two", relation="SELF")], "edges":[]},
    {"nodes": [node("abc", relation="DIRECT")], "edges":[]},
    {"nodes": [node("abc", relation="SELF", system="PYPI")], "edges":[]},
    {"nodes": [node("abc", relation="SELF", errors="leak")], "edges":[]},
])
def test_invalid_envelope_cannot_be_called_zero_data(bad):
    out, store, _ = run(payload=bad)
    assert out["status"] == "invalid_source_shape"
    assert out["root"] is None and out["summary"] is None
    assert not store.items


def test_cache_replay_proves_zero_network():
    cache = Cache()
    first, _, called = run(cache=cache)
    second, _, second_calls = run(cache=cache, code=503)
    assert first["status"] == second["status"] == "observed"
    assert first["network_performed"] and not second["network_performed"]
    assert second["cache_hit"] and second["requests_attempted"] == 0
    assert cache.used == 1 and len(called) == 1 and second_calls == []


def test_poisoned_dependency_cache_rejected_and_refetched():
    cache = Cache()
    run(cache=cache)
    key = next(iter(cache.items))
    cache.items[key]["payload"]["nodes"][1]["versionKey"]["name"] = "\0hidden"
    out, _, called = run(cache=cache)
    assert out["status"] == "observed" and not out["cache_hit"]
    assert len(called) == 1 and cache.used == 2


def test_expired_cache_not_used():
    cache = Cache()
    run(cache=cache)
    key = next(iter(cache.items))
    cache.items[key]["observed_at"] = (NOW-timedelta(hours=13)).isoformat()
    out, _, called = run(cache=cache)
    assert out["status"] == "observed" and not out["cache_hit"] and len(called) == 1


def test_foreign_scope_cache_rejected():
    cache = Cache()
    run(cache=cache)
    key = next(iter(cache.items))
    cache.items[key]["requested"]["ecosystem"] = "PYPI"
    out, _, called = run(cache=cache)
    assert out["status"] == "observed" and len(called) == 1 and not out["cache_hit"]


@pytest.mark.parametrize("code,reason", [(401,"provider_response_error"),(403,"provider_response_error"),
                                           (404,"provider_response_error"),(429,"http_429"),
                                           (500,"provider_response_error"),(503,"http_503")])
def test_unavailable_http_never_yields_zero_dependencies(code, reason):
    out, cache, called = run(code=code)
    assert out["status"] == "unavailable" and out["reason"] == reason
    assert out["summary"] is None and out["root"] is None and len(called) == 1
    assert len(cache.cooldowns) == (1 if code in (429,503) else 0)


def test_existing_cooldown_prevents_network():
    cache = Cache()
    cache.block = True
    out, cache, called = run(cache=cache)
    assert out["status"] == "unavailable" and out["reason"] == "provider_cooldown"
    assert not called and cache.used == 0


def test_daily_budget_exhaustion_redacted_and_no_request():
    class DailyBudgetExceeded(Exception):
        pass
    cache = Cache()
    cache.fail = DailyBudgetExceeded("SECRET_API_KEY")
    out, _, called = run(cache=cache)
    assert out["reason"] == "local_daily_budget_exceeded"
    assert out["requests_attempted"] == 0 and not called
    assert "SECRET_API_KEY" not in json.dumps(out)


def test_source_exception_not_echoed_to_user():
    cache = Cache()
    def fail(_url):
        raise RuntimeError("Authorization: Bearer SENSITIVE")
    out = dep.inspect_package_dependencies(ecosystem="NPM", package="is-odd",
        version="3.0.1", execute=True, cache=cache, fetcher=fail, observed_at=NOW)
    assert out["status"] == "unavailable"
    assert "SENSITIVE" not in json.dumps(out)


def test_oversized_source_is_invalid_not_zero():
    def fail(_url):
        raise dep.ResponseTooLarge("do not expose raw payload")
    out = dep.inspect_package_dependencies(ecosystem="NPM",package="is-odd",
       version="3.0.1",execute=True,cache=Cache(),fetcher=fail,observed_at=NOW)
    assert out["status"] == "invalid_source_shape" and out["reason"] == "response_oversized"


def test_transport_session_fixed_host_no_proxy_or_redirects(monkeypatch):
    requests = pytest.importorskip("requests")
    class Response:
        status_code = 200
        headers = {"Content-Type":"application/json"}
        class raw:
            @staticmethod
            def read(n, *, decode_content=False):
                assert decode_content and n == dep.MAX_BYTES + 1
                return json.dumps(graph(node("is-number"))).encode()
        def __enter__(self): return self
        def __exit__(self,*_args): return None
    class Session:
        def __init__(self): self.trust_env = True
        def get(self,url,**kwargs):
            assert self.trust_env is False
            assert url.startswith("https://api.deps.dev/")
            assert kwargs["allow_redirects"] is False and kwargs["stream"] is True
            assert kwargs["timeout"] == (4,12)
            return Response()
        def close(self): pass
    monkeypatch.setattr(requests,"Session",Session)
    code, body = dep._fetch(dep._url("NPM","is-odd","3.0.1"))
    assert code == 200 and body["nodes"]
    with pytest.raises(ValueError):
        dep._fetch("https://evil.example/v3/systems/npm/packages/x/versions/1:dependencies")


def test_root_can_be_pypi_with_no_direct_dependencies():
    obj = {"nodes":[node("colorama","0.4.6",system="PYPI",relation="SELF")],
           "edges":[],"error":""}
    out, _, _ = run(system="pypi", package="colorama", version="0.4.6", payload=obj)
    assert out["root"]["ecosystem"] == "PYPI" and out["root"]["package"] == "colorama"
    assert out["summary"]["root_only_zero_dependencies_observed"]


def test_no_user_secrets_or_unbounded_root_error_in_persisted_cache():
    cache = Cache()
    p = graph(node("is-number"))
    p["provider_internal_access_token"] = "SECRET"
    out, cache, _ = run(payload=p, cache=cache)
    assert out["status"] == "observed"
    assert "SECRET" not in json.dumps(cache.items) and "SECRET" not in json.dumps(out)
