"""Free-only opt-in OpenAlex topic landscape scan.

Three source-counted top-100 group pages broaden observation beyond the newest
20 papers. A maximum of two recent topics absent from older rankings receive
direct historical source-count checks rather than invented zero baselines.
Even this remains a bounded, partial scan, NOT a survey of the entire
OpenAlex topic universe or evidence of sales/search demand.
"""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from typing import Any
from urllib.parse import urlencode

from mcp_trendpulse.intelligence_core import (
    BudgetCache, IntelligenceError, Plan, collect, plan_source,
)
from mcp_trendpulse.intelligence_trends import (
    PERIOD_COUNT, PUBLICATION_TYPES, TOPIC_ID, _count_plan, _read_count,
    classify_publication_momentum, completed_periods,
)

TOP_GROUPS_PER_PERIOD = 100  # OpenAlex API supported standard per_page max
GROUP_REQUESTS = PERIOD_COUNT
MAX_MISSING_HISTORY_PROBES = 2
MAX_HISTORY_PROBE_REQUESTS = PERIOD_COUNT * MAX_MISSING_HISTORY_PROBES
MAX_SCAN_REQUESTS = GROUP_REQUESTS + MAX_HISTORY_PROBE_REQUESTS
WATCHLIST_LIMIT = 8
ANOMALY_REVIEW_LIMIT = 6
CAUTION_DIRECTIONS = {
    "abrupt_publication_spike_needs_validation",
    "volatile_rebound_needs_validation",
}


def _group_plan(template: Plan, period: dict[str, str]) -> Plan:
    """Trusted fixed OpenAlex origin; only public, non-sync filters."""
    start = date.fromisoformat(period["from"])
    end = date.fromisoformat(period["through"])
    if start > end:
        raise ValueError("Trend period must be chronological")
    return replace(template, url="https://api.openalex.org/works?" + urlencode({
        "filter": ",".join([
            f"from_publication_date:{start.isoformat()}",
            f"to_publication_date:{end.isoformat()}",
            "type:" + PUBLICATION_TYPES,
        ]),
        "group_by": "primary_topic.id",
        "per_page": TOP_GROUPS_PER_PERIOD,
    }))


def _read_group_counts(result: dict[str, Any]) -> dict[str, Any] | None:
    """Validate a bounded OpenAlex group-by response without inventing zeros."""
    if not isinstance(result, dict) or result.get("status") != "observed":
        return None
    data = result.get("data")
    if not isinstance(data, dict):
        return None
    meta = data.get("meta")
    groups = data.get("group_by")
    total = meta.get("count") if isinstance(meta, dict) else None
    if (isinstance(total, bool) or not isinstance(total, int)
            or not 1 <= total <= 10_000_000_000
            or not isinstance(groups, list)
            or not 1 <= len(groups) <= TOP_GROUPS_PER_PERIOD):
        return None
    found: dict[str, dict[str, Any]] = {}
    for group in groups:
        if not isinstance(group, dict):
            return None
        key, count, label = (group.get("key"), group.get("count"),
                             group.get("key_display_name"))
        match = TOPIC_ID.fullmatch(key) if isinstance(key, str) else None
        if (match is None or isinstance(count, bool)
                or not isinstance(count, int) or not 0 < count <= total
                or not isinstance(label, str)):
            # A non-topic or provider-derived "unknown" bucket is not a
            # genuine topic. Ignore rather than guessing a trend from it.
            continue
        label = "".join(
            (x if x.isprintable() else " ") for x in label
        ).strip()
        label = re.sub(r"\s+", " ", label)[:100]
        code = match.group(1)
        if not label or code in found:
            return None
        found[code] = {"label": label, "count": count}
    if not found:
        return None
    return {"corpus_count": total, "topic_groups": found,
            "groups_received": len(groups)}


def _publication_count(
    template: Plan, period: dict[str, str], topic_id: str, *,
    cache: BudgetCache | None = None, env: dict[str, str] | None = None,
) -> int | None:
    """Explicitly verify one history cell with a real OpenAlex source total."""
    plan = _count_plan(template, period, topic_id)
    try:
        result = collect(plan, fetch=True, cache=cache, env=env, timeout=20)
    except (OSError, ValueError, IntelligenceError):
        return None
    return _read_count(result)


def scan_openalex_topic_landscape(
    *, as_of: date, lookback_days: int, cache: BudgetCache | None = None,
    env: dict[str, str] | None = None,
    probe_recent_missing: bool = True,
) -> dict[str, Any]:
    """Three grouped pages plus up to six measured gap-history requests.

    Returning a topic in the newest top 100 but not an older top 100
    proves only RANKING omission. A real change is reported only after
    exact date/topic count GETs succeed for all three periods.
    """
    if not isinstance(probe_recent_missing, bool):
        raise ValueError("probe_recent_missing must be a boolean")
    periods = completed_periods(as_of, lookback_days)
    output: dict[str, Any] = {
        "status": "unavailable",
        "mode": "bounded_top100_research_with_verified_recent_history_probes",
        "scan_source": "openalex",
        "source_requests": 0,
        "max_source_requests": MAX_SCAN_REQUESTS,
        "grouped_source_requests": GROUP_REQUESTS,
        "historical_probe_source_requests": 0,
        "max_history_probe_candidates": MAX_MISSING_HISTORY_PROBES,
        "top_topic_groups_per_period": TOP_GROUPS_PER_PERIOD,
        "topic_groups_observed_per_period": [],
        "compared_topic_ids_present_in_all_three_pages": 0,
        "not_comparable_groups_due_to_ranking_truncation": 0,
        "recent_top100_missing_older_rankings": 0,
        "history_probe_candidate_count": 0,
        "history_probe_measured": 0,
        "history_probe_unavailable": 0,
        "history_probe_inconsistent_recent_counts": 0,
        "history_probe_results": [],
        "periods": periods,
        "rising_or_accelerating_watchlist": [],
        "unconfirmed_spikes_for_source_audit": [],
        "unconfirmed_spikes_not_product_idea_leads": True,
        "buyer_or_market_growth_verified": False,
        "not_a_complete_niche_scan": True,
        "omitted_group_not_equivalent_to_zero_count": True,
        "history_probe_counts_are_source_observed_not_market_demand": True,
    }
    template = plan_source(
        "openalex", discover=True, lookback_days=lookback_days,
        limit=1, env=env,
    )
    rows: list[dict[str, Any] | None] = []
    for period in periods:
        plan = _group_plan(template, period)
        output["source_requests"] += 1
        try:
            response = collect(plan, fetch=True, cache=cache, env=env,
                               timeout=20)
        except (OSError, ValueError, IntelligenceError):
            response = {"status": "unavailable"}
        parsed = _read_group_counts(response)
        rows.append(parsed)
        output["topic_groups_observed_per_period"].append(
            len(parsed["topic_groups"]) if parsed is not None else None
        )
    if any(x is None for x in rows):
        output["status"] = "unavailable_or_partial_source_pages"
        return output

    old, middle, recent = rows
    old_ids = set(old["topic_groups"])
    middle_ids = set(middle["topic_groups"])
    recent_ids = set(recent["topic_groups"])
    common = old_ids & middle_ids & recent_ids
    union = old_ids | middle_ids | recent_ids
    output["compared_topic_ids_present_in_all_three_pages"] = len(common)
    output["not_comparable_groups_due_to_ranking_truncation"] = len(union - common)
    output["recent_top100_missing_older_rankings"] = len(recent_ids - common)
    denominators = [x["corpus_count"] for x in rows]
    upward = {
        "newly_observed_research_activity",
        "accelerating_research_share",
        "rising_research_share",
        "early_rising_research_watchlist",
    }
    shared_signals = []
    anomaly_review = []
    for code in sorted(common):
        counted = [
            old["topic_groups"][code]["count"],
            middle["topic_groups"][code]["count"],
            recent["topic_groups"][code]["count"],
        ]
        measured = classify_publication_momentum(counted, denominators)
        if (measured["direction"] not in upward
                and measured["direction"] not in CAUTION_DIRECTIONS):
            continue
        item = {
            "topic_id": code,
            "label": recent["topic_groups"][code]["label"],
            "source_topic_reference": "https://openalex.org/" + code,
            "topic_counts": counted,
            "corpus_counts": denominators,
            "sample_selection": "top100_in_each_of_three_mature_periods",
            "historical_cells_verified_by_direct_count": False,
            **measured,
        }
        if measured["direction"] in CAUTION_DIRECTIONS:
            anomaly_review.append(item)
        else:
            shared_signals.append(item)

    niche_signals = []
    if probe_recent_missing:
        gap_candidates = list(recent_ids - common)
        # Prefer a topic absent from BOTH older rankings, then one absent
        # from only one. This prioritizes a provenance gap for verification;
        # it DOES NOT equate ranking entry with emergence or growth.
        gap_candidates.sort(key=lambda code: (
            -int(code not in old_ids) - int(code not in middle_ids),
            -recent["topic_groups"][code]["count"], code,
        ))
        for code in gap_candidates[:MAX_MISSING_HISTORY_PROBES]:
            output["history_probe_candidate_count"] += 1
            counted: list[int | None] = []
            for period in periods:
                output["source_requests"] += 1
                output["historical_probe_source_requests"] += 1
                count = _publication_count(
                    template, period, code, cache=cache, env=env,
                )
                counted.append(count)
                if count is None:
                    break
            label = recent["topic_groups"][code]["label"]
            probe: dict[str, Any] = {
                "topic_id": code,
                "label": label,
                "source_topic_reference": "https://openalex.org/" + code,
                "missing_from_older_top100_pages": sum(
                    [code not in old_ids, code not in middle_ids]
                ),
                "source_count_queries_performed": len(counted),
                "published_source_counts": counted,
                "not_a_market_or_buyer_validation": True,
            }
            if len(counted) != PERIOD_COUNT or any(n is None for n in counted):
                probe["status"] = "unavailable_source_count"
                output["history_probe_unavailable"] += 1
                output["history_probe_results"].append(probe)
                continue
            # A provider backfill/change between group_by and count calls
            # must not quietly become a commercial story.
            visible_recent = recent["topic_groups"][code]["count"]
            if abs(counted[-1] - visible_recent) > max(3, visible_recent // 20):
                probe["status"] = "inconsistent_source_snapshots"
                output["history_probe_inconsistent_recent_counts"] += 1
                output["history_probe_results"].append(probe)
                continue
            measured = classify_publication_momentum(counted, denominators)
            if not measured["research_share_measured"]:
                probe["status"] = "invalid_source_count_comparison"
                output["history_probe_unavailable"] += 1
                output["history_probe_results"].append(probe)
                continue
            output["history_probe_measured"] += 1
            probe["status"] = "measured"
            probe["research_direction"] = measured["direction"]
            output["history_probe_results"].append(probe)
            if (measured["direction"] in upward
                    or measured["direction"] in CAUTION_DIRECTIONS):
                item = {
                    "topic_id": code, "label": label,
                    "source_topic_reference": "https://openalex.org/" + code,
                    "topic_counts": counted, "corpus_counts": denominators,
                    "sample_selection":
                        "recent_top100_history_verified_by_three_direct_counts",
                    "historical_cells_verified_by_direct_count": True,
                    **measured,
                }
                if measured["direction"] in CAUTION_DIRECTIONS:
                    anomaly_review.append(item)
                else:
                    niche_signals.append(item)

    def ranking(row: dict[str, Any]) -> tuple[float, int, str]:
        return (
            -(row.get("oldest_to_recent_share_change_percent") or 0),
            -row["topic_counts"][-1], row["topic_id"],
        )

    shared_signals.sort(key=ranking)
    niche_signals.sort(key=ranking)
    # Reserve up to two display places for source-verified emerging-rank
    # candidates. Otherwise the most populated stable fields dominate.
    reserved = min(MAX_MISSING_HISTORY_PROBES, len(niche_signals))
    shown = shared_signals[:WATCHLIST_LIMIT - reserved] + niche_signals[:reserved]
    output["rising_or_accelerating_watchlist"] = sorted(shown, key=ranking)
    anomaly_review.sort(key=ranking)
    output["unconfirmed_spikes_for_source_audit"] = anomaly_review[
        :ANOMALY_REVIEW_LIMIT
    ]
    output["status"] = "observed_bounded_top100_overlap"
    return output


def format_broad_topic_scan(scan: dict[str, Any]) -> list[str]:
    lines = [
        "BROADER TOPIC MOMENTUM SCAN (OpenAlex, opt-in):",
        "  Most represented 100 topic groups per completed date window. "
        "Top-100 ranking absence means UNKNOWN, not zero or decline. "
        "A maximum of two recent-only ranking gaps get direct history counts.",
    ]
    if scan["status"] != "observed_bounded_top100_overlap":
        lines.append(
            "  Grouped source evidence unavailable/incomplete; "
            "no broad topic direction inferred."
        )
        return lines
    lines.append(
        "  Groups observed by period: " +
        " → ".join(map(str, scan["topic_groups_observed_per_period"]))
        + "; present in all three: "
        + str(scan["compared_topic_ids_present_in_all_three_pages"])
        + "; incomparable because of ranking truncation: "
        + str(scan["not_comparable_groups_due_to_ranking_truncation"]) + "."
    )
    lines.append(
        "  Recent top-100 topics absent from one or both older top-100 lists: "
        + str(scan["recent_top100_missing_older_rankings"])
        + "; followed up with complete period counts: "
        + str(scan["history_probe_candidate_count"])
        + "; measured: " + str(scan["history_probe_measured"])
        + "; source-unavailable: " + str(scan["history_probe_unavailable"])
        + "; inconsistent source snapshots: "
        + str(scan["history_probe_inconsistent_recent_counts"]) + "."
    )
    signals = scan["rising_or_accelerating_watchlist"]
    anomalies = scan.get("unconfirmed_spikes_for_source_audit", [])
    if not signals:
        lines.append(
            "  No qualifying SUSTAINED upward research-share signal among "
            "the comparable or verified follow-up topics; unmeasured niches "
            "remain UNKNOWN."
        )
    for i, row in enumerate(signals, 1):
        change = row["oldest_to_recent_share_change_percent"]
        if isinstance(change, (int, float)) and not isinstance(change, bool):
            change_label = f"{change:+.1f}%"
        else:
            # A source-confirmed zero baseline makes percentage growth
            # mathematically undefined. Do not fabricate infinity/100%.
            change_label = "undefined (measured zero first-period baseline)"
        mode = (
            "three additional source-count checks"
            if row["historical_cells_verified_by_direct_count"]
            else "same topic in all three ranked windows"
        )
        lines.append(
            f"  {i}. {row['label']} [{row['topic_id']}] "
            f"— {row['direction'].replace('_', ' ')} | "
            f"source-normalized research share change {change_label}"
        )
        lines.append("     Evidence: " + mode)
        lines.append(
            "     Research works across completed periods: "
            + " → ".join(map(str, row["topic_counts"]))
        )
        lines.append(
            "     Topic works per million comparable publications: "
            + " → ".join(str(x) for x in row["share_per_million"])
        )
        lines.append("     " + row["source_topic_reference"])
    if anomalies:
        lines.append(
            "  UNCONFIRMED PUBLICATION SPIKES — NOT product-idea "
            "growth leads; inspect source indexing, publication dates "
            "and independent evidence:"
        )
        for row in anomalies:
            lines.append(
                "    " + row["label"] + " [" + row["topic_id"] + "]"
                + " — " + row["direction"].replace("_", " ")
            )
            lines.append(
                "      Actual source works, old → middle → recent: "
                + " → ".join(map(str, row["topic_counts"]))
            )
            lines.append(
                "      Normalized works per million: "
                + " → ".join(map(str, row["share_per_million"]))
            )
            lines.append("      " + row["source_topic_reference"])
    lines.append(
        "  This is a bounded source-count scan, not all 4,516 topics "
        "or a survey of emerging product niches; source indexing/classifier "
        "changes can revise historical counts. Google keyword demand, "
        "product adoption, buyers and market growth are NOT verified."
    )
    return lines
