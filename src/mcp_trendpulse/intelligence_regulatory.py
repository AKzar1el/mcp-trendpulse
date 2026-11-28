"""Optional U.S. regulatory context alongside the existing seedless discovery.

This is an independent, source-attributed enrichment. It NEVER changes the
baseline's cross-source candidate counts or implies laws or buying demand.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from mcp_trendpulse.intelligence_core import (
    BudgetCache, DailyBudgetExceeded, IntelligenceError, collect, plan_source,
)
from mcp_trendpulse.intelligence_federal_register import validate_topic

MAX_DOCUMENTS = 10


def choose_topic(baseline: dict[str, Any], explicit: str = "") -> tuple[str, str]:
    """Use a user-specified topic or one actual existing source-derived label."""
    if not isinstance(explicit, str):
        raise ValueError("regulatory_term must be a string")
    if explicit:
        return validate_topic(explicit), "explicit_user_topic"
    for item in baseline.get("candidates", [])[:8]:
        if not isinstance(item, dict):
            continue
        label = item.get("label")
        if not isinstance(label, str) or not (8 <= len(label) <= 80) or len(label.split()) < 2:
            continue
        try:
            return validate_topic(label), "source_derived_candidate"
        except IntelligenceError:
            continue
    for item in baseline.get("research_observations", [])[:3]:
        if not isinstance(item, dict):
            continue
        label = item.get("provider_assigned_topic")
        if not isinstance(label, str) or not (8 <= len(label) <= 80) or len(label.split()) < 2:
            continue
        try:
            return validate_topic(label), "source_assigned_research_topic"
        except IntelligenceError:
            continue
    return "", "no_supported_source_derived_topic"


def enrich_regulatory_context(
    baseline: dict[str, Any], *, regulatory_term: str = "",
    lookback_days: int = 30, limit: int = 10,
    cache: BudgetCache | None = None, env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """At most one explicitly opted-in fixed-origin, bounded public request."""
    topic, origin = choose_topic(baseline, regulatory_term)
    common = {
        "source": "federal_register",
        "topic_origin": origin,
        "legal_effect_verified": False,
        "buyer_demand_verified": False,
        "independent_population_growth_verified": False,
        "regulatory_documents_are_context_not_cross_source_candidate_votes": True,
    }
    if not topic:
        return {
            **common, "status": "no_supported_topic",
            "source_requests_budgeted": 0, "documents": [],
        }
    plan = plan_source(
        "federal_register", keyword=topic, lookback_days=lookback_days,
        limit=min(limit, MAX_DOCUMENTS), env=env,
    )
    common["topic"] = topic
    common["source_url"] = plan.url
    common["source_documentation"] = plan.docs
    try:
        outcome = collect(plan, fetch=True, cache=cache, env=env, timeout=20)
    except DailyBudgetExceeded as exc:
        return {
            **common, "status": "unavailable", "reason_code": "daily_source_budget_exhausted",
            "quota_utc_day": exc.utc_day, "quota_limit": exc.cap, "source_requests_budgeted": 1,
            "documents": [],
        }
    except (sqlite3.Error, OSError, IntelligenceError):
        return {
            **common, "status": "unavailable", "reason_code": "collection_unavailable",
            "source_requests_budgeted": 1, "documents": [],
        }
    if outcome.get("status") != "observed":
        reason = outcome.get("reason")
        if reason not in {
            "HTTPError", "URLError", "TimeoutError", "provider_cooldown",
            "invalid_source_shape", "collection_failed", "JSONDecodeError",
        }:
            reason = outcome.get("status") if outcome.get("status") in {
                "unavailable", "invalid_source_shape", "rate_limited",
            } else "unrecognized_source_status"
        return {
            **common, "status": "unavailable", "reason_code": reason,
            "http_status": outcome.get("http_status")
            if type(outcome.get("http_status")) is int else None,
            "source_requests_budgeted": 1, "documents": [],
        }
    observations = outcome.get("observations", {})
    items = observations.get("sample") if isinstance(observations, dict) else None
    if not isinstance(items, list) or any(not isinstance(x, dict) for x in items):
        return {
            **common, "status": "invalid_source_shape",
            "source_requests_budgeted": 1, "documents": [],
        }
    return {
        **common, "status": "observed",
        "source_requests_budgeted": 1,
        "cache_hit": outcome.get("cache_hit") is True,
        "sampled_documents": len(items),
        "documents": items[:MAX_DOCUMENTS],
        "sample_is_not_population": True,
    }
