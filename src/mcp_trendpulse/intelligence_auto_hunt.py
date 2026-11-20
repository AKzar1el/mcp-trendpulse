"""Opt-in source-derived cross-provider context using the existing hunter.

Never invent predefined sector seeds, interpret relevance-ranked samples
as population growth, or auto-promote projects/awards into product demand.
Only existing free CORDIS and USAspending adapters are reused here.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from mcp_trendpulse.intelligence_corroboration import source_phrase
from mcp_trendpulse.intelligence_core import BudgetCache
from mcp_trendpulse.intelligence_hunter import hunt_current

SOURCE_IDS = ("cordis", "usaspending")
MAX_AUTO_TOPICS = 2
MAX_NEW_SOURCE_REQUESTS = len(SOURCE_IDS) * MAX_AUTO_TOPICS


def investigate_discovered_topics(
    research_watchlist: list[dict[str, Any]], *, as_of: date,
    lookback_days: int, cache: BudgetCache | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Reuse the hunter on at most two safe labels generated from research.

    The CORDIS project query finds title substrings (often historical and
    without a comparable publication date). USAspending finds U.S. award
    descriptions, not the number of commercial customers for the topic.
    """
    if not isinstance(research_watchlist, list):
        raise ValueError("Expected research-topic watchlist array")
    if not isinstance(as_of, date) or not isinstance(lookback_days, int):
        raise ValueError("Invalid source observation period")
    outcome: dict[str, Any] = {
        "status": "no_research_topic_to_investigate",
        "mode": "existing_hunter_cross_source_context_not_market_growth",
        "source_ids": list(SOURCE_IDS),
        "source_request_budget": 0,
        "max_source_request_budget": MAX_NEW_SOURCE_REQUESTS,
        "auto_topic_limit": MAX_AUTO_TOPICS,
        "no_predefined_keyword_seeds": True,
        "source_records_not_comparable_population_counts": True,
        "independent_buyer_demand_verified": False,
        "product_or_market_growth_verified": False,
        "seo_keyword_growth_verified": False,
        "topics": [],
    }
    selected: list[tuple[str, str, str]] = []
    used: set[str] = set()
    for row in research_watchlist[:20]:
        if not isinstance(row, dict):
            continue
        code = row.get("topic_id")
        phrase = source_phrase(row.get("label"))
        if (not isinstance(code, str)
                or re.fullmatch(r"T[0-9]{4,10}", code) is None
                or not phrase or phrase.lower() in used):
            continue
        selected.append((code, str(row["label"])[:100], phrase))
        used.add(phrase.lower())
        if len(selected) >= MAX_AUTO_TOPICS:
            break
    if not selected:
        return outcome
    # The called hunter uses the same read-only fixed URL planners,
    # filesystem cache, source budgets, 429 cooldowns and strict limits.
    # Explicit topics bypass the hunter's rotating DEFAULT/SEED_TOPICS.
    result = hunt_current(
        topics=[s[2] for s in selected],
        sources=list(SOURCE_IDS),
        as_of=as_of.isoformat(), lookback_days=lookback_days,
        execute=True, cache=cache, env=env,
    )
    outcome["source_request_budget"] = len(selected) * len(SOURCE_IDS)
    observed = 0
    # The hunter ranks topics by evidence strength and may reorder them.
    # Join on exact normalized source phrase, never list position.
    returned = {
        row["topic"]: row for row in result["topics"]
        if isinstance(row, dict) and isinstance(row.get("topic"), str)
    }
    for code, label, phrase in selected:
        checked = returned.get(phrase.lower(), {})
        coverage = []
        for provider in checked.get("source_coverage", []):
            if provider.get("source") not in SOURCE_IDS:
                continue
            status = provider.get("status", "unavailable")
            if status == "observed":
                observed += 1
            summary = {
                "source": provider["source"],
                "status": status,
                "sample_records_accepted": int(
                    provider.get("records_accepted") or 0
                ),
                "topical_title_matches_in_sample": int(
                    provider.get("topical_title_matches") or 0
                ),
                "recent_dated_matches_in_sample": int(
                    provider.get("recent_eligible_matches") or 0
                ),
                "context_only_matches_in_sample": int(
                    provider.get("context_only_matches") or 0
                ),
                "not_exhaustive": True,
            }
            # The hunter has already allowlisted these diagnostics. Keep
            # only known status metadata; never pass through provider text,
            # credentials, redirect URLs or arbitrary transport errors.
            if status != "observed":
                http_code = provider.get("http_status")
                reason = provider.get("reason")
                if (isinstance(http_code, int)
                        and not isinstance(http_code, bool)
                        and 100 <= http_code <= 599):
                    summary["http_status"] = http_code
                elif isinstance(reason, str) and reason in {
                    "HTTPError", "URLError", "TimeoutError",
                    "provider_cooldown", "not_configured",
                    "source_setup_required_or_invalid_plan",
                    "collection_failed", "invalid_source_shape",
                }:
                    summary["reason"] = reason
            coverage.append(summary)
        examples = []
        for row in checked.get("evidence", [])[:3]:
            if row.get("source") not in SOURCE_IDS:
                continue
            title = str(row.get("title") or "")
            title = " ".join(
                (ch if ch.isprintable() else " ") for ch in title
            ).strip()[:110]
            ref = row.get("reference")
            if not isinstance(ref, str) or not ref.startswith("https://"):
                continue
            examples.append({
                "source": row["source"], "title": title,
                "reference": ref, "event_date": row.get("event_date"),
            })
        # The existing hunter intentionally places historic/undated CORDIS
        # projects and USAspending last-modified dates into context_examples
        # rather than dated recent evidence. Preserve *their* citations and
        # exclusion reasons instead of silently hiding every match.
        contextual = []
        reasons = {
            "timestamp_not_comparable_recent_market_event",
            "publication_date_unavailable", "outside_requested_lookback",
            "not_recent_activity",
        }
        for row in checked.get("context_examples", [])[:4]:
            source = row.get("source")
            ref = row.get("reference")
            if source not in SOURCE_IDS or not isinstance(ref, str):
                continue
            if source == "cordis":
                exact = re.fullmatch(
                    r"https://cordis\.europa\.eu/project/id/[0-9]{4,15}",
                    ref,
                ) is not None
                portal = ref == "https://cordis.europa.eu/"
            else:
                # USAspending's Award ID is not the internally scoped
                # USASpending database ID. Do not manufacture an /award/ URL.
                exact = False
                portal = ref == "https://www.usaspending.gov/search"
            if not (exact or portal):
                continue
            title = " ".join(
                ch if ch.isprintable() else " "
                for ch in str(row.get("title") or "")
            ).strip()[:110]
            if not title:
                continue
            reason = row.get("reason")
            if reason not in reasons:
                continue
            day = row.get("event_date")
            if not isinstance(day, str) or re.fullmatch(
                r"[0-9]{4}-[0-9]{2}-[0-9]{2}", day
            ) is None:
                day = None
            contextual.append({
                "source": source, "title": title, "reference": ref,
                "reference_specificity": (
                    "exact_official_project_record" if exact
                    else "provider_search_or_home_landing_only"
                ),
                "event_date": day, "not_recent_reason": reason,
                "not_recent_market_activity": True,
            })
        outcome["topics"].append({
            "topic_id": code,
            "label": label,
            "source_derived_search_phrase": phrase,
            "research_direction": next(
                (x.get("research_direction", "unspecified")
                 for x in research_watchlist if isinstance(x, dict)
                 and x.get("topic_id") == code), "unspecified"
            ),
            "selection_basis": next(
                (x.get("selection_basis", "direct_topic_list")
                 for x in research_watchlist if isinstance(x, dict)
                 and x.get("topic_id") == code), "direct_topic_list"
            ),
            "source_coverage": coverage,
            "source_examples": examples,
            "source_context_examples": contextual,
            "source_context_exclusions_are_auditable": True,
            "hunter_screening_status": checked.get(
                "status", "unavailable"
            ),
            "source_sample_not_demand_growth": True,
        })
    outcome["status"] = (
        "observed_bounded_source_context"
        if observed == len(selected) * len(SOURCE_IDS)
        else "partially_available_source_context"
    )
    return outcome


def format_discovered_source_context(result: dict[str, Any]) -> list[str]:
    lines = [
        "ADDITIONAL EXISTING SOURCES (CORDIS + USAspending, opt-in):",
        "  Research-derived topic phrases only; bounded title-based "
        "source samples, not comprehensive source populations or trends.",
    ]
    if not result["topics"]:
        lines.append(
            "  No eligible measured research watchlist topic; no "
            "predefined sector seeds or network requests substituted."
        )
        return lines
    for topic in result["topics"]:
        lines.append(
            "  " + topic["label"] + " [" + topic["topic_id"] + "]"
            + " | source-derived phrase: "
            + topic["source_derived_search_phrase"]
        )
        if topic.get("selection_basis") != "direct_topic_list":
            lines.append(
                "    Research source classification: "
                + str(topic["research_direction"])
                + " | selection: " + str(topic["selection_basis"])
                + " | NOT a validated product trend"
            )
        for provider in topic["source_coverage"]:
            if provider["status"] == "observed":
                lines.append(
                    f"    {provider['source']}: observed "
                    f"{provider['sample_records_accepted']} source samples; "
                    f"{provider['topical_title_matches_in_sample']} "
                    f"topic-title overlap(s), "
                    f"{provider['recent_dated_matches_in_sample']} "
                    f"recent dated evidence row(s)"
                )
            else:
                detail = ""
                if "http_status" in provider:
                    detail = f" (HTTP {provider['http_status']})"
                elif provider.get("reason"):
                    detail = f" ({provider['reason']})"
                lines.append(
                    f"    {provider['source']}: {provider['status']}{detail}; "
                    "source evidence incomplete — NOT zero market interest."
                )
        for item in topic["source_examples"]:
            lines.append(
                f"    Recent source clue ({item['source']}): {item['title']}"
            )
            lines.append("      " + item["reference"])
        if topic.get("source_context_examples"):
            lines.append(
                "    CONTEXT-ONLY SOURCE RECORDS — matches do not "
                "qualify as recent market activity:"
            )
        for item in topic.get("source_context_examples", []):
            date_text = item["event_date"] or "no comparable event date"
            lines.append(
                f"      {item['source']} | {date_text} | "
                f"{item['not_recent_reason']}: {item['title']}"
            )
            if item["reference_specificity"] == "exact_official_project_record":
                lines.append(
                    "        Exact published project fact sheet: "
                    + item["reference"]
                )
            else:
                lines.append(
                    "        Provider search/home only — NOT an exact "
                    "record permalink: " + item["reference"]
                )
    lines.append(
        "  CORDIS funded project metadata and US federal awards are "
        "not independent paying customers or software adoption counts. "
        "A lexical title match does not prove the same workflow."
    )
    lines.append(
        "  These additional source adapters were already in TrendPulse; "
        "no product-growth, SEO-volume or buyer-intent claim follows."
    )
    return lines
