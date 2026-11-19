"""Synthetic falsification tests for exact buyer ID links and safe source watchlists.

These are deliberately invented records; they are NOT real market signals.
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from mcp_trendpulse.intelligence_observations import observe_source_snapshots

ASOF = "2026-11-19"


def observed(source, items, *, count=None):
    return {
        "source": source, "status": "observed",
        "observations": {
            "record_count": len(items) if count is None else count,
            "sample": items,
        },
    }


def company(number="00000006", name="EXAMPLE SOFTWARE LTD", status="active"):
    return {
        "company_number": number, "title": name,
        "company_status": status, "date_of_creation": "1998-03-09",
    }


def lei(number="00000006", authority="RA000585", name="EXAMPLE SOFTWARE LTD"):
    return {
        "id": "529900EXAMPLE1234567",
        "attributes": {
            "entity": {
                "legalName": {"name": name},
                "registeredAt": {"id": authority},
                "registeredAs": number,
            },
        },
    }


def research(day="2026-11-15"):
    return {
        "id": "https://openalex.org/W2741809807",
        "display_name": "Battery recycling research",
        "publication_date": day,
    }


def review(items, *, asof=ASOF):
    return observe_source_snapshots("battery recycling", items, as_of=asof)


def test_exact_registry_identifier_links_without_claiming_purchasing_intent():
    result = review([
        observed("companies_house", [company()]),
        observed("gleif", [lei()]),
        observed("openalex", [research()]),
    ])
    assert len(result["exact_registry_matches"]) == 1
    matched = result["exact_registry_matches"][0]
    assert matched["companies_house_number"] == "00000006"
    assert matched["registration_authority"] == "RA000585"
    assert matched["lei"] == "529900EXAMPLE1234567"
    assert matched["paid_buyer_verified"] is False
    assert result["paid_customer_outcome_verified"] is False
    assert result["success_probability"] is None
    assert result["market_momentum"]["complete_28_day_series"] is False
    assert result["dated_recent_sample_records"] == 1
    assert result["name_only_matches_promoted"] == 0
    assert result["externally_visible_requests_performed"] == 0


@pytest.mark.parametrize("num,authority", [
    ("00000007", "RA000585"),
    ("00000006", "RA000598"),
    ("00000006", ""),
    ("00000006", "RA999999"),
])
def test_company_names_never_override_nonmatching_official_identifiers(num, authority):
    match = review([
        observed("companies_house", [company()]),
        observed("gleif", [lei(num, authority)]),
    ])
    assert match["exact_registry_matches"] == []
    assert match["name_only_matches_promoted"] == 0


def test_names_differ_but_exact_registry_identifiers_require_review():
    result = review([
        observed("companies_house", [company(name="EXAMPLE LTD")]),
        observed("gleif", [lei(name="EXAMPLE HOLDING LTD")]),
    ])
    assert result["exact_registry_matches"][0]["name_conflict_requires_review"] is True


def test_similar_company_names_without_matching_registration_number_not_linked():
    r = review([
        observed("companies_house", [
            company("00000006", "ACME LIMITED"),
            company("00000007", "ACME LIMITED"),
        ]),
        observed("gleif", [lei("00000008", name="ACME LIMITED")]),
    ])
    assert r["exact_registry_matches"] == []


def test_us_award_recipient_is_supplier_not_budget_owner():
    award = {
        "Award ID": "TEST123", "Awarding Agency": "Environmental Protection Agency",
        "Recipient Name": "EXAMPLE SOFTWARE LTD", "Award Amount": 1500.0,
        "Description": "Contract for data transformation",
        "Last Modified Date": "2026-11-18",
    }
    result = review([observed("usaspending", [award])])
    row = result["sample_records"][0]
    assert row["buyer_name"] == "Environmental Protection Agency"
    assert row["supplier_name"] == "EXAMPLE SOFTWARE LTD"
    assert row["reported_award_amount_usd"] == 1500
    assert row["date_semantics"] == "record_last_modified_not_award_date"
    assert result["dated_recent_sample_records"] == 0
    assert result["buyer_budget_verified"] is False


def test_cordis_exact_project_id_links_are_source_attributed_not_new_demand():
    report = review([observed("cordis", [{
        "id": "101123330", "title": "Battery recycling research project",
    }])])
    row = report["sample_records"][0]
    assert row["reference"] == "https://cordis.europa.eu/project/id/101123330"
    assert row["event_date"] is None
    assert row["date_semantics"] == "research_project_no_comparable_event_date"
    assert report["dated_recent_sample_records"] == 0
    assert report["buyer_budget_verified"] is False


def test_non_numeric_cordis_identifier_does_not_invent_project_deep_link():
    report = review([observed("cordis", [{
        "id": "TEST:UNKNOWN", "title": "Battery recycling research project",
    }])])
    assert report["sample_records"][0]["reference"] == "https://cordis.europa.eu/"
    assert report["dated_recent_sample_records"] == 0


def test_research_search_pages_are_not_growth_estimators():
    result = review([observed("openalex", [
        research(), {**research("2026-11-16"), "id": "https://openalex.org/W2741809808"},
        {**research("2027-01-01"), "id": "https://openalex.org/W2741809809"},
    ], count=500000)])
    assert result["source_coverage"][0]["sample_complete"] is False
    assert result["dated_recent_sample_records"] == 2
    assert result["market_momentum"]["status"] == "not_estimable_from_relevance_ranked_samples"
    assert result["evidence_class_counts"] == {"research": 3}
    assert result["success_probability"] is None


def test_deduplicate_original_ids_and_keep_source_provenance():
    result = review([observed("openalex", [research(), research()])])
    assert result["records_reviewed"] == 1
    assert result["discarded_records"]["duplicate_provider_record"] == 1


def test_failure_does_not_masquerade_as_zero_market_interest():
    result = review([
        {"source": "companies_house", "status": "unavailable", "reason": "HTTPError"},
        observed("openalex", [research()]),
    ])
    assert result["coverage_degraded"] is True
    assert result["unavailable_sources"] == ["companies_house"]
    assert result["source_coverage"][0]["records_examined"] == 0
    assert result["dated_recent_sample_records"] == 1


def test_unexpected_schema_and_missing_record_id_are_not_silent_success():
    failed = review([
        {"source": "companies_house", "status": "observed", "observations": {"record_count": 0}},
        observed("gleif", [{"id": "", "attributes": {}}]),
    ])
    assert failed["coverage_degraded"] is True
    assert failed["source_coverage"][0]["status"] == "invalid_source_shape"
    assert failed["discarded_records"]["unsupported_or_unidentified_record"] == 1


def test_issue_pull_requests_cannot_inflate_reported_problem_counts():
    item = {
        "id": 210, "title": "Need manual workflow automation",
        "created_at": "2026-11-18",
        "html_url": "https://github.com/example/project/issues/210",
    }
    result = review([observed("github_issues", [
        {**item, "pull_request": {"url": "https://api.github.com/"}},
        item,
    ])])
    assert result["records_reviewed"] == 1
    assert result["sample_records"][0]["kind"] == "reported_problem"


def test_confidential_or_arbitrary_external_urls_never_republished():
    result = review([observed("github_issues", [{
        "id": 700, "title": "Private leaked link",
        "created_at": "2026-11-18",
        "html_url": "https://example.com/?api_key=DO_NOT_LEAK",
    }])])
    assert "DO_NOT_LEAK" not in repr(result)
    assert result["sample_records"][0]["reference"] == "https://github.com/"


def test_cfpb_public_id_is_needed_before_counting_complaint():
    result = review([observed("cfpb", [
        {"issue": "Incorrect billing", "date_received": "2026-11-17"},
        {"public_complaint_id": "12345", "issue": "Incorrect billing",
         "date_received": "2026-11-17"},
    ])])
    assert result["records_reviewed"] == 1
    assert result["discarded_records"]["unsupported_or_unidentified_record"] == 1


@pytest.mark.parametrize("wrong", [None, [], {}, [123], [{"source": "bogus", "status": "observed"}]])
def test_invalid_boundaries_rejected(wrong):
    with pytest.raises(ValueError):
        review(wrong)


def test_duplicate_source_snapshot_refused_and_not_double_counted():
    x = observed("openalex", [research()])
    with pytest.raises(ValueError, match="one source response"):
        review([x, deepcopy(x)])


def test_large_input_refused():
    with pytest.raises(ValueError, match="220 KB"):
        review([observed("openalex", [{"description": "x" * 230_000}])])


def test_cannot_claim_temporal_change_from_old_record():
    x = review([observed("openalex", [research("2017-06-01")])])
    assert x["dated_recent_sample_records"] == 0


def test_all_eighteen_lanes_have_explicit_partial_topic_coverage():
    x = review([
        observed("openalex", [research()]),
        observed("cordis", [{"id": "10001000", "title": "Battery recycling research"}]),
    ])
    assert len(x["eighteen_lane_coverage"]) == 18
    row = next(r for r in x["eighteen_lane_coverage"] if r["lane"] == "research_to_product")
    assert row["sampled_sources"] == 2
    assert row["literal_topic_records_in_sample"] == 2
    assert row["distinct_topic_evidence_classes"] == 2
    assert row["decision"] == "review_original_sources_and_buyer_workflow"
    assert row["not_a_validated_market_opportunity"] is True
    assert x["market_momentum"]["complete_28_day_series"] is False
    assert x["buyer_budget_verified"] is False


def test_one_source_topic_match_not_an_independent_commercial_signal():
    x = review([observed("openalex", [research()])])
    row = next(r for r in x["eighteen_lane_coverage"] if r["lane"] == "research_to_product")
    assert row["decision"] == "insufficient_topical_cross_source_evidence"
    assert x["literal_topic_matches_in_sample"] == 1


def test_bounded_projection_is_not_a_complete_provider_population():
    x = review([observed("openalex", [research()], count=1)])
    assert x["source_coverage"][0]["projection_sample_complete"] is True
    assert x["source_coverage"][0]["sample_complete"] is False
    assert x["source_coverage"][0]["population_coverage_verified"] is False


def test_unrelated_topic_never_treated_as_credible_cross_source_overlap():
    x = review([
        observed("openalex", [research()]),
        observed("cordis", [{"id": "3333333", "title": "Marine acoustics modeling"}]),
    ])
    row = next(r for r in x["eighteen_lane_coverage"] if r["lane"] == "research_to_product")
    assert row["distinct_topic_evidence_classes"] == 1
    assert row["decision"] == "insufficient_topical_cross_source_evidence"


def test_cfpb_public_product_and_issue_are_observable_without_narratives():
    response = review([observed("cfpb", [{
        "public_complaint_id": "987654",
        "product": "Credit card", "issue": "Incorrect fees",
        "narrative": "CONFIDENTIAL_NOT_FOR_HUNTER",
        "date_received": "2026-11-18",
    }])])
    item = response["sample_records"][0]
    assert item["title"] == "Credit card - Incorrect fees"
    assert item["consumer_product"] == "Credit card"
    assert "CONFIDENTIAL_NOT_FOR_HUNTER" not in repr(response)
