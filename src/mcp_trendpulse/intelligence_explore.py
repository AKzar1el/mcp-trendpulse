"""M04: bounded Explore relative interest and related-query source observations.

Google Trends is sampled and normalized, not absolute keyword search volume.
This opt-in adapter reuses the existing paced TrendSpy provider and *the same*
local two/day provider-operation budget as the legacy related-keyword probe.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from datetime import date, datetime, timezone
from typing import Any

from mcp_trendpulse.intelligence_core import BudgetCache, DailyBudgetExceeded
from mcp_trendpulse.intelligence_keyword_probe import (
    PROVIDER_BUDGET_ID, UTC_DAILY_PROVIDER_CAP, _status as _related_status,
)
from mcp_trendpulse.intelligence_signal import (
    SignalPeriod, SignalProvenance, TrendSignal,
)

MODE = "google_trends_explore_source_evidence"
TIMEFRAMES = frozenset(("today 3-m", "today 12-m"))
DEFAULT_TIMEFRAME = "today 3-m"
CACHE_TTL_SECONDS = 6 * 3600
MAX_INTEREST_INPUT_POINTS = 400
MAX_INTEREST_OUTPUT_POINTS = 16
SOURCE_URL = "https://trends.google.com/trends/explore"
RSS_SOURCE = "google_trending_now_rss"
BIGQUERY_SOURCE = "google_trends_bigquery"
BIGQUERY_SOURCE_URL = (
    "https://cloud.google.com/blog/products/data-analytics/"
    "international-google-trends-datasets-in-bigquery"
)
VALID_STATUSES = frozenset(("observed", "observed_partial", "observed_empty"))
_GOOD_COUNTRY = re.compile(r"[A-Z]{2}\Z")


def _term(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("Term must be printable text")
    term = " ".join(value.split())
    if (not 2 <= len(term) <= 80 or "://" in term
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ValueError("Term must be 2-80 printable characters, not a URL")
    return term


def _country(value: Any) -> str:
    if not isinstance(value, str) or _GOOD_COUNTRY.fullmatch(value) is None:
        raise ValueError("Country must be an uppercase two-letter market code")
    return value


def select_seed(
    *, term: str | None = None, country: str | None = None,
    source: Any = None,
) -> dict[str, str | None]:
    """Only explicit input or an M01/M03 source-marked observed record."""
    if source is None:
        if term is None or country is None:
            raise ValueError("Provide --term and --country, or --source-file")
        return {
            "term": _term(term), "country": _country(country),
            "origin": "operator_supplied", "source_id": None, "language": None,
        }
    if term is not None or country is not None:
        raise ValueError("Source-file seed cannot be combined with manual term or market")
    if not isinstance(source, dict) or source.get("status") not in {
        "observed", "observed_partial",
    }:
        raise ValueError("Only observed M01 or M03 data can provide a seed")
    if source.get("mode") == "google_trending_now_public_rss_source_attributed":
        items = source.get("trends")
        record_id = RSS_SOURCE
    elif source.get("source") == "google_trends_bigquery_public":
        items = source.get("signals")
        record_id = BIGQUERY_SOURCE
    else:
        raise ValueError("Unsupported source input; expected M01 RSS or M03 BigQuery")
    market = _country(source.get("country"))
    if not isinstance(items, list) or not 1 <= len(items) <= 25:
        raise ValueError("Observed source has no bounded seed records")
    for item in items:
        try:
            raw = item["signal"] if record_id == RSS_SOURCE else item
            signal = TrendSignal.model_validate(raw)
            expected_url = (
                f"https://trends.google.com/trending/rss?geo={market}"
                if record_id == RSS_SOURCE else BIGQUERY_SOURCE_URL
            )
            if not (
                signal.source_id == record_id
                and signal.country == market
                and signal.coverage_status == "observed"
                and signal.source_url == expected_url
                and signal.provenance.method == (
                    "public_rss" if record_id == RSS_SOURCE else "public_dataset"
                )
                and signal.metric_type == (
                    "google_trending_traffic_bucket" if record_id == RSS_SOURCE
                    else "google_bigquery_rank"
                )
                and signal.observed_at <= datetime.now(timezone.utc)
                and (datetime.now(timezone.utc) - signal.observed_at).days <= (
                    7 if record_id == RSS_SOURCE else 30
                )
            ):
                continue
            value = _term(signal.raw_term)
        except (TypeError, KeyError, ValueError, AttributeError):
            continue
        return {
            "term": value, "country": market,
            "origin": "source_observed", "source_id": record_id,
            "language": signal.language,
        }
    raise ValueError("Source contained no valid observed Google Trends seed")


def _cache_key(seed: dict[str, Any], timeframe: str, operation: str) -> str:
    material = json.dumps(
        ["mjau_m04_v1", operation, seed["term"].casefold(), seed["country"],
         timeframe], separators=(",", ":"), ensure_ascii=False,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _related(raw: Any) -> dict[str, Any]:
    if (not isinstance(raw, dict)
            or "top" not in raw or "rising" not in raw):
        return {"status": "invalid_provider_shape", "top": [], "rising": []}
    tested = _related_status(raw)
    if tested["status"] == "invalid_provider_shape":
        return {"status": "invalid_provider_shape", "top": [], "rising": []}
    rows: dict[str, list[dict[str, Any]]] = {}
    for kind in ("top", "rising"):
        rows[kind] = []
        for candidate in tested[kind]:
            row = dict(candidate)
            if kind == "rising":
                row["breakout_meaning"] = (
                    "greater_than_5000_percent" if row["is_breakout"] else None
                )
                row["provider_value_semantics"] = (
                    "previous_comparable_period_percentage_growth_not_absolute_volume"
                )
            rows[kind].append(row)
    return {
        "status": "observed" if rows["top"] or rows["rising"] else "observed_empty",
        **rows,
    }


def _interest(
    raw: Any, *, seed: dict[str, Any], timeframe: str,
    observed: datetime,
) -> dict[str, Any]:
    if not isinstance(raw, list):
        return {"status": "invalid_provider_shape", "signals": []}
    seen: set[str] = set()
    signals: list[dict[str, Any]] = []
    rejected = 0
    for point in raw[:MAX_INTEREST_INPUT_POINTS]:
        if not isinstance(point, dict):
            rejected += 1
            continue
        raw_day = point.get("date")
        number = point.get("value")
        if (not isinstance(raw_day, str) or len(raw_day) != 10
                or not isinstance(number, (int, float)) or isinstance(number, bool)
                or not math.isfinite(number) or not 0 <= number <= 100
                or point.get("keyword") != seed["term"]):
            rejected += 1
            continue
        try:
            day = date.fromisoformat(raw_day)
        except ValueError:
            rejected += 1
            continue
        if day > observed.date() or raw_day in seen:
            rejected += 1
            continue
        seen.add(raw_day)
        signal = TrendSignal(
            source_id="google_trends_explore",
            source_url=SOURCE_URL,
            observed_at=observed,
            country=seed["country"],
            language=None,  # A country does not identify the search language.
            raw_term=seed["term"],
            normalized_term=seed["term"].casefold(),
            metric_type="google_trends_normalized_interest",
            metric_unit="relative_index_0_100",
            period=SignalPeriod(
                start_date=day, end_date=day, granularity="point_in_time",
            ),
            value=float(number),
            sampling_scope=(
                f"Single term Explore {timeframe} {seed['country']} "
                "within-query 0-100 time series; not absolute volume"
            ),
            coverage_status="observed",
            provenance=SignalProvenance(
                method="community_provider",
                sampling_basis="within_query_geography_and_timeframe_normalized_interest",
                is_observed_search_query=False,
            ),
        )
        signals.append(signal.model_dump(mode="json"))
    signals.sort(key=lambda s: s["period"]["start_date"])
    clipped = len(signals) > MAX_INTEREST_OUTPUT_POINTS
    signals = signals[-MAX_INTEREST_OUTPUT_POINTS:]
    return {
        "status": (
            "invalid_provider_shape" if raw and not signals else
            "observed_partial" if rejected or clipped or len(raw) > MAX_INTEREST_INPUT_POINTS
            else "observed" if signals else "observed_empty"
        ),
        "signals": signals,
        "source_points_received": len(raw),
        "source_points_rejected": rejected,
        "points_truncated": clipped or len(raw) > MAX_INTEREST_INPUT_POINTS,
        "basis": "single_keyword_normalized_0_to_100_within_selected_country_timeframe",
    }


def _cached_operation(
    raw: Any, *, operation: str, seed: dict[str, Any],
    timeframe: str, observed: datetime,
) -> dict[str, Any] | None:
    if (not isinstance(raw, dict) or raw.get("operation") != operation
            or raw.get("seed") != seed or raw.get("timeframe") != timeframe):
        return None
    output = raw.get("result")
    if not isinstance(output, dict) or output.get("status") not in VALID_STATUSES:
        return None
    if operation == "related":
        # Cached derived rows must be rechecked as original provider values.
        payload = {
            kind: [
                {
                    "query": item.get("query"), "value": item.get("provider_value"),
                    "is_breakout": item.get("is_breakout", False),
                }
                for item in output.get(kind, [])[:3]
            ] if isinstance(output.get(kind), list) and len(output[kind]) <= 3
            else None
            for kind in ("top", "rising")
        }
        candidate = _related(payload)
        return candidate if candidate["status"] == output["status"] else None
    if not isinstance(output.get("signals"), list) or len(output["signals"]) > MAX_INTEREST_OUTPUT_POINTS:
        return None
    checked = []
    try:
        for raw_signal in output["signals"]:
            signal = TrendSignal.model_validate(raw_signal)
            if (
                signal.source_id != "google_trends_explore"
                or signal.country != seed["country"]
                or signal.language is not None
                or signal.source_url != SOURCE_URL
                or signal.raw_term != seed["term"]
                or signal.metric_type != "google_trends_normalized_interest"
                or signal.observed_at > observed
                or signal.provenance.method != "community_provider"
                or signal.period.start_date > observed.date()
            ):
                return None
            checked.append(signal.model_dump(mode="json"))
    except (TypeError, ValueError, KeyError):
        return None
    if (output["status"] in {"observed", "observed_partial"} and not checked
            or output["status"] == "observed_empty" and checked):
        return None
    return {**output, "signals": checked}


async def discover_explore(
    seed: dict[str, Any], *, execute: bool = False,
    timeframe: str = DEFAULT_TIMEFRAME, provider: Any = None,
    cache: BudgetCache | None = None, observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Never fetch unless explicitly opted in; no paid or retry fallback."""
    if not isinstance(seed, dict):
        raise ValueError("Expected a validated seed")
    clean_seed = select_seed(term=seed.get("term"), country=seed.get("country"))
    if seed.get("origin") not in {"source_observed", "operator_supplied"}:
        raise ValueError("Unknown seed origin")
    if seed.get("language") is not None:
        if not isinstance(seed["language"], str) or len(seed["language"]) > 18:
            raise ValueError("Invalid source language")
    clean_seed.update({
        "origin": seed["origin"],
        "source_id": seed.get("source_id"),
        "language": seed.get("language"),
    })
    if timeframe not in TIMEFRAMES:
        raise ValueError("Timeframe must be 'today 3-m' or 'today 12-m'")
    if not isinstance(execute, bool):
        raise ValueError("Execute must be a boolean")
    observed = observed_at if observed_at is not None else datetime.now(timezone.utc)
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("Observation timestamp must have a timezone")
    observed = observed.astimezone(timezone.utc)
    report: dict[str, Any] = {
        "mode": MODE, "status": "planned" if not execute else "unavailable",
        "seed": clean_seed, "timeframe": timeframe,
        "source": "community_google_trends_trendspy",
        "source_url": SOURCE_URL,
        "language": None,
        "observed_at": observed.isoformat(),
        "provider_is_unofficial": True,
        "physical_http_requests_not_measured": True,
        "provider_budget_id": PROVIDER_BUDGET_ID,
        "local_utc_daily_provider_operations_cap": UTC_DAILY_PROVIDER_CAP,
        "provider_operations_attempted": 0,
        "network_performed": False,
        "exact_search_volume_available": False,
        "site_property_required": False,
        "paid_services_used": False,
        "related": {"status": "planned", "top": [], "rising": [], "cache_hit": False},
        "interest": {"status": "planned", "signals": [], "cache_hit": False},
    }
    if not execute:
        return report
    try:
        store = cache if cache is not None else BudgetCache()
    except (OSError, ValueError, sqlite3.Error):
        report["status"] = "local_budget_store_unavailable"
        for op in ("related", "interest"):
            report[op]["status"] = report["status"]
        return report

    for operation in ("related", "interest"):
        key = _cache_key(clean_seed, timeframe, operation)
        target = report[operation]
        try:
            previous = store.cached(key)
            cached = _cached_operation(
                previous, operation=operation, seed=clean_seed,
                timeframe=timeframe, observed=observed,
            )
            if cached is not None:
                target.update(cached)
                target["cache_hit"] = True
                continue
            if store.blocked(PROVIDER_BUDGET_ID):
                target["status"] = "provider_cooldown"
                continue
            store.reserve(PROVIDER_BUDGET_ID, UTC_DAILY_PROVIDER_CAP)
        except DailyBudgetExceeded:
            target["status"] = "local_daily_budget_exhausted"
            continue
        except (OSError, ValueError, sqlite3.Error):
            target["status"] = "local_budget_store_unavailable"
            continue

        if provider is None:
            from mcp_trendpulse.providers import get_provider_set
            provider = get_provider_set().trends
        report["provider_operations_attempted"] += 1
        report["network_performed"] = True
        try:
            if operation == "related":
                response = await provider.get_related_queries(
                    keyword=clean_seed["term"], geo=clean_seed["country"],
                    timeframe=timeframe, cat=0, gprop="",
                )
                result = _related(response)
            else:
                response = await provider.get_trends(
                    keyword=clean_seed["term"], geo=clean_seed["country"],
                    timeframe=timeframe, data_mode="daily",
                    source="google search", cat=0,
                )
                result = _interest(
                    response, seed=clean_seed, timeframe=timeframe, observed=observed,
                )
        except Exception as exc:
            # Never copy provider exception text: URLs/tokens may be embedded.
            name = type(exc).__name__
            if "RateLimit" in name or "Cooldown" in name:
                target["status"] = "provider_rate_limited"
                try:
                    store.cool_down(PROVIDER_BUDGET_ID, 300)
                except (OSError, ValueError, sqlite3.Error):
                    pass
            elif "Timeout" in name:
                target["status"] = "provider_timeout"
            else:
                target["status"] = "provider_unavailable"
            continue

        target.update(result)
        if result["status"] in VALID_STATUSES:
            try:
                store.save(key, {
                    "operation": operation, "seed": clean_seed,
                    "timeframe": timeframe, "result": result,
                }, CACHE_TTL_SECONDS)
            except (OSError, ValueError, TypeError, sqlite3.Error):
                target["cache_write_failed"] = True

    statuses = {report[op]["status"] for op in ("related", "interest")}
    if statuses <= VALID_STATUSES:
        report["status"] = (
            "observed_partial" if "observed_partial" in statuses
            else "observed_empty" if statuses == {"observed_empty"}
            else "observed"
        )
    elif statuses == {"local_daily_budget_exhausted"}:
        report["status"] = "local_daily_budget_exhausted"
    elif statuses == {"local_budget_store_unavailable"}:
        report["status"] = "local_budget_store_unavailable"
    elif "observed" in statuses or "observed_partial" in statuses or "observed_empty" in statuses:
        report["status"] = "observed_partial"
    else:
        report["status"] = "unavailable"
    return report


def format_explore_report(report: dict[str, Any]) -> str:
    seed = report["seed"]
    lines = [
        f"GOOGLE TRENDS EXPLORE | {seed['term']} [{seed['country']}] | {report['status']}",
        f"Window: {report['timeframe']} | Origin: {seed['origin']}",
        "Existing unofficial paced TrendSpy provider; max 2 shared local operations/UTC day.",
        "Top = relative rank; Rising = percent growth over comparable prior period.",
        "Breakout means >5000% growth, not 5000 searches; no exact volume or buyer demand.",
        f"Operations attempted: {report['provider_operations_attempted']}"
        + (" (cache used)" if report["related"].get("cache_hit")
           or report["interest"].get("cache_hit") else ""),
    ]
    for key in ("related", "interest"):
        lines.append(f"{key.upper()}: {report[key]['status']}")
    for kind in ("top", "rising"):
        for item in report["related"]["top" if kind == "top" else "rising"]:
            val = "Breakout >5000%" if item["is_breakout"] else item["provider_value"]
            lines.append(f"  {kind}: {item['query']} — {val}")
    for signal in report["interest"]["signals"]:
        lines.append(
            f"  {signal['period']['start_date']}: "
            f"{signal['value']}/100 normalized interest"
        )
    return "\n".join(lines)
