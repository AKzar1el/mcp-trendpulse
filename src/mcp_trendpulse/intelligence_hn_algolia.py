"""M07: bounded, keyless Hacker News Algolia discussion evidence.

This is a community search *sample*, not HN population statistics, a
corroborated customer problem or commercial demand. Story/comment units
are never mixed. No external links, comment bodies or author profiles
are fetched, persisted or exposed by this adapter.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from mcp_trendpulse.intelligence_core import BudgetCache, DailyBudgetExceeded
from mcp_trendpulse.intelligence_signal import (
    SignalPeriod, SignalProvenance, TrendSignal,
)

MODE = "hacker_news_algolia_recent_discussions"
SOURCE_ID = "hacker_news_algolia"
URL = "https://hn.algolia.com/api/v1/search_by_date"
ALLOWED_TAGS = frozenset(("story", "show_hn", "ask_hn", "comment"))
UTC_DAILY_REQUEST_CAP = 5
CACHE_TTL_SECONDS = 2 * 3600
ANCHOR_SECONDS = 2 * 3600
MAX_RESULTS = 20
MAX_RESPONSE_BYTES = 160 * 1024
_EXACT_MAX = (1 << 53) - 1
_ITEM_ID = re.compile(r"[1-9]\d{0,17}\Z")


class ResponseTooLarge(RuntimeError):
    """The source response exceeds the bounded single-fetch size."""


def _term(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("Hacker News research term must be a string")
    if (value != value.strip() or not 3 <= len(value) <= 90
            or "://" in value or "@" in value
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ValueError("Use an explicit printable 3-90 character research phrase")
    return value


def _title(value: Any) -> str | None:
    if (not isinstance(value, str) or not 2 <= len(value) <= 180
            or value != value.strip()
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        return None
    return value


def _id(value: Any) -> str | None:
    # Algolia objectID is a string; story_id can be an int.
    if type(value) is int:
        value = str(value)
    if not isinstance(value, str) or _ITEM_ID.fullmatch(value) is None:
        return None
    return value


def _count(value: Any) -> int | None:
    if value is None:
        return None  # Missing points/comments are not invented zeros.
    return value if type(value) is int and 0 <= value <= _EXACT_MAX else None


def _observed_scope(
    *, tag: str, days: int, limit: int, observed_at: datetime,
) -> dict[str, Any]:
    if tag not in ALLOWED_TAGS:
        raise ValueError("HN scope must be story, show_hn, ask_hn or comment")
    if type(days) is not int or not 1 <= days <= 30:
        raise ValueError("HN lookback is bounded to 1-30 days")
    if type(limit) is not int or not 1 <= limit <= MAX_RESULTS:
        raise ValueError("HN result cap must be 1-20")
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("Observation timestamp requires UTC timezone")
    now = observed_at.astimezone(timezone.utc)
    anchor = int(now.timestamp()) // ANCHOR_SECONDS * ANCHOR_SECONDS
    if anchor <= 0:
        raise ValueError("Observation must be after Unix epoch")
    start = anchor - days * 86400
    if start <= 0:
        raise ValueError("Observation window is invalid")
    return {
        "start_epoch_inclusive": start,
        "end_epoch_exclusive": anchor,
        "days": days,
        "source_snapshot_end_utc": datetime.fromtimestamp(
            anchor, tz=timezone.utc,
        ).isoformat(),
        "hour_bucket_seconds": ANCHOR_SECONDS,
    }


def _params(query: str, tag: str, limit: int, window: dict[str, Any]) -> dict[str, str]:
    return {
        "query": query,
        "tags": tag,
        "numericFilters": (
            f"created_at_i>={window['start_epoch_inclusive']},"
            f"created_at_i<{window['end_epoch_exclusive']}"
        ),
        "hitsPerPage": str(limit),
        "page": "0",
    }


def _key(query: str, tag: str, limit: int, window: dict[str, Any]) -> str:
    payload = json.dumps(
        ["mjau_m07_v1", query.casefold(), tag, limit, window],
        ensure_ascii=False, separators=(",", ":"), sort_keys=True,
    )
    return "mjau_hn:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _record(hit: Any, *, tag: str, window: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(hit, dict):
        return None
    raw_id = _id(hit.get("objectID"))
    timestamp = hit.get("created_at_i")
    flags = hit.get("_tags")
    if (raw_id is None or type(timestamp) is not int
            or not window["start_epoch_inclusive"] <= timestamp
                   < window["end_epoch_exclusive"]
            or not isinstance(flags, list)
            or any(not isinstance(t, str) for t in flags)
            or tag not in flags):
        return None
    if tag == "comment":
        if "comment" not in flags:
            return None
        story_id = _id(hit.get("story_id"))
        if story_id is None:
            return None
        title = _title(hit.get("story_title"))
        kind = "comment"
    else:
        if "story" not in flags:
            return None
        story_id = raw_id
        title = _title(hit.get("title"))
        if title is None:
            return None
        kind = "story"
    created = hit.get("created_at")
    if not isinstance(created, str):
        return None
    try:
        parsed = datetime.fromisoformat(created.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        utc = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        if abs((parsed.astimezone(timezone.utc) - utc).total_seconds()) > 1:
            return None
    except (OverflowError, OSError, ValueError):
        return None

    # Preserve metadata only. Do not return raw comment text or author.
    result: dict[str, Any] = {
        "item_id": raw_id,
        "story_id": story_id,
        "kind": kind,
        "hn_url": f"https://news.ycombinator.com/item?id={raw_id}",
        "created_at": utc.isoformat(),
        "utc_day": utc.date().isoformat(),
        "title": title,
    }
    if kind == "story":
        points = hit.get("points")
        replies = hit.get("num_comments")
        if points is not None and _count(points) is None:
            return None
        if replies is not None and _count(replies) is None:
            return None
        result["points"] = points
        result["num_comments"] = replies
    return result


def _parse(
    payload: Any, *, tag: str, window: dict[str, Any], limit: int,
) -> dict[str, Any]:
    if (not isinstance(payload, dict) or not isinstance(payload.get("hits"), list)
            or type(payload.get("nbHits")) is not int
            or type(payload.get("nbPages")) is not int
            or type(payload.get("page")) is not int
            or type(payload.get("hitsPerPage")) is not int):
        return {"status": "invalid_source_shape"}
    hits = payload["hits"]
    total, pages = payload["nbHits"], payload["nbPages"]
    if (not 0 <= total <= 100_000_000 or not 0 <= pages <= 100_000_000
            or payload["page"] != 0
            or not 1 <= payload["hitsPerPage"] <= MAX_RESULTS
            or len(hits) > limit or len(hits) > payload["hitsPerPage"]
            or total < len(hits)):
        return {"status": "invalid_source_shape"}
    seen = set()
    rows = []
    for hit in hits:
        parsed = _record(hit, tag=tag, window=window)
        if parsed is None or parsed["item_id"] in seen:
            continue
        seen.add(parsed["item_id"])
        rows.append(parsed)
    rows.sort(key=lambda r: (r["created_at"], r["item_id"]), reverse=True)
    omitted = len(hits) - len(rows)
    unfetched = max(0, total - len(hits))
    if not rows:
        status = "invalid_source_shape" if hits or total else "no_data"
    elif omitted or unfetched or pages > 1:
        status = "observed_partial"
    else:
        status = "observed"
    return {
        "status": status, "records": rows, "source_rows_received": len(hits),
        "source_rows_rejected": omitted,
        "source_total_matches_reported": total,
        "source_other_pages_present": pages > 1,
        "matching_hits_not_fetched_reported": unfetched,
    }


def _validate_cache(
    body: Any, *, query: str, tag: str, limit: int,
    window: dict[str, Any], observed_at: datetime,
) -> tuple[dict[str, Any], datetime] | None:
    if (not isinstance(body, dict)
            or any(body.get(k) != v for k, v in (
                ("query", query), ("tag", tag), ("limit", limit),
                ("window", window),
            ))):
        return None
    try:
        when = datetime.fromisoformat(body["observed_at"])
        if when.tzinfo is None or when.utcoffset() is None:
            return None
        when = when.astimezone(timezone.utc)
        if when > observed_at or when < observed_at - timedelta(days=1):
            return None
    except (TypeError, ValueError, KeyError):
        return None
    if (body.get("status") not in {"observed", "observed_partial", "no_data"}
            or not isinstance(body.get("records"), list)
            or len(body["records"]) > limit):
        return None
    rows = []
    used = set()
    for x in body["records"]:
        if not isinstance(x, dict):
            return None
        rid = _id(x.get("item_id"))
        sid = _id(x.get("story_id"))
        raw_day = x.get("utc_day")
        try:
            stamp = datetime.fromisoformat(x.get("created_at"))
            if stamp.tzinfo is None:
                return None
            stamp = stamp.astimezone(timezone.utc)
        except (TypeError, ValueError):
            return None
        if (rid is None or sid is None or rid in used
                or type(raw_day) is not str or raw_day != stamp.date().isoformat()
                or not window["start_epoch_inclusive"] <= int(stamp.timestamp())
                       < window["end_epoch_exclusive"]
                or x.get("kind") != ("comment" if tag == "comment" else "story")
                or x.get("hn_url") != f"https://news.ycombinator.com/item?id={rid}"):
            return None
        title = x.get("title")
        if title is not None and _title(title) is None:
            return None
        if tag != "comment" and (title is None or sid != rid):
            return None
        row = {
            "item_id": rid, "story_id": sid, "kind": x["kind"],
            "hn_url": f"https://news.ycombinator.com/item?id={rid}",
            "created_at": stamp.isoformat(), "utc_day": raw_day,
            "title": title,
        }
        if tag != "comment":
            points, replies = x.get("points"), x.get("num_comments")
            if (points is not None and _count(points) is None
                    or replies is not None and _count(replies) is None):
                return None
            row["points"], row["num_comments"] = points, replies
        rows.append(row)
        used.add(rid)
    total, rejected, received = (
        body.get("source_total_matches_reported"),
        body.get("source_rows_rejected"),
        body.get("source_rows_received"),
    )
    pages, other = body.get("matching_hits_not_fetched_reported"), body.get(
        "source_other_pages_present",
    )
    if (type(total) is not int or type(rejected) is not int
            or type(received) is not int or type(pages) is not int
            or type(other) is not bool
            or not 0 <= rejected <= received <= limit
            or not 0 <= total <= 100_000_000 or total < received
            or received != len(rows) + rejected
            or pages != total - received
            or body["status"] == "observed" and (not rows or rejected or pages or other)
            or body["status"] == "observed_partial" and (not rows or not (rejected or pages or other))
            or body["status"] == "no_data" and (rows or received or total)):
        return None
    # Reconstruct only allowlisted types, preventing arbitrary SQLite JSON
    # content or unexpected hidden data from being emitted.
    return {
        "status": body["status"], "records": rows,
        "source_rows_received": received, "source_rows_rejected": rejected,
        "source_total_matches_reported": total,
        "source_other_pages_present": other,
        "matching_hits_not_fetched_reported": pages,
    }, when


def _summary(records: list[dict[str, Any]], tag: str) -> dict[str, Any]:
    days = Counter(row["utc_day"] for row in records)
    story_ids = {r["story_id"] for r in records}
    return {
        "unit": "comment_matches" if tag == "comment" else "distinct_story_items",
        "observed_items_on_returned_page": len(records),
        "distinct_discussion_threads_on_returned_page": len(story_ids),
        "distinct_utc_days_on_returned_page": len(days),
        "daily_sample_counts": [
            {"date": day, "count": days[day]} for day in sorted(days)
        ],
        "not_all_hacker_news_items_counted": True,
        "customer_demand_verified": False,
        "sentiment_or_problem_validated": False,
    }


def _story_signals(
    *, records: list[dict[str, Any]], query: str,
    observed: datetime,
) -> list[dict[str, Any]]:
    counts = Counter(r["utc_day"] for r in records)
    return [
        TrendSignal(
            source_id=SOURCE_ID, source_url=URL, observed_at=observed,
            country=None, language=None, raw_term=query,
            normalized_term=query.casefold(),
            metric_type="hacker_news_story_mentions", metric_unit="stories",
            period=SignalPeriod(
                start_date=day, end_date=day, granularity="daily",
            ),
            value=total, coverage_status="partial",
            sampling_scope=(
                "Unique matching HN story IDs on bounded first Algolia "
                "search-by-date page; not total HN activity"
            ),
            provenance=SignalProvenance(
                method="public_api",
                sampling_basis="first_page_search_match_unique_story_id_per_utc_day",
                is_observed_search_query=False,
            ),
        ).model_dump(mode="json")
        for day, total in sorted(counts.items())
    ]


def _fetch(url: str, params: dict[str, str]) -> tuple[int, Any]:
    import requests

    if url != URL:
        raise ValueError("Unapproved HN API request destination")
    session = requests.Session()
    session.trust_env = False
    try:
        with session.get(
            url, params=params, stream=True, allow_redirects=False,
            timeout=(5, 12),
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    "mcp-trendpulse/0.2 (https://github.com/AKzar1el/mcp-trendpulse)"
                ),
            },
        ) as response:
            code = response.status_code
            if code != 200 or "json" not in response.headers.get("Content-Type", "").lower():
                return code, None
            data = response.raw.read(MAX_RESPONSE_BYTES + 1, decode_content=True)
            if len(data) > MAX_RESPONSE_BYTES:
                raise ResponseTooLarge()
            try:
                return code, json.loads(data)
            except (UnicodeError, ValueError):
                return code, None
    finally:
        session.close()


def discover_hn_discussions(
    *, query: str, tag: str = "story", days: int = 14,
    limit: int = 10, execute: bool = False,
    cache: Any = None,
    fetcher: Callable[[str, dict[str, str]], tuple[int, Any]] | None = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Bounded one-page public discussion lookup; no browser or paid API."""
    query = _term(query)
    if type(execute) is not bool:
        raise ValueError("Execute must be a boolean")
    observed = observed_at or datetime.now(timezone.utc)
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("Observation needs timezone")
    observed = observed.astimezone(timezone.utc)
    window = _observed_scope(
        tag=tag, days=days, limit=limit, observed_at=observed,
    )
    result: dict[str, Any] = {
        "mode": MODE, "source": SOURCE_ID, "source_url": URL,
        "status": "planned" if not execute else "unavailable",
        "query": query, "tag": tag, "kind": "comment" if tag == "comment" else "story",
        "window": window,
        "observed_at": observed.isoformat(),
        "country": None, "language": None, "page": 0, "limit": limit,
        "sort_order": "newest_first", "query_provenance": "manual_research_phrase",
        "requests_attempted": 0, "network_performed": False,
        "cache_hit": False,
        "local_utc_daily_request_cap": UTC_DAILY_REQUEST_CAP,
        "source_rows_received": 0, "source_rows_rejected": 0,
        "source_total_matches_reported": None,
        "source_other_pages_present": False,
        "matching_hits_not_fetched_reported": None,
        "records": [], "signals": [], "summary": _summary([], tag),
        "algorithmic_keyword_match_not_human_relevance_check": True,
        "search_volume_verified": False, "customer_demand_verified": False,
        "paid_services_used": False,
    }
    if not execute:
        return result

    try:
        store = cache if cache is not None else BudgetCache()
        key = _key(query, tag, limit, window)
        cached = _validate_cache(
            store.cached(key), query=query, tag=tag, limit=limit,
            window=window, observed_at=observed,
        )
        if cached is not None:
            parsed, observed_original = cached
            result.update(parsed)
            result["observed_at"] = observed_original.isoformat()
            result["cache_hit"] = True
            result["summary"] = _summary(parsed["records"], tag)
            if tag != "comment":
                result["signals"] = _story_signals(
                    records=parsed["records"], query=query, observed=observed_original,
                )
            return result
        if store.blocked(SOURCE_ID):
            result["status"] = "provider_cooldown"
            return result
        store.reserve(SOURCE_ID, UTC_DAILY_REQUEST_CAP)
    except DailyBudgetExceeded:
        result["status"] = "local_daily_budget_exhausted"
        return result
    except (OSError, TypeError, ValueError, sqlite3.Error):
        result["status"] = "local_budget_unavailable"
        return result

    result["requests_attempted"] = 1
    result["network_performed"] = True
    try:
        http, payload = (fetcher or _fetch)(URL, _params(query, tag, limit, window))
        if http in {429, 503}:
            result["status"] = "provider_rate_limited"
            try:
                store.cool_down(SOURCE_ID, 300)
            except (OSError, TypeError, ValueError, sqlite3.Error):
                pass
            return result
        if http != 200:
            result["status"] = "provider_unavailable"
            return result
        parsed = _parse(payload, tag=tag, window=window, limit=limit)
    except ResponseTooLarge:
        result["status"] = "response_too_large"
        return result
    except Exception:
        # Upstream error strings can include sensitive source URLs/content.
        result["status"] = "provider_unavailable"
        return result
    result.update(parsed)
    if parsed["status"] != "invalid_source_shape":
        result["summary"] = _summary(parsed["records"], tag)
        if tag != "comment":
            result["signals"] = _story_signals(
                records=parsed["records"], query=query, observed=observed,
            )
        try:
            store.save(key, {
                "query": query, "tag": tag, "limit": limit, "window": window,
                "observed_at": observed.isoformat(), **parsed,
            }, CACHE_TTL_SECONDS)
        except (OSError, TypeError, ValueError, sqlite3.Error):
            result["cache_write_failed"] = True
    return result


def format_hn_report(report: dict[str, Any]) -> str:
    rows = [
        f"HN ALGOLIA | {report['query']} | {report['tag']} | {report['status']}",
        f"Observed first-page {report['sort_order']} matches; "
        "not total discussions or validated market demand.",
        f"Requests: {report['requests_attempted']}"
        + (" (cached)" if report["cache_hit"] else ""),
        f"Distinct item IDs: {report['summary']['observed_items_on_returned_page']}; "
        f"threads: {report['summary']['distinct_discussion_threads_on_returned_page']}; "
        f"days: {report['summary']['distinct_utc_days_on_returned_page']}",
    ]
    for item in report["records"]:
        title = item["title"] or "(thread title unavailable)"
        rows.append(
            f"{item['utc_day']} | {item['kind']} | {title} | {item['hn_url']}"
        )
    return "\n".join(rows)
