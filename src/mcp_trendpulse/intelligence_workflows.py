"""Offline, evidence-attributed workflow leads from current seedless discovery.

These are *investigations*, not software products, independently verified buyers,
customer demand, market-size estimates or growth forecasts. No network or LLM.
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import date
from typing import Any

MAX_BRIEFS = 6
MAX_PROCUREMENT_BRIEFS = 4
MAX_PROBLEM_BRIEFS = 2
MAX_RESEARCH_LINKS = 2
MAX_NORMALIZED_RECORDS = 60
CFPB_LANDING = "https://www.consumerfinance.gov/data-research/consumer-complaints/"
TED_LINK = re.compile(r"https://ted\.europa\.eu/en/notice/-/detail/[0-9]{1,7}-20[0-9]{2}")
OPENALEX_WORK = re.compile(r"https://openalex\.org/W[0-9]{4,15}")
OPENALEX_TOPIC = re.compile(r"https://openalex\.org/T[0-9]{4,10}")
CPV = re.compile(r"[0-9]{8}")
AMOUNT = re.compile(r"[0-9]{1,13}(?:\.[0-9]{1,2})?")
CURRENCY = re.compile(r"[A-Z]{3}")

# Phrase overlap is a weak *lexical* research clue, never semantic validation.
# Exclude generic software/research wording to prevent artificial joins.
GENERIC = frozenset((
    "a an and are by for from in into of on or the to with without based "
    "study studies research analysis software services service systems system "
    "project projects method methods application applications development "
    "information technical technology technologies new recent current general "
    "public private management data report reports results approach approaches"
).split())


def _clean(value: Any, length: int = 125) -> str:
    if not isinstance(value, str):
        return ""
    clean = "".join(ch if ch.isprintable() else " " for ch in value)
    return " ".join(clean.split())[:length]


def _day(value: Any, as_of: date) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
        return ""
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return ""
    return value if parsed <= as_of else ""


def _reference(source: str, value: Any) -> str:
    if not isinstance(value, str):
        return ""
    if source == "ted" and TED_LINK.fullmatch(value):
        return value
    if source == "openalex" and OPENALEX_WORK.fullmatch(value):
        return value
    if source == "cfpb" and value == CFPB_LANDING:
        return value
    return ""


def _phrases(value: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", value.lower())
    phrases = set()
    for width in (2, 3, 4):
        for offset in range(max(0, len(words) - width + 1)):
            segment = words[offset:offset + width]
            phrase = " ".join(segment)
            if (12 <= len(phrase) <= 65
                    and all(len(word) >= 3 and word not in GENERIC for word in segment)
                    and any(len(word) >= 5 for word in segment)):
                phrases.add(phrase)
    return phrases


def _shared_phrase(left: str, right: str) -> str:
    common = _phrases(left) & _phrases(right)
    return sorted(common, key=lambda p: (-len(p.split()), -len(p), p))[0] if common else ""


def _evidence(record: dict[str, Any], as_of: date) -> dict[str, Any] | None:
    source = record.get("source")
    if source not in {"ted", "cfpb", "openalex"}:
        return None
    ref = _reference(source, record.get("reference"))
    title = _clean(record.get("title"), 140)
    day = _day(record.get("date"), as_of)
    if not ref or not title or not day:
        return None
    return {
        "source": source, "date": day, "title": title,
        "reference": ref,
        "reference_specificity": (
            "source_landing_not_individual_complaint"
            if source == "cfpb" else "exact_source_record"
        ),
        "date_semantics": {
            "ted": "notice_publication_not_award",
            "cfpb": "complaint_received_not_customer_purchase",
            "openalex": "research_publication_not_adoption",
        }[source],
    }


def _research_links(
    label: str, works: list[dict[str, Any]], *, as_of: date,
) -> list[dict[str, Any]]:
    links = []
    used = set()
    for work in works:
        topic = _clean(work.get("theme"), 100)
        phrase = _shared_phrase(label, topic)
        proof = _evidence(work, as_of)
        if not phrase or proof is None or proof["reference"] in used:
            continue
        links.append({
            "basis": "exact_contiguous_multitoken_phrase_not_same_workflow_proof",
            "shared_source_phrase": phrase,
            "provider_assigned_research_topic": topic,
            "research_record": proof,
            "research_is_not_buyer_demand": True,
        })
        used.add(proof["reference"])
        if len(links) == MAX_RESEARCH_LINKS:
            break
    return links


def _base_brief(kind: str, label: str, samples: list[dict[str, Any]],
                *, research: list[dict[str, Any]], as_of: date) -> dict[str, Any]:
    observed = [x for item in samples if (x := _evidence(item, as_of)) is not None]
    key = kind + "|" + label.casefold() + "|" + observed[0]["reference"]
    return {
        "brief_id": hashlib.sha256(key.encode()).hexdigest()[:14],
        "kind": kind, "source_published_workflow_clue": label,
        "sampled_original_record_count": len(samples),
        "evidence": observed[:2],
        "source_family_count": 1,
        "research_context": _research_links(label, research, as_of=as_of),
        "measured_research_context": [],
        "related_operational_problem_context": [],
        "buyer_legal_identity_verified": False,
        "same_workflow_across_sources_verified": False,
        "repeatable_software_product_verified": False,
        "independent_paying_customers_verified": False,
        "buyer_willingness_to_pay_verified": False,
        "market_growth_verified": False,
        "seo_demand_verified": False,
    }


def build_workflow_briefs(
    records: list[dict[str, Any]], *, as_of: date,
) -> dict[str, Any]:
    """Deterministic, read-only candidate assembly from normalized records.

    Preserves source metadata; never rewrites provider titles into imagined
    product categories, joins buyers by name or fabricates source coverage.
    """
    if (not isinstance(records, list) or len(records) > MAX_NORMALIZED_RECORDS
            or not isinstance(as_of, date)
            or any(not isinstance(row, dict) for row in records)):
        raise ValueError("Expected <=60 normalized records and an analysis date")
    research = sorted(
        (r for r in records if r.get("source") == "openalex"),
        key=lambda r: str(r.get("date", "")), reverse=True,
    )
    complaints: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in records:
        if (row.get("source") != "cfpb"
                or row.get("theme_basis") != "cfpb_public_product_issue_categories"
                or not _evidence(row, as_of)):
            continue
        theme = _clean(row.get("theme"), 120)
        identifier = row.get("id")
        if (not theme or not isinstance(identifier, str)
                or re.fullmatch(r"[A-Za-z0-9._:-]{1,100}", identifier) is None):
            continue
        complaints[theme][identifier] = row
    problem_groups = [
        (label, sorted(rows.values(), key=lambda x: x["date"], reverse=True))
        for label, rows in complaints.items() if len(rows) >= 2
    ]
    problem_groups.sort(key=lambda pair: (-len(pair[1]), pair[0].casefold()))

    # Past or incomplete publication criteria are historical context, not
    # forward-looking tenders. A future published deadline is NOT proof that
    # a tender remains open, unamended or addressable by a new supplier.
    tender_rows = []
    tender_context = []
    for row in records:
        if (row.get("source") != "ted"
                or row.get("procurement_stage") != "contract_notice_not_award"
                or not _evidence(row, as_of)):
            continue
        cpv = row.get("main_cpv_code")
        if not isinstance(cpv, str) or not CPV.fullmatch(cpv) or cpv[:2] not in {"48", "72"}:
            continue
        last_day = _day(row.get("latest_lot_deadline_date"), date.max)
        buyer = _clean(row.get("buyer_name"), 100)
        qualifies = bool(buyer and last_day and last_day >= as_of.isoformat())
        if qualifies:
            tender_rows.append(row)
        else:
            reason = (
                "published_lot_date_before_analysis"
                if last_day and last_day < as_of.isoformat()
                else "published_buyer_label_missing" if not buyer
                else "published_lot_date_missing_or_invalid"
            )
            tender_context.append({
                "title": _clean(row.get("title"), 130),
                "reference": _reference("ted", row.get("reference")),
                "published_primary_cpv": cpv,
                "published_last_lot_date": last_day,
                "reason": reason,
                "not_an_upcoming_procurement_lead": True,
                "actual_tender_status_not_verified": True,
            })
    tender_rows.sort(key=lambda row: (
        str(row.get("date", "")),
        str(row.get("latest_lot_deadline_date", "")),
        str(row.get("reference", "")),
    ), reverse=True)
    tender_context.sort(key=lambda row: (
        row["published_last_lot_date"], row["reference"]
    ), reverse=True)

    briefs = []
    for row in tender_rows[:MAX_PROCUREMENT_BRIEFS]:
        label = _clean(row["title"], 130)
        brief = _base_brief("published_software_it_procurement_to_investigate",
                            label, [row], research=research, as_of=as_of)
        amount = row.get("estimated_value_as_published")
        currency = row.get("estimated_value_currency")
        estimate = (
            {"amount": amount, "currency": currency,
             "procedure_estimate_not_awarded_or_software_only_spend": True}
            if isinstance(amount, str) and AMOUNT.fullmatch(amount)
            and isinstance(currency, str) and CURRENCY.fullmatch(currency)
            else None
        )
        brief.update({
            "published_buyer_label": _clean(row.get("buyer_name"), 100),
            "buyer_country_code": _clean(row.get("buyer_country_code"), 3),
            "published_primary_cpv": row["main_cpv_code"],
            "published_last_lot_date": _day(row.get("latest_lot_deadline_date"), date.max),
            "published_lot_date_on_or_after_analysis": True,
            "tender_open_status_verified": False,
            "software_lot_scope_verified": False,
            "published_procedure_estimate": estimate,
            "next_validation": (
                "Read original lot and eligibility; identify a repeatable "
                "software task, incumbent alternatives and a real purchaser."
            ),
        })
        for problem_label, rows in problem_groups:
            phrase = _shared_phrase(label, problem_label)
            if not phrase:
                continue
            brief["related_operational_problem_context"].append({
                "reported_category": problem_label,
                "shared_source_phrase": phrase,
                "complaints_in_bounded_sample": len(rows),
                "source_reference": CFPB_LANDING,
                "reference_specificity": "source_landing_not_individual_complaint",
                "relationship": "lexical_phrase_only_not_verified_same_workflow",
            })
            break
        briefs.append(brief)

    for label, rows in problem_groups[:MAX_PROBLEM_BRIEFS]:
        brief = _base_brief("recurring_public_consumer_issue_to_investigate",
                            label, rows, research=research, as_of=as_of)
        brief.update({
            "consumer_issue_source_category": label,
            "published_buyer_label": "",
            "buyer_not_identified_from_complaints": True,
            "distinct_complaint_ids_not_distinct_customers": True,
            "next_validation": (
                "Identify the repeatable resolution task, affected users, "
                "the responsible organization, alternatives and who pays."
            ),
        })
        briefs.append(brief)

    return {
        "status": ("source_backed_workflow_investigations"
                   if briefs else "no_workflow_investigation_from_sample"),
        "mode": "source_grounded_workflow_briefs_not_validated_market_demand",
        "briefs": briefs, "brief_count": len(briefs),
        "max_briefs": MAX_BRIEFS,
        "sampled_software_it_contract_notices": len(tender_rows) + len(tender_context),
        "sampled_software_it_notices_with_future_or_today_published_lot_dates": len(tender_rows),
        "sampled_software_it_notices_not_forward_qualified": len(tender_context),
        "past_or_incomplete_tender_context": tender_context[:3],
        "sampled_repeated_consumer_issue_groups": len(problem_groups),
        "source_requests_added": 0,
        "no_predefined_industry_seeds": True,
        "no_llm_inference_or_synonym_expansion": True,
        "no_raw_provider_narratives_or_credentials_returned": True,
        "unmatched_research_is_not_absence_of_application": True,
        "source_populations_or_trend_growth_verified": False,
        "product_market_fit_verified": False,
        "method": (
            "Only source-published software/IT main-CPV contract notices and "
            "recurring CFPB product/issue categories. Research association "
            "requires an identical multiword phrase in provider-assigned "
            "topic and workflow clue, and is lexical context only."
        ),
    }


def attach_measured_research(
    result: dict[str, Any], trend_evidence: dict[str, Any],
) -> None:
    """Attach source-counted OpenAlex topics only after strict phrase matching."""
    watchlist = trend_evidence.get("idea_watchlist", [])
    if not isinstance(watchlist, list):
        return
    for brief in result.get("briefs", []):
        label = brief["source_published_workflow_clue"]
        for topic in watchlist[:20]:
            if not isinstance(topic, dict):
                continue
            code = topic.get("topic_id")
            name = _clean(topic.get("label"), 100)
            if not isinstance(code, str) or not re.fullmatch(r"T[0-9]{4,10}", code):
                continue
            phrase = _shared_phrase(label, name)
            if not phrase:
                continue
            ref = "https://openalex.org/" + code
            if not OPENALEX_TOPIC.fullmatch(ref):
                continue
            brief["measured_research_context"].append({
                "source": "openalex", "topic_id": code,
                "provider_assigned_topic": name,
                "source_topic_reference": ref,
                "source_measured_direction": _clean(topic.get("research_direction"), 55),
                "shared_source_phrase": phrase,
                "connection": "lexical_only_not_verified_same_workflow",
                "research_momentum_is_not_buyer_or_product_demand": True,
            })
            break


def format_workflow_briefs(result: dict[str, Any]) -> list[str]:
    if result.get("mode") != "source_grounded_workflow_briefs_not_validated_market_demand":
        raise ValueError("Requires a completed opt-in workflow brief")
    lines = [
        "SOURCE-ATTRIBUTED COMMERCIAL WORKFLOW INVESTIGATIONS (opt-in; no new API calls):",
        "  Published IT procurement and repeated consumer issues are leads, NOT ready-made products, buyers or market growth.",
        "  Academic topics are linked only by exact multiword source phrasing; synonyms and independent buying intent are NOT inferred.",
    ]
    if not result["briefs"]:
        lines.append("  No qualifying workflow clues in the bounded source sample; this is NOT a market-wide negative finding.")
    if result.get("sampled_software_it_notices_not_forward_qualified"):
        lines.append(
            "  Software/IT notices excluded from forward-looking briefs: "
            f"{result['sampled_software_it_notices_not_forward_qualified']} "
            "(past/missing published lot dates or missing buyer label; not an active-bid conclusion)."
        )
        for item in result.get("past_or_incomplete_tender_context", [])[:3]:
            lines.append(
                f"  - Historical/incomplete TED context: {item['title']} "
                f"| reason: {item['reason']} "
                f"| published last lot date: {item['published_last_lot_date'] or 'missing'}"
            )
            lines.append("    " + item["reference"])
    for index, item in enumerate(result["briefs"], 1):
        lines.append(f"  {index}. {item['source_published_workflow_clue']} [{item['kind']}]")
        lines.append(
            f"     Source records in bounded sample: {item['sampled_original_record_count']}"
            " | independent paying buyers: NOT VERIFIED"
        )
        if item["kind"] == "published_software_it_procurement_to_investigate":
            lines.append(
                f"     Published buyer label: {item['published_buyer_label'] or 'missing'}"
                f" | main CPV: {item['published_primary_cpv']}"
                f" | published lot date: {item['published_last_lot_date'] or 'missing'}"
            )
            amount = item["published_procedure_estimate"]
            if amount:
                lines.append(
                    f"     Procedure estimate (NOT spent or software-only): "
                    f"{amount['amount']} {amount['currency']}"
                )
        else:
            lines.append("     CFPB category repetition does not identify distinct people or paying firms.")
        for proof in item["evidence"][:2]:
            lines.append(f"     {proof['source']} [{proof['date']}]: {proof['reference']}")
        for link in item["research_context"][:1]:
            lines.append(
                f"     Research phrase overlap (NOT adoption): {link['shared_source_phrase']}"
                f" | {link['research_record']['reference']}"
            )
        for link in item["measured_research_context"][:1]:
            lines.append(
                f"     Measured research topic lexical overlap: {link['shared_source_phrase']}"
                f" | {link['source_topic_reference']}"
            )
        for link in item["related_operational_problem_context"][:1]:
            lines.append(
                f"     Complaint-category lexical overlap only: {link['reported_category']}"
                f" | {link['source_reference']}"
            )
        lines.append("     Next validation: " + item["next_validation"])
    lines.append(
        "  Source samples are capped and non-representative. No verified buyer identity, "
        "active bid, software-only budget, adoption, trend growth or SEO volume."
    )
    return lines
