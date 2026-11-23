"""Backwards-compatible compact discovery reply with preserved evidence and cautions."""
from __future__ import annotations

import json
from copy import deepcopy

from fastmcp import Client
import pytest

from mcp_trendpulse import intelligence_discovery, intelligence_mcp


@pytest.fixture
def recorded_report():
    return {
        "mode": "seedless_public_source_discovery_not_market_growth",
        "as_of": "2026-11-23",
        "lookback_days": 14,
        "discovery_query_mode": "no_seed_topics_or_sector_keywords",
        "source_coverage": [
            {"source": "openalex", "status": "observed", "cache_hit": True},
            {"source": "cfpb", "status": "unavailable", "cache_hit": False},
            {"source": "ted", "status": "observed", "cache_hit": True},
        ],
        "recent_observations": 10,
        "candidate_count": 1,
        "candidates": [{
            "candidate_id": "public-evidence-1",
            "label": "Public complaint investigation",
            "examples": [{"date": "2026-11-22", "source": "cfpb",
                          "reference": "https://www.consumerfinance.gov/data-research/consumer-complaints/"}],
            "commercial_budget_verified": False,
            "same_buyer_verified": False,
            "growth_direction": "unknown_without_comparable_population_history",
        }],
        "procurement_review": {
            "qualified_notices_in_bounded_sample": 2,
            "estimated_value_is_not_spending_or_software_only_budget": True,
        },
        "ted_sampling_audit": {
            "first_page_hit_record_cap": True,
            "sector_share_or_growth_estimable": False,
        },
        "source_health_degraded": True,
        "population_coverage_verified": False,
        "growth_rate_verified": False,
        "paid_buyers_verified": False,
        "no_paid_apis": True,
        "limits": "Small, biased samples; source failure does not mean no demand.",
        "network_performed": True,
        "queries_budgeted": 3,
        "ted_date_slices": 1,
        "sample_limit": 5,
        "user_credentials_exposed": False,
        "procurement_observations": [{"raw": "x" * 8500}],
        "procurement_estimate_examples": [{"raw": "y" * 600}],
        "coarse_cpv_repeats_not_candidates": [{"raw": "z" * 600}],
        "same_published_identity_repeats_not_candidates": [],
        "research_observations": [{"raw": "w" * 1600}],
        "sample_examples_by_source": {"ted": [{"raw": "v" * 1000}]},
    }


def test_compact_shrinks_reply_without_erasing_cautions(monkeypatch, recorded_report):
    inputs = []

    def fake_discover(**kwargs):
        inputs.append(kwargs)
        return deepcopy(recorded_report)

    monkeypatch.setattr(intelligence_discovery, "discover_current", fake_discover)
    default = intelligence_mcp.intelligence_discover_current(
        execute=True, lookback_days=14, limit=5,
    )
    compact = intelligence_mcp.intelligence_discover_current(
        execute=True, lookback_days=14, limit=5, compact=True,
    )
    assert default == recorded_report
    assert len(inputs) == 2 and all(call["execute"] is True for call in inputs)
    assert compact["response_view"] == "compact_decision_brief"
    assert compact["candidates"] == recorded_report["candidates"]
    assert compact["source_coverage"] == recorded_report["source_coverage"]
    assert compact["ted_sampling_audit"] == recorded_report["ted_sampling_audit"]
    for key in (
        "source_health_degraded", "paid_buyers_verified",
        "population_coverage_verified", "growth_rate_verified",
        "no_paid_apis", "limits", "procurement_review",
        "network_performed", "queries_budgeted",
    ):
        assert compact[key] == recorded_report[key]
    for key in compact["details_omitted"]:
        assert key not in compact
        assert key in default
    assert len(json.dumps(compact)) < len(json.dumps(default)) * 0.45


def test_plan_only_compact_does_not_change_plan_or_force_network(monkeypatch):
    plan = {"status": "planned", "network_performed": False, "request_count": 3}
    seen = []

    def fake_discover(**kwargs):
        seen.append(kwargs)
        return deepcopy(plan)

    monkeypatch.setattr(intelligence_discovery, "discover_current", fake_discover)
    assert intelligence_mcp.intelligence_discover_current(compact=True) == plan
    assert len(seen) == 1
    assert seen[0]["execute"] is False


@pytest.mark.parametrize("bad", ["true", 1, None, [], {}])
def test_compact_rejects_non_boolean_before_source_work(monkeypatch, bad):
    def never(**kwargs):
        raise AssertionError("Invalid compact flag reached source")
    monkeypatch.setattr(intelligence_discovery, "discover_current", never)
    with pytest.raises(ValueError, match="compact must be a boolean"):
        intelligence_mcp.intelligence_discover_current(compact=bad)


@pytest.mark.parametrize("flag", ["measure_trends", "broad_topic_scan",
                                  "corroborate_issues", "cross_source_hunt"])
def test_compact_does_not_hide_requested_enrichments(monkeypatch, flag):
    def never(**kwargs):
        raise AssertionError("Invalid combination reached source")
    monkeypatch.setattr(intelligence_discovery, "discover_current", never)
    with pytest.raises(ValueError, match="enrichments"):
        intelligence_mcp.intelligence_discover_current(compact=True, **{flag: True})


@pytest.mark.asyncio
async def test_real_fastmcp_tool_contract_exposes_compact_read_only(monkeypatch, recorded_report):
    monkeypatch.setattr(
        intelligence_discovery, "discover_current",
        lambda **kwargs: deepcopy(recorded_report),
    )
    async with Client(intelligence_mcp.intel_mcp) as client:
        defs = await client.list_tools()
        tool = next(d for d in defs if d.name == "intelligence_discover_current")
        assert tool.inputSchema["properties"]["compact"]["type"] == "boolean"
        assert tool.inputSchema["properties"]["compact"]["default"] is False
        original = await client.call_tool(
            "intelligence_discover_current",
            {"execute": True, "limit": 5},
        )
        brief = await client.call_tool(
            "intelligence_discover_current",
            {"execute": True, "limit": 5, "compact": True},
        )
        assert not original.is_error and not brief.is_error
        assert original.structured_content["procurement_observations"]
        assert brief.structured_content["paid_buyers_verified"] is False
        assert brief.structured_content["source_health_degraded"] is True
        assert "procurement_observations" not in brief.structured_content
