"""Free-only opt-in OpenAlex topic landscape scan.

Three counted, top-20 group_by pages broaden observation beyond the newest
20 papers. This is explicitly a TOP-20-PER-PERIOD *mainstream* snapshot,
not complete coverage of 4,516 topics, niche discovery, or market demand.
A group missing from any window is *unknown* due to ranking/truncation,
never interpreted as zero papers.
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
    PERIOD_COUNT, PUBLICATION_TYPES, TOPIC_ID, classify_publication_momentum,
    completed_periods,
)

TOP_GROUPS_PER_PERIOD = 20
GROUP_REQUESTS = PERIOD_COUNT
WATCHLIST_LIMIT = 8


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


def scan_openalex_topic_landscape(
    *, as_of: date, lookback_days: int, cache: BudgetCache | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """At most 3 fixed free requests; compare only shared top-20 topic IDs."""
    periods = completed_periods(as_of, lookback_days)
    output: dict[str, Any] = {
        "status": "unavailable",
        "mode": "bounded_mainstream_topic_landscape_not_complete_market_scan",
        "scan_source": "openalex",
        "source_requests": 0,
        "max_source_requests": GROUP_REQUESTS,
        "top_topic_groups_per_period": TOP_GROUPS_PER_PERIOD,
        "topic_groups_observed_per_period": [],
        "compared_topic_ids_present_in_all_three_pages": 0,
        "not_comparable_groups_due_to_top20_truncation": 0,
        "periods": periods,
        "rising_or_accelerating_watchlist": [],
        "buyer_or_market_growth_verified": False,
        "not_a_complete_niche_scan": True,
        "omitted_group_not_equivalent_to_zero_count": True,
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

    old, mid, recent = rows
    common = set(old["topic_groups"]) & set(mid["topic_groups"]) & set(recent["topic_groups"])
    union = set(old["topic_groups"]) | set(mid["topic_groups"]) | set(recent["topic_groups"])
    output["compared_topic_ids_present_in_all_three_pages"] = len(common)
    output["not_comparable_groups_due_to_top20_truncation"] = len(union - common)
    denominators = [x["corpus_count"] for x in rows]
    upward = {
        "newly_observed_research_activity",
        "accelerating_research_share",
        "rising_research_share",
        "early_rising_research_watchlist",
    }
    signals = []
    for code in sorted(common):
        counted = [
            old["topic_groups"][code]["count"],
            mid["topic_groups"][code]["count"],
            recent["topic_groups"][code]["count"],
        ]
        measured = classify_publication_momentum(counted, denominators)
        if measured["direction"] not in upward:
            continue
        signals.append({
            "topic_id": code,
            "label": recent["topic_groups"][code]["label"],
            "source_topic_reference": "https://openalex.org/" + code,
            "topic_counts": counted,
            "corpus_counts": denominators,
            "sample_selection": "top20_in_each_of_three_mature_periods",
            **measured,
        })
    signals.sort(key=lambda item: (
        -item.get("oldest_to_recent_share_change_percent", 0),
        -item["topic_counts"][-1], item["topic_id"],
    ))
    output["rising_or_accelerating_watchlist"] = signals[:WATCHLIST_LIMIT]
    output["status"] = "observed_bounded_top20_overlap"
    return output


def format_broad_topic_scan(scan: dict[str, Any]) -> list[str]:
    lines = [
        "BROADER TOPIC MOMENTUM SCAN (OpenAlex, opt-in):",
        "  Most represented 20 topics per completed window, not the "
        "full 4,516-topic universe. Missing from a top-20 page means UNKNOWN, "
        "not zero or decline.",
    ]
    if scan["status"] != "observed_bounded_top20_overlap":
        lines.append(
            "  Grouped source evidence unavailable/incomplete; "
            "no broad topic direction inferred."
        )
        return lines
    lines.append(
        f"  Shared comparable groups: "
        f"{scan['compared_topic_ids_present_in_all_three_pages']}; "
        f"excluded due to truncated top-20 coverage: "
        f"{scan['not_comparable_groups_due_to_top20_truncation']}."
    )
    signals = scan["rising_or_accelerating_watchlist"]
    if not signals:
        lines.append(
            "  No consistently rising groups were detected among the "
            "fully comparable top-20 intersection; niche topics are unmeasured."
        )
    for i, row in enumerate(signals, 1):
        change = row["oldest_to_recent_share_change_percent"]
        lines.append(
            f"  {i}. {row['label']} [{row['topic_id']}] "
            f"— {row['direction'].replace('_', ' ')} | "
            f"source-normalized research share {change:+.1f}%"
        )
        lines.append(
            "     Research works across the three completed periods: "
            + " → ".join(map(str, row["topic_counts"]))
        )
        lines.append(
            "     Works per million comparable publications: "
            + " → ".join(str(x) for x in row["share_per_million"])
        )
        lines.append("     " + row["source_topic_reference"])
    lines.append(
        "  These are measured research-topic signals only. "
        "Product demand, niche coverage, customer adoption and search volume "
        "are NOT verified."
    )
    return lines
