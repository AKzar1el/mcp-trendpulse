"""MJAU M08: bounded GitHub issue evidence through the *existing* collector.

No second GitHub HTTP client, alternate credentials, per-issue fetch, or
unbounded pagination. Public issue text/author/body never enters this report.
Search matches are not buyers, distinct users, or independent problems.
"""
from __future__ import annotations

import re
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit

from mcp_trendpulse.intelligence_core import (
    BudgetCache,
    DailyBudgetExceeded,
    IntelligenceError,
    collect,
    plan_source,
)
from mcp_trendpulse.intelligence_signal import (
    SignalPeriod,
    SignalProvenance,
    TrendSignal,
)

MODE = "github_public_issue_problem_evidence"
SOURCE_ID = "github_issues"
MAX_ISSUES = 10
_SEARCH_PHRASE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 .+_-]{2,79}\Z")
_OWNER_REPO = re.compile(
    r"([A-Za-z0-9][A-Za-z0-9_.-]{0,38})/([A-Za-z0-9][A-Za-z0-9_.-]{0,99})\Z"
)
_ISSUE_PATH = re.compile(
    r"/([A-Za-z0-9][A-Za-z0-9_.-]{0,38})/"
    r"([A-Za-z0-9][A-Za-z0-9_.-]{0,99})/issues/([1-9]\d*)\Z"
)
_REPO_PATH = re.compile(
    r"/repos/([A-Za-z0-9][A-Za-z0-9_.-]{0,38})/"
    r"([A-Za-z0-9][A-Za-z0-9_.-]{0,99})\Z"
)
_ALLOWED_ISSUE_TYPES = frozenset({
    "reported_operational_problem",
    "unverified_public_issue",
    "promotional_market_claim",
    "hypothetical_or_unverified_design",
    "profile_repository_work_item",
    "internal_implementation_work_item",
})


def _phrase(value: str) -> str:
    if not isinstance(value, str) or not _SEARCH_PHRASE.fullmatch(value):
        raise ValueError(
            "GitHub problem phrase must be a printable 3-80 character term, "
            "not a URL, user selector or search-qualifier expression"
        )
    return value


def _repository(value: str) -> str:
    if not isinstance(value, str) or (
        value and (
            _OWNER_REPO.fullmatch(value) is None
            or "." in value.split("/", 1)[0]
        )
    ):
        raise ValueError("GitHub repository must be a public owner/repo selector")
    return value


def _utc(value: Any, observed: datetime) -> datetime | None:
    if not isinstance(value, str) or len(value) > 35:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        parsed = parsed.astimezone(timezone.utc)
        if parsed > observed + timedelta(minutes=5) or parsed.year < 2008:
            return None
        return parsed
    except (OverflowError, ValueError, TypeError):
        return None


def _record(
    item: Any, *,
    observed: datetime,
    expected_repo: str,
    utc_cutoff: datetime,
    phrase: str,
) -> dict[str, Any] | None:
    if not isinstance(item, dict) or item.get("pull_request") is not None:
        return None
    ghid = item.get("id")
    number = item.get("number")
    title = item.get("title")
    if (type(ghid) is not int or not 0 < ghid < 2**53
            or type(number) is not int or not 0 < number < 2**31
            or item.get("state") != "open"
            or not isinstance(title, str) or not 2 <= len(title) <= 180
            or title != title.strip()
            or any(ord(char) < 32 or ord(char) == 127 for char in title)):
        return None
    link = item.get("html_url")
    project = item.get("repository_url")
    if not isinstance(link, str) or not isinstance(project, str):
        return None
    try:
        html = urlsplit(link)
        repo_url = urlsplit(project)
        html_port, repo_port = html.port, repo_url.port
    except ValueError:
        return None
    if (
        html.scheme != "https" or html.hostname != "github.com"
        or repo_url.scheme != "https" or repo_url.hostname != "api.github.com"
        or html.username or html.password or html_port is not None
        or repo_url.username or repo_url.password or repo_port is not None
        or html.query or html.fragment or repo_url.query or repo_url.fragment
    ):
        return None
    match = _ISSUE_PATH.fullmatch(html.path)
    repo_match = _REPO_PATH.fullmatch(repo_url.path)
    if match is None or repo_match is None or int(match.group(3)) != number:
        return None
    owner_repo = f"{match.group(1)}/{match.group(2)}"
    if (
        match.group(1).casefold() != repo_match.group(1).casefold()
        or match.group(2).casefold() != repo_match.group(2).casefold()
        or expected_repo and owner_repo.casefold() != expected_repo.casefold()
    ):
        return None
    created = _utc(item.get("created_at"), observed)
    updated = _utc(item.get("updated_at"), observed)
    if (
        created is None or updated is None or updated < created
        or created < utc_cutoff
    ):
        return None
    quality = item.get("issue_evidence_type")
    if quality not in _ALLOWED_ISSUE_TYPES:
        return None
    return {
        "issue_id": ghid,
        "number": number,
        "repository": owner_repo,
        "created_at": created.isoformat(),
        "updated_at": updated.isoformat(),
        "utc_day": created.date().isoformat(),
        "state": "open",
        "title": title,
        "source_url": (
            f"https://github.com/{match.group(1)}/{match.group(2)}/issues/{number}"
        ),
        "issue_evidence_type": quality,
        "title_contains_exact_phrase": phrase.casefold() in title.casefold(),
    }


def _sample(
    data: Any, observations: Any, *,
    observed: datetime,
    phrase: str,
    repository: str,
    lookback_days: int,
) -> dict[str, Any]:
    if (
        not isinstance(data, dict) or not isinstance(observations, dict)
        or not isinstance(observations.get("sample"), list)
        or type(observations.get("record_count")) is not int
        or observations["record_count"] < 0
        or type(data.get("page_items_received")) is not int
        or not 0 <= data["page_items_received"] <= MAX_ISSUES
        or observations["record_count"] != data["page_items_received"]
        or type(data.get("total_count")) is not int
        or not 0 <= data["total_count"] <= 100_000_000
        or type(data.get("incomplete_results")) is not bool
        or data["total_count"] < observations["record_count"]
    ):
        return {"status": "invalid_source_shape"}
    rows = observations["sample"]
    if len(rows) > MAX_ISSUES or len(rows) != observations["record_count"]:
        return {"status": "invalid_source_shape"}
    cutoff = datetime.combine(
        observed.date() - timedelta(days=lookback_days),
        datetime.min.time(), tzinfo=timezone.utc,
    )
    unique_ids: set[int] = set()
    unique_repos: set[tuple[str, int]] = set()
    accepted = []
    for item in rows:
        row = _record(
            item, observed=observed, expected_repo=repository,
            utc_cutoff=cutoff, phrase=phrase,
        )
        if row is None:
            continue
        pair = (row["repository"].casefold(), row["number"])
        if row["issue_id"] in unique_ids or pair in unique_repos:
            continue
        unique_ids.add(row["issue_id"])
        unique_repos.add(pair)
        accepted.append(row)
    accepted.sort(key=lambda r: (r["created_at"], r["issue_id"]), reverse=True)
    rejected = len(rows) - len(accepted)
    total = data["total_count"]
    if not rows and not total and not data["incomplete_results"]:
        status = "no_data"
    elif not accepted:
        status = "invalid_source_shape"
    elif (
        rejected or total > len(rows) or data["incomplete_results"]
    ):
        status = "observed_partial"
    else:
        status = "observed"

    # Owner/repository selection is non-representative; no authors are
    # retained. Multiple issues in one repo are not independent buyers.
    repo_counts = Counter(x["repository"] for x in accepted)
    owner_counts = Counter(x["repository"].split("/")[0].casefold() for x in accepted)
    return {
        "status": status,
        "issues": accepted,
        "source_rows_received": len(rows),
        "source_rows_rejected_or_duplicated": rejected,
        "provider_total_matches_reported": total,
        "provider_incomplete_results": data["incomplete_results"],
        "provider_matches_not_fetched": max(0, total-len(rows)),
        "summary": {
            "unique_open_issue_ids_in_sample": len(accepted),
            "distinct_repositories_in_sample": len(repo_counts),
            "distinct_repository_owners_in_sample": len(owner_counts),
            "largest_owner_share_of_sample": (
                round(max(owner_counts.values()) / len(accepted), 3)
                if accepted else None
            ),
            "daily_sample_counts": [
                {"utc_day": day, "issue_count": count}
                for day, count in sorted(
                    Counter(x["utc_day"] for x in accepted).items()
                )
            ],
            "reported_operational_problem_labels": sum(
                r["issue_evidence_type"] == "reported_operational_problem"
                for r in accepted
            ),
            "source_report_is_partial": status != "observed",
            "repository_owner_bias": (
                "explicit_repository_filter" if repository
                else "GitHub search rank, public repositories and owner dominance"
            ),
            "distinct_humans_verified": False,
            "independent_buyers_verified": False,
            "product_demand_verified": False,
        },
    }


def _signals(
    *, rows: list[dict[str, Any]], phrase: str,
    observed: datetime, source_url: str,
) -> list[dict[str, Any]]:
    daily = Counter(r["utc_day"] for r in rows)
    return [
        TrendSignal(
            source_id=SOURCE_ID, source_url=source_url,
            observed_at=observed,
            country=None, language=None, raw_term=phrase,
            normalized_term=phrase.casefold(),
            metric_type="github_issue_mentions",
            metric_unit="issues",
            period=SignalPeriod(
                start_date=day, end_date=day, granularity="daily",
            ),
            value=count,
            sampling_scope=(
                "Unique GitHub open-issue IDs in bounded first-page public "
                "search sample; repository/owner bias, not all GitHub issues"
            ),
            coverage_status="partial",
            provenance=SignalProvenance(
                method="public_api",
                sampling_basis="first_page_issue_id_distinct_created_utc_day",
                is_observed_search_query=False,
            ),
        ).model_dump(mode="json")
        for day, count in sorted(daily.items())
    ]


def discover_github_problems(
    *, query: str, repository: str = "", lookback_days: int = 30,
    limit: int = 10, execute: bool = False, cache: Any = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Use exactly the existing Foundation -> Core GitHub search path."""
    query = _phrase(query)
    repository = _repository(repository)
    if type(lookback_days) is not int or not 7 <= lookback_days <= 90:
        raise ValueError("Issue search lookback must be 7-90 days")
    if type(limit) is not int or not 1 <= limit <= MAX_ISSUES:
        raise ValueError("Issue search limit must be 1-10")
    if type(execute) is not bool:
        raise ValueError("Execute must be boolean")
    observed = observed_at or datetime.now(timezone.utc)
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("Observation requires timezone")
    observed = observed.astimezone(timezone.utc)
    plan = plan_source(
        SOURCE_ID, keyword=query, identifier=repository,
        lookback_days=lookback_days, limit=limit, env={},
    )
    result: dict[str, Any] = {
        "mode": MODE, "source": SOURCE_ID, "source_url": plan.url,
        "status": "planned" if not execute else "unavailable",
        "query": query, "query_provenance": "manual_keyword_not_observed_search",
        "repository_filter": repository or None,
        "lookback_days": lookback_days, "limit": limit,
        "observed_at": observed.isoformat(), "country": None,
        "language": None,
        "method": "existing_intelligence_foundation_github_issues",
        "duplicate_github_api_client_created": False,
        "requests_attempted": 0, "network_performed": False,
        "cache_hit": False, "daily_original_source_budget": plan.budget_per_day,
        "source_rows_received": 0, "source_rows_rejected_or_duplicated": 0,
        "provider_total_matches_reported": None,
        "provider_incomplete_results": None,
        "provider_matches_not_fetched": None,
        "issues": [], "signals": [],
        "summary": None, "paid_services_used": False,
        "search_volume_verified": False, "independent_buyers_verified": False,
    }
    if not execute:
        return result
    try:
        store = cache if cache is not None else BudgetCache()
        original = collect(plan, cache=store, fetch=True)
    except DailyBudgetExceeded:
        result["status"] = "local_daily_budget_exhausted"
        return result
    except (IntelligenceError, OSError, TypeError, ValueError, sqlite3.Error):
        result["status"] = "local_budget_unavailable"
        return result

    result["cache_hit"] = bool(original.get("cache_hit"))
    is_cooldown = original.get("reason") == "provider_cooldown"
    result["network_performed"] = not result["cache_hit"] and not is_cooldown
    result["requests_attempted"] = int(result["network_performed"])
    if original.get("status") != "observed":
        if is_cooldown:
            result["status"] = "provider_cooldown"
        elif original.get("http_status") in (429, 503):
            result["status"] = "provider_rate_limited"
        elif original.get("status") == "invalid_source_shape":
            result["status"] = "invalid_source_shape"
        else:
            result["status"] = "provider_unavailable"
        return result
    retrieved_at = _utc(original.get("retrieved_at"), observed)
    if (retrieved_at is None or original.get("source") != SOURCE_ID
            or original.get("source_url") != plan.url):
        result["status"] = "invalid_source_metadata"
        return result
    parsed = _sample(
        original.get("data"), original.get("observations"),
        observed=observed, phrase=query, repository=repository,
        lookback_days=lookback_days,
    )
    result.update(parsed)
    if parsed["status"] in ("observed", "observed_partial"):
        result["signals"] = _signals(
            rows=parsed["issues"], phrase=query,
            observed=retrieved_at, source_url=plan.url,
        )
    return result


def format_github_problems(report: dict[str, Any]) -> str:
    lines = [
        f"GITHUB ISSUES | {report['query']} | {report['status']}",
        "Public open-issue sample, not independent buyers or search volume.",
        f"Repo filter: {report['repository_filter'] or 'all searchable repos'}; "
        f"lookback: {report['lookback_days']} days; "
        f"requests: {report['requests_attempted']}"
        + (" (cached)" if report["cache_hit"] else ""),
    ]
    for item in report["issues"]:
        lines.append(
            f"{item['utc_day']} | {item['repository']}#{item['number']} "
            f"| {item['issue_evidence_type']} | {item['title']}"
        )
    return "\n".join(lines)
