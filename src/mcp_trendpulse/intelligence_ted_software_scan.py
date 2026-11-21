"""Opt-in TED software opportunity coverage, independent of unbiased 20-row page.

A single explicitly CPV-filtered, bounded official TED search may recover
IT/software primary-classification procurements absent from a sector-neutral
page. Query inclusion is NOT market growth or representative sector frequency.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import date, timedelta
from typing import Any

from mcp_trendpulse.intelligence_core import (
    BudgetCache, DailyBudgetExceeded, IntelligenceError, collect, plan_source,
)

MAX_FOCUS_ROWS = 12
MAX_FOCUS_ADDITIONAL_REQUESTS = 1
FOCUS_PREFIXES = ("48", "72")


def software_scan_query(as_of: date, lookback_days: int) -> str:
    if (not isinstance(as_of, date) or isinstance(lookback_days, bool)
            or not isinstance(lookback_days, int)
            or not 7 <= lookback_days <= 90):
        raise ValueError("Invalid date or lookback for bounded TED software scan")
    start = as_of - timedelta(days=lookback_days - 1)
    # TED expert-search field alias PC = classification-cpv; PD = publication-date.
    # The short official aliases leave room for the ORDER BY expression in the
    # source builder's conservative 140-character budget. Without SORT BY,
    # the first page can contain only the oldest publications in the window.
    # No topic, vendor or product term is supplied.
    query = (
        f"PD = ({start:%Y%m%d} <> {as_of:%Y%m%d}) "
        "AND notice-type IN (cn-standard cn-social cn-desg) "
        "AND (PC=48* OR PC=72*) SORT BY publication-date DESC"
    )
    if len(query) > 140:
        raise ValueError("Unexpected TED query size")
    return query


def scan_software_procurements(
    *, as_of: date, lookback_days: int = 30,
    cache: BudgetCache | None = None, env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """One free official source request; no loss of the neutral baseline."""
    query = software_scan_query(as_of, lookback_days)
    plan = plan_source(
        "ted", keyword=query, limit=MAX_FOCUS_ROWS, env=env,
    )
    result = {
        "mode": "ted_primary_software_it_focused_sample_not_market_prevalence",
        "status": "unavailable",
        "source": "ted",
        "query_classification": "cpv_48_or_72_any_classification_search",
        "qualification_classification": "main_cpv_48_or_72_only",
        "source_query_requests_publication_date_desc": True,
        "source_ordering_verified_by_observation": False,
        "sample_date_order": "not_observed",
        "source_requests_budgeted": MAX_FOCUS_ADDITIONAL_REQUESTS,
        "max_additional_source_requests": MAX_FOCUS_ADDITIONAL_REQUESTS,
        "source_requests_performed": 0,
        "sampled_records": 0,
        "qualified_primary_software_briefs": 0,
        "added_to_combined_briefs": 0,
        "sample_hit_cap": False,
        "keyword_seed_list_used": False,
        "searched_publication_date_not_bid_status": True,
        "buyer_willingness_to_pay_verified": False,
        "recurring_market_growth_verified": False,
        "population_prevalence_verifiable": False,
        "independent_baseline_preserved": True,
        "briefs": [],
    }
    try:
        outcome = collect(plan, fetch=True, cache=cache, env=env, timeout=20)
    except DailyBudgetExceeded as exc:
        # No HTTP request was made. The typed local limit is safe to publish.
        outcome = {
            "status": "unavailable", "reason": "local_daily_budget_exhausted",
        }
        result["local_quota_utc_day"] = exc.utc_day
        result["local_quota_used"] = exc.used
        result["local_quota_limit"] = exc.cap
    except sqlite3.Error:
        outcome = {
            "status": "unavailable", "reason": "local_cache_storage_error",
        }
    except (OSError, ValueError, IntelligenceError):
        outcome = {"status": "unavailable", "reason": "collection_failed"}
    result["cache_hit"] = outcome.get("cache_hit") is True
    safe_reasons = {
        "local_daily_budget_exhausted", "local_cache_storage_error",
        "provider_cooldown", "HTTPError", "URLError", "TimeoutError",
        "collection_failed",
    }
    raw_reason = outcome.get("reason")
    reason = raw_reason if isinstance(raw_reason, str) else ""
    if outcome.get("status") != "observed":
        result["source_failure_reason"] = (
            reason if reason in safe_reasons else "source_failure_unclassified"
        )
    result["source_requests_performed"] = (
        0 if result["cache_hit"] or reason in {
            "provider_cooldown", "local_daily_budget_exhausted",
            "local_cache_storage_error",
        } else 1
    )
    state = outcome.get("status")
    if state != "observed":
        result["status"] = (state if state in {
            "unavailable", "rate_limited", "invalid_source_shape",
        } else "unavailable")
        http = outcome.get("http_status")
        if isinstance(http, int) and not isinstance(http, bool) and 400 <= http <= 599:
            result["http_status"] = http
        return result
    observations = outcome.get("observations")
    rows = observations.get("sample") if isinstance(observations, dict) else None
    if (not isinstance(rows, list) or len(rows) > MAX_FOCUS_ROWS
            or any(not isinstance(r, dict) for r in rows)):
        result["status"] = "invalid_source_shape"
        return result
    # Summarize independently: a source-filtered page never inflates the
    # unbiased baseline's prevalence counts, date-window audit or candidates.
    from mcp_trendpulse.intelligence_discovery import (
        _compact_ted_discovery, summarize_discovery,
    )

    sanitized = [_compact_ted_discovery(r) for r in rows]
    # Validate and report the order of the *returned* page separately from
    # the sort requested in the expert query. Equal-day ties are expected.
    observed_dates = []
    for raw in sanitized:
        published = raw.get("publication-date")
        if not isinstance(published, str) or len(published) < 10:
            continue
        try:
            observed_dates.append(date.fromisoformat(published[:10]))
        except ValueError:
            continue
    observed_order = (
        "not_observed" if not observed_dates
        else "sample_descending_or_same_day"
        if len(observed_dates) == len(rows)
        and observed_dates == sorted(observed_dates, reverse=True)
        else "sample_unordered_or_dated_rows_missing"
    )
    summary = summarize_discovery([{
        "source": "ted", "status": "observed",
        "observations": {"sample": sanitized, "record_count": len(sanitized)},
    }], as_of=as_of.isoformat(), lookback_days=lookback_days,
        workflow_briefs=True)
    focus = summary["workflow_briefs"]
    eligible = [
        {**brief, "observation_sampling_basis": (
            "cpv_filtered_ted_page_not_neutral_baseline_or_market_population"
        )}
        for brief in focus["briefs"]
        if brief.get("kind") == "published_software_it_procurement_to_investigate"
        and brief.get("published_lot_date_on_or_after_analysis") is True
    ]
    result.update({
        "status": "source_observed_with_qualified_briefs"
                  if eligible else "source_observed_without_qualified_primary_it_briefs",
        "sampled_records": len(sanitized),
        "sample_date_order": observed_order,
        "source_ordering_verified_by_observation": (
            observed_order == "sample_descending_or_same_day"
        ),
        "earliest_sampled_publication": (
            min(observed_dates).isoformat() if observed_dates else ""
        ),
        "latest_sampled_publication": (
            max(observed_dates).isoformat() if observed_dates else ""
        ),
        "qualified_primary_software_briefs": len(eligible),
        "sample_hit_cap": len(sanitized) == MAX_FOCUS_ROWS,
        "source_recent_valid_records": summary["source_coverage"][0][
            "recent_valid_records"
        ],
        "sampled_primary_it_records": summary["ted_sampling_audit"][
            "main_cpv_48_or_72_observed"
        ],
        "briefs": eligible,
    })
    return result


def merge_focused_briefs(
    workflow: dict[str, Any], focused: dict[str, Any],
) -> int:
    """Add distinct tender proofs within existing six-brief/four-tender limits.

    Focusing never promotes source observations to market trends, alters
    the neutral baseline counters or creates a new customer identity.
    """
    if (workflow.get("mode") != "source_grounded_workflow_briefs_not_validated_market_demand"
            or focused.get("mode") !=
            "ted_primary_software_it_focused_sample_not_market_prevalence"):
        raise ValueError("Unexpected typed source evidence for focused merge")
    rows = workflow.get("briefs")
    if not isinstance(rows, list) or len(rows) > 6:
        raise ValueError("Expected bounded original workflow briefs")
    existing_refs = {
        b["evidence"][0]["reference"]
        for b in rows if isinstance(b, dict)
        and isinstance(b.get("evidence"), list)
        and b["evidence"] and isinstance(b["evidence"][0], dict)
        and isinstance(b["evidence"][0].get("reference"), str)
    }
    it_count = sum(
        isinstance(row, dict)
        and row.get("kind") == "published_software_it_procurement_to_investigate"
        for row in rows
    )
    count = 0
    for brief in focused.get("briefs", [])[:4]:
        if len(rows) == 6 or it_count == 4:
            break
        proof = brief.get("evidence")
        ref = proof[0].get("reference") if isinstance(proof, list) and proof else None
        if (not isinstance(ref, str) or not re.fullmatch(
            r"https://ted\.europa\.eu/en/notice/-/detail/[0-9]{1,7}-20[0-9]{2}",
            ref,
        ) or ref in existing_refs):
            continue
        rows.append(brief)
        existing_refs.add(ref)
        it_count += 1
        count += 1
    workflow["brief_count"] = len(rows)
    workflow["targeted_ted_software_briefs_added"] = count
    workflow["targeted_evidence_cannot_change_neutral_baseline_sector_counts"] = True
    focused["added_to_combined_briefs"] = count
    return count


def format_software_scan(report: dict[str, Any]) -> list[str]:
    if report.get("mode") != "ted_primary_software_it_focused_sample_not_market_prevalence":
        raise ValueError("Expected focused TED evidence")
    lines = [
        "FOCUSED TED SOFTWARE/IT PROCUREMENT DISCOVERY (explicit opt-in, 1 extra free query):",
        "  Separate CPV 48/72-filtered sample; does NOT revise neutral 20-notice coverage or prove market growth.",
        f"  TED source: {report['status']} | sampled: {report['sampled_records']}/{MAX_FOCUS_ROWS} "
        f"| qualifying primary-CPV briefs: {report['qualified_primary_software_briefs']}"
        f" | added: {report['added_to_combined_briefs']}"
        + (" (cached)" if report.get("cache_hit") else ""),
    ]
    if report.get("sample_hit_cap"):
        lines.append("  Filtered first page hit 12-row cap; not exhaustive for the sector.")
    if report.get("sampled_records"):
        lines.append(
            "  Requested newest-first TED ordering | returned sample: "
            + report["sample_date_order"]
            + " | sampled publication span: "
            + (report["earliest_sampled_publication"] or "unknown")
            + " to "
            + (report["latest_sampled_publication"] or "unknown")
        )
        if not report.get("source_ordering_verified_by_observation"):
            lines.append(
                "  Warning: published-date order cannot be established from"
                " this bounded provider sample; no recency guarantee."
            )
    if report.get("http_status"):
        lines.append(f"  Source HTTP {report['http_status']} (unavailable; NOT no demand)")
    if report["status"] in {"unavailable", "rate_limited", "invalid_source_shape"}:
        lines.append(
            "  TED collection did not produce a usable focused sample;"
            " eligibility is UNKNOWN, not zero opportunities."
        )
        if report.get("source_failure_reason"):
            lines.append(
                "  Source failure: " + report["source_failure_reason"]
            )
        if report.get("source_failure_reason") == "local_daily_budget_exhausted":
            lines.append(
                "  UTC " + report["local_quota_utc_day"]
                + " local TED quota "
                + str(report["local_quota_used"])
                + "/" + str(report["local_quota_limit"])
                + " exhausted; no bypass or automatic retry."
            )
    elif not report["briefs"]:
        lines.append(
            "  No eligible primary-CPV software notices in the observed bounded"
            " page; NOT a market-wide negative finding."
        )
    for item in report["briefs"][:4]:
        evidence = item["evidence"][0]
        lines.append("  - " + item["source_published_workflow_clue"])
        lines.append("    " + evidence["reference"])
    return lines
