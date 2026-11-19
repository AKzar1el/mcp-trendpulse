"""Offline, provenance-preserving observation layer for optional free intelligence.

Produces a cautious source trail and exact registry-identifier joins from
caller-supplied `intelligence_collect` outputs. It does not fetch, score a
startup, infer market growth from search pages, or access credentials.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, timedelta
from typing import Any

from mcp_trendpulse.intelligence_opportunities import LANES, SOURCE_KIND, _day, _string

# GLEIF's published Registration Authorities list for the three Companies
# House registries. Name similarity alone is NEVER a verified entity join.
UK_COMPANIES_HOUSE_RA = {"RA000585", "RA000586", "RA000587"}
COMPANY_NUMBER = re.compile(r"[A-Z0-9]{8}")
LEI = re.compile(r"[A-Z0-9]{20}")
OPENALEX_WORK = re.compile(r"https://openalex\.org/(W[0-9]{4,15})")
SAFE_RECORD = re.compile(r"[A-Za-z0-9._:-]{1,100}")
ALLOWED = {
    "companies_house", "gleif", "openalex", "usaspending", "ted",
    "github_issues", "cordis", "cfpb", "greenhouse",
}
MAX_INPUT_BYTES = 220_000
MAX_SNAPSHOTS = 12
MAX_ROWS = 160


def _text(value: Any, size: int = 130) -> str:
    return " ".join(value.split())[:size] if isinstance(value, str) else ""


def _date(value: Any, asof: date) -> str | None:
    if not isinstance(value, str):
        return None
    day_string = value[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", day_string) is None:
        return None
    try:
        when = date.fromisoformat(day_string)
    except ValueError:
        return None
    return when.isoformat() if when <= asof else None


def _key(value: Any) -> str:
    if isinstance(value, int) and not isinstance(value, bool):
        value = str(value)
    if not isinstance(value, str) or SAFE_RECORD.fullmatch(value) is None:
        return ""
    return value


def _entry(source: str, raw: dict[str, Any], asof: date) -> dict[str, Any] | None:
    """Extract only source-published non-personal fields, never raw payloads."""
    result: dict[str, Any] = {"source": source, "kind": SOURCE_KIND[source]}
    if source == "companies_house":
        num = _text(raw.get("company_number"), 12).upper()
        if COMPANY_NUMBER.fullmatch(num) is None:
            return None
        result.update({
            "id": num, "legal_name": _text(raw.get("title")),
            "company_number": num,
            "registry": "companies_house",
            "company_status": _text(raw.get("company_status"), 36),
            "reference": "https://find-and-update.company-information.service.gov.uk/company/" + num,
            # Incorporation is not current market demand.
            "event_date": None, "date_semantics": "registry_identity_not_trend",
        })
    elif source == "gleif":
        lei = _text(raw.get("id"), 22).upper()
        attrs = raw.get("attributes")
        if LEI.fullmatch(lei) is None or not isinstance(attrs, dict):
            return None
        ent = attrs.get("entity")
        if not isinstance(ent, dict):
            return None
        name = ent.get("legalName")
        reg = ent.get("registeredAt")
        # Some client schema projections use registrationAuthority instead.
        if reg is None:
            reg = ent.get("registrationAuthority")
        authority = reg.get("id") if isinstance(reg, dict) else ""
        registered = _text(ent.get("registeredAs"), 24).upper()
        company_number = (
            registered if authority in UK_COMPANIES_HOUSE_RA
            and COMPANY_NUMBER.fullmatch(registered) else ""
        )
        result.update({
            "id": lei, "legal_name": _text(name.get("name")) if isinstance(name, dict) else "",
            "lei": lei, "company_number": company_number,
            "registration_authority": authority if authority in UK_COMPANIES_HOUSE_RA else "",
            "reference": "https://api.gleif.org/api/v1/lei-records/" + lei,
            "event_date": None, "date_semantics": "registry_identity_not_trend",
        })
    elif source == "openalex":
        match = OPENALEX_WORK.fullmatch(_text(raw.get("id"), 80))
        if match is None:
            return None
        result.update({
            "id": match.group(1), "title": _text(raw.get("display_name")),
            "reference": "https://openalex.org/" + match.group(1),
            "event_date": _date(raw.get("publication_date"), asof),
            "date_semantics": "research_publication_not_purchase",
        })
    elif source == "usaspending":
        award_id = _key(raw.get("Award ID"))
        if not award_id:
            return None
        result.update({
            "id": award_id,
            # Awarding agency is the government buyer. Award recipient is a
            # supplier, NOT evidence that the supplier buys this category.
            "buyer_name": _text(raw.get("Awarding Agency")),
            "supplier_name": _text(raw.get("Recipient Name")),
            "title": _text(raw.get("Description"), 180),
            "reference": "https://www.usaspending.gov/search",
            "event_date": _date(raw.get("Last Modified Date"), asof),
            "date_semantics": "record_last_modified_not_award_date",
        })
        amount = raw.get("Award Amount")
        if isinstance(amount, (int, float)) and not isinstance(amount, bool):
            if 0 <= amount <= 10**15 and amount == amount and amount != float("inf"):
                result["reported_award_amount_usd"] = round(amount, 2)
                result["amount_caveat"] = "Award amount is not verified payment or addressable software budget"
    elif source == "ted":
        tender_id = _key(raw.get("publication-number") or raw.get("publication_number"))
        if not tender_id:
            return None
        result.update({
            "id": tender_id,
            "buyer_name": _text(raw.get("buyer-name") or raw.get("buyer_name")),
            "title": _text(raw.get("notice-title") or raw.get("notice_title"), 180),
            "notice_type": _text(raw.get("notice-type") or raw.get("notice_type"), 50),
            "reference": "https://ted.europa.eu/en/",
            "event_date": _date(raw.get("publication-date") or raw.get("publication_date"), asof),
            "date_semantics": "notice_publication_not_confirmed_award",
        })
    elif source == "github_issues":
        if raw.get("pull_request"):
            return None
        issue_id = _key(raw.get("id"))
        url = raw.get("html_url")
        # The provider API is the evidence origin, but never echo arbitrary
        # URLs from caller-supplied snapshots.
        ref = "https://github.com/" if not isinstance(url, str) else url
        if not re.fullmatch(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/issues/[0-9]+", ref):
            ref = "https://github.com/"
        if not issue_id:
            return None
        from mcp_trendpulse.intelligence_issue_quality import classify_github_issue

        # A cached older collector snapshot may omit the classification.
        # Classify title and vetted GitHub URL locally as a conservative
        # fallback; never treat absent body metadata as verified buyer pain.
        provided_type = raw.get("issue_evidence_type")
        issue_type = (
            provided_type
            if isinstance(provided_type, str) and provided_type in {
                "promotional_market_claim", "hypothetical_or_unverified_design",
                "profile_repository_work_item", "internal_implementation_work_item",
                "reported_operational_problem", "unverified_public_issue",
            }
            else classify_github_issue(raw.get("title"), url=ref)
        )
        result.update({
            "id": issue_id, "title": _text(raw.get("title"), 180),
            "reference": ref, "issue_evidence_type": issue_type,
            "event_date": _date(raw.get("created_at"), asof),
            "date_semantics": "issue_creation_not_buyer_spend",
        })
    elif source == "cordis":
        ident = _key(raw.get("id"))
        if not ident:
            return None
        result.update({
            "id": ident, "title": _text(raw.get("title"), 180),
            "reference": "https://cordis.europa.eu/",
            "event_date": None, "date_semantics": "research_project_no_comparable_event_date",
        })
    elif source == "cfpb":
        ident = _key(raw.get("public_complaint_id"))
        if not ident:
            return None
        product = _text(raw.get("product"), 70)
        issue = _text(raw.get("issue"), 140)
        # Product + issue are public categories; never project narratives.
        result.update({
            "id": ident,
            "title": " - ".join(part for part in (product, issue) if part),
            "consumer_product": product, "reported_issue": issue,
            "company_name": _text(raw.get("company")),
            "reference": "https://www.consumerfinance.gov/data-research/consumer-complaints/",
            "event_date": _date(raw.get("date_received"), asof),
            "date_semantics": "complaint_received_not_purchase",
        })
    elif source == "greenhouse":
        ident = _key(raw.get("id"))
        if not ident:
            return None
        result.update({
            "id": ident, "title": _text(raw.get("title"), 160),
            "reference": "https://www.greenhouse.com/",
            "event_date": None,
            "date_semantics": "job_index_without_verified_publication_date",
        })
    else:
        return None
    return result


def observe_source_snapshots(
    topic: str, snapshots: list[dict[str, Any]], *, as_of: str | None = None,
) -> dict[str, Any]:
    """Explain a bounded set of source snapshots without manufacturing trends."""
    subject = _string(topic, "topic", 100)
    if not isinstance(snapshots, list) or not 1 <= len(snapshots) <= MAX_SNAPSHOTS:
        raise ValueError("Provide 1-12 bounded intelligence_collect snapshots")
    try:
        size = len(json.dumps(snapshots, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Snapshots must be finite, serializable JSON") from exc
    if size > MAX_INPUT_BYTES:
        raise ValueError("Snapshots exceed 220 KB")
    asof = _day(as_of, "as_of") if as_of is not None else date.today()
    sources: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    first_company: dict[str, dict[str, Any]] = {}
    other_company: dict[str, dict[str, Any]] = {}
    ignored = Counter()
    source_unique = set()
    for row in snapshots:
        if not isinstance(row, dict):
            raise ValueError("Each snapshot must be an object")
        source = row.get("source")
        if source not in ALLOWED:
            raise ValueError("Unsupported source; only nine validated observation adapters accepted")
        if source in source_unique:
            raise ValueError("Only one source response per observation batch")
        source_unique.add(source)
        status = row.get("status")
        if status not in {"observed", "unavailable", "invalid_source_shape", "rate_limited"}:
            raise ValueError("Unknown source response status")
        report: dict[str, Any] = {
            "source": source, "kind": SOURCE_KIND[source], "status": status,
            "source_health": "reported_healthy" if status == "observed" else "not_verified",
            "sample_complete": False, "population_coverage_verified": False,
            "records_examined": 0, "records_accepted": 0,
            "cache_hit": row.get("cache_hit") is True,
            "quality_reclassified_from_cached_payload": 0,
        }
        # Only publish bounded, known diagnostic fields; never copy arbitrary
        # HTTP responses, auth values or provider error texts to the watchlist.
        code = row.get("http_status")
        if isinstance(code, int) and not isinstance(code, bool) and 100 <= code <= 599:
            report["http_status"] = code
        reason = row.get("reason")
        if isinstance(reason, str) and reason in {
            "HTTPError", "URLError", "TimeoutError", "provider_cooldown",
            "not_configured", "source_setup_required_or_invalid_plan",
            "collection_failed", "invalid_source_shape",
        }:
            report["reason"] = reason
        if status != "observed":
            report["caveat"] = "Source unavailable or invalid; not evidence of zero interest"
            sources.append(report)
            continue
        obs = row.get("observations")
        if not isinstance(obs, dict) or not isinstance(obs.get("sample"), list):
            report["status"] = "invalid_source_shape"
            report["source_health"] = "not_verified"
            report["caveat"] = "Missing validated collector observations; not zero demand"
            sources.append(report)
            continue
        sample = obs["sample"]
        count = obs.get("record_count")
        if (isinstance(count, bool) or not isinstance(count, int)
                or count < 0 or len(sample) > 20 or count < len(sample)):
            report["status"] = "invalid_source_shape"
            report["source_health"] = "not_verified"
            report["caveat"] = "Invalid bounded sample or upstream result count"
            sources.append(report)
            continue
        report["records_examined"] = len(sample)
        # record_count counts the collector's bounded projection, NOT the
        # provider's whole result population. This is never a complete
        # 28-day search, even when count equals the sample's length.
        report["projection_sample_complete"] = count == len(sample)
        report["sample_complete"] = False
        report["caveat"] = "Only a bounded source sample; population coverage is not verified"
        # Old successful collector caches hold a *bounded, already retrieved*
        # data.items payload, while observations.sample predates body-aware
        # quality classification. Upgrade those labels IN MEMORY, without a
        # network request, deleting cache rows or exposing raw issue bodies.
        raw_issue_by_id: dict[str, dict[str, Any]] = {}
        if source == "github_issues":
            payload = row.get("data")
            raw_items = payload.get("items") if isinstance(payload, dict) else None
            if isinstance(raw_items, list):
                for raw in raw_items[:20]:
                    if isinstance(raw, dict):
                        key = _key(raw.get("id"))
                        if key and isinstance(raw.get("body"), str):
                            raw_issue_by_id[key] = raw
        for item in sample:
            if len(records) >= MAX_ROWS:
                ignored["result_budget"] += 1
                break
            if not isinstance(item, dict):
                ignored["malformed_record"] += 1
                continue
            if source == "github_issues" and raw_issue_by_id:
                from mcp_trendpulse.intelligence_issue_quality import (
                    EXCLUDED_FROM_CURRENT_HUNT, classify_github_issue,
                )

                raw_issue = raw_issue_by_id.get(_key(item.get("id")))
                # An issue ID alone must not allow a different cached item
                # to contaminate this observation's classification.
                if (raw_issue is not None
                        and raw_issue.get("title") == item.get("title")
                        and raw_issue.get("html_url") == item.get("html_url")):
                    repaired = classify_github_issue(
                        raw_issue.get("title"), raw_issue.get("body"),
                        raw_issue.get("html_url"),
                    )
                    previous = item.get("issue_evidence_type")
                    # Preserve a previously stricter classification if the
                    # truncated cached body omits its original evidence.
                    if repaired in EXCLUDED_FROM_CURRENT_HUNT and repaired != previous:
                        item = {**item, "issue_evidence_type": repaired}
                        report["quality_reclassified_from_cached_payload"] += 1
                    elif not isinstance(previous, str) or previous not in {
                        "promotional_market_claim", "hypothetical_or_unverified_design",
                        "profile_repository_work_item",
                        "internal_implementation_work_item",
                        "reported_operational_problem", "unverified_public_issue",
                    }:
                        item = {**item, "issue_evidence_type": repaired}
                        report["quality_reclassified_from_cached_payload"] += 1
            entry = _entry(source, item, asof)
            if entry is None:
                ignored["unsupported_or_unidentified_record"] += 1
                continue
            identity = (source, entry["id"])
            if identity in seen:
                ignored["duplicate_provider_record"] += 1
                continue
            seen.add(identity)
            records.append(entry)
            report["records_accepted"] += 1
            if source == "companies_house" and entry["company_number"] not in first_company:
                first_company[entry["company_number"]] = entry
            if source == "gleif" and entry["company_number"]:
                other_company[entry["lei"]] = entry
        sources.append(report)
    exact_matches: list[dict[str, Any]] = []
    for lei, entity in sorted(other_company.items()):
        company = first_company.get(entity["company_number"])
        if company:
            exact_matches.append({
                "match_type": "registration_authority_and_company_number",
                "companies_house_number": company["company_number"],
                "companies_house_name": company["legal_name"],
                "gleif_name": entity["legal_name"], "lei": lei,
                "registration_authority": entity["registration_authority"],
                "name_conflict_requires_review": (
                    company["legal_name"].casefold() != entity["legal_name"].casefold()
                ),
                "references": [company["reference"], entity["reference"]],
                "paid_buyer_verified": False,
            })
    cutoff = (asof - timedelta(days=29)).isoformat()
    recent = [
        row for row in records
        if row.get("event_date") is not None
        and row["event_date"] >= cutoff
        and row["date_semantics"] not in {
            "record_last_modified_not_award_date",
            "registry_identity_not_trend",
        }
    ]
    # Literal text overlap is an audit aid, NOT semantic similarity, market
    # momentum, a cross-organizational identity join or buyer confirmation.
    topic_normal = " ".join(subject.casefold().split())
    literal_matches = [
        record for record in records if topic_normal in " ".join(
            str(record.get(field, "")) for field in (
                "title", "legal_name", "buyer_name", "company_name",
            )
        ).casefold()
    ]
    lane_coverage = []
    for lane, info in LANES.items():
        relevant = [r for r in sources if r["source"] in info["sources"]
                    and r["status"] == "observed" and r["records_accepted"] > 0]
        overlap = [r for r in literal_matches if r["source"] in info["sources"]]
        lane_coverage.append({
            "lane": lane, "recipe_sources": len(info["sources"]),
            "sampled_sources": len(relevant),
            "literal_topic_records_in_sample": len(overlap),
            "distinct_topic_evidence_classes": len({r["kind"] for r in overlap}),
            "decision": (
                "review_original_sources_and_buyer_workflow"
                if len({r["kind"] for r in overlap}) >= 2 else
                "insufficient_topical_cross_source_evidence"
            ),
            "not_a_validated_market_opportunity": True,
        })
    lane_coverage.sort(key=lambda r: (
        -r["distinct_topic_evidence_classes"], -r["sampled_sources"], r["lane"]
    ))
    counts = Counter(row["kind"] for row in records)
    unresolved = [src["source"] for src in sources if src["source_health"] != "reported_healthy"]
    return {
        "as_of": asof.isoformat(), "topic": subject,
        "mode": "bounded_source_observations_not_market_forecast",
        "provenance": "caller_supplied_collector_outputs_not_independently_authenticated",
        "source_coverage": sources, "coverage_degraded": bool(unresolved),
        "unavailable_sources": unresolved, "records_reviewed": len(records),
        "evidence_class_counts": dict(sorted(counts.items())),
        "exact_registry_matches": exact_matches[:20],
        "name_only_matches_promoted": 0,
        "dated_recent_sample_records": len(recent),
        "dated_recent_sample_by_class": dict(sorted(Counter(x["kind"] for x in recent).items())),
        "sample_records": records[:40],
        "literal_topic_matches_in_sample": len(literal_matches),
        "literal_matching_is_not_semantic_relevance": True,
        "eighteen_lane_coverage": lane_coverage,
        "discarded_records": dict(ignored),
        "market_momentum": {
            "status": "not_estimable_from_relevance_ranked_samples",
            "reason": "No complete dated baseline, page coverage, stable source denominators or matched buyer spending",
            "complete_28_day_series": False,
        },
        "buyer_budget_verified": False,
        "paid_customer_outcome_verified": False,
        "success_probability": None,
        "next_checks": [
            "Verify primary source records and legal entity identities",
            "Link original awards or notices to the same named budget owner and exact workflow",
            "Establish complete comparable daily event coverage before claiming growth",
            "Interview budget owners and verify whether current substitutes are funded",
        ],
        "externally_visible_requests_performed": 0,
    }
