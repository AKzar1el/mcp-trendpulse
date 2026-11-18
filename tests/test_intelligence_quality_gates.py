"""Adversarial quality gates for the optional opportunity research extension.

These are synthetic fixtures, not historical paying-customer observations.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from mcp_trendpulse.intelligence_evidence import (
    UnexpectedSourceShape, evidence_projection,
)
from mcp_trendpulse.intelligence_opportunities import (
    LANES, SOURCE_KIND, evaluate_opportunities,
)

ASOF = date(2026, 11, 18)


def candidate():
    return {
        "id": "cloud-cost", "title": "Cloud-cost operations",
        "lane": "public_cloud_finops", "workflow": "cloud_cost_review",
        "geography": "US", "buyer": "Public agencies",
        "buyer_entity": "agency-example",
    }


def item(source, num, **extra):
    row = {
        "id": f"signal-{num}", "candidate": "cloud-cost",
        "source": source, "origin_id": f"record-{num}",
        "publisher": f"original-{num}", "geography": "US",
        "workflow": "cloud_cost_review",
        "url": f"https://example.org/records/{num}",
        "published_at": "2026-11-05", "observed_at": "2026-11-06",
        "polarity": "support", "claim": "Synthetic research observation",
        "buyer_entity": "agency-example",
    }
    row.update(extra)
    return row


def series(source, *, bad_value=None):
    first = ASOF - timedelta(days=27)
    return [
        {
            "candidate": "cloud-cost", "source": source,
            "day": (first + timedelta(days=i)).isoformat(),
            "geography": "US", "unit": "daily_events",
            "value": bad_value if bad_value is not None else (2 if i < 14 else 5),
            "coverage_complete": True,
        }
        for i in range(28)
    ]


def evaluate(trends=None, health=None, items=None):
    return evaluate_opportunities(
        [candidate()], items or [], as_of=ASOF.isoformat(),
        daily_trends=trends, source_health=health,
    )["results"][0]


def test_eighteen_lanes_have_unique_actionable_source_mixes():
    assert len(LANES) == 18
    assert len({tuple(sorted(x["sources"])) for x in LANES.values()}) == 18
    for meta in LANES.values():
        assert len(meta["sources"]) == len(set(meta["sources"]))
        assert set(meta["sources"]) <= SOURCE_KIND.keys()
        kinds = {SOURCE_KIND[src] for src in meta["sources"]}
        assert len(kinds) >= 2
        assert {"hiring", "reported_problem", "procurement_notice", "public_award"} & kinds


def test_two_hiring_ats_feeds_are_one_signal_family():
    trend = evaluate(series("greenhouse") + series("greenhouse_job"))["trend"]
    assert trend["status"] == "mixed_or_single_source"
    assert trend["independent_signal_families"] == 1
    assert {row["signal_family"] for row in trend["per_source"]} == {"hiring_ats"}


def test_distinct_issue_and_hiring_sources_can_confirm_rise():
    trend = evaluate(series("github_issues") + series("greenhouse_job"))["trend"]
    assert trend["status"] == "rising_multi_source"
    assert trend["independent_signal_families"] == 2


def test_unrelated_source_cannot_claim_selected_lane_momentum():
    trend = evaluate(series("cfpb") + series("github_issues"))["trend"]
    assert trend["status"] == "unknown"


@pytest.mark.parametrize("health", [
    "timeout", "unavailable", "rate_limited", "stale",
    "not_configured", "invalid_source_shape",
])
def test_unhealthy_provider_invalidates_current_trend_and_rank(health):
    row = evaluate(
        series("github_issues") + series("greenhouse_job"),
        {"github_issues": health},
        [item("github_issues", 1), item("greenhouse_job", 2),
         item("usaspending", 3)],
    )
    assert row["trend"]["status"] == "coverage_degraded"
    assert row["priority_order"] <= 1
    assert row["ignored_reasons"]["unhealthy_provider"] == 1


@pytest.mark.parametrize("value", [True, -1, 1.5, 1_000_000_001, float("inf")])
def test_daily_event_counts_must_be_bounded_nonnegative_integers(value):
    with pytest.raises(ValueError, match="Daily event count"):
        evaluate(series("github_issues", bad_value=value))


def test_utm_query_variants_are_not_independent_evidence():
    a = item(
        "github_issues", 1,
        url="https://EXAMPLE.org/records/same/?utm_source=blog&a=1&b=2",
    )
    b = item(
        "greenhouse_job", 2,
        url="https://example.org/records/same?b=2&a=1&ref=twitter",
    )
    row = evaluate(items=[a, b])
    assert row["supporting_origins"] == 1
    assert row["ignored_reasons"]["duplicate_origin"] == 1
    assert row["source_references"][0]["url"] in {a["url"], b["url"]}


@pytest.mark.parametrize(("source", "payload"), [
    ("usaspending", {"results": {"error": "partial"}}),
    ("ted", {"notices": {"message": "rate limit"}}),
    ("github_issues", {"items": [None]}),
    ("greenhouse", {"jobs": "upstream failure"}),
    ("openalex", {"results": [7]}),
    ("cordis", {"results": {"bindings": "temporarily unavailable"}}),
])
def test_http_200_schema_drift_is_not_zero_demand(source, payload):
    with pytest.raises(UnexpectedSourceShape):
        evidence_projection(source, payload)


@pytest.mark.parametrize(("source", "payload"), [
    ("usaspending", {"results": []}),
    ("ted", {"notices": []}),
    ("github_issues", {"items": []}),
])
def test_legitimate_empty_record_arrays_are_valid(source, payload):
    assert evidence_projection(source, payload)["record_count"] == 0
