"""Seedless current-topic discovery from bounded, original public-source records.

No prechosen industry keywords, historical baseline, LLM, paid API, crawler,
synthetic trend scores, background polling or unauthorized secrets.
A candidate is an *observation worth investigating*, NOT established market
growth, a matched buyer or proven commercial opportunity.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from mcp_trendpulse.intelligence_core import (
    MAX_RESPONSE_BYTES, BudgetCache, IntelligenceError, collect, plan_source,
)
from mcp_trendpulse.intelligence_hunter import _words
from mcp_trendpulse.intelligence_observations import _entry
from mcp_trendpulse.intelligence_opportunities import _day

SOURCES = ("openalex", "cfpb", "ted")
SOURCE_LABELS = {
    "openalex": "recently published research",
    "cfpb": "consumer complaint categories",
    "ted": "EU published contract/design competition notices",
}
MAX_RECORDS = 20
# The provider's 256-KiB HTTP limit applies per request, not to the sum of
# three separate source snapshots. Allow only those bounded responses plus
# small collector envelopes, then enforce 180 KB on normalized evidence.
MAX_SOURCE_INPUT_BYTES = 3 * MAX_RESPONSE_BYTES + 32_768
MAX_SNAPSHOT_BYTES = 180_000
NAME = re.compile(r"[^\w .,&/()'-]+", re.UNICODE)
_CUTOFF_WORDS = frozenset({
    "market", "growth", "forecast", "reach", "billion", "million",
    "study", "paper", "review", "overview", "approach", "method",
    "effect", "impact", "toward", "towards", "evaluation",
})


def _clean_name(value: Any, maximum: int = 100) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(NAME.sub(" ", value).split())[:maximum]


def _theme_tokens(value: str) -> list[str]:
    return [word for word in _words(value)
            if word not in _CUTOFF_WORDS and len(word) >= 4]


def _ngrams(text: str) -> set[str]:
    tokens = _theme_tokens(text)
    # OpenAlex topical text can be lengthy. Only a bounded excerpt matters;
    # each unique phrase in a record counts at most once.
    found: set[str] = set()
    for n in (2, 3):
        for i in range(max(0, min(len(tokens), 24) - n + 1)):
            phrase = " ".join(tokens[i:i + n])
            if 8 <= len(phrase) <= 55:
                found.add(phrase)
    return found


def _cpv_granularity(code: str) -> str:
    """Official TED main CPV hierarchy: 2/3/4/5 significant digits.

    Division-, group- and class-level labels are too general to infer that
    multiple buyers have a matching narrow procurement workflow.
    """
    if not isinstance(code, str) or re.fullmatch(r"[0-9]{8}", code) is None:
        return "invalid"
    significant = len(code.rstrip("0"))
    return ("division" if significant == 2 else
            "group" if significant == 3 else
            "class" if significant == 4 else
            "category_or_finer" if significant >= 5 else
            "invalid")


def _record(
    source: str, raw: dict[str, Any], today: date, cutoff: date,
) -> dict[str, Any] | None:
    base = _entry(source, raw, today)
    if base is None or base.get("event_date") is None:
        return None
    when = date.fromisoformat(base["event_date"])
    if not cutoff <= when <= today:
        return None
    if base.get("date_semantics") not in {
        "research_publication_not_purchase",
        "complaint_received_not_purchase",
        "notice_publication_not_confirmed_award",
    }:
        return None
    # A TED record without a usable original or published translation title
    # cannot be interpreted as a procurement opportunity from its ID alone.
    if source == "ted" and not base.get("title"):
        return None
    out = {
        "source": source, "evidence_class": base["kind"],
        "id": base["id"], "title": base.get("title", ""),
        "date": when.isoformat(), "reference": base["reference"],
        "date_semantics": base["date_semantics"],
        "theme": "", "theme_basis": "",
    }
    if source == "openalex":
        primary = raw.get("primary_topic")
        theme = primary.get("display_name") if isinstance(primary, dict) else None
        theme = _clean_name(theme)
        if 8 <= len(theme) <= 85 and len(_theme_tokens(theme)) >= 2:
            out["theme"] = theme
            out["theme_basis"] = "openalex_assigned_primary_topic"
    elif source == "cfpb":
        product = _clean_name(base.get("consumer_product"), 65)
        issue = _clean_name(base.get("reported_issue"), 75)
        if product and issue:
            out["theme"] = f"{product} — {issue}"[:110]
            out["theme_basis"] = "cfpb_public_product_issue_categories"
    elif source == "ted":
        # A contract notice is buying-process evidence, not a confirmed order.
        # Contract award notices describe an outcome, not a new open tender.
        # Other notice types are not classified without source-specific proof.
        kind = base.get("notice_type", "").lower()
        if kind.startswith("cn-"):
            stage = "contract_notice_not_award"
        elif kind.startswith("can-"):
            stage = "contract_award_notice_not_open_tender"
        elif kind.startswith("pin-"):
            stage = "prior_information_notice"
        else:
            stage = "unclassified_procurement_notice"
        deadlines = base.get("lot_deadline_dates", [])
        if deadlines:
            if deadlines[-1] < today.isoformat():
                deadline_assessment = "all_published_lot_dates_past"
            elif deadlines[0] >= today.isoformat():
                deadline_assessment = "published_lot_dates_on_or_after_asof"
            else:
                deadline_assessment = "mixed_past_and_future_published_lot_dates"
        else:
            deadline_assessment = "no_published_lot_deadline"
        out.update({
            "buyer_name": base.get("buyer_name", ""),
            "buyer_country_code": base.get("buyer_country_code", ""),
            "notice_type": kind,
            "procurement_stage": stage,
            "title_language": base.get("title_language", ""),
            "cpv_codes": base.get("cpv_codes", []),
            "main_cpv_code": base.get("main_cpv_code", ""),
            "lot_deadline_dates": deadlines,
            "latest_lot_deadline_date": deadlines[-1] if deadlines else "",
            "deadline_assessment": deadline_assessment,
            "estimated_value_as_published": base.get("estimated_value_as_published", ""),
            "estimated_value_currency": base.get("estimated_value_currency", ""),
            "estimated_value_not_verified_spending": True,
        })
        # TED notices are distinct original records. A single notice cannot
        # establish a recurring trend; cross-source matching stays separate.
    return out


def summarize_discovery(
    snapshots: list[dict[str, Any]], *, as_of: str | None = None,
    lookback_days: int = 30,
) -> dict[str, Any]:
    """Offline, deterministic, source-backed discovery from <=3 prior results."""
    if isinstance(lookback_days, bool) or not isinstance(lookback_days, int) or not 7 <= lookback_days <= 90:
        raise ValueError("lookback_days must be 7-90")
    if not isinstance(snapshots, list) or not 1 <= len(snapshots) <= len(SOURCES):
        raise ValueError("Provide 1-3 bounded discovery snapshots")
    try:
        bytes_used = len(json.dumps(snapshots, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Snapshots must be JSON-serializable finite data") from exc
    if bytes_used > MAX_SOURCE_INPUT_BYTES:
        raise ValueError("Discovery source input exceeds bounded three-provider budget")
    today = _day(as_of, "as_of") if as_of is not None else date.today()
    cutoff = today - timedelta(days=lookback_days - 1)

    coverage = []
    records: list[dict[str, Any]] = []
    seen_sources: set[str] = set()
    seen_records: set[tuple[str, str]] = set()

    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            raise ValueError("Each source snapshot must be an object")
        source = snapshot.get("source")
        if not isinstance(source, str) or source not in SOURCES or source in seen_sources:
            raise ValueError("Unknown or repeated discovery source")
        seen_sources.add(source)
        status = snapshot.get("status")
        if status not in {"observed", "unavailable", "rate_limited", "invalid_source_shape"}:
            raise ValueError("Invalid discovery source status")
        row: dict[str, Any] = {
            "source": source, "scope": SOURCE_LABELS[source],
            "status": status, "sampled_rows": 0, "recent_valid_records": 0,
            "cache_hit": snapshot.get("cache_hit") is True,
            "sample_is_not_population": True,
            "future_dated_records_rejected": 0,
            "missing_or_invalid_dates_or_identity": 0,
        }
        http = snapshot.get("http_status")
        if isinstance(http, int) and not isinstance(http, bool) and 400 <= http <= 599:
            row["http_status"] = http
        if status != "observed":
            row["note"] = "Not accessible: absence of evidence is not evidence of no activity"
            coverage.append(row)
            continue
        observation = snapshot.get("observations")
        sample = observation.get("sample") if isinstance(observation, dict) else None
        if not isinstance(sample, list) or len(sample) > MAX_RECORDS:
            row["status"] = "invalid_source_shape"
            row["note"] = "Missing bounded observations"
            coverage.append(row)
            continue
        row["sampled_rows"] = len(sample)
        for raw in sample:
            if not isinstance(raw, dict):
                row["missing_or_invalid_dates_or_identity"] += 1
                continue
            if source == "openalex" and isinstance(raw.get("publication_date"), str):
                try:
                    candidate_day = date.fromisoformat(raw["publication_date"][:10])
                except ValueError:
                    candidate_day = None
                if candidate_day is not None and candidate_day > today:
                    row["future_dated_records_rejected"] += 1
                    continue
            item = _record(source, raw, today, cutoff)
            if item is None:
                row["missing_or_invalid_dates_or_identity"] += 1
                continue
            identifier = (source, item["id"])
            if identifier in seen_records:
                continue
            seen_records.add(identifier)
            records.append(item)
            row["recent_valid_records"] += 1
        coverage.append(row)

    # A 20-row TED/OpenAlex projection can contain large multilingual maps
    # and unrelated provider metadata. Never reject that bounded raw input
    # solely for exceeding the normalized-evidence limit. _record() keeps
    # only validated non-personal fields with capped strings and code lists.
    # Preserve the original 180-KB safety gate on what analysis actually uses.
    if len(json.dumps(records, ensure_ascii=False, allow_nan=False).encode("utf-8")) > MAX_SNAPSHOT_BYTES:
        raise ValueError("Normalized discovery evidence exceeds 180 KB")

    # A source-declared public category is more grounded than arbitrary
    # token splitting. A candidate needs >=2 DISTINCT source IDs.
    category_buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in records:
        if item["theme"]:
            category_buckets[(item["source"], item["theme"].casefold())].append(item)

    # Cross-origin lexical overlap is useful for follow-up, but it cannot
    # assert a shared buyer, a shared workflow or synonymous meanings.
    phrase_records: dict[str, dict[tuple[str, str], dict[str, Any]]] = defaultdict(dict)
    for item in records:
        for phrase in _ngrams(item["title"]):
            phrase_records[phrase][(item["source"], item["id"])] = item
    candidates = []
    for (source, _), group in category_buckets.items():
        if len(group) < 2:
            continue
        theme = group[0]["theme"]
        candidates.append({
            "label": theme, "group_basis": group[0]["theme_basis"],
            "records": group, "source_count": 1,
        })
    for phrase, matching in phrase_records.items():
        group = list(matching.values())
        sources = {item["source"] for item in group}
        if len(sources) < 2:
            continue
        candidates.append({
            "label": phrase, "group_basis": "literal_phrase_across_sources_not_verified_workflow",
            "records": group, "source_count": len(sources),
        })
    # Repeated procedure-level CPV across distinct *published buyer labels*
    # is more directly commercial than complaint frequency. Labels are NOT
    # verified legal entities; exclude award/PIN and same-buyer repeats.
    ted_by_cpv: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if (record["source"] == "ted"
                and record.get("procurement_stage") == "contract_notice_not_award"
                and record.get("main_cpv_code") and record.get("buyer_name")):
            ted_by_cpv[record["main_cpv_code"]].append(record)
    coarse_cpv_repeats = []
    for cpv, group in ted_by_cpv.items():
        buyer_labels = {
            " ".join(r["buyer_name"].casefold().split())
            for r in group if r["buyer_name"].strip()
        }
        if len(group) < 2 or len(buyer_labels) < 2:
            continue
        grain = _cpv_granularity(cpv)
        if grain != "category_or_finer":
            # The published code identifies a broad sector, NOT a shared
            # workflow: e.g., flood works and fibre expansion both 45000000.
            # Keep the factual repeat visible without promoting it to a lead.
            coarse_cpv_repeats.append({
                "main_cpv_code": cpv, "hierarchy_level": grain,
                "notice_count_in_sample": len(group),
                "distinct_published_buyer_labels_in_sample": len(buyer_labels),
                "candidate_suppressed": True,
                "shared_workflow_verified": False,
            })
            continue
        candidates.append({
            "label": f"TED CPV {cpv}",
            "group_basis": "ted_distinct_published_buyer_labels_shared_primary_cpv",
            "records": group, "source_count": 1,
            "cpv_hierarchy_level": grain,
            "published_buyer_label_count": len(buyer_labels),
        })
    ranking = {
        "literal_phrase_across_sources_not_verified_workflow": 0,
        "ted_distinct_published_buyer_labels_shared_primary_cpv": 1,
        "openalex_assigned_primary_topic": 2,
        "cfpb_public_product_issue_categories": 3,
    }
    candidates.sort(key=lambda c: (
        -c["source_count"], ranking.get(c["group_basis"], 9),
        -len(c["records"]),
        -int(max(r["date"] for r in c["records"]).replace("-", "")),
        c["label"].lower(),
    ))

    selected = []
    basis_counts: dict[str, int] = defaultdict(int)
    # Avoid saturating the first dozen slots with one complaint category
    # family just because there are many independent public record IDs.
    for row in candidates:
        kind = row["group_basis"]
        max_of_kind = 4 if kind == "cfpb_public_product_issue_categories" else 6
        if basis_counts[kind] >= max_of_kind:
            continue
        group = row["records"]
        sources = sorted({r["source"] for r in group})
        selected.append({
            "candidate_id": hashlib.sha256((
                row["group_basis"] + "|" + row["label"].casefold()
            ).encode()).hexdigest()[:14],
            "label": row["label"], "basis": row["group_basis"],
            "investigation_priority": 2 if len(sources) >= 2 else 1,
            "unique_recent_records_in_sample": len(group),
            "distinct_source_classes": len(sources),
            "sources": sources,
            "distinct_published_buyer_labels_in_sample": row.get(
                "published_buyer_label_count", 0,
            ),
            "buyer_labels_not_verified_entity_identities": True,
            "cpv_hierarchy_level": row.get("cpv_hierarchy_level", ""),
            "latest_event_date": max(r["date"] for r in group),
            "examples": [{
                "source": r["source"], "title": r["title"],
                "date": r["date"], "reference": r["reference"],
                "date_semantics": r["date_semantics"],
            } for r in sorted(group, key=lambda z: (z["date"], z["source"]), reverse=True)[:3]],
            "same_buyer_verified": False, "commercial_budget_verified": False,
            "growth_direction": "unknown_without_comparable_population_history",
            "next_check": (
                "Compare original sources: do they describe the same buyer/workflow?"
                if len(sources) >= 2 else
                "Validate the published buyers, precise CPV scope, dates and tender value"
                if kind == "ted_distinct_published_buyer_labels_shared_primary_cpv" else
                "Validate independent sources and a buyer with a budget"
            ),
        })
        basis_counts[kind] += 1
        if len(selected) >= 12:
            break

    # Source-balanced observations are visible even when one CFPB complaint
    # category dominates all repeated-theme candidate slots. These are NOT
    # separately scored trends or counted as additional commercial winners.
    ted_records = sorted(
        (r for r in records if r["source"] == "ted" and r["title"]),
        key=lambda x: (x["date"], x["id"]), reverse=True,
    )
    # Surface current competition notice types first (excluding contract
    # awards and prior-information announcements). Publication does not imply
    # the tender is still open, even if lot dates are in the future.
    procurement_sorted = sorted(
        ted_records,
        key=lambda x: (
            x.get("procurement_stage") == "contract_notice_not_award"
            and x.get("deadline_assessment") != "all_published_lot_dates_past",
            x["date"], x["id"],
        ), reverse=True,
    )
    # An individual published tender is a more directly inspectable
    # buyer-side lead than a repeated paper topic or consumer complaint.
    # This is only a source-completeness review, NOT an open-tender,
    # buyer-identity, software budget, or market-growth verification.
    # We keep a sector-agnostic fetch and select from its existing records:
    # two main-CPV 48/72 IT/software notices at most, plus up to four
    # other sectors, filling any unused slots in original recency order.
    # Published lot dates may be revised/cancelled: never infer "open now".
    buyer_review = [
        r for r in ted_records
        if r.get("procurement_stage") == "contract_notice_not_award"
        and r.get("buyer_name")
        and r.get("main_cpv_code")
        and r.get("latest_lot_deadline_date", "") >= today.isoformat()
        and r.get("reference", "").startswith(
            "https://ted.europa.eu/en/notice/-/detail/"
        )
    ]
    software_it = [
        r for r in buyer_review if r["main_cpv_code"][:2] in {"48", "72"}
    ]
    other_sectors = [
        r for r in buyer_review if r["main_cpv_code"][:2] not in {"48", "72"}
    ]
    review_selected = software_it[:2] + other_sectors[:4]
    selected_ids = {r["id"] for r in review_selected}
    for r in buyer_review:
        if len(review_selected) >= 6:
            break
        if r["id"] not in selected_ids:
            review_selected.append(r)
            selected_ids.add(r["id"])
    # Preserve additional recent examples (which may also qualify but were
    # not selected in the six review slots) when the queue has room.
    display_notices = review_selected + [
        r for r in procurement_sorted if r["id"] not in selected_ids
    ][:max(0, 8 - len(review_selected))]
    review_ids = {r["id"] for r in review_selected}
    qualified_ids = {r["id"] for r in buyer_review}
    procurement_observations = [{
        "title": r["title"], "date": r["date"], "reference": r["reference"],
        "buyer_name": r.get("buyer_name", ""),
        "buyer_country_code": r.get("buyer_country_code", ""),
        "notice_type": r.get("notice_type", ""),
        "procurement_stage": r.get("procurement_stage", ""),
        "title_language": r.get("title_language", ""),
        "main_cpv_code": r.get("main_cpv_code", ""),
        "cpv_codes": r.get("cpv_codes", []),
        "latest_lot_deadline_date": r.get("latest_lot_deadline_date", ""),
        "deadline_assessment": r.get("deadline_assessment", ""),
        "estimated_value_as_published": r.get("estimated_value_as_published", ""),
        "estimated_value_currency": r.get("estimated_value_currency", ""),
        "estimated_value_not_verified_spending": True,
        "buyer_side_review_qualified": r["id"] in qualified_ids,
        "buyer_side_review_selected": r["id"] in review_ids,
        "main_cpv_software_it_category": (
            r.get("main_cpv_code", "")[:2] in {"48", "72"}
        ),
        "buyer_entity_identity_verified": False,
        "still_open_tender_verified": False,
        "software_only_estimate_verified": False,
        "buying_intent_verified": False, "contract_value_verified": False,
    } for r in display_notices]
    # A recent-first page may contain just one publication date from an
    # entire 30-day search. Report observed coverage rather than inventing
    # population-level sector shares or growth from this sampling scheme.
    ted_dates = [r["date"] for r in ted_records]
    ted_divisions = Counter(
        r["main_cpv_code"][:2]
        for r in ted_records if _cpv_granularity(r.get("main_cpv_code", "")) != "invalid"
    )
    ted_cover = next((c for c in coverage if c["source"] == "ted"), None)
    ted_sample = {
        "status": ted_cover["status"] if ted_cover else "unavailable",
        "observed_notice_count": len(ted_records),
        "publication_days_represented": len(set(ted_dates)),
        "earliest_sampled_publication": min(ted_dates) if ted_dates else "",
        "latest_sampled_publication": max(ted_dates) if ted_dates else "",
        "requested_lookback_days": lookback_days,
        "first_page_hit_record_cap": bool(
            ted_cover and ted_cover["sampled_rows"] == MAX_RECORDS
        ),
        "main_cpv_divisions_in_sample": dict(
            sorted(ted_divisions.items(), key=lambda item: (-item[1], item[0]))
        ),
        "main_cpv_48_or_72_observed": sum(
            r.get("main_cpv_code", "")[:2] in {"48", "72"}
            for r in ted_records
        ),
        "sector_share_or_growth_estimable": False,
        "excludes_sampled_unknown_categories_from_demand_inference": True,
    }
    procurement_review = {
        "basis": "published_contract_notice_with_buyer_primary_cpv_and_future_lot_date",
        "qualified_notices_in_bounded_sample": len(buyer_review),
        "qualified_main_cpv_software_it": len(software_it),
        "qualified_other_main_cpv_sectors": len(other_sectors),
        "selected_for_review": len(review_selected),
        "not_trend_candidates": True,
        "same_buyer_legal_entity_verified": False,
        "open_bid_status_verified": False,
        "market_growth_verified": False,
        "estimated_value_is_not_spending_or_software_only_budget": True,
    }
    research_records = sorted(
        (r for r in records if r["source"] == "openalex" and r["title"]),
        key=lambda x: (x["date"], x["id"]), reverse=True,
    )
    research_observations = [{
        "title": r["title"], "date": r["date"], "reference": r["reference"],
        "provider_assigned_topic": r["theme"],
        "business_adoption_verified": False,
    } for r in research_records[:3]]
    recent_examples = {}
    for source in SOURCES:
        rows = [r for r in records if r["source"] == source]
        recent_examples[source] = [{
            "title": r["title"], "date": r["date"], "reference": r["reference"],
            "theme": r["theme"], "date_semantics": r["date_semantics"],
        } for r in sorted(rows, key=lambda x: (x["date"], x["id"]), reverse=True)[:2]]
    return {
        "mode": "seedless_public_source_discovery_not_market_growth",
        "as_of": today.isoformat(), "lookback_days": lookback_days,
        "discovery_query_mode": "no_seed_topics_or_sector_keywords",
        "source_coverage": coverage, "recent_observations": len(records),
        "candidate_count": len(selected), "candidates": selected,
        "procurement_observations": procurement_observations,
        "procurement_review": procurement_review,
        "ted_sampling_audit": ted_sample,
        "coarse_cpv_repeats_not_candidates": sorted(
            coarse_cpv_repeats, key=lambda row: (
                -row["notice_count_in_sample"], row["main_cpv_code"],
            )
        )[:6],
        "research_observations": research_observations,
        "source_balanced_examples_not_additional_trend_candidates": True,
        "sample_examples_by_source": recent_examples,
        "source_health_degraded": any(c["status"] != "observed" for c in coverage),
        "population_coverage_verified": False, "growth_rate_verified": False,
        "paid_buyers_verified": False, "no_paid_apis": True,
        "limits": (
            "This is an explicitly small recent-date sample, not a uniform "
            "random sample or evidence of market acceleration. CFPB records "
            "reflect published consumer complaints, OpenAlex topic assignment "
            "is algorithmic, and TED competition notices represent procurement "
            "interest rather than awards or verified software budgets."
        ),
    }


def discover_current(
    *, lookback_days: int = 30, limit: int = 12,
    execute: bool = False, cache: BudgetCache | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Execute only when explicitly requested. Three fixed-source, bounded calls."""
    if isinstance(lookback_days, bool) or not isinstance(lookback_days, int) or not 7 <= lookback_days <= 90:
        raise ValueError("lookback_days must be 7-90")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 2 <= limit <= MAX_RECORDS:
        raise ValueError("limit must be 2-20")
    if not isinstance(execute, bool):
        raise ValueError("execute must be a boolean")
    now = date.today()
    period_start = (now - timedelta(days=lookback_days - 1)).strftime("%Y%m%d")
    plans = [
        plan_source("openalex", limit=limit, lookback_days=lookback_days,
                    discover=True, env=env),
        plan_source("cfpb", limit=limit, lookback_days=lookback_days, env=env),
        plan_source("ted",
                    keyword=(f"PD = ({period_start} <> {now:%Y%m%d}) "
                             "AND notice-type IN (cn-standard cn-social cn-desg) "
                             "SORT BY publication-date DESC"),
                    limit=limit, env=env),
    ]
    if not execute:
        return {
            "status": "planned", "network_performed": False,
            "execute_required_for_network": True,
            "source_count": len(plans),
            "plans": [plan.public() for plan in plans],
            "budget_excludes_paid_api_tiers": True,
        }
    sources = []
    for plan in plans:
        try:
            result = collect(plan, fetch=True, cache=cache, env=env, timeout=20)
            if result.get("status") not in {
                "observed", "unavailable", "invalid_source_shape", "rate_limited",
            }:
                raise IntelligenceError("Unexpected provider result")
            # Collectors may retain arbitrary raw provider JSON in data;
            # only sanitized, bounded projections enter discovery or MCP.
            sources.append({
                key: result[key] for key in (
                    "source", "status", "observations", "cache_hit", "http_status",
                ) if key in result
            })
        except (OSError, ValueError, IntelligenceError) as exc:
            sources.append({
                "source": plan.source, "status": "unavailable",
                "reason_code": type(exc).__name__,
            })
    result = summarize_discovery(sources, as_of=now.isoformat(), lookback_days=lookback_days)
    result["network_performed"] = True
    result["queries_budgeted"] = len(plans)
    result["user_credentials_exposed"] = False
    return result


def format_discovery_report(result: dict[str, Any]) -> str:
    if result.get("mode") != "seedless_public_source_discovery_not_market_growth":
        raise ValueError("Text output requires a completed discovery result")
    lines = [
        f"CURRENT TOPIC DISCOVERY | {result['as_of']} | last {result['lookback_days']} days",
        "No predefined topic seeds. Candidate observations are NOT verified market trends.",
        "TED sample: published competition notices (cn-standard, cn-social, cn-desg), not awards or planning.",
        "",
    ]
    for item in result["source_coverage"]:
        tag = f"{item['source']}: {item['status']} | {item['recent_valid_records']}/{item['sampled_rows']} recent valid records"
        if item["future_dated_records_rejected"]:
            tag += f" | future-dated rejected:{item['future_dated_records_rejected']}"
        if item["missing_or_invalid_dates_or_identity"]:
            tag += f" | invalid/outside lookback:{item['missing_or_invalid_dates_or_identity']}"
        if "http_status" in item:
            tag += f" | HTTP {item['http_status']}"
        if item["cache_hit"]:
            tag += " (cached)"
        lines.append("Source: " + tag)
    lines.append("")
    sample_audit = result.get("ted_sampling_audit", {})
    if sample_audit and sample_audit["status"] == "observed":
        span = (
            sample_audit["earliest_sampled_publication"]
            if sample_audit["earliest_sampled_publication"]
            == sample_audit["latest_sampled_publication"] else
            sample_audit["earliest_sampled_publication"] + " to "
            + sample_audit["latest_sampled_publication"]
        )
        lines.append(
            "TED SAMPLING AUDIT: "
            f"{sample_audit['observed_notice_count']} notices span "
            f"{sample_audit['publication_days_represented']} publication date(s) "
            f"({span or 'none'}) in the requested "
            f"{sample_audit['requested_lookback_days']}-day window."
        )
        if sample_audit["first_page_hit_record_cap"]:
            lines.append(
                "Sample hit the 20-record first-page cap; earlier dates and "
                "other CPV divisions may be absent."
            )
        lines.append(
            "Primary CPV 48/72 software/IT in sampled notices: "
            f"{sample_audit['main_cpv_48_or_72_observed']} "
            "(not a market-wide frequency or proof of zero demand)."
        )
        lines.append("")
    coarse = result.get("coarse_cpv_repeats_not_candidates", [])
    if coarse:
        lines.append("BROAD CPV REPEATS — excluded from the candidate ranking:")
        for item in coarse:
            lines.append(
                f"  CPV {item['main_cpv_code']} ({item['hierarchy_level']}): "
                f"{item['notice_count_in_sample']} notices, "
                f"{item['distinct_published_buyer_labels_in_sample']} "
                "published buyer labels; shared workflow NOT verified"
            )
        lines.append("")
    buyer_review = result.get("procurement_review", {})
    if buyer_review:
        lines.append(
            "BUYER-SIDE PROCUREMENT REVIEW (bounded sample, not verified active bids): "
            f"{buyer_review['qualified_notices_in_bounded_sample']} records with "
            "published buyer label, primary CPV and at least one "
            "lot date on/after analysis date "
            f"(software/IT main CPV: {buyer_review['qualified_main_cpv_software_it']}; "
            f"other: {buyer_review['qualified_other_main_cpv_sectors']})."
        )
        lines.append(
            "Source-based review only: buyer legal identities, tender amendments, "
            "eligibility, awarded spend, software-only budgets and market growth unverified."
        )
        lines.append("")
    if not result["candidates"]:
        lines.append("No recurring current themes passed conservative grouping in this small sample.")
    for idx, item in enumerate(result["candidates"], start=1):
        lines.append(
            f"{idx}. {item['label']} | investigation {item['investigation_priority']}/2 "
            f"| {item['unique_recent_records_in_sample']} distinct source records "
            f"| {', '.join(item['sources'])}"
        )
        lines.append("   Basis: " + item["basis"].replace("_", " "))
        for original in item["examples"][:2]:
            title = "".join(c if c.isprintable() else " " for c in original["title"])
            lines.append(
                f"   - {original['source']} {original['date']}: {' '.join(title.split())[:90]}"
            )
            lines.append(f"     {original['reference']}")
        if item["basis"] == "cfpb_public_product_issue_categories":
            lines.append(
                "   Interpretation: repeat complaints in one source, not "
                "independent buyers or verified market growth"
            )
        if item["basis"] == "ted_distinct_published_buyer_labels_shared_primary_cpv":
            lines.append(
                "   Buyer-side repeat: "
                f"{item['distinct_published_buyer_labels_in_sample']} distinct "
                "published buyer labels; CPV category-or-finer only; "
                "shared workflows, legal-entity identities, awards and "
                "market growth NOT verified"
            )
        lines.append("   Next: " + item["next_check"])
        lines.append("")
    if result.get("procurement_observations"):
        lines.append("Recent EU procurement notices (not confirmed new purchases):")
        for notice in result["procurement_observations"]:
            title = "".join(c if c.isprintable() else " " for c in notice["title"])
            lines.append(
                f"  TED [{notice['date']}] {' '.join(title.split())[:100]}"
            )
            details = []
            if notice.get("buyer_side_review_selected"):
                details.append("buyer-side review: inspect original notice")
            if notice["buyer_name"]:
                buyer = "".join(c if c.isprintable() else " " for c in notice["buyer_name"])
                details.append("buyer published: " + " ".join(buyer.split())[:85])
            details.append(notice["procurement_stage"].replace("_", " "))
            if notice["buyer_country_code"]:
                details.append("buyer country: " + notice["buyer_country_code"])
            if notice["main_cpv_code"]:
                details.append("main CPV: " + notice["main_cpv_code"])
            if notice.get("main_cpv_software_it_category"):
                details.append("main CPV software/IT class 48/72; scope not verified")
            if len(notice.get("cpv_codes", [])) > 1:
                extra = [
                    code for code in notice["cpv_codes"]
                    if code != notice["main_cpv_code"]
                ][:4]
                if extra:
                    details.append("other published CPVs: " + ", ".join(extra))
            if notice["latest_lot_deadline_date"]:
                details.append("last published lot date: " + notice["latest_lot_deadline_date"])
            if notice["estimated_value_as_published"]:
                details.append(
                    "estimated (not spent): "
                    + notice["estimated_value_as_published"] + " "
                    + notice["estimated_value_currency"]
                )
            if notice["title_language"]:
                details.append("title language: " + notice["title_language"])
            lines.append("    " + " | ".join(details))
            lines.append(f"    {notice['reference']}")
        lines.append("")
    if result.get("research_observations"):
        lines.append("Recent scholarly work (research activity, not buyer demand):")
        for work in result["research_observations"]:
            title = "".join(c if c.isprintable() else " " for c in work["title"])
            lines.append(f"  OpenAlex [{work['date']}] {' '.join(title.split())[:95]}")
            if work["provider_assigned_topic"]:
                topic = "".join(
                    c if c.isprintable() else " "
                    for c in work["provider_assigned_topic"]
                )
                lines.append(
                    f"    Provider topic (algorithmic): {' '.join(topic.split())[:85]}"
                )
            lines.append(f"    {work['reference']}")
        lines.append("")
    lines.append("Other recent source observations (not validated trends):")
    for source, examples in result["sample_examples_by_source"].items():
        for item in examples[:1]:
            title = "".join(c if c.isprintable() else " " for c in item["title"])
            lines.append(f"  {source} [{item['date']}]: {' '.join(title.split())[:90]}")
            lines.append(f"    {item['reference']}")
    lines.append(
        "Growth, buyer budgets and market size: NOT VERIFIED. "
        "CFPB complaint counts are not a representative market sample. "
        "Later comparable source histories may improve confidence."
    )
    return "\n".join(lines)


def record_discovery_history(
    result: dict[str, Any], path: Path | None = None,
) -> dict[str, Any]:
    """Opt-in 90-day hashed candidate-index history; no raw records retained."""
    if result.get("mode") != "seedless_public_source_discovery_not_market_growth":
        raise ValueError("Record only completed discovery runs")
    db = Path(path) if path is not None else (
        Path.home() / ".mcp-trendpulse" / "intelligence" / "discovery_history.sqlite"
    )
    if not db.is_absolute() or db.is_symlink() or db.parent.is_symlink():
        raise ValueError("Use an absolute nonsymlink history path")
    db.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    cutoff = (date.today() - timedelta(days=90)).isoformat()
    run_date = _day(result["as_of"], "as_of").isoformat()
    with sqlite3.connect(db, timeout=10) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS discovery_candidates (
                day TEXT NOT NULL, candidate_hash TEXT NOT NULL,
                sample_records INTEGER NOT NULL, source_classes INTEGER NOT NULL,
                PRIMARY KEY(day, candidate_hash)
            )
        """)
        for c in result["candidates"][:12]:
            connection.execute("""
                INSERT INTO discovery_candidates VALUES (?, ?, ?, ?)
                ON CONFLICT(day, candidate_hash) DO UPDATE SET
                    sample_records=excluded.sample_records,
                    source_classes=excluded.source_classes
            """, (
                run_date, c["candidate_id"],
                c["unique_recent_records_in_sample"], c["distinct_source_classes"],
            ))
        connection.execute("DELETE FROM discovery_candidates WHERE day < ?", (cutoff,))
    return {
        "status": "recorded", "candidate_count": len(result["candidates"]),
        "history_path": str(db), "raw_records_saved": False,
        "growth_verified": False,
    }
