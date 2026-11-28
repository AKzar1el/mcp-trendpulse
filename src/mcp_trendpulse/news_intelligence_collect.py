"""Explicit free-only collection of bounded news metadata.

Reuse the existing durable BudgetCache, atomic reservations, file lock and
no-redirect HTTP handler. No registry, scheduler, external key or paid service.
The provider-specific raw response is projected before any cache write.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from filelock import FileLock, Timeout as FileLockTimeout

from mcp_trendpulse.intelligence_core import (
    BudgetCache,
    DailyBudgetExceeded,
    IntelligenceError,
    SourceCoolingDown,
    _NoRedirect,
)
from mcp_trendpulse.news_intelligence_schema import (
    MAX_ARTICLES,
    MAX_BYTES,
    GdeltCoverage,
    NewsArticle,
    NewsBatch,
    _utc,
    gdelt_doc_request,
    nasa_rss_request,
    parse_gdelt_raw_timeline,
    parse_nasa_rss_capture,
    parse_news_capture,
)

_SOURCES = ("gdelt_articles", "gdelt_timeline", "nasa_rss")
# Conservative LOCAL limits, not promises of upstream capacity. Both DOC
# operations share a budget and a source-wide lock/cooldown.
_CAPS = {"gdelt_doc": 6, "nasa_rss": 4}
_TTL = {"gdelt_doc": 900, "nasa_rss": 300}
_MIN_GAP = 30
_CACHE_VERSION = "news_v4_collection_v1"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _plan(source, phrase, as_of, days, limit):
    if source not in _SOURCES or type(limit) is not int or not 1 <= limit <= MAX_ARTICLES:
        raise ValueError("Unsupported news source or limit")
    if source == "nasa_rss":
        if phrase is not None or as_of is not None or days is not None:
            raise ValueError("NASA is a recent-content feed, not keyword or historical search")
        request = nasa_rss_request()
        scope = {
            "coverage": "recent NASA-published content only", "query": None,
            "country_filter": None, "language_filter": None, "pagination": "none",
            "limit": limit,
        }
        family = "nasa_rss"
    else:
        end = (_now().replace(minute=0, second=0, microsecond=0).isoformat()
               if as_of is None else _utc(as_of))
        if datetime.fromisoformat(end) > _now():
            raise ValueError("Future query cutoff")
        days = 3 if days is None else days
        mode = "artlist" if source == "gdelt_articles" else "timelinevolraw"
        if source == "gdelt_timeline" and limit != 10:
            raise ValueError("Article limit does not apply to a timeline")
        request = gdelt_doc_request(phrase, as_of=end, days=days, limit=limit, mode=mode)
        scope = {
            "coverage": "GDELT monitored news, translated search, not all worldwide news",
            "query": phrase, "as_of": end, "days": days,
            "country_filter": None, "language_filter": None, "pagination": "none",
            "limit": limit if mode == "artlist" else None,
            "mode": mode,
        }
        family = "gdelt_doc"
    return {
        "source": source, "provider": family, "url": request["url"], "method": "GET",
        "scope": scope, "attribution": request["attribution"],
        "local_daily_cap": _CAPS[family],
        "retention_scope": "metadata_only", "paid_services_used": False,
    }


def _result(plan, status, *, attempted=False, cache_hit=False, reason=None,
            captured_at=None, evidence=None, http_status=None):
    return {
        **plan, "status": status, "reason": reason,
        "network_performed": attempted, "provider_requests": int(attempted),
        "retry_automatically": False, "cache_hit": cache_hit,
        "captured_at": captured_at, "http_status": http_status, "evidence": evidence,
    }


def _typed_evidence(plan, evidence, captured_at):
    # Revalidate even local cache data; never echo arbitrary cached fields.
    wire = json.dumps(evidence, ensure_ascii=False, allow_nan=False)
    if plan["source"] == "gdelt_timeline":
        value = GdeltCoverage.model_validate_json(wire)
        if any(datetime.fromisoformat(p.interval_at) > datetime.fromisoformat(captured_at)
               for p in value.points):
            raise ValueError("Future coverage interval")
    else:
        value = NewsBatch.model_validate_json(wire)
        if (value.provider != plan["provider"] or value.captured_at != captured_at
                or len(value.articles) > plan["scope"]["limit"]
                or any(a.capture_mode != "live" for a in value.articles)):
            raise ValueError("Cache provenance mismatch")
    return value


def _read_cache(plan, cached):
    if not isinstance(cached, dict) or set(cached) != {"plan", "captured_at", "evidence"}:
        raise ValueError("Invalid cache envelope")
    if cached["plan"] != plan:
        raise ValueError("Cache scope mismatch")
    capture = _utc(cached["captured_at"])
    if datetime.fromisoformat(capture) > _now():
        raise ValueError("Future cache capture")
    value = _typed_evidence(plan, cached["evidence"], capture)
    if value.status not in ("observed", "partial", "empty"):
        raise ValueError("Invalid cache status")
    return _result(plan, value.status, cache_hit=True, captured_at=capture,
                   evidence=value.model_dump(mode="json"))


def _retry_seconds(value):
    if isinstance(value, str) and len(value) <= 128:
        value = value.strip()
        if re.fullmatch(r"[0-9]{1,9}", value):
            return max(300, int(value))
        try:
            until = parsedate_to_datetime(value)
            if until.tzinfo is not None:
                return max(300, int((until - _now()).total_seconds()) + 1)
        except (ValueError, TypeError, OverflowError):
            pass
    return 300


def _project(plan, raw, captured_at):
    if plan["source"] == "gdelt_timeline":
        value = parse_gdelt_raw_timeline(raw)
    else:
        limit = plan["scope"]["limit"]
        if plan["source"] == "nasa_rss":
            value = parse_nasa_rss_capture(raw, captured_at=captured_at, limit=limit)
        else:
            value = parse_news_capture(raw, provider="gdelt_doc", captured_at=captured_at, limit=limit)
        # Only this actual transport path may mark a source capture as live.
        data = value.model_dump()
        data["articles"] = tuple(
            NewsArticle.model_validate({
                **a.model_dump(exclude={"article_id", "observation_id"}), "capture_mode": "live"
            }) for a in value.articles
        )
        value = NewsBatch.model_validate(data)
    return _typed_evidence(plan, value.model_dump(mode="json"), captured_at)


def _execute_locked(plan, store, key, timeout):
    try:
        cached = store.cached(key)
        if cached is not None:
            return _read_cache(plan, cached)
        family = plan["provider"]
        store.reserve(family, _CAPS[family], guard_cooldown=True)
        # Persist spacing before I/O, so a crashed process cannot immediately
        # repeat a request. The source lock remains held until I/O completes.
        store._extend_cooldown(family, _MIN_GAP)
    except SourceCoolingDown:
        return _result(plan, "unavailable", reason="provider_cooldown")
    except DailyBudgetExceeded:
        return _result(plan, "unavailable", reason="local_daily_budget_exhausted")
    except (OSError, ValueError, TypeError, sqlite3.Error):
        return _result(plan, "unavailable", reason="local_cache_or_budget_invalid")

    accept = ("application/rss+xml, application/xml, text/xml"
              if family == "nasa_rss" else "application/json")
    try:
        # The URL is generated by _plan, not supplied by a caller or response.
        request = Request(plan["url"], method="GET", headers={
            "User-Agent": "mcp-trendpulse-intelligence/0.1 (research; read-only)",
            "Accept": accept, "Accept-Encoding": "identity",
        })
        with build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=timeout) as response:
            mime = response.headers.get_content_type()
            raw = response.read(MAX_BYTES + 1)
            if response.status != 200 or len(raw) > MAX_BYTES:
                raise ValueError("Unexpected response status or size")
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise ValueError("Unsupported response encoding")
            if mime not in accept.split(", "):
                raise ValueError("Unexpected response content type")
        captured_at = _now().isoformat()
        value = _project(plan, raw, captured_at)
    except HTTPError as exc:
        reason = "provider_rate_limited" if exc.code == 429 else "provider_http_error"
        if exc.code in (429, 503):
            try:
                store._extend_cooldown(family, _retry_seconds(exc.headers.get("Retry-After", "") if exc.headers else ""))
            except (OSError, sqlite3.Error):
                reason = "local_cooldown_write_failed"
        return _result(plan, "unavailable", attempted=True, reason=reason, http_status=exc.code)
    except (URLError, TimeoutError, OSError):
        return _result(plan, "unavailable", attempted=True, reason="provider_transport_unavailable")
    except (ValueError, TypeError):
        return _result(plan, "invalid", attempted=True, reason="invalid_source_shape")

    evidence = value.model_dump(mode="json")
    result = _result(plan, value.status, attempted=True, captured_at=captured_at,
                     evidence=evidence, http_status=200,
                     reason=value.reason if isinstance(value, NewsBatch) else None)
    if value.status in ("observed", "partial", "empty"):
        try:
            store.save(key, {"plan": plan, "captured_at": captured_at, "evidence": evidence}, _TTL[family])
        except (OSError, ValueError, sqlite3.Error):
            result["cache_write_failed"] = True
    return result


def collect_news(source, *, phrase=None, as_of=None, days=None, limit=10,
                 execute=False, cache=None, timeout=12):
    """Plan by default. Explicit execution makes at most one source request."""
    if type(execute) is not bool or type(timeout) is not int or not 2 <= timeout <= 30:
        raise ValueError("Invalid execution or timeout")
    plan = _plan(source, phrase, as_of, days, limit)
    if not execute:
        return _result(plan, "planned")
    key = hashlib.sha256(json.dumps([_CACHE_VERSION, plan], sort_keys=True).encode()).hexdigest()
    try:
        store = cache if cache is not None else BudgetCache()
        cached = store.cached(key)
        if cached is not None:
            return _read_cache(plan, cached)
        lock_root = store.db.parent / ".request_locks"
        if lock_root.is_symlink():
            raise IntelligenceError("Unsafe lock directory")
        lock_root.mkdir(mode=0o700, exist_ok=True)
        lock_path = lock_root / ("news-v4-" + plan["provider"] + ".lock")
        if lock_path.is_symlink():
            raise IntelligenceError("Unsafe lock path")
        with FileLock(str(lock_path), timeout=0):
            return _execute_locked(plan, store, key, timeout)
    except FileLockTimeout:
        return _result(plan, "unavailable", reason="provider_local_concurrency_limit")
    except (OSError, ValueError, TypeError, sqlite3.Error):
        return _result(plan, "unavailable", reason="local_cache_or_budget_invalid")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=_SOURCES)
    parser.add_argument("--phrase")
    parser.add_argument("--as-of")
    parser.add_argument("--days", type=int)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        report = collect_news(args.source, phrase=args.phrase, as_of=args.as_of,
                              days=args.days, limit=args.limit, execute=args.execute)
    except ValueError:
        parser.error("Invalid source, phrase or time window")
    # ASCII JSON safely represents Unicode on terminals with legacy encodings.
    print(json.dumps(report, ensure_ascii=True, allow_nan=False))


if __name__ == "__main__":
    main()
