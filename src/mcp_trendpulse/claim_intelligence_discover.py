"""V5.04: plan-first discovery of claim-related evidence candidates.

Use existing no-key fixed-origin adapters and optional existing news search.
No source automatically becomes supporting/contradicting evidence.
"""
from __future__ import annotations

import asyncio
import math
import re
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, model_validator

from mcp_trendpulse.claim_intelligence_graph import ClaimEvidenceGraph, _typed
from mcp_trendpulse.claim_intelligence_reviews import parse_review_capture
from mcp_trendpulse.intelligence_core import (
    DailyBudgetExceeded, IntelligenceError, SourceCoolingDown, collect, plan_source,
)
from mcp_trendpulse.news_intelligence_investigate import investigate_news
from mcp_trendpulse.news_intelligence_schema import FrozenModel, _digest, _text, _url, _utc

MAX_RECORD_QUERIES = 3
MAX_REVIEW_CAPTURES = 3
SOURCE_DETAILS = {
    "worldbank": ("World Bank", "official_indicator_candidate",
                  "https://datacatalog.worldbank.org/public-licenses"),
    "gleif": ("GLEIF", "legal_entity_candidate",
              "https://www.gleif.org/en/meta/lei-data-terms-of-use/"),
    "cellar": ("Publications Office of the European Union", "legal_publication_metadata_candidate",
               "https://op.europa.eu/en/web/cellar/cellar-data"),
}


def _now():
    return datetime.now(timezone.utc)


class RecordQuery(FrozenModel):
    source: Literal["worldbank", "gleif", "cellar"]
    keyword: str = ""
    country: str = ""
    identifier: str = ""
    limit: int = Field(default=5, ge=1, le=10, strict=True)

    @model_validator(mode="after")
    def _check(self):
        if self.source == "worldbank":
            if self.keyword or re.fullmatch(r"[A-Z]{2}", self.country) is None or re.fullmatch(
                    r"[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)+", self.identifier) is None:
                raise ValueError("World Bank requires explicit country and indicator")
        elif self.country or self.identifier:
            raise ValueError("This adapter requires only a search keyword")
        else:
            _text(self.keyword, 120 if self.source == "gleif" else 60)
        return self


def _object(value):
    if not isinstance(value, dict):
        raise ValueError("Expected record object")
    return value


def _optional(value, limit=160):
    return None if value is None else _text(value, limit)


def _record(query, row, plan):
    row = _object(row)
    if query.source == "worldbank":
        indicator, country = _object(row.get("indicator")), _object(row.get("country"))
        if indicator.get("id") != query.identifier or country.get("id") != query.country:
            raise ValueError("Indicator record outside requested scope")
        period = _text(row.get("date"), 16)
        if re.fullmatch(r"\d{4}", period) is None:
            raise ValueError("Unsupported indicator period")
        value = row.get("value")
        if value is not None and (type(value) not in (int, float) or abs(value) > 10**100 or not math.isfinite(value)):
            raise ValueError("Invalid indicator observation")
        return {"record_url": _url(plan.url), "indicator_id": query.identifier,
                "indicator_label": _text(indicator.get("value"), 300), "country_code": query.country,
                "country_label": _text(country.get("value"), 160), "period_reported": period,
                "value_reported": value, "unit_reported": _optional(row.get("unit") or None),
                "observation_status_reported": _optional(row.get("obs_status") or None)}
    if query.source == "gleif":
        attributes = _object(row.get("attributes"))
        entity, registration = _object(attributes.get("entity")), _object(attributes.get("registration"))
        lei = attributes.get("lei")
        if not isinstance(lei, str) or re.fullmatch(r"[A-Z0-9]{20}", lei) is None or row.get("id") != lei:
            raise ValueError("Invalid legal entity reference")
        return {"record_url": "https://api.gleif.org/api/v1/lei-records/" + lei, "lei": lei,
                "legal_name_reported": _text(_object(entity.get("legalName")).get("name"), 300),
                "entity_status_reported": _optional(entity.get("status")),
                "registration_status_reported": _optional(registration.get("status"))}
    # Official Cellar identifiers commonly use HTTP as persistent identifiers.
    # Preserve the returned URI; only construct an HTTPS citation for the exact
    # documented publication origin/path, never follow arbitrary returned URLs.
    uri = _text(row.get("work"), 2048)
    parsed = urlsplit(uri)
    if (parsed.scheme not in ("http", "https") or parsed.netloc != "publications.europa.eu"
            or not parsed.path.startswith("/resource/") or parsed.query or parsed.fragment):
        raise ValueError("Unexpected Cellar work identifier")
    return {"record_url": _url("https://publications.europa.eu" + parsed.path),
            "work_uri_reported": uri, "title_reported": _text(row.get("title"), 512)}


def _planned(query, plan):
    name, role, rights = SOURCE_DETAILS[query.source]
    return {"source": query.source, "query": query.model_dump(mode="json"), "attribution": name,
            "candidate_role": role, "documentation": plan.docs, "rights_reference": rights,
            "request": plan.public(), "status": "planned", "reason": None, "captured_at": None,
            "cache_hit": False, "http_status": None, "records": [],
            "returned_sample_count": None, "rejected_rows": None, "source_record_count": None}


def _project(query, plan, receipt, cutoff):
    out = _planned(query, plan)
    if not isinstance(receipt, dict) or receipt.get("source") != query.source:
        return {**out, "status": "invalid", "reason": "invalid_source_receipt"}
    if receipt.get("status") != "observed":
        status = receipt.get("http_status")
        reason = receipt.get("reason")
        known_reasons = ("provider_cooldown", "local_daily_budget_exhausted", "HTTPError", "URLError", "TimeoutError", "OSError")
        return {**out, "status": "invalid" if receipt.get("status") == "invalid_source_shape" else "unavailable",
                "reason": reason if reason in known_reasons else "source_unavailable_or_invalid",
                "http_status": status if type(status) is int and 100 <= status <= 599 else None,
                "cache_hit": receipt.get("cache_hit") is True}
    try:
        if receipt.get("source_url") != plan.url or receipt.get("http_status") not in (None, 200):
            raise ValueError("Scope or transport mismatch")
        capture = _utc(receipt.get("retrieved_at"))
        if datetime.fromisoformat(capture) > cutoff:
            raise ValueError("Future receipt")
        observations = _object(receipt.get("observations"))
        count, rows = observations.get("record_count"), observations.get("sample")
        if (type(count) is not int or count < 0 or count > 20 or not isinstance(rows, list)
                or len(rows) > count or len(rows) > 20):
            raise ValueError("Invalid source sample")
    except (ValueError, TypeError):
        return {**out, "status": "invalid", "reason": "invalid_source_receipt"}
    records = []
    rejected = 0
    for row in rows[:query.limit]:
        try:
            record = _record(query, row, plan)
            record["candidate_id"] = _digest([query.source, capture, record])
            records.append(record)
        except (ValueError, TypeError, OverflowError):
            rejected += 1
    # Count is bounded adapter sample count, never a complete universe.
    status = ("partial" if rejected or count > len(records) else "observed") if records else (
        "empty" if count == 0 else "invalid")
    return {**out, "status": status, "reason": "no_usable_rows" if status == "invalid" else None,
            "captured_at": capture, "cache_hit": receipt.get("cache_hit") is True,
            "source_record_count": count, "returned_sample_count": len(rows),
            "rejected_rows": rejected, "records": records}


async def discover_claim_evidence(graph, *, claim_id, queries=(), news_phrase=None,
                                  review_captures=(), permit_review_metadata=False,
                                  execute=False, cache=None):
    """Investigate one explicit graph claim; query scope is caller-selected.

    No automatic query dispatch from claim or source content. Existing source
    caches/quotas apply. Review imports are (bytes, format, captured_at) triples.
    """
    if not isinstance(graph, ClaimEvidenceGraph) or type(execute) is not bool:
        raise ValueError("Expected typed claim graph and explicit execution flag")
    try:
        graph = ClaimEvidenceGraph.model_validate_json(graph.model_dump_json())
    except (ValueError, TypeError):
        raise ValueError("Invalid claim graph") from None
    start = _now()
    if datetime.fromisoformat(graph.as_of) > start or claim_id not in {c.claim_id for c in graph.claims}:
        raise ValueError("Claim outside graph or cutoff")
    queries = _typed(queries, RecordQuery, MAX_RECORD_QUERIES)
    if len({q.source for q in queries}) != len(queries):
        raise ValueError("Only one operation per official source")
    plans = [(q, plan_source(q.source, keyword=q.keyword, country=q.country,
                             identifier=q.identifier, limit=q.limit, env={})) for q in queries]
    if any(p.headers and q.source != "cellar" or p.allow_loopback for q, p in plans):
        raise ValueError("Unexpected credential or loopback plan")
    if not isinstance(review_captures, (list, tuple)) or len(review_captures) > MAX_REVIEW_CAPTURES:
        raise ValueError("Review import budget exceeded")
    imports = []
    for entry in review_captures:
        if not isinstance(entry, (list, tuple)) or len(entry) != 3:
            raise ValueError("Invalid review capture")
        raw, format, captured_at = entry
        if datetime.fromisoformat(_utc(captured_at)) > start:
            raise ValueError("Review capture after investigation start")
        imports.append(parse_review_capture(raw, format=format, captured_at=captured_at,
                                            permit_metadata=permit_review_metadata))
    imports.sort(key=lambda r: r["report_id"])
    news = None
    if news_phrase is not None:
        news = await investigate_news(news_phrase, sources=("google_news_rss",), limit=5)
    if execute and not plans and news is None:
        raise ValueError("Execution requires an explicit source query")
    receipts = []
    for q, plan in plans:
        if not execute:
            receipts.append(_planned(q, plan))
            continue
        try:
            receipt = await asyncio.to_thread(collect, plan, cache=cache, fetch=True, env={})
        except DailyBudgetExceeded:
            receipt = {"source": q.source, "status": "unavailable", "reason": "local_daily_budget_exhausted"}
        except SourceCoolingDown:
            receipt = {"source": q.source, "status": "unavailable", "reason": "provider_cooldown"}
        except (IntelligenceError, OSError):
            receipt = {"source": q.source, "status": "unavailable", "reason": "source_unavailable_or_invalid"}
        receipts.append(_project(q, plan, receipt, _now()))
    if execute and news is not None:
        news = await investigate_news(news_phrase, sources=("google_news_rss",), limit=5,
                                      execute=True, cache=cache)
    report = {
        "schema_version": 1, "method": "claim_evidence_discovery_v1", "graph_id": graph.graph_id,
        "claim_id": claim_id, "as_of": _now().isoformat(), "execute_requested": execute,
        "official_record_receipts": receipts,
        "reporting_candidates": None if news is None else {
            "query": news["query"], "status": news["status"], "source_receipts": news["source_receipts"],
            "citations": news["citations"], "independence": "unknown"},
        "imported_review_receipts": imports,
        "google_fact_check_search": {
            "status": "disabled_unverified_free_access",
            "documentation": "https://developers.google.com/fact-check/tools/api/reference/rest/v1alpha1/claims/search",
            "network_performed": False},
        "semantic_verification": "not_performed", "claim_match": "not_assessed",
        "source_independence": "unknown", "automatic_relations_created": 0,
        "paid_services_used": False,
        "network_performed": False if not execute else None,
        "limitations": [
            "Explicit query candidates are not verified matches to the claim or independent corroboration.",
            "Official adapter samples are bounded, may be revised or incomplete, and require exact metric/record scope review.",
            "Dataset-specific rights must be checked before redistribution; existing collector cache behavior is unchanged.",
            "Fact-check metadata is imported only with permission. Original review ratings are not TrendPulse verdicts.",
            "Literal archive and correction references are candidates only; no retrieval, authentication, or claim verification.",
            "Exact network request counts are not supplied by every legacy collector.",
        ],
    }
    report["report_id"] = _digest(report)
    return report
