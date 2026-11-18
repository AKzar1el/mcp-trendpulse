"""Deterministic adversarial tests for the optional 18-lane opportunity evaluator.

All identifiers, amounts, and organizations in this file are illustrative
fixtures. They are NOT actual market findings or trained outcome labels.
"""

from __future__ import annotations

import copy
import random
from datetime import date, timedelta

import pytest

from mcp_trendpulse.intelligence_core import source_catalog
from mcp_trendpulse.intelligence_opportunities import (
    LANES, SOURCE_KIND, evaluate_opportunities, lane_catalog,
)

ASOF = "2026-11-18"


def candidate(*, lane="developer_reliability", ident="workflow-one", region="US",
              buyer="Public agencies"):
    return {
        "id": ident, "title": "Reliability workflow",
        "lane": lane, "geography": region,
        "workflow": "incident_triage", "buyer": buyer,
        "buyer_entity": "agency-test",
    }


def ev(source, num, *, candidate_id="workflow-one", workflow="incident_triage",
       region="US", publisher=None, origin_id=None, published="2026-11-05",
       observed="2026-11-07", polarity="support", claim="An attributed public source"):
    return {
        "id": f"example-{num}", "candidate": candidate_id, "source": source,
        "buyer_entity": "agency-test" if source == "usaspending" else "",
        "origin_id": origin_id or f"original-{num}",
        "publisher": publisher or f"publisher-{num}",
        "geography": region, "workflow": workflow,
        "published_at": published, "observed_at": observed, "polarity": polarity,
        "url": f"https://example.org/public/{num}",
        "claim": claim,
    }


def strong():
    return [
        ev("github_issues", 1),
        ev("greenhouse_job", 2),
        ev("usaspending", 3),
    ]


def evaluation(evidence=None, **kwargs):
    return evaluate_opportunities([candidate()], strong() if evidence is None else evidence,
                                  as_of=ASOF, **kwargs)


def test_all_eighteen_combinations_only_use_existing_source_registry():
    catalog = {x["id"] for x in source_catalog()}
    assert catalog == set(SOURCE_KIND)
    assert len(lane_catalog()) == 18
    assert set(LANES) == {x["id"] for x in lane_catalog()}
    for lane in LANES.values():
        assert len(lane["sources"]) >= 3
        assert set(lane["sources"]) <= catalog
    assert "opsi_slovenia" not in catalog


def test_buyer_triage_no_fabricated_success_probability():
    row = evaluation()["results"][0]
    assert row["status"] == "buyer_interview_priority"
    assert row["priority_order"] == 3
    assert row["independent_publishers"] == 3
    assert row["distinct_classes"] == 3
    assert not row["buying_intent_confirmed"]
    assert row["success_probability"] is None
    assert "buying proxy" in " ".join(row["caveats"])


def test_no_buyer_or_spend_does_not_promote_to_interview_priority():
    c = candidate(buyer="")
    r = evaluate_opportunities([c], strong(), as_of=ASOF)["results"][0]
    assert r["status"] == "investigate"
    assert r["priority_order"] == 2
    without_award = [ev("github_issues", 1), ev("greenhouse_job", 2)]
    assert evaluation(without_award)["results"][0]["status"] == "investigate"
    assert evaluation([ev("github_issues", 1)])["results"][0]["status"] == "monitor"


def test_one_company_cannot_manufacture_multiple_independent_votes():
    items = [ev("github_issues", 1, publisher="same-company"),
             ev("greenhouse_job", 2, publisher="same-company"),
             ev("usaspending", 3, publisher="same-company")]
    row = evaluation(items)["results"][0]
    assert row["status"] == "monitor"
    assert row["independent_publishers"] == 1


def test_republished_article_across_sources_is_deduplicated():
    records = [ev("github_issues", 1, origin_id="same-release"),
               ev("greenhouse_job", 2, origin_id="same-release")]
    row = evaluation(records)["results"][0]
    assert row["supporting_origins"] == 1
    assert row["ignored_reasons"]["duplicate_origin"] == 1
    assert row["status"] == "monitor"


def test_contradiction_downgrades_even_perfect_support():
    disagree = strong() + [ev("github_issues", 4, polarity="against")]
    assert evaluation(disagree)["results"][0]["status"] == "contested"
    disagree.append(ev("greenhouse_job", 5, polarity="against"))
    assert evaluation(disagree)["results"][0]["status"] == "conflict_review"


def test_provider_timeout_degrades_not_false_zero_demand():
    row = evaluation(source_health={"github_issues": "timeout"})["results"][0]
    assert row["status"] == "partial_provider_coverage"
    assert row["source_health"]["github_issues"] == "timeout"
    assert row["ignored_reasons"]["unhealthy_provider"] == 1
    assert row["supporting_origins"] == 2


def test_as_of_prevents_future_evidence_leakage():
    old = evaluation()["results"][0]
    leak = ev("github_issues", 4, published="2026-12-01", observed="2026-12-02")
    now = evaluation(strong() + [leak])["results"][0]
    assert now["priority_order"] == old["priority_order"]
    assert now["supporting_origins"] == old["supporting_origins"]
    assert now["ignored_reasons"]["future_or_unobserved"] == 1
    late_ingest = ev("greenhouse_job", 5, observed="2026-12-04")
    assert evaluation(strong() + [late_ingest])["results"][0][
        "ignored_reasons"]["future_or_unobserved"] == 1


def test_different_region_or_workflow_never_cross_contaminates():
    mixed = strong() + [
        ev("github_issues", 4, region="DE"),
        ev("greenhouse_job", 5, workflow="tax_audits"),
    ]
    r = evaluation(mixed)["results"][0]
    assert r["supporting_origins"] == 3
    assert r["ignored_reasons"]["different_geography"] == 1
    assert r["ignored_reasons"]["different_workflow"] == 1


def test_invalid_record_rejected_without_destroying_valid_evidence():
    bad = ev("github_issues", 4)
    bad["url"] = "http://127.0.0.1:5000/secrets"
    unknown = ev("unknown_provider", 5)
    result = evaluation(strong() + [bad, unknown])
    assert result["rejected_count"] == 2
    assert result["results"][0]["supporting_origins"] == 3
    assert result["results"][0]["status"] == "buyer_interview_priority"
    assert "127.0.0.1" not in repr(result["rejected_records"])


@pytest.mark.parametrize("field,value", [
    ("candidate", "not-registered"), ("published_at", "2030-02-30"),
    ("observed_at", "invalid"), ("polarity", "definitely_winning"),
    ("geography", "EVERYWHERE"), ("publisher", "../private"), ("origin_id", ""),
])
def test_bad_facts_report_rejection(field, value):
    bad = ev("github_issues", 7)
    bad[field] = value
    result = evaluation([*strong(), bad])
    assert result["rejected_count"] == 1


def test_order_independence_and_no_cross_candidate_voting():
    second = candidate(ident="workflow-two")
    row = ev("github_issues", 9, candidate_id="workflow-two")
    pool = strong() + [row]
    shuffled = copy.deepcopy(pool)
    random.Random(3).shuffle(shuffled)
    one = evaluate_opportunities([candidate(), second], pool, as_of=ASOF)
    two = evaluate_opportunities([second, candidate()], shuffled, as_of=ASOF)
    assert [(x["id"], x["priority_order"]) for x in one["results"]] == [
        (x["id"], x["priority_order"]) for x in two["results"]]
    assert next(x for x in one["results"] if x["id"] == "workflow-two")["status"] == "monitor"


def _series(source, *, missing=None, later=4, earlier=2, extra_future=False):
    end = date.fromisoformat(ASOF)
    start = end - timedelta(days=27)
    rows = []
    for i in range(28):
        if i == missing:
            continue
        rows.append({
            "candidate": "workflow-one", "source": source,
            "day": (start + timedelta(days=i)).isoformat(),
            "geography": "US", "unit": "daily_events",
            "value": earlier if i < 14 else later,
            "coverage_complete": True,
        })
    if extra_future:
        rows.append({**rows[-1], "day": (end + timedelta(days=1)).isoformat(), "value": 999999})
    return rows


def test_trends_need_complete_comparable_sample_and_multiple_sources():
    rows = _series("github_issues") + _series("greenhouse_job")
    t = evaluation(daily_trends=rows)["results"][0]["trend"]
    assert t["status"] == "rising_multi_source"
    assert t["not_revenue_forecast"]
    missing = _series("github_issues", missing=9)
    assert evaluation(daily_trends=missing)["results"][0]["trend"]["status"] == "unknown"
    assert evaluation(daily_trends=_series("github_issues", extra_future=True))[
        "results"][0]["trend"]["status"] == "mixed_or_single_source"


def test_opposing_trend_series_do_not_average_into_false_rise():
    rows = _series("github_issues", earlier=2, later=5)
    rows += _series("greenhouse_job", earlier=5, later=2)
    assert evaluation(daily_trends=rows)["results"][0]["trend"]["status"] == "conflicted"


def test_forged_or_missing_daily_coverage_cannot_produce_trend():
    bad = _series("github_issues")
    bad[0]["coverage_complete"] = False
    result = evaluation(daily_trends=bad)
    assert result["results"][0]["trend"]["status"] == "unknown"
    dup = _series("github_issues")
    dup.append(copy.deepcopy(dup[0]))
    assert evaluation(daily_trends=dup)["results"][0]["trend"]["status"] == "unknown"


def test_oversized_or_duplicate_candidates_fail_closed():
    with pytest.raises(ValueError):
        evaluate_opportunities([candidate(), candidate()], [], as_of=ASOF)
    with pytest.raises(ValueError):
        evaluate_opportunities([candidate()], [{}] * 301, as_of=ASOF)
    with pytest.raises(ValueError):
        evaluate_opportunities([candidate()], [], as_of="not-a-date")



def test_public_award_must_match_same_buyer_before_interview_priority():
    items = strong()
    items[2]["buyer_entity"] = "different-agency"
    result = evaluation(items)["results"][0]
    assert result["status"] == "investigate"
    assert result["priority_order"] == 2
    assert "Awarding buyer identity" in " ".join(result["caveats"])


def test_unknown_credential_source_does_not_create_buying_proof():
    result = evaluation(strong(), source_health={"usaspending": "not_configured"})
    assert result["results"][0]["status"] == "partial_provider_coverage"
    assert result["results"][0]["success_probability"] is None



@pytest.mark.parametrize("lane", sorted(LANES))
def test_every_lane_accepts_valid_independent_source_mix_without_fake_sales(lane):
    base = candidate(lane=lane)
    sources = list(LANES[lane]["sources"])
    # Ensure at least one real-world work/spend signal where supported;
    # regulations/research/economic context alone never imply customers.
    sources = sources[:3] if any(SOURCE_KIND[x] in {
        "reported_problem", "hiring", "procurement_notice", "public_award"
    } for x in sources[:3]) else sources
    items = [ev(src, i+20) for i, src in enumerate(sources)]
    result = evaluate_opportunities([base], items, as_of=ASOF)
    row = result["results"][0]
    assert row["distinct_classes"] >= 2
    assert row["independent_publishers"] >= 3
    assert row["priority_order"] >= 2, (lane, row)
    assert row["status"] in {"investigate", "buyer_interview_priority"}
    assert row["success_probability"] is None
    assert not row["buying_intent_confirmed"]


def test_same_original_url_aggregated_under_two_ids_only_once():
    items = [ev("github_issues", 1), ev("greenhouse_job", 2)]
    items[1]["url"] = items[0]["url"]
    row = evaluation(items)["results"][0]
    assert row["supporting_origins"] == 1
    assert row["ignored_reasons"]["duplicate_origin"] == 1


def test_two_lanes_on_one_topic_do_not_share_evidence_automatically():
    c1 = candidate(lane="developer_reliability")
    c2 = candidate(lane="fraud_identity", ident="other-problem")
    result = evaluate_opportunities([c1, c2], strong(), as_of=ASOF)
    statuses = {x["id"]: x["status"] for x in result["results"]}
    assert statuses["other-problem"] == "insufficient"
    assert statuses["workflow-one"] == "buyer_interview_priority"


@pytest.mark.parametrize("health", [
    "unavailable", "timeout", "rate_limited", "stale", "not_configured",
])
def test_each_provider_outage_suppresses_unsupported_high_priority(health):
    row = evaluation(source_health={"github_issues": health})["results"][0]
    assert row["priority_order"] <= 1
    assert row["success_probability"] is None


def test_invalid_aggregate_health_metadata_cannot_silently_rank():
    with pytest.raises(ValueError, match="source_health"):
        evaluation(source_health={"github_issues": ["timeout"]})
    with pytest.raises(ValueError, match="source_health"):
        evaluation(source_health={"ghost-provider": "ok"})



def test_batch_manifest_or_static_catalogue_cannot_claim_topical_growth():
    for source in ("gdelt_latest", "copernicus", "gleif", "eurostat"):
        result = evaluation(daily_trends=_series(source))
        assert result["results"][0]["trend"]["status"] == "unknown"
