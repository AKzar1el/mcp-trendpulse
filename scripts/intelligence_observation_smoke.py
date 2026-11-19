"""No-key live acceptance of offline source observations across three source classes.

Read-only, once per workflow run. Produces bounded status-only diagnostics
without leaking credentials or full upstream records into logs/artifacts.
This smoke NEVER validates paid demand or a new market trend.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from mcp_trendpulse.intelligence_core import BudgetCache, collect, plan_source
from mcp_trendpulse.intelligence_observations import observe_source_snapshots

CASES = (
    # OpenAlex is already exercised by the multi-lane workflow. Its
    # keyless allowance is shared on CI runner IPs and has returned HTTP 429.
    # Avoid duplicate concurrent queries; use independent public GLEIF here.
    ("gleif", {"keyword": "Siemens", "limit": 2}),
    ("cordis", {"keyword": "battery", "limit": 2}),
    ("usaspending", {"keyword": "battery", "limit": 2}),
)


def main() -> int:
    snapshots = []
    diagnostics = []
    with tempfile.TemporaryDirectory(prefix="trendpulse-observation-") as root:
        cache = BudgetCache(Path(root))
        for source, inputs in CASES:
            try:
                plan = plan_source(source, **inputs, env={})
                response = collect(plan, cache=cache, fetch=True, env={}, timeout=22)
                status = response.get("status")
            except (OSError, ValueError) as exc:
                status = "unavailable"
                response = {"source": source, "status": "unavailable"}
                diagnostics.append({
                    "source": source, "status": "unavailable",
                    "error_type": type(exc).__name__,
                })
            else:
                diagnostics.append({
                    "source": source, "status": status,
                    "reason": response.get("reason") if response.get("reason") in {
                        "HTTPError", "TimeoutError", "URLError", "provider_cooldown",
                        "invalid_source_shape", "not_configured",
                    } else None,
                    "http_status": response.get("http_status")
                    if isinstance(response.get("http_status"), int) else None,
                })
            if status not in {"observed", "unavailable", "invalid_source_shape", "rate_limited"}:
                raise AssertionError("Unexpected provider status")
            snapshots.append(response)
    result = observe_source_snapshots("battery", snapshots)
    if len(result["eighteen_lane_coverage"]) != 18:
        raise AssertionError("18-lane availability analysis missing")
    if result["market_momentum"]["complete_28_day_series"]:
        raise AssertionError("Partial searches were promoted to market momentum")
    if result["buyer_budget_verified"] or result["paid_customer_outcome_verified"]:
        raise AssertionError("Source snapshots were promoted to buyer proof")
    if result["success_probability"] is not None:
        raise AssertionError("Invented success probability")
    if not all(s["population_coverage_verified"] is False
               for s in result["source_coverage"]):
        raise AssertionError("Bounded search page wrongly claims population coverage")
    observed_count = sum(x["status"] == "observed" for x in diagnostics)
    summary = {
        "status": "passed" if observed_count >= 2 else "inconclusive",
        "mode": "one_time_read_only_live_observations",
        "source_results": diagnostics,
        "providers_observed": observed_count,
        "sample_records_reviewed": result["records_reviewed"],
        "literal_topic_matches": result["literal_topic_matches_in_sample"],
        "lanes_checked": len(result["eighteen_lane_coverage"]),
        "verified_commercial_winners": 0,
        "buyer_budgets_verified": 0,
    }
    Path("intelligence-observations-live.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary), flush=True)
    return 0 if observed_count >= 2 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "status": "failed", "exception_type": type(exc).__name__,
        }), file=sys.stderr)
        raise SystemExit(1) from None
