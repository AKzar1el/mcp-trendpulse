"""V2 integration: provider-safe free-only MCP tools, no global surface change."""
from __future__ import annotations

import asyncio

import pytest

from mcp_trendpulse.intelligence_mcp import (
    intel_mcp,
    intelligence_dependency_graph,
    intelligence_repository_scorecard,
    intelligence_repository_star_history,
    intelligence_release_lifecycle,
    intelligence_hf_catalog,
)


def test_five_new_tools_registered_only_in_opt_in_intelligence_mcp():
    tools = asyncio.run(intel_mcp.list_tools())
    names = {tool.name for tool in tools}
    assert "intelligence_dependency_graph" in names
    assert "intelligence_repository_scorecard" in names
    assert "intelligence_repository_star_history" in names
    assert "intelligence_release_lifecycle" in names
    assert "intelligence_hf_catalog" in names
    assert len(names) == 19
    for tool in tools:
        if tool.name in {"intelligence_dependency_graph",
                         "intelligence_repository_scorecard",
                         "intelligence_repository_star_history",
                         "intelligence_release_lifecycle",
                         "intelligence_hf_catalog"}:
            assert tool.annotations.readOnlyHint is True
            assert tool.annotations.destructiveHint is False


def test_existing_public_hosted_and_community_tools_unchanged():
    from mcp_trendpulse.hosted import hosted_mcp
    # Community 16-tool registry is independent; hosted has six tools.
    assert len(asyncio.run(hosted_mcp.list_tools())) == 6


def test_dependency_and_scorecard_plan_never_touch_sqlite_or_network(monkeypatch):
    import sqlite3
    import requests

    def forbid(*_args, **_kwargs):
        raise AssertionError("Plan-only called an I/O source")

    monkeypatch.setattr(sqlite3, "connect", forbid)
    monkeypatch.setattr(requests.Session, "get", forbid)
    dependency = intelligence_dependency_graph("npm", "is-odd", "3.0.1")
    score = intelligence_repository_scorecard("pallets", "flask")
    stars = intelligence_repository_star_history("fastapi", "fastapi")
    lifecycle = intelligence_release_lifecycle("nodejs", "20")
    hf_catalog = intelligence_hf_catalog("models", limit=2)
    for result in (dependency, score, stars, lifecycle, hf_catalog):
        assert result["status"] == "planned"
        assert result["requests_attempted"] == 0
        assert result["network_performed"] is False
        assert result["cache_hit"] is False


@pytest.mark.parametrize("value", ["", "not an ecosystem", "GO"])
def test_bad_dependency_ecosystem_fails_without_network(value):
    with pytest.raises(ValueError):
        intelligence_dependency_graph(value, "pkg", "1.0", execute=True)


def test_bad_repository_identifier_fails_without_network():
    with pytest.raises(ValueError):
        intelligence_repository_scorecard("pallets", "../escape", execute=True)


def test_execute_requires_real_boolean():
    with pytest.raises(ValueError):
        intelligence_dependency_graph("npm", "is-odd", "3.0.1", execute="yes")
    with pytest.raises(ValueError):
        intelligence_repository_scorecard("pallets", "flask", execute="yes")
    with pytest.raises(ValueError):
        intelligence_repository_star_history("fastapi", "fastapi", execute="yes")
    with pytest.raises(ValueError):
        intelligence_release_lifecycle("nodejs", "20", execute="yes")
    with pytest.raises(ValueError):
        intelligence_hf_catalog("models", execute="yes")


def test_explicit_execute_uses_original_isolated_sqlite_cache(monkeypatch, tmp_path):
    from mcp_trendpulse import intelligence_core
    from mcp_trendpulse.mjau_v2 import depsdev_graph, openssf_scorecard

    store = intelligence_core.BudgetCache(tmp_path / "v2-proof")
    monkeypatch.setattr(intelligence_core, "BudgetCache",
                        lambda root=None: store)
    calls = {"deps": 0, "score": 0}

    def deps_fetch(_url):
        calls["deps"] += 1
        return 200, {
            "nodes": [
                {"versionKey": {"system": "NPM", "name": "is-odd",
                                "version": "3.0.1"},
                 "relation": "SELF", "bundled": False, "errors": []},
                {"versionKey": {"system": "NPM", "name": "is-number",
                                "version": "6.0.0"},
                 "relation": "DIRECT", "bundled": False, "errors": []},
            ],
            "edges": [{"fromNode": 0, "toNode": 1}],
            "error": "",
        }

    def score_fetch(_url):
        from datetime import datetime, timezone

        calls["score"] += 1
        today = datetime.now(timezone.utc).date().isoformat()
        return 200, {
            "date": today,
            "repo": {"name": "github.com/pallets/flask",
                     "commit": "a" * 40},
            "scorecard": {"version": "v5.7.0"},
            "score": 7.1,
            "checks": [{"name": "Maintained", "score": 10},
                       {"name": "Code-Review", "score": 4}],
        }

    monkeypatch.setattr(depsdev_graph, "_fetch", deps_fetch)
    monkeypatch.setattr(openssf_scorecard, "_fetch", score_fetch)
    first_deps = intelligence_dependency_graph(
        "npm", "is-odd", "3.0.1", execute=True,
    )
    repeat_deps = intelligence_dependency_graph(
        "npm", "is-odd", "3.0.1", execute=True,
    )
    first_score = intelligence_repository_scorecard(
        "pallets", "flask", execute=True,
    )
    repeat_score = intelligence_repository_scorecard(
        "pallets", "flask", execute=True,
    )
    assert first_deps["status"] == "observed"
    assert first_deps["summary"]["distinct_direct_dependency_versions"] == 1
    assert first_score["status"] == "observed"
    assert first_score["aggregate_score"] == 7.1
    assert first_score["source_scan_precision"] == "date"
    assert repeat_deps["cache_hit"] and not repeat_deps["network_performed"]
    assert repeat_score["cache_hit"] and not repeat_score["network_performed"]
    assert calls == {"deps": 1, "score": 1}


def test_unavailable_or_not_covered_cannot_be_interpreted_as_zero(monkeypatch, tmp_path):
    from mcp_trendpulse import intelligence_core
    from mcp_trendpulse.mjau_v2 import depsdev_graph, openssf_scorecard

    native_cache = intelligence_core.BudgetCache(tmp_path / "unavailable")
    monkeypatch.setattr(intelligence_core, "BudgetCache",
                        lambda root=None: native_cache)
    # Missing provider record is distinct from a score of 0.
    monkeypatch.setattr(openssf_scorecard, "_fetch", lambda url: (404, None))
    score = intelligence_repository_scorecard(
        "pallets", "flask", execute=True,
    )
    assert score["status"] == "not_covered"
    assert score["aggregate_score"] is None
    assert score["no_score_is_not_insecure"]
    # A query rate-limit is provider unavailable, not zero dependencies.
    monkeypatch.setattr(depsdev_graph, "_fetch", lambda url: (429, None))
    dep = intelligence_dependency_graph(
        "npm", "is-odd", "3.0.1", execute=True,
    )
    assert dep["status"] == "unavailable"
    assert dep["summary"] is None

def test_budget_cache_closes_windows_sqlite_before_disposable_cleanup(tmp_path):
    """Windows cannot unlink a SQLite file if an old connection is live."""
    import shutil

    from mcp_trendpulse.intelligence_core import BudgetCache

    cache_root = tmp_path / "temporary-cache"
    cache = BudgetCache(cache_root)
    cache.reserve("safe-release-probe", 2)
    cache.save("probe", {"ok": True}, ttl=60)
    assert cache.cached("probe") == {"ok": True}
    assert cache.blocked("safe-release-probe") is False
    # No gc.collect(), process exit, retries, or skipped Windows assertions:
    # the connection-owning operations must release their file descriptors.
    shutil.rmtree(cache_root)
    assert not cache_root.exists()


def test_b02_post_eol_commercial_support_uses_bounded_sqlite_replay(
    monkeypatch, tmp_path,
):
    """A real optional MCP tool cannot turn commercial maintenance into support."""
    from datetime import datetime, timedelta, timezone

    from mcp_trendpulse import intelligence_core
    from mcp_trendpulse.mjau_v2 import endoflife_release

    store = intelligence_core.BudgetCache(tmp_path / "b02-cache")
    monkeypatch.setattr(intelligence_core, "BudgetCache", lambda root=None: store)
    source_calls = []

    def fetch(url):
        source_calls.append(url)
        return 200, {
            "schema_version": "1.2.1",
            "generated_at": (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat(),
            "result": {
                "name": "20",
                "isEol": True,
                "eolFrom": "2026-04-30",
                "isMaintained": True,
                "isEoes": False,
                "eoesFrom": None,
            },
        }

    monkeypatch.setattr(endoflife_release, "_fetch", fetch)
    first = intelligence_release_lifecycle("nodejs", "20", execute=True)
    repeated = intelligence_release_lifecycle("nodejs", "20", execute=True)
    assert first["status"] == repeated["status"] == "observed_partial"
    assert first["provider_phase_consistent"] and not first["provider_phase_conflicts"]
    assert first["support_scope_caveats"] == [
        "post_eol_extended_or_commercial_support_possible"]
    assert not first["official_vendor_support_verified_by_api"]
    assert not first["support_entitlement_verified"]
    assert not first["unconditional_support_or_migration_advice_allowed"]
    assert first["primary_vendor_schedule_reference"].endswith("schedule.json")
    assert repeated["cache_hit"] and not repeated["network_performed"]
    assert repeated["requests_attempted"] == 0
    assert source_calls == [first["source_url"]]


def test_a07_hub_model_metadata_is_source_scoped_and_cache_replays(
    monkeypatch, tmp_path,
):
    """An opt-in Hub call returns public metadata, never implied buyer demand."""
    from datetime import datetime, timezone

    from mcp_trendpulse import intelligence_core
    from mcp_trendpulse.mjau_v2 import hf_catalog

    store = intelligence_core.BudgetCache(tmp_path / "a07-cache")
    monkeypatch.setattr(intelligence_core, "BudgetCache", lambda root=None: store)
    source_calls = []

    def fetch(url, params):
        source_calls.append((url, params))
        return 200, [{
            "id": "example/alpha-2",
            "modelId": "example/alpha-2",
            "private": False,
            "gated": "manual",
            "trendingScore": 3.5,
            "downloads": 20,
            "likes": 2,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }]

    monkeypatch.setattr(hf_catalog, "_fetch", fetch)
    first = intelligence_hf_catalog("models", limit=2, execute=True)
    repeated = intelligence_hf_catalog("models", limit=2, execute=True)
    assert first["status"] == repeated["status"] == "observed_partial"
    assert first["records"][0]["repository_id"] == "example/alpha-2"
    assert first["records"][0]["gated"] == "manual"
    assert first["records"][0]["provider_download_window"] == (
        "not_verified_by_this_adapter"
    )
    assert not first["comparative_time_series_provided"]
    assert not first["buyer_demand_verified"]
    assert not first["model_weights_or_dataset_files_downloaded"]
    assert repeated["cache_hit"] and not repeated["network_performed"]
    assert repeated["requests_attempted"] == 0
    assert len(source_calls) == 1
    assert source_calls[0][0] == "https://huggingface.co/api/models"
