"""Choose source-measured topics for *investigation*, not trend promotion.

A research-share classification can be inconclusive even where two completed
intervals rise modestly. Opted-in independent providers may investigate this
narrow signal, but it is not eligible for the product-idea growth watchlist.
"""

from __future__ import annotations

import re
from typing import Any

from mcp_trendpulse.intelligence_corroboration import source_phrase

MAX_FOLLOWUP_TOPICS = 2
DISALLOWED_DIRECTIONS = frozenset({
    "unavailable", "insufficient_volume",
    "volatile_rebound_needs_validation",
    "abrupt_publication_spike_needs_validation",
    "declining_research_share",
    "early_declining_research_watchlist",
})
FOLLOWUP_DIRECTIONS = frozenset({
    "inconclusive", "approximately_stable_research_share",
})


def select_source_followups(trend_evidence: dict[str, Any]) -> dict[str, Any]:
    """Prefer rising watchlist items; rescue measured nonvolatile context.

    The fallback uses *source-counted* topic/corpus population ratios, never
    a recent-paper sample or absent top-N ranking as a zero. Two consecutive
    nondeclining normalized intervals, >=10% total increase, >=8% latest
    interval increase, >=8 works in each period and no source-quality flag qualify
    only for research follow-up, NOT for an upward-trend label.
    """
    if not isinstance(trend_evidence, dict):
        raise ValueError("Expected measured research evidence mapping")
    selected: list[dict[str, Any]] = []
    used: set[str] = set()

    def add(row: dict[str, Any], basis: str) -> None:
        code = row.get("topic_id")
        label = row.get("label")
        direction = row.get("research_direction", row.get("direction", ""))
        if (not isinstance(code, str)
                or re.fullmatch(r"T\d{4,10}", code) is None
                or code in used or direction in DISALLOWED_DIRECTIONS
                or not isinstance(label, str) or not source_phrase(label)
                or len(selected) >= MAX_FOLLOWUP_TOPICS):
            return
        used.add(code)
        selected.append({
            "topic_id": code,
            "label": label,
            "research_direction": direction,
            "selection_basis": basis,
            "included_in_product_idea_watchlist": (
                basis == "existing_rising_research_watchlist"
            ),
            "research_share_measured_not_market_demand": True,
            "commercial_demand_verified": False,
        })

    watchlist = trend_evidence.get("idea_watchlist", [])
    topics = trend_evidence.get("topics", [])
    if not isinstance(watchlist, list) or not isinstance(topics, list):
        raise ValueError("Measured topic lists must be arrays")
    for row in watchlist:
        if isinstance(row, dict):
            add(row, "existing_rising_research_watchlist")
        if len(selected) == MAX_FOLLOWUP_TOPICS:
            break

    eligible = []
    for row in topics:
        if (not isinstance(row, dict)
                or row.get("research_share_measured") is not True
                or row.get("trajectory_integrity_flag")
                or row.get("direction") not in FOLLOWUP_DIRECTIONS
                or row.get("topic_id") in used):
            continue
        topic_counts = row.get("topic_counts")
        corpus_counts = row.get("corpus_counts")
        if (not isinstance(topic_counts, list)
                or not isinstance(corpus_counts, list)
                or len(topic_counts) != 3 or len(corpus_counts) != 3
                or any(isinstance(n, bool) or not isinstance(n, int)
                       for n in topic_counts + corpus_counts)
                or any(t < 0 or c <= 0 or t > c
                       for t, c in zip(topic_counts, corpus_counts))
                or min(topic_counts) < 8):
            continue
        shares = [t / c for t, c in zip(topic_counts, corpus_counts)]
        if (shares[0] <= 0 or shares[1] <= 0
                or shares[1] < shares[0]
                or shares[2] < shares[1]
                or shares[2] < shares[0] * 1.10
                or shares[2] < shares[1] * 1.08):
            continue
        eligible.append((
            -(shares[2] / shares[1]),
            -(shares[2] / shares[0]),
            str(row.get("topic_id", "")),
            row,
        ))
    for _, _, _, row in sorted(eligible):
        add(row, "exploratory_monotonic_below_trend_threshold")
        if len(selected) == MAX_FOLLOWUP_TOPICS:
            break
    return {
        "status": "source_measured_topics_selected" if selected
                  else "no_eligible_measured_followup_topics",
        "max_auto_topics": MAX_FOLLOWUP_TOPICS,
        "no_new_queries_for_topic_selection": True,
        "product_idea_watchlist_unchanged": True,
        "no_predefined_topic_seeds": True,
        "followup_is_not_verified_growth": True,
        "topics": selected,
    }


def format_source_followups(data: dict[str, Any]) -> list[str]:
    lines = [
        "SOURCE FOLLOW-UP SELECTION (not a product-demand ranking):",
        "  Up to two source-measured research topics; first prefer the "
        "existing rising watchlist, then only nonvolatile upward-but-"
        "inconclusive trajectories. No static topic seeds.",
    ]
    if not data["topics"]:
        lines.append(
            "  No eligible measured topics for independent review; "
            "unavailable or volatile data are not treated as zero demand."
        )
    for row in data["topics"]:
        interpretation = (
            "ranked research watchlist"
            if row["included_in_product_idea_watchlist"]
            else "exploratory only — research direction still inconclusive"
        )
        lines.append(
            f"  {row['label']} [{row['topic_id']}] — {interpretation}"
        )
    lines.append(
        "  Follow-up source observations do not upgrade the research "
        "direction, verify buyer interest or establish SEO search demand."
    )
    return lines
