"""Falsify opt-in source-backed commercial workflow projection without APIs."""
from __future__ import annotations

from datetime import date

import pytest

from mcp_trendpulse import intelligence_discovery as discovery
from mcp_trendpulse import intelligence_workflows as workflow

DAY = date(2026, 11, 20)


def record(source, ref, title, *, day="2026-11-19", **more):
    return {"source": source, "id": ref.split("/")[-1], "reference": ref,
            "title": title, "date": day, **more}


def tender(title="Battery recycling monitoring software", *,
           cpv="72000000", num="804742-2026", stage="contract_notice_not_award",
           buyer="EU buyer", deadline="2026-12-21", amount="10588350"):
    return record(
        "ted", "https://ted.europa.eu/en/notice/-/detail/" + num, title,
        procurement_stage=stage, main_cpv_code=cpv, buyer_name=buyer,
        buyer_country_code="GRC", latest_lot_deadline_date=deadline,
        estimated_value_as_published=amount, estimated_value_currency="EUR",
    )


def complaint(ident, theme="Credit card — Incorrect purchase statement"):
    return record(
        "cfpb", workflow.CFPB_LANDING,
        theme, id=ident, theme=theme,
        theme_basis="cfpb_public_product_issue_categories",
    )


def research(ident="W2741809807", topic="Battery recycling systems"):
    return record(
        "openalex", "https://openalex.org/" + ident,
        "New study on recyclable materials", theme=topic,
    )


def test_buyers_and_research_phrase_are_attributed_without_demand_promotion():
    data = workflow.build_workflow_briefs(
        [tender(), research()], as_of=DAY,
    )
    assert data["brief_count"] == 1
    assert data["source_requests_added"] == 0
    assert data["no_predefined_industry_seeds"] is True
    brief = data["briefs"][0]
    assert brief["kind"] == "published_software_it_procurement_to_investigate"
    assert brief["published_buyer_label"] == "EU buyer"
    assert brief["published_primary_cpv"] == "72000000"
    assert brief["published_lot_date_on_or_after_analysis"] is True
    assert brief["published_procedure_estimate"]["amount"] == "10588350"
    assert brief["published_procedure_estimate"]["procedure_estimate_not_awarded_or_software_only_spend"]
    assert brief["research_context"][0]["shared_source_phrase"] == "battery recycling"
    assert brief["research_context"][0]["research_is_not_buyer_demand"] is True
    assert brief["buyer_legal_identity_verified"] is False
    assert brief["market_growth_verified"] is False
    assert "Source records in bounded sample" in "\n".join(
        workflow.format_workflow_briefs(data)
    )


def test_no_semantic_or_generic_one_word_links_between_unrelated_records():
    data = workflow.build_workflow_briefs(
        [tender("Cloud infrastructure software"), research(topic="Criminal Law and Policy")],
        as_of=DAY,
    )
    assert len(data["briefs"]) == 1
    assert data["briefs"][0]["research_context"] == []
    workflow.attach_measured_research(data, {"idea_watchlist": [
        {"topic_id": "T13376", "label": "Criminal Law and Policy",
         "research_direction": "early_rising_research_watchlist"},
    ]})
    assert data["briefs"][0]["measured_research_context"] == []
    assert data["product_market_fit_verified"] is False


def test_strict_source_id_and_phrase_gate_for_measured_watchlist():
    data = workflow.build_workflow_briefs([tender()], as_of=DAY)
    workflow.attach_measured_research(data, {"idea_watchlist": [
        {"topic_id": "T123", "label": "Battery recycling methods"},
        {"topic_id": "T12345", "label": "Battery recycling materials",
         "research_direction": "early_rising_research_watchlist"},
        {"topic_id": "T98765", "label": "Cloud costs"},
    ]})
    links = data["briefs"][0]["measured_research_context"]
    assert len(links) == 1
    assert links[0]["source_topic_reference"] == "https://openalex.org/T12345"
    assert links[0]["connection"] == "lexical_only_not_verified_same_workflow"


def test_repeated_complaints_are_not_distinct_buyers_and_not_individual_record_links():
    theme = "Credit card — Incorrect purchase statement"
    data = workflow.build_workflow_briefs(
        [complaint("101", theme), complaint("102", theme), complaint("102", theme)],
        as_of=DAY,
    )
    assert data["brief_count"] == 1
    brief = data["briefs"][0]
    assert brief["sampled_original_record_count"] == 2
    assert brief["buyer_not_identified_from_complaints"] is True
    assert brief["distinct_complaint_ids_not_distinct_customers"] is True
    assert brief["evidence"][0]["reference_specificity"] == (
        "source_landing_not_individual_complaint"
    )
    assert brief["independent_paying_customers_verified"] is False


def test_awards_non_it_or_invalid_links_not_promoted_to_vendor_briefs():
    data = workflow.build_workflow_briefs([
        tender(stage="contract_award_notice_not_open_tender"),
        tender(cpv="45212000", num="804743-2026"),
        tender(num="bad", title="BAD LINK"),
        tender(num="804744-2026", deadline="2026-10-01"),
    ], as_of=DAY)
    assert data["brief_count"] == 0
    assert data["sampled_software_it_contract_notices"] == 1
    assert data["sampled_software_it_notices_not_forward_qualified"] == 1
    old = data["past_or_incomplete_tender_context"][0]
    assert old["reason"] == "published_lot_date_before_analysis"
    assert old["published_last_lot_date"] == "2026-10-01"
    assert old["not_an_upcoming_procurement_lead"] is True
    assert "Historical/incomplete TED context" in "\n".join(
        workflow.format_workflow_briefs(data)
    )
    assert "BAD LINK" not in repr(data)


def test_capped_results_no_fabricated_solutions_or_provider_secrets():
    inputs = [
        tender("Cloud billing software", num=f"{804740+i}-2026",
               buyer=f"Public buyer {i}")
        for i in range(15)
    ]
    inputs += [complaint(str(i), f"Consumer product {i // 2} — Incorrect charges")
               for i in range(8)]
    inputs += [research("W2741809807", "Unrelated topic")]
    inputs[0]["private_narrative"] = "SECRET_PRIVATE_NARRATIVE"
    result = workflow.build_workflow_briefs(inputs, as_of=DAY)
    assert result["brief_count"] <= workflow.MAX_BRIEFS
    assert result["sampled_software_it_contract_notices"] == 15
    assert len([r for r in result["briefs"] if r["kind"].startswith("published")]) <= 4
    assert "SECRET_PRIVATE_NARRATIVE" not in repr(result)
    assert "buyer_willingness_to_pay_verified" in repr(result)


def test_zero_and_malformed_inputs_are_safe_and_no_fake_empty_market():
    zero = workflow.build_workflow_briefs([research()], as_of=DAY)
    assert zero["status"] == "no_workflow_investigation_from_sample"
    assert "NOT a market-wide negative" in "\n".join(
        workflow.format_workflow_briefs(zero)
    )
    with pytest.raises(ValueError):
        workflow.build_workflow_briefs([{}] * 61, as_of=DAY)
    with pytest.raises(ValueError):
        workflow.build_workflow_briefs([123], as_of=DAY)
    with pytest.raises(ValueError):
        workflow.build_workflow_briefs([], as_of="2026-11-20")


def test_optional_discovery_integration_no_extra_calls(monkeypatch):
    today = date.today().isoformat()
    calls = []
    def fake_collect(plan, **kwargs):
        calls.append(plan.source)
        rows = []
        if plan.source == "cfpb":
            rows = [
                {"public_complaint_id": "101", "product": "Credit card",
                 "issue": "Incorrect statement", "date_received": today},
                {"public_complaint_id": "102", "product": "Credit card",
                 "issue": "Incorrect statement", "date_received": today},
            ]
        elif plan.source == "ted":
            rows = [{
                "publication-number": "804742-2026", "publication-date": today,
                "notice-title": {"eng": ["Financial software operations"]},
                "buyer-name": {"eng": ["Public authority"]},
                "notice-type": "cn-standard",
                "main-classification-proc": "72000000",
                "deadline-receipt-tender-date-lot": "2026-12-21",
            }]
        return {"source": plan.source, "status": "observed",
                "observations": {"sample": rows, "record_count": len(rows)}}
    monkeypatch.setattr(discovery, "collect", fake_collect)
    plain = discovery.discover_current(execute=True, env={})
    assert "workflow_briefs" not in plain
    calls.clear()
    planned = discovery.discover_current(execute=False, workflow_briefs=True, env={})
    assert planned["workflow_briefs"]["source_requests_added"] == 0
    assert calls == []
    enriched = discovery.discover_current(
        execute=True, workflow_briefs=True, env={},
    )
    assert calls == ["openalex", "cfpb", "ted"]
    assert enriched["queries_budgeted"] == 3
    assert enriched["workflow_briefs"]["brief_count"] == 2
    assert enriched["workflow_briefs"]["source_requests_added"] == 0
    assert "SOURCE-ATTRIBUTED COMMERCIAL WORKFLOW" in discovery.format_discovery_report(enriched)
    assert enriched["growth_rate_verified"] is False


def test_workflow_briefs_flag_is_explicit_opt_in_and_type_safe():
    with pytest.raises(ValueError, match="workflow_briefs"):
        discovery.discover_current(execute=False, workflow_briefs="yes")
    report = discovery.summarize_discovery([
        {"source": "openalex", "status": "observed",
         "observations": {"sample": [], "record_count": 0}},
    ], as_of=DAY.isoformat())
    assert "workflow_briefs" not in report


def test_cli_workflow_briefs_option_executes_network_free_plan():
    import json

    from click.testing import CliRunner
    from mcp_trendpulse.cli import cli

    run = CliRunner().invoke(cli, [
        "intelligence", "discover", "--workflow-briefs", "--format", "json",
    ])
    assert run.exit_code == 0, run.output
    plan = json.loads(run.output)
    assert plan["status"] == "planned"
    assert plan["network_performed"] is False
    assert plan["request_count"] == 3
    assert plan["workflow_briefs"]["source_requests_added"] == 0


def test_live_field_shape_keeps_two_future_date_tenders_not_past_vendor_license():
    rows = [
        tender("Greece IT employment portal", num="804742-2026",
               deadline="2026-12-21"),
        tender("Germany Finanzsoftware", num="781080-2026",
               deadline="2026-12-14"),
        tender("IBM Lizenzen fuer EntireX und webMethods", num="754533-2026",
               deadline="2026-11-12"),
    ]
    result = workflow.build_workflow_briefs(rows, as_of=DAY)
    assert result["brief_count"] == 2
    assert result["sampled_software_it_contract_notices"] == 3
    assert result["sampled_software_it_notices_with_future_or_today_published_lot_dates"] == 2
    assert result["sampled_software_it_notices_not_forward_qualified"] == 1
    assert all(row["published_lot_date_on_or_after_analysis"]
               for row in result["briefs"])
    assert "IBM Lizenzen" not in repr(result["briefs"])
    assert result["past_or_incomplete_tender_context"][0]["reason"] == (
        "published_lot_date_before_analysis"
    )
