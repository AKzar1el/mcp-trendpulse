"""A software/IT CPV tender must not silently become a greenfield SaaS idea."""
from __future__ import annotations

import pytest

from mcp_trendpulse import intelligence_product_fit as fit
from mcp_trendpulse import intelligence_idea_map as idea_map


def tender(label: str, *, cpv="48000000", scope: str | None = None):
    value = {
        "kind": "published_software_it_procurement_to_investigate",
        "published_primary_cpv": cpv,
        "source_published_workflow_clue": label,
    }
    if scope is not None:
        value["published_scope_context"] = {
            "status": "observed_scope_excerpts",
            "procedure_description": [{"language": "slv", "excerpt": scope}],
        }
    return value


@pytest.mark.parametrize(("title", "cpv", "category"), [
    (
        "Slovenia – Obnova licenčnih pravic in dokup uporabniških licenc",
        "48000000", "license_or_entitlement_purchase",
    ),
    (
        "Lithuania – Elektroninių pranešimų saugyklos (EPS) priežiūros ir palaikymo paslaugos",
        "72267000", "maintenance_or_support_service",
    ),
    (
        "Lithuania – Servers – Grafinė serverinė stotis",
        "48820000", "hardware_or_equipment_purchase",
    ),
    (
        "Poland – Dostawa licencji oprogramowań dla jednostek AGH",
        "48000000", "license_or_entitlement_purchase",
    ),
    (
        "Hungary – UiPath szoftver licenc előfizetés és támogatás",
        "72260000", "license_or_entitlement_purchase",
    ),
    (
        "Estonia – Riigiportaali eesti.ee arendus- ja hooldustööd",
        "72200000", "development_and_support_service",
    ),
    (
        "Germany – Implementation of identity and API gateway",
        "48219100", "custom_development_or_implementation_service",
    ),
    (
        "Switzerland – API-Management-System",
        "48219100", "unclassified_software_it_purchase",
    ),
])
def test_published_title_and_primary_cpv_screen_contract_type_only(
    title, cpv, category,
):
    screen = fit.screen_procurement(tender(title, cpv=cpv))
    assert screen["category"] == category
    assert not screen["repeatable_greenfield_software_demand_verified"]
    assert not screen["new_independent_paying_customers_verified"]
    assert "source_published_primary_cpv" in screen["screen_basis"] or (
        screen["screen_basis"] == "unclassified_source_title_and_primary_cpv"
    )


def test_scope_qualified_screen_and_no_arbitrary_source_key_leak():
    p = tender("Slovenia – Software systems", cpv="48000000", scope=(
        "Predmet javnega naročila je obnova licenčnih pravic "
        "za podporo pisarniškemu poslovanju."
    ))
    p["raw_private_narrative"] = "DO_NOT_LEAK_ACCESS_TOKEN"
    s = fit.screen_procurement(p)
    assert s["category"] == "license_or_entitlement_purchase"
    assert "DO_NOT_LEAK_ACCESS_TOKEN" not in repr(s)
    assert "DO_NOT_LEAK_ACCESS_TOKEN" not in s["next_research"]


def test_product_idea_map_writes_separate_fit_screen_without_product_claim():
    source = {
        "as_of": "2026-11-20",
        "workflow_briefs": {
            "mode": "source_grounded_workflow_briefs_not_validated_market_demand",
            "briefs": [
                {
                    **tender(
                        "Slovenia – Obnova licenčnih pravic in dokup licenc",
                        cpv="48000000",
                    ),
                    "brief_id": "abc123abc123ab",
                    "published_lot_date_on_or_after_analysis": True,
                    "buyer_country_code": "SVN",
                    "evidence": [{
                        "reference": "https://ted.europa.eu/en/notice/-/detail/807273-2026",
                        "date": "2026-11-19",
                    }],
                },
            ],
        },
    }
    report = idea_map.build_idea_map(source)
    assert report["idea_count"] == 1
    assert report["screened_non_greenfield_purchase_lead_count"] == 1
    lead = report["ideas"][0]
    assert lead["procurement_fit_screen"]["category"] == "license_or_entitlement_purchase"
    assert "not proof of a new SaaS" in lead["product_direction_hypothesis"]
    assert not lead["repeatable_small_software_product_verified"]
    assert "Fit screen: license_or_entitlement_purchase" in "\n".join(
        idea_map.format_idea_map(report)
    )


def test_invalid_unclassified_cpv_does_not_infer_custom_saas_opportunity():
    s = fit.screen_procurement(tender("Unrelated procurement title", cpv="broken"))
    assert s["category"] == "unclassified_software_it_purchase"
    assert s["published_primary_cpv"] == ""
    assert not s["repeatable_greenfield_software_demand_verified"]
