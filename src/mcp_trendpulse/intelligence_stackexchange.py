"""M11: bounded public Stack Overflow question evidence via Stack Exchange 2.3.

Provider search matching, unresolved questions and accepted answers are not
keyword search volume, confirmed customer pain, or paying developer counts.
Only a single keyless first page is fetched, with original durable quota.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import urlsplit

from mcp_trendpulse.intelligence_core import BudgetCache, DailyBudgetExceeded
from mcp_trendpulse.intelligence_signal import (
    SignalPeriod, SignalProvenance, TrendSignal,
)

SOURCE = "stackexchange_question_mentions"
URL = "https://api.stackexchange.com/2.3/search/advanced"
SITE = "stackoverflow"
UTC_DAILY_CAP = 3
MAX_RESULTS = 10
CACHE_SECONDS = 6 * 3600
ANCHOR_SECONDS = 6 * 3600
MAX_RESPONSE_BYTES = 128 * 1024
_MAX_EXACT = 2**53-1
_TAG = re.compile(r"[a-z0-9][a-z0-9.+#-]{0,34}\Z")
_TERM = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._+#-]{2,79}\Z")
_QUESTION_PATH = re.compile(r"/questions/([1-9]\d*)(?:/[^?#]*)?\Z")


class ResponseTooLarge(RuntimeError):
    """An upstream response exceeded its documented local byte cap."""


def _tag(value: Any) -> str:
    if not isinstance(value, str) or _TAG.fullmatch(value) is None or ".." in value:
        raise ValueError("Supply one exact lowercase Stack Overflow technology tag")
    return value


def _term(value: Any) -> str:
    if not isinstance(value, str) or value and _TERM.fullmatch(value) is None:
        raise ValueError("Question phrase must be empty or a safe printable literal")
    return value


def _window(days: int, observed: datetime) -> dict[str, Any]:
    if type(days) is not int or not 7 <= days <= 30:
        raise ValueError("Stack Exchange recent search accepts 7-30 UTC days")
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("Timezone is required for a dated source observation")
    seconds = int(observed.astimezone(timezone.utc).timestamp())
    anchor = seconds // ANCHOR_SECONDS * ANCHOR_SECONDS
    start = anchor-days*86400
    if start <= 0:
        raise ValueError("Invalid Stack Exchange observation window")
    return {
        "start_epoch_inclusive": start,
        "end_epoch_exclusive": anchor,
        "days": days,
        "end_utc": datetime.fromtimestamp(anchor, tz=timezone.utc).isoformat(),
    }


def _params(tag: str, term: str, limit: int, window: dict[str, Any]) -> dict[str, str]:
    result = {
        "site": SITE, "tagged": tag, "sort": "creation", "order": "desc",
        "page": "1", "pagesize": str(limit),
        "fromdate": str(window["start_epoch_inclusive"]),
        "todate": str(window["end_epoch_exclusive"]-1),
    }
    if term:
        result["q"] = term
    return result


def _key(tag: str, term: str, limit: int, window: dict[str, Any]) -> str:
    data = json.dumps(
        ["mjau_stackexchange_v1", tag, term, limit, window],
        separators=(",", ":"), sort_keys=True, ensure_ascii=False,
    )
    return "mjau_se:" + hashlib.sha256(data.encode("utf-8")).hexdigest()


def _integer(raw: Any, *, allow_negative: bool = False) -> int | None:
    if type(raw) is not int or abs(raw) > _MAX_EXACT:
        return None
    if raw < 0 and not allow_negative:
        return None
    return raw


def _record(raw: Any, *, tag: str, term: str, window: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    question_id = _integer(raw.get("question_id"))
    answers = _integer(raw.get("answer_count"))
    created = _integer(raw.get("creation_date"))
    answered = raw.get("is_answered")
    tags = raw.get("tags")
    title_raw = raw.get("title")
    if (
        question_id is None or question_id == 0
        or answers is None or created is None
        or type(answered) is not bool or not isinstance(tags, list)
        or tag not in tags or len(tags) > 15 or any(
            not isinstance(t, str) or len(t) > 40 for t in tags
        )
        or not isinstance(title_raw, str)
        or not window["start_epoch_inclusive"] <= created
               < window["end_epoch_exclusive"]
    ):
        return None
    title = html.unescape(title_raw)
    if (
        not 2 <= len(title) <= 180
        or title != title.strip()
        or any(ord(c) < 32 or ord(c) == 127 for c in title)
    ):
        return None
    link = raw.get("link")
    if not isinstance(link, str):
        return None
    try:
        parts = urlsplit(link)
        port = parts.port
    except ValueError:
        return None
    match = _QUESTION_PATH.fullmatch(parts.path)
    if (
        parts.scheme != "https" or parts.hostname != "stackoverflow.com"
        or parts.username or parts.password or port is not None
        or parts.query or parts.fragment
        or match is None or int(match.group(1)) != question_id
    ):
        return None
    accepted_raw = raw.get("accepted_answer_id")
    if accepted_raw is not None and (
        _integer(accepted_raw) in (None, 0) or answers == 0
    ):
        return None
    score = raw.get("score")
    views = raw.get("view_count")
    if score is not None and _integer(score, allow_negative=True) is None:
        return None
    if views is not None and _integer(views) is None:
        return None
    if answered and answers == 0:
        return None
    dt = datetime.fromtimestamp(created, tz=timezone.utc)
    return {
        "question_id": question_id,
        "source_url": f"https://stackoverflow.com/questions/{question_id}",
        "created_at": dt.isoformat(),
        "utc_day": dt.date().isoformat(),
        "title": title,
        "tag": tag,
        "answer_count": answers,
        "is_answered": answered,
        "has_accepted_answer": accepted_raw is not None,
        "accepted_answer_id": accepted_raw,
        "score": score,
        "view_count": views,
        "title_contains_exact_phrase": bool(term and term.casefold() in title.casefold()),
    }


def _report_data(payload: Any, *, tag: str, term: str, limit: int,
                 window: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or (
        any(key in payload for key in ("error_id", "error_name", "error_message"))
    ):
        return {"status": "provider_error"}
    items = payload.get("items")
    has_more = payload.get("has_more")
    remaining = payload.get("quota_remaining")
    maximum = payload.get("quota_max")
    backoff = payload.get("backoff")
    if (
        not isinstance(items, list) or len(items) > limit
        or type(has_more) is not bool
        or _integer(remaining) is None
        or maximum is not None and (
            _integer(maximum) is None or maximum < remaining
        )
        or backoff is not None and (
            _integer(backoff) is None or backoff > 7*86400
        )
    ):
        return {"status": "invalid_source_shape"}
    rows = []
    ids = set()
    rejected = 0
    for raw in items:
        record = _record(raw, tag=tag, term=term, window=window)
        if record is None or record["question_id"] in ids:
            rejected += 1
            continue
        ids.add(record["question_id"])
        rows.append(record)
    rows.sort(key=lambda r: (r["created_at"], r["question_id"]), reverse=True)
    if not rows and items:
        status = "invalid_source_shape"
    elif not rows and has_more:
        status = "invalid_source_shape"
    elif not rows:
        status = "no_data"
    elif has_more or rejected:
        status = "observed_partial"
    else:
        status = "observed"
    return {
        "status": status,
        "questions": rows,
        "source_rows_received": len(items),
        "source_rows_rejected": rejected,
        "has_more": has_more,
        "quota_remaining": remaining,
        "quota_max": maximum,
        "backoff_seconds": backoff,
    }


def _cached(
    cached: Any, *, tag: str, term: str, limit: int,
    window: dict[str, Any], observed: datetime,
) -> tuple[dict[str, Any], datetime] | None:
    if not isinstance(cached, dict) or any(
        cached.get(k) != v for k, v in (
            ("tag", tag), ("term", term), ("limit", limit),
            ("window", window), ("source", SOURCE),
        )
    ):
        return None
    try:
        at = datetime.fromisoformat(cached["observed_at"])
        if at.tzinfo is None or at.utcoffset() is None:
            return None
        at = at.astimezone(timezone.utc)
        if at > observed or at < observed-timedelta(hours=7):
            return None
    except (KeyError, TypeError, ValueError):
        return None
    status = cached.get("status")
    questions = cached.get("questions")
    received, rejected = cached.get("source_rows_received"), cached.get(
        "source_rows_rejected",
    )
    remaining, maximum = cached.get("quota_remaining"), cached.get("quota_max")
    backoff = cached.get("backoff_seconds")
    has_more = cached.get("has_more")
    if (
        status not in ("observed", "observed_partial", "no_data")
        or not isinstance(questions, list) or len(questions) > limit
        or type(received) is not int or type(rejected) is not int
        or not 0 <= rejected <= received <= limit
        or type(has_more) is not bool
        or _integer(remaining) is None
        or maximum is not None and (
            _integer(maximum) is None or maximum < remaining
        )
        or backoff is not None and (
            _integer(backoff) is None or backoff > 7*86400
        )
    ):
        return None
    rows = []
    ids = set()
    for item in questions:
        if not isinstance(item, dict):
            return None
        qid = _integer(item.get("question_id"))
        if qid in (None, 0) or qid in ids:
            return None
        dt_raw = item.get("created_at")
        try:
            dt = datetime.fromisoformat(dt_raw)
            if dt.tzinfo is None or dt.utcoffset() is None:
                return None
            dt = dt.astimezone(timezone.utc)
        except (ValueError, TypeError):
            return None
        checked = _record({
            "question_id": qid,
            "answer_count": item.get("answer_count"),
            "creation_date": int(dt.timestamp()),
            "is_answered": item.get("is_answered"),
            "tags": [tag],
            "title": item.get("title"),
            "link": f"https://stackoverflow.com/questions/{qid}",
            "accepted_answer_id": item.get("accepted_answer_id"),
            "score": item.get("score"),
            "view_count": item.get("view_count"),
        }, tag=tag, term=term, window=window)
        if (
            checked is None or item.get("source_url") != checked["source_url"]
            or item.get("utc_day") != checked["utc_day"]
            or item.get("tag") != tag
            or item.get("title_contains_exact_phrase") != checked[
                "title_contains_exact_phrase"
            ]
        ):
            return None
        rows.append(checked)
        ids.add(qid)
    if (
        len(rows)+rejected != received
        or status == "no_data" and (rows or has_more or received)
        or status == "observed" and (not rows or has_more or rejected)
        or status == "observed_partial" and (
            not rows or not (has_more or rejected)
        )
    ):
        return None
    rows.sort(key=lambda r: (r["created_at"], r["question_id"]), reverse=True)
    return {
        "status": status, "questions": rows, "source_rows_received": received,
        "source_rows_rejected": rejected, "has_more": has_more,
        "quota_remaining": remaining, "quota_max": maximum,
        "backoff_seconds": backoff,
    }, at


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "distinct_questions_first_page": len(rows),
        "distinct_utc_creation_days": len({r["utc_day"] for r in rows}),
        "without_answer_first_page": sum(not r["is_answered"] for r in rows),
        "with_answer_first_page": sum(r["is_answered"] for r in rows),
        "with_accepted_answer_first_page": sum(
            r["has_accepted_answer"] for r in rows
        ),
        "per_utc_day": [
            {"utc_day": day, "question_count": n}
            for day, n in sorted(Counter(r["utc_day"] for r in rows).items())
        ],
        "unique_developers_verified": False,
        "customer_demand_verified": False,
        "search_volume_verified": False,
    }


def _signals(rows: list[dict[str, Any]], *, tag: str, term: str,
             observed: datetime) -> list[dict[str, Any]]:
    days = Counter(r["utc_day"] for r in rows)
    return [
        TrendSignal(
            source_id=SOURCE, source_url=URL, observed_at=observed,
            country=None, language=None,
            raw_term=term or tag, normalized_term=(term or tag).casefold(),
            metric_type=SOURCE, metric_unit="questions",
            period=SignalPeriod(
                start_date=day, end_date=day, granularity="daily",
            ),
            value=count, coverage_status="partial",
            sampling_scope=(
                "First page of Stack Overflow questions filtered by one tag; "
                "partial search index, not total users or keyword volume"
            ),
            provenance=SignalProvenance(
                method="public_api",
                source_record_id=f"stackoverflow:{tag}:{day}",
                sampling_basis="first_page_question_id_utc_created_day",
                is_observed_search_query=False,
            ),
        ).model_dump(mode="json")
        for day, count in sorted(days.items())
    ]


def _durable_hold(store: Any, seconds: int) -> None:
    if not seconds:
        return
    until = time.time() + seconds
    with store._connect() as conn:
        conn.execute(
            "INSERT INTO cooldown(source, until) VALUES (?, ?) "
            "ON CONFLICT(source) DO UPDATE SET until=MAX(until, excluded.until)",
            (SOURCE, until),
        )


def _http_get(url: str, params: dict[str, str]) -> tuple[int, Any]:
    import requests

    if url != URL:
        raise ValueError("Unapproved Stack Exchange endpoint")
    session = requests.Session()
    session.trust_env = False
    try:
        with session.get(
            url, params=params, timeout=(5, 12),
            allow_redirects=False, stream=True,
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    "mcp-trendpulse/0.2 "
                    "(https://github.com/AKzar1el/mcp-trendpulse)"
                ),
            },
        ) as response:
            code = response.status_code
            if code != 200 or "json" not in response.headers.get(
                "Content-Type", "",
            ).lower():
                return code, None
            raw = response.raw.read(MAX_RESPONSE_BYTES+1, decode_content=True)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ResponseTooLarge()
            try:
                return code, json.loads(raw)
            except (UnicodeError, ValueError):
                return code, None
    finally:
        session.close()


def discover_stackoverflow_questions(
    *, tag: str, term: str = "", days: int = 14, limit: int = 10,
    execute: bool = False, cache: Any = None,
    fetcher: Callable[[str, dict[str, str]], tuple[int, Any]] | None = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """One opt-in Stack Overflow first-page question search, never a census."""
    tag = _tag(tag)
    term = _term(term)
    if type(execute) is not bool or type(limit) is not int or not 1 <= limit <= MAX_RESULTS:
        raise ValueError("Execute must be boolean; limit must be 1-10")
    observed = observed_at or datetime.now(timezone.utc)
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("Observed timestamp must carry an explicit timezone")
    observed = observed.astimezone(timezone.utc)
    window = _window(days, observed)
    result: dict[str, Any] = {
        "mode": "stackexchange_stackoverflow_recent_questions",
        "source": SOURCE, "source_url": URL, "site": SITE,
        "status": "planned" if not execute else "unavailable",
        "tag": tag, "term": term, "term_is_manual_phrase": bool(term),
        "window": window, "limit": limit, "page": 1,
        "sort_order": "creation_desc", "observed_at": observed.isoformat(),
        "country": None, "language": None,
        "requests_attempted": 0, "network_performed": False,
        "cache_hit": False, "local_utc_daily_request_cap": UTC_DAILY_CAP,
        "source_rows_received": 0, "source_rows_rejected": 0,
        "has_more": None, "quota_remaining": None, "quota_max": None,
        "backoff_seconds": None,
        "questions": [], "signals": [], "summary": _summary([]),
        "independent_customers_verified": False,
        "search_volume_verified": False, "paid_services_used": False,
    }
    if not execute:
        return result
    try:
        store = cache if cache is not None else BudgetCache()
        key = _key(tag, term, limit, window)
        previous = _cached(
            store.cached(key), tag=tag, term=term, limit=limit,
            window=window, observed=observed,
        )
        if previous is not None:
            parsed, saved_at = previous
            result.update(parsed)
            result["cache_hit"] = True
            result["observed_at"] = saved_at.isoformat()
            result["summary"] = _summary(parsed["questions"])
            result["signals"] = _signals(
                parsed["questions"], tag=tag, term=term, observed=saved_at,
            )
            return result
        if store.blocked(SOURCE):
            result["status"] = "provider_cooldown"
            return result
        store.reserve(SOURCE, UTC_DAILY_CAP)
    except DailyBudgetExceeded:
        result["status"] = "local_daily_budget_exhausted"
        return result
    except (OSError, TypeError, ValueError, sqlite3.Error):
        result["status"] = "local_budget_unavailable"
        return result

    result["requests_attempted"] = 1
    result["network_performed"] = True
    try:
        http, payload = (fetcher or _http_get)(URL, _params(tag, term, limit, window))
        if http in (429, 503):
            result["status"] = "provider_rate_limited"
            try:
                _durable_hold(store, 300)
            except (OSError, TypeError, ValueError, sqlite3.Error):
                result["status"] = "local_cooldown_unavailable"
            return result
        if http != 200:
            result["status"] = "provider_unavailable"
            return result
        parsed = _report_data(payload, tag=tag, term=term, limit=limit, window=window)
    except ResponseTooLarge:
        result["status"] = "response_too_large"
        return result
    except Exception:
        result["status"] = "provider_unavailable"
        return result
    backoff = payload.get("backoff") if isinstance(payload, dict) else None
    if type(backoff) is int and 0 < backoff <= 7*86400:
        # Honor provider backoff even if its wrapper is an error/invalid
        # payload, before considering any retry. No automatic retries.
        try:
            _durable_hold(store, backoff)
        except (OSError, TypeError, ValueError, sqlite3.Error):
            result["status"] = "local_cooldown_unavailable"
            return result
    if parsed["status"] not in ("observed", "observed_partial", "no_data"):
        result["status"] = parsed["status"]
        return result
    try:
        if parsed["quota_remaining"] == 0:
            next_utc = datetime.combine(
                (datetime.now(timezone.utc) + timedelta(days=1)).date(),
                datetime.min.time(), tzinfo=timezone.utc,
            )
            _durable_hold(
                store, max(60, int((next_utc-datetime.now(timezone.utc)).total_seconds())+2),
            )
    except (OSError, TypeError, ValueError, sqlite3.Error):
        result["status"] = "local_cooldown_unavailable"
        return result
    result.update(parsed)
    result["summary"] = _summary(parsed["questions"])
    result["signals"] = _signals(
        parsed["questions"], tag=tag, term=term, observed=observed,
    )
    compact = {
        "source": SOURCE, "tag": tag, "term": term,
        "limit": limit, "window": window,
        "observed_at": observed.isoformat(), **parsed,
    }
    try:
        store.save(key, compact, CACHE_SECONDS)
    except (OSError, TypeError, ValueError, sqlite3.Error):
        result["cache_write_failed"] = True
    return result


def format_stackexchange_report(report: dict[str, Any]) -> str:
    lines = [
        f"STACK OVERFLOW | {report['tag']} | {report['status']}",
        "Public first-page questions, not buyers or total keyword search volume.",
        f"Requests {report['requests_attempted']}"
        + (" (cache hit)" if report["cache_hit"] else ""),
        f"Distinct sampled questions: {report['summary']['distinct_questions_first_page']}",
    ]
    for question in report["questions"]:
        lines.append(
            f"{question['utc_day']} | {question['question_id']} | "
            f"{question['title']} | {question['source_url']}"
        )
    return "\n".join(lines)
