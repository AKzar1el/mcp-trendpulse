"""A04 opt-in Wikidata identity pilot: strict QIDs, languages and unknowns.

This pure, offline adapter intentionally makes NO HTTP requests. An approved
integration owner may route its fixed-origin request plan through the existing
TrendPulse budget, cache, and credential-free transport after live proof.
Search strings never become QIDs without explicit human confirmation.
"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any
from urllib.parse import urlencode

SOURCE = "https://www.wikidata.org/w/api.php"
SUPPORTED_LANGUAGES = ("en", "de", "fr", "es", "sl", "it")
MAX_ENTITIES = 3
MAX_BYTES = 192_000
MAX_ALIASES = 8
QID = re.compile(r"Q[1-9][0-9]{0,9}\Z")


def _scope(qids: list[str], languages: list[str]) -> tuple[list[str], list[str]]:
    if (not isinstance(qids, list) or not 1 <= len(qids) <= MAX_ENTITIES
            or any(not isinstance(q, str) or QID.fullmatch(q) is None for q in qids)
            or len(set(qids)) != len(qids)):
        raise ValueError("Expected 1-3 unique explicit Wikidata QIDs")
    if (not isinstance(languages, list) or not 1 <= len(languages) <= 6
            or any(not isinstance(lang, str) or lang not in SUPPORTED_LANGUAGES for lang in languages)
            or len(set(languages)) != len(languages)):
        raise ValueError("Expected 1-6 unique supported language codes")
    return qids, languages


def plan_qid_lookup(qids: list[str], languages: list[str]) -> dict[str, Any]:
    """Return a fixed-origin, one-request, plan-only Action API operation.

    Does not touch network and is not registered as CLI/MCP tool. Executing
    this plan must use an explicitly approved v1 budgeted collector.
    """
    ids, langs = _scope(qids, languages)
    query = urlencode({
        "action": "wbgetentities", "ids": "|".join(ids),
        "languages": "|".join(langs), "props": "labels|aliases|descriptions",
        "format": "json", "formatversion": "2",
    })
    return {
        "source": "wikidata_action_api", "url": f"{SOURCE}?{query}",
        "qids": ids, "languages": langs,
        "execution": "PLAN_ONLY", "request_count_if_approved": 1,
        "max_response_bytes": MAX_BYTES, "timeout_seconds_if_approved": 8,
        "requires_user_agent_with_contact": True,
        "requires_existing_trendpulse_budget_and_cache": True,
        "zero_network_calls": True,
    }


def _clean_text(value: Any) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 160:
        raise ValueError("Invalid bounded Wikidata text")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError("Control characters in Wikidata text")
    return unicodedata.normalize("NFC", value)


def _localized(record: Any, lang: str) -> str | None:
    if record is None:
        return None
    if (not isinstance(record, dict) or record.get("language") != lang):
        raise ValueError("Language-inconsistent Wikidata label")
    return _clean_text(record.get("value"))


def _aliases(entity: dict[str, Any], lang: str) -> list[str]:
    rows = entity.get("aliases", {}).get(lang, [])
    if not isinstance(rows, list) or len(rows) > MAX_ALIASES:
        raise ValueError("Too many or malformed aliases")
    seen = set()
    out = []
    for record in rows:
        value = _localized(record, lang)
        if value not in seen:
            out.append(value)
            seen.add(value)
    return out


def parse_qid_lookup(
    payload: Any, qids: list[str], languages: list[str],
) -> dict[str, Any]:
    """Validate an externally acquired official wbgetentities response.

    Missing entity, absent language, and partial response all remain unknown;
    none is synthesized as zero/false. Unknown names never auto-merge.
    """
    ids, langs = _scope(qids, languages)
    try:
        size = len(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid Wikidata JSON") from exc
    if size > MAX_BYTES:
        raise ValueError("Wikidata response too large")
    if not isinstance(payload, dict) or payload.get("success") != 1 or "error" in payload:
        raise ValueError("Wikidata upstream error or invalid success envelope")
    if "redirects" in payload or "normalized" in payload:
        raise ValueError("Unexpected entity redirect or normalization needs explicit review")
    entities = payload.get("entities")
    if not isinstance(entities, dict) or len(entities) > MAX_ENTITIES:
        raise ValueError("Invalid Wikidata entity result map")
    if any(key not in ids for key in entities):
        raise ValueError("Unrequested entity in Wikidata result")
    results = []
    for qid in ids:
        raw = entities.get(qid)
        if raw is None:
            results.append({"qid": qid, "status": "unknown_partial_response"})
            continue
        if not isinstance(raw, dict) or raw.get("id") != qid:
            raise ValueError("Mismatched Wikidata identity")
        if "missing" in raw:
            results.append({"qid": qid, "status": "unknown_missing_entity"})
            continue
        if raw.get("type") != "item":
            raise ValueError("Expected a Wikidata item")
        for key in ("labels", "descriptions", "aliases"):
            if not isinstance(raw.get(key, {}), dict):
                raise ValueError(f"Malformed Wikidata {key} map")
            if any(lang not in langs for lang in raw.get(key, {})):
                raise ValueError("Unrequested language in source result")
        names = {}
        for lang in langs:
            label = _localized(raw.get("labels", {}).get(lang), lang)
            description = _localized(raw.get("descriptions", {}).get(lang), lang)
            aliases = _aliases(raw, lang)
            names[lang] = {"label": label, "description": description, "aliases": aliases}
        results.append({
            "qid": qid, "status": "source_item_observed", "entity_url": f"https://www.wikidata.org/wiki/{qid}",
            "names": names, "source_id": "wikidata_action_api",
            "source_licenses_data_as_cc0": True,
            "original_source_identity_not_corporate_registry_confirmation": True,
        })
    return {
        "source": "wikidata_action_api", "status": "OFFLINE_PARSED_UPSTREAM_PAYLOAD",
        "qids_requested": ids, "languages_requested": langs, "results": results,
        "source_coverage_complete": len(entities) == len(ids),
        "raw_payload_reused_not_fetched": True, "no_auto_entity_merging": True,
    }


def candidates_for_name(parsed: dict[str, Any], name: str, language: str) -> dict[str, Any]:
    """Surface exact source alias candidates, never assert an identity match."""
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError("Unsupported source language")
    needle = _clean_text(name).casefold()
    options = []
    for item in parsed.get("results", []):
        if item.get("status") != "source_item_observed":
            continue
        record = item["names"].get(language)
        if not record:
            continue
        forms = [record["label"], *record["aliases"]]
        if any(isinstance(v, str) and v.casefold() == needle for v in forms):
            options.append(item["qid"])
    options.sort()
    return {
        "query": name, "language": language, "candidate_qids": options,
        "status": "ambiguous" if len(options) > 1 else (
            "candidate_requires_confirmation" if options else "unknown_no_match"
        ),
        "identity_confirmed": False,
        "missing_source_items_are_unknown_not_negative": True,
    }


def parse_transport_result(
    http_status: int, payload: Any, qids: list[str], languages: list[str],
) -> dict[str, Any]:
    """Map one externally budgeted HTTP response without retry or fake zero.

    Callers own their approved fixed-origin transport and its bounded cache.
    This consumes an already received response; never opens a connection.
    """
    _scope(qids, languages)
    if isinstance(http_status, bool) or not isinstance(http_status, int):
        raise ValueError("Invalid HTTP status")
    if http_status != 200:
        return {
            "source": "wikidata_action_api", "status": "source_unavailable",
            "http_status": http_status,
            "reason": ("permission_denied" if http_status in (401, 403) else
                       "rate_limited" if http_status == 429 else
                       "upstream_unavailable" if http_status in (503, 500, 502, 504) else
                       "redirect_disallowed" if 300 <= http_status < 400 else
                       "unhandled_http_status"),
            "results": None, "automatic_retry": False,
            "zero_not_inferred_from_absence": True,
        }
    return parse_qid_lookup(payload, qids, languages)
