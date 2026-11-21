"""M05: opt-in market-wide Bing Webmaster keyword research over REST/JSON.

Not Bing Search Performance, not Google search volume, and not a paid API.
The API key belongs in the operator's secure environment/credential store.
Bing's documented JSON GET protocol requires apikey in request parameters;
this module never serializes, logs or returns authenticated request URLs.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from mcp_trendpulse.intelligence_core import BudgetCache, DailyBudgetExceeded
from mcp_trendpulse.intelligence_settings import resolved_environment
from mcp_trendpulse.intelligence_signal import (
    SignalPeriod,
    SignalProvenance,
    TrendSignal,
)

MODE = "bing_official_market_keyword_research"
BING_BUDGET_ID = "bing_webmaster_keyword_research"
UTC_DAILY_BING_CAP = 3
CACHE_TTL_SECONDS = 3 * 3600
MAX_ROWS = 20
MAX_PROVIDER_ROWS = 180
MAX_RESPONSE_BYTES = 128 * 1024

ENDPOINTS = {
    "stats": "https://ssl.bing.com/webmaster/api.svc/json/GetKeywordStats",
    "related": "https://ssl.bing.com/webmaster/api.svc/json/GetRelatedKeywords",
}
_COUNTRY = re.compile(r"[A-Z]{2}\Z")
_LANGUAGE = re.compile(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8}){0,2}\Z")
_DOTNET_TICKS = re.compile(r"/Date\((\d{12,13})([+-]\d{4})?\)/\Z")
_CACHE_STATUSES = frozenset(("observed", "observed_partial", "no_data"))
# TrendSignal serializes numeric values as IEEE-754 doubles. Do not promote
# provider integers beyond the exactly representable range as exact counts.
_COUNT_MAX = (1 << 53) - 1
_SOURCE_SCOPE = "bing_search_keyword_research_not_site_performance"
_KINDS = frozenset(ENDPOINTS)


class ResponseTooLarge(RuntimeError):
    """Provider response crossed the bounded byte limit."""


def _query(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Bing keyword query must be a text string")
    trimmed = " ".join(value.split())
    if (not 2 <= len(trimmed) <= 90 or "://" in trimmed
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in value)):
        raise ValueError("Query must be 2–90 printable characters, not a URL")
    return trimmed


def _country(value: str) -> str:
    if not isinstance(value, str) or not _COUNTRY.fullmatch(value):
        raise ValueError("Bing country must be uppercase two-letter ISO code")
    return value


def _language(value: str) -> str:
    if (not isinstance(value, str) or not _LANGUAGE.fullmatch(value)
            or len(value) > 18):
        raise ValueError("Bing language must be an IETF tag such as en-US or sl-SI")
    return value


def _period(
    kind: str, start_date: str | None, end_date: str | None, today: date,
) -> tuple[str | None, str | None]:
    if kind == "stats":
        if start_date is not None or end_date is not None:
            raise ValueError("GetKeywordStats has no date-range request parameters")
        return None, None
    if kind != "related":
        raise ValueError("Bing method must be stats or related")
    end = today if end_date is None else _date(end_date)
    start = end - timedelta(days=29) if start_date is None else _date(start_date)
    days = (end - start).days + 1
    if end > today or not 1 <= days <= 90 or start < today - timedelta(days=365):
        raise ValueError("Related keyword window must be 1–90 days, current/past year")
    return start.isoformat(), end.isoformat()


def _date(value: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Dates must use YYYY-MM-DD")
    return date.fromisoformat(value)


def _count(value: Any) -> int | None:
    return value if type(value) is int and 0 <= value <= _COUNT_MAX else None


def _term(value: Any) -> str | None:
    if (not isinstance(value, str) or not 2 <= len(value) <= 120
            or not value.strip() or value.strip() != value
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in value)):
        return None
    return value


def _bing_date(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    found = _DOTNET_TICKS.fullmatch(value)
    if found is None:
        return None
    try:
        milliseconds = int(found.group(1))
        when = datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)
        offset = found.group(2)
        if offset is not None:
            hours, minutes = int(offset[1:3]), int(offset[3:])
            if hours > 14 or minutes > 59 or (hours == 14 and minutes):
                return None
            direction = 1 if offset[0] == "+" else -1
            when = when.astimezone(
                timezone(direction * timedelta(hours=hours, minutes=minutes))
            )
        day = when.date()
        if not date(2000, 1, 1) <= day <= datetime.now(timezone.utc).date():
            return None
        return day.isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def _parsed_rows(
    body: Any, *, kind: str, query: str, limit: int,
) -> dict[str, Any]:
    if not isinstance(body, dict) or not isinstance(body.get("d"), list):
        return {"status": "invalid_source_shape", "records": [],
                "source_rows_received": 0, "source_rows_omitted": 0,
                "rows_truncated": False}
    raw = body["d"]
    if not raw:
        return {"status": "no_data", "records": [],
                "source_rows_received": 0, "source_rows_omitted": 0,
                "rows_truncated": False}

    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for item in raw[:MAX_PROVIDER_ROWS]:
        if not isinstance(item, dict):
            continue
        term = _term(item.get("Query"))
        exact = _count(item.get("Impressions"))
        broad = _count(item.get("BroadImpressions"))
        if term is None or exact is None or broad is None:
            continue
        if kind == "stats":
            if term.casefold() != query.casefold():
                continue
            period = _bing_date(item.get("Date"))
            if period is None or period in seen:
                continue
            seen.add(period)
            rows.append({"query": term, "date": period,
                         "exact_impressions": exact, "broad_impressions": broad})
        else:
            normalized = term.casefold()
            if normalized in seen:
                continue
            seen.add(normalized)
            rows.append({"query": term,
                         "exact_impressions": exact, "broad_impressions": broad})

    if kind == "stats":
        rows.sort(key=lambda row: row["date"])
        kept = rows[-limit:]
    else:
        rows.sort(key=lambda row: (-row["exact_impressions"], row["query"].casefold()))
        kept = rows[:limit]

    omitted = len(raw) - len(kept)
    if not kept:
        status = "invalid_source_shape"
    elif omitted:
        status = "observed_partial"
    else:
        status = "observed"
    return {
        "status": status,
        "records": kept,
        "source_rows_received": len(raw),
        "source_rows_omitted": omitted,
        "rows_truncated": len(rows) > limit or len(raw) > MAX_PROVIDER_ROWS,
    }


def _cache_key(
    *, kind: str, query: str, country: str, language: str,
    start_date: str | None, end_date: str | None,
    limit: int, api_key: str,
) -> str:
    # A one-way account discriminator prevents reusing one user's cached
    # keyword data when the operator changes the Bing Webmaster credentials.
    fingerprint = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    basis = json.dumps([
        "mjau_m05_v1", kind, query.casefold(), country, language,
        start_date, end_date, limit, fingerprint,
    ], separators=(",", ":"), ensure_ascii=False)
    return "mjau_bing:" + hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _cached_rows(
    value: Any, *, kind: str, query: str, country: str, language: str,
    start_date: str | None, end_date: str | None, limit: int,
    observed: datetime,
) -> tuple[dict[str, Any], datetime] | None:
    if not isinstance(value, dict) or any(value.get(key) != expected for key, expected in (
        ("kind", kind), ("query", query), ("country", country),
        ("language", language), ("start_date", start_date),
        ("end_date", end_date),
    )):
        return None
    rows = value.get("records")
    total = value.get("source_rows_received")
    omitted = value.get("source_rows_omitted")
    truncated = value.get("rows_truncated")
    status = value.get("status")
    if (not isinstance(rows, list) or len(rows) > limit
            or type(total) is not int or type(omitted) is not int
            or type(truncated) is not bool or total < 0 or omitted < 0
            or total != len(rows) + omitted or status not in _CACHE_STATUSES):
        return None
    try:
        recorded = datetime.fromisoformat(value["observed_at"])
        if recorded.tzinfo is None or recorded.utcoffset() is None:
            return None
        recorded = recorded.astimezone(timezone.utc)
    except (TypeError, ValueError, KeyError):
        return None
    if recorded > observed or recorded < observed - timedelta(days=2):
        return None
    checked: list[dict[str, Any]] = []
    unique: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            return None
        t = _term(row.get("query"))
        exact, broad = _count(row.get("exact_impressions")), _count(row.get("broad_impressions"))
        if t is None or exact is None or broad is None:
            return None
        if kind == "stats":
            d = row.get("date")
            try:
                actual = _date(d)
            except (TypeError, ValueError):
                return None
            if actual > observed.date() or t.casefold() != query.casefold():
                return None
            key = d
            checked.append({"query": t, "date": d,
                            "exact_impressions": exact, "broad_impressions": broad})
        else:
            key = t.casefold()
            checked.append({"query": t,
                            "exact_impressions": exact, "broad_impressions": broad})
        if key in unique:
            return None
        unique.add(key)
    if (status == "no_data" and (total != 0 or checked)
            or status == "observed" and (omitted or not checked or truncated)
            or status == "observed_partial" and (not checked or not omitted)):
        return None
    # Strictly reconstruct cached output from known fields. Never echo
    # unknown SQLite JSON keys, even if a cache file has been tampered with.
    return {
        "status": status, "records": checked, "source_rows_received": total,
        "source_rows_omitted": omitted, "rows_truncated": truncated,
    }, recorded


def _to_signals(
    records: list[dict[str, Any]], *, query: str, country: str,
    language: str, observed: datetime,
) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for row in records:
        day = date.fromisoformat(row["date"])
        for variant in ("exact", "broad"):
            signal = TrendSignal(
                source_id=BING_BUDGET_ID, source_url=ENDPOINTS["stats"],
                observed_at=observed, country=country, language=language,
                raw_term=row["query"], normalized_term=query.casefold(),
                metric_type="bing_keyword_impressions", metric_unit="impressions",
                period=SignalPeriod(
                    start_date=day, end_date=day, granularity="weekly",
                ),
                value=row[f"{variant}_impressions"],
                sampling_scope=(
                    f"Bing market-wide {variant}-match weekly keyword impressions"
                    f" for {country}/{language}; not site performance or Google volume"
                ),
                coverage_status="observed",
                provenance=SignalProvenance(
                    method="official_api",
                    sampling_basis=f"bing_weekly_{variant}_query_impressions",
                    is_observed_search_query=False,
                ),
            )
            signals.append(signal.model_dump(mode="json"))
    return signals


def _fetch_json(endpoint: str, params: dict[str, str]) -> tuple[int, Any]:
    """Single fixed-host TLS request; no redirects, proxies, or raw URL logs."""
    import requests

    session = requests.Session()
    session.trust_env = False
    try:
        with session.get(
            endpoint, params=params, timeout=(5, 12), stream=True,
            allow_redirects=False,
            headers={
                "Accept": "application/json",
                "User-Agent": "mcp-trendpulse/0.2 M05 read-only Bing market research",
            },
        ) as response:
            code = response.status_code
            if code != 200:
                return code, None
            if "json" not in response.headers.get("Content-Type", "").lower():
                return code, None
            raw = response.raw.read(MAX_RESPONSE_BYTES + 1, decode_content=True)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ResponseTooLarge()
            try:
                return code, json.loads(raw)
            except (UnicodeError, ValueError):
                return code, None
    finally:
        session.close()


def discover_bing_keyword(
    *, query: str, country: str, language: str,
    kind: str = "stats", start_date: str | None = None,
    end_date: str | None = None, limit: int = MAX_ROWS,
    execute: bool = False, api_key: str | None = None,
    cache: Any = None,
    fetcher: Callable[[str, dict[str, str]], tuple[int, Any]] | None = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """M05: per-invocation opt-in to exactly one REST keyword source request."""
    query = _query(query)
    country = _country(country)
    language = _language(language)
    if kind not in _KINDS:
        raise ValueError("Bing keyword research accepts stats or related only")
    if type(limit) is not int or not 1 <= limit <= MAX_ROWS:
        raise ValueError("Bing keyword output limit is 1..20")
    if type(execute) is not bool:
        raise ValueError("execute must be a boolean")
    observed = observed_at or datetime.now(timezone.utc)
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("Observation timestamp must have a timezone")
    observed = observed.astimezone(timezone.utc)
    start_date, end_date = _period(
        kind, start_date, end_date, observed.date(),
    )
    report: dict[str, Any] = {
        "mode": MODE, "source": BING_BUDGET_ID,
        "source_url": ENDPOINTS[kind],  # Never include apikey or user parameters.
        "source_is_official": True, "status": "planned" if not execute else "unavailable",
        "kind": kind, "query": query, "country": country, "language": language,
        "market_scope": _SOURCE_SCOPE,
        "site_property_required_for_keyword_query": False,
        "site_url_parameter_sent": False,
        "account_may_require_verified_site_to_issue_key": True,
        "provider_api_is_bing_not_google": True,
        "google_search_volume_verified": False,
        "website_impressions_included": False,
        "paid_services_used": False,
        "period": (
            {"start_date": start_date, "end_date": end_date,
             "granularity": "selected_period_aggregate"}
            if kind == "related" else
            {"granularity": "source_reported_weekly_history", "date_filter_available": False}
        ),
        "observed_at": observed.isoformat(),
        "requests_attempted": 0, "network_performed": False, "cache_hit": False,
        "local_utc_daily_request_cap": UTC_DAILY_BING_CAP,
        "provider_requests_per_invocation_max": 1,
        "source_rows_received": 0, "source_rows_omitted": 0,
        "rows_truncated": False,
        "records": [], "signals": [],
        "metric_note": (
            "Bing market-wide keyword research impression counts, "
            "exact-match vs broad-match; not literal searches, "
            "site clicks, Google volume, competition or paying demand"
        ),
    }
    if not execute:
        return report
    if api_key is None:
        try:
            api_key = resolved_environment(provider="bing_webmaster").get("BING_WEBMASTER_API_KEY")
        except (OSError, ValueError):
            api_key = None
    if (not isinstance(api_key, str) or not 8 <= len(api_key) <= 256
            or any(ord(c) < 33 or ord(c) > 126 for c in api_key)):
        report["status"] = "no_bing_credentials"
        return report

    try:
        store = cache if cache is not None else BudgetCache()
        key = _cache_key(
            kind=kind, query=query, country=country, language=language,
            start_date=start_date, end_date=end_date, limit=limit, api_key=api_key,
        )
        old = store.cached(key)
        valid = _cached_rows(
            old, kind=kind, query=query, country=country, language=language,
            start_date=start_date, end_date=end_date, limit=limit, observed=observed,
        )
        if valid is not None:
            result, cached_observed = valid
            report.update(result)
            report["observed_at"] = cached_observed.isoformat()
            report["cache_hit"] = True
            if kind == "stats":
                report["signals"] = _to_signals(
                    result["records"], query=query, country=country,
                    language=language, observed=cached_observed,
                )
            return report
        if store.blocked(BING_BUDGET_ID):
            report["status"] = "provider_cooldown"
            return report
        store.reserve(BING_BUDGET_ID, UTC_DAILY_BING_CAP)
    except DailyBudgetExceeded:
        report["status"] = "local_daily_budget_exhausted"
        return report
    except (OSError, TypeError, ValueError, sqlite3.Error):
        report["status"] = "local_budget_unavailable"
        return report

    params = {"apikey": api_key, "q": query,
              "country": country.lower(), "language": language}
    if kind == "related":
        params["startDate"] = start_date  # type: ignore[assignment]
        params["endDate"] = end_date  # type: ignore[assignment]
    report["requests_attempted"] = 1
    report["network_performed"] = True
    try:
        http_status, value = (fetcher or _fetch_json)(ENDPOINTS[kind], params)
        if http_status in {401, 403}:
            report["status"] = "authentication_required"
            return report
        if http_status in {429, 503}:
            report["status"] = "provider_rate_limited"
            try:
                store.cool_down(BING_BUDGET_ID, 300)
            except (OSError, TypeError, ValueError, sqlite3.Error):
                pass
            return report
        if http_status != 200:
            report["status"] = "provider_unavailable"
            return report
        parsed = _parsed_rows(value, kind=kind, query=query, limit=limit)
    except ResponseTooLarge:
        report["status"] = "response_too_large"
        return report
    except Exception:
        # Requests exceptions may contain authenticated URLs. Never copy any
        # provider exception message or repr into reports, logs or CLI errors.
        report["status"] = "provider_unavailable"
        return report

    report.update(parsed)
    if kind == "stats" and parsed["status"] in {"observed", "observed_partial"}:
        report["signals"] = _to_signals(
            parsed["records"], query=query, country=country,
            language=language, observed=observed,
        )
    if parsed["status"] in _CACHE_STATUSES:
        safe = {
            "kind": kind, "query": query, "country": country,
            "language": language, "start_date": start_date,
            "end_date": end_date, "observed_at": observed.isoformat(),
            **parsed,
        }
        try:
            store.save(key, safe, CACHE_TTL_SECONDS)
        except (OSError, TypeError, ValueError, sqlite3.Error):
            report["cache_write_failed"] = True
    return report


def format_bing_report(report: dict[str, Any]) -> str:
    lines = [
        f"BING KEYWORD RESEARCH | {report['query']} | "
        f"{report['country']} {report['language']} | {report['status']}",
        "Official Bing market-wide keyword research, not site traffic or Google volume.",
        "Exact and broad match are distinct impression measures, not search counts.",
        f"Daily source budget: {report['local_utc_daily_request_cap']} "
        f"| network calls: {report['requests_attempted']}"
        + (" (cache hit)" if report["cache_hit"] else ""),
    ]
    for item in report["records"]:
        when = f" {item['date']}" if "date" in item else ""
        lines.append(
            f"{item['query']}{when}: exact={item['exact_impressions']} "
            f"broad={item['broad_impressions']}"
        )
    if report["source_rows_omitted"]:
        lines.append(f"Source rows omitted: {report['source_rows_omitted']}")
    return "\n".join(lines)
