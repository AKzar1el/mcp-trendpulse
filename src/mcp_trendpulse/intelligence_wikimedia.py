"""M06: exact-article Wikimedia Analytics API pageviews, not market search volume.

Explicit opt-in uses the existing durable free-only quota store. The title is
checked via the matching wiki's read-only Action API before querying AQS.
No redirect/disambiguation auto-follow, no paid fallback or guessed zeros.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import quote

from mcp_trendpulse.intelligence_core import BudgetCache, DailyBudgetExceeded
from mcp_trendpulse.intelligence_signal import SignalPeriod, SignalProvenance, TrendSignal

MODE = "wikimedia_official_daily_pageviews"
BUDGET_ID = "wikimedia_pageviews"
UTC_DAILY_SOURCE_CAP = 4  # Each uncached command uses up to two API requests.
CACHE_TTL_SECONDS = 6 * 3600
MAX_RESPONSE_BYTES = 96 * 1024
MAX_DAYS = 30
MIN_DATE = date(2015, 7, 1)
_API_ROOT = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article"
_LANGUAGE = re.compile(r"[a-z]{2,3}(?:-[a-z0-9]{2,8})?")
_PROJECT = re.compile(r"([a-z]{2,3}(?:-[a-z0-9]{2,8})?)\.wikipedia\.org\Z")
_TIMESTAMP = re.compile(r"\d{8}00\Z")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_CACHED_STATUSES = frozenset(("observed", "observed_partial", "no_data"))
_EXACT_COUNT_MAX = (1 << 53) - 1
CONTACT_USER_AGENT = (
    "mcp-trendpulse/0.2.47 "
    "(https://github.com/AKzar1el/mcp-trendpulse) requests/2"
)


class ResponseTooLarge(RuntimeError):
    """The upstream response is larger than the safe per-request ceiling."""


def _project_name(value: str) -> tuple[str, str]:
    if not isinstance(value, str) or (match := _PROJECT.fullmatch(value)) is None:
        raise ValueError("Project must be an exact language.wikipedia.org hostname")
    return value, match.group(1)


def _title(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Article title must be a string")
    clean = value.replace("_", " ")
    if (
        clean != clean.strip() or not 2 <= len(clean) <= 120
        or clean.startswith(":") or ":" in clean or "://" in clean
        or "#" in clean or "?" in clean or "/" in clean or "%" in clean
        or any(ord(c) < 32 or ord(c) == 127 for c in clean)
    ):
        raise ValueError(
            "Provide an explicit, unambiguous article title; no URLs, namespaces or redirects"
        )
    return clean


def _date(value: str) -> date:
    if not isinstance(value, str) or _DATE.fullmatch(value) is None:
        raise ValueError("Date must use YYYY-MM-DD")
    return date.fromisoformat(value)


def _window(
    days: int, end_date: str | None, observed: datetime,
) -> dict[str, str | int]:
    if type(days) is not int or not 1 <= days <= MAX_DAYS:
        raise ValueError("Compare 1-30 daily samples in each equal-length period")
    latest_safe = observed.date() - timedelta(days=2)
    end = latest_safe if end_date is None else _date(end_date)
    start = end - timedelta(days=days - 1)
    prior_start = start - timedelta(days=days)
    if end > latest_safe or prior_start < MIN_DATE:
        raise ValueError("Dates require two complete, historical equal-length windows")
    return {
        "days_each": days,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "previous_start_date": prior_start.isoformat(),
        "previous_end_date": (start - timedelta(days=1)).isoformat(),
    }


def _urls(project: str, article: str, window: dict[str, str | int]) -> tuple[str, str]:
    start = str(window["previous_start_date"]).replace("-", "")
    end = str(window["end_date"]).replace("-", "")
    encoded = quote(article.replace(" ", "_"), safe="")
    metadata = f"https://{project}/w/api.php"
    views = f"{_API_ROOT}/{project}/all-access/user/{encoded}/daily/{start}/{end}"
    return metadata, views


def _cache_key(
    *, project: str, title: str, window: dict[str, str | int],
) -> str:
    content = json.dumps(
        ["mjau_m06_v1", project, title, window],
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return "mjau_wikimedia:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


def _metadata(body: Any, *, title: str) -> str:
    """Return a safe status: title metadata never becomes an auto-redirect."""
    if not isinstance(body, dict) or not isinstance(body.get("query"), dict):
        return "invalid_article_metadata"
    query = body["query"]
    if not isinstance(query.get("pages"), list) or len(query["pages"]) != 1:
        return "invalid_article_metadata"
    pages = query["pages"]
    if any(not isinstance(item, dict) for item in pages):
        return "invalid_article_metadata"
    page = pages[0]
    if query.get("redirects"):
        return "redirect_requires_canonical_title"
    if "missing" in page or "invalid" in page:
        return "article_not_found"
    if page.get("ns") != 0 or type(page.get("pageid")) is not int:
        return "invalid_article_metadata"
    reported_title = page.get("title")
    if not isinstance(reported_title, str) or reported_title.casefold() != title.casefold():
        return "canonical_title_mismatch"
    props = page.get("pageprops")
    if props is not None and not isinstance(props, dict):
        return "invalid_article_metadata"
    if isinstance(props, dict) and "disambiguation" in props:
        return "disambiguation_requires_article"
    return "verified_canonical_article"


def _count(value: Any) -> int | None:
    return value if type(value) is int and 0 <= value <= _EXACT_COUNT_MAX else None


def _views(
    body: Any, *, project: str, title: str, window: dict[str, str | int],
) -> dict[str, Any]:
    if not isinstance(body, dict) or not isinstance(body.get("items"), list):
        return {"status": "invalid_source_shape", "rows": [],
                "source_rows_received": 0, "source_rows_rejected": 0}
    items = body["items"]
    if len(items) > MAX_DAYS * 2:
        return {"status": "invalid_source_shape", "rows": [],
                "source_rows_received": len(items), "source_rows_rejected": len(items)}
    expected = set()
    from_date = _date(str(window["previous_start_date"]))
    until = _date(str(window["end_date"]))
    cursor = from_date
    while cursor <= until:
        expected.add(cursor.isoformat())
        cursor += timedelta(days=1)
    rows = []
    seen = set()
    rejected = 0
    for item in items:
        if not isinstance(item, dict):
            rejected += 1
            continue
        raw_time = item.get("timestamp")
        reported_title = item.get("article")
        project_name = item.get("project")
        # The API convention is en.wikipedia (without .org) in the result;
        # treat a wrong wiki/title/access/agent as source contamination.
        if (
            not isinstance(raw_time, str)
            or _TIMESTAMP.fullmatch(raw_time) is None
            or item.get("granularity") != "daily"
            or item.get("access") != "all-access"
            or item.get("agent") != "user"
            or project_name not in (project, project.removesuffix(".org"))
            or not isinstance(reported_title, str)
            or reported_title.replace("_", " ").casefold() != title.casefold()
        ):
            return {"status": "invalid_source_scope", "rows": [],
                    "source_rows_received": len(items),
                    "source_rows_rejected": len(items)}
        day = raw_time[:4] + "-" + raw_time[4:6] + "-" + raw_time[6:8]
        try:
            parsed = _date(day)
        except ValueError:
            rejected += 1
            continue
        count = _count(item.get("views"))
        if parsed.isoformat() not in expected or day in seen or count is None:
            rejected += 1
            continue
        seen.add(day)
        rows.append({"date": day, "views": count})

    rows.sort(key=lambda r: r["date"])
    missing = sorted(expected - seen)
    if not rows and items:
        status = "invalid_source_shape"
    elif not rows:
        status = "no_data"
    elif missing or rejected:
        status = "observed_partial"
    else:
        status = "observed"
    return {
        "status": status, "rows": rows, "source_rows_received": len(items),
        "source_rows_rejected": rejected, "missing_dates": missing,
    }


def _summarize(
    *, rows: list[dict[str, Any]], window: dict[str, str | int],
) -> dict[str, Any]:
    seen = {row["date"]: row["views"] for row in rows}
    days = int(window["days_each"])
    before = _date(str(window["previous_start_date"]))
    current = _date(str(window["start_date"]))
    previous_dates = [(before + timedelta(days=i)).isoformat() for i in range(days)]
    current_dates = [(current + timedelta(days=i)).isoformat() for i in range(days)]
    previous_values = [seen.get(d) for d in previous_dates]
    current_values = [seen.get(d) for d in current_dates]
    previous_total = sum(previous_values) if None not in previous_values else None
    current_total = sum(current_values) if None not in current_values else None
    growth = None
    if previous_total is not None and current_total is not None and previous_total > 0:
        growth = round((current_total - previous_total) / previous_total * 100, 2)
    return {
        "previous_window": {
            "start_date": str(window["previous_start_date"]),
            "end_date": str(window["previous_end_date"]),
            "days_expected": days, "days_observed": days - previous_values.count(None),
            "views_sum": previous_total,
        },
        "current_window": {
            "start_date": str(window["start_date"]),
            "end_date": str(window["end_date"]),
            "days_expected": days, "days_observed": days - current_values.count(None),
            "views_sum": current_total,
        },
        "change_percent_only_if_both_complete_and_prior_positive": growth,
    }


def _signals(
    *, rows: list[dict[str, Any]], project: str, language: str, title: str,
    observed: datetime, source_url: str,
) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        day = _date(row["date"])
        signal = TrendSignal(
            source_id=BUDGET_ID, source_url=source_url, observed_at=observed,
            country=None,  # Project's language != geographic origin of readers.
            language=language, raw_term=title, normalized_term=title.casefold(),
            metric_type="wikimedia_pageviews", metric_unit="pageviews",
            period=SignalPeriod(start_date=day, end_date=day, granularity="daily"),
            value=row["views"],
            sampling_scope=(
                f"Exact {project} article; all-access/user daily page views; "
                "redirects excluded; not unique readers or search demand"
            ),
            coverage_status="observed",
            provenance=SignalProvenance(
                method="official_api", sampling_basis="per_article_user_daily_pageviews",
                is_observed_search_query=False,
            ),
        )
        result.append(signal.model_dump(mode="json"))
    return result


def _cached(
    value: Any, *, project: str, title: str, window: dict[str, str | int],
    observed: datetime,
) -> tuple[dict[str, Any], datetime] | None:
    if not isinstance(value, dict) or any(
        value.get(k) != v for k, v in (
            ("project", project), ("article_title", title), ("window", window),
            ("article_verification", "verified_canonical_article"),
        )
    ):
        return None
    try:
        at = datetime.fromisoformat(value["observed_at"])
        if at.tzinfo is None or at.utcoffset() is None:
            return None
        at = at.astimezone(timezone.utc)
    except (TypeError, ValueError, KeyError):
        return None
    if at > observed or at < observed - timedelta(days=2):
        return None
    original = value.get("source_rows_received")
    rejected = value.get("source_rows_rejected")
    rows = value.get("rows")
    status = value.get("status")
    if (
        type(original) is not int or type(rejected) is not int
        or not 0 <= rejected <= original <= MAX_DAYS * 2
        or not isinstance(rows, list) or status not in _CACHED_STATUSES
    ):
        return None
    checked = []
    days = set()
    start, end = _date(str(window["previous_start_date"])), _date(str(window["end_date"]))
    for item in rows:
        if not isinstance(item, dict):
            return None
        try:
            dt = _date(item.get("date"))
        except (TypeError, ValueError):
            return None
        count = _count(item.get("views"))
        if not start <= dt <= end or count is None or dt in days:
            return None
        days.add(dt)
        checked.append({"date": dt.isoformat(), "views": count})
    if len(checked) + rejected > original:
        return None
    expected = int(window["days_each"]) * 2
    if (
        (status == "observed" and (len(checked) != expected or rejected))
        or (status == "observed_partial" and (not checked or len(checked) == expected and not rejected))
        or (status == "no_data" and (checked or original))
    ):
        return None
    checked.sort(key=lambda r: r["date"])
    all_dates = {(start + timedelta(days=i)).isoformat() for i in range(expected)}
    return {
        "status": status, "rows": checked,
        "source_rows_received": original, "source_rows_rejected": rejected,
        "missing_dates": sorted(all_dates - {x["date"] for x in checked}),
    }, at


def _http_get(url: str, params: dict[str, str] | None) -> tuple[int, Any]:
    """Strict fixed-host request; the URL/response never appears in exception logs."""
    import requests
    from urllib.parse import urlsplit

    parts = urlsplit(url)
    if (
        parts.scheme != "https" or parts.username or parts.password
        or parts.fragment or parts.port not in (None, 443)
        or not (
            parts.hostname == "wikimedia.org"
            and parts.path.startswith("/api/rest_v1/metrics/pageviews/per-article/")
            or parts.hostname and _PROJECT.fullmatch(parts.hostname)
            and parts.path == "/w/api.php"
        )
    ):
        raise ValueError("Wikimedia API destination refused")

    session = requests.Session()
    session.trust_env = False
    try:
        with session.get(
            url, params=params, stream=True, allow_redirects=False,
            timeout=(5, 12),
            headers={
                "Accept": "application/json",
                "User-Agent": CONTACT_USER_AGENT,
            },
        ) as response:
            status = response.status_code
            if status != 200 or "json" not in response.headers.get("Content-Type", "").lower():
                return status, None
            body = response.raw.read(MAX_RESPONSE_BYTES + 1, decode_content=True)
            if len(body) > MAX_RESPONSE_BYTES:
                raise ResponseTooLarge()
            try:
                return status, json.loads(body)
            except (UnicodeError, ValueError):
                return status, None
    finally:
        session.close()


def discover_pageviews(
    *, article_title: str, project: str = "en.wikipedia.org",
    days: int = 7, end_date: str | None = None, execute: bool = False,
    cache: Any = None,
    fetcher: Callable[[str, dict[str, str] | None], tuple[int, Any]] | None = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """One explicit article; two inclusive equal-length periods, no guessing."""
    project, language = _project_name(project)
    article_title = _title(article_title)
    if type(execute) is not bool:
        raise ValueError("Execute must be boolean")
    observed = observed_at or datetime.now(timezone.utc)
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("Observation timestamp must specify a timezone")
    observed = observed.astimezone(timezone.utc)
    window = _window(days, end_date, observed)
    meta_url, views_url = _urls(project, article_title, window)
    report: dict[str, Any] = {
        "mode": MODE, "status": "planned" if not execute else "unavailable",
        "source": BUDGET_ID, "source_url": views_url,
        "project": project, "language": language, "country": None,
        "article_title": article_title,
        "article_verification": "not_checked",
        "title_auto_redirects_followed": False,
        "article_title_ambiguity_resolved_automatically": False,
        "window": window, "observed_at": observed.isoformat(),
        "access": "all-access", "agent": "user", "granularity": "daily",
        "requests_attempted": 0, "network_performed": False, "cache_hit": False,
        "local_utc_daily_request_cap": UTC_DAILY_SOURCE_CAP,
        "max_provider_requests_per_invocation": 2,
        "source_rows_received": 0, "source_rows_rejected": 0,
        "missing_dates": [], "rows": [], "signals": [],
        "comparison": _summarize(rows=[], window=window),
        "zero_or_unloaded_not_assumed_from_missing": True,
        "country_of_readers_unknown": True, "search_volume_verified": False,
        "unique_visitors_verified": False, "paid_services_used": False,
    }
    if not execute:
        return report
    try:
        store = cache if cache is not None else BudgetCache()
        key = _cache_key(project=project, title=article_title, window=window)
        previous = store.cached(key)
        checked = _cached(
            previous, project=project, title=article_title,
            window=window, observed=observed,
        )
        if checked is not None:
            rows, when = checked
            report.update(rows)
            report["cache_hit"] = True
            report["article_verification"] = "verified_canonical_article"
            report["observed_at"] = when.isoformat()
            report["signals"] = _signals(
                rows=rows["rows"], project=project, language=language,
                title=article_title, observed=when, source_url=views_url,
            )
            report["comparison"] = _summarize(rows=rows["rows"], window=window)
            return report
        if store.blocked(BUDGET_ID):
            report["status"] = "provider_cooldown"
            return report
        # Reserve BOTH operations atomically before either is issued, even
        # across processes. No partial reservations, no quota bypass.
        store.reserve_many(BUDGET_ID, UTC_DAILY_SOURCE_CAP, 2)
    except DailyBudgetExceeded:
        report["status"] = "local_daily_budget_exhausted"
        return report
    except (OSError, TypeError, ValueError, sqlite3.Error):
        report["status"] = "local_budget_unavailable"
        return report

    do_get = fetcher if fetcher is not None else _http_get
    metadata_params = {
        "action": "query", "format": "json", "formatversion": "2",
        "redirects": "1", "prop": "pageprops", "titles": article_title,
        "maxlag": "5",
    }
    try:
        report["requests_attempted"] += 1
        report["network_performed"] = True
        http, source = do_get(meta_url, metadata_params)
        if http in {429, 503}:
            report["status"] = "provider_rate_limited"
            try:
                store.cool_down(BUDGET_ID, 300)
            except (OSError, ValueError, sqlite3.Error):
                pass
            return report
        if http != 200:
            report["status"] = "metadata_unavailable"
            return report
        title_status = _metadata(source, title=article_title)
        report["article_verification"] = title_status
        if title_status != "verified_canonical_article":
            report["status"] = title_status
            return report

        report["requests_attempted"] += 1
        status, payload = do_get(views_url, None)
        if status in {429, 503}:
            report["status"] = "provider_rate_limited"
            try:
                store.cool_down(BUDGET_ID, 300)
            except (OSError, ValueError, sqlite3.Error):
                pass
            return report
        if status == 404:
            report["status"] = "zero_or_not_loaded_unknown"
            return report
        if status != 200:
            report["status"] = "source_unavailable"
            return report
        parsed = _views(
            payload, project=project, title=article_title, window=window,
        )
    except ResponseTooLarge:
        report["status"] = "response_too_large"
        return report
    except Exception:
        # Upstream errors can embed request URLs. Never echo exception text.
        report["status"] = "source_unavailable"
        return report

    report.update(parsed)
    report["comparison"] = _summarize(rows=parsed["rows"], window=window)
    report["signals"] = _signals(
        rows=parsed["rows"], project=project, language=language,
        title=article_title, observed=observed, source_url=views_url,
    )
    if parsed["status"] in _CACHED_STATUSES:
        try:
            store.save(key, {
                "project": project, "article_title": article_title,
                "window": window, "article_verification": report["article_verification"],
                "observed_at": observed.isoformat(),
                **parsed,
            }, CACHE_TTL_SECONDS)
        except (OSError, TypeError, ValueError, sqlite3.Error):
            report["cache_write_failed"] = True
    return report


def format_pageviews(report: dict[str, Any]) -> str:
    lines = [
        f"WIKIMEDIA PAGEVIEWS | {report['project']} | {report['article_title']}",
        f"Source status: {report['status']} | canonical: {report['article_verification']}",
        f"Window: {report['window']['previous_start_date']} through "
        f"{report['window']['end_date']}; comparison: {report['window']['days_each']} days each",
        "User agents, all device access; article views are not people, "
        "searches or evidence of buying demand.",
        f"Requests attempted: {report['requests_attempted']}"
        + (" (cache hit)" if report["cache_hit"] else ""),
    ]
    for name in ("previous_window", "current_window"):
        period = report["comparison"][name]
        lines.append(
            f"{name}: observed {period['days_observed']}/"
            f"{period['days_expected']} days | "
            f"views sum: {period['views_sum'] if period['views_sum'] is not None else 'unknown'}"
        )
    change = report["comparison"]["change_percent_only_if_both_complete_and_prior_positive"]
    if change is not None:
        lines.append(f"Window-to-window view change: {change:+.2f}% (not search growth)")
    if report["missing_dates"]:
        lines.append(f"Unknown dates: {', '.join(report['missing_dates'])}")
    return "\n".join(lines)
