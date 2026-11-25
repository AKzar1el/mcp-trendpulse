"""Offline regressions for opt-in hunter depth and relevance controls."""

from datetime import date
import sqlite3
from urllib.parse import parse_qs, urlsplit

from fastmcp import Client
import pytest

from mcp_trendpulse import intelligence_hunter as hunter
from mcp_trendpulse.intelligence_core import DailyBudgetExceeded, IntelligenceError, plan_source
from mcp_trendpulse.intelligence_mcp import intel_mcp


def _plan_query(plan):
    return parse_qs(urlsplit(plan.url).query)


def _work(index, title):
    return {
        "id": f"https://openalex.org/W{10000 + index}",
        "display_name": title,
        "publication_date": date.today().isoformat(),
    }


def _observed(source, rows):
    return {"source": source, "status": "observed",
            "observations": {"record_count": len(rows), "sample": rows}}


def test_default_and_opt_in_plans_preserve_date_and_request_count(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Plan-only must not collect")
    monkeypatch.setattr(hunter, "collect", forbidden)
    sources = ["openalex", "github_issues"]
    original = hunter.hunt_current(["battery recycling"], sources, env={})
    improved = hunter.hunt_current(
        ["battery recycling"], sources, env={}, sample_limit=10, relevance_first=True,
    )
    assert original["request_count"] == improved["request_count"] == 2
    assert original["requested_sample_limit_per_source"] == 5
    assert improved["requested_sample_limit_per_source"] == 10
    assert improved["relevance_first_sources"] == sources
    assert improved["maximum_sample_records_per_topic"] == 20
    assert improved["network_performed"] is False
    a = [parse_qs(urlsplit(c["plan"]["url"]).query) for c in original["topics"][0]["calls"]]
    b = [parse_qs(urlsplit(c["plan"]["url"]).query) for c in improved["topics"][0]["calls"]]
    assert a[0]["sort"] == ["publication_date:desc"]
    assert b[0]["sort"] == ["relevance_score:desc"]
    assert a[0]["filter"] == b[0]["filter"]
    assert a[1]["sort"] == ["created"]
    assert "sort" not in b[1] and "order" not in b[1]
    assert a[1]["q"] == b[1]["q"]
    assert all(query["per_page"] == ["10"] for query in b)


@pytest.mark.parametrize("bad", [0, 11, True, 1.5, "10"])
def test_invalid_depth_stops_before_planning(monkeypatch, bad):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid input must not plan")
    monkeypatch.setattr(hunter, "plan_source", forbidden)
    with pytest.raises(ValueError, match="sample_limit"):
        hunter.hunt_current(["battery recycling"], ["openalex"], sample_limit=bad)


def test_aggregate_sample_cap_and_relevance_validation():
    with pytest.raises(ValueError, match="40 per topic"):
        hunter.hunt_current(
            ["battery recycling"], list(hunter.HUNT_SOURCES[:5]), sample_limit=10,
        )
    with pytest.raises(ValueError, match="relevance_first"):
        hunter.hunt_current(["battery recycling"], ["openalex"], relevance_first="true")
    with pytest.raises(IntelligenceError, match="Relevance-first"):
        plan_source("openalex", discover=True, lookback_days=30, relevance_first=True, env={})
    with pytest.raises(IntelligenceError, match="Relevance-first"):
        plan_source("cfpb", keyword="credit card", relevance_first=True, env={})


def test_deeper_sample_finds_later_match_and_clamps_provider_overreturn(monkeypatch):
    rows = [_work(i, "Unrelated geology") for i in range(5)]
    rows.append(_work(5, "Battery recycling workflow"))
    rows.append(_work(6, "Battery recycling process"))

    def fake_collect(plan, **kwargs):
        return _observed(plan.source, rows)

    monkeypatch.setattr(hunter, "collect", fake_collect)
    base = hunter.hunt_current(["battery recycling"], ["openalex"], env={}, execute=True)
    deep = hunter.hunt_current(
        ["battery recycling"], ["openalex"], env={}, execute=True, sample_limit=6,
    )
    assert base["topics"][0]["recent_dated_records_in_sample"] == 0
    assert deep["topics"][0]["recent_dated_records_in_sample"] == 1
    coverage = deep["topics"][0]["source_coverage"][0]
    assert coverage["records_examined"] == 6
    assert coverage["projection_sample_complete"] is False
    assert deep["source_request_budget"] == base["source_request_budget"] == 1


def test_provider_label_context_not_ranked_as_title_evidence(monkeypatch):
    work = _work(1, "A methodological evaluation")
    work["primary_topic"] = {"display_name": "Battery recycling"}
    work["doi"] = "https://doi.org/10.1002/ADMA.201404892"
    monkeypatch.setattr(hunter, "collect", lambda plan, **kw: _observed(plan.source, [work]))
    result = hunter.hunt_current(["battery recycling"], ["openalex"], env={},
                                 execute=True, relevance_first=True)
    topic = result["topics"][0]
    assert topic["recent_dated_records_in_sample"] == 0
    assert topic["source_coverage"][0]["provider_label_only_matches"] == 1
    assert topic["provider_label_context_examples"][0]["title"] == work["display_name"]
    assert "primary_topic" in _plan_query(plan_source(
        "openalex", keyword="battery recycling", relevance_first=True, env={},
    ))["select"][0]


def test_explicit_acronym_expansion_not_fuzzy_entity_matching():
    assert hunter._relevant("MCP reliability", "Model Context Protocol reliability")
    assert hunter._relevant("machine learning reliability", "ML reliability")
    assert not hunter._relevant("MCP reliability", "Cloud reliability")


def test_quota_exhaustion_does_not_erase_healthy_source(monkeypatch):
    def fake_collect(plan, **kwargs):
        if plan.source == "github_issues":
            raise DailyBudgetExceeded(plan.source, date.today().isoformat(), 12, 12)
        assert _plan_query(plan)["sort"] == ["relevance_score:desc"]
        return _observed(plan.source, [_work(1, "Battery recycling workflow")])

    monkeypatch.setattr(hunter, "collect", fake_collect)
    result = hunter.hunt_current(
        ["battery recycling"], ["github_issues", "openalex"],
        env={}, execute=True, relevance_first=True,
    )
    topic = result["topics"][0]
    assert topic["recent_dated_records_in_sample"] == 1
    assert topic["provider_coverage_degraded"] is True
    coverage = {row["source"]: row for row in topic["source_coverage"]}
    assert coverage["github_issues"]["status"] == "rate_limited"
    assert coverage["github_issues"]["reason"] == "local_daily_budget_exhausted"
    assert coverage["openalex"]["status"] == "observed"


def test_history_separates_configurations_without_storing_raw_evidence(monkeypatch, tmp_path):
    def fake_collect(plan, **kwargs):
        return _observed(plan.source, [_work(1, "Battery recycling workflow")])
    monkeypatch.setattr(hunter, "collect", fake_collect)
    store = tmp_path / "history.sqlite"
    for limit, relevance in [(5, False), (5, False), (8, True), (8, True)]:
        report = hunter.hunt_current(
            ["battery recycling"], ["openalex"], execute=True, env={},
            sample_limit=limit, relevance_first=relevance,
        )
        hunter.record_hunt_history(report, store)
    with sqlite3.connect(store) as conn:
        assert conn.execute("SELECT COUNT(*) FROM hunter_snapshots").fetchone()[0] == 2
    assert b"Battery recycling workflow" not in store.read_bytes()


async def test_mcp_advertises_bounds_and_preserves_plan_only_behavior():
    async with Client(intel_mcp) as client:
        tool = next(t for t in await client.list_tools() if t.name == "intelligence_hunt_current")
        properties = tool.inputSchema["properties"]
        assert properties["lookback_days"]["minimum"] == 7
        assert properties["lookback_days"]["maximum"] == 90
        assert properties["sample_limit"]["minimum"] == 1
        assert properties["sample_limit"]["maximum"] == 10
        response = await client.call_tool("intelligence_hunt_current", {
            "topics": ["battery recycling"], "sources": ["openalex"],
            "sample_limit": 10, "relevance_first": True,
        })
    assert response.structured_content["network_performed"] is False
    assert response.structured_content["requested_sample_limit_per_source"] == 10
