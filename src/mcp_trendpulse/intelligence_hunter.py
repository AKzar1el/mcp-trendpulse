"""Optional, bounded current-activity hunter; history is never a prerequisite.

Ranks which *current investigations deserve reading* from recent, original,
source-attributed observations. A small search sample cannot demonstrate market
growth, population prevalence, buyer budgets, or startup success. No LLM, paid
API, scraping proxy, unattended scheduler, or cross-source identity guesswork.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from mcp_trendpulse.intelligence_core import (
    BudgetCache, DailyBudgetExceeded, IntelligenceError, collect, plan_source,
)
from mcp_trendpulse.intelligence_observations import MAX_SAMPLE_RECORDS, observe_source_snapshots
from mcp_trendpulse.intelligence_issue_quality import EXCLUDED_FROM_CURRENT_HUNT
from mcp_trendpulse.intelligence_opportunities import _day

HUNT_SOURCES = (
    "github_issues", "openalex", "cordis", "usaspending",
    "cfpb", "ted", "gleif", "companies_house",
)
DEFAULT_SOURCES = ("github_issues", "openalex", "cordis", "usaspending")
SEED_TOPICS = (
    "agent reliability", "cloud cost management", "supplier due diligence",
    "industrial maintenance", "privacy operations", "battery recycling",
    "customer dispute automation", "energy flexibility", "cybersecurity",
    "care administration", "laboratory automation", "fraud detection",
    "public procurement", "grid storage", "data interoperability",
    "carbon accounting", "developer productivity", "research commercialization",
)
MAX_TOPICS = 4
MAX_SOURCES = 5
DEFAULT_SAMPLE_LIMIT = 5
MAX_SAMPLE_LIMIT = 10
RELEVANCE_SOURCES = frozenset({"openalex", "github_issues"})
DATE_SEMANTICS = {
    "research_publication_not_purchase", "issue_creation_not_buyer_spend",
    "complaint_received_not_purchase", "notice_publication_not_confirmed_award",
}
NOISE = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "data", "for",
    "from", "how", "in", "is", "it", "new", "of", "on", "or", "our", "the",
    "their", "this", "to", "using", "with", "system", "systems",
    "software", "research", "study", "company", "companies", "service",
    "services", "platform", "analysis", "future", "solutions", "model",
    "models", "report", "reports", "public",
}
WORD = re.compile(r"[a-z0-9]+", re.ASCII)
TOPIC = re.compile(r"[A-Za-z0-9][A-Za-z0-9 -]{2,79}\Z")
ACRONYMS = {
    "ai": ("artificial", "intelligence"),
    "ml": ("machine", "learning"),
    "llm": ("large", "language"),
    "llms": ("large", "language"),
    "mcp": ("context", "protocol"),
    "api": ("application", "programming", "interface"),
    "apis": ("application", "programming", "interface"),
}


def _topics(topics: list[str] | None, today: date) -> list[str]:
    if topics is None or topics == []:
        # Rotate across all sector hypotheses rather than repeatedly polling
        # the same tech headlines. These are SEEDS, never "trends" themselves.
        index = today.toordinal() % len(SEED_TOPICS)
        topics = [SEED_TOPICS[(index + i * 5) % len(SEED_TOPICS)] for i in range(3)]
    if not isinstance(topics, list) or not 1 <= len(topics) <= MAX_TOPICS:
        raise ValueError("Provide at most four investigation topics")
    result = []
    for term in topics:
        if not isinstance(term, str):
            raise ValueError("Each topic must be plain text")
        normalized = " ".join(term.strip().split()).lower()
        if TOPIC.fullmatch(normalized) is None or normalized in result:
            raise ValueError("Topics must be unique, simple 3-80 character phrases")
        result.append(normalized)
    return result


def _sources(sources: list[str] | None) -> list[str]:
    if sources is None or sources == []:
        sources = list(DEFAULT_SOURCES)
    if (not isinstance(sources, list) or not 1 <= len(sources) <= MAX_SOURCES
            or any(not isinstance(source, str) or source not in HUNT_SOURCES
                   for source in sources)
            or len(set(sources)) != len(sources)):
        raise ValueError("Supply 1-5 unique approved hunter sources")
    return list(sources)


def _words(value: str) -> list[str]:
    tokens = []
    for word in WORD.findall(value.lower()):
        if word in ACRONYMS:
            tokens.extend(ACRONYMS[word])
            continue
        # Limited plural normalization for cost/costs and study/studies.
        # This is lexical matching, never semantic proof of the same demand.
        if word.endswith("ies") and len(word) >= 6:
            word = word[:-3] + "y"
        elif word.endswith("s") and not word.endswith("ss") and len(word) >= 5:
            word = word[:-1]
        if word not in NOISE and len(word) >= 3:
            tokens.append(word)
    return tokens


def _relevant(topic: str, title: str) -> bool:
    """Require multiple distinctive topic terms; avoid a loose single match."""
    subject = set(_words(topic))
    if not subject:
        return False
    found = set(_words(title))
    needed = min(len(subject), max(2, (len(subject) * 2 + 2) // 3))
    return len(subject & found) >= needed


def _candidate_phrases(observations: list[dict[str, Any]], seeds: set[str]) -> list[dict[str, Any]]:
    phrases: dict[str, set[str]] = defaultdict(set)
    for item in observations:
        tokens = _words(str(item.get("title") or ""))
        for width in (2, 3):
            for index in range(len(tokens) - width + 1):
                phrase = " ".join(tokens[index:index + width])
                if phrase not in seeds and len(phrase) <= 55:
                    phrases[phrase].add(item["kind"])
    # Real corroboration requires multiple source classes, not multiple
    # publications from one source nor duplicated search results.
    qualified = [x for x in phrases.items() if len(x[1]) >= 2]
    qualified.sort(key=lambda p: (-len(p[1]), p[0]))
    return [{"phrase": phrase, "distinct_source_classes": len(classes),
             "candidate_only": True} for phrase, classes in qualified[:5]]


def summarize_current_hunt(
    topic_batches: list[dict[str, Any]], *, as_of: str | None = None,
    lookback_days: int = 30,
) -> dict[str, Any]:
    """Pure offline ranking of dated observations, without historical baselines."""
    if (isinstance(lookback_days, bool) or not isinstance(lookback_days, int)
            or not 7 <= lookback_days <= 90):
        raise ValueError("lookback_days must be an integer between 7 and 90")
    if not isinstance(topic_batches, list) or not 1 <= len(topic_batches) <= MAX_TOPICS:
        raise ValueError("Provide one to four bounded topic batches")
    now = _day(as_of, "as_of") if as_of is not None else date.today()
    names = _topics([x.get("topic") if isinstance(x, dict) else None
                     for x in topic_batches], now)
    recent_cutoff = (now - timedelta(days=lookback_days - 1)).isoformat()
    weekly_cutoff = (now - timedelta(days=6)).isoformat()
    ranked = []
    all_recent = []
    for term, batch in zip(names, topic_batches):
        snapshots = batch.get("snapshots")
        report = observe_source_snapshots(term, snapshots, as_of=now.isoformat())
        matches = [row for row in report["sample_records"]
                   if _relevant(term, str(row.get("title") or ""))]
        # OpenAlex's assigned labels are useful discovery context when a
        # title alone is vague. Never promote these labels to dated activity.
        label_matches = [
            row for row in report["sample_records"] if row["source"] == "openalex"
            and row not in matches and any(
                _relevant(term, label) for label in row.get("provider_research_labels", [])
            )
        ]
        excluded = [
            row for row in matches
            if row["source"] == "github_issues"
            and row.get("issue_evidence_type") in EXCLUDED_FROM_CURRENT_HUNT
        ]
        quality_reasons = Counter(
            row["issue_evidence_type"] for row in excluded
        )
        # GitHub issue titles often contain market forecasts, hypothetical
        # specifications, or profile-repo tasks. They remain auditable, but
        # can never become fresh customer-pain or purchasing signals.
        screened = [row for row in matches if row not in excluded]
        current = [
            row for row in screened
            if row.get("event_date") is not None
            and recent_cutoff <= row["event_date"] <= now.isoformat()
            and row.get("date_semantics") in DATE_SEMANTICS
        ]
        all_recent.extend(current)
        classes = {row["kind"] for row in current}
        source_count = len({row["source"] for row in current})
        recent_week = [row for row in current if row["event_date"] >= weekly_cutoff]
        context = [row for row in screened if row not in current]
        if len(classes) >= 2 and source_count >= 2:
            # Independent source categories = investigation priority, NOT
            # shared buyer/workflow or a validated commercial opportunity.
            stage, priority = "current_cross_source_activity", 2
        elif current:
            # A single GitHub issue / paper is evidence of *publication*,
            # never two-thirds confidence in an actual business opportunity.
            stage, priority = "current_single_source_activity", 1
        elif context:
            # Historic/undated evidence does not establish current momentum.
            stage, priority = "context_only_not_recent_activity", 0
        elif excluded:
            stage, priority = "excluded_low_quality_activity", 0
        else:
            stage, priority = "insufficient_topical_observation", 0
        coverage = report["source_coverage"]
        # "observed:5" means five valid *sample* records, not five
        # topic matches. Expose both measurements without another request.
        for provider in coverage:
            key = provider["source"]
            topical = [r for r in matches if r["source"] == key]
            fresh = [r for r in current if r["source"] == key]
            contextual = [r for r in context if r["source"] == key]
            noisy = [r for r in excluded if r["source"] == key]
            provider["topical_title_matches"] = len(topical)
            provider["recent_eligible_matches"] = len(fresh)
            provider["context_only_matches"] = len(contextual)
            provider["excluded_noise_matches"] = len(noisy)
            provider["unmatched_sample_records"] = max(
                0, provider["records_accepted"] - len(topical)
            )
            if key == "openalex":
                provider["provider_label_only_matches"] = len(label_matches)
            if provider["status"] == "observed":
                if not provider["records_accepted"]:
                    provider["topical_coverage_note"] = "empty_bounded_sample"
                elif not topical:
                    provider["topical_coverage_note"] = (
                        "provider_label_context_only" if key == "openalex" and label_matches
                        else "no_title_match_in_bounded_sample"
                    )
                elif not fresh:
                    provider["topical_coverage_note"] = "context_or_noise_only"
                else:
                    provider["topical_coverage_note"] = "recent_dated_title_match"
        if coverage and all(row["status"] != "observed" for row in coverage):
            stage, priority = "no_usable_provider_coverage", 0
        context_examples = []
        for item in context[:4]:
            day = item.get("event_date")
            semantics = item.get("date_semantics")
            if semantics not in DATE_SEMANTICS:
                reason = "timestamp_not_comparable_recent_market_event"
            elif day is None:
                reason = "publication_date_unavailable"
            elif day < recent_cutoff:
                reason = "outside_requested_lookback"
            else:
                reason = "not_recent_activity"
            context_examples.append({
                "source": item["source"], "title": item.get("title", ""),
                "reference": item["reference"], "event_date": day,
                "reason": reason,
            })
        latest = max((row["event_date"] for row in current), default=None)
        candidate = {
            "topic": term, "status": stage, "investigation_priority": priority,
            "recent_dated_records_in_sample": len(current),
            "recent_7_day_records_in_sample": len(recent_week),
            "latest_supported_event_date": latest,
            "distinct_recent_source_classes": len(classes),
            "recent_source_classes": sorted(classes),
            "recent_independent_provider_types": source_count,
            "topical_context_records": len(context),
            "provider_label_context_examples": [
                {"source": row["source"], "title": row["title"], "reference": row["reference"],
                 "event_date": row["event_date"], "labels": row["provider_research_labels"]}
                for row in label_matches[:4]
            ],
            "provider_label_context_omitted": max(0, len(label_matches) - 4),
            "context_examples": context_examples,
            "title_overlap_is_not_semantic_or_buyer_validation": True,
            "quality_screened_issue_records": len(excluded),
            "quality_exclusion_reasons": dict(sorted(quality_reasons.items())),
            "quality_excluded_examples": [{
                "reference": row["reference"], "title": row.get("title", ""),
                "classification": row["issue_evidence_type"],
            } for row in excluded[:3]],
            "quality_screen_is_heuristic": True,
            "evidence_preview_omitted": max(0, len(current) - 12),
            "provider_coverage_degraded": report["coverage_degraded"],
            "source_coverage": coverage,
            "evidence": [
                {
                    "source": row["source"], "kind": row["kind"],
                    "id": row["id"], "title": row.get("title", ""),
                    "event_date": row["event_date"],
                    "date_semantics": row["date_semantics"],
                    "reference": row["reference"],
                    **({"doi": row["doi"]} if row.get("doi") else {}),
                    **({"issue_evidence_type": row["issue_evidence_type"]}
                       if row["source"] == "github_issues" else {}),
                }
                for row in sorted(current, key=lambda x: (x["event_date"], x["source"]),
                                  reverse=True)[:12]
            ],
            "exact_registry_matches": report["exact_registry_matches"][:5],
            "sample_population_coverage_verified": False,
            "same_buyer_workflow_independently_verified": False,
            "buying_intent_confirmed": False,
            "trend_growth_direction": "unknown_without_comparable_baseline",
            "success_probability": None,
            "follow_up": (
                "Read original evidence and verify common workflow, geography, and budget owner"
                if priority >= 2 else
                "Investigate independent buying evidence; recent posts alone cannot establish demand"
                if priority == 1 else
                "Discard promotional/hypothetical issue noise and seek original sources"
                if excluded else
                "Collect more recent dated evidence and identify the paying buyer"
            ),
        }
        ranked.append(candidate)
    ranked.sort(key=lambda x: (
        -x["investigation_priority"], -x["distinct_recent_source_classes"],
        -x["recent_7_day_records_in_sample"], x["topic"],
    ))
    return {
        "mode": "fresh_source_activity_hunt_not_market_growth_forecast",
        "as_of": now.isoformat(), "lookback_days": lookback_days,
        "seed_topics_checked": len(ranked),
        "active_multi_source_topics": sum(
            row["status"] == "current_cross_source_activity" for row in ranked),
        "topics": ranked, "discovered_related_phrases": _candidate_phrases(
            all_recent, set(names)),
        "data_science_caveat": (
            "Relevance-ranked small samples and different jurisdictions cannot "
            "provide population prevalence, verified demand growth, or TAM."
        ),
        "buyer_outcomes_verified": 0, "paid_apis_used": False,
        "longitudinal_history_required_for_current_triage": False,
    }


def hunt_current(
    topics: list[str] | None = None, sources: list[str] | None = None,
    *, as_of: str | None = None, lookback_days: int = 30,
    execute: bool = False, cache: BudgetCache | None = None,
    env: dict[str, str] | None = None,
    sample_limit: int = DEFAULT_SAMPLE_LIMIT, relevance_first: bool = False,
) -> dict[str, Any]:
    """Explicit network opt-in; every provider uses the existing safe planner."""
    asof = _day(as_of, "as_of") if as_of else date.today()
    selected_topics = _topics(topics, asof)
    selected_sources = _sources(sources)
    if (isinstance(lookback_days, bool) or not isinstance(lookback_days, int)
            or not 7 <= lookback_days <= 90):
        raise ValueError("lookback_days must be 7..90")
    if not isinstance(execute, bool):
        raise ValueError("execute must be a boolean")
    if type(sample_limit) is not int or not 1 <= sample_limit <= MAX_SAMPLE_LIMIT:
        raise ValueError("sample_limit must be an integer between 1 and 10")
    if sample_limit * len(selected_sources) > MAX_SAMPLE_RECORDS:
        raise ValueError("sample_limit times source count must not exceed 40 per topic")
    if type(relevance_first) is not bool:
        raise ValueError("relevance_first must be a boolean")
    relevance_sources = [
        source for source in selected_sources
        if relevance_first and source in RELEVANCE_SOURCES
    ]
    controls = {
        "requested_sample_limit_per_source": sample_limit,
        "relevance_first_sources": relevance_sources,
        "maximum_sample_records_per_topic": sample_limit * len(selected_sources),
    }
    prepared = []
    for topic in selected_topics:
        calls = []
        for source in selected_sources:
            keyword = f"FT = {topic}" if source == "ted" else topic
            try:
                plan = plan_source(
                    source, keyword=keyword, limit=sample_limit,
                    env=env, lookback_days=lookback_days,
                    relevance_first=source in relevance_sources,
                )
            except (IntelligenceError, ValueError) as exc:
                calls.append({
                    "source": source, "status": "not_configured",
                    "reason": "source_setup_required_or_invalid_plan",
                    "reason_type": type(exc).__name__,
                })
                continue
            if not execute:
                calls.append({"source": source, "status": "planned",
                              "plan": plan.public()})
                continue
            try:
                response = collect(plan, cache=cache, fetch=True, env=env, timeout=18)
                if response.get("status") not in {
                    "observed", "unavailable", "invalid_source_shape", "rate_limited",
                }:
                    raise IntelligenceError("Unexpected source status")
                # Some providers return more rows than requested. Preserve
                # the collector count, and never hide an invalid sample shape.
                observations = response.get("observations")
                if response["status"] == "observed" and isinstance(observations, dict):
                    sample = observations.get("sample")
                    count = observations.get("record_count")
                    if (
                        isinstance(sample, list) and sample_limit < len(sample) <= 20
                        and type(count) is int and count >= len(sample)
                    ):
                        response = {
                            **response,
                            "observations": {**observations, "sample": sample[:sample_limit]},
                        }
                calls.append({"source": source, "status": response["status"],
                              "snapshot": response})
            except DailyBudgetExceeded:
                calls.append({
                    "source": source, "status": "rate_limited",
                    "snapshot": {
                        "source": source, "status": "rate_limited",
                        "reason": "local_daily_budget_exhausted",
                        "cache_hit": False,
                    },
                })
            except (IntelligenceError, OSError, ValueError) as exc:
                calls.append({"source": source, "status": "unavailable",
                              "reason": "collection_failed",
                              "reason_type": type(exc).__name__})
        prepared.append({"topic": topic, "calls": calls})
    if not execute:
        return {
            "status": "planned", "execute_required_for_network": True,
            "network_performed": False, "topics": prepared,
            "request_count": len(selected_topics) * len(selected_sources),
            **controls,
            "provider_credentials_disclosed": False,
        }
    batches = []
    for row in prepared:
        snapshots = []
        for call in row["calls"]:
            if call.get("snapshot") is not None:
                snapshots.append(call["snapshot"])
            else:
                snapshots.append({"source": call["source"], "status": "unavailable",
                                  "reason": call.get("reason", "not_configured")})
        batches.append({"topic": row["topic"], "snapshots": snapshots})
    result = summarize_current_hunt(
        batches, as_of=asof.isoformat(), lookback_days=lookback_days,
    )
    result["network_performed"] = True
    result["requested_source_ids"] = selected_sources
    result["provider_credentials_disclosed"] = False
    result["source_request_budget"] = len(selected_topics) * len(selected_sources)
    result.update(controls)
    return result


def record_hunt_history(
    result: dict[str, Any], path: Path | None = None,
) -> dict[str, Any]:
    """Optional minimal SQLite telemetry: no keys, raw records, names, or URLs."""
    if result.get("mode") != "fresh_source_activity_hunt_not_market_growth_forecast":
        raise ValueError("Only a completed current hunt may be recorded")
    folder = Path.home() / ".mcp-trendpulse" / "intelligence"
    db = Path(path) if path is not None else folder / "hunter_history.sqlite"
    if db.is_symlink() or db.parent.is_symlink():
        raise ValueError("History database must not be a symlink")
    db.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    saved = 0
    with sqlite3.connect(db, timeout=10) as conn:
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hunter_snapshots (
                as_of TEXT NOT NULL,
                topic_hash TEXT NOT NULL,
                query_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                recent_sample_records INTEGER NOT NULL,
                recent_source_classes INTEGER NOT NULL,
                provider_coverage_degraded INTEGER NOT NULL,
                recorded_at TEXT NOT NULL,
                PRIMARY KEY (as_of, topic_hash, query_hash)
            )
        """)
        asof = _day(result.get("as_of"), "as_of")
        sources = result.get("requested_source_ids", [])
        if not isinstance(sources, list) or len(sources) > MAX_SOURCES:
            raise ValueError("Missing safe query-source provenance")
        signature_input = [sources, result.get("lookback_days")]
        sample_limit = result.get("requested_sample_limit_per_source", DEFAULT_SAMPLE_LIMIT)
        relevance_sources = result.get("relevance_first_sources", [])
        if sample_limit != DEFAULT_SAMPLE_LIMIT or relevance_sources:
            # Preserve the existing default history key; separate new
            # research configurations so differently sampled runs do not collide.
            signature_input.extend([sample_limit, relevance_sources])
        signature = hashlib.sha256(json.dumps(
            signature_input, sort_keys=True
        ).encode()).hexdigest()
        for item in result.get("topics", []):
            topic = item["topic"]
            safe = hashlib.sha256(topic.encode("utf-8")).hexdigest()
            conn.execute("""
                INSERT OR REPLACE INTO hunter_snapshots (
                    as_of, topic_hash, query_hash, status,
                    recent_sample_records, recent_source_classes,
                    provider_coverage_degraded, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                asof.isoformat(), safe, signature, item["status"],
                item["recent_dated_records_in_sample"],
                item["distinct_recent_source_classes"],
                int(item["provider_coverage_degraded"]),
                datetime.now(timezone.utc).isoformat(),
            ))
            saved += 1
        # Retention caps storage growth. Snapshots contain no raw identity data.
        conn.execute("DELETE FROM hunter_snapshots WHERE as_of < ?",
                     ((date.today() - timedelta(days=90)).isoformat(),))
    return {
        "status": "recorded", "topics_saved": saved,
        "history_path": str(db),
        "no_raw_records_or_keys_saved": True,
        "growth_or_purchase_validated": False,
    }


def format_hunt_report(result: dict[str, Any]) -> str:
    """Compact human-facing watchlist; never display auth headers."""
    if result.get("mode") != "fresh_source_activity_hunt_not_market_growth_forecast":
        raise ValueError("Text presentation requires a completed current hunt")
    lines = [
        f"CURRENT ACTIVITY WATCHLIST | {result['as_of']} | last {result['lookback_days']} days",
        "Investigation leads only: not verified market growth or buyers.",
        "",
    ]
    for index, row in enumerate(result["topics"], start=1):
        lines.append(
            f"{index}. {row['topic'].upper()} | priority {row['investigation_priority']}/3 "
            f"| {row['status']}"
        )
        lines.append(
            f"   Dated samples: {row['recent_dated_records_in_sample']} "
            f"({row['recent_7_day_records_in_sample']} from last seven days); "
            f"evidence classes: {row['distinct_recent_source_classes']}"
        )
        states = []
        for provider in row["source_coverage"]:
            source = provider["source"]
            if provider["status"] == "observed":
                state = f"{source}=observed:{provider['records_accepted']}"
                if provider.get("cache_hit"):
                    state += "(cached)"
            else:
                state = f"{source}={provider['status']}"
                if "http_status" in provider:
                    state += f"(HTTP {provider['http_status']})"
                elif provider.get("reason"):
                    state += f"({provider['reason']})"
            states.append(state)
        if states:
            lines.append("   Providers: " + " | ".join(states))
        counts = []
        for provider in row["source_coverage"]:
            src = provider["source"]
            title_hits = provider.get("topical_title_matches", 0)
            recent = provider.get("recent_eligible_matches", 0)
            noise = provider.get("excluded_noise_matches", 0)
            contextual = provider.get("context_only_matches", 0)
            counts.append(
                f"{src}={title_hits} title match(es) "
                f"[recent:{recent}, context:{contextual}, screened:{noise}]"
            )
        if counts:
            lines.append("   Topic overlap: " + " | ".join(counts))
        repaired = sum(
            p.get("quality_reclassified_from_cached_payload", 0)
            for p in row["source_coverage"]
        )
        if repaired:
            lines.append(
                f"   Cached issue quality refreshed: {repaired} record(s), "
                "no new API calls"
            )
        if row["provider_coverage_degraded"]:
            lines.append("   Coverage incomplete: one or more providers unavailable")
        if row["quality_screened_issue_records"]:
            reasons = ", ".join(
                f"{name}={number}" for name, number in
                row["quality_exclusion_reasons"].items()
            )
            lines.append(
                f"   Noise screened: {row['quality_screened_issue_records']} "
                f"GitHub issue(s) ({reasons})"
            )
        for item in row["evidence"][:3]:
            # Publisher titles are untrusted. Strip terminal control codes.
            raw = str(item.get("title") or "")
            title = "".join(ch if ch.isprintable() else " " for ch in raw)
            title = " ".join(title.split())[:75]
            lines.append(f"   - {item['source']} {item['event_date']}: {title}")
            lines.append(f"     {item['reference']}")
        if not row["evidence"] and row.get("context_examples"):
            lines.append("   Context only (not recent market activity):")
            for item in row["context_examples"][:2]:
                raw = str(item.get("title") or "")
                title = "".join(ch if ch.isprintable() else " " for ch in raw)
                title = " ".join(title.split())[:75]
                lines.append(f"   - {item['source']} ({item['reason']}): {title}")
                lines.append(f"     {item['reference']}")
        lines.append(f"   Next: {row['follow_up']}")
        lines.append("")
    lines.append(
        "Growth direction unknown without comparable, coverage-verified baseline measurements."
    )
    lines.append(
        "Use --record-history to preserve minimal metadata for later comparison."
    )
    return "\n".join(lines)
