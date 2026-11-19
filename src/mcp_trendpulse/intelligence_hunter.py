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
    BudgetCache, IntelligenceError, collect, plan_source,
)
from mcp_trendpulse.intelligence_observations import observe_source_snapshots
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
    return [x for x in WORD.findall(value.lower()) if x not in NOISE and len(x) >= 3]


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
        current = [
            row for row in matches
            if row.get("event_date") is not None
            and recent_cutoff <= row["event_date"] <= now.isoformat()
            and row.get("date_semantics") in DATE_SEMANTICS
        ]
        all_recent.extend(current)
        classes = {row["kind"] for row in current}
        source_count = len({row["source"] for row in current})
        recent_week = [row for row in current if row["event_date"] >= weekly_cutoff]
        context = [row for row in matches if row not in current]
        if len(classes) >= 2 and source_count >= 2:
            stage, priority = "current_cross_source_activity", 3
        elif current:
            stage, priority = "current_single_source_activity", 2
        elif context:
            stage, priority = "context_only_not_recent_activity", 1
        else:
            stage, priority = "insufficient_topical_observation", 0
        coverage = report["source_coverage"]
        if coverage and all(row["status"] != "observed" for row in coverage):
            stage, priority = "no_usable_provider_coverage", 0
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
            "provider_coverage_degraded": report["coverage_degraded"],
            "source_coverage": coverage,
            "evidence": [
                {
                    "source": row["source"], "kind": row["kind"],
                    "id": row["id"], "title": row.get("title", ""),
                    "event_date": row["event_date"],
                    "date_semantics": row["date_semantics"],
                    "reference": row["reference"],
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
    prepared = []
    for topic in selected_topics:
        calls = []
        for source in selected_sources:
            keyword = f"FT = {topic}" if source == "ted" else topic
            try:
                plan = plan_source(
                    source, keyword=keyword, limit=5,
                    env=env, lookback_days=lookback_days,
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
                calls.append({"source": source, "status": response["status"],
                              "snapshot": response})
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
        signature = hashlib.sha256(json.dumps(
            [sources, result.get("lookback_days")], sort_keys=True
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
