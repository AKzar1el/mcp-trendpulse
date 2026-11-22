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


@pytest.mark.parametrize("count", [0, 30, 31, 300])
def test_source_reference_excerpt_reports_total_and_truncation(count):
    evidence = [ev("github_issues", i) for i in range(count)]
    row = evaluation(evidence)["results"][0]
    assert row["source_references_total"] == count
    assert row["source_references_truncated"] is (count > 30)
    assert len(row["source_references"]) == min(count, 30)
    assert [ref["id"] for ref in row["source_references"]] == sorted(
        item["id"] for item in evidence
    )[:30]


def test_source_reference_excerpt_counts_support_and_opposition_in_any_order():
    evidence = [
        ev("github_issues", i, polarity="against" if i % 5 == 0 else "support")
        for i in range(31)
    ]
    shuffled = copy.deepcopy(evidence)
    random.Random(23).shuffle(shuffled)
    expected_ids = sorted(item["id"] for item in evidence)[:30]
    for records in (evidence, shuffled):
        row = evaluation(records)["results"][0]
        assert row["source_references_total"] == 31
        assert row["source_references_truncated"] is True
        assert row["supporting_origins"] + row["contradicting_origins"] == 31
        assert [ref["id"] for ref in row["source_references"]] == expected_ids
        assert any(ref["polarity"] == "against" for ref in row["source_references"])


def test_source_reference_excerpt_excludes_duplicates_and_rejected_records():
    evidence = [ev("github_issues", i) for i in range(30)]
    syndicated = ev("greenhouse_job", 31, origin_id=evidence[4]["origin_id"])
    bad = ev("github_issues", 32)
    bad["url"] = "http://127.0.0.1/private"
    result = evaluation(evidence + [syndicated, bad])
    row = result["results"][0]
    assert result["rejected_count"] == 1
    assert row["ignored_reasons"]["duplicate_origin"] == 1
    assert row["source_references_total"] == 30
    assert row["source_references_truncated"] is False
    assert len(row["source_references"]) == 30


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


@pytest.mark.parametrize(("rejected_owner", "expected_warned"), [
    ("workflow-one", {"workflow-one"}),
    ("workflow-two", {"workflow-two"}),
    ("not-registered", set()),
])
def test_rejected_evidence_caveat_is_candidate_scoped(rejected_owner, expected_warned):
    candidates = [candidate(), candidate(ident="workflow-two")]
    valid = strong() + [ev("github_issues", 90, candidate_id="workflow-two")]
    baseline = evaluate_opportunities(candidates, valid, as_of=ASOF)
    malformed = ev("github_issues", 91, candidate_id=rejected_owner)
    malformed["url"] = "http://127.0.0.1/private"

    actual = evaluate_opportunities(candidates, valid + [malformed], as_of=ASOF)
    assert actual["rejected_count"] == 1
    assert actual["rejected_records"] == [{
        "index": len(valid), "reason": "source_url must be a public HTTPS evidence reference",
    }]
    baseline_by_id = {row["id"]: row for row in baseline["results"]}
    warning = "Some evidence input records were rejected; inspect reasons"
    for row in actual["results"]:
        assert (warning in row["caveats"]) == (row["id"] in expected_warned)
        original = baseline_by_id[row["id"]]
        assert (row["status"], row["priority_order"], row["source_references"]) == (
            original["status"], original["priority_order"], original["source_references"])


def test_cross_candidate_duplicate_id_warns_both_affected_candidates():
    candidates = [candidate(), candidate(ident="workflow-two")]
    first = ev("github_issues", 92)
    second = ev("greenhouse_job", 93, candidate_id="workflow-two")
    second["id"] = first["id"]
    actual = evaluate_opportunities(candidates, [first, second], as_of=ASOF)
    assert actual["rejected_count"] == 2
    for row in actual["results"]:
        assert "Some evidence input records were rejected; inspect reasons" in row["caveats"]


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


@pytest.mark.parametrize("polarity", ["OMITTED", None, "", "invalid"])
def test_missing_or_invalid_polarity_cannot_count_as_support(polarity):
    rows = strong()
    if polarity == "OMITTED":
        rows[2].pop("polarity")
    else:
        rows[2]["polarity"] = polarity
    result = evaluation(rows)
    assert result["rejected_count"] == 1
    assert result["results"][0]["supporting_origins"] == 2
    assert result["results"][0]["status"] == "investigate"


def test_all_omitted_polarities_cannot_create_support():
    rows = strong()
    for row in rows:
        row.pop("polarity")
    result = evaluation(rows)
    assert result["rejected_count"] == 3
    assert result["results"][0]["supporting_origins"] == 0
    assert result["results"][0]["status"] == "insufficient"


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


@pytest.mark.parametrize("unknown_first", [True, False])
def test_unknown_candidate_cannot_reserve_valid_evidence_id(unknown_first):
    valid = ev("github_issues", 61)
    unknown = ev("greenhouse_job", 62, candidate_id="not-registered")
    unknown["id"] = valid["id"]
    records = [unknown, valid] if unknown_first else [valid, unknown]

    result = evaluation(records)
    row = result["results"][0]
    assert result["rejected_records"] == [{
        "index": 0 if unknown_first else 1,
        "reason": "Evidence references unknown candidate",
    }]
    assert result["rejected_count"] == 1
    assert row["status"] == "monitor"
    assert row["supporting_origins"] == 1
    assert [ref["id"] for ref in row["source_references"]] == [valid["id"]]


@pytest.mark.parametrize("seed", range(5))
def test_unknown_candidate_duplicate_ids_do_not_change_mixed_candidate_results(seed):
    candidates = [candidate(), candidate(ident="workflow-two")]
    valid = [ev("github_issues", 71),
             ev("github_issues", 72, candidate_id="workflow-two")]
    unknown = [ev("greenhouse_job", 73, candidate_id="not-registered"),
               ev("greenhouse_job", 74, candidate_id="not-registered")]
    for invalid, good in zip(unknown, valid):
        invalid["id"] = good["id"]
    baseline = evaluate_opportunities(candidates, valid, as_of=ASOF)
    records = valid + unknown
    random.Random(seed).shuffle(records)
    actual = evaluate_opportunities(candidates, records, as_of=ASOF)

    assert actual["rejected_count"] == 2
    assert {item["reason"] for item in actual["rejected_records"]} == {
        "Evidence references unknown candidate"}
    assert [(row["id"], row["status"], row["source_references"])
            for row in actual["results"]] == [
                (row["id"], row["status"], row["source_references"])
                for row in baseline["results"]]


@pytest.mark.parametrize("seed", range(5))
def test_cross_candidate_evidence_id_collision_fails_closed_regardless_of_order(seed):
    candidates = [candidate(), candidate(ident="workflow-two")]
    support = [ev("github_issues", 81), ev("greenhouse_job", 82),
               ev("usaspending", 83)]
    contradiction = ev("github_issues", 84, candidate_id="workflow-two",
                       polarity="against")
    contradiction["id"] = support[0]["id"]
    records = support + [contradiction]
    random.Random(seed).shuffle(records)

    result = evaluate_opportunities(candidates, records, as_of=ASOF)
    by_id = {row["id"]: row for row in result["results"]}
    assert result["rejected_count"] == 2
    assert result["rejected_records"] == [
        {"index": index, "reason": "Duplicate evidence ID across candidates"}
        for index, item in enumerate(records) if item["id"] == support[0]["id"]]
    assert by_id["workflow-one"]["status"] == "investigate"
    assert by_id["workflow-one"]["supporting_origins"] == 2
    assert {ref["id"] for ref in by_id["workflow-one"]["source_references"]} == {
        support[1]["id"], support[2]["id"]}
    assert by_id["workflow-two"]["status"] == "insufficient"
    assert by_id["workflow-two"]["contradicting_origins"] == 0


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
