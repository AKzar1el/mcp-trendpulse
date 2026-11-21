"""One-time, keyless, no-market-winner current-hunter acceptance smoke.

Only fixed public origins and existing per-day budgets. The test is allowed to
report provider outages, but never masks one as missing demand. Only a
status/count summary is uploaded; public source records remain in memory.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from mcp_trendpulse.intelligence_core import BudgetCache
from mcp_trendpulse.intelligence_hunter import hunt_current


def main() -> int:
    sources = ["cordis", "usaspending", "gleif"]
    topics = ["battery recycling", "cloud cost management"]
    planned = hunt_current(topics, sources, execute=False, env={})
    if (planned["status"] != "planned"
            or planned["request_count"] != len(sources) * len(topics)
            or planned["network_performed"] is not False):
        raise AssertionError("Plan-only mode changed its no-network contract")
    with tempfile.TemporaryDirectory(prefix="trendpulse-current-hunter-") as folder:
        result = hunt_current(
            topics, sources, execute=True, env={},
            cache=BudgetCache(Path(folder)),
        )
    if result["longitudinal_history_required_for_current_triage"]:
        raise AssertionError("Current activity cannot require months of history")
    if len(result["topics"]) != 2 or result["paid_apis_used"]:
        raise AssertionError("Current hunt had an unexpected scope")
    if result["buyer_outcomes_verified"] != 0:
        raise AssertionError("Unverified buyer outcomes promoted to proof")
    if any(
        item["success_probability"] is not None
        or item["trend_growth_direction"] != "unknown_without_comparable_baseline"
        or item["sample_population_coverage_verified"]
        or item["buying_intent_confirmed"]
        for item in result["topics"]
    ):
        raise AssertionError("Current search was promoted to a false market forecast")
    healthy = sum(
        x["status"] == "observed"
        for item in result["topics"] for x in item["source_coverage"]
    )
    diagnostic = {
        "status": "passed" if healthy >= 2 else "inconclusive",
        "mode": "keyless_current_first_hunter_live_smoke",
        "topics_checked": len(result["topics"]),
        "source_queries": len(sources) * len(topics),
        "sources_observed": healthy,
        "seed_topics_not_prevalidated": True,
        "current_cross_source_activity_topics": result["active_multi_source_topics"],
        "provider_states": [
            {"topic": item["topic"], "providers": [
                {"source": x["source"], "status": x["status"]}
                for x in item["source_coverage"]
            ]} for item in result["topics"]
        ],
        "historical_baseline_required": False,
        "market_growth_verified": False,
        "buyer_outcomes_verified": False,
        "api_credentials_exposed": False,
    }
    Path("intelligence-hunter-status.json").write_text(
        json.dumps(diagnostic, indent=2), encoding="utf-8",
    )
    print(json.dumps(diagnostic), flush=True)
    return 0 if healthy >= 2 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "status": "failed", "error_type": type(exc).__name__,
        }), file=sys.stderr)
        raise SystemExit(1) from None
