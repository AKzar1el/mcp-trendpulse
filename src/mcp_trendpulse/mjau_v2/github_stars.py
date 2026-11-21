"""A02: bounded, privacy-safe GitHub repository star history (proof only).

No individual stargazers are fetched, no user data are retained. GitHub's
history reports stars that remain active now, *not* original unstar events.
Provider week/day boundaries are not guaranteed UTC; daily slots remain
unlabeled to avoid inventing geographic/UTC date semantics.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Callable

SOURCE = "github_privacy_safe_star_history"
API = "https://api.github.com"
VERSION = "2026-03-10"
CAP = 4
TTL_SECONDS = 12 * 3600
MAX_RESPONSE_BYTES = 96 * 1024
MAX_PAGE = 12
_OWNER = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_REPO = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


class SourceTooLarge(ValueError):
    """The provider exceeded the per-request safety ceiling."""


def _identifier(owner: Any, repo: Any) -> tuple[str, str]:
    if not isinstance(owner, str) or not _OWNER.fullmatch(owner):
        raise ValueError("GitHub repository owner must be a bounded ASCII name")
    if (not isinstance(repo, str) or not _REPO.fullmatch(repo)
            or repo in {".", ".."} or repo.endswith(".git")
            or ".." in repo):
        raise ValueError("GitHub repository must be a bounded name without path syntax")
    return owner, repo


def _request_url(owner: str, repo: str) -> str:
    return f"{API}/repos/{owner}/{repo}/stargazers/history"


def _weekly_rows(payload: Any, limit: int, now: datetime) -> dict[str, Any]:
    if not isinstance(payload, list) or len(payload) > limit:
        return {"status": "invalid_source_shape", "weeks": []}
    weeks: list[dict[str, Any]] = []
    prev: int | None = None
    try:
        for obj in payload:
            if not isinstance(obj, dict):
                raise ValueError("row")
            epoch, total, days = obj.get("week"), obj.get("total"), obj.get("days")
            if (type(epoch) is not int or epoch < 1199145600
                    or epoch > int(now.timestamp()) + 7 * 86400
                    or type(total) is not int or not 0 <= total <= 2_000_000_000
                    or not isinstance(days, list) or len(days) != 7
                    or any(type(d) is not int or not 0 <= d <= 2_000_000_000 for d in days)
                    or sum(days) != total):
                raise ValueError("row")
            if prev is not None and not 6 * 86400 <= prev - epoch <= 8 * 86400:
                raise ValueError("noncontiguous-or-misordered-week")
            weeks.append({"week_start_provider_epoch": epoch, "weekly_active_star_events": total,
                          "provider_day_slots_sun_to_sat": list(days)})
            prev = epoch
    except (ValueError, OverflowError):
        return {"status": "invalid_source_shape", "weeks": []}
    return {
        "status": "no_data" if not weeks else "observed_partial",
        "weeks": weeks,
        "returned_week_count": len(weeks),
        "unit": "stars_remaining_active_today_grouped_by_original_star_date",
        "provider_week_day_timezone": "not_guaranteed_utc",
        "scope": "one_page_newest_first_not_complete_repo_lifetime",
        "has_historical_unstar_events": False,
        "is_traffic_users_downloads_or_revenue": False,
    }


def _compare(weeks: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    """Two four-week windows after a conservative two-week recency exclusion.

    Counts represent the present-day cohort of stars attributed to old
    weekly buckets; changing unstars may alter later snapshots retroactively.
    """
    default = {"status": "insufficient_eligible_history", "recent_4wk": None,
               "previous_4wk": None, "percent_change": None,
               "excludes_two_newest_provider_weeks": True,
               "is_forecast_or_inferred_actual_historical_interest": False}
    if len(weeks) < 10 or now.timestamp() - weeks[2]["week_start_provider_epoch"] < 14 * 86400:
        return default
    recent = sum(w["weekly_active_star_events"] for w in weeks[2:6])
    previous = sum(w["weekly_active_star_events"] for w in weeks[6:10])
    return {**default, "status": "descriptive_cohort_window_comparison",
            "recent_4wk": recent, "previous_4wk": previous,
            "percent_change": round((recent - previous) * 100 / previous, 2)
            if previous > 0 else None}


def _fetch(url: str, params: dict[str, str]) -> tuple[int, Any]:
    """Single keyless fixed-origin request with no proxy or redirects."""
    import requests

    if (not re.fullmatch(r"https://api\.github\.com/repos/[A-Za-z0-9-]+/[A-Za-z0-9_.-]+/stargazers/history", url)
            or set(params) != {"per_page", "page"} or params["page"] != "1"
            or not params["per_page"].isdigit() or not 1 <= int(params["per_page"]) <= MAX_PAGE):
        raise ValueError("Unsafe GitHub star-history request")
    session = requests.Session()
    session.trust_env = False
    try:
        with session.get(
            url, params=params, allow_redirects=False, timeout=(4, 10), stream=True,
            headers={"Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": VERSION,
                     "User-Agent": "mcp-trendpulse/0.2 (source-attributed research; no user profiles)"},
        ) as response:
            if response.status_code != 200 or "json" not in response.headers.get("Content-Type", "").lower():
                return response.status_code, None
            raw = response.raw.read(MAX_RESPONSE_BYTES + 1, decode_content=True)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise SourceTooLarge("GitHub response exceeds safety cap")
            try:
                return 200, json.loads(raw)
            except (UnicodeError, ValueError):
                return 200, None
    finally:
        session.close()


def _key(owner: str, repo: str, limit: int) -> str:
    return "mjau_v2_github_stars_" + hashlib.sha256(json.dumps(
        [SOURCE, owner.lower(), repo.lower(), limit, 1, VERSION],
    ).encode()).hexdigest()


def github_star_history(
    *, owner: str, repo: str, limit: int = 10, execute: bool = False,
    cache: Any = None,
    fetcher: Callable[[str, dict[str, str]], tuple[int, Any]] | None = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    owner, repo = _identifier(owner, repo)
    if type(limit) is not int or not 1 <= limit <= MAX_PAGE:
        raise ValueError("Star-history page size must be 1..12")
    if type(execute) is not bool:
        raise ValueError("Explicit execute boolean required")
    observed = observed_at or datetime.now(timezone.utc)
    if not isinstance(observed, datetime) or observed.utcoffset() is None:
        raise ValueError("Timezone-aware observation required")
    observed = observed.astimezone(timezone.utc)
    url = _request_url(owner, repo)
    params = {"per_page": str(limit), "page": "1"}
    report: dict[str, Any] = {
        "status": "planned", "source": SOURCE, "source_url": url,
        "repo": f"{owner}/{repo}", "limit": limit, "page": 1,
        "observed_at": observed.isoformat(), "requests_attempted": 0,
        "cache_hit": False, "network_performed": False,
        "weeks": [], "comparison": _compare([], observed),
        "local_daily_request_cap": CAP, "complete_repo_history": False,
        "star_count_equals_user_count": False, "paid_api_used": False,
        "individual_stargazer_data_collected": False,
    }
    if not execute:
        return report
    try:
        if cache is None:
            from mcp_trendpulse.intelligence_core import BudgetCache
            cache = BudgetCache()
        key = _key(owner, repo, limit)
        saved = cache.cached(key)
        if (isinstance(saved, dict) and saved.get("source") == SOURCE
                and saved.get("repo", "").lower() == report["repo"].lower()
                and saved.get("limit") == limit and isinstance(saved.get("observed_at"), str)):
            try:
                stamp = datetime.fromisoformat(saved["observed_at"])
                if stamp.utcoffset() is not None and 0 <= (observed - stamp).total_seconds() <= TTL_SECONDS:
                    valid = _weekly_rows(saved.get("source_rows"), limit, observed)
                    if valid["status"] in {"observed_partial", "no_data"}:
                        report.update(valid)
                        report["observed_at"] = stamp.astimezone(timezone.utc).isoformat()
                        report["comparison"] = _compare(valid["weeks"], observed)
                        report["cache_hit"] = True
                        return report
            except (ValueError, TypeError):
                pass
        if cache.blocked(SOURCE):
            report.update(status="unavailable", reason="provider_cooldown")
            return report
        cache.reserve(SOURCE, CAP, guard_cooldown=True)
        report["requests_attempted"] = 1
        status, payload = (fetcher or _fetch)(url, params)
        report["network_performed"] = True
        if status in (429, 503):
            cache.cool_down(SOURCE, seconds=120)
            report.update(status="unavailable", reason=f"http_{status}")
            return report
        if status != 200:
            report.update(status="unavailable", reason="provider_response_error")
            return report
        valid = _weekly_rows(payload, limit, observed)
        report.update(valid)
        if valid["status"] in {"no_data", "observed_partial"}:
            report["comparison"] = _compare(valid["weeks"], observed)
            # Validate source on cache replay; only whitelisted counters persist.
            cache.save(key, {"source": SOURCE, "repo": report["repo"],
                             "observed_at": observed.isoformat(), "limit": limit,
                             "source_rows": [{"week": w["week_start_provider_epoch"],
                                              "total": w["weekly_active_star_events"],
                                              "days": w["provider_day_slots_sun_to_sat"]}
                                             for w in valid["weeks"]]}, ttl=TTL_SECONDS)
        return report
    except Exception as exc:
        if isinstance(exc, SourceTooLarge):
            report.update(status="invalid_source_shape", reason="response_oversized")
        elif type(exc).__name__ == "DailyBudgetExceeded":
            report.update(status="unavailable", reason="local_daily_budget_exceeded")
        elif type(exc).__name__ == "SourceCoolingDown":
            report.update(status="unavailable", reason="provider_cooldown")
        else:
            report.update(status="unavailable", reason="storage_or_network_unavailable")
        return report
