"""Opt-in, bounded related-query checks for already source-derived idea keywords.

Reuses TrendPulse's existing *unofficial* Google Trends community provider.
This is not Google's limited-access official Trends API, not Keyword Planner
and not an exact search-volume or startup-demand measurement.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from datetime import date
from typing import Any

from mcp_trendpulse.intelligence_core import BudgetCache, IntelligenceError

PROVIDER_BUDGET_ID = "google_trends_idea_related_queries"
MAX_PROVIDER_OPERATIONS = 2
UTC_DAILY_PROVIDER_CAP = 2
MAX_ROWS_PER_SERIES = 3
CACHE_TTL_SECONDS = 6 * 3600
KEYWORD = re.compile(r"[\w][\w \-']{3,69}\Z", re.UNICODE)
ISO_COUNTRY = re.compile(r"[A-Z]{2}\Z")
SAFE_REASON = {
    "ProviderRateLimitError", "ProviderTimeoutError", "ProviderUnavailableError",
    "TrendsCooldownError", "IntelligenceError", "TimeoutError", "OSError",
    "ValueError",
}


def select_related_query_seeds(idea_map: dict[str, Any]) -> list[dict[str, str]]:
    """Use one source-published procurement phrase and one consumer issue first."""
    if (not isinstance(idea_map, dict)
            or idea_map.get("mode") != "source_grounded_project_idea_and_keyword_research_queue"
            or not isinstance(idea_map.get("ideas"), list)
            or len(idea_map["ideas"]) > 6):
        raise ValueError("Requires completed bounded source-backed Idea Map")
    pool = []
    used = set()
    for idea in idea_map["ideas"]:
        if not isinstance(idea, dict):
            continue
        market = idea.get("geography", {}).get("country_code") if isinstance(idea.get("geography"), dict) else None
        if not isinstance(market, str) or ISO_COUNTRY.fullmatch(market) is None:
            continue
        term = ""
        candidates = idea.get("keyword_hypotheses", [])
        if not isinstance(candidates, list):
            continue
        # Query shorter original source terms in the published language;
        # a complete paragraph or artificial concatenated category is not a
        # trustworthy provider seed.
        for row in candidates[:4]:
            if not isinstance(row, dict):
                continue
            value = row.get("keyword")
            basis = row.get("basis")
            if not isinstance(value, str) or not isinstance(basis, str):
                continue
            if (basis == "combined_published_categories_not_an_observed_query"
                    or KEYWORD.fullmatch(value) is None
                    or len(value) > 60):
                continue
            term = value
            break
        if not term or (market, term.casefold()) in used:
            continue
        used.add((market, term.casefold()))
        ident = idea.get("id")
        if not isinstance(ident, str) or re.fullmatch(r"[a-f0-9]{14}", ident) is None:
            continue
        pool.append({
            "idea_id": ident, "keyword": term,
            "market": market,
            "kind": idea.get("kind", ""),
            "observed_as_search_query_at_selection": False,
        })
    procurement = [r for r in pool if r["kind"] == "procurement_derived_software_hypothesis"]
    consumer = [r for r in pool if r["kind"] == "consumer_problem_derived_software_hypothesis"]
    chosen = []
    if procurement:
        chosen.append(procurement.pop(0))
    if consumer:
        chosen.append(consumer.pop(0))
    for item in procurement + consumer:
        if len(chosen) == MAX_PROVIDER_OPERATIONS:
            break
        chosen.append(item)
    return chosen


def _query_rows(payload: Any, *, key: str) -> list[dict[str, Any]] | None:
    if payload is None:
        return []
    if not isinstance(payload, list):
        return None
    rows = []
    seen = set()
    for value in payload[:30]:
        if not isinstance(value, dict):
            return None
        phrase = value.get("query")
        if (not isinstance(phrase, str)
                or len(phrase) > 70
                or KEYWORD.fullmatch(phrase.strip()) is None):
            continue
        phrase = " ".join(phrase.split())[:70]
        if phrase.casefold() in seen:
            continue
        seen.add(phrase.casefold())
        number = value.get("value")
        breakout = value.get("is_breakout") is True
        if breakout and key == "rising":
            score = None
        elif isinstance(number, (int, float)) and not isinstance(number, bool):
            if not math.isfinite(number) or not (
                0 <= number <= (100 if key == "top" else 10_000_000)
            ):
                continue
            score = round(float(number), 2)
        else:
            continue
        rows.append({
            "query": phrase, "provider_value": score,
            "provider_series": key,
            "is_breakout": breakout if key == "rising" else False,
            "provider_value_semantics": (
                "within_query_relative_score_not_volume"
                if key == "top" else
                "provider_rising_percentage_or_breakout_not_absolute_search_volume"
            ),
            "keyword_demand_verified": False,
            "keyword_competition_verified": False,
        })
        if len(rows) == MAX_ROWS_PER_SERIES:
            break
    return rows


def _status(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"status": "invalid_provider_shape", "top": [], "rising": []}
    top = _query_rows(value.get("top"), key="top")
    rising = _query_rows(value.get("rising"), key="rising")
    if top is None or rising is None:
        return {"status": "invalid_provider_shape", "top": [], "rising": []}
    return {
        "status": "observed_related_queries" if top or rising
                  else "observed_empty_related_queries",
        "top": top, "rising": rising,
    }


async def probe_idea_keywords_async(
    idea_map: dict[str, Any], *,
    provider: Any = None, cache: BudgetCache | None = None,
) -> dict[str, Any]:
    """Two provider operations maximum, plus a durable two/day local quota."""
    selected = select_related_query_seeds(idea_map)
    summary: dict[str, Any] = {
        "mode": "optional_existing_unofficial_google_trends_related_queries",
        "status": "no_safe_source_keywords",
        "provider": "community_google_trends_trendspy",
        "provider_is_not_official_google_trends_api": True,
        "max_provider_operations_per_invocation": MAX_PROVIDER_OPERATIONS,
        "local_utc_daily_provider_operations_cap": UTC_DAILY_PROVIDER_CAP,
        "provider_operations_budgeted": len(selected),
        "provider_operations_attempted": 0,
        "physical_http_requests_not_measured": True,
        "source_keys_used_as_search_queries_not_verified_before_probe": True,
        "provider_search_volumes_not_available": True,
        "new_paid_services_used": False,
        "results": [],
    }
    if not selected:
        return summary
    store = cache if cache is not None else BudgetCache()
    if provider is None:
        from mcp_trendpulse.providers import get_provider_set

        provider = get_provider_set().trends
    observed = 0
    for choice in selected:
        keyword, market = choice["keyword"], choice["market"]
        key = hashlib.sha256(json.dumps(
            ["source_idea_related_v1", market, keyword.casefold(),
             "today 12-m"], separators=(",", ":"),
        ).encode()).hexdigest()
        output = {
            "idea_id": choice["idea_id"], "keyword": keyword,
            "market": market, "source": "community_google_trends_trendspy",
            "timeframe": "today 12-m", "status": "unavailable",
            "top": [], "rising": [], "cache_hit": False,
            "source_keyword_was_not_observed_google_query": True,
        }
        try:
            cached = store.cached(key)
        except (OSError, ValueError):
            cached = None
        if isinstance(cached, dict) and cached.get("status") in {
            "observed_related_queries", "observed_empty_related_queries"
        }:
            # Re-validate all cached candidates; never pass provider blobs
            # or user-modified SQLite JSON straight through to the report.
            tested = _status(cached)
            output.update(tested)
            output["cache_hit"] = True
            observed += 1
            summary["results"].append(output)
            continue
        try:
            store.reserve(PROVIDER_BUDGET_ID, UTC_DAILY_PROVIDER_CAP)
        except (OSError, ValueError, IntelligenceError):
            output["status"] = "local_daily_budget_exhausted_or_unavailable"
            summary["results"].append(output)
            continue
        summary["provider_operations_attempted"] += 1
        try:
            result = await provider.get_related_queries(
                keyword=keyword, geo=market, timeframe="today 12-m",
                cat=0, gprop="",
            )
            tested = _status(result)
            output.update(tested)
        except Exception as exc:
            # Never surface provider exception strings or request metadata.
            name = type(exc).__name__
            output["reason_code"] = name if name in SAFE_REASON else "provider_failed"
            output["status"] = "provider_rate_limited" if "RateLimit" in name or "Cooldown" in name else "unavailable"
        if output["status"] in {
            "observed_related_queries", "observed_empty_related_queries"
        }:
            observed += 1
            try:
                store.save(key, {"status": output["status"], "top": output["top"],
                                 "rising": output["rising"]}, CACHE_TTL_SECONDS)
            except (OSError, ValueError):
                pass  # Shared cache is best effort, not evidence.
        summary["results"].append(output)
    summary["status"] = (
        "observed_related_query_sources" if observed == len(selected)
        else "partial_or_unavailable_related_query_sources"
    )
    return summary


def probe_idea_keywords(idea_map: dict[str, Any], *, cache: BudgetCache | None = None) -> dict[str, Any]:
    """Synchronous CLI adapter. Never nest an event loop in an MCP handler."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(probe_idea_keywords_async(idea_map, cache=cache))
    raise ValueError("Keyword probe is synchronous CLI-only inside an existing event loop")


def format_keyword_probe(report: dict[str, Any]) -> list[str]:
    if report.get("mode") != "optional_existing_unofficial_google_trends_related_queries":
        raise ValueError("Expected source-keyword provider probe")
    lines = [
        "GOOGLE TRENDS RELATED SEARCHES (explicit opt-in; existing unofficial paced provider):",
        "  Up to 2 locally quota-guarded provider operations/day. A provider operation may involve multiple HTTP calls.",
        "  Top values = relative ranking; rising values = provider-reported %/Breakout. Neither is absolute keyword volume or proof of buyers.",
    ]
    if not report["results"]:
        lines.append("  No safe original-source market-specific keywords selected. No automatic substitute.")
    for item in report["results"]:
        lines.append(
            f"  {item['keyword']} [{item['market']}]: {item['status']}"
            + (" (cached)" if item.get("cache_hit") else "")
        )
        if item.get("reason_code"):
            lines.append(f"    Reason class: {item['reason_code']}")
        for kind in ("top", "rising"):
            for query in item[kind]:
                val = ("Breakout" if query["is_breakout"] else query["provider_value"])
                lines.append(
                    f"    {kind} related search: {query['query']}"
                    f" | provider value: {val} (NOT search volume)"
                )
    lines.append(
        "  Unavailable/rate-limited providers imply missing coverage, not zero searches."
        " Recheck market, language, user problem, incumbent alternatives, and actual purchasing evidence."
    )
    return lines
