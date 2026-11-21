"""Conservative, source-lexical procurement fitness screen for product ideas.

A published software/IT-category tender is NOT automatically a new SaaS
product opportunity. These explicitly limited language clues label the
PURCHASE/WORKFLOW type for human review; they do not establish competitors,
buying willingness, unmet needs or the success of an eventual business.
No network, translations, LLM guesses, new industry seeds or paid services.
"""
from __future__ import annotations

import re
from typing import Any

# Only screen native source-published notice titles or source-projected scope.
# Unicode casefold preserves Lithuanian, Slovenian, Polish and other languages.
# A missed term is "unclassified", NEVER a validated greenfield opportunity.
_LICENSE = re.compile(
    r"\blicen[csč]\w*|\blicen[sz]\w*|\bsubscription\w*|"
    r"\bprenumerat\w*|\bsubskr\w*|\brenewal\w*|\brenew\w*|"
    r"\bobnov[aeio]\w*|\bprzedłużen\w*",
    re.UNICODE,
)
_MAINTAIN = re.compile(
    r"\bmaintenance\b|\bwartung\w*|\bpriežiūr\w*|"
    r"\bpalaikym\w*|\bhooldu\w*|\bprieziur\w*|"
    r"\bservis\w*|\bmaintien\w*",
    re.UNICODE,
)
_DEVELOP = re.compile(
    r"\bdevelop\w*|\bentwickl\w*|\barendus\w*|"
    r"\brozw[óo]j\w*|\brazvoj\w*|\bprogramav\w*|\bįgyvendin\w*|"
    r"\bimplementation\b|\bimplementac\w*",
    re.UNICODE,
)
_HARDWARE = re.compile(
    r"\bserverinė\s+stotis\b|\bservers?\s+equipment\b|"
    r"\bserver\s+station\b|\bhardware\s+equipment\b",
    re.UNICODE,
)
MAX_SOURCE_SNIPPETS = 5

# Not an opportunity score: labels are tentative contract-type screens.
_NEXT = {
    "hardware_or_equipment_purchase": (
        "This appears to procure hardware or equipment. Seek an independently "
        "observed recurring SOFTWARE problem before proposing a new product."
    ),
    "license_or_entitlement_purchase": (
        "This appears to procure or renew software entitlements. Validate an "
        "independent license-management or compliance problem with buyers; "
        "the license purchase itself is not proof of a new SaaS opportunity."
    ),
    "maintenance_or_support_service": (
        "This appears to buy maintenance/support of a system. Check ownership, "
        "existing vendor obligations and recurring pain before proposing "
        "a reusable automation or standalone product."
    ),
    "development_and_support_service": (
        "This appears to combine development and support. Validate a repeatable "
        "subworkflow across separate buyers; do not mistake a custom contract "
        "for SaaS product-market fit."
    ),
    "custom_development_or_implementation_service": (
        "This appears to buy implementation or custom development. Investigate "
        "reusable components and independent customer demand before building SaaS."
    ),
    "unclassified_software_it_purchase": (
        "Published IT CPV alone does not identify new-product demand. Read "
        "original specifications and check the incumbent and buyer workflow."
    ),
}


def screen_procurement(brief: dict[str, Any]) -> dict[str, Any]:
    """Deterministic, minimally inferential contract-type triage with provenance."""
    if not isinstance(brief, dict):
        raise ValueError("Expected source-validated procurement brief")
    cpv = brief.get("published_primary_cpv")
    if not isinstance(cpv, str) or re.fullmatch(r"[0-9]{8}", cpv) is None:
        cpv = ""
    source_title = brief.get("source_published_workflow_clue")
    chunks = [source_title[:180]] if isinstance(source_title, str) else []
    scope = brief.get("published_scope_context")
    if isinstance(scope, dict) and scope.get("status") == "observed_scope_excerpts":
        for key in (
            "lot_title_excerpts_without_lot_identity",
            "procedure_description",
            "lot_description_excerpts_without_lot_identity",
        ):
            entries = scope.get(key)
            if not isinstance(entries, list):
                continue
            for item in entries[:2]:
                excerpt = item.get("excerpt") if isinstance(item, dict) else None
                if isinstance(excerpt, str):
                    chunks.append(excerpt[:280])
                if len(chunks) >= MAX_SOURCE_SNIPPETS:
                    break
            if len(chunks) >= MAX_SOURCE_SNIPPETS:
                break
    text = " ".join(chunks).casefold()
    matches = {
        "hardware": cpv in {"48820000"} or bool(_HARDWARE.search(text)),
        "license": bool(_LICENSE.search(text)),
        "maintenance": bool(_MAINTAIN.search(text)),
        "development": bool(_DEVELOP.search(text)),
    }
    if matches["hardware"]:
        category = "hardware_or_equipment_purchase"
    elif matches["license"]:
        category = "license_or_entitlement_purchase"
    elif matches["development"] and matches["maintenance"]:
        category = "development_and_support_service"
    elif matches["maintenance"] or cpv == "72267000":
        category = "maintenance_or_support_service"
    elif matches["development"]:
        category = "custom_development_or_implementation_service"
    else:
        category = "unclassified_software_it_purchase"
    identifiers = [
        k for k in ("hardware", "license", "maintenance", "development")
        if matches[k]
    ]
    if cpv in {"48820000", "72267000"}:
        identifiers.append("source_primary_cpv_" + cpv)
    return {
        "type": "source_lexical_contract_type_screen_not_product_validation",
        "category": category,
        "screen_basis": (
            "source_published_primary_cpv_and_original_language_text"
            if identifiers else "unclassified_source_title_and_primary_cpv"
        ),
        "matched_lexical_categories": identifiers,
        "published_primary_cpv": cpv,
        "classification_is_tentative": True,
        "actual_bid_scope_or_award_verified": False,
        "repeatable_greenfield_software_demand_verified": False,
        "new_independent_paying_customers_verified": False,
        "commercial_problem_validation_required": True,
        "next_research": _NEXT[category],
    }
