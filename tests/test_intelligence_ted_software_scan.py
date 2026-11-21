"""TED software CPV follow-up must be separate from sector-neutral source sample."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from click.testing import CliRunner

from mcp_trendpulse import intelligence_discovery as discovery
from mcp_trendpulse import intelligence_ted_software_scan as focused
from mcp_trendpulse.cli import cli
from mcp_trendpulse.intelligence_core import DailyBudgetExceeded

DAY = date.today()
NOW = DAY.isoformat()
NEXT = (DAY + timedelta(days=30)).isoformat()


def ted(id="804742-2026", cpv="72000000", *, when=NOW):
    return {
        "publication-number": id, "publication-date": when,
        "notice-type": "cn-standard",
        "notice-title": {"eng": ["Government software integration system"]},
        "buyer-name": {"eng": ["Example public buyer"]},
        "buyer-country": "GRC",
        "main-classification-proc": cpv,
        "deadline-receipt-tender-date-lot": NEXT,
    }


def snapshot(source, rows):
    return {"source": source, "status": "observed",
            "observations": {"record_count": len(rows), "sample": rows}}


def test_filtered_source_query_capped_and_exact_cpv_expression():
    query = focused.software_scan_query(DAY, 30)
    assert "(PC=48* OR PC=72*)" in query
    assert query.startswith("PD = (")
    assert "notice-type IN (cn-standard cn-social cn-desg)" in query
    assert query.endswith("SORT BY publication-date DESC")
    assert f"{DAY:%Y%m%d}" in query
    assert len(query) <= 140
    with pytest.raises(ValueError):
        focused.software_scan_query(DAY, 91)


def test_focused_software_tenders_are_not_conflated_with_base_sector_sample(monkeypatch):
    captured = []
    def fake(plan, **kwargs):
        captured.append((plan, kwargs))
        return snapshot("ted", [
            ted("804742-2026", cpv="72000000"),
            ted("804743-2026", cpv="48000000"),
            ted("804744-2026", cpv="33140000"),  # secondary matching CPV excluded
        ])
    monkeypatch.setattr(focused, "collect", fake)
    result = focused.scan_software_procurements(
        as_of=DAY, lookback_days=30, env={},
    )
    assert len(captured) == 1 and captured[0][0].source == "ted"
    assert captured[0][0].body["limit"] == 12
    assert result["sampled_records"] == 3
    assert result["qualified_primary_software_briefs"] == 2
    assert result["sampled_primary_it_records"] == 2
    assert result["source_requests_budgeted"] == 1
    assert result["source_query_requests_publication_date_desc"] is True
    assert result["source_ordering_verified_by_observation"] is True
    assert result["sample_date_order"] == "sample_descending_or_same_day"
    assert result["earliest_sampled_publication"] == NOW
    assert all(x["observation_sampling_basis"].startswith("cpv_filtered_")
               for x in result["briefs"])
    main = discovery.summarize_discovery([
        snapshot("ted", [ted("900001-2026", cpv="33140000")]),
    ], as_of=NOW, workflow_briefs=True)
    original = main["ted_sampling_audit"]["main_cpv_48_or_72_observed"]
    count = focused.merge_focused_briefs(main["workflow_briefs"], result)
    assert count == 2 and main["workflow_briefs"]["brief_count"] == 2
    assert original == 0
    assert main["ted_sampling_audit"]["main_cpv_48_or_72_observed"] == 0
    assert "FOCUSED TED SOFTWARE" in "\\n".join(focused.format_software_scan(result))


def test_focused_unsorted_provider_rows_report_warning_without_false_recency(monkeypatch):
    early = (DAY - timedelta(days=20)).isoformat()
    late = (DAY - timedelta(days=1)).isoformat()
    def provider(*_a, **_kw):
        return snapshot("ted", [
            ted("804742-2026", when=early),
            ted("804743-2026", when=late),
        ])
    monkeypatch.setattr(focused, "collect", provider)
    result = focused.scan_software_procurements(
        as_of=DAY, lookback_days=30, env={},
    )
    assert result["sample_date_order"] == "sample_unordered_or_dated_rows_missing"
    assert result["source_ordering_verified_by_observation"] is False
    assert "recency guarantee" in "\n".join(focused.format_software_scan(result))


def test_focused_api_unavailable_keeps_buyer_claims_unknown(monkeypatch):
    monkeypatch.setattr(focused, "collect", lambda *a, **kw: {
        "source": "ted", "status": "unavailable", "http_status": 429,
        "response": "DO_NOT_LEAK_ACCESS_TOKEN",
    })
    result = focused.scan_software_procurements(as_of=DAY, env={})
    assert result["status"] == "unavailable"
    assert result["http_status"] == 429
    assert result["briefs"] == []
    assert "DO_NOT_LEAK_ACCESS_TOKEN" not in repr(result)
    assert result["recurring_market_growth_verified"] is False


def test_exhausted_ted_quota_is_unavailable_not_no_eligible_notices(monkeypatch):
    def exhausted(*_a, **_kw):
        raise DailyBudgetExceeded("ted", "2026-11-20", 20, 20)

    monkeypatch.setattr(focused, "collect", exhausted)
    result = focused.scan_software_procurements(as_of=DAY, env={})
    assert result["status"] == "unavailable"
    assert result["source_requests_performed"] == 0
    assert result["source_failure_reason"] == "local_daily_budget_exhausted"
    assert result["qualified_primary_software_briefs"] == 0
    assert not result["briefs"]
    text = "\n".join(focused.format_software_scan(result))
    assert "eligibility is UNKNOWN, not zero opportunities" in text
    assert "quota 20/20 exhausted" in text
    assert "No eligible primary-CPV software notices" not in text


def test_focused_observed_empty_page_is_different_from_unavailable(monkeypatch):
    monkeypatch.setattr(focused, "collect", lambda *_a, **_kw: snapshot("ted", []))
    result = focused.scan_software_procurements(as_of=DAY, env={})
    text = "\n".join(focused.format_software_scan(result))
    assert result["status"] == "source_observed_without_qualified_primary_it_briefs"
    assert "No eligible primary-CPV software notices" in text
    assert "eligibility is UNKNOWN" not in text


def test_plan_only_is_offline_and_adds_single_source_request(monkeypatch):
    monkeypatch.setattr(discovery, "collect", lambda *a, **kw: (
        (_ for _ in ()).throw(AssertionError("Network not allowed in plan mode"))
    ))
    p = discovery.discover_current(
        workflow_briefs=True, ted_software_scan=True,
        ted_scope_details=True, ted_related_notices=True,
        idea_map=True, execute=False, env={},
    )
    assert p["network_performed"] is False
    assert p["request_count"] == 3
    assert p["max_requests_with_ted_software_scan"] == 4
    assert p["max_requests_with_ted_related_notices"] == 8
    with pytest.raises(ValueError, match="ted-software-scan"):
        discovery.discover_current(ted_software_scan=True, execute=False, env={})


def test_no_it_in_base_but_focus_enriches_briefs_and_ideas(monkeypatch):
    calls = []
    def baseline(plan, **_kw):
        calls.append(("base", plan.source))
        return snapshot(plan.source, [ted("804744-2026", cpv="33140000")]
                        if plan.source == "ted" else [])
    def targeted(plan, **_kw):
        calls.append(("focused", plan.source))
        return snapshot("ted", [ted("804742-2026")])
    monkeypatch.setattr(discovery, "collect", baseline)
    monkeypatch.setattr(focused, "collect", targeted)
    result = discovery.discover_current(
        execute=True, lookback_days=30, env={},
        workflow_briefs=True, ted_software_scan=True, idea_map=True,
    )
    assert calls == [
        ("base", "openalex"), ("base", "cfpb"),
        ("base", "ted"), ("focused", "ted"),
    ]
    assert result["queries_budgeted"] == 4
    assert result["ted_sampling_audit"]["main_cpv_48_or_72_observed"] == 0
    assert result["targeted_software_scan"]["qualified_primary_software_briefs"] == 1
    assert result["workflow_briefs"]["targeted_ted_software_briefs_added"] == 1
    assert result["idea_map"]["idea_count"] == 1
    assert result["idea_map"]["ideas"][0]["market_growth_verified"] is False
    assert "FOCUSED TED SOFTWARE/IT" in discovery.format_discovery_report(result)


def test_cli_exposes_source_focus_only_when_requested():
    cli_runner = CliRunner()
    x = cli_runner.invoke(cli, ["intelligence", "discover",
                                "--workflow-briefs", "--ted-software-scan"])
    assert x.exit_code == 0, x.output
    assert '"max_requests_with_ted_software_scan": 4' in x.output
    invalid = cli_runner.invoke(cli, ["intelligence", "discover",
                                      "--ted-software-scan"])
    assert invalid.exit_code != 0
