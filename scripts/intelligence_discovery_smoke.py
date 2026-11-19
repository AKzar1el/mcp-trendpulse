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
    covered = sum(s["status"] == "observed" for s in result["source_coverage"])
    diagnostic = {
        "status": "source_contracts_observed" if covered == 3
                  else "partial_source_availability_inconclusive",
        "mode": "seedless_current_topics_keyless_live_smoke",
        "providers_attempted": 3,
        "per_provider_record_limit_requested": 20,
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
