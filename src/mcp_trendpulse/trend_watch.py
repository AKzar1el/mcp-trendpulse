"""Offline, opt-in watch rules evaluated against explicitly supplied evidence.

Trend Watch does not fetch Google data, schedule jobs, send notifications, or
enable the still-gated public hosted service. All rule state is local.
"""

from __future__ import annotations

import json
import math
import os
import re
import secrets
import sqlite3
from contextlib import closing, contextmanager
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from statistics import fmean
from typing import Any


MAX_EVIDENCE_BYTES = 256 * 1024
MAX_POINTS = 520


@dataclass(frozen=True)
class WatchRule:
    id: str
    keyword: str
    market: str
    growth_pct: float
    minimum_interest: float
    window: int
    cooldown_days: int
    last_alert_date: str | None = None


@dataclass(frozen=True)
class WatchDecision:
    rule_id: str
    status: str
    evidence_date: str | None
    baseline_interest: float | None
    current_interest: float | None
    growth_pct: float | None
    note: str = "User-supplied normalized Google Trends-style series; not independently verified."

    def as_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))


def validate_rule(
    keyword: str,
    market: str,
    growth_pct: float,
    minimum_interest: float,
    window: int,
    cooldown_days: int,
) -> None:
    if not isinstance(keyword, str) or not 1 <= len(keyword.strip()) <= 200:
        raise ValueError("Watch keyword must contain 1-200 characters")
    if re.fullmatch(r"[A-Z]{2}", market) is None:
        raise ValueError("Watch market must be a two-letter uppercase country code")
    if not math.isfinite(growth_pct) or not 1 <= growth_pct <= 1000:
        raise ValueError("Growth threshold must be between 1% and 1000%")
    if not math.isfinite(minimum_interest) or not 0 <= minimum_interest <= 100:
        raise ValueError("Minimum interest must be between 0 and 100")
    if not isinstance(window, int) or isinstance(window, bool) or not 2 <= window <= 12:
        raise ValueError("Comparison window must have 2-12 observations")
    if not isinstance(cooldown_days, int) or isinstance(cooldown_days, bool) or not 1 <= cooldown_days <= 90:
        raise ValueError("Cooldown must be between 1 and 90 days")


def parse_evidence(payload: bytes, *, keyword: str, market: str) -> list[tuple[date, float]]:
    """Read a bounded envelope without network access or silent cross-market mixing."""
    if len(payload) > MAX_EVIDENCE_BYTES:
        raise ValueError("Evidence file exceeds 256 KiB")
    try:
        envelope = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Evidence must be valid UTF-8 JSON") from exc
    if not isinstance(envelope, dict):
        raise ValueError("Evidence must include keyword, market and points")
    if envelope.get("keyword") != keyword or envelope.get("market") != market:
        raise ValueError("Evidence keyword/market does not match the saved watch rule")
    points = envelope.get("points")
    if not isinstance(points, list) or len(points) > MAX_POINTS:
        raise ValueError("Evidence points must be a list of at most 520 observations")

    rows: list[tuple[date, float]] = []
    observed: set[date] = set()
    for item in points:
        if not isinstance(item, dict):
            raise ValueError("Each point must contain an ISO date and normalized value")
        try:
            raw_date = item["date"]
            if not isinstance(raw_date, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_date) is None:
                raise ValueError("Evidence date must be YYYY-MM-DD")
            when = date.fromisoformat(raw_date)
            raw = item["value"]
            if isinstance(raw, bool):
                raise ValueError("Interest must be numeric")
            value = float(raw)
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Each point must contain a valid date and interest value") from exc
        if when > date.today() or when in observed or not math.isfinite(value) or not 0 <= value <= 100:
            raise ValueError("Evidence contains future/duplicate dates or an invalid 0-100 score")
        if "isPartial" in item and not isinstance(item["isPartial"], bool):
            raise ValueError("isPartial must be a boolean")
        observed.add(when)
        if item.get("isPartial", False):
            continue
        rows.append((when, value))
    if rows != sorted(rows):
        raise ValueError("Evidence observations must be sorted by date")
    return rows


def evaluate_watch(rule: WatchRule, rows: list[tuple[date, float]]) -> WatchDecision:
    """Compare complete recent and preceding windows on the same normalized series."""
    if len(rows) < rule.window * 2:
        return WatchDecision(rule.id, "insufficient_data", None, None, None, None)
    previous = fmean(value for _, value in rows[-2 * rule.window : -rule.window])
    current = fmean(value for _, value in rows[-rule.window :])
    latest = rows[-1][0].isoformat()
    if previous <= 0:
        return WatchDecision(rule.id, "zero_baseline", latest, previous, current, None)
    growth = 100.0 * (current - previous) / previous
    if current < rule.minimum_interest or growth < rule.growth_pct:
        status = "below_threshold"
    elif rule.last_alert_date is not None and latest <= rule.last_alert_date:
        status = "duplicate"
    elif (
        rule.last_alert_date is not None
        and (rows[-1][0] - date.fromisoformat(rule.last_alert_date)).days < rule.cooldown_days
    ):
        status = "cooldown"
    else:
        status = "triggered"
    return WatchDecision(rule.id, status, latest, round(previous, 2), round(current, 2), round(growth, 2))


class WatchStore:
    """Private SQLite watch-rule store, separate from shared provider cache."""

    def __init__(self, directory: Path | None = None):
        if directory is not None:
            root = Path(directory)
        elif os.environ.get("TRENDPULSE_WATCH_DIR"):
            root = Path(os.environ["TRENDPULSE_WATCH_DIR"])
        else:
            root = Path.home() / ".mcp-trendpulse" / "watches"
        root = root.expanduser()
        if not root.is_absolute() or root.is_symlink():
            raise ValueError("Watch directory must be an absolute, non-symlink directory")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._database = root / "watches.sqlite3"
        with self._connection() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS rules ("
                "id TEXT PRIMARY KEY, keyword TEXT NOT NULL, market TEXT NOT NULL,"
                "growth_pct REAL NOT NULL, minimum_interest REAL NOT NULL, window INTEGER NOT NULL,"
                "cooldown_days INTEGER NOT NULL, last_alert_date TEXT)"
            )
        if os.name != "nt":
            self._database.chmod(0o600)

    @contextmanager
    def _connection(self):
        with closing(sqlite3.connect(str(self._database), timeout=3)) as db:
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    @staticmethod
    def _as_rule(row: tuple[Any, ...]) -> WatchRule:
        return WatchRule(*row)

    def create(
        self,
        *,
        keyword: str,
        market: str,
        growth_pct: float = 30.0,
        minimum_interest: float = 20.0,
        window: int = 4,
        cooldown_days: int = 7,
    ) -> WatchRule:
        keyword = keyword.strip()
        validate_rule(keyword, market, growth_pct, minimum_interest, window, cooldown_days)
        rule = WatchRule(secrets.token_hex(8), keyword, market, growth_pct, minimum_interest, window, cooldown_days)
        with self._connection() as db:
            db.execute(
                "INSERT INTO rules VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                tuple(asdict(rule).values()),
            )
        return rule

    def list_rules(self) -> list[WatchRule]:
        with self._connection() as db:
            records = db.execute(
                "SELECT id, keyword, market, growth_pct, minimum_interest, window, cooldown_days,"
                " last_alert_date FROM rules ORDER BY keyword, market, id"
            ).fetchall()
        return [self._as_rule(row) for row in records]

    def get(self, rule_id: str) -> WatchRule:
        if re.fullmatch(r"[0-9a-f]{16}", rule_id) is None:
            raise ValueError("Unknown watch ID")
        with self._connection() as db:
            row = db.execute(
                "SELECT id, keyword, market, growth_pct, minimum_interest, window, cooldown_days,"
                " last_alert_date FROM rules WHERE id=?",
                (rule_id,),
            ).fetchone()
        if row is None:
            raise ValueError("Unknown watch ID")
        return self._as_rule(row)

    def delete(self, rule_id: str) -> bool:
        self.get(rule_id)
        with self._connection() as db:
            return bool(db.execute("DELETE FROM rules WHERE id=?", (rule_id,)).rowcount)

    def evaluate_and_record(self, rule_id: str, evidence: bytes) -> WatchDecision:
        rule = self.get(rule_id)
        rows = parse_evidence(evidence, keyword=rule.keyword, market=rule.market)
        # Evaluate under the write lock to avoid duplicate alerts across agents.
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute(
                "SELECT id, keyword, market, growth_pct, minimum_interest, window, cooldown_days,"
                " last_alert_date FROM rules WHERE id=?",
                (rule_id,),
            ).fetchone()
            if current is None:
                raise ValueError("Watch was removed")
            decision = evaluate_watch(self._as_rule(current), rows)
            if decision.status == "triggered":
                db.execute(
                    "UPDATE rules SET last_alert_date=? WHERE id=?",
                    (decision.evidence_date, rule_id),
                )
            return decision
