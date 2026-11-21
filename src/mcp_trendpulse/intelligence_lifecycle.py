"""M13: offline, conservative lifecycle inference from aligned typed source series.

No provider calls, cache writes, forecasting, cross-metric aggregation,
site-property dependencies, or inference that observations equal buyers.
"""
from __future__ import annotations

import calendar
import math
from collections import defaultdict
from datetime import date, timedelta, timezone
from statistics import mean, median, pstdev
from typing import Any

from pydantic import ValidationError

from mcp_trendpulse.intelligence_signal import TrendSignal

MAX_INPUT_BYTES = 128 * 1024
MAX_SIGNALS = 500
MAX_SERIES = 16
MAX_MISSING_DATES = 24
MAX_SOURCE_REFS = 12
_MIN_WINDOW = {"daily": 7, "weekly": 4, "monthly": 3}
_ALLOWED_GRANULARITIES = frozenset(_MIN_WINDOW)
_UNSUPPORTED_VALUES = frozenset({
    "google_trending_traffic_bucket",
    "google_bigquery_rank",
    "generated_keyword_candidate",
})
_ALLOWED_STATUSES = frozenset({"observed", "partial"})


def _series_key(signal: TrendSignal) -> tuple[str, ...]:
    """Prevent unlike series/source scopes from sharing a denominator."""
    return (
        signal.source_id, signal.source_url, signal.normalized_term,
        signal.country or "", signal.language or "", signal.metric_type,
        signal.metric_unit, signal.sampling_scope,
        signal.provenance.method, signal.provenance.sampling_basis,
        signal.period.granularity,
    )


def _metadata(key: tuple[str, ...], signals: list[TrendSignal]) -> dict[str, Any]:
    return {
        "source_id": key[0],
        "source_url": key[1],
        "normalized_term": key[2],
        "country": key[3] or None,
        "language": key[4] or None,
        "metric_type": key[5],
        "metric_unit": key[6],
        "sampling_scope": key[7],
        "provenance_method": key[8],
        "provenance_sampling_basis": key[9],
        "granularity": key[10],
        "original_terms": sorted({sig.raw_term for sig in signals}),
        "cross_source_metrics_aggregated": False,
        "unique_users_verified": False,
        "search_volume_verified": False,
        "buyer_demand_verified": False,
    }


def _month_after(d: date) -> date:
    return date(d.year + (d.month == 12), (d.month % 12) + 1, 1)


def _month_end(d: date) -> date:
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def _period_shape(signal: TrendSignal) -> str | None:
    start, end = signal.period.start_date, signal.period.end_date
    grain = signal.period.granularity
    if grain == "daily":
        return "daily" if start == end else None
    if grain == "weekly":
        if start == end:
            return "weekly_source_date_label"
        if end - start == timedelta(days=6):
            return "weekly_inclusive_span"
        return None
    if grain == "monthly":
        if start.day != 1:
            return None
        if end == start:
            return "monthly_source_date_label"
        if end == _month_end(start):
            return "monthly_inclusive_span"
    return None


def _next_anchor(d: date, grain: str) -> date:
    if grain == "daily":
        return d + timedelta(days=1)
    if grain == "weekly":
        return d + timedelta(days=7)
    if grain == "monthly":
        return _month_after(d)
    raise ValueError("Unsupported lifecycle period granularity")


def _expected_gap_dates(
    signals: list[TrendSignal], grain: str,
) -> tuple[list[str], int, bool]:
    """Calculate gaps with bounded work, including very distant source dates.

    Weekly labels must share an exact seven-day grid (same weekday).
    Calendar-month dates must advance by whole months on the first.
    """
    missing: list[str] = []
    count = 0
    for previous, current in zip(signals, signals[1:]):
        before, after = (
            previous.period.start_date, current.period.start_date,
        )
        if grain == "daily":
            steps = (after - before).days
        elif grain == "weekly":
            delta = (after - before).days
            if delta % 7:
                return [], 0, False
            steps = delta // 7
        else:
            steps = (after.year - before.year) * 12 + after.month - before.month
        if steps < 1:
            return [], 0, False
        blanks = steps - 1
        count += blanks
        if len(missing) < MAX_MISSING_DATES and blanks:
            next_date = _next_anchor(before, grain)
            for _ in range(min(blanks, MAX_MISSING_DATES - len(missing))):
                missing.append(next_date.isoformat())
                next_date = _next_anchor(next_date, grain)
    return missing, count, True


def _round(value: float) -> float:
    return round(float(value), 4)


def _variation(values: list[float]) -> float | None:
    avg = mean(values)
    return pstdev(values) / avg if avg > 0 else None


def _weekly_repetition(values: list[float]) -> dict[str, Any]:
    """Four complete 7-day blocks with repeatable high-amplitude shapes.

    This is a *weekly-pattern heuristic*, NOT established seasonality across
    multiple annual cycles, holidays, product releases or market demand.
    """
    if len(values) < 28:
        return {"detected": False, "reason": "fewer_than_four_full_7day_cycles"}
    recent = values[-28:]
    weeks = [recent[i:i + 7] for i in range(0, 28, 7)]
    week_means = [mean(week) for week in weeks]
    if not all(m > 0 for m in week_means):
        return {"detected": False, "reason": "zero_week_mean"}
    if max(week_means) / min(week_means) > 1.25:
        return {"detected": False, "reason": "week_level_drift_exceeds_25pct"}
    normalized = [
        [value / avg for value in week] for week, avg in zip(weeks, week_means)
    ]
    profile = [mean(week[day] for week in normalized) for day in range(7)]
    amplitude = max(profile) - min(profile)
    if amplitude < 0.65:
        return {"detected": False, "reason": "weekly_amplitude_too_small"}
    correlations = []
    p_mean = mean(profile)
    p_norm = math.sqrt(sum((x - p_mean) ** 2 for x in profile))
    if p_norm <= 0:
        return {"detected": False, "reason": "no_repeating_shape"}
    for week in normalized:
        avg = mean(week)
        w_norm = math.sqrt(sum((x - avg) ** 2 for x in week))
        corr = (
            sum((x - avg) * (y - p_mean) for x, y in zip(week, profile))
            / (w_norm * p_norm)
            if w_norm > 0 else 0
        )
        correlations.append(corr)
    if min(correlations) < 0.85:
        return {
            "detected": False,
            "reason": "weekly_shapes_not_consistently_repeated",
        }
    return {
        "detected": True,
        "period_days": 7,
        "complete_cycles": 4,
        "minimum_profile_correlation": _round(min(correlations)),
        "normalized_profile_peak_to_trough": _round(amplitude),
        "method": "four_cycle_weekly_pattern_heuristic_not_annual_seasonality",
    }


def _lifecycle(
    values: list[float], *, grain: str, window_size: int,
) -> tuple[str, str, dict[str, Any]]:
    """Classify only complete, aligned, numeric within-source windows."""
    before = values[-2 * window_size:-window_size]
    recent = values[-window_size:]
    previous_mean = mean(before)
    recent_mean = mean(recent)
    ratio = recent_mean / previous_mean if previous_mean else None
    change_pct = (
        100.0 * (recent_mean - previous_mean) / previous_mean
        if previous_mean else None
    )
    diagnostics: dict[str, Any] = {
        "previous_window_mean": _round(previous_mean),
        "recent_window_mean": _round(recent_mean),
        "recent_vs_previous_pct": _round(change_pct) if change_pct is not None else None,
        "previous_window_cv": _round(_variation(before))
        if _variation(before) is not None else None,
        "recent_window_cv": _round(_variation(recent))
        if _variation(recent) is not None else None,
        "relative_ratio": _round(ratio) if ratio is not None else None,
        "recent_positive_periods": sum(v > 0 for v in recent),
        "prior_positive_periods": sum(v > 0 for v in before),
    }
    if grain == "daily":
        weekly = _weekly_repetition(values)
        diagnostics["weekly_pattern"] = weekly
        if weekly["detected"]:
            return (
                "seasonal_pattern", "observed",
                {
                    **diagnostics,
                    "explanation": (
                        "Four repeated seven-day shapes; weekly-pattern "
                        "heuristic only, not annual or causal seasonality."
                    ),
                },
            )
    baseline = median(before) if before else 0
    recent_peak = max(recent)
    trim = recent.copy()
    trim.remove(recent_peak)
    trimmed_mean = mean(trim) if trim else 0
    if (
        previous_mean > 0
        and recent_peak >= max(4 * baseline, 4 * previous_mean)
        and sum(v >= 2.5 * previous_mean for v in recent) == 1
        and abs(trimmed_mean - previous_mean) / previous_mean <= 0.3
    ):
        return (
            "one_off_spike", "observed",
            {
                **diagnostics,
                "explanation": (
                    "Exactly one unusually large recent period; other "
                    "recent periods remain near the prior baseline. "
                    "Recurrence and cause are unverified."
                ),
            },
        )
    if previous_mean == 0:
        if recent_mean == 0:
            return (
                "no_activity_observed", "observed",
                {**diagnostics, "explanation": (
                    "All sampled, complete windows contain explicitly "
                    "measured zero values. Absence outside this scope is unknown."
                )},
            )
        repeated_recent = sum(v > 0 for v in recent) >= max(
            3, window_size // 3,
        )
        if repeated_recent and all(v == 0 for v in values[:-window_size]):
            return (
                "new_in_observed_window", "observed",
                {**diagnostics, "explanation": (
                    "All earlier supplied source periods were measured "
                    "zero, followed by multiple observed positive periods. "
                    "This is NOT an established global first-seen date."
                )},
            )
        if repeated_recent and any(v > 0 for v in values[:-window_size]):
            return (
                "resurfacing_in_observed_window", "observed",
                {**diagnostics, "explanation": (
                    "Earlier source observations were positive, followed "
                    "by a measured-zero baseline and multiple positive "
                    "recent periods; do not mislabel this as globally new."
                )},
            )
        return (
            "unconfirmed_change", "abstained",
            {**diagnostics, "explanation": (
                "Prior observed zeros with too few positive recent "
                "periods to establish a repeatable new pattern."
            )},
        )
    if (
        len(values) >= 3 * window_size
        and mean(values[-3 * window_size:-2 * window_size]) > 0
        and recent_mean > previous_mean * 1.25
    ):
        older_mean = mean(values[-3 * window_size:-2 * window_size])
        first_growth = previous_mean / older_mean - 1
        second_growth = recent_mean / previous_mean - 1
        diagnostics.update({
            "older_window_mean": _round(older_mean),
            "prior_growth_ratio_minus_one": _round(first_growth),
            "recent_growth_ratio_minus_one": _round(second_growth),
        })
        if first_growth >= 0.10 and second_growth > first_growth + 0.20:
            return (
                "accelerating", "observed",
                {**diagnostics, "explanation": (
                    "Two consecutive positive window-to-window increases, "
                    "the latter more pronounced; observational, not forecast."
                )},
            )
    if recent_mean <= previous_mean * 0.75:
        # A single zero in a complete source period is real, not a missing day.
        return (
            "declining", "observed",
            {**diagnostics, "explanation": (
                "Recent complete-window mean is at least 25% below "
                "the prior comparable observed mean; no causal claim."
            )},
        )
    if recent_mean >= previous_mean * 1.25:
        return (
            "rising_not_acceleration_verified", "observed",
            {**diagnostics, "explanation": (
                "Recent complete-window mean is at least 25% higher; "
                "acceleration not supported by enough consecutive growth windows."
            )},
        )
    if (
        abs(recent_mean - previous_mean) / previous_mean <= 0.15
        and all(
            (v is not None and v <= 0.65)
            for v in (_variation(before), _variation(recent))
        )
    ):
        return (
            "sustained", "observed",
            {**diagnostics, "explanation": (
                "Comparable observed window means vary by at most 15%, "
                "with bounded intra-window volatility."
            )},
        )
    return (
        "irregular_or_unclassified", "abstained",
        {**diagnostics, "explanation": (
            "Full observed windows exist but the signal is volatile or "
            "fails all conservative lifecycle decision rules."
        )},
    )


def _analyze(key: tuple[str, ...], signals: list[TrendSignal]) -> dict[str, Any]:
    meta = _metadata(key, signals)
    grain = key[10]
    report: dict[str, Any] = {
        **meta,
        "status": "abstained",
        "lifecycle": "unknown",
        "reason": None,
        "input_records": len(signals),
        "periods_observed": 0,
        "duplicate_observations_collapsed": 0,
        "min_points_per_window": _MIN_WINDOW.get(grain),
        "required_observed_periods": (
            2 * _MIN_WINDOW[grain] if grain in _MIN_WINDOW else None
        ),
        "missing_period_dates_first_24": [],
        "missing_period_count": 0,
        "source_coverage_incomplete": False,
        "internal_observation_gaps_checked": False,
        "provider_declared_window_boundaries_verified": False,
        "boundary_coverage_caveat": (
            "Only gaps BETWEEN supplied source periods can be detected "
            "without provider-declared expected start/end bounds; leading "
            "or trailing omitted source periods remain unknown."
        ),
        "first_recorded_source_period": None,
        "first_positive_observed_period": None,
        "last_recorded_source_period": None,
        "compared_window_dates": None,
        "comparison": None,
        "source_record_ids_first_12": sorted({
            s.provenance.source_record_id
            for s in signals if s.provenance.source_record_id is not None
        })[:MAX_SOURCE_REFS],
        "observed_at_utc_first": min(
            s.observed_at.astimezone(timezone.utc) for s in signals
        ).isoformat(),
        "observed_at_utc_last": max(
            s.observed_at.astimezone(timezone.utc) for s in signals
        ).isoformat(),
        "new_source_or_user_growth_verified": False,
        "annual_seasonality_verified": False,
        "forecast_generated": False,
    }
    if grain not in _ALLOWED_GRANULARITIES:
        report.update(status="unsupported_granularity", reason=(
            "Point-in-time records cannot form complete aligned "
            "daily, weekly or monthly lifecycle windows."
        ))
        return report
    if key[5] in _UNSUPPORTED_VALUES:
        report.update(status="unsupported_metric", reason=(
            "Buckets, source rank and derived hypotheses are not "
            "comparable continuous quantitative series."
        ))
        return report
    if key[6] == "relative_index_0_100" and len({
        s.observed_at for s in signals
    }) > 1:
        report.update(
            status="incomparable_normalized_batches",
            reason=(
                "Provider-normalized interest indices from different "
                "observation batches cannot be compared as one 0–100 scale."
            ),
        )
        return report
    if any(
        sig.metric_unit in {
            "rank", "impressions", "pageviews", "stories", "issues",
            "downloads", "questions", "mentions",
        } and sig.value is not None and sig.value > 2**53 - 1
        for sig in signals
    ):
        report.update(
            status="unsafe_numeric_precision",
            reason=(
                "Provider count exceeds the exact IEEE-754 integer range; "
                "refusing false precision and computed growth."
            ),
        )
        return report
    if any(
        sig.coverage_status != "observed" or sig.value is None
        for sig in signals
    ):
        report.update(
            status="coverage_incomplete",
            source_coverage_incomplete=True,
            reason=(
                "One or more source observations are partial, unavailable, "
                "no_data or unmeasured; never fill missing values with zeros."
            ),
        )
        return report

    by_period: dict[tuple[date, date], list[TrendSignal]] = defaultdict(list)
    for sig in signals:
        by_period[(sig.period.start_date, sig.period.end_date)].append(sig)
    distinct: list[TrendSignal] = []
    for period in sorted(by_period):
        records = by_period[period]
        first = records[0]
        if any(
            sig.value != first.value
            or sig.period.granularity != first.period.granularity
            for sig in records[1:]
        ):
            report.update(
                status="conflicting_source_revisions",
                reason=(
                    "Multiple observations disagree for the same source "
                    "period; no latest-value cherry-picking is permitted."
                ),
            )
            return report
        distinct.append(min(
            records, key=lambda sig: (
                sig.observed_at,
                sig.provenance.source_record_id or "",
            ),
        ))
    report["periods_observed"] = len(distinct)
    report["duplicate_observations_collapsed"] = len(signals) - len(distinct)
    report["first_recorded_source_period"] = (
        distinct[0].period.start_date.isoformat()
    )
    report["last_recorded_source_period"] = (
        distinct[-1].period.start_date.isoformat()
    )
    positives = [sig.period.start_date for sig in distinct if sig.value and sig.value > 0]
    report["first_positive_observed_period"] = (
        min(positives).isoformat() if positives else None
    )
    shape = [_period_shape(sig) for sig in distinct]
    if None in shape or len(set(shape)) != 1:
        report.update(
            status="unaligned_or_mixed_period_shapes",
            reason=(
                "Source period shapes must be valid, exact and consistent; "
                "no resampling or ambiguous date labeling permitted."
            ),
        )
        return report
    if any(
        sig.period.end_date > sig.observed_at.date() for sig in distinct
    ):
        report.update(
            status="source_time_inconsistent",
            reason="A source measurement period ends after its observation timestamp.",
        )
        return report
    missing, count, aligned = _expected_gap_dates(distinct, grain)
    report["internal_observation_gaps_checked"] = aligned
    if not aligned:
        report.update(
            status="unaligned_or_mixed_period_shapes",
            reason=(
                "Weekly date labels shifted from their seven-day source grid "
                "or period anchors are not strictly increasing."
            ),
        )
        return report
    report["missing_period_dates_first_24"] = missing
    report["missing_period_count"] = count
    if count:
        report.update(
            status="coverage_incomplete",
            source_coverage_incomplete=True,
            reason=(
                "Missing intermediate source periods are unknown, not zero; "
                "window means and growth comparisons are suppressed."
            ),
        )
        return report
    window = _MIN_WINDOW[grain]
    if len(distinct) < 2 * window:
        report.update(
            status="insufficient_history",
            reason=(
                f"Requires at least {2 * window} fully observed, aligned "
                f"{grain} source periods; {len(distinct)} verified. "
                "Do not extrapolate from a short source snapshot."
            ),
        )
        return report
    recent = distinct[-window:]
    previous = distinct[-2 * window:-window]
    report["compared_window_dates"] = {
        "previous_first": previous[0].period.start_date.isoformat(),
        "previous_last": previous[-1].period.start_date.isoformat(),
        "recent_first": recent[0].period.start_date.isoformat(),
        "recent_last": recent[-1].period.start_date.isoformat(),
    }
    lifecycle, status, diagnostics = _lifecycle(
        [float(sig.value) for sig in distinct], grain=grain, window_size=window,
    )
    report.update(
        status=status,
        lifecycle=lifecycle,
        reason=diagnostics.pop("explanation"),
        comparison=diagnostics,
    )
    return report


def analyze_lifecycle(payload: Any) -> dict[str, Any]:
    """Consume supplied M00 typed signals; no filesystem/network side effects."""
    if isinstance(payload, list):
        incoming = payload
    elif isinstance(payload, dict) and set(payload) == {"signals"}:
        incoming = payload["signals"]
    else:
        raise ValueError("Expected an array of typed signals or {'signals': [...]}")
    if not isinstance(incoming, list) or not 1 <= len(incoming) <= MAX_SIGNALS:
        raise ValueError("Expected 1–500 sourced observations")
    grouped: dict[tuple[str, ...], list[TrendSignal]] = defaultdict(list)
    for obj in incoming:
        try:
            signal = TrendSignal.model_validate(obj)
        except (ValidationError, ValueError, TypeError) as exc:
            raise ValueError("Input contains an invalid typed source signal") from exc
        if len(signal.raw_term) > 180 or len(signal.normalized_term) > 180:
            raise ValueError("Invalid source term length")
        grouped[_series_key(signal)].append(signal)
    if len(grouped) > MAX_SERIES:
        raise ValueError("Too many source/term/metric/scope groups in one offline file")
    result = [
        _analyze(key, grouped[key])
        for key in sorted(grouped)
    ]
    return {
        "schema_version": 1,
        "mode": "offline_source_scoped_history_lifecycle",
        "network_performed": False,
        "provider_operations": 0,
        "sqlite_or_quota_modified": False,
        "paid_services_used": False,
        "dependencies_added": False,
        "forecast_generated": False,
        "cross_source_metric_comparison_performed": False,
        "input_records": len(incoming),
        "source_series": len(result),
        "series": result,
        "classification_note": (
            "Labels are conservative heuristics on aligned, fully observed "
            "within-source periods; not buyer demand, search volume, forecasts "
            "or proof of seasonal/causal behavior."
        ),
        "missingness_note": (
            "Partial/missing, unavailable and no-data periods never mean "
            "measured zero. Explicit source-observed zero is valid."
        ),
        "normalized_interest_note": (
            "Relative Google Trends 0–100 values compare only within a "
            "consistent original normalization batch, never across snapshots."
        ),
        "rank_direction_note": (
            "Source rank and approximate bucket metrics are excluded from "
            "numeric lifecycle inference."
        ),
    }


def format_lifecycle_report(report: dict[str, Any]) -> str:
    lines = [
        "OFFLINE M13 SOURCE-SCOPED TREND LIFECYCLE",
        f"Sources: {report['source_series']} | observations: {report['input_records']}",
        "No network or quota changes; labels are observational heuristics.",
    ]
    for group in report["series"]:
        lines.append(
            f"- {group['normalized_term']} [{group['source_id']}:"
            f"{group['metric_type']}/{group['country'] or 'scope_unknown'}/"
            f"{group['language'] or 'language_unknown'}] "
            f"{group['status']}: {group['lifecycle']}"
        )
        lines.append(f"  {group['reason']}")
    return "\n".join(lines)
