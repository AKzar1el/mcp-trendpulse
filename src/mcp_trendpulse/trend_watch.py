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
from dataclasses import asdict, dataclass, replace
from datetime import date
from pathlib import Path
from statistics import fmean, median
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


def evaluate_watch(
    rule: WatchRule, rows: list[tuple[date, float]], *, as_of: date | None = None
) -> WatchDecision:
    """Compare complete recent and preceding windows on the same normalized series."""
    if len(rows) < rule.window * 2:
        return WatchDecision(rule.id, "insufficient_data", None, None, None, None)
    compared = rows[-2 * rule.window :]
    latest_date = compared[-1][0]
    latest = latest_date.isoformat()
    gaps = [(right[0] - left[0]).days for left, right in zip(compared, compared[1:])]
    cadence_days = median(gaps)
    if max(gaps) > max(2 * cadence_days, cadence_days + 7):
        return WatchDecision(rule.id, "irregular_data", latest, None, None, None)
    # Allow delayed weekly/monthly provider buckets, but never turn old evidence
    # into a present-day alert merely because its historical scores increased.
    max_age_days = min(62, max(14, int(2 * cadence_days)))
    if ((as_of if as_of is not None else date.today()) - latest_date).days > max_age_days:
        return WatchDecision(rule.id, "stale_data", latest, None, None, None)
    previous = fmean(value for _, value in rows[-2 * rule.window : -rule.window])
    current = fmean(value for _, value in rows[-rule.window :])
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
        if self._database.is_symlink():
            raise ValueError("Watch database must not be a symlink")
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

    def preview(self, rule_id: str, evidence: bytes) -> WatchDecision:
        """Evaluate one saved rule without consuming its alert or cooldown."""
        rule = self.get(rule_id)
        rows = parse_evidence(evidence, keyword=rule.keyword, market=rule.market)
        return evaluate_watch(rule, rows)

    @staticmethod
    def _historical_report(rule: WatchRule, rows: list[tuple[date, float]]) -> dict[str, Any]:
        hypothetical = replace(rule, last_alert_date=None)
        status_counts: dict[str, int] = {}
        simulated_alerts: list[dict[str, Any]] = []
        for end in range(2 * rule.window, len(rows) + 1):
            # Only evidence available through this simulated observation is visible.
            decision = evaluate_watch(hypothetical, rows[:end], as_of=rows[end - 1][0])
            status_counts[decision.status] = status_counts.get(decision.status, 0) + 1
            if decision.status == "triggered":
                simulated_alerts.append(asdict(decision))
                hypothetical = replace(hypothetical, last_alert_date=decision.evidence_date)
        return {
            "rule_id": rule.id,
            "keyword": rule.keyword,
            "market": rule.market,
            "window": rule.window,
            "cooldown_days": rule.cooldown_days,
            "evaluated_windows": sum(status_counts.values()),
            "status_counts": status_counts,
            "simulated_alerts": simulated_alerts,
            "simulated": True,
            "note": (
                "Retrospective what-if on one user-supplied normalized series; not a reconstruction "
                "of data availability at each historical date, independent source verification, "
                "or an issued alert. Saved cooldown is neither read nor changed."
            ),
        }

    def backtest(
        self,
        rule_id: str,
        evidence: bytes,
        *,
        growth_pct: float | None = None,
        minimum_interest: float | None = None,
        window: int | None = None,
        cooldown_days: int | None = None,
        compare_baseline: bool = False,
    ) -> dict[str, Any]:
        """Simulate offline alerts with optional saved-policy versus scenario comparison."""
        saved_rule = self.get(rule_id)
        overrides = {
            key: value
            for key, value in {
                "growth_pct": growth_pct,
                "minimum_interest": minimum_interest,
                "window": window,
                "cooldown_days": cooldown_days,
            }.items()
            if value is not None
        }
        if compare_baseline and not overrides:
            raise ValueError("Baseline comparison requires at least one scenario override")
        rule = saved_rule
        if overrides:
            rule = replace(rule, **overrides)
            validate_rule(
                rule.keyword, rule.market, rule.growth_pct,
                rule.minimum_interest, rule.window, rule.cooldown_days,
            )
        rows = parse_evidence(evidence, keyword=rule.keyword, market=rule.market)
        report = self._historical_report(rule, rows)
        if overrides:
            report["scenario"] = {
                "growth_pct": rule.growth_pct,
                "minimum_interest": rule.minimum_interest,
                "window": rule.window,
                "cooldown_days": rule.cooldown_days,
                "overrides": sorted(overrides),
            }
        if compare_baseline:
            baseline = self._historical_report(saved_rule, rows)

            def brief(candidate: WatchRule, result: dict[str, Any]) -> dict[str, Any]:
                return {
                    "policy": {
                        "growth_pct": candidate.growth_pct,
                        "minimum_interest": candidate.minimum_interest,
                        "window": candidate.window,
                        "cooldown_days": candidate.cooldown_days,
                    },
                    "evaluated_windows": result["evaluated_windows"],
                    "status_counts": result["status_counts"],
                    "simulated_alert_dates": [a["evidence_date"] for a in result["simulated_alerts"]],
                }

            baseline_dates = set(a["evidence_date"] for a in baseline["simulated_alerts"])
            scenario_dates = set(a["evidence_date"] for a in report["simulated_alerts"])
            report["comparison"] = {
                "baseline": brief(saved_rule, baseline),
                "scenario": brief(rule, report),
                "added_alert_dates": sorted(scenario_dates - baseline_dates),
                "removed_alert_dates": sorted(baseline_dates - scenario_dates),
                "alert_count_delta": len(scenario_dates) - len(baseline_dates),
                "note": (
                    "Hypothetical historical alerts on one supplied series, not predictive performance "
                    "or verified demand. Different windows may have different evaluation counts; "
                    "added/removed dates do not establish improved alert quality."
                ),
            }
        return report

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
