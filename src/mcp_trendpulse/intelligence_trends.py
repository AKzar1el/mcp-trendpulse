"""Opt-in, source-counted research trend direction; never a market forecast.

No user-supplied topic seeds. The existing seedless OpenAlex work sample
supplies candidate *provider IDs*; three completed, equal date ranges measure
each topic's share of comparable publication types relative to the full
OpenAlex corpus. This does not infer money, buyers, or population prevalence
outside OpenAlex. Source-managed caching, budget, origin restrictions and
fixed no-key/free-key caps remain in force.
"""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlencode

from mcp_trendpulse.intelligence_core import (
    BudgetCache, IntelligenceError, Plan, collect, plan_source,
)

MAX_TOPICS = 2
PERIOD_COUNT = 3
PUBLICATION_LAG_DAYS = 14
MAX_ADDITIONAL_REQUESTS = PERIOD_COUNT * (MAX_TOPICS + 1)
TOPIC_ID = re.compile(r"(?:https://openalex\.org/)?(T[0-9]{4,10})\Z")
WORK_ID = re.compile(r"https://openalex\.org/W[0-9]{4,15}\Z")
# A stable subset: exclude data-series, specimen records and unmatched
# material that can dominate a provider-assigned topic's works_count.
PUBLICATION_TYPES = "article|review|book|book-chapter"


def completed_periods(as_of: date, days: int) -> list[dict[str, str]]:
    """Oldest-to-newest three nonoverlapping, mature publication windows."""
    if not isinstance(as_of, date) or isinstance(days, bool) or not isinstance(days, int) or not 7 <= days <= 90:
        raise ValueError("Trend periods require a real date and 7-90-day width")
    most_recent_end = as_of - timedelta(days=PUBLICATION_LAG_DAYS)
    return [
        {
            "from": (most_recent_end - timedelta(days=days * (PERIOD_COUNT - i) - 1)).isoformat(),
            "through": (most_recent_end - timedelta(days=days * (PERIOD_COUNT - i - 1))).isoformat(),
        }
        for i in range(PERIOD_COUNT)
    ]


def discovered_topic_ids(
    source_snapshot: dict[str, Any], *, as_of: date, lookback_days: int,
) -> list[dict[str, Any]]:
    """Never accept manual seed strings or infer IDs from topic display names."""
    if not isinstance(source_snapshot, dict) or source_snapshot.get("source") != "openalex" or source_snapshot.get("status") != "observed":
        return []
    observations = source_snapshot.get("observations")
    sample = observations.get("sample") if isinstance(observations, dict) else None
    if not isinstance(sample, list) or len(sample) > 20:
        return []
    start = as_of - timedelta(days=lookback_days - 1)
    grouped: dict[str, dict[str, Any]] = {}
    already_seen = set()
    for raw in sample:
        if not isinstance(raw, dict):
            continue
        work_id = raw.get("id")
        if not isinstance(work_id, str) or not WORK_ID.fullmatch(work_id) or work_id in already_seen:
            continue
        published = raw.get("publication_date")
        if not isinstance(published, str):
            continue
        try:
            day = date.fromisoformat(published[:10])
        except ValueError:
            continue
        if not start <= day <= as_of:
            continue
        topic = raw.get("primary_topic")
        if not isinstance(topic, dict):
            continue
        provider_id = topic.get("id")
        found = TOPIC_ID.fullmatch(provider_id) if isinstance(provider_id, str) else None
        label = topic.get("display_name")
        if not found or not isinstance(label, str):
            continue
        label = " ".join("".join(ch if ch.isprintable() else " " for ch in label).split())
        if not 8 <= len(label) <= 100:
            continue
        code = found.group(1)
        already_seen.add(work_id)
        row = grouped.setdefault(code, {
            "topic_id": code, "label": label, "sample_work_count": 0,
            "recent_research_examples": [],
        })
        row["sample_work_count"] += 1
        # The source-published paper titles are discovery clues, not proof
        # of customer pain. Keep at most two verified source URLs; never
        # invent product ideas or include unbounded provider metadata.
        title = raw.get("display_name")
        if isinstance(title, str):
            title = "".join(ch if ch.isprintable() else " "
                             for ch in title).strip()
            title = " ".join(title.split())[:115]
            if title and len(row["recent_research_examples"]) < 2:
                row["recent_research_examples"].append({
                    "title": title, "reference": work_id,
                })
    return sorted(
        (row for row in grouped.values() if row["sample_work_count"] >= 2),
        key=lambda row: (-row["sample_work_count"], row["topic_id"]),
    )[:MAX_TOPICS]


def _count_plan(template: Plan, period: dict[str, str], topic: str | None) -> Plan:
    if topic is not None and TOPIC_ID.fullmatch(topic) is None:
        raise ValueError("Only discovered OpenAlex topic IDs may be measured")
    date.fromisoformat(period["from"])
    date.fromisoformat(period["through"])
    terms = [
        "from_publication_date:" + period["from"],
        "to_publication_date:" + period["through"],
        "type:" + PUBLICATION_TYPES,
    ]
    if topic is not None:
        terms.append("primary_topic.id:" + topic)
    url = "https://api.openalex.org/works?" + urlencode({
        "filter": ",".join(terms), "per_page": 1, "select": "id",
    })
    # Copy the trusted origin, optional free-key authorization, and the SAME
    # daily source quota as ordinary OpenAlex collection.
    return replace(template, url=url)


def _read_count(outcome: dict[str, Any]) -> int | None:
    if not isinstance(outcome, dict) or outcome.get("status") != "observed":
        return None
    data = outcome.get("data")
    meta = data.get("meta") if isinstance(data, dict) else None
    total = meta.get("count") if isinstance(meta, dict) else None
    if isinstance(total, bool) or not isinstance(total, int) or not 0 <= total <= 10_000_000_000:
        return None
    return total


def classify_publication_momentum(
    topic_counts: list[int | None], corpus_counts: list[int | None],
) -> dict[str, Any]:
    """Directional HEURISTIC over three comparable source population counts.

    Compare topic share, rather than raw volume. A source index or classifier
    backfill may revise all historical data; never call this market growth.
    """
    if (len(topic_counts) != PERIOD_COUNT or len(corpus_counts) != PERIOD_COUNT
            or any(
                t is None or c is None or isinstance(t, bool)
                or isinstance(c, bool) or not isinstance(t, int)
                or not isinstance(c, int) or not 0 <= t <= c or c <= 0
                for t, c in zip(topic_counts, corpus_counts)
            )):
        return {
            "direction": "unavailable", "share_per_million": [],
            "period_over_period_share_ratios": [],
            "oldest_to_recent_share_change_percent": None,
            "latest_interval_share_change_percent": None,
            "research_share_measured": False,
            "market_growth_verified": False,
        }
    shares = [t / c for t, c in zip(topic_counts, corpus_counts)]
    ppm = [round(1_000_000 * s, 3) for s in shares]
    ratios = [
        round(shares[i + 1] / shares[i], 3) if shares[i] else None
        for i in range(PERIOD_COUNT - 1)
    ]
    first, middle, recent = topic_counts
    a, b = ratios
    total_change = round(100 * (shares[2] / shares[0] - 1), 1) if shares[0] else None
    latest_change = round(100 * (shares[2] / shares[1] - 1), 1) if shares[1] else None
    direction = "inconclusive"
    # Do not turn a small denominator or two stray indexed papers into a
    # sensational new trend. These bounds are transparent heuristics,
    # not calibrated confidence intervals or statistical significance tests.
    if recent >= 8 and first <= 2 and middle <= 2:
        direction = "newly_observed_research_activity"
    elif min(first, middle, recent) >= 8:
        if (a is not None and b is not None and
                a >= 1.15 and b >= 1.30 and b >= a * 1.10):
            direction = "accelerating_research_share"
        elif (b is not None and a is not None and
              b >= 1.30 and a * b >= 1.45):
            direction = "rising_research_share"
        elif (b is not None and a is not None and
              b <= 0.75 and a * b <= 0.65):
            direction = "declining_research_share"
        elif (a is not None and b is not None and
              a >= 1.03 and b >= 1.08 and a * b >= 1.20):
            # A moderate *monotonic* increase is worth investigating.
            # Explicitly a watchlist cue, weaker than our rising label:
            # it is not a statistically calibrated test or a market trend.
            direction = "early_rising_research_watchlist"
        elif (a is not None and b is not None and
              a <= 0.97 and b <= 0.92 and a * b <= 0.80):
            direction = "early_declining_research_watchlist"
        elif (a is not None and b is not None and
              0.85 <= a <= 1.15 and 0.85 <= b <= 1.15):
            direction = "approximately_stable_research_share"
    elif max(first, middle, recent) < 8:
        direction = "insufficient_volume"
    return {
        "direction": direction,
        "share_per_million": ppm,
        "period_over_period_share_ratios": ratios,
        "oldest_to_recent_share_change_percent": total_change,
        "latest_interval_share_change_percent": latest_change,
        "research_share_measured": True,
        "market_growth_verified": False,
    }


def measure_discovered_research_trends(
    source_snapshot: dict[str, Any], *,
    as_of: date, lookback_days: int, cache: BudgetCache | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Explicitly fetch at most nine count-only OpenAlex pages (no sync API)."""
    topics = discovered_topic_ids(
        source_snapshot, as_of=as_of, lookback_days=lookback_days,
    )
    periods = completed_periods(as_of, lookback_days)
    out: dict[str, Any] = {
        "mode": "source_measured_openalex_research_direction",
        "status": "no_repeated_provider_topic_ids" if not topics else "partial",
        "period_days": lookback_days,
        "publication_lag_days": PUBLICATION_LAG_DAYS,
        "periods": periods,
        "auto_selected_topic_count": len(topics),
        "max_topics": MAX_TOPICS,
        "additional_source_requests": 0,
        "max_additional_source_requests": MAX_ADDITIONAL_REQUESTS,
        "source_class": "openalex_publication_activity",
        "measurement_is_share_of_comparable_openalex_publications": True,
        "source_model_or_index_changes_can_revise_history": True,
        "buyer_spending_or_market_growth_verified": False,
        "other_source_topic_direction_unmeasured": ["cfpb", "ted"],
        "topic_selection_is_small_nonrepresentative_latest_work_sample": True,
        "idea_watchlist_is_investigation_not_validated_product": True,
        "idea_watchlist": [],
        "topics": [],
    }
    if not topics:
        return out
    template = plan_source(
        "openalex", discover=True, lookback_days=lookback_days, limit=1,
        env=env,
    )

    def fetch_total(period: dict[str, str], topic: str | None) -> int | None:
        plan = _count_plan(template, period, topic)
        out["additional_source_requests"] += 1
        try:
            response = collect(plan, fetch=True, cache=cache, env=env, timeout=20)
        except (OSError, ValueError, IntelligenceError):
            return None
        return _read_count(response)

    corpus = [fetch_total(p, None) for p in periods]
    if any(x is None or x <= 0 for x in corpus):
        out["status"] = "unavailable_corpus_denominator"
        out["topics"] = [{
            "topic_id": t["topic_id"], "label": t["label"],
            "sample_work_count": t["sample_work_count"],
            "recent_research_examples": t["recent_research_examples"],
            "direction": "unavailable", "topic_counts": [None] * PERIOD_COUNT,
            "corpus_counts": corpus,
            "market_growth_verified": False,
        } for t in topics]
        return out
    for t in topics:
        counts = [fetch_total(p, t["topic_id"]) for p in periods]
        evidence = classify_publication_momentum(counts, corpus)
        out["topics"].append({
            "topic_id": t["topic_id"],
            "label": t["label"],
            "sample_work_count": t["sample_work_count"],
            "recent_research_examples": t["recent_research_examples"],
            "topic_counts": counts,
            "corpus_counts": corpus,
            **evidence,
        })
    # Only measured upward-share signals enter the product-idea
    # investigation watchlist. A declining or stable topic remains
    # valuable context, but not a fabricated new market opening.
    for topic in out["topics"]:
        if topic["direction"] in {
            "newly_observed_research_activity",
            "accelerating_research_share",
            "rising_research_share",
            "early_rising_research_watchlist",
        }:
            out["idea_watchlist"].append({
                "topic_id": topic["topic_id"],
                "label": topic["label"],
                "research_direction": topic["direction"],
                "oldest_to_recent_share_change_percent": topic.get(
                    "oldest_to_recent_share_change_percent"
                ),
                "recent_research_examples": topic["recent_research_examples"],
                "why_investigate": "Published research share is rising; "
                    "inspect the cited practical techniques and whether "
                    "real users have unsolved recurring workflows.",
                "product_opportunity_verified": False,
                "keyword_search_demand_verified": False,
            })
    out["status"] = (
        "observed" if all(t["research_share_measured"]
                          for t in out["topics"]) else "partial"
    )
    return out


def format_research_trends(evidence: dict[str, Any]) -> list[str]:
    lines = [
        "MEASURED RESEARCH TREND DIRECTIONS (OpenAlex, optional):",
        "  Three equal completed publication periods; latest 14 days excluded "
        "to reduce partial indexing bias. Source counts, NOT a latest-20 sample.",
        "  DISCOVERY LIMIT: only up to two repeated topics selected from the "
        "newest 20 OpenAlex work records, NOT a cross-industry trend survey.",
    ]
    if evidence["status"] == "no_repeated_provider_topic_ids":
        lines.append("  No repeated, usable topic IDs in the bounded recent work sample.")
    elif not evidence["topics"]:
        lines.append("  Source-count evidence unavailable; no trend direction inferred.")
    priority = {
        "newly_observed_research_activity": 0,
        "accelerating_research_share": 1,
        "rising_research_share": 2,
        "early_rising_research_watchlist": 3,
        "approximately_stable_research_share": 4,
        "inconclusive": 5,
        "insufficient_volume": 6,
        "early_declining_research_watchlist": 7,
        "declining_research_share": 8,
        "unavailable": 9,
    }
    for topic in sorted(evidence["topics"], key=lambda t: (
        priority.get(t["direction"], 10), t["topic_id"],
    )):
        label = topic["label"]
        lines.append(
            "  " + label + " [" + topic["topic_id"] + "] — "
            + topic["direction"].replace("_", " ")
        )
        if topic.get("share_per_million"):
            lines.append(
                "    Old → middle → recent topic works: " +
                " → ".join(map(str, topic["topic_counts"]))
            )
            lines.append(
                "    Topic works per million comparable publications: " +
                " → ".join(str(x) for x in topic["share_per_million"])
            )
            total = topic.get("oldest_to_recent_share_change_percent")
            recent = topic.get("latest_interval_share_change_percent")
            if total is not None:
                lines.append(
                    f"    Research-share change, oldest → recent: {total:+.1f}%"
                    + (f" | middle → recent: {recent:+.1f}%" if recent is not None else "")
                )
        else:
            lines.append(
                "    Count comparison unavailable (missing source totals); "
                "no inferred decrease or zero demand."
            )
    if evidence.get("broad_topic_scan") is not None:
        from mcp_trendpulse.intelligence_broad_scan import format_broad_topic_scan

        lines.extend(format_broad_topic_scan(evidence["broad_topic_scan"]))
    watchlist = evidence.get("idea_watchlist", [])
    if watchlist:
        lines.append("  PRODUCT-IDEA RESEARCH WATCHLIST (hypotheses, not buyers):")
        for row in watchlist:
            lines.append(
                "    " + row["label"] + " — inspect practical workflows "
                "and unsolved user problems; product demand NOT verified."
            )
            for paper in row["recent_research_examples"][:2]:
                lines.append("      Research clue: " + paper["title"])
                lines.append("        " + paper["reference"])
            if row.get("source_topic_reference"):
                lines.append("      Provider topic: " +
                             row["source_topic_reference"])
    else:
        lines.append(
            "  PRODUCT-IDEA RESEARCH WATCHLIST: no measurable upward "
            "research-share signal from the sampled topics."
        )
    lines.append(
        "  Source topic assignments changed in October 2026 and the index "
        "can be revised. Early-rising/declining labels are explicit "
        "heuristic watchlist signals, NOT calibrated statistical forecasts."
    )
    lines.append(
        "  Academic topic momentum is NOT verified product adoption, "
        "market demand, Google search volume, buyer intent or revenue."
    )
    lines.append(
        "  CFPB complaint and TED procurement topic directions remain unmeasured "
        "until comparable population counts are available."
    )
    return lines
