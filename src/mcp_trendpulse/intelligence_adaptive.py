"""Opt-in, bounded multi-pass hunter using the existing provider collectors.

Sessions retain only configuration and evidence fingerprints, counts and
typed statuses. No raw queries, source documents, credentials or titles are
stored. Completed passes are resumable; an interrupted in-flight request is
not evidence of success or failure.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import closing, nullcontext
from datetime import date
from pathlib import Path
from typing import Any

from filelock import FileLock

from mcp_trendpulse.intelligence_core import BudgetCache
from mcp_trendpulse.intelligence_hunter import (
    DEFAULT_SAMPLE_LIMIT, MAX_SAMPLE_LIMIT, RELEVANCE_SOURCES,
    _sources, _topics, hunt_current,
)
from mcp_trendpulse.intelligence_observations import MAX_SAMPLE_RECORDS

MAX_PASSES = 3
MAX_REQUESTS = 15
MAX_VERSIONS = 10
MAX_STATE_BYTES = 32768
HEX = re.compile(r"[0-9a-f]{64}")


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _session_db(path: Path | None) -> Path:
    db = path or Path.home() / ".mcp-trendpulse" / "intelligence" / "hunter_history.sqlite"
    if not db.is_absolute() or any(
        p.is_symlink() or getattr(p, "is_junction", lambda: False)()
        for p in (db, *db.parents)
    ):
        raise ValueError("Research history requires an absolute non-aliased path")
    db.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    return db


def _load(db: Path, key: str, config: str) -> dict[str, Any]:
    with closing(sqlite3.connect(db, timeout=5)) as conn:
        row = conn.execute(
            "SELECT body FROM adaptive_hunter_sessions WHERE session=? AND config=? "
            "ORDER BY version DESC LIMIT 1", (key, config),
        ).fetchone()
    if row is None or len(row[0]) > MAX_STATE_BYTES:
        raise ValueError("No matching bounded research checkpoint; start a new configuration")
    state = json.loads(row[0])
    if (not isinstance(state, dict) or not isinstance(state.get("seen"), list)
            or len(state["seen"]) > MAX_PASSES * 12
            or any(not isinstance(pair, list) or len(pair) != 2
                   or any(not isinstance(h, str) or HEX.fullmatch(h) is None for h in pair)
                   for pair in state["seen"])
            or not isinstance(state.get("passes"), list) or len(state["passes"]) > MAX_PASSES
            or not isinstance(state.get("attempted"), list) or len(state["attempted"]) > MAX_PASSES
            or any(not isinstance(h, str) or HEX.fullmatch(h) is None for h in state["attempted"])
            or not isinstance(state.get("next_sources"), list)
            or any(not isinstance(s, str) for s in state["next_sources"])
            or state.get("stop_reason") not in (
                None, "no_new_preview_evidence", "no_healthy_weak_sources", "request_budget_exhausted",
                "maximum_passes_reached", "no_distinct_strategy", "interrupted_pass_unknown",
            )
            or type(state.get("spent")) is not int or not 0 <= state["spent"] <= MAX_REQUESTS):
        raise ValueError("Invalid research checkpoint")
    return state


def _save(db: Path, key: str, config: str, state: dict[str, Any]) -> int:
    body = json.dumps(state, separators=(",", ":"), sort_keys=True)
    if len(body) > MAX_STATE_BYTES:
        raise ValueError("Research checkpoint exceeds local storage cap")
    with closing(sqlite3.connect(db, timeout=5)) as conn, conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS adaptive_hunter_sessions (
                session TEXT NOT NULL, version INTEGER NOT NULL,
                config TEXT NOT NULL, body TEXT NOT NULL,
                PRIMARY KEY(session, version)
            )
        """)
        conn.execute("BEGIN IMMEDIATE")
        version = conn.execute(
            "SELECT COALESCE(MAX(version),0)+1 FROM adaptive_hunter_sessions WHERE session=?",
            (key,),
        ).fetchone()[0]
        conn.execute("INSERT INTO adaptive_hunter_sessions VALUES (?,?,?,?)",
                     (key, version, config, body))
        conn.execute("DELETE FROM adaptive_hunter_sessions WHERE session=? AND version<=?",
                     (key, version - MAX_VERSIONS))
    return version


def adaptive_hunt(
    topic: str, sources: list[str] | None = None, *, lookback_days: int = 30,
    execute: bool = False, sample_limit: int = DEFAULT_SAMPLE_LIMIT,
    relevance_first: bool = False, max_passes: int = 2,
    request_budget: int | None = None, alternate_queries: list[str] | None = None,
    exclude_terms: list[str] | None = None, session_id: str | None = None,
    resume: bool = False, cache: BudgetCache | None = None,
    env: dict[str, str] | None = None, history_path: Path | None = None,
) -> dict[str, Any]:
    today = date.today()
    objective = _topics([topic], today)[0]
    selected = _sources(sources)
    if type(max_passes) is not int or not 1 <= max_passes <= MAX_PASSES:
        raise ValueError("max_passes must be 1..3")
    if type(execute) is not bool or type(resume) is not bool or type(relevance_first) is not bool:
        raise ValueError("Research flags must be booleans")
    if (type(sample_limit) is not int or not 1 <= sample_limit <= MAX_SAMPLE_LIMIT
            or sample_limit * len(selected) > MAX_SAMPLE_RECORDS):
        raise ValueError("Invalid bounded research sample")
    if type(lookback_days) is not int or not 7 <= lookback_days <= 90:
        raise ValueError("lookback_days must be 7..90")
    budget = len(selected) * max_passes if request_budget is None else request_budget
    if type(budget) is not int or not len(selected) <= budget <= MAX_REQUESTS:
        raise ValueError("request_budget must cover the first pass and be at most 15")
    if alternate_queries is not None and (not isinstance(alternate_queries, list) or len(alternate_queries) > 2):
        raise ValueError("At most two explicit alternate queries")
    alternates = _topics(alternate_queries, today) if alternate_queries else []
    if objective in alternates:
        raise ValueError("Alternate queries must differ from the objective")
    if exclude_terms is not None and (
        not isinstance(exclude_terms, list) or len(exclude_terms) > 5
        or any(not isinstance(t, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 -]{1,59}", t)
               for t in exclude_terms)
    ):
        raise ValueError("At most five simple exclusion phrases")
    exclusions = [t.casefold() for t in (exclude_terms or [])]
    if session_id is not None and (
        not isinstance(session_id, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", session_id) is None
    ):
        raise ValueError("Use a simple opaque research session ID")
    if resume and session_id is None:
        raise ValueError("resume requires a session_id")
    config = _hash([today.isoformat(), objective, selected, lookback_days, sample_limit,
                    relevance_first, max_passes, budget, alternates, exclusions])
    if not execute:
        return {
            "status": "planned", "network_performed": False, "session_written": False,
            "configuration_hash": config, "maximum_passes": max_passes,
            "maximum_request_slots": budget, "first_pass": hunt_current(
                [objective], selected, lookback_days=lookback_days, sample_limit=sample_limit,
                relevance_first=relevance_first, execute=False, env=env,
            ),
            "followups": "Only distinct strategies for healthy, weakly covered sources; stop on no novelty",
        }
    db = _session_db(history_path) if session_id is not None else None
    key = _hash(session_id) if session_id is not None else ""
    lock_path = db.parent / ("adaptive-" + key + ".lock") if db else None
    if lock_path is not None and (lock_path.is_symlink() or lock_path.is_dir()):
        raise ValueError("Unsafe research session lock")
    lock = FileLock(str(lock_path), timeout=2) if lock_path else nullcontext()
    with lock:
        if resume:
            try:
                state = _load(db, key, config)
            except sqlite3.OperationalError as exc:
                raise ValueError("No matching saved research session") from exc
        else:
            state = {"seen": [], "passes": [], "spent": 0, "next_sources": selected,
                     "attempted": [], "stop_reason": None}
        if state["spent"] > budget or len(state["attempted"]) > max_passes:
            raise ValueError("Checkpoint exceeds configured research bounds")
        seen = {tuple(pair) for pair in state["seen"]}
        preview = []
        version = None
        started_passes = len(state["passes"])
        initial_stop = state["stop_reason"]
        if len(state["attempted"]) > len(state["passes"]) and not state["stop_reason"]:
            # An interrupted pass may already have consumed provider quota.
            # Its precharged request slots cannot be used a second time.
            if len(state["attempted"]) >= max_passes or state["spent"] >= budget:
                state["stop_reason"] = "interrupted_pass_unknown"
        while not state["stop_reason"] and len(state["attempted"]) < max_passes:
            index = len(state["attempted"])
            active = [s for s in selected if s in state["next_sources"]]
            remaining = budget - state["spent"]
            active = active[:remaining]
            if not active:
                state["stop_reason"] = "request_budget_exhausted" if remaining <= 0 else "no_healthy_weak_sources"
                break
            query = objective if index == 0 or index > len(alternates) else alternates[index - 1]
            depth = sample_limit if index == 0 else min(MAX_SAMPLE_LIMIT, MAX_SAMPLE_RECORDS // len(active))
            relevance = relevance_first or (index > 0 and bool(set(active) & RELEVANCE_SOURCES))
            strategy = _hash([query, active, depth, relevance])
            if strategy in state["attempted"]:
                state["stop_reason"] = "no_distinct_strategy"
                break
            state["spent"] += len(active)
            state["attempted"].append(strategy)
            if db is not None:
                version = _save(db, key, config, state)
            report = hunt_current(
                [query], active, lookback_days=lookback_days, execute=True,
                sample_limit=depth, relevance_first=relevance, cache=cache, env=env,
            )["topics"][0]
            coverage = report["source_coverage"]
            new = duplicates = conflicts = excluded = 0
            for row in report["evidence"]:
                title = row.get("title", "").casefold()
                if any(re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", title) for term in exclusions):
                    excluded += 1
                    continue
                doi = row.get("doi") if row["source"] == "openalex" else None
                identity = _hash(["doi", doi] if doi else [row["source"], row["id"]])
                revision = _hash([row.get("title"), row.get("event_date"),
                                  None if doi else row.get("reference"),
                                  row.get("issue_evidence_type")])
                if (identity, revision) in seen:
                    duplicates += 1
                    continue
                conflicting = any(prior == identity for prior, _ in seen)
                conflicts += int(conflicting)
                seen.add((identity, revision))
                new += 1
                if len(preview) < 12:
                    preview.append({**row, "conflicts_with_prior_metadata": conflicting, "pass": index + 1})
            state["seen"] = sorted([list(pair) for pair in seen])
            state["passes"].append({
                "pass": index + 1, "strategy_hash": strategy, "request_slots": len(active),
                "sample_limit": depth, "relevance_first": relevance,
                "new_preview_records": new, "duplicate_preview_records": duplicates,
                "conflicting_preview_records": conflicts, "excluded_preview_records": excluded,
                "sources": [{"source": c["source"], "status": c["status"],
                             "recent_eligible_matches": c.get("recent_eligible_matches", 0)}
                            for c in coverage],
            })
            state["next_sources"] = [
                c["source"] for c in coverage
                if c["status"] == "observed" and c.get("recent_eligible_matches", 0) < 2
            ]
            if index > 0 and new == 0:
                state["stop_reason"] = "no_new_preview_evidence"
            elif not state["next_sources"]:
                state["stop_reason"] = "no_healthy_weak_sources"
            elif state["spent"] >= budget:
                state["stop_reason"] = "request_budget_exhausted"
            elif index + 1 >= max_passes:
                state["stop_reason"] = "maximum_passes_reached"
            if db is not None:
                version = _save(db, key, config, state)
        if db is not None and state["stop_reason"] != initial_stop and version is None:
            version = _save(db, key, config, state)
        return {
            "status": "completed", "configuration_hash": config, "as_of": today.isoformat(),
            "objective": objective, "request_slots_used": state["spent"],
            "maximum_request_slots": budget, "passes": state["passes"],
            "stop_reason": state["stop_reason"], "completed_passes_before_resume": started_passes,
            "unconfirmed_attempts": len(state["attempted"]) - len(state["passes"]),
            "new_evidence_preview": preview, "distinct_preview_revisions_seen": len(seen),
            "session_checkpoint_version": version, "maximum_retained_versions": MAX_VERSIONS,
            "preview_counts_are_not_population_coverage": True,
            "no_raw_records_persisted": True, "buying_intent_confirmed": False,
            "request_slots_include_cached_or_unavailable_calls": True,
        }
