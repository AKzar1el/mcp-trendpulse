"""One-time, no-key, read-only multi-lane provider compatibility verification.

This is NOT a predictive benchmark, automatic buyer join, or market-demand score.
Use only fixed public endpoints with existing TrendPulse source budgets. Source
payloads and possible personal details are never written to CI artifacts.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp_trendpulse.intelligence_core import BudgetCache, collect, plan_source
from mcp_trendpulse.intelligence_opportunities import LANES, SOURCE_KIND

# Sample queries are deliberately small. A keyword match cannot establish
# comparable buyer, workflow, location, or time period. Several scenarios
# deliberately show cross-jurisdiction and unrelated-publisher limitations.
SCENARIOS: tuple[dict[str, Any], ...] = (
    {
        "lane": "research_to_product",
        "topic": "battery",
        "probes": (
            ("cordis", {"keyword": "battery", "limit": 2}),
            ("openalex", {"keyword": "battery", "limit": 2}),
        ),
    },
    {
        "lane": "procurement_regulation",
        "topic": "battery",
        "probes": (
            ("cellar", {"keyword": "battery", "limit": 2}),
            ("ted", {"keyword": "FT = battery", "limit": 2}),
            ("usaspending", {"keyword": "battery", "limit": 2}),
        ),
    },
    {
        "lane": "customer_dispute_ops",
        "topic": "credit card",
        "probes": (
            ("cfpb", {"keyword": "credit card", "limit": 2}),
            ("usaspending", {"keyword": "credit card", "limit": 2}),
        ),
    },
    {
        "lane": "public_cloud_finops",
        "topic": "cloud",
        "probes": (
            ("github_issues", {
                "keyword": "cloud", "identifier": "kubernetes/kubernetes",
                "limit": 2,
            }),
            ("usaspending", {"keyword": "cloud", "limit": 2}),
        ),
    },
    {
        "lane": "vendor_due_diligence",
        "topic": "Siemens",
        "probes": (
            ("gleif", {"keyword": "Siemens", "limit": 2}),
            ("ted", {"keyword": "FT = Siemens", "limit": 2}),
        ),
    },
    {
        "lane": "sme_margin",
        "topic": "German economic context",
        "probes": (
            ("eurostat", {
                "dataset": "nama_10_gdp", "country": "DE", "limit": 2,
            }),
            ("worldbank", {
                "identifier": "NY.GDP.MKTP.CD", "country": "DE", "limit": 2,
            }),
            ("greenhouse", {"company": "mozilla", "limit": 2}),
        ),
    },
)


def validate_recipes() -> dict[str, Any]:
    """Audit allowlists and source classes without network or credentials."""
    pairs: set[tuple[str, str]] = set()
    unique_sources: set[str] = set()
    for case in SCENARIOS:
        lane = case["lane"]
        if lane not in LANES:
            raise AssertionError("Unregistered investigation lane")
        probes = case["probes"]
        if not 2 <= len(probes) <= 5:
            raise AssertionError("Lane should have 2-5 bounded source probes")
        for source, params in probes:
            if source not in LANES[lane]["sources"] or source not in SOURCE_KIND:
                raise AssertionError("Probe is not valid for the selected lane")
            if (lane, source) in pairs:
                raise AssertionError("Duplicated lane/source probe")
            pairs.add((lane, source))
            unique_sources.add(source)
            if params.get("limit", 0) > 2:
                raise AssertionError("Live probe unexpectedly exceeds 2 records")
            plan = plan_source(source, **params, env={})
            # Some public SPARQL services require an Accept content-type
            # header; disallow *credential* headers, not harmless negotiation.
            if plan.allow_loopback or any(
                name.lower() not in {"accept", "user-agent"}
                for name in plan.headers
            ):
                raise AssertionError("Live probe must be keyless and remote-public")
            if any(term in plan.url.lower() for term in ("apikey=", "api_key=", "token=")):
                raise AssertionError("Credential-looking query parameter")
    return {
        "recipes": len(SCENARIOS),
        "source_slots": len(pairs),
        "unique_public_sources": len(unique_sources),
        "mode": "no_key_only",
    }


def offline_checks() -> int:
    facts = validate_recipes()
    assert facts["recipes"] == 6
    assert facts["unique_public_sources"] >= 10
    # A live transport matrix must never claim correlated buyer identities.
    assert not any("buyer_entity" in case for case in SCENARIOS)
    print(json.dumps({"status": "passed", **facts}), flush=True)
    return 0


def live_checks(report: Path) -> int:
    facts = validate_recipes()
    observations: dict[str, dict[str, Any]] = {}
    scenarios: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="trendpulse-keyless-matrix-") as root:
        store = BudgetCache(Path(root))
        for case in SCENARIOS:
            sources = []
            for source, params in case["probes"]:
                plan = plan_source(source, **params, env={})
                # Distinct queries remain distinct. Repeated exact inputs reuse
                # the same bounded cached response and do not spend quota twice.
                signature = json.dumps(
                    [source, params], sort_keys=True, separators=(",", ":")
                )
                if signature not in observations:
                    start = time.monotonic()
                    try:
                        result = collect(
                            plan, cache=store, fetch=True, timeout=18, env={},
                        )
                        status = result.get("status", "missing_status")
                        evidence = result.get("observations") or {}
                        count = evidence.get("record_count") if status == "observed" else None
                        if status == "observed" and (
                            not isinstance(count, int) or count < 0
                        ):
                            raise AssertionError("Observed provider has invalid record count")
                        summary = {
                            "source": source,
                            "status": status,
                            "record_count": count,
                            "reason": result.get("reason"),
                            "http_status": result.get("http_status"),
                            "source_class": SOURCE_KIND[source],
                            "retrieval_ms": round((time.monotonic() - start) * 1000),
                        }
                    except (ValueError, OSError, AssertionError) as exc:
                        summary = {
                            "source": source,
                            "status": "not_verified",
                            "exception_type": type(exc).__name__,
                            "source_class": SOURCE_KIND[source],
                            "record_count": None,
                        }
                    observations[signature] = summary
                sources.append(observations[signature])
            observed = [x for x in sources if x["status"] == "observed"
                        and x["record_count"] > 0]
            scenarios.append({
                "lane": case["lane"],
                "topic": case["topic"],
                "sources": sources,
                "observed_nonempty_sources": len(observed),
                "distinct_observed_source_classes": len({
                    x["source_class"] for x in observed
                }),
                "technical_multi_source_compatible": len(observed) >= 2,
                "same_buyer_verified": False,
                "geography_and_period_join_verified": False,
                "customer_payment_verified": False,
                "commercial_opportunity_validated": False,
                "why_not_ranked": (
                    "Original legal/buyer identities, dated purchasing facts, "
                    "comparable jurisdictions and historical customer outcomes "
                    "have not been independently joined or verified."
                ),
            })
    all_checks = list(observations.values())
    status = "completed" if any(
        c["observed_nonempty_sources"] >= 2 for c in scenarios
    ) else "insufficient_live_sources"
    final = {
        "status": status,
        "mode": "one_time_keyless_source_compatibility",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        **facts,
        "observed_unique_queries": sum(
            x["status"] == "observed" for x in all_checks
        ),
        "unique_queries_tested": len(all_checks),
        "combinations_with_two_observed_sources": sum(
            x["technical_multi_source_compatible"] for x in scenarios
        ),
        "commercial_success_probability": None,
        "real_buyer_outcome_backtest_performed": False,
        "no_market_winner_claim": True,
        "scenarios": scenarios,
    }
    report.write_text(
        json.dumps(final, indent=2, ensure_ascii=False), encoding="utf-8",
    )
    print(json.dumps({
        "mode": final["mode"], "status": status,
        "scenarios": len(scenarios),
        "unique_queries": len(all_checks),
        "observed": final["observed_unique_queries"],
        "technical_combinations": final["combinations_with_two_observed_sources"],
        "commercial_proof": False,
    }), flush=True)
    # Only an entirely unusable public-source test matrix is a CI blocker;
    # an upstream outage must be visible without becoming fake negative demand.
    return 0 if status == "completed" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("offline", "live"), default="offline")
    parser.add_argument("--report", default="intelligence-multi-lane.json")
    args = parser.parse_args()
    try:
        if args.mode == "offline":
            return offline_checks()
        return live_checks(Path(args.report))
    except Exception as exc:
        print(json.dumps({
            "status": "failed", "mode": args.mode,
            "exception_type": type(exc).__name__,
        }), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
