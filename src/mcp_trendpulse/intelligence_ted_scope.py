"""Explicit, bounded TED scope projection for source-backed procurement briefs.

Fetch the source's own published procedure and lot excerpts only on opt-in.
TED Search API's projected multi-lot arrays are not relational lot records:
NEVER join them to a lot budget, lot deadline, supplier or distinct product.
"""
from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from mcp_trendpulse.intelligence_core import (
    BudgetCache, IntelligenceError, collect, plan_source,
)

MAX_SCOPE_REQUESTS = 2
MAX_FIELD_EXCERPTS = 2
MAX_EXCERPT_CHARS = 280
TED_ID = re.compile(r"[0-9]{1,7}-20[0-9]{2}")
TED_REFERENCE = re.compile(
    r"https://ted\.europa\.eu/en/notice/-/detail/([0-9]{1,7}-20[0-9]{2})"
)
EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
URL = re.compile(r"https?://\S+", re.I)
PHONE = re.compile(r"(?<!\w)\+?[0-9][0-9 .()/-]{8,}[0-9](?!\w)")
SCOPE_FIELDS = (
    "description-proc", "title-lot", "description-lot",
)
ALLOWED_STATUSES = {
    "observed", "unavailable", "rate_limited", "invalid_source_shape",
}
ALLOWED_REASONS = {
    "HTTPError", "URLError", "TimeoutError", "provider_cooldown",
    "collection_failed", "invalid_source_shape",
}


def _excerpt(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    # Public procurement prose can contain email, URL and contact metadata.
    # Keep only a short normalized display excerpt, never raw payloads.
    sanitized = EMAIL.sub("[email withheld]", URL.sub("[URL withheld]", value))
    sanitized = PHONE.sub("[number withheld]", sanitized)
    sanitized = "".join(ch if ch.isprintable() else " " for ch in sanitized)
    return " ".join(sanitized.split())[:MAX_EXCERPT_CHARS]


def _published_excerpts(value: Any, official: Any = None) -> list[dict[str, str]]:
    """Keep at most two items from one source language, without translations.

    The TED projection can flatten multi-lot values; it does not guarantee
    alignment between title, descriptions, deadlines or monetary amounts.
    """
    if isinstance(value, str):
        text = _excerpt(value)
        return [{"language": "unspecified", "excerpt": text}] if text else []
    if not isinstance(value, dict):
        return []
    translations = {}
    for lang, raw in list(value.items())[:12]:
        if not isinstance(lang, str) or re.fullmatch(r"[A-Za-z]{2,3}", lang) is None:
            continue
        rows = raw if isinstance(raw, list) else [raw]
        selected = []
        for entry in rows[:8]:
            text = _excerpt(entry)
            if text and text not in selected:
                selected.append(text)
            if len(selected) == MAX_FIELD_EXCERPTS:
                break
        if selected:
            translations[lang.lower()] = selected
    official_lang = ""
    if isinstance(official, list) and official and isinstance(official[0], str):
        official_lang = official[0].lower()
    elif isinstance(official, str):
        official_lang = official.lower()
    choices = ["eng", "en", official_lang, *sorted(translations)]
    for language in choices:
        if language in translations:
            return [
                {"language": language, "excerpt": text}
                for text in translations[language]
            ]
    return []


def _selected_briefs(briefs: dict[str, Any]) -> list[tuple[dict[str, Any], str]]:
    rows = briefs.get("briefs")
    if not isinstance(rows, list) or len(rows) > 6:
        raise ValueError("Expected bounded completed workflow briefs")
    selected = []
    seen = set()
    for brief in rows:
        if not isinstance(brief, dict):
            raise ValueError("Invalid workflow brief")
        if (brief.get("kind") != "published_software_it_procurement_to_investigate"
                or brief.get("published_lot_date_on_or_after_analysis") is not True):
            continue
        evidence = brief.get("evidence", [])
        if not isinstance(evidence, list) or not evidence:
            continue
        ref = evidence[0].get("reference") if isinstance(evidence[0], dict) else None
        match = TED_REFERENCE.fullmatch(ref) if isinstance(ref, str) else None
        if match and match.group(1) not in seen:
            selected.append((brief, match.group(1)))
            seen.add(match.group(1))
            if len(selected) == MAX_SCOPE_REQUESTS:
                break
    return selected


def inspect_ted_scopes(
    briefs: dict[str, Any], *,
    cache: BudgetCache | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Use at most two extra existing TED free requests, never scheduled."""
    selected = _selected_briefs(briefs)
    output = {
        "mode": "source_published_ted_scope_not_verified_lot_mapping",
        "status": "no_eligible_published_tenders",
        "source": "ted", "max_additional_source_requests": MAX_SCOPE_REQUESTS,
        "source_requests_budgeted": len(selected),
        "source_requests_performed": 0,
        "source_status": [],
        "source_fields": list(SCOPE_FIELDS),
        "lot_identifiers_to_excerpts_verified": False,
        "lot_specific_prices_or_deadlines_verified": False,
        "active_tender_or_buyer_eligibility_verified": False,
        "original_documents_fully_read": False,
        "not_proof_of_software_only_budget_or_recurring_market": True,
    }
    if not selected:
        return output
    for brief, tender_id in selected:
        base = plan_source(
            "ted", keyword=f"publication-number = {tender_id}",
            limit=1, env=env,
        )
        fields = list(dict.fromkeys([*base.body["fields"], *SCOPE_FIELDS]))
        plan = replace(base, body={**base.body, "fields": fields})
        try:
            outcome = collect(plan, fetch=True, cache=cache, env=env, timeout=20)
        except (OSError, ValueError, IntelligenceError):
            outcome = {"status": "unavailable", "reason": "collection_failed"}
        status = outcome.get("status")
        if status not in ALLOWED_STATUSES:
            status = "unavailable"
        observed = status == "observed"
        meta = {
            "notice_id": tender_id,
            "brief_id": brief["brief_id"],
            "source": "ted",
            "status": status,
            "reference": "https://ted.europa.eu/en/notice/-/detail/" + tender_id,
            "cache_hit": outcome.get("cache_hit") is True,
        }
        if not meta["cache_hit"] and outcome.get("reason") != "provider_cooldown":
            output["source_requests_performed"] += 1
        if not observed:
            code = outcome.get("http_status")
            reason = outcome.get("reason")
            if isinstance(code, int) and not isinstance(code, bool) and 400 <= code <= 599:
                meta["http_status"] = code
            elif isinstance(reason, str) and reason in ALLOWED_REASONS:
                meta["reason"] = reason
            output["source_status"].append(meta)
            continue
        observations = outcome.get("observations")
        sample = observations.get("sample") if isinstance(observations, dict) else None
        if (not isinstance(sample, list) or len(sample) != 1
                or not isinstance(sample[0], dict)
                or sample[0].get("publication-number") != tender_id):
            meta["status"] = "invalid_source_shape"
            output["source_status"].append(meta)
            continue
        row = sample[0]
        official = row.get("official-language")
        procedure = _published_excerpts(row.get("description-proc"), official)
        lot_titles = _published_excerpts(row.get("title-lot"), official)
        lot_descriptions = _published_excerpts(row.get("description-lot"), official)
        values = {
            "status": "observed_scope_excerpts" if (procedure or lot_titles or lot_descriptions)
                      else "observed_no_projected_scope_text",
            "original_notice_reference": meta["reference"],
            "procedure_description": procedure[:1],
            "lot_title_excerpts_without_lot_identity": lot_titles,
            "lot_description_excerpts_without_lot_identity": lot_descriptions,
            "lot_description_and_title_alignment_verified": False,
            "lot_budget_deadline_alignment_verified": False,
            "source_language_not_translated": True,
            "full_tender_documents_not_read": True,
        }
        # Mutate only the opt-in brief projection; no change to the source
        # candidate scoring, baseline normalization, or persisted history.
        brief["published_scope_context"] = values
        meta["status"] = values["status"]
        meta["scope_excerpts_count"] = (
            len(values["procedure_description"])
            + len(lot_titles) + len(lot_descriptions)
        )
        output["source_status"].append(meta)
    output["status"] = (
        "published_scope_context_observed"
        if any(r["status"] == "observed_scope_excerpts"
               for r in output["source_status"])
        else "published_scope_unavailable_or_missing"
    )
    return output


def format_ted_scopes(report: dict[str, Any], briefs: dict[str, Any]) -> list[str]:
    if report.get("mode") != "source_published_ted_scope_not_verified_lot_mapping":
        raise ValueError("Expected opt-in original TED scope check")
    lines = [
        "ORIGINAL TED PROCEDURE / LOT SCOPE (opt-in, at most 2 free extra requests):",
        "  Original-language search projections only; flattened lot values"
        " are NOT assigned to a specific lot, deadline or budget.",
    ]
    if not report["source_status"]:
        lines.append("  No future-published-lot-date software/IT notices qualified; no extra TED search.")
    brief_ids = {
        b["brief_id"]: b for b in briefs.get("briefs", [])
        if isinstance(b, dict) and isinstance(b.get("brief_id"), str)
    }
    for source in report["source_status"]:
        brief = brief_ids.get(source["brief_id"], {})
        lines.append(
            f"  TED {source['notice_id']}: {source['status']}"
            + (" (cached)" if source.get("cache_hit") else "")
        )
        lines.append("    " + source["reference"])
        scope = brief.get("published_scope_context") or {}
        for field, label in (
            ("procedure_description", "Procedure description"),
            ("lot_title_excerpts_without_lot_identity", "Published lot title (unassigned)"),
            ("lot_description_excerpts_without_lot_identity", "Lot description (unassigned)"),
        ):
            for item in scope.get(field, []):
                lines.append(
                    f"    {label} [{item['language']}]: {item['excerpt']}"
                )
        if source.get("http_status"):
            lines.append(f"    HTTP {source['http_status']} (unavailable, not zero demand)")
        elif source.get("reason"):
            lines.append(f"    {source['reason']} (unavailable, not zero demand)")
    lines.append(
        "  Verify the official full notice and documents before inferring"
        " the delivered product, lot scope, bidder eligibility or software-only spend."
    )
    return lines
