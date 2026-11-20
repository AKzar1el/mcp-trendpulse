"""Source-backed product hypotheses and keyword validation queues.

Explicitly NOT an AI oracle, search-volume source or commercial forecast.
This module uses existing bounded discovery output and optional operator-supplied
normalized Google Trends evidence. It makes no network requests.
"""
from __future__ import annotations

import json
import re
from typing import Any

MAX_IDEAS = 6
MAX_KEYWORDS_PER_IDEA = 4
MAX_EVIDENCE_BYTES = 65536
MAX_SCOPE_CONTEXT = 150
WORD = re.compile(r"[^\W_]+(?:-[^\W_]+)*", re.UNICODE)
TED_REF = re.compile(r"https://ted\.europa\.eu/en/notice/-/detail/[0-9]{1,7}-20[0-9]{2}")
CFPB_REF = "https://www.consumerfinance.gov/data-research/consumer-complaints/"
PROOF_LABEL = "hypothesis_not_verified_search_query"
# These words are generic structure, not an industry keyword seed corpus.
GENERIC_WORDS = frozenset((
    "and und oder the with for from into of der die das einer einem einen"
    " mehr weitere einschließlich digital online service services software"
    " systems system platform portal project projects other personal"
    " consumer consumers problem report your information on"
).split())
# Official TED buyer-country is ISO-3166 alpha-3. Provider keyword geos
# use alpha-2; map known European market codes explicitly and fail closed
# on unknown values (never silently treat a source country as US).
COUNTRY_BY_ISO3 = {
    "ALB": "AL", "AND": "AD", "AUT": "AT", "BEL": "BE",
    "BGR": "BG", "BIH": "BA", "CHE": "CH", "CYP": "CY",
    "CZE": "CZ", "DEU": "DE", "DNK": "DK", "ESP": "ES",
    "EST": "EE", "FIN": "FI", "FRA": "FR", "GBR": "GB",
    "GRC": "GR", "HRV": "HR", "HUN": "HU", "IRL": "IE",
    "ISL": "IS", "ITA": "IT", "LIE": "LI", "LTU": "LT",
    "LUX": "LU", "LVA": "LV", "MCO": "MC", "MDA": "MD",
    "MKD": "MK", "MLT": "MT", "MNE": "ME", "NLD": "NL",
    "NOR": "NO", "POL": "PL", "PRT": "PT", "ROU": "RO",
    "SRB": "RS", "SVK": "SK", "SVN": "SI", "SWE": "SE",
    "TUR": "TR", "UKR": "UA",
}


def _clean(value: Any, maximum: int = 140) -> str:
    if not isinstance(value, str):
        return ""
    chars = "".join(ch if ch.isprintable() else " " for ch in value)
    return " ".join(chars.split())[:maximum]


def _keyword(text: str) -> str:
    # Do not translate or insert imagined terms. Preserve the language
    # and accent of the original publicly projected title.
    text = _clean(text, 160)
    if not text or len(text) < 5:
        return ""
    return text.casefold()


def _observed_keywords(brief: dict[str, Any]) -> list[dict[str, Any]]:
    origin = brief.get("kind")
    candidates: list[tuple[str, str]] = []
    if origin == "recurring_public_consumer_issue_to_investigate":
        label = _clean(brief.get("consumer_issue_source_category"), 130)
        if " — " in label:
            product, issue = label.split(" — ", 1)
            candidates.extend([
                (issue, "published_cfpb_issue_category"),
                (product, "published_cfpb_product_category"),
                (f"{product} {issue}", "combined_published_categories_not_an_observed_query"),
            ])
    elif origin == "published_software_it_procurement_to_investigate":
        scope = brief.get("published_scope_context")
        if isinstance(scope, dict):
            for key in (
                "lot_title_excerpts_without_lot_identity",
                "procedure_description",
            ):
                values = scope.get(key)
                if not isinstance(values, list):
                    continue
                for item in values[:2]:
                    if not isinstance(item, dict):
                        continue
                    phrase = _clean(item.get("excerpt"), MAX_SCOPE_CONTEXT)
                    if phrase and len(phrase) <= 92:
                        candidates.append((phrase, "published_ted_scope_original_language"))
                    else:
                        # A long paragraph is not itself a search query. Use
                        # only contiguous published source tokens; no synonyms.
                        tokens = WORD.findall(phrase)
                        windows = []
                        for width in (2, 3):
                            for start in range(max(0, len(tokens) - width + 1)):
                                piece = tokens[start:start+width]
                                if (
                                    all(len(token) >= 3 for token in piece)
                                    and sum(token.casefold() not in GENERIC_WORDS
                                            for token in piece) >= 2
                                ):
                                    windows.append(" ".join(piece))
                        if windows:
                            candidates.append((
                                sorted(windows, key=lambda s: (-len(s), s))[0],
                                "contiguous_published_ted_scope_phrase",
                            ))
                        # Do not strip case or rewrite original language.
            # Also keep the unshortened lot title if it is short.
        label = _clean(brief.get("source_published_workflow_clue"), 130)
        if label:
            part = label.split(" – ")[-1].strip(" ()")
            if part:
                candidates.append((part, "published_ted_notice_title"))
    seen = set()
    result = []
    for phrase, basis in candidates:
        candidate = _keyword(phrase)
        if not 5 <= len(candidate) <= 90 or candidate in seen:
            continue
        seen.add(candidate)
        result.append({
            "keyword": candidate,
            "basis": basis,
            "market_search_evidence_verified": False,
            "search_volume": None,
            "search_trend_direction": "not_measured",
            "competition": "not_measured",
            "observed_as_actual_search_query": False,
            "keyword_status": PROOF_LABEL,
        })
        if len(result) == MAX_KEYWORDS_PER_IDEA:
            break
    return result


def _market(brief: dict[str, Any]) -> dict[str, str]:
    if brief.get("kind") == "recurring_public_consumer_issue_to_investigate":
        return {"country_code": "US", "basis": "cfpb_us_consumer_complaints"}
    code = brief.get("buyer_country_code", "")
    return {
        "country_code": COUNTRY_BY_ISO3.get(code, ""),
        "source_buyer_country_iso3": (
            code if isinstance(code, str)
            and re.fullmatch(r"[A-Z]{3}", code) else ""
        ),
        "source_market_geo_mapping": (
            "known_iso3_to_iso2" if code in COUNTRY_BY_ISO3
            else "unknown_source_country_not_guessed"
        ),
        "basis": "source_published_ted_buyer_country_not_market_size",
    }


def _validate_trend_evidence(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("Keyword evidence must be an object")
    try:
        size = len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode())
    except (ValueError, TypeError) as exc:
        raise ValueError("Keyword evidence must be finite JSON") from exc
    if size > MAX_EVIDENCE_BYTES:
        raise ValueError("Keyword evidence exceeds 64 KiB")
    if set(value) - {"keyword", "market", "points", "source_note"}:
        raise ValueError("Unknown keyword evidence fields")
    keyword = _keyword(value.get("keyword"))
    market = value.get("market")
    if (not keyword or not isinstance(market, str)
            or re.fullmatch(r"[A-Z]{2}", market) is None):
        raise ValueError("Keyword evidence requires exact term and ISO market")
    # Reuse the existing no-network validated local watch evidence parser.
    from mcp_trendpulse.trend_watch import parse_evidence
    validated = parse_evidence(
        json.dumps({"keyword": value["keyword"], "market": market,
                    "points": value.get("points")}, ensure_ascii=False).encode(),
        keyword=value["keyword"], market=market,
    )
    return {"keyword": keyword, "market": market, "validated_points": validated}


def _attach_keyword_interest(
    ideas: list[dict[str, Any]], evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    status = {
        "status": "not_supplied" if evidence is None else "exact_keyword_and_market_not_in_idea_map",
        "source": "operator_supplied_normalized_google_trends_style_series",
        "independently_verified_provider_provenance": False,
        "absolute_search_volume_verified": False,
        "attached_idea_count": 0,
    }
    if evidence is None:
        return status
    from mcp_trendpulse.trend_watch import WatchRule, evaluate_watch

    for idea in ideas:
        if idea["geography"]["country_code"] != evidence["market"]:
            continue
        for candidate in idea["keyword_hypotheses"]:
            if candidate["keyword"] != evidence["keyword"]:
                continue
            rule = WatchRule(
                "0000000000000000", candidate["keyword"], evidence["market"],
                10.0, 0.0, 4, 7,
            )
            report = evaluate_watch(rule, evidence["validated_points"])
            candidate["search_trend_direction"] = (
                "user_supplied_series_nonpositive_or_below_threshold"
                if report.status == "below_threshold"
                else "user_supplied_series_exceeds_10_percent_threshold"
                if report.status == "triggered"
                else "inconclusive_" + report.status
            )
            candidate["normalized_series_status"] = report.status
            candidate["normalized_series_observation_count"] = len(evidence["validated_points"])
            candidate["normalized_series_latest_date"] = (
                evidence["validated_points"][-1][0].isoformat()
                if evidence["validated_points"] else None
            )
            candidate["growth_percent_in_user_series"] = report.growth_pct
            candidate["series_provenance"] = "operator_supplied_unverified_source"
            candidate["market_search_evidence_verified"] = False
            status["status"] = "attached_unverified_operator_supplied_series"
            status["attached_idea_count"] += 1
    return status


def build_idea_map(
    discovery: dict[str, Any], *, keyword_evidence: Any = None,
) -> dict[str, Any]:
    """Offline hypothesis list, preserving each original observation and caveat."""
    if not isinstance(discovery, dict):
        raise ValueError("Expected completed seedless discovery")
    briefs = discovery.get("workflow_briefs")
    if (not isinstance(briefs, dict)
            or briefs.get("mode") != "source_grounded_workflow_briefs_not_validated_market_demand"
            or not isinstance(briefs.get("briefs"), list)
            or len(briefs["briefs"]) > MAX_IDEAS):
        raise ValueError("Idea map needs bounded completed workflow briefs")
    valid_evidence = _validate_trend_evidence(keyword_evidence)
    output: list[dict[str, Any]] = []
    audit = briefs.get("independent_source_checks")
    followup = {
        r["brief_id"]: r for r in (audit.get("topics", []) if isinstance(audit, dict) else [])
        if isinstance(r, dict) and isinstance(r.get("brief_id"), str)
    }
    for brief in briefs["briefs"]:
        if not isinstance(brief, dict):
            continue
        kind = brief.get("kind")
        if kind not in (
            "published_software_it_procurement_to_investigate",
            "recurring_public_consumer_issue_to_investigate",
        ):
            continue
        raw_evidence = brief.get("evidence")
        if not isinstance(raw_evidence, list) or not raw_evidence:
            continue
        proof = raw_evidence[0]
        if not isinstance(proof, dict):
            continue
        ref = proof.get("reference")
        if kind.startswith("published"):
            if (not isinstance(ref, str) or TED_REF.fullmatch(ref) is None
                    or brief.get("published_lot_date_on_or_after_analysis") is not True):
                continue
        elif ref != CFPB_REF:
            continue
        label = _clean(brief.get("source_published_workflow_clue"), 125)
        ident = brief.get("brief_id")
        if not label or not isinstance(ident, str) or re.fullmatch(r"[0-9a-f]{14}", ident) is None:
            continue
        scope = brief.get("published_scope_context")
        scope_available = isinstance(scope, dict) and scope.get("status") == "observed_scope_excerpts"
        lineage = brief.get("related_notice_context")
        newer_related = bool(
            isinstance(lineage, dict)
            and lineage.get("newer_source_publication_requires_scope_revalidation") is True
        )
        kind_is_ted = kind.startswith("published")
        project_direction = (
            "Prototype a small component of the published implementation workflow; "
            "check for repeated independent buyers and incumbent software first."
            if kind_is_ted else
            "Prototype evidence collection and resolution tracking for this "
            "reported consumer problem; verify who would pay before building."
        )
        buyer = (
            "Published procurement authority (one procedure, not independent market demand)"
            if kind_is_ted else
            "Consumer or complaint-handling organization (hypothetical payer)"
        )
        idea = {
            "id": ident,
            "title": label,
            "kind": "procurement_derived_software_hypothesis" if kind_is_ted
                    else "consumer_problem_derived_software_hypothesis",
            "source_observed_problem": label,
            "product_direction_hypothesis": project_direction,
            "buyer_or_operator_hypothesis": buyer,
            "published_buyer_label": _clean(brief.get("published_buyer_label"), 100),
            "geography": _market(brief),
            "source_reference": ref,
            "original_record_dates": [
                _clean(r.get("date"), 10) for r in raw_evidence[:2]
                if isinstance(r, dict) and isinstance(r.get("date"), str)
            ],
            "sampled_source_records": brief.get("sampled_original_record_count", 0),
            "buyer_legal_identity_verified": False,
            "buyer_willingness_to_pay_verified": False,
            "repeatability_across_independent_buyers_verified": False,
            "repeatable_small_software_product_verified": False,
            "market_growth_verified": False,
            "keyword_search_volume_verified": False,
            "keyword_competition_verified": False,
            "keyword_hypotheses": _observed_keywords(brief),
            "provider_research_context": [{
                "source": "openalex", "source_topic_reference": _clean(
                    r.get("source_topic_reference"), 80
                ),
                "relation": "lexical_only_not_independent_search_demand",
            } for r in brief.get("measured_research_context", [])[:1]
                if isinstance(r, dict)],
            "scope_excerpt_present": scope_available,
            "newer_ted_notice_requires_scope_revalidation": newer_related,
            "current_version_of_scope_verified": False,
            "scope_specificity": (
                "published_procedure_and_unassigned_lot_excerpts"
                if scope_available else
                "notice_title_and_classification_only"
                if kind_is_ted else "source_published_complaint_category"
            ),
            "independent_probe": {
                "status": _clean(followup[ident].get("hunter_screening_status"), 60),
                "same_buyer_verified": False,
            } if ident in followup else None,
            "next_verification": (
                "A newer same-procedure TED publication exists: check the newest"
                " official notice and documents before using the prior scope."
                if newer_related else
                "Check related TED notices, current tender documents, lot scope,"
                " suppliers, and similar buyers; then test a reusable module."
                if kind_is_ted else
                "Interview actual users/operators; measure repeat occurrence "
                "in comparable periods and test an explicit paying customer."
            ),
        }
        output.append(idea)
    interest_status = _attach_keyword_interest(output, valid_evidence)
    if not isinstance(discovery.get("as_of"), str):
        raise ValueError("Discovery analysis date is required")
    return {
        "mode": "source_grounded_project_idea_and_keyword_research_queue",
        "status": "investigation_ideas_not_validated_products" if output else "no_source_backed_ideas_in_sample",
        "as_of": discovery["as_of"],
        "idea_count": len(output), "ideas": output,
        "max_ideas": MAX_IDEAS,
        "source_requests_added": 0,
        "keyword_evidence": interest_status,
        "source_and_market_populations_are_not_comparable": True,
        "research_publication_momentum_is_not_search_trends": True,
        "all_keyword_seeds_are_unverified_search_queries": True,
        "seo_keyword_volumes_and_difficulty_not_measured": True,
        "buyer_demand_and_product_market_fit_not_verified": True,
        "no_paid_apis_or_new_network_requests": True,
        "no_predefined_industry_seed_list": True,
        "limitations": (
            "Bounded observations, non-representative samples and source-published "
            "labels. Source keywords are hypotheses until independently measured "
            "in the target country and language; a keyword's appearance in a "
            "tender or complaint is not a real search query."
        ),
    }


def format_idea_map(report: dict[str, Any]) -> list[str]:
    if report.get("mode") != "source_grounded_project_idea_and_keyword_research_queue":
        raise ValueError("Expected completed opt-in idea map")
    lines = [
        "PROJECT IDEA + KEYWORD INVESTIGATION MAP (opt-in, offline):",
        "  Directions are hypotheses from observed source records, NOT verified reusable products, customers or market growth.",
        "  All keyword candidates are source-derived HYPOTHESES, not observed Google queries, volumes, CPC or difficulty.",
    ]
    for i, idea in enumerate(report["ideas"], 1):
        lines.append(f"  {i}. {idea['title']} [{idea['kind']}]")
        lines.append(f"     Build hypothesis: {idea['product_direction_hypothesis']}")
        lines.append(f"     Buyer hypothesis: {idea['buyer_or_operator_hypothesis']}")
        lines.append(f"     Market of source (NOT where search demand was measured): {idea['geography']['country_code'] or 'unknown'}")
        lines.append(f"     Original evidence: {idea['source_reference']}")
        lines.append(f"     Scope: {idea['scope_specificity']}")
        if not idea["keyword_hypotheses"]:
            lines.append("     No exact source-derived candidate keyword qualified; manual language-specific research required.")
        for candidate in idea["keyword_hypotheses"]:
            lines.append(
                f"     Keyword hypothesis: {candidate['keyword']}"
                f" | {candidate['basis']} | trend: {candidate['search_trend_direction']}"
                " | search volume: UNKNOWN"
            )
        lines.append("     Next: " + idea["next_verification"])
    lines.append(
        "  Validate candidate terms by country, language and time period using Google Trends Explore"
        " and your own Search Console data; do not conflate normalized interest with search volume."
    )
    if report["keyword_evidence"]["status"] != "not_supplied":
        lines.append(
            "  Local keyword series: " + report["keyword_evidence"]["status"]
            + " (operator-supplied; provider provenance NOT independently verified)."
        )
    return lines
