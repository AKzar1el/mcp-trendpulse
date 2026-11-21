"""B01: bounded public OpenSSF Scorecard repository-security evidence.

A public Scorecard assessment is *not* an audit, guarantee, exploit report,
commercial opportunity, or proof an unscored project is insecure.
No default MCP tool or background scan is registered.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

BASE = "https://api.scorecard.dev"
SOURCE = "openssf_published_scorecard"
CAP_PER_DAY = 4
TTL_SECONDS = 24 * 3600
MAX_BODY_BYTES = 96 * 1024
MAX_CHECKS = 40
_OWNER = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_REPO = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_CHECK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,79}$")
_COMMIT = re.compile(r"^[0-9a-fA-F]{40}$")


class ResponseTooLarge(ValueError):
    pass


def _id(owner: Any, repo: Any) -> tuple[str, str]:
    if not isinstance(owner, str) or not _OWNER.fullmatch(owner):
        raise ValueError("Invalid GitHub owner")
    if (not isinstance(repo, str) or not _REPO.fullmatch(repo)
            or repo in {".", ".."} or ".." in repo):
        raise ValueError("Invalid GitHub repository")
    return owner, repo


def _url(owner: str, repo: str) -> str:
    return f"{BASE}/projects/github.com/{owner}/{repo}"


def _key(owner: str, repo: str) -> str:
    return "mjau_v2_scorecard_" + hashlib.sha256(json.dumps(
        [SOURCE, owner.casefold(), repo.casefold()], separators=(",", ":"),
    ).encode()).hexdigest()


def _parse(payload: Any, *, owner: str, repo: str,
           observed_at: datetime) -> dict[str, Any]:
    invalid = {"status": "invalid_source_shape", "checks": [],
               "aggregate_score": None}
    if not isinstance(payload, dict):
        return invalid
    source_repo, source_tool = payload.get("repo"), payload.get("scorecard")
    checks, aggregate = payload.get("checks"), payload.get("score")
    if (not isinstance(source_repo, dict)
            or not isinstance(source_tool, dict)
            or not isinstance(checks, list) or not 1 <= len(checks) <= MAX_CHECKS
            or not isinstance(source_repo.get("name"), str)
            or source_repo["name"].casefold() != f"github.com/{owner}/{repo}".casefold()
            or not isinstance(source_repo.get("commit"), str)
            or not _COMMIT.fullmatch(source_repo["commit"])):
        return invalid
    if (type(aggregate) not in (int, float) or not -1 <= aggregate <= 10
            or not isinstance(source_tool.get("version"), str)
            or not 1 <= len(source_tool["version"]) <= 50):
        return invalid
    try:
        when = datetime.fromisoformat(payload["date"].replace("Z", "+00:00"))
        if when.utcoffset() is None or when > observed_at:
            return invalid
        when = when.astimezone(timezone.utc)
    except (KeyError, ValueError, AttributeError, TypeError):
        return invalid
    clean = []
    seen = set()
    for row in checks:
        if not isinstance(row, dict):
            return invalid
        name, score = row.get("name"), row.get("score")
        if (not isinstance(name, str) or not _CHECK.fullmatch(name)
                or name.casefold() in seen
                or type(score) not in (int, float) or not -1 <= score <= 10):
            return invalid
        clean.append({"name": name, "score": None if score < 0 else score,
                      "inconclusive": score < 0})
        seen.add(name.casefold())
    clean.sort(key=lambda row: row["name"])
    age_days = max(0, (observed_at.date() - when.date()).days)
    return {
        "status": "observed_stale" if age_days > 30 else "observed",
        "source_scan_at": when.isoformat(),
        "scan_age_days": age_days,
        "repo_commit_scanned": source_repo["commit"],
        "scorecard_version": source_tool["version"],
        "aggregate_score": None if aggregate < 0 else aggregate,
        "aggregate_inconclusive": aggregate < 0,
        "checks": clean,
        "reported_check_count": len(clean),
        "inconclusive_check_count": sum(row["inconclusive"] for row in clean),
        "score_scale": "source_check_score_0_to_10_inconclusive_is_null",
        "not_a_security_audit_or_vulnerability_guarantee": True,
        "no_score_is_not_insecure": True,
        "coverage": "published_scanned_repo_only_not_all_public_repositories",
        "source_viewer_url": (f"https://scorecard.dev/viewer/?uri="
                              f"github.com/{owner}/{repo}"),
    }


def _fetch(url: str) -> tuple[int, Any]:
    """One fixed-host, body-bounded, non-redirecting HTTPS request."""
    import requests

    if not re.fullmatch(r"https://api\.scorecard\.dev/projects/github\.com/[A-Za-z0-9-]+/[A-Za-z0-9_.-]+", url):
        raise ValueError("Unapproved Scorecard destination")
    session = requests.Session()
    session.trust_env = False
    try:
        with session.get(
            url, stream=True, allow_redirects=False, timeout=(4, 12),
            headers={"Accept": "application/json",
                     "User-Agent": "mcp-trendpulse/0.2 (read-only security metadata)"},
        ) as response:
            if (response.status_code != 200
                    or "json" not in response.headers.get("Content-Type", "").lower()):
                return response.status_code, None
            raw = response.raw.read(MAX_BODY_BYTES + 1, decode_content=True)
            if len(raw) > MAX_BODY_BYTES:
                raise ResponseTooLarge("Scorecard source exceeded local cap")
            try:
                return 200, json.loads(raw)
            except (UnicodeError, ValueError):
                return 200, None
    finally:
        session.close()


def inspect_openssf_scorecard(
    *, owner: str, repo: str, execute: bool = False,
    cache: Any = None,
    fetcher: Callable[[str], tuple[int, Any]] | None = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    owner, repo = _id(owner, repo)
    if type(execute) is not bool:
        raise ValueError("execute must be a boolean")
    now = observed_at or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("Observed-at requires timezone")
    now = now.astimezone(timezone.utc)
    url = _url(owner, repo)
    result: dict[str, Any] = {
        "status": "planned", "source": SOURCE,
        "source_url": url, "repository": f"github.com/{owner}/{repo}",
        "observed_at": now.isoformat(), "requests_attempted": 0,
        "network_performed": False, "cache_hit": False,
        "aggregate_score": None, "checks": [],
        "local_daily_request_cap": CAP_PER_DAY, "no_score_is_not_insecure": True,
        "source_not_a_security_audit": True, "verified_exploits": False,
        "revenue_or_customer_demand_verified": False,
    }
    if not execute:
        return result
    try:
        if cache is None:
            from mcp_trendpulse.intelligence_core import BudgetCache
            cache = BudgetCache(root=Path.home() / ".mcp-trendpulse" / "mjau-v2-intelligence")
        key = _key(owner, repo)
        saved = cache.cached(key)
        if (isinstance(saved, dict) and saved.get("source") == SOURCE
                and saved.get("repository", "").casefold() == result["repository"].casefold()
                and isinstance(saved.get("observed_at"), str)):
            try:
                before = datetime.fromisoformat(saved["observed_at"])
                if (before.utcoffset() is not None and 0 <= (now - before).total_seconds() <= TTL_SECONDS):
                    parsed = _parse(saved.get("payload"), owner=owner, repo=repo, observed_at=now)
                    if parsed["status"] == "observed":
                        result.update(parsed)
                        result["cache_hit"] = True
                        result["observed_at"] = before.astimezone(timezone.utc).isoformat()
                        return result
            except (ValueError, TypeError):
                pass
        if cache.blocked(SOURCE):
            result.update(status="unavailable", reason="provider_cooldown")
            return result
        cache.reserve(SOURCE, CAP_PER_DAY, guard_cooldown=True)
        result["requests_attempted"] = 1
        status, payload = (fetcher or _fetch)(url)
        result["network_performed"] = True
        if status in (429, 503):
            cache.cool_down(SOURCE, seconds=120)
            result.update(status="unavailable", reason=f"http_{status}")
            return result
        if status == 404:
            result.update(status="not_covered", reason="no_published_scorecard")
            return result
        if status != 200:
            result.update(status="unavailable", reason="provider_response_error")
            return result
        parsed = _parse(payload, owner=owner, repo=repo, observed_at=now)
        result.update(parsed)
        if parsed["status"] == "observed":
            safe_checks = [
                {"name": row["name"],
                 "score": -1 if row["inconclusive"] else row["score"]}
                for row in parsed["checks"]
            ]
            cache.save(key, {
                "source": SOURCE, "repository": result["repository"],
                "observed_at": now.isoformat(),
                "payload": {
                    "date": parsed["source_scan_at"],
                    "repo": {"name": result["repository"],
                             "commit": parsed["repo_commit_scanned"]},
                    "scorecard": {"version": parsed["scorecard_version"]},
                    "score": -1 if parsed["aggregate_inconclusive"]
                        else parsed["aggregate_score"],
                    "checks": safe_checks,
                },
            }, ttl=TTL_SECONDS)
        return result
    except Exception as exc:
        if isinstance(exc, ResponseTooLarge):
            result.update(status="invalid_source_shape", reason="response_oversized")
        elif type(exc).__name__ == "DailyBudgetExceeded":
            result.update(status="unavailable", reason="local_daily_budget_exceeded")
        elif type(exc).__name__ == "SourceCoolingDown":
            result.update(status="unavailable", reason="provider_cooldown")
        else:
            result.update(status="unavailable", reason="storage_or_network_unavailable")
        return result
