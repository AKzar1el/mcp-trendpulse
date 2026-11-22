"""M01: bounded Google Trending Now RSS using the existing TrendSpy provider.

No RSS client, extra dependency, browser, site property or background poller.
Google's public RSS exposes a short list of recent *grouped* trend labels with
approximate traffic buckets, not exact search volumes or a population sample.
"""
from __future__ import annotations

import hashlib
import html
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from mcp_trendpulse.errors import (
    ProviderError, ProviderRateLimitError, ProviderTimeoutError,
)
from mcp_trendpulse.intelligence_core import BudgetCache, DailyBudgetExceeded
from mcp_trendpulse.intelligence_signal import (
    SignalPeriod, SignalProvenance, TrendSignal,
)

MODE = "google_trending_now_public_rss_source_attributed"
SOURCE_BUDGET_ID = "google_trending_now_rss"
MAX_FREE_REQUESTS_PER_UTC_DAY = 12
CACHE_TTL_SECONDS = 15 * 60
MAX_SOURCE_ROWS = 20
MAX_OUTPUT_ROWS = 10
MAX_NEWS_PER_TREND = 3
_SENSITIVE_QUERY = frozenset((
    "apikey", "api_key", "key", "token", "access_token", "authorization",
    "password", "secret", "client_secret",
))
_TRAFFIC = re.compile(r"(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?[KMB]?\+?\Z", re.I)


def _geo(country: str) -> str:
    if not isinstance(country, str) or not re.fullmatch(r"[A-Z]{2}", country):
        raise ValueError("Google Trending Now country must be uppercase ISO alpha-2")
    return country


def _source_url(geo: str) -> str:
    return "https://trends.google.com/trending/rss?geo=" + geo


def _text(value: Any, maximum: int) -> str:
    if not isinstance(value, str):
        return ""
    result = " ".join(html.unescape(value).split())
    if (not result or len(result) > maximum
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in result)):
        return ""
    return result


def _public_news_link(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 500 or any(
        c.isspace() or ord(c) < 32 for c in value
    ):
        return ""
    try:
        parsed = urlsplit(value)
        query_keys = {key.casefold() for key, _ in parse_qsl(
            parsed.query, keep_blank_values=True,
        )}
        if (parsed.scheme != "https" or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.fragment or _SENSITIVE_QUERY & query_keys):
            return ""
    except ValueError:
        return ""
    return value


def _started_at(raw: Any, observed: datetime) -> datetime | None:
    # TrendSpy 0.1.6 TrendKeywordLite.started is a Unix epoch integer.
    # It is the feed's start/publication time, not the HTTP fetch timestamp.
    if (not isinstance(raw, (int, float)) or isinstance(raw, bool)
            or not 0 < raw <= observed.timestamp()):
        return None
    try:
        return datetime.fromtimestamp(raw, tz=timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None


def _extract_news(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, (list, tuple)):
        return []
    results: list[dict[str, str]] = []
    urls = set()
    for entry in raw[:15]:
        if not isinstance(entry, dict):
            continue
        title = _text(entry.get("title"), 180)
        link = _public_news_link(entry.get("url"))
        if not title or not link or link in urls:
            continue
        urls.add(link)
        results.append({
            "title": title, "url": link,
            "source": _text(entry.get("source"), 70),
        })
        if len(results) == MAX_NEWS_PER_TREND:
            break
    return results


def _output_base(geo: str, *, execute: bool) -> dict[str, Any]:
    return {
        "mode": MODE,
        "status": "unavailable" if execute else "planned",
        "source": "google_trends",
        "provider": "existing_trendspy_provider",
        "country": geo,
        "language": None,  # RSS geography is not evidence of query language.
        "source_url": _source_url(geo),
        "site_property_required": False,
        "metric": "approximate_search_bucket_not_exact_google_search_volume",
        "feed_scope": "short_lived_recent_trend_labels_not_all_google_queries",
        "trend_labels_may_group_related_queries": True,
        "source_requests_performed": 0,
        "local_daily_request_cap": MAX_FREE_REQUESTS_PER_UTC_DAY,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "cache_hit": False,
        "network_performed": False,
        "trends": [],
        "records_observed": 0,
        "records_rejected": 0,
        "duplicates_removed": 0,
        "automatic_retry": False,
        "paid_services_used": False,
    }


def _read_cached(payload: Any, country: str) -> dict[str, Any] | None:
    if (not isinstance(payload, dict)
            or payload.get("mode") != MODE
            or payload.get("country") != country
            or payload.get("source_url") != _source_url(country)
            or payload.get("status") not in {
                "observed", "observed_partial", "observed_empty",
            }
            or not isinstance(payload.get("trends"), list)
            or len(payload["trends"]) > MAX_OUTPUT_ROWS):
        return None
    checked = []
    try:
        for item in payload["trends"]:
            if not isinstance(item, dict) or not isinstance(item.get("related_news"), list):
                return None
            signal = TrendSignal.model_validate(item["signal"])
            if (signal.source_id != "google_trending_now_rss"
                    or signal.source_url != _source_url(country)
                    or signal.country != country
                    or signal.metric_type != "google_trending_traffic_bucket"
                    or signal.coverage_status not in {"observed", "partial"}):
                return None
            news = _extract_news(item["related_news"])
            if len(news) != len(item["related_news"]):
                return None
            checked.append({"signal": signal.model_dump(mode="json"), "related_news": news})
    except (KeyError, TypeError, ValueError):
        return None
    return {
        **_output_base(country, execute=True),
        "status": payload["status"],
        "trends": checked,
        "records_observed": len(checked),
        "cache_hit": True,
        "network_performed": False,
        "observed_at": payload.get("observed_at"),
        "source_requests_performed": 0,
        "records_rejected": payload.get("records_rejected", 0),
        "duplicates_removed": payload.get("duplicates_removed", 0),
    }


def _normalize_feed(rows: Any, country: str, observed: datetime) -> dict[str, Any]:
    result = _output_base(country, execute=True)
    result["observed_at"] = observed.isoformat()
    if not isinstance(rows, (list, tuple)):
        result["status"] = "invalid_source_shape"
        return result
    if not rows:
        result["status"] = "observed_empty"
        return result

    seen: set[str] = set()
    processed: list[dict[str, Any]] = []
    rejected = 0
    duplicates = 0
    output_truncated = False
    for index, raw in enumerate(rows[:MAX_SOURCE_ROWS]):
        if not isinstance(raw, dict):
            rejected += 1
            continue
        term = _text(raw.get("keyword"), 180)
        bucket = _text(raw.get("volume"), 48)
        if not term or not bucket or _TRAFFIC.fullmatch(bucket) is None:
            rejected += 1
            continue
        key = term.casefold()
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        started = _started_at(raw.get("started"), observed)
        signal = TrendSignal(
            source_id="google_trending_now_rss",
            source_url=_source_url(country),
            observed_at=observed,
            published_at=started,
            country=country,
            language=None,
            raw_term=term,
            normalized_term=key,
            metric_type="google_trending_traffic_bucket",
            metric_unit="approximate_search_bucket",
            period=SignalPeriod(
                start_date=started.date() if started else observed.date(),
                end_date=observed.date(),
                granularity="point_in_time",
            ),
            value=None,
            value_label=bucket,
            sampling_scope=(
                "Google Trending Now public RSS for " + country
                + "; limited current feed, not all searches"
            ),
            coverage_status="observed",
            provenance=SignalProvenance(
                method="public_rss",
                sampling_basis="google_trending_now_grouped_search_label",
                is_observed_search_query=False,
            ),
        )
        processed.append({
            "signal": signal.model_dump(mode="json"),
            "related_news": _extract_news(raw.get("news")),
        })
        if len(processed) >= MAX_OUTPUT_ROWS:
            output_truncated = index + 1 < len(rows)
            break
    result["records_observed"] = len(processed)
    result["records_rejected"] = rejected
    result["duplicates_removed"] = duplicates
    truncated = len(rows) > MAX_SOURCE_ROWS or output_truncated
    result["status"] = (
        "invalid_source_shape" if not processed else
        "observed_partial" if truncated or rejected else "observed"
    )
    result["trends"] = processed
    return result


async def discover_trending_rss(
    country: str = "US", *, execute: bool = False,
    provider: Any = None, cache: BudgetCache | None = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """One opt-in provider operation or cached result. No retries, no browser."""
    country = _geo(country)
    if not isinstance(execute, bool):
        raise ValueError("execute must be a boolean")
    report = _output_base(country, execute=execute)
    if not execute:
        return report
    observed = observed_at if observed_at is not None else datetime.now(timezone.utc)
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("Observed time must include an explicit timezone")
    observed = observed.astimezone(timezone.utc)
    # TTL is minutes to avoid presenting yesterday's short-lived list as current.
    # The quota itself is daily and durable; no background polling is created.
    key = hashlib.sha256(("mjau_rss_v1_" + country).encode()).hexdigest()
    try:
        store = cache if cache is not None else BudgetCache()
        cached = store.cached(key)
        if cached is not None:
            valid = _read_cached(cached, country)
            if valid is not None:
                return valid
        if store.blocked(SOURCE_BUDGET_ID):
            return {**report, "status": "provider_cooldown"}
        store.reserve(SOURCE_BUDGET_ID, MAX_FREE_REQUESTS_PER_UTC_DAY)
    except DailyBudgetExceeded as exc:
        return {
            **report, "status": "local_daily_budget_exhausted",
            "quota_utc_day": exc.utc_day,
            "quota_used": exc.used, "quota_limit": exc.cap,
        }
    except (OSError, ValueError, sqlite3.Error):
        return {**report, "status": "local_budget_store_unavailable"}
    if provider is None:
        from mcp_trendpulse.providers import get_provider_set
        provider = get_provider_set().trends

    report["source_requests_performed"] = 1
    report["network_performed"] = True  # One bounded provider operation attempted.
    try:
        rows = await provider.get_trending_terms(geo=country, full_data=True)
    except ProviderRateLimitError:
        try:
            store.cool_down(SOURCE_BUDGET_ID, 300)
        except (OSError, ValueError, sqlite3.Error):
            pass
        return {**report, "status": "provider_rate_limited"}
    except ProviderTimeoutError:
        return {**report, "status": "provider_timeout"}
    except ProviderError:
        return {**report, "status": "provider_unavailable"}
    except (TypeError, ValueError):
        return {**report, "status": "invalid_source_shape"}
    except Exception:
        # No arbitrary provider exception strings: they can contain URL tokens.
        return {**report, "status": "provider_unavailable"}

    normalized = _normalize_feed(rows, country, observed)
    normalized["source_requests_performed"] = 1
    normalized["network_performed"] = True
    if normalized["status"] in {"observed", "observed_partial", "observed_empty"}:
        try:
            store.save(key, normalized, CACHE_TTL_SECONDS)
        except (OSError, ValueError, TypeError, sqlite3.Error):
            normalized["cache_write_failed"] = True
    return normalized


def format_rss_report(report: dict[str, Any]) -> str:
    """Compact source-labeled text; never reinterpret traffic buckets."""
    lines = [
        f"GOOGLE TRENDING NOW RSS | {report['country']} | {report['status']}",
        "Approximate traffic buckets, NOT precise search volume or buying demand.",
        "Source: " + report["source_url"],
        "Requests attempted: " + str(report["source_requests_performed"])
        + (" | cached snapshot" if report.get("cache_hit") else ""),
    ]
    if report.get("observed_at"):
        lines.append("Snapshot observed at (UTC): " + report["observed_at"])
    if report.get("status") == "planned":
        lines.append("No network request; use --execute for one bounded source operation.")
    elif report.get("status") not in {"observed", "observed_partial", "observed_empty"}:
        lines.append("Source unavailable, incomplete or quota-limited; trend presence UNKNOWN.")
    elif not report["trends"]:
        lines.append("Observed feed contained no trend rows; NOT proof of absent demand.")
    for item in report["trends"]:
        signal = item["signal"]
        lines.append(
            "- " + signal["raw_term"] + " | traffic: " + signal["value_label"]
            + " | started: " + (signal["published_at"] or "not supplied")
        )
        for entry in item["related_news"][:2]:
            lines.append("  News: " + entry["title"] + " | " + entry["url"])
    return "\n".join(lines)
