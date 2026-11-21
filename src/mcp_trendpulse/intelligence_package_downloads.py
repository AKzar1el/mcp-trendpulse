"""M09/M10: strictly bounded package-download observations, not users.

Official keyless npm downloads and publicly hosted PyPI Stats. One opt-in
request per package, UTC-day quotas and validated cached source evidence.
Never compare or sum npm and PyPI count series into a single demand score.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import quote, urlsplit

from mcp_trendpulse.intelligence_core import BudgetCache, DailyBudgetExceeded
from mcp_trendpulse.intelligence_signal import (
    SignalPeriod, SignalProvenance, TrendSignal,
)

SOURCE = {
    "npm": {
        "source_id": "npm_package_downloads",
        "host": "api.npmjs.org",
        "daily_cap": 5,
        "max_response_bytes": 128 * 1024,
    },
    "pypi": {
        "source_id": "pypi_package_downloads",
        "host": "pypistats.org",
        "daily_cap": 3,  # Volunteer-run source with IP rate limits.
        "max_response_bytes": 160 * 1024,
    },
}
MAX_EXACT_COUNT = 2**53 - 1
CACHE_TTL_SECONDS = 24 * 3600
_NPM_PACKAGE = re.compile(
    r"(?:@[a-z0-9][a-z0-9._~-]{0,99}/)?[a-z0-9][a-z0-9._~-]{0,119}\Z"
)
_PYPI_PACKAGE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}\Z")
_DAY = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_VALID_STATES = frozenset(("observed", "observed_partial", "no_data"))


class ResponseTooLarge(RuntimeError):
    """Provider response exceeded the safe single-request size."""


def _package(raw: str, ecosystem: str) -> str:
    if ecosystem not in SOURCE or not isinstance(raw, str):
        raise ValueError("Unknown package ecosystem or invalid package identifier")
    if ecosystem == "npm":
        if _NPM_PACKAGE.fullmatch(raw) is None or ".." in raw:
            raise ValueError("npm package must be a literal unscoped or @scope/name identifier")
        return raw
    if _PYPI_PACKAGE.fullmatch(raw) is None:
        raise ValueError("PyPI package must be a literal PEP 503 project identifier")
    # PyPI normalizes runs of [-_.] to '-' for distribution identity.
    return re.sub(r"[-_.]+", "-", raw).lower()


def _day(value: Any) -> date:
    if not isinstance(value, str) or _DAY.fullmatch(value) is None:
        raise ValueError("Provider date must be YYYY-MM-DD")
    return date.fromisoformat(value)


def _count(raw: Any) -> int | None:
    return raw if type(raw) is int and 0 <= raw <= MAX_EXACT_COUNT else None


def _url(package: str, ecosystem: str, days: int) -> str:
    if ecosystem == "npm":
        period = "last-week" if days == 7 else "last-month"
        return f"https://api.npmjs.org/downloads/range/{period}/{quote(package, safe='@')}"
    return (
        "https://pypistats.org/api/packages/"
        f"{quote(package, safe='')}/overall?mirrors=false"
    )


def _cache_key(package: str, ecosystem: str, days: int, observed: datetime) -> str:
    payload = json.dumps(
        ["mjau_packages_v1", ecosystem, package, days, observed.date().isoformat()],
        separators=(",", ":"), ensure_ascii=False,
    )
    return "mjau_pkg:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalise_rows(
    raw: list[Any], *, expected_start: date, expected_end: date,
    ecosystem: str,
) -> dict[str, Any]:
    expected = {
        (expected_start + timedelta(days=i)).isoformat()
        for i in range((expected_end - expected_start).days + 1)
    }
    accepted = []
    seen = set()
    rejected = 0
    for x in raw:
        if not isinstance(x, dict):
            rejected += 1
            continue
        if ecosystem == "pypi" and x.get("category") != "without_mirrors":
            return {"status": "invalid_source_scope", "source_rows_received": len(raw)}
        dt_raw = x.get("day") if ecosystem == "npm" else x.get("date")
        try:
            dt = _day(dt_raw)
        except ValueError:
            rejected += 1
            continue
        value = _count(x.get("downloads"))
        if (
            dt.isoformat() not in expected or value is None
            or dt.isoformat() in seen
        ):
            rejected += 1
            continue
        seen.add(dt.isoformat())
        accepted.append({"date": dt.isoformat(), "downloads": value})
    accepted.sort(key=lambda x: x["date"])
    missing = sorted(expected - seen)
    if not accepted and raw:
        status = "invalid_source_shape"
    elif not accepted:
        status = "no_data"
    elif missing or rejected:
        status = "observed_partial"
    else:
        status = "observed"
    return {
        "status": status,
        "rows": accepted,
        "missing_dates": missing,
        "source_rows_received": len(raw),
        "source_rows_rejected": rejected,
    }


def _npm_data(payload: Any, *, package: str, days: int, observed: datetime) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"status": "invalid_source_shape"}
    if payload.get("package") != package:
        return {"status": "invalid_source_scope"}
    try:
        start, end = _day(payload.get("start")), _day(payload.get("end"))
    except ValueError:
        return {"status": "invalid_source_shape"}
    if (end - start).days + 1 != days or end >= observed.date() or (
        observed.date() - end
    ).days > 14:
        return {"status": "invalid_source_window"}
    values = payload.get("downloads")
    if not isinstance(values, list) or len(values) > days:
        return {"status": "invalid_source_shape"}
    checked = _normalise_rows(
        values, expected_start=start, expected_end=end, ecosystem="npm",
    )
    if checked["status"] == "invalid_source_shape":
        return checked
    return {
        **checked, "window": {
            "start": start.isoformat(), "end": end.isoformat(),
            "days_expected": days,
        },
        "source_lag_days": (observed.date() - end).days,
    }


def _pypi_data(payload: Any, *, package: str, days: int, observed: datetime) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("type") != "overall_downloads":
        return {"status": "invalid_source_shape"}
    if not isinstance(payload.get("package"), str) or (
        re.sub(r"[-_.]+", "-", payload["package"]).lower() != package
    ):
        return {"status": "invalid_source_scope"}
    records = payload.get("data")
    if not isinstance(records, list) or len(records) > 185:
        return {"status": "invalid_source_shape"}
    if not records:
        return {"status": "no_data", "rows": [], "source_rows_received": 0,
                "source_rows_rejected": 0, "missing_dates": [], "window": None,
                "source_lag_days": None}
    dates = []
    for row in records:
        if not isinstance(row, dict) or row.get("category") != "without_mirrors":
            return {"status": "invalid_source_scope"}
        try:
            d = _day(row.get("date"))
        except ValueError:
            return {"status": "invalid_source_shape"}
        if d >= observed.date() or d < observed.date() - timedelta(days=185):
            return {"status": "invalid_source_window"}
        if _count(row.get("downloads")) is None:
            return {"status": "invalid_source_shape"}
        dates.append(d)
    end = max(dates)
    start = end - timedelta(days=days - 1)
    if start < observed.date() - timedelta(days=185):
        return {"status": "invalid_source_window"}
    selected = [row for row in records if start <= _day(row["date"]) <= end]
    checked = _normalise_rows(
        selected, expected_start=start, expected_end=end, ecosystem="pypi",
    )
    lag_days = (observed.date() - end).days
    if lag_days > 3 and checked["status"] == "observed":
        checked["status"] = "observed_partial"
    return {
        **checked,
        "window": {
            "start": start.isoformat(), "end": end.isoformat(),
            "days_expected": days,
        },
        "source_rows_all_history": len(records),
        "source_lag_days": lag_days,
    }


def _cache_valid(
    value: Any, *, package: str, ecosystem: str,
    days: int, observed: datetime,
) -> tuple[dict[str, Any], datetime] | None:
    if not isinstance(value, dict) or any(
        value.get(field) != expected for field, expected in (
            ("package", package), ("ecosystem", ecosystem), ("days", days),
            ("source", SOURCE[ecosystem]["source_id"]),
        )
    ):
        return None
    try:
        at = datetime.fromisoformat(value["observed_at"])
        if at.tzinfo is None or at.utcoffset() is None:
            return None
        at = at.astimezone(timezone.utc)
        if not at <= observed or at.date() != observed.date():
            return None
    except (TypeError, ValueError, KeyError):
        return None
    status = value.get("status")
    rows = value.get("rows")
    window = value.get("window")
    history_count = value.get("source_rows_all_history")
    if ecosystem == "pypi" and history_count is not None and (
        type(history_count) is not int or not 0 <= history_count <= 185
    ):
        return None
    received, rejected = value.get("source_rows_received"), value.get(
        "source_rows_rejected",
    )
    if (
        status not in _VALID_STATES or not isinstance(rows, list)
        or type(received) is not int or type(rejected) is not int
        or not 0 <= rejected <= received <= 185
        or (status == "no_data" and (rows or received))
    ):
        return None
    if status == "no_data":
        if ecosystem == "pypi":
            if window is not None:
                return None
            clean_window = None
            lag = None
        else:
            if not isinstance(window, dict) or window.get("days_expected") != days:
                return None
            try:
                start, end = _day(window["start"]), _day(window["end"])
            except (KeyError, ValueError):
                return None
            if ((end-start).days+1 != days or end >= observed.date()
                    or (observed.date()-end).days > 14):
                return None
            clean_window = {
                "start": start.isoformat(), "end": end.isoformat(),
                "days_expected": days,
            }
            lag = (observed.date()-end).days
        return {
            "status": "no_data", "rows": [], "window": clean_window,
            "source_rows_received": 0, "source_rows_rejected": 0,
            "missing_dates": [], "source_lag_days": lag,
            "source_rows_all_history": history_count,
        }, at
    if not isinstance(window, dict) or window.get("days_expected") != days:
        return None
    try:
        start = _day(window["start"])
        end = _day(window["end"])
    except (ValueError, KeyError):
        return None
    if (end-start).days + 1 != days or end >= observed.date() or (
        observed.date() - end
    ).days > 185:
        return None
    unique = set()
    validated = []
    for row in rows:
        if not isinstance(row, dict):
            return None
        try:
            dt = _day(row.get("date"))
        except ValueError:
            return None
        val = _count(row.get("downloads"))
        if dt in unique or not start <= dt <= end or val is None:
            return None
        unique.add(dt)
        validated.append({"date": dt.isoformat(), "downloads": val})
    if (
        not validated or len(validated) > days
        or len(validated)+rejected > received
        or (status == "observed" and (len(validated) != days or rejected))
        or (status == "observed_partial" and len(validated) == days
            and not rejected and not (ecosystem == "pypi" and (
                observed.date()-end).days > 3))
    ):
        return None
    validated.sort(key=lambda r: r["date"])
    dates = {
        (start + timedelta(days=i)).isoformat() for i in range(days)
    }
    result = {
        "status": status,
        "source_rows_all_history": history_count,
        "rows": validated, "window": {
            "start": start.isoformat(), "end": end.isoformat(),
            "days_expected": days,
        },
        "missing_dates": sorted(dates - {row["date"] for row in validated}),
        "source_rows_received": received, "source_rows_rejected": rejected,
        "source_lag_days": (observed.date() - end).days,
    }
    return result, at


def _http_get(url: str, ecosystem: str) -> tuple[int, Any]:
    """One bounded GET to an exact official host, never a user-supplied URL."""
    import requests

    parsed = urlsplit(url)
    host = SOURCE[ecosystem]["host"]
    if (
        parsed.scheme != "https" or parsed.hostname != host
        or parsed.username or parsed.password or parsed.fragment
        or parsed.port not in (None, 443)
        or (
            ecosystem == "npm" and (
                parsed.query or not parsed.path.startswith("/downloads/range/")
            )
        )
        or (
            ecosystem == "pypi" and (
                parsed.query != "mirrors=false"
                or not parsed.path.startswith("/api/packages/")
                or not parsed.path.endswith("/overall")
            )
        )
    ):
        raise ValueError("Unapproved package downloads endpoint")
    session = requests.Session()
    session.trust_env = False
    try:
        with session.get(
            url, stream=True, allow_redirects=False,
            timeout=(5, 12),
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    "mcp-trendpulse/0.2 "
                    "(https://github.com/AKzar1el/mcp-trendpulse)"
                ),
            },
        ) as response:
            status = response.status_code
            if status != 200 or "json" not in response.headers.get(
                "Content-Type", "",
            ).lower():
                return status, None
            body = response.raw.read(
                SOURCE[ecosystem]["max_response_bytes"] + 1,
                decode_content=True,
            )
            if len(body) > SOURCE[ecosystem]["max_response_bytes"]:
                raise ResponseTooLarge()
            try:
                return status, json.loads(body)
            except (UnicodeError, ValueError):
                return status, None
    finally:
        session.close()


def _signals(
    *, package: str, ecosystem: str, rows: list[dict[str, Any]],
    observed: datetime, source_url: str, status: str,
) -> list[dict[str, Any]]:
    cfg = SOURCE[ecosystem]
    return [
        TrendSignal(
            source_id=cfg["source_id"], source_url=source_url,
            observed_at=observed, country=None, language=None,
            raw_term=package, normalized_term=package,
            metric_type=cfg["source_id"], metric_unit="downloads",
            period=SignalPeriod(
                start_date=_day(row["date"]),
                end_date=_day(row["date"]),
                granularity="daily",
            ),
            value=row["downloads"],
            coverage_status=(
                "observed" if status == "observed" else "partial"
            ),
            sampling_scope=(
                ("npm registry tarball downloads; CI/bots/dependencies included"
                 if ecosystem == "npm" else
                 "PyPI Stats daily downloads excluding known mirrors")
                + "; not unique users or buyer demand"
            ),
            provenance=SignalProvenance(
                method="public_api" if ecosystem == "pypi" else "official_api",
                source_record_id=(
                    f"{hashlib.sha256(package.encode('utf-8')).hexdigest()[:24]}"
                    f":{row['date']}"
                ),
                sampling_basis=(
                    "single_package_daily_registry_downloads"
                    if ecosystem == "npm" else
                    "single_package_daily_pypi_stats_without_known_mirrors"
                ),
                is_observed_search_query=False,
            ),
        ).model_dump(mode="json")
        for row in rows
    ]


def discover_package_downloads(
    *, ecosystem: str, package: str, days: int = 7,
    execute: bool = False,
    cache: Any = None,
    fetcher: Callable[[str, str], tuple[int, Any]] | None = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Opt-in source history, distinct ecosystems, no customer-count inference."""
    package = _package(package, ecosystem)
    if type(days) is not int or days not in (7, 30):
        raise ValueError("Package history allows only 7 or 30 daily observations")
    if type(execute) is not bool:
        raise ValueError("Execute must be boolean")
    observed = observed_at or datetime.now(timezone.utc)
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("Observation date must specify timezone")
    observed = observed.astimezone(timezone.utc)
    cfg = SOURCE[ecosystem]
    url = _url(package, ecosystem, days)
    report: dict[str, Any] = {
        "mode": f"{ecosystem}_public_package_downloads",
        "source": cfg["source_id"], "source_url": url,
        "status": "planned" if not execute else "unavailable",
        "ecosystem": ecosystem, "package": package, "days": days,
        "observed_at": observed.isoformat(),
        "country": None, "language": None,
        "requests_attempted": 0, "network_performed": False,
        "cache_hit": False, "local_utc_daily_request_cap": cfg["daily_cap"],
        "source_rows_received": 0, "source_rows_rejected": 0,
        "source_rows_all_history": None,
        "source_lag_days": None, "window": None, "missing_dates": [],
        "rows": [], "signals": [], "downloads_sum_if_full_coverage": None,
        "mirror_handling": (
            "npm_counts_include_ci_bots_and_mirrors_unknown"
            if ecosystem == "npm" else
            "pypi_stats_excludes_known_mirrors"
        ),
        "unique_users_verified": False, "customer_demand_verified": False,
        "cross_ecosystem_counts_additive": False,
        "paid_services_used": False,
    }
    if not execute:
        return report
    try:
        store = cache if cache is not None else BudgetCache()
        key = _cache_key(package, ecosystem, days, observed)
        previous = _cache_valid(
            store.cached(key), package=package, ecosystem=ecosystem,
            days=days, observed=observed,
        )
        if previous is not None:
            parsed, saved_at = previous
            report.update(parsed)
            report["observed_at"] = saved_at.isoformat()
            report["cache_hit"] = True
            report["signals"] = _signals(
                package=package, ecosystem=ecosystem, rows=parsed["rows"],
                observed=saved_at, source_url=url, status=parsed["status"],
            )
            if parsed["status"] == "observed":
                report["downloads_sum_if_full_coverage"] = sum(
                    row["downloads"] for row in parsed["rows"]
                )
            return report
        if store.blocked(cfg["source_id"]):
            report["status"] = "provider_cooldown"
            return report
        store.reserve(cfg["source_id"], cfg["daily_cap"])
    except DailyBudgetExceeded:
        report["status"] = "local_daily_budget_exhausted"
        return report
    except (OSError, ValueError, TypeError, sqlite3.Error):
        report["status"] = "local_budget_unavailable"
        return report

    report["requests_attempted"] = 1
    report["network_performed"] = True
    try:
        http, payload = (fetcher or _http_get)(url, ecosystem)
        if http in (429, 503):
            report["status"] = "provider_rate_limited"
            try:
                store.cool_down(cfg["source_id"], 300)
            except (OSError, ValueError, TypeError, sqlite3.Error):
                pass
            return report
        if http == 404:
            report["status"] = "package_not_found_or_data_unavailable"
            return report
        if http != 200:
            report["status"] = "provider_unavailable"
            return report
        parsed = (
            _npm_data(payload, package=package, days=days, observed=observed)
            if ecosystem == "npm" else
            _pypi_data(payload, package=package, days=days, observed=observed)
        )
    except ResponseTooLarge:
        report["status"] = "response_too_large"
        return report
    except Exception:
        report["status"] = "provider_unavailable"
        return report
    report.update(parsed)
    if parsed["status"] in _VALID_STATES:
        report["signals"] = _signals(
            package=package, ecosystem=ecosystem, rows=parsed["rows"],
            observed=observed, source_url=url, status=parsed["status"],
        )
        if parsed["status"] == "observed":
            report["downloads_sum_if_full_coverage"] = sum(
                row["downloads"] for row in parsed["rows"]
            )
        compact = {
            "package": package, "ecosystem": ecosystem,
            "days": days, "source": cfg["source_id"],
            "status": parsed["status"],
            "observed_at": observed.isoformat(),
            "rows": parsed["rows"], "window": parsed["window"],
            "source_rows_received": parsed["source_rows_received"],
            "source_rows_rejected": parsed["source_rows_rejected"],
            "source_rows_all_history": parsed.get("source_rows_all_history"),
        }
        try:
            store.save(key, compact, CACHE_TTL_SECONDS)
        except (OSError, ValueError, TypeError, sqlite3.Error):
            report["cache_write_failed"] = True
    return report


def format_package_downloads(report: dict[str, Any]) -> str:
    lines = [
        f"{report['ecosystem'].upper()} PACKAGE DOWNLOADS | {report['package']}",
        f"Status: {report['status']}; "
        f"provider requests: {report['requests_attempted']}"
        + (" (validated cache hit)" if report["cache_hit"] else ""),
        "Counts are downloads, not distinct users, human installs or buyers.",
    ]
    for row in report["rows"]:
        lines.append(f"{row['date']}: {row['downloads']} downloads")
    if report["missing_dates"]:
        lines.append(
            f"Missing source dates (not zero): {', '.join(report['missing_dates'])}"
        )
    return "\n".join(lines)
