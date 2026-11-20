"""Local, source-safe and opt-in 90-day opportunity sighting ledger.

A seen date records only that this bounded pipeline observed a source, NOT
new demand, an active procurement, repeated independent customers, or a
revalidated notice. No API calls, provider payload retention, or background
jobs. The stored text is limited to published TED notice titles / CFPB categories.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

MAX_DAYS = 90
MAX_CURRENT = 6
MAX_PREVIOUS_SHOWN = 5
MODE = "source_observed_opportunity_sightings_not_market_growth"
TED_REF = re.compile(
    r"https://ted\.europa\.eu/en/notice/-/detail/[0-9]{1,7}-20[0-9]{2}\Z"
)
CFPB_REF = "https://www.consumerfinance.gov/data-research/consumer-complaints/"
KEY = re.compile(r"[a-f0-9]{14}\Z")


def _source_identity(idea: dict[str, Any]) -> dict[str, str] | None:
    """Strictly identify one published notice or one CFPB product/issue category."""
    if not isinstance(idea, dict):
        return None
    ident = idea.get("id")
    label = idea.get("source_observed_problem")
    reference = idea.get("source_reference")
    kind = idea.get("kind")
    if (not isinstance(ident, str) or KEY.fullmatch(ident) is None
            or not isinstance(label, str)
            or not isinstance(reference, str)
            or not 1 <= len(label) <= 125):
        return None
    if kind == "procurement_derived_software_hypothesis":
        if TED_REF.fullmatch(reference) is None:
            return None
        # A tender's publication ID is stable even if a later scope is revised.
        subject_text = "tender|" + reference
    elif kind == "consumer_problem_derived_software_hypothesis":
        if reference != CFPB_REF:
            return None
        # CFPB source landing links are shared; separate by published category.
        subject_text = "cfpb_category|" + label.casefold()
    else:
        return None
    if any(ord(c) < 32 or ord(c) == 127 for c in label):
        return None
    # Existing Idea Map screening has already reduced source text to a bounded,
    # published title/category. No narrative or complaint ID is serialized.
    screen = idea.get("procurement_fit_screen")
    screen_type = (
        screen.get("category")
        if isinstance(screen, dict) else ""
    )
    allowed = {
        "hardware_or_equipment_purchase",
        "license_or_entitlement_purchase",
        "maintenance_or_support_service",
        "development_and_support_service",
        "custom_development_or_implementation_service",
        "unclassified_software_it_purchase",
    }
    if screen_type not in allowed:
        screen_type = "not_classified"
    return {
        "key": hashlib.sha256(subject_text.encode("utf-8")).hexdigest()[:24],
        "kind": kind, "reference": reference,
        "label": label, "screen": screen_type,
    }


def record_idea_history(
    report: dict[str, Any], *, path: Path | None = None,
) -> dict[str, Any]:
    """Persist public source identity and one sighting per distinct local run day."""
    if (not isinstance(report, dict)
            or report.get("mode") != "source_grounded_project_idea_and_keyword_research_queue"
            or not isinstance(report.get("ideas"), list)
            or len(report["ideas"]) > MAX_CURRENT):
        raise ValueError("Opt-in idea history requires a completed bounded Idea Map")
    raw_day = report.get("as_of")
    if (not isinstance(raw_day, str)
            or re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_day) is None):
        raise ValueError("Idea history requires an ISO analysis date")
    try:
        as_of = date.fromisoformat(raw_day)
    except ValueError as exc:
        raise ValueError("Invalid analysis date") from exc
    db = Path(path) if path is not None else (
        Path.home() / ".mcp-trendpulse" / "intelligence" / "opportunity_history.sqlite3"
    )
    if (not db.is_absolute() or db.is_symlink()
            or any(parent.is_symlink() for parent in db.parents)):
        raise ValueError("Idea-history path must be absolute with no symlink components")
    db.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    raw_ideas = [_source_identity(idea) for idea in report["ideas"]]
    observed = list({i["key"]: i for i in raw_ideas if i is not None}.values())
    cutoff = (as_of - timedelta(days=MAX_DAYS - 1)).isoformat()
    newly_seen = 0
    with sqlite3.connect(db, timeout=10) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS opportunity_sources (
                subject_hash TEXT PRIMARY KEY, kind TEXT NOT NULL,
                reference TEXT NOT NULL, label TEXT NOT NULL,
                screen_category TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS opportunity_sightings (
                subject_hash TEXT NOT NULL,
                observed_day TEXT NOT NULL,
                PRIMARY KEY(subject_hash, observed_day),
                FOREIGN KEY(subject_hash)
                    REFERENCES opportunity_sources(subject_hash)
                    ON DELETE CASCADE
            )
        """)
        for subject in observed:
            connection.execute("""
                INSERT INTO opportunity_sources VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(subject_hash) DO UPDATE SET
                  reference=excluded.reference,
                  label=excluded.label,
                  screen_category=excluded.screen_category
            """, (
                subject["key"], subject["kind"], subject["reference"],
                subject["label"], subject["screen"],
            ))
            cursor = connection.execute(
                "INSERT OR IGNORE INTO opportunity_sightings VALUES (?, ?)",
                (subject["key"], raw_day),
            )
            newly_seen += max(0, cursor.rowcount)
        connection.execute(
            "DELETE FROM opportunity_sightings WHERE observed_day < ?",
            (cutoff,),
        )
        connection.execute("""
            DELETE FROM opportunity_sources WHERE subject_hash NOT IN
                (SELECT subject_hash FROM opportunity_sightings)
        """)
        history = connection.execute("""
            SELECT s.subject_hash, s.kind, s.reference, s.label,
                   s.screen_category, MIN(t.observed_day), MAX(t.observed_day),
                   COUNT(*)
            FROM opportunity_sources s
            JOIN opportunity_sightings t ON t.subject_hash=s.subject_hash
            GROUP BY s.subject_hash
            ORDER BY MAX(t.observed_day) DESC, s.subject_hash ASC
        """).fetchall()
    selected = {s["key"] for s in observed}
    previous = []
    current = []
    for key, kind, reference, label, screen, first, last, days in history:
        display = {
            "kind": kind, "source_reference": reference,
            "source_label": label, "last_screen_category": screen,
            "first_seen": first, "last_seen": last,
            "distinct_days_seen_in_this_pipeline": days,
            "repeat_buyers_or_market_growth_verified": False,
        }
        if key in selected:
            current.append(display)
        elif len(previous) < MAX_PREVIOUS_SHOWN:
            previous.append({
                **display, "current_source_status": (
                    "not_seen_in_current_bounded_sample_requires_revalidation"
                ),
                "prior_deadline_or_scope_may_have_changed": True,
            })
    return {
        "mode": MODE, "status": "locally_recorded_source_sightings",
        "storage": str(db),
        "retention_days": MAX_DAYS,
        "current_source_items_recorded": len(observed),
        "new_distinct_day_sightings": newly_seen,
        "existing_same_day_sightings": max(0, len(observed) - newly_seen),
        "current_source_history": current,
        "previously_observed_but_not_in_current_sample": previous,
        "max_previous_shown": MAX_PREVIOUS_SHOWN,
        "all_previous_sources_not_guaranteed_listed": True,
        "source_revalidation_performed": False,
        "historical_tenders_not_treated_as_active": True,
        "repeat_sample_appearance_is_not_verified_market_growth": True,
        "individual_cfpb_complaint_records_saved": False,
        "new_network_requests": 0,
        "no_scheduled_task_created": True,
    }


def format_idea_history(report: dict[str, Any]) -> list[str]:
    if report.get("mode") != MODE:
        raise ValueError("Expected completed opt-in source-sighting history")
    lines = [
        "OPPORTUNITY SOURCE HISTORY (opt-in local SQLite, 90-day retention):",
        f"  Current source leads: {report['current_source_items_recorded']} "
        f"| new unique source/day observations: {report['new_distinct_day_sightings']}"
        f" | already recorded on this analysis day: {report['existing_same_day_sightings']}",
        "  A sighting means this bounded pipeline saw a published source; "
        "not rising demand, new customers, or a currently open tender.",
    ]
    for row in report["current_source_history"][:MAX_CURRENT]:
        lines.append(
            f"  Current: {row['source_label']} | first seen: {row['first_seen']}"
            f" | observed run-days: {row['distinct_days_seen_in_this_pipeline']}"
        )
    if report["previously_observed_but_not_in_current_sample"]:
        lines.append("  Prior leads NOT present in current sample; do not treat as active:")
        for row in report["previously_observed_but_not_in_current_sample"]:
            lines.append(
                f"    {row['source_label']} | last seen: {row['last_seen']}"
                " | status: requires original-source revalidation"
            )
            lines.append("    " + row["source_reference"])
    else:
        lines.append("  No earlier separately observed sources found within retention.")
    lines.append(
        "  Source title/category and official reference only. "
        "No full provider payloads or CFPB personal complaint narratives retained."
    )
    return lines
