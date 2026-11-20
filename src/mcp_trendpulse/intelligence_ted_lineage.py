"""Bounded, opt-in related TED notice investigation by source procedure UUID.

An exact same-procedure ID links published notices; it does NOT prove that
the newest notice supersedes an earlier one, that a bid remains open, or
that an award/budget belongs to a particular software lot.
"""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from typing import Any
from uuid import UUID

from mcp_trendpulse.intelligence_core import (
    BudgetCache, IntelligenceError, collect, plan_source,
)

MAX_RELATED_REQUESTS = 2
MAX_RESULTS_PER_PROCEDURE = 10
TED_ID = re.compile(r"[0-9]{1,7}-20[0-9]{2}")
REASONS = {"HTTPError", "URLError", "TimeoutError", "provider_cooldown", "collection_failed"}


def _source_uuid(value: Any) -> str:
    """Only one canonical UUIDv4 may establish the same-procedure join."""
    if isinstance(value, list):
        if len(value) != 1:
            return ""
        value = value[0]
    if not isinstance(value, str) or len(value) != 36:
        return ""
    try:
        identifier = UUID(value)
    except (ValueError, AttributeError):
        return ""
    return str(identifier) if identifier.version == 4 and str(identifier) == value.lower() else ""


def _date(value: Any, *, as_of: date) -> str:
    if not isinstance(value, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
        return ""
    try:
        day = date.fromisoformat(value)
    except ValueError:
        return ""
    return day.isoformat() if day <= as_of else ""


def _notice_type(value: Any) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[a-z0-9-]{2,40}", value) is None:
        return "unknown"
    return value


def _selected(briefs: dict[str, Any]) -> list[tuple[dict[str, Any], str, str]]:
    rows = briefs.get("briefs", [])
    if not isinstance(rows, list) or len(rows) > 6:
        raise ValueError("Expected bounded completed workflow briefs")
    selected = []
    seen = set()
    for brief in rows:
        if (not isinstance(brief, dict)
                or brief.get("kind") != "published_software_it_procurement_to_investigate"
                or brief.get("published_lot_date_on_or_after_analysis") is not True):
            continue
        scope = brief.get("published_scope_context")
        if not isinstance(scope, dict) or scope.get("status") != "observed_scope_excerpts":
            continue
        identifier = _source_uuid(scope.get("published_procedure_identifier"))
        proof = brief.get("evidence")
        if not identifier or not isinstance(proof, list) or not proof:
            continue
        base = proof[0]
        if not isinstance(base, dict):
            continue
        original_ref = base.get("reference", "")
        match = re.fullmatch(
            r"https://ted\.europa\.eu/en/notice/-/detail/([0-9]{1,7}-20[0-9]{2})",
            original_ref,
        ) if isinstance(original_ref, str) else None
        if match and identifier not in seen:
            selected.append((brief, match.group(1), identifier))
            seen.add(identifier)
            if len(selected) == MAX_RELATED_REQUESTS:
                break
    return selected


def inspect_related_ted_notices(
    briefs: dict[str, Any], *, as_of: date,
    cache: BudgetCache | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    if not isinstance(as_of, date):
        raise ValueError("Analysis date required for related TED notices")
    selected = _selected(briefs)
    result = {
        "mode": "source_joined_ted_related_notices_not_confirmed_amendments",
        "status": "no_source_published_procedure_uuid",
        "max_additional_requests": MAX_RELATED_REQUESTS,
        "source_requests_budgeted": len(selected),
        "source_requests_performed": 0,
        "related_notice_results": [],
        "join_basis": "same_published_procedure_identifier_uuid_v4",
        "notice_version_supersession_verified": False,
        "current_bid_status_verified": False,
        "lot_specific_scope_or_budget_verified": False,
        "all_related_notices_retrieved": False,
    }
    if not selected:
        return result
    successes = 0
    for brief, original_id, procedure_id in selected:
        template = plan_source(
            "ted", keyword=f"procedure-identifier = {procedure_id}",
            limit=MAX_RESULTS_PER_PROCEDURE, env=env,
        )
        fields = list(dict.fromkeys([
            *template.body["fields"], "procedure-identifier",
            "previous-notice-id-proc",
        ]))
        plan = replace(template, body={**template.body, "fields": fields})
        row = {
            "brief_id": brief["brief_id"],
            "original_notice": original_id,
            "procedure_identifier_source_validated": True,
            "source": "ted", "status": "unavailable",
            "related_notice_count_in_bounded_sample": 0,
            "result_sample_hit_cap": False,
            "newer_same_procedure_publication_present": False,
            "newest_related_notice": None,
            "related_notice_references": [],
            "same_procedure_not_sufficient_to_prove_amendment": True,
            "actual_current_lot_or_bid_status_verified": False,
        }
        try:
            response = collect(plan, fetch=True, cache=cache, env=env, timeout=20)
        except (OSError, ValueError, IntelligenceError):
            response = {"status": "unavailable", "reason": "collection_failed"}
        row["cache_hit"] = response.get("cache_hit") is True
        if not row["cache_hit"] and response.get("reason") != "provider_cooldown":
            result["source_requests_performed"] += 1
        state = response.get("status")
        if state != "observed":
            row["status"] = (state if state in {"unavailable", "rate_limited",
                                               "invalid_source_shape"} else "unavailable")
            http = response.get("http_status")
            if isinstance(http, int) and not isinstance(http, bool) and 400 <= http <= 599:
                row["http_status"] = http
            elif response.get("reason") in REASONS:
                row["reason"] = response["reason"]
            result["related_notice_results"].append(row)
            continue
        observations = response.get("observations")
        sample = observations.get("sample") if isinstance(observations, dict) else None
        if not isinstance(sample, list) or len(sample) > MAX_RESULTS_PER_PROCEDURE:
            row["status"] = "invalid_source_shape"
            result["related_notice_results"].append(row)
            continue
        unique = {}
        for item in sample:
            if not isinstance(item, dict):
                continue
            if _source_uuid(item.get("procedure-identifier")) != procedure_id:
                continue
            notice = item.get("publication-number")
            published = _date(item.get("publication-date"), as_of=as_of)
            if not isinstance(notice, str) or TED_ID.fullmatch(notice) is None or not published:
                continue
            unique[notice] = {
                "publication_number": notice,
                "published": published,
                "notice_type": _notice_type(item.get("notice-type")),
                "reference": "https://ted.europa.eu/en/notice/-/detail/" + notice,
                "source_published_procedure_join": True,
                "supersession_and_amendment_type_not_verified": True,
            }
        notices = sorted(
            unique.values(), key=lambda item: (item["published"], item["publication_number"]),
            reverse=True,
        )
        old_evidence = brief.get("evidence")
        original_day = (
            _date(old_evidence[0].get("date"), as_of=as_of)
            if isinstance(old_evidence, list) and old_evidence
            and isinstance(old_evidence[0], dict) else ""
        )
        newer = bool(original_day and any(
            item["published"] > original_day and item["publication_number"] != original_id
            for item in notices
        ))
        row.update({
            "status": "observed_related_notice_sample" if notices else "observed_no_valid_same_procedure_notices_in_sample",
            "related_notice_count_in_bounded_sample": len(notices),
            "result_sample_hit_cap": len(sample) >= MAX_RESULTS_PER_PROCEDURE,
            "newer_same_procedure_publication_present": newer,
            "newest_related_notice": notices[0] if notices else None,
            "related_notice_references": notices[:5],
        })
        brief["related_notice_context"] = {
            "newer_source_publication_requires_scope_revalidation": newer,
            "latest_published_notice": notices[0] if notices else None,
            "published_same_procedure_not_confirmed_supersession": True,
            "current_tender_status_verified": False,
        }
        successes += 1
        result["related_notice_results"].append(row)
    result["status"] = (
        "source_joined_related_notices_observed"
        if successes == len(selected)
        else "partial_or_unavailable_related_notices"
    )
    return result


def format_related_ted_notices(report: dict[str, Any]) -> list[str]:
    if report.get("mode") != "source_joined_ted_related_notices_not_confirmed_amendments":
        raise ValueError("Expected opt-in same-procedure TED report")
    lines = [
        "RELATED TED NOTICES (opt-in; exact source procedure ID; at most 2 extra free queries):",
        "  The same published procedure UUID is a source-backed join, not proof of an amendment or superseded text.",
        "  Newer publications require manual current-scope and deadline review, not a claim of an active bid.",
    ]
    if not report["related_notice_results"]:
        lines.append("  No usable published UUIDv4 in retrieved TED scope. No speculative title/name matches.")
    for item in report["related_notice_results"]:
        lines.append(
            f"  Original TED {item['original_notice']}: {item['status']}"
            + (" (cached)" if item.get("cache_hit") else "")
        )
        if item["newer_same_procedure_publication_present"]:
            lines.append("    NEWER SAME-PROCEDURE PUBLICATION: recheck scope, amendments, deadlines and outcome")
        newest = item["newest_related_notice"]
        if newest:
            lines.append(
                f"    Latest sampled notice: {newest['publication_number']}"
                f" | {newest['published']} | {newest['notice_type']}"
            )
            lines.append("    " + newest["reference"])
        if item.get("http_status"):
            lines.append(f"    HTTP {item['http_status']} (unavailable, not absence of activity)")
        if item.get("reason"):
            lines.append(f"    {item['reason']} (unavailable, not absence of activity)")
        if item["result_sample_hit_cap"]:
            lines.append("    Sample hit 10-record cap; other notices may exist")
    lines.append(
        "  No latest notice is silently treated as a confirmed award, updated lot budget,"
        " open deadline, or verified supersession. Read the original official record."
    )
    return lines
