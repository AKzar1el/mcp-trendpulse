"""Seedless current-topic discovery from bounded, original public-source records.

No prechosen industry keywords, historical baseline, LLM, paid API, crawler,
synthetic trend scores, background polling or unauthorized secrets.
A candidate is an *observation worth investigating*, NOT established market
growth, a matched buyer or proven commercial opportunity.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from mcp_trendpulse.intelligence_core import (
    BudgetCache, IntelligenceError, collect, plan_source,
)
from mcp_trendpulse.intelligence_hunter import _words
from mcp_trendpulse.intelligence_observations import _entry
from mcp_trendpulse.intelligence_opportunities import _day

SOURCES = ("openalex", "cfpb", "ted")
SOURCE_LABELS = {
    "openalex": "recently published research",
    "cfpb": "consumer complaint categories",
    "ted": "EU public procurement notices",
}
MAX_RECORDS = 20
MAX_SNAPSHOT_BYTES = 180_000
NAME = re.compile(r"[^\w .,&/()'-]+", re.UNICODE)
_CUTOFF_WORDS = frozenset({
    "market", "growth", "forecast", "reach", "billion", "million",
    "study", "paper", "review", "overview", "approach", "method",
    "effect", "impact", "toward", "towards", "evaluation",
})


def _clean_name(value: Any, maximum: int = 100) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(NAME.sub(" ", value).split())[:maximum]


def _theme_tokens(value: str) -> list[str]:
    return [word for word in _words(value)
            if word not in _CUTOFF_WORDS and len(word) >= 4]


def _ngrams(text: str) -> set[str]:
    tokens = _theme_tokens(text)
    # OpenAlex topical text can be lengthy. Only a bounded excerpt matters;
    # each unique phrase in a record counts at most once.
    found: set[str] = set()
    for n in (2, 3):
        for i in range(max(0, min(len(tokens), 24) - n + 1)):
            phrase = " ".join(tokens[i:i + n])
            if 8 <= len(phrase) <= 55:
                found.add(phrase)
    return found


def _record(
    source: str, raw: dict[str, Any], today: date, cutoff: date,
) -> dict[str, Any] | None:
    base = _entry(source, raw, today)
    if base is None or base.get("event_date") is None:
        return None
    when = date.fromisoformat(base["event_date"])
    if not cutoff <= when <= today:
        return None
    if base.get("date_semantics") not in {
        "research_publication_not_purchase",
        "complaint_received_not_purchase",
        "notice_publication_not_confirmed_award",
    }:
        return None
    out = {
        "source": source, "evidence_class": base["kind"],
        "id": base["id"], "title": base.get("title", ""),
        "date": when.isoformat(), "reference": base["reference"],
        "date_semantics": base["date_semantics"],
        "theme": "", "theme_basis": "",
    }
    if source == "openalex":
        primary = raw.get("primary_topic")
        theme = primary.get("display_name") if isinstance(primary, dict) else None
        theme = _clean_name(theme)
        if 8 <= len(theme) <= 85 and len(_theme_tokens(theme)) >= 2:
            out["theme"] = theme
            out["theme_basis"] = "openalex_assigned_primary_topic"
    elif source == "cfpb":
        product = _clean_name(base.get("consumer_product"), 65)
        issue = _clean_name(base.get("reported_issue"), 75)
        if product and issue:
            out["theme"] = f"{product} — {issue}"[:110]
            out["theme_basis"] = "cfpb_public_product_issue_categories"
    elif source == "ted":
        # TED notices are distinct real published notices. Their complete
        # titles are too arbitrary for a trustworthy single-notice cluster.
        # Cross-origin exact lexical overlap is handled separately below.
        pass
    return out


def summarize_discovery(
    snapshots: list[dict[str, Any]], *, as_of: str | None = None,
    lookback_days: int = 30,
) -> dict[str, Any]:
    """Offline, deterministic, source-backed discovery from <=3 prior results."""
    if isinstance(lookback_days, bool) or not isinstance(lookback_days, int) or not 7 <= lookback_days <= 90:
        raise ValueError("lookback_days must be 7-90")
    if not isinstance(snapshots, list) or not 1 <= len(snapshots) <= len(SOURCES):
        raise ValueError("Provide 1-3 bounded discovery snapshots")
    try:
        bytes_used = len(json.dumps(snapshots, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Snapshots must be JSON-serializable finite data") from exc
    if bytes_used > MAX_SNAPSHOT_BYTES:
        raise ValueError("Discovery snapshots exceed 180 KB")
    today = _day(as_of, "as_of") if as_of is not None else date.today()
    cutoff = today - timedelta(days=lookback_days - 1)

    coverage = []
    records: list[dict[str, Any]] = []
    seen_sources: set[str] = set()
    seen_records: set[tuple[str, str]] = set()

    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            raise ValueError("Each source snapshot must be an object")
        source = snapshot.get("source")
        if not isinstance(source, str) or source not in SOURCES or source in seen_sources:
            raise ValueError("Unknown or repeated discovery source")
        seen_sources.add(source)
        status = snapshot.get("status")
        if status not in {"observed", "unavailable", "rate_limited", "invalid_source_shape"}:
            raise ValueError("Invalid discovery source status")
        row: dict[str, Any] = {
            "source": source, "scope": SOURCE_LABELS[source],
            "status": status, "sampled_rows": 0, "recent_valid_records": 0,
            "cache_hit": snapshot.get("cache_hit") is True,
            "sample_is_not_population": True,
        }
        http = snapshot.get("http_status")
        if isinstance(http, int) and not isinstance(http, bool) and 400 <= http <= 599:
            row["http_status"] = http
        if status != "observed":
            row["note"] = "Not accessible: absence of evidence is not evidence of no activity"
            coverage.append(row)
            continue
        observation = snapshot.get("observations")
        sample = observation.get("sample") if isinstance(observation, dict) else None
        if not isinstance(sample, list) or len(sample) > MAX_RECORDS:
            row["status"] = "invalid_source_shape"
            row["note"] = "Missing bounded observations"
            coverage.append(row)
            continue
        row["sampled_rows"] = len(sample)
        for raw in sample:
            if not isinstance(raw, dict):
                continue
            item = _record(source, raw, today, cutoff)
            if item is None:
                continue
            identifier = (source, item["id"])
            if identifier in seen_records:
                continue
            seen_records.add(identifier)
            records.append(item)
            row["recent_valid_records"] += 1
        coverage.append(row)

    # A source-declared public category is more grounded than arbitrary
    # token splitting. A candidate needs >=2 DISTINCT source IDs.
    category_buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in records:
        if item["theme"]:
            category_buckets[(item["source"], item["theme"].casefold())].append(item)

    # Cross-origin lexical overlap is useful for follow-up, but it cannot
    # assert a shared buyer, a shared workflow or synonymous meanings.
    phrase_records: dict[str, dict[tuple[str, str], dict[str, Any]]] = defaultdict(dict)
    for item in records:
        for phrase in _ngrams(item["title"]):
            phrase_records[phrase][(item["source"], item["id"])] = item
    candidates = []
    for (source, _), group in category_buckets.items():
        if len(group) < 2:
            continue
        theme = group[0]["theme"]
        candidates.append({
            "label": theme, "group_basis": group[0]["theme_basis"],
            "records": group, "source_count": 1,
        })
    for phrase, matching in phrase_records.items():
        group = list(matching.values())
        sources = {item["source"] for item in group}
        if len(sources) < 2:
            continue
        candidates.append({
            "label": phrase, "group_basis": "literal_phrase_across_sources_not_verified_workflow",
            "records": group, "source_count": len(sources),
        })
    candidates.sort(key=lambda c: (
        -c["source_count"], -len(c["records"]),
        -int(max(r["date"] for r in c["records"]).replace("-", "")),
        c["label"].lower(),
    ))

    selected = []
    for row in candidates:
        group = row["records"]
        sources = sorted({r["source"] for r in group})
        selected.append({
            "candidate_id": hashlib.sha256((
                row["group_basis"] + "|" + row["label"].casefold()
            ).encode()).hexdigest()[:14],
            "label": row["label"], "basis": row["group_basis"],
            "investigation_priority": 2 if len(sources) >= 2 else 1,
            "unique_recent_records_in_sample": len(group),
            "distinct_source_classes": len(sources),
            "sources": sources,
            "latest_event_date": max(r["date"] for r in group),
            "examples": [{
                "source": r["source"], "title": r["title"],
                "date": r["date"], "reference": r["reference"],
                "date_semantics": r["date_semantics"],
            } for r in sorted(group, key=lambda z: (z["date"], z["source"]), reverse=True)[:3]],
            "same_buyer_verified": False, "commercial_budget_verified": False,
            "growth_direction": "unknown_without_comparable_population_history",
            "next_check": (
                "Compare original sources: do they describe the same buyer/workflow?"
                if len(sources) >= 2 else
                "Validate independent sources and a buyer with a budget"
            ),
        })
        if len(selected) >= 12:
            break

    recent_examples = {}
    for source in SOURCES:
        rows = [r for r in records if r["source"] == source]
        recent_examples[source] = [{
            "title": r["title"], "date": r["date"], "reference": r["reference"],
            "theme": r["theme"], "date_semantics": r["date_semantics"],
        } for r in sorted(rows, key=lambda x: (x["date"], x["id"]), reverse=True)[:2]]
    return {
        "mode": "seedless_public_source_discovery_not_market_growth",
        "as_of": today.isoformat(), "lookback_days": lookback_days,
        "discovery_query_mode": "no_seed_topics_or_sector_keywords",
        "source_coverage": coverage, "recent_observations": len(records),
        "candidate_count": len(selected), "candidates": selected,
        "sample_examples_by_source": recent_examples,
        "source_health_degraded": any(c["status"] != "observed" for c in coverage),
        "population_coverage_verified": False, "growth_rate_verified": False,
        "paid_buyers_verified": False, "no_paid_apis": True,
        "limits": (
            "This is an explicitly small recent-date sample, not a uniform "
            "random sample or evidence of market acceleration. CFPB records "
            "reflect published consumer complaints, OpenAlex topic assignment "
            "is algorithmic, and TED notices represent procurement interest "
            "rather than awards or verified software budgets."
        ),
    }


def discover_current(
    *, lookback_days: int = 30, limit: int = 12,
    execute: bool = False, cache: BudgetCache | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Execute only when explicitly requested. Three fixed-source, bounded calls."""
    if isinstance(lookback_days, bool) or not isinstance(lookback_days, int) or not 7 <= lookback_days <= 90:
        raise ValueError("lookback_days must be 7-90")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 2 <= limit <= MAX_RECORDS:
        raise ValueError("limit must be 2-20")
    if not isinstance(execute, bool):
        raise ValueError("execute must be a boolean")
    now = date.today()
    period_start = (now - timedelta(days=lookback_days - 1)).strftime("%Y%m%d")
    plans = [
        plan_source("openalex", limit=limit, lookback_days=lookback_days,
                    discover=True, env=env),
        plan_source("cfpb", limit=limit, lookback_days=lookback_days, env=env),
        plan_source("ted", keyword=f"PD = ({period_start} <> {now:%Y%m%d})",
                    limit=limit, env=env),
    ]
    if not execute:
        return {
            "status": "planned", "network_performed": False,
            "execute_required_for_network": True,
            "source_count": len(plans),
            "plans": [plan.public() for plan in plans],
            "budget_excludes_paid_api_tiers": True,
        }
    sources = []
    for plan in plans:
        try:
            result = collect(plan, fetch=True, cache=cache, env=env, timeout=20)
            if result.get("status") not in {
                "observed", "unavailable", "invalid_source_shape", "rate_limited",
            }:
                raise IntelligenceError("Unexpected provider result")
            # Collectors may retain arbitrary raw provider JSON in data;
            # only sanitized, bounded projections enter discovery or MCP.
            sources.append({
                key: result[key] for key in (
                    "source", "status", "observations", "cache_hit", "http_status",
                ) if key in result
            })
        except (OSError, ValueError, IntelligenceError) as exc:
            sources.append({
                "source": plan.source, "status": "unavailable",
                "reason_code": type(exc).__name__,
            })
    result = summarize_discovery(sources, as_of=now.isoformat(), lookback_days=lookback_days)
    result["network_performed"] = True
    result["queries_budgeted"] = len(plans)
    result["user_credentials_exposed"] = False
    return result


def format_discovery_report(result: dict[str, Any]) -> str:
    if result.get("mode") != "seedless_public_source_discovery_not_market_growth":
        raise ValueError("Text output requires a completed discovery result")
    lines = [
        f"CURRENT TOPIC DISCOVERY | {result['as_of']} | last {result['lookback_days']} days",
        "No predefined topic seeds. Candidate observations are NOT verified market trends.",
        "",
    ]
    for item in result["source_coverage"]:
        tag = f"{item['source']}: {item['status']} | {item['recent_valid_records']}/{item['sampled_rows']} recent valid records"
        if "http_status" in item:
            tag += f" | HTTP {item['http_status']}"
        if item["cache_hit"]:
            tag += " (cached)"
        lines.append("Source: " + tag)
    lines.append("")
    if not result["candidates"]:
        lines.append("No recurring current themes passed conservative grouping in this small sample.")
    for idx, item in enumerate(result["candidates"], start=1):
        lines.append(
            f"{idx}. {item['label']} | investigation {item['investigation_priority']}/2 "
            f"| {item['unique_recent_records_in_sample']} independent records "
            f"| {', '.join(item['sources'])}"
        )
        lines.append("   Basis: " + item["basis"].replace("_", " "))
        for original in item["examples"][:2]:
            title = "".join(c if c.isprintable() else " " for c in original["title"])
            lines.append(
                f"   - {original['source']} {original['date']}: {' '.join(title.split())[:90]}"
            )
            lines.append(f"     {original['reference']}")
        lines.append("   Next: " + item["next_check"])
        lines.append("")
    lines.append("Other recent source observations (not validated trends):")
    for source, examples in result["sample_examples_by_source"].items():
        for item in examples[:1]:
            title = "".join(c if c.isprintable() else " " for c in item["title"])
            lines.append(f"  {source} [{item['date']}]: {' '.join(title.split())[:90]}")
            lines.append(f"    {item['reference']}")
    lines.append(
        "Growth, buyer budgets and market size: NOT VERIFIED. "
        "Later comparable source histories may improve confidence."
    )
    return "\n".join(lines)


def record_discovery_history(
    result: dict[str, Any], path: Path | None = None,
) -> dict[str, Any]:
    """Opt-in 90-day hashed candidate-index history; no raw records retained."""
    if result.get("mode") != "seedless_public_source_discovery_not_market_growth":
        raise ValueError("Record only completed discovery runs")
    db = Path(path) if path is not None else (
        Path.home() / ".mcp-trendpulse" / "intelligence" / "discovery_history.sqlite"
    )
    if not db.is_absolute() or db.is_symlink() or db.parent.is_symlink():
        raise ValueError("Use an absolute nonsymlink history path")
    db.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    cutoff = (date.today() - timedelta(days=90)).isoformat()
    run_date = _day(result["as_of"], "as_of").isoformat()
    with sqlite3.connect(db, timeout=10) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS discovery_candidates (
                day TEXT NOT NULL, candidate_hash TEXT NOT NULL,
                sample_records INTEGER NOT NULL, source_classes INTEGER NOT NULL,
                PRIMARY KEY(day, candidate_hash)
            )
        """)
        for c in result["candidates"][:12]:
            connection.execute("""
                INSERT INTO discovery_candidates VALUES (?, ?, ?, ?)
                ON CONFLICT(day, candidate_hash) DO UPDATE SET
                    sample_records=excluded.sample_records,
                    source_classes=excluded.source_classes
            """, (
                run_date, c["candidate_id"],
                c["unique_recent_records_in_sample"], c["distinct_source_classes"],
            ))
        connection.execute("DELETE FROM discovery_candidates WHERE day < ?", (cutoff,))
    return {
        "status": "recorded", "candidate_count": len(result["candidates"]),
        "history_path": str(db), "raw_records_saved": False,
        "growth_verified": False,
    }
