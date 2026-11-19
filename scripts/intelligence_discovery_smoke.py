"""Keyless live acceptance for seedless topic discovery.

Status-only diagnostics; no raw external data, personal information, key,
API response body or fabricated commercial predictions in CI artifacts.
Provider unavailability is explicitly inconclusive, not a source pass.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from mcp_trendpulse.intelligence_core import BudgetCache
from mcp_trendpulse.intelligence_discovery import discover_current


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="trendpulse-seedless-") as temp:
        cache = BudgetCache(Path(temp))
        plan = discover_current(execute=False, cache=cache, env={})
        if (plan["status"] != "planned"
                or plan["network_performed"] is not False
                or plan["source_count"] != 3):
            raise AssertionError("Plan-only mode performed network access")
        plan3 = discover_current(
            execute=False, limit=20, lookback_days=30, ted_date_slices=3,
            cache=cache, env={},
        )
        if (plan3["network_performed"] or plan3["request_count"] != 5
                or plan3["source_count"] != 3
                or sum(w["requested_limit"] for w in plan3["ted_windows"]) != 20):
            raise AssertionError("Time-stratified plan is not network-free or bounded")
        measured_plan = discover_current(
            execute=False, limit=20, lookback_days=30, ted_date_slices=3,
            measure_trends=True, cache=cache, env={},
        )
        if (measured_plan["network_performed"]
                or measured_plan["request_count"] != 5
                or measured_plan["max_requests_with_trend_measurement"] != 14
                or measured_plan["trend_evidence"]["network_performed"]
                or measured_plan["trend_evidence"]["max_additional_source_requests"] != 9):
            raise AssertionError("Opt-in trend measurement plan is not bounded and offline")
        broad_plan = discover_current(
            execute=False, limit=20, lookback_days=30, ted_date_slices=3,
            measure_trends=True, broad_topic_scan=True, cache=cache, env={},
        )
        if (broad_plan["network_performed"]
                or broad_plan["request_count"] != 5
                or broad_plan["max_requests_with_trend_measurement"] != 17
                or broad_plan["trend_evidence"]["network_performed"]
                or broad_plan["trend_evidence"]["max_additional_source_requests"] != 12
                or not broad_plan["trend_evidence"]["broad_topic_scan_opted_in"]):
            raise AssertionError("Broad trend plan must remain opt-in and network free")
        result = discover_current(
            execute=True, limit=20, lookback_days=30,
            cache=cache, env={},
        )
    if (result["growth_rate_verified"]
            or result["paid_buyers_verified"]
            or result["population_coverage_verified"]):
        raise AssertionError("Seedless source search fabricated a market trend")
    if any(
        row["commercial_budget_verified"] or row["same_buyer_verified"]
        for row in result["candidates"]
    ):
        raise AssertionError("Unverified records promoted to buyer proof")
    audit = result["ted_sampling_audit"]
    if (audit["sector_share_or_growth_estimable"]
            or audit["registration_identity_independently_verified"]
            or audit["procedure_identity_independently_verified"]
            or not 0 <= audit["with_source_published_buyer_registration"]
                   <= audit["observed_notice_count"]
            or not 0 <= audit["with_source_published_procedure_identifier"]
                   <= audit["observed_notice_count"]
            or any(not x["not_independently_verified_identity"]
                   or x["same_buying_workflow_verified"]
                   for x in result["same_published_identity_repeats_not_candidates"])
            or any(x["hierarchy_level"] == "category_or_finer"
                   for x in result["coarse_cpv_repeats_not_candidates"])):
        raise AssertionError("Procurement grain or sample representativeness fabricated")
    if any(
        c["cpv_hierarchy_level"] != "category_or_finer"
        for c in result["candidates"]
        if c["basis"] == "ted_distinct_published_buyer_labels_shared_primary_cpv"
    ):
        raise AssertionError("Broad primary CPV counted as narrow workflow demand")
    review = result["procurement_review"]
    if (review["qualified_with_published_procedure_estimate"]
            + review["qualified_without_published_procedure_estimate"]
            != review["qualified_notices_in_bounded_sample"]
            or review["estimate_review_is_not_value_or_sector_ranking"] is not True
            or len(result["procurement_estimate_examples"]) > 3
            or len(result["procurement_estimate_examples"])
            != review["procedure_estimate_examples_selected"]
            or any(
                e["confirmed_buyer_budget"] or e["awarded_contract_value"]
                or e["still_open_tender_verified"] or
                e["product_market_fit_verified"]
                or not e["published_procedure_estimate"]
                or not e["published_currency"]
                for e in result["procurement_estimate_examples"]
            )):
        raise AssertionError("Procurement estimate evidence fabricated spending or counts")
    if (review["software_it_not_review_qualified"] < 0
            or review["software_it_not_review_qualified"]
            + review["qualified_main_cpv_software_it"]
            != audit["main_cpv_48_or_72_observed"]):
        raise AssertionError("Published CPV and buyer-review counts disagree")
    if (review["open_bid_status_verified"]
            or review["same_buyer_legal_entity_verified"]
            or review["market_growth_verified"]
            or review["qualified_notices_in_bounded_sample"] <
            review["selected_for_review"]):
        raise AssertionError("Buyer-side review fabricated verification or coverage")
    if sum(x["buyer_side_review_selected"]
           for x in result["procurement_observations"]) != review["selected_for_review"]:
        raise AssertionError("Buyer-side review selection count misreported")
    if (sum(x["buyer_side_review_qualified"]
            for x in result["procurement_observations"]) <
            review["selected_for_review"]):
        raise AssertionError("Buyer-side qualification labels are inconsistent")
    covered = sum(s["status"] == "observed" for s in result["source_coverage"])
    diagnostic = {
        "status": "source_contracts_observed" if covered == 3
                  else "partial_source_availability_inconclusive",
        "mode": "seedless_current_topics_keyless_live_smoke",
        "providers_attempted": 3,
        "per_provider_record_limit_requested": 20,
        "stratified_plan_only_safety_verified": True,
        "trend_measurement_plan_only_safety_verified": True,
        "broad_trend_plan_only_safety_verified": True,
        "providers_observed": covered,
        "source_status": [
            {"source": s["source"], "status": s["status"],
             "http_status": s.get("http_status"),
             "recent_valid_records": s["recent_valid_records"]}
            for s in result["source_coverage"]
        ],
        "sample_recent_records": result["recent_observations"],
        "research_candidates_in_sample": result["candidate_count"],
        "procurement_titles_available": len(result["procurement_observations"]),
        "buyer_side_review_qualified_in_sample": review[
            "qualified_notices_in_bounded_sample"
        ],
        "buyer_side_review_software_it_in_sample": review[
            "qualified_main_cpv_software_it"
        ],
        "buyer_side_review_selected": review["selected_for_review"],
        "buyer_review_with_published_estimate": review[
            "qualified_with_published_procedure_estimate"
        ],
        "buyer_review_without_published_estimate": review[
            "qualified_without_published_procedure_estimate"
        ],
        "procedure_estimate_examples_selected": review[
            "procedure_estimate_examples_selected"
        ],
        "buyer_side_review_it_unqualified_in_sample": review[
            "software_it_not_review_qualified"
        ],
        "procurement_competition_notices_rendered": sum(
            x["procurement_stage"] == "contract_notice_not_award"
            for x in result["procurement_observations"]
        ),
        "procurement_non_competition_notices_rendered": sum(
            x["procurement_stage"] != "contract_notice_not_award"
            for x in result["procurement_observations"]
        ),
        "procurement_with_published_main_cpv": sum(
            bool(x["main_cpv_code"]) for x in result["procurement_observations"]
        ),
        "procurement_with_lot_date": sum(
            bool(x["latest_lot_deadline_date"]) for x in result["procurement_observations"]
        ),
        "ted_pub_days_in_sample": audit["publication_days_represented"],
        "ted_first_page_hit_cap": audit["first_page_hit_record_cap"],
        "ted_primary_48_72_in_sample": audit["main_cpv_48_or_72_observed"],
        "ted_coarse_cpv_repeats_suppressed": len(result[
            "coarse_cpv_repeats_not_candidates"
        ]),
        "ted_with_published_buyer_registration": audit[
            "with_source_published_buyer_registration"
        ],
        "ted_with_published_procedure_identifier": audit[
            "with_source_published_procedure_identifier"
        ],
        "ted_same_published_identity_repeats_suppressed": len(result[
            "same_published_identity_repeats_not_candidates"
        ]),
        "procurement_cpv_buyer_repeat_candidates": sum(
            x["basis"] == "ted_distinct_published_buyer_labels_shared_primary_cpv"
            for x in result["candidates"]
        ),
        "research_titles_available": len(result["research_observations"]),
        "latest_procurement_date": (
            result["procurement_observations"][0]["date"]
            if result["procurement_observations"] else None
        ),
        "market_growth_verified": False,
        "buyer_budget_verified": False,
        "customer_outcomes_verified": False,
        "provider_availability_not_a_code_quality_pass": True,
    }
    Path("intelligence-discovery-smoke.json").write_text(
        json.dumps(diagnostic, indent=2), encoding="utf-8"
    )
    print(json.dumps(diagnostic), flush=True)
    # Fail only if core safety checks fail. External 403/429 is inconclusive,
    # not a code regression; offline tests verify actual shape constraints.
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "status": "failed_core_safety_contract",
            "error_type": type(exc).__name__,
        }), file=sys.stderr)
        raise SystemExit(1) from None
