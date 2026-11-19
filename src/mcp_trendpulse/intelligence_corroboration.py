"""Optional free GitHub issue-text corroboration for measured research trends.

This is lexical discussion evidence, NOT validated user pain, independent
customers, commercial adoption, market growth or search-volume evidence.
Public searches only; two adjacent completed windows; privacy-safe counts.
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
from mcp_trendpulse.intelligence_trends import completed_periods

MAX_TOPICS = 2
COUNT_WINDOWS = 2
MAX_SOURCE_REQUESTS = MAX_TOPICS * COUNT_WINDOWS
MAX_SOURCE_COUNT = 100_000_000


def source_phrase(provider_label: Any) -> str:
    """Safe strictly lexical phrase from a published provider topic label.

    Parenthetical abbreviations are not necessarily used in issue bodies;
    don't silently invent synonyms or inject provider punctuation as search
    operators. Ambiguous, very short or non-ASCII names are unsearchable.
    """
    if not isinstance(provider_label, str):
        return ""
    if (any(ord(ch) < 32 for ch in provider_label)
            or '"' in provider_label
            or any(token in provider_label.lower()
                   for token in ("is:", "created:", "repo:", "in:"))):
        return ""
    primary = provider_label.split("(", 1)[0]
    tokens = re.findall(r"[A-Za-z0-9]+", primary)
    phrase = " ".join(tokens)
    if (len(tokens) < 2 or not 12 <= len(phrase) <= 80
            or len(tokens) > 8):
        return ""
    return phrase


def issue_count_plan(template: Plan, phrase: str, period: dict[str, str]) -> Plan:
    """Fixed GitHub search endpoint using the existing source-local budget."""
    if source_phrase(phrase) != phrase:
        raise ValueError("Only source-derived, bounded plain phrases are allowed")
    from_day = date.fromisoformat(period["from"])
    through_day = date.fromisoformat(period["through"])
    if from_day > through_day:
        raise ValueError("Invalid GitHub issue count period")
    query = (
        f'"{phrase}" in:title,body is:issue is:public '
        f'created:{from_day.isoformat()}..{through_day.isoformat()}'
    )
    url = "https://api.github.com/search/issues?" + urlencode({
        "q": query, "per_page": 1,
        "sort": "created", "order": "desc",
    })
    return replace(template, url=url)


def _source_count(outcome: dict[str, Any]) -> int | None:
    if not isinstance(outcome, dict) or outcome.get("status") != "observed":
        return None
    data = outcome.get("data")
    if not isinstance(data, dict) or data.get("incomplete_results") is not False:
        return None
    value = data.get("total_count")
    if (isinstance(value, bool) or not isinstance(value, int)
            or not 0 <= value <= MAX_SOURCE_COUNT):
        return None
    return value


def corroborate_research_issue_mentions(
    watchlist: list[dict[str, Any]], *, as_of: date,
    lookback_days: int, cache: BudgetCache | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Two source-count periods for at most two auto-discovered trend topics."""
    periods = completed_periods(as_of, lookback_days)[-2:]
    output: dict[str, Any] = {
        "status": "no_eligible_research_topics",
        "source": "github_issues",
        "mode": "lexical_public_issue_count_not_verified_product_demand",
        "periods": periods,
        "max_auto_topics": MAX_TOPICS,
        "source_requests": 0,
        "max_source_requests": MAX_SOURCE_REQUESTS,
        "not_customer_pain_verified": True,
        "not_independent_users_or_buyers_verified": True,
        "not_market_or_search_growth_verified": True,
        "not_normalized_by_all_github_issues": True,
        "incomplete_results_must_not_be_zero": True,
        "public_issue_bodies_and_authors_not_cached": True,
        "topics": [],
    }
    if not isinstance(watchlist, list):
        raise ValueError("Research watchlist must be a list")
    selected: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for item in watchlist[:20]:
        if not isinstance(item, dict):
            continue
        code = item.get("topic_id")
        phrase = source_phrase(item.get("label"))
        if not isinstance(code, str) or re.fullmatch(r"T\d{4,10}", code) is None:
            continue
        if not phrase or code in seen:
            continue
        seen.add(code)
        selected.append((code, item["label"], phrase))
        if len(selected) == MAX_TOPICS:
            break
    if not selected:
        return output
    template = plan_source(
        "github_issues", keyword="research", limit=1, env=env,
    )
    for code, label, phrase in selected:
        source_counts: list[int | None] = []
        links: list[str] = []
        for period in periods:
            plan = issue_count_plan(template, phrase, period)
            links.append("https://github.com/search?" + urlencode({
                "q": (
                    f'"{phrase}" in:title,body is:issue is:public '
                    f'created:{period["from"]}..{period["through"]}'
                ),
                "type": "issues",
            }))
            output["source_requests"] += 1
            try:
                result = collect(
                    plan, fetch=True, cache=cache, env=env, timeout=20,
                )
            except (OSError, ValueError, IntelligenceError):
                result = {"source": "github_issues", "status": "unavailable"}
            source_counts.append(_source_count(result))
        output["topics"].append({
            "topic_id": code,
            "label": label,
            "exact_source_phrase": phrase,
            "source_created_issue_counts": source_counts,
            "source_search_urls": links,
            "status": (
                "observed_complete_lexical_counts"
                if all(n is not None for n in source_counts)
                else "unavailable_or_incomplete_lexical_counts"
            ),
            "observed_text_matches_are_not_validated_user_needs": True,
            "market_and_product_adoption_verified": False,
        })
    output["status"] = (
        "observed_complete_lexical_counts"
        if all(item["status"] == "observed_complete_lexical_counts"
               for item in output["topics"])
        else "partial_or_unavailable_source"
    )
    return output


def format_issue_corroboration(result: dict[str, Any]) -> list[str]:
    lines = [
        "INDEPENDENT DEVELOPER DISCUSSION CHECK (GitHub issues, opt-in):",
        "  Exact public phrase matches in issue titles/bodies, open + closed, "
        "across two equal completed date windows. NOT verified unmet needs.",
    ]
    if not result["topics"]:
        lines.append(
            "  No eligible bounded provider topic labels; no search "
            "was performed or zero interest inferred."
        )
    for item in result["topics"]:
        lines.append(
            f"  {item['label']} [{item['topic_id']}] — "
            f"exact phrase: {item['exact_source_phrase']}"
        )
        if item["status"] == "observed_complete_lexical_counts":
            lines.append(
                "    Matching issues (older → newer): "
                + " → ".join(map(str, item["source_created_issue_counts"]))
            )
        else:
            lines.append(
                "    GitHub search count unavailable/incomplete: "
                "cannot infer zero discussion, a decline or adoption."
            )
        for period, link in zip(result["periods"], item["source_search_urls"]):
            lines.append(
                f"    Inspect {period['from']}–{period['through']}: {link}"
            )
    lines.append(
        "  GitHub text search is not a count of distinct users, "
        "confirmed pain points or paying customers; repositories and "
        "terminology are biased, and raw issue contents are not cached."
    )
    lines.append(
        "  Research momentum, GitHub issue mentions and SEO search demand "
        "are different measures; none establishes market growth."
    )
    return lines
