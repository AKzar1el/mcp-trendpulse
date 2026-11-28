"""V4.07: bounded news investigation, plan-first and free-only.

Reuse existing collectors, headline provider, extraction and offline analysis.
No MCP registration, paid dependency, automatic retries or background polling.
"""
from __future__ import annotations

import argparse
import asyncio
import html
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock, Timeout as FileLockTimeout

from mcp_trendpulse.config import get_google_news_country, get_google_news_language
from mcp_trendpulse.errors import ProviderRateLimitError, ProviderTimeoutError
from mcp_trendpulse.intelligence_core import BudgetCache, DailyBudgetExceeded, SourceCoolingDown
from mcp_trendpulse.news_intelligence_collect import collect_news
from mcp_trendpulse.news_intelligence_coverage import summarize_gdelt_coverage, summarize_news_snapshot
from mcp_trendpulse.news_intelligence_dedup import MAX_OBSERVATIONS, analyze_news_duplicates
from mcp_trendpulse.news_intelligence_extract import extract_article
from mcp_trendpulse.news_intelligence_schema import (
    MAX_ARTICLES, MAX_BYTES, NewsArticle, NewsBatch, _digest, _text, _utc, parse_news_capture,
)

SOURCES = ("google_news_rss", "gdelt_articles", "gdelt_timeline", "nasa_rss")
DEFAULT_SOURCES = ("google_news_rss", "nasa_rss")
_GOOGLE_BUDGET = "google_news_rss"
_GOOGLE_DAILY_CAP = 6
_GOOGLE_TTL = 300
_MAX_IMPORTS = 4
_MAX_EXTRACTIONS = 2
_GOOGLE_ATTRIBUTION = "Google News RSS (https://news.google.com/)"
_OK = frozenset({"observed", "partial", "empty"})


def _now():
    return datetime.now(timezone.utc)


def _google_plan(phrase, days, limit):
    country, language = get_google_news_country(), get_google_news_language()
    if not re.fullmatch(r"[A-Z]{2}", country) or not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})?", language):
        raise ValueError("Unsupported configured Google News edition")
    return {
        "source": "google_news_rss", "provider": "google_news_rss",
        "scope": {"query": phrase, "days": days, "limit": limit, "configured_country": country,
                  "configured_language": language, "coverage": "legacy filtered headline sample"},
        "attribution": _GOOGLE_ATTRIBUTION, "local_daily_cap": _GOOGLE_DAILY_CAP,
        "retention_scope": "metadata_only", "method": "existing_keyword_rss_provider",
    }


def _google_result(plan, status, *, batch=None, reason=None, attempted=False, cached=False):
    return {**plan, "status": status, "reason": reason, "network_performed": attempted,
            "provider_requests": int(attempted), "cache_hit": cached, "retry_automatically": False,
            "captured_at": batch.captured_at if batch else None,
            "evidence": batch.model_dump(mode="json") if batch else None}


def _read_google_cache(plan, value):
    if not isinstance(value, dict) or set(value) != {"plan", "batch"} or value["plan"] != plan:
        raise ValueError("Cache scope mismatch")
    batch = NewsBatch.model_validate_json(json.dumps(value["batch"], allow_nan=False))
    if (batch.provider != "google_news_rss" or batch.status not in ("observed", "partial")
            or not batch.captured_at or datetime.fromisoformat(batch.captured_at) > _now()
            or len(batch.articles) > plan["scope"]["limit"]
            or any(a.capture_mode != "live" for a in batch.articles)):
        raise ValueError("Invalid Google News cache evidence")
    return _google_result(plan, batch.status, batch=batch, cached=True)


async def _google_collect(plan, cache):
    key = _digest(["news_investigation_google_v1", plan])
    try:
        store = cache if cache is not None else BudgetCache()
        cached = store.cached(key)
        if cached is not None:
            return _read_google_cache(plan, cached)
        root = store.db.parent / ".request_locks"
        if root.is_symlink():
            raise ValueError("Unsafe lock root")
        root.mkdir(mode=0o700, exist_ok=True)
        lock = root / "news-v4-google_news_rss.lock"
        if lock.is_symlink():
            raise ValueError("Unsafe lock path")
        with FileLock(str(lock), timeout=0):
            cached = store.cached(key)
            if cached is not None:
                return _read_google_cache(plan, cached)
            store.reserve(_GOOGLE_BUDGET, _GOOGLE_DAILY_CAP, guard_cooldown=True)
            # Existing worker has a 30-second caller deadline; do not overlap
            # immediate new operations after a timeout or cancellation.
            store._extend_cooldown(_GOOGLE_BUDGET, 60)
            return await _google_fetch(plan, store, key)
    except SourceCoolingDown:
        return _google_result(plan, "unavailable", reason="provider_cooldown")
    except DailyBudgetExceeded:
        return _google_result(plan, "unavailable", reason="local_daily_budget_exhausted")
    except FileLockTimeout:
        return _google_result(plan, "unavailable", reason="provider_local_concurrency_limit")
    except (OSError, ValueError, TypeError, sqlite3.Error):
        return _google_result(plan, "unavailable", reason="local_cache_or_budget_invalid")


async def _google_fetch(plan, store, key):
    scope = plan["scope"]
    try:
        from mcp_trendpulse.providers import get_provider_set

        if _google_plan(scope["query"], scope["days"], scope["limit"]) != plan:
            return _google_result(plan, "unavailable", reason="edition_changed")
        rows = await get_provider_set().news.get_rss_headlines_by_keyword(
            keyword=scope["query"], period=scope["days"], max_results=scope["limit"],
        )
        captured = _now().isoformat()
    except ProviderRateLimitError:
        try:
            store._extend_cooldown(_GOOGLE_BUDGET, 300)
        except (OSError, sqlite3.Error):
            return _google_result(plan, "unavailable", reason="local_cooldown_write_failed", attempted=True)
        return _google_result(plan, "unavailable", reason="provider_rate_limited", attempted=True)
    except ProviderTimeoutError:
        return _google_result(plan, "unavailable", reason="provider_timeout", attempted=True)
    except Exception:
        # Provider exceptions can contain sensitive or untrusted text.
        return _google_result(plan, "unavailable", reason="provider_unavailable", attempted=True)
    if not isinstance(rows, list) or len(rows) > MAX_ARTICLES:
        return _google_result(plan, "invalid", reason="invalid_source_shape", attempted=True)
    if not rows:
        # The legacy provider may filter all input rows or swallow upstream
        # absence. No raw response count/HTTP receipt is available here.
        return _google_result(plan, "unavailable", reason="legacy_empty_or_unavailable", attempted=True)
    try:
        raw = json.dumps(rows, allow_nan=False, ensure_ascii=False).encode("utf-8")
        if len(raw) > MAX_BYTES:
            raise ValueError("Oversized headline projection")
        batch = parse_news_capture(raw, provider="google_news_rss", captured_at=captured, limit=scope["limit"])
        data = batch.model_dump()
        data["articles"] = tuple(
            NewsArticle.model_validate({**a.model_dump(exclude={"article_id", "observation_id"}), "capture_mode": "live"})
            for a in batch.articles
        )
        batch = NewsBatch.model_validate(data)
    except (ValueError, TypeError, OverflowError):
        return _google_result(plan, "invalid", reason="invalid_source_shape", attempted=True)
    result = _google_result(plan, batch.status, batch=batch, reason=batch.reason, attempted=True)
    if batch.status in ("observed", "partial"):
        try:
            store.save(key, {"plan": plan, "batch": batch.model_dump(mode="json")}, _GOOGLE_TTL)
        except (OSError, ValueError, sqlite3.Error):
            result["cache_write_failed"] = True
    return result


def _plan_sources(phrase, sources, days, limit, timeline_as_of):
    _text(phrase, 120)
    if not all(c.isalnum() or c in " -" for c in phrase) or not any(c.isalpha() for c in phrase):
        raise ValueError("Use a bounded literal query phrase")
    if (not isinstance(sources, (list, tuple)) or len(sources) > len(SOURCES)
            or any(not isinstance(s, str) or s not in SOURCES for s in sources)
            or len(set(sources)) != len(sources)):
        raise ValueError("Invalid or repeated source selection")
    if type(days) is not int or not 1 <= days <= 30 or type(limit) is not int or not 1 <= limit <= MAX_ARTICLES:
        raise ValueError("Invalid query bounds")
    # Freeze one GDELT window for both modes; recent RSS feeds are not historical.
    if timeline_as_of is not None and not any(s.startswith("gdelt_") for s in sources):
        raise ValueError("GDELT cutoff requires a selected GDELT source")
    end = (_now().replace(minute=0, second=0, microsecond=0).isoformat()
           if timeline_as_of is None else _utc(timeline_as_of))
    plans = []
    for source in SOURCES:
        if source not in sources:
            continue
        if source == "google_news_rss":
            plans.append(_google_plan(phrase, days, limit))
        else:
            kwargs = {"limit": limit} if source == "nasa_rss" else {
                "phrase": phrase, "days": days, "as_of": end,
                "limit": 10 if source == "gdelt_timeline" else limit,
            }
            plans.append(collect_news(source, **kwargs))
    return plans


def _batch_from_result(result):
    provider, attribution = result["provider"], result["attribution"]
    payload = result.get("evidence")
    if payload is not None:
        try:
            batch = NewsBatch.model_validate_json(json.dumps(payload, allow_nan=False))
            if (batch.provider != provider or batch.attribution != attribution
                    or batch.status != result["status"] or batch.captured_at != result["captured_at"]):
                raise ValueError("Source receipt mismatch")
            return batch
        except (ValueError, TypeError, KeyError):
            return NewsBatch(provider=provider, attribution=attribution, status="invalid",
                             captured_at=None, reason="invalid_payload")
    invalid = result["status"] == "invalid"
    return NewsBatch(provider=provider, attribution=attribution, captured_at=None,
                     status="invalid" if invalid else "unavailable",
                     reason="invalid_payload" if invalid else "provider_unavailable")


def _receipt(result, plan):
    # Only known transport metadata is exposed. No raw provider error payload.
    return {
        "source": plan["source"], "provider": plan["provider"], "scope": plan["scope"],
        "attribution": plan["attribution"], "status": result["status"],
        "reason": result.get("reason"), "captured_at": result.get("captured_at"),
        "cache_hit": result.get("cache_hit", False),
        "provider_requests": result.get("provider_requests", 0),
        "network_performed": result.get("network_performed", False),
        "http_status": result.get("http_status"),
        "citation_url": plan.get("url"),
    }


def _safe_imports(batches):
    if not isinstance(batches, (list, tuple)) or len(batches) > _MAX_IMPORTS:
        raise ValueError("Invalid import batch selection")
    imported = []
    for batch in batches:
        if not isinstance(batch, NewsBatch):
            raise ValueError("Expected typed saved news batch")
        try:
            imported.append(NewsBatch.model_validate_json(batch.model_dump_json()))
        except (ValueError, TypeError):
            raise ValueError("Invalid saved news batch") from None
    return imported


async def investigate_news(phrase, *, sources=DEFAULT_SOURCES, days=3, limit=10,
                           execute=False, extract_limit=0, imported_batches=(), cache=None,
                           timeline_as_of=None):
    """Compose one bounded investigation; defaults to zero provider operations.

    Google and GDELT article lists are query-scoped samples; NASA is explicitly
    recent context. Imports have unknown query scope. Neither proves relevance,
    independent corroboration, demand or verified event occurrence.
    """
    if type(execute) is not bool or type(extract_limit) is not int or not 0 <= extract_limit <= _MAX_EXTRACTIONS:
        raise ValueError("Invalid execution or extraction budget")
    if extract_limit and not execute:
        raise ValueError("Extraction requires explicit execution")
    plans = _plan_sources(phrase, sources, days, limit, timeline_as_of)
    imported = _safe_imports(imported_batches)
    article_sources = sum(p["source"] != "gdelt_timeline" for p in plans)
    # Validate the worst-case analysis budget before any I/O, even if sources fail.
    if sum(len(b.articles) for b in imported) + article_sources * limit > MAX_OBSERVATIONS:
        raise ValueError("Investigation observation budget exceeded")
    if any(b.captured_at and datetime.fromisoformat(b.captured_at) > _now() for b in imported):
        raise ValueError("Imported capture in the future")

    receipts, topical, context = [], [], []
    timeline = None
    for plan in plans:
        source = plan["source"]
        if not execute:
            receipts.append(_receipt({**plan, "status": "planned"}, plan))
            continue
        if source == "google_news_rss":
            result = await _google_collect(plan, cache)
        else:
            scope = plan["scope"]
            kwargs = {"limit": limit} if source == "nasa_rss" else {
                "phrase": phrase, "days": scope["days"], "as_of": scope["as_of"],
                "limit": 10 if source == "gdelt_timeline" else limit,
            }
            result = await asyncio.to_thread(collect_news, source, execute=True, cache=cache, **kwargs)
        receipt = _receipt(result, plan)
        if source == "gdelt_timeline":
            try:
                timeline = summarize_gdelt_coverage(result)
            except ValueError:
                receipt.update(status="invalid", reason="invalid_timeline_receipt")
        else:
            batch = _batch_from_result(result)
            if batch.status != result["status"]:
                receipt.update(status=batch.status, reason="invalid_article_receipt")
            (context if source == "nasa_rss" else topical).append(batch)
        receipts.append(receipt)

    topical_rows = {a.observation_id: a for b in topical for a in b.articles}
    extractions = []
    # Select deterministic topical observations only. Don't follow canonical
    # hints or fetch contextual/imported links implicitly.
    extraction_targets = sorted(topical_rows.values(), key=lambda a: a.observation_id)
    hosts = set()
    if extract_limit:
        from urllib.parse import urlsplit

        for article in extraction_targets:
            host = urlsplit(article.reported_url).hostname
            if host in hosts:
                continue
            hosts.add(host)
            result = await extract_article(article, execute=True)
            extractions.append(result)
            if len(extractions) >= extract_limit or result.reason in ("http_rate_limited", "http_access_denied", "http_payment_required"):
                break

    cutoff = _now().isoformat()
    batches = topical + context + imported
    observations = {a.observation_id: a for b in batches for a in b.articles}
    snapshot = summarize_news_snapshot(batches, as_of=cutoff) if batches else None
    topical_snapshot = summarize_news_snapshot(topical, as_of=cutoff) if topical else None
    dedup = analyze_news_duplicates(list(observations.values()), extractions=extractions) if batches else None
    citations = []
    for index, oid in enumerate(sorted(observations), start=1):
        row = observations[oid]
        memberships = [name for name, group in (
            ("query_scoped_sample", topical), ("recent_context", context), ("imported_unscoped", imported)
        ) if any(a.observation_id == oid for b in group for a in b.articles)]
        citations.append({"citation_id": f"N{index}", "observation_id": oid, "title": row.title,
                          "url": row.reported_url, "provider": row.discovery_provider,
                          "publisher_label": row.publisher_label, "scope": memberships})
    if not execute:
        state = "offline_replay" if imported else "planned"
    else:
        accepted = [r for r in receipts if r["status"] in _OK]
        state = ("unavailable" if not accepted else "partial" if len(accepted) != len(receipts)
                 or any(r["status"] == "partial" for r in receipts)
                 or (snapshot is not None and snapshot["status"] == "partial")
                 or any(e.status != "extracted" for e in extractions)
                 else "observed")
    return {
        "schema_version": 1, "method": "news_investigation_v1",
        "run_id": _digest([phrase, cutoff, receipts, sorted(observations)]),
        "query": phrase, "as_of": cutoff, "status": state,
        "execute_requested": execute, "paid_services_used": False,
        "budget": {"selected_source_operations": len(plans), "article_limit_per_source": limit,
                   "max_extraction_operations": extract_limit, "automatic_retries": False,
                   "provider_operations_attempted": sum(r["provider_requests"] for r in receipts),
                   "extraction_operations_attempted": len(extractions),
                   "extraction_http_request_count": None if extractions else 0},
        "source_receipts": receipts, "import_count": len(imported),
        "topical_sample": topical_snapshot, "all_sample_and_context": snapshot,
        "coverage_timeline": timeline, "duplicate_evidence": dedup,
        "extraction_receipts": [e.model_dump(mode="json") for e in extractions],
        "citations": citations, "claim_verification": "not_performed",
        "limitations": [
            "News attention is not search demand, adoption, sales, causation or proof of occurrence.",
            "Query-scoped results are sampled reports, not a relevance or completeness guarantee.",
            "NASA is recent unfiltered context; imported captures have unknown query scope.",
            "Legacy Google News counts describe filtered returned rows, not upstream raw coverage; empty is ambiguous.",
            "A GDELT source-wide cooldown can defer a second selected mode; no waiting or automatic retries.",
            "Extraction is explicitly optional, bounded in operations (not individual redirects/HTTP requests), and returns no body.",
            "Candidate event and shared-text relations do not establish independent sources. No claim verification is performed.",
        ],
    }


def _md(value):
    # Untrusted headlines/publisher labels are inert Markdown text, not headings,
    # HTML, images or links. URLs are rendered as escaped text, not fetched.
    value = html.escape(str(value), quote=True)
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~\-])", r"\\\1", value)


def _number(value):
    return "unknown" if value is None else str(value)


def format_investigation_markdown(report):
    lines = ["# News investigation", "", "Query: " + _md(report["query"]),
             "Status: " + _md(report["status"]), "As of (UTC): " + _md(report["as_of"]), "",
             "## Source outcomes", ""]
    for receipt in report["source_receipts"]:
        line = "- " + _md(receipt["source"]) + ": " + _md(receipt["status"])
        if receipt["reason"]:
            line += " (" + _md(receipt["reason"]) + ")"
        if receipt["cache_hit"]:
            line += "; cached capture"
        lines.append(line)
    lines.extend(["", "## Query-scoped sample", ""])
    sample = report["topical_sample"]
    if sample is None:
        lines.append("No query-scoped sample was collected.")
    else:
        lines.extend(["- Provider-scoped article keys: " + _number(sample["provider_scoped_article_keys"]),
                      "- Candidate events (not verified): " + _number(sample["event_candidate_count"]),
                      "- Independent sources: unknown"])
    coverage = report["coverage_timeline"]
    if coverage is not None:
        lines.extend(["", "## GDELT monitored coverage", "",
                      "Status: " + _md(coverage["status"]),
                      "Weighted share over returned intervals (%): " + _number(coverage["weighted_coverage_pct"])])
    lines.extend(["", "## Source citations (reported headlines; not verified claims)", ""])
    for item in report["citations"]:
        lines.append("- [" + item["citation_id"] + "] " + _md(item["title"]) + " — "
                     + _md(item["provider"]) + " / " + _md(", ".join(item["scope"])))
        lines.append("  URL: " + _md(item["url"]))
    lines.extend(["", "## Limitations", ""])
    lines.extend("- " + _md(x) for x in report["limitations"])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phrase")
    parser.add_argument("--source", action="append", choices=SOURCES)
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--gdelt-as-of")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--extract-limit", type=int, default=0)
    parser.add_argument("--google-capture", type=Path)
    parser.add_argument("--capture-time")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    imports = []
    try:
        if args.capture_time and not args.google_capture:
            raise ValueError("Capture time requires an import")
        if args.google_capture:
            with args.google_capture.open("rb") as stream:
                raw = stream.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError("Capture exceeds byte limit")
            imports.append(parse_news_capture(raw, provider="google_news_rss", captured_at=args.capture_time))
        selected = args.source if args.source is not None else (() if imports and not args.execute else DEFAULT_SOURCES)
        report = asyncio.run(investigate_news(
            args.phrase, sources=selected, days=args.days, limit=args.limit,
            timeline_as_of=args.gdelt_as_of, execute=args.execute, extract_limit=args.extract_limit,
            imported_batches=imports,
        ))
    except (OSError, ValueError):
        parser.error("Invalid investigation arguments or saved capture")
    print(json.dumps(report, ensure_ascii=True, allow_nan=False) if args.format == "json"
          else format_investigation_markdown(report), end="\n")


if __name__ == "__main__":
    main()
