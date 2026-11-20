"""Bounded, source-phrase-based independent checks for optional workflow briefs.

Only already-available GitHub Issues and USAspending adapters are queried,
on explicit opt-in. Lexical source matches are neither buying evidence nor
a verified shared workflow, growth trend or product recommendation.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from mcp_trendpulse.intelligence_corroboration import source_phrase
from mcp_trendpulse.intelligence_core import BudgetCache
from mcp_trendpulse.intelligence_hunter import hunt_current
from mcp_trendpulse.intelligence_workflows import _clean, _phrases

SOURCE_IDS = ("github_issues", "usaspending")
MAX_FOLLOWUPS = 2
MAX_ADDITIONAL_REQUESTS = MAX_FOLLOWUPS * len(SOURCE_IDS)
ISSUE_URL = re.compile(
    r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/issues/[0-9]+"
)
USA_LANDING = "https://www.usaspending.gov/search"
REASONS = frozenset({
    "HTTPError", "URLError", "TimeoutError", "provider_cooldown",
    "not_configured", "source_setup_required_or_invalid_plan",
    "collection_failed", "invalid_source_shape",
})
CONTEXT_REASONS = frozenset({
    "timestamp_not_comparable_recent_market_event",
    "publication_date_unavailable", "outside_requested_lookback",
    "not_recent_activity",
})


def _phrase_from_source_label(label: str) -> str:
    """Never generate synonyms, default hypotheses, provider query operators."""
    options = [
        phrase for phrase in _phrases(label)
        if len(phrase.split()) <= 3 and source_phrase(phrase) == phrase
    ]
    if not options:
        return ""
    lowered = label.lower()
    return sorted(options, key=lambda phrase: (
        lowered.find(phrase) if phrase in lowered else 1000,
        len(phrase.split()), len(phrase), phrase,
    ))[0]


def select_workflow_followups(briefs: dict[str, Any]) -> list[dict[str, str]]:
    """Choose one source-derived reported problem and one procurement scope first."""
    if not isinstance(briefs, dict) or not isinstance(briefs.get("briefs"), list):
        raise ValueError("Expected completed source-backed workflow briefs")
    candidates = []
    seen = set()
    for row in briefs["briefs"][:6]:
        if not isinstance(row, dict):
            continue
        kind = row.get("kind")
        if kind not in {
            "published_software_it_procurement_to_investigate",
            "recurring_public_consumer_issue_to_investigate",
        }:
            continue
        label = row.get("source_published_workflow_clue")
        ident = row.get("brief_id")
        if (not isinstance(label, str)
                or not isinstance(ident, str)
                or re.fullmatch(r"[a-f0-9]{14}", ident) is None):
            continue
        phrase = _phrase_from_source_label(label)
        if not phrase or phrase in seen:
            continue
        seen.add(phrase)
        candidates.append({
            "brief_id": ident,
            "brief_kind": kind,
            "source_derived_phrase": phrase,
            "origin": "observed_cfpb_problem_category" if kind.startswith("recurring")
                      else "observed_ted_software_it_notice_title",
        })
    problems = [c for c in candidates if c["brief_kind"].startswith("recurring")]
    tenders = [c for c in candidates if c["brief_kind"].startswith("published")]
    chosen = []
    if problems:
        chosen.append(problems.pop(0))
    if tenders:
        chosen.append(tenders.pop(0))
    for item in problems + tenders:
        if len(chosen) == MAX_FOLLOWUPS:
            break
        chosen.append(item)
    return chosen


def investigate_workflow_briefs(
    briefs: dict[str, Any], *, as_of: date, lookback_days: int,
    cache: BudgetCache | None = None, env: dict[str, str] | None = None,
) -> dict[str, Any]:
    if (not isinstance(as_of, date)
            or isinstance(lookback_days, bool)
            or not isinstance(lookback_days, int)
            or not 7 <= lookback_days <= 90):
        raise ValueError("Invalid dated workflow check period")
    selected = select_workflow_followups(briefs)
    report: dict[str, Any] = {
        "mode": "source_derived_workflow_checks_not_buyer_validation",
        "status": "no_safe_source_derived_phrases",
        "source_ids": list(SOURCE_IDS),
        "source_requests_budgeted": len(selected) * len(SOURCE_IDS),
        "max_additional_source_requests": MAX_ADDITIONAL_REQUESTS,
        "no_rotating_default_topic_seeds": True,
        "no_synonym_expansion_or_industry_prior": True,
        "source_queries_from_original_observations_only": True,
        "source_population_coverage_verified": False,
        "same_commercial_workflow_verified": False,
        "buying_intent_or_budget_verified": False,
        "trend_or_seo_growth_verified": False,
        "topics": [],
    }
    if not selected:
        return report
    # hunt_current uses the existing per-origin free cap, cache, 429 cooldowns,
    # fixed provider plans and issue-quality screen. No raw provider errors copied.
    result = hunt_current(
        topics=[r["source_derived_phrase"] for r in selected],
        sources=list(SOURCE_IDS),
        as_of=as_of.isoformat(), lookback_days=lookback_days,
        execute=True, cache=cache, env=env,
    )
    returned = {
        item["topic"]: item
        for item in result.get("topics", [])
        if isinstance(item, dict) and isinstance(item.get("topic"), str)
    }
    observed = 0
    for selection in selected:
        original = returned.get(selection["source_derived_phrase"], {})
        coverage = []
        for source in SOURCE_IDS:
            found = next((
                row for row in original.get("source_coverage", [])
                if isinstance(row, dict) and row.get("source") == source
            ), {})
            status = found.get("status", "unavailable")
            if status == "observed":
                observed += 1
            row = {
                "source": source, "status": status
                if status in {"observed", "unavailable", "rate_limited",
                              "invalid_source_shape"} else "unavailable",
                "sample_records_accepted": max(0, min(20, found.get("records_accepted", 0)))
                if isinstance(found.get("records_accepted"), int)
                and not isinstance(found.get("records_accepted"), bool) else 0,
                "topic_title_matches_in_sample": max(
                    0, min(20, found.get("topical_title_matches", 0))
                ) if isinstance(found.get("topical_title_matches"), int)
                and not isinstance(found.get("topical_title_matches"), bool) else 0,
                "recent_dated_matches_in_sample": (
                    max(0, min(20, found.get("recent_eligible_matches", 0)))
                    if isinstance(found.get("recent_eligible_matches"), int)
                    and not isinstance(found.get("recent_eligible_matches"), bool) else 0
                ),
                "not_exhaustive": True,
            }
            if row["status"] != "observed":
                code = found.get("http_status")
                reason = found.get("reason")
                if isinstance(code, int) and not isinstance(code, bool) and 100 <= code <= 599:
                    row["http_status"] = code
                elif isinstance(reason, str) and reason in REASONS:
                    row["reason"] = reason
            coverage.append(row)
        issues = []
        for item in original.get("evidence", [])[:8]:
            if item.get("source") != "github_issues":
                continue
            ref = item.get("reference")
            title = _clean(item.get("title"), 110)
            when = item.get("event_date")
            if (not isinstance(ref, str) or ISSUE_URL.fullmatch(ref) is None
                    or not title or not isinstance(when, str)
                    or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", when) is None):
                continue
            issues.append({
                "source": "github_issues", "title": title,
                "date": when, "reference": ref,
                "evidence_class": "published_issue_not_validated_customer_pain",
            })
            if len(issues) == 2:
                break
        historic = []
        for item in original.get("context_examples", [])[:4]:
            if item.get("source") != "usaspending":
                continue
            ref = item.get("reference")
            reason = item.get("reason")
            title = _clean(item.get("title"), 110)
            if ref != USA_LANDING or reason not in CONTEXT_REASONS or not title:
                continue
            historic.append({
                "source": "usaspending", "title": title,
                "reference": USA_LANDING,
                "reference_specificity": "provider_search_not_exact_award",
                "not_recent_reason": reason,
                "record_last_modified_is_not_new_award": True,
            })
            if len(historic) == 2:
                break
        report["topics"].append({
            **selection, "source_coverage": coverage,
            "github_issue_examples": issues,
            "usaspending_context_only_examples": historic,
            "hunter_screening_status": _clean(original.get("status"), 65),
            "recent_github_issue_mentions_not_paying_customers": True,
            "usaspending_context_not_recent_procurement_evidence": True,
            "same_workflow_or_buyer_independently_verified": False,
        })
    report["status"] = (
        "bounded_independent_source_checks_observed"
        if observed == len(selected) * len(SOURCE_IDS)
        else "partial_independent_source_coverage"
    )
    return report


def format_workflow_followup(result: dict[str, Any]) -> list[str]:
    if result.get("mode") != "source_derived_workflow_checks_not_buyer_validation":
        raise ValueError("Expected completed independent source checks")
    lines = [
        "SOURCE-DERIVED INDEPENDENT CHECK (GitHub Issues + USAspending; explicit opt-in):",
        "  Phrases originate in actual TED/CFPB observations, never academic label seeds or invented synonyms.",
        "  Keyword results, GitHub issues and award record edits do NOT establish a shared workflow or paying buyers.",
    ]
    if not result["topics"]:
        lines.append("  No safe multiword source phrase qualified. No fallback seeds or network requests substituted.")
    for item in result["topics"]:
        lines.append(
            f"  {item['source_derived_phrase']} | from {item['origin']}"
            " | NOT market-demand verified"
        )
        for cover in item["source_coverage"]:
            diagnostic = ""
            if "http_status" in cover:
                diagnostic = f" (HTTP {cover['http_status']})"
            elif cover.get("reason"):
                diagnostic = f" ({cover['reason']})"
            lines.append(
                f"    {cover['source']}: {cover['status']}{diagnostic}"
                f" | sample title overlap: {cover['topic_title_matches_in_sample']}"
                f" | recent dated: {cover['recent_dated_matches_in_sample']}"
            )
        for issue in item["github_issue_examples"]:
            lines.append(f"    Public issue [{issue['date']}] {issue['title']}")
            lines.append("      " + issue["reference"])
        for context in item["usaspending_context_only_examples"]:
            lines.append(
                f"    Historical award-record context ({context['not_recent_reason']}): "
                + context["title"]
            )
            lines.append("      USAspending search landing, NOT exact award: " + USA_LANDING)
    lines.append(
        "  Two source phrases maximum, four extra free requests maximum; zero new providers or credentials. "
        "Unobserved sources are unknown, not proof of zero demand."
    )
    return lines
