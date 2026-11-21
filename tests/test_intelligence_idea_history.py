"""Durable, source-safe observation history is not a market-growth claim."""
from __future__ import annotations

from datetime import date, timedelta

from click.testing import CliRunner

from mcp_trendpulse import intelligence_idea_history as history
from mcp_trendpulse.cli import cli

DAY = date.today()
TED = "https://ted.europa.eu/en/notice/-/detail/807273-2026"
CFPB = history.CFPB_REF


def idea(reference: str, label: str, *, kind="procurement_derived_software_hypothesis"):
    return {
        "id": "aabbccddeeff00",
        "kind": kind,
        "source_reference": reference,
        "source_observed_problem": label,
        "procurement_fit_screen": {
            "category": "license_or_entitlement_purchase",
        } if kind.startswith("procurement") else None,
    }


def bundle(day, ideas):
    return {
        "mode": "source_grounded_project_idea_and_keyword_research_queue",
        "as_of": day.isoformat(),
        "ideas": ideas,
    }


def test_unique_source_day_idempotence_and_visible_prior_tender(tmp_path):
    db = tmp_path / "ledger.sqlite3"
    one = idea(TED, "Slovenia – Obnova licenčnih pravic")
    complain = idea(CFPB, "Debt collection — Attempts to collect debt not owed",
                    kind="consumer_problem_derived_software_hypothesis")
    first = history.record_idea_history(bundle(DAY, [one, complain]), path=db)
    assert first["current_source_items_recorded"] == 2
    assert first["new_distinct_day_sightings"] == 2
    assert first["previously_observed_but_not_in_current_sample"] == []
    assert all(item["distinct_days_seen_in_this_pipeline"] == 1
               for item in first["current_source_history"])
    same = history.record_idea_history(bundle(DAY, [one, complain]), path=db)
    assert same["new_distinct_day_sightings"] == 0
    assert same["existing_same_day_sightings"] == 2
    assert "already recorded on this analysis day: 2" in "\n".join(
        history.format_idea_history(same)
    )
    assert all(item["distinct_days_seen_in_this_pipeline"] == 1
               for item in same["current_source_history"])
    second = history.record_idea_history(
        bundle(DAY + timedelta(days=1), [complain]), path=db,
    )
    assert second["new_distinct_day_sightings"] == 1
    assert second["current_source_history"][0]["distinct_days_seen_in_this_pipeline"] == 2
    old = second["previously_observed_but_not_in_current_sample"]
    assert len(old) == 1 and old[0]["source_reference"] == TED
    assert old[0]["last_screen_category"] == "license_or_entitlement_purchase"
    assert old[0]["current_source_status"] == (
        "source_status_not_provided_not_revalidated"
    )
    assert old[0]["prior_deadline_or_scope_may_have_changed"]
    assert "source status not supplied; current presence UNKNOWN" in "\n".join(
        history.format_idea_history(second)
    )


def test_unavailable_ted_does_not_make_historical_notice_disappear(tmp_path):
    db = tmp_path / "ledger.sqlite3"
    old = idea(TED, "Slovenia – Obnova licenčnih pravic")
    observed_cfpb = idea(
        CFPB, "Checking or savings account — Managing an account",
        kind="consumer_problem_derived_software_hypothesis",
    )
    history.record_idea_history(bundle(DAY, [old]), path=db)
    refreshed = history.record_idea_history(
        bundle(DAY, [observed_cfpb]), path=db,
        source_status={"ted": "unavailable", "cfpb": "observed"},
    )
    past = refreshed["prior_history_not_selected_in_current_idea_map"]
    assert len(past) == 1
    assert past[0]["source_reference"] == TED
    assert past[0]["current_source_status"] == "source_unavailable_not_revalidated"
    assert past[0]["current_source_collection_status"] == "unavailable"
    assert "current presence UNKNOWN" in "\n".join(
        history.format_idea_history(refreshed)
    )
    assert refreshed["new_distinct_day_sightings"] == 1
    assert refreshed["source_revalidation_performed"] is False


def test_observed_source_capped_map_selection_does_not_prove_absence(tmp_path):
    db = tmp_path / "ledger.sqlite3"
    old = idea(
        CFPB, "Credit reporting — Incorrect information on your report",
        kind="consumer_problem_derived_software_hypothesis",
    )
    current = idea(
        CFPB, "Checking or savings account — Managing an account",
        kind="consumer_problem_derived_software_hypothesis",
    )
    history.record_idea_history(bundle(DAY, [old]), path=db)
    result = history.record_idea_history(
        bundle(DAY, [current]), path=db,
        source_status={"cfpb": "observed", "ted": "unavailable"},
    )
    prior = result["prior_history_not_selected_in_current_idea_map"]
    assert prior[0]["current_source_status"] == (
        "not_selected_in_current_capped_idea_map"
    )
    assert "NOT proof of source absence" in "\n".join(
        history.format_idea_history(result)
    )


def test_same_ted_reference_survives_reworded_title_without_new_identity(tmp_path):
    db = tmp_path / "ledger.sqlite3"
    original = idea(TED, "Licenčne pravice")
    changed = idea(TED, "Software licensing - revised wording")
    history.record_idea_history(bundle(DAY, [original]), path=db)
    second = history.record_idea_history(
        bundle(DAY + timedelta(days=1), [changed]), path=db,
    )
    assert second["current_source_items_recorded"] == 1
    assert second["current_source_history"][0]["first_seen"] == DAY.isoformat()
    assert second["current_source_history"][0]["source_label"] == changed[
        "source_observed_problem"
    ]
    assert second["current_source_history"][0]["distinct_days_seen_in_this_pipeline"] == 2
    assert second["previously_observed_but_not_in_current_sample"] == []


def test_shared_cfpb_landing_does_not_merge_different_categories(tmp_path):
    a = idea(CFPB, "Debt collection — Attempts to collect debt not owed",
             kind="consumer_problem_derived_software_hypothesis")
    b = idea(CFPB, "Credit reporting — Incorrect information on your report",
             kind="consumer_problem_derived_software_hypothesis")
    result = history.record_idea_history(
        bundle(DAY, [a, b]), path=tmp_path / "opportunities.sqlite3",
    )
    assert result["current_source_items_recorded"] == 2
    assert result["individual_cfpb_complaint_records_saved"] is False


def test_invalid_proofs_private_urls_and_large_labels_are_not_recorded(tmp_path):
    bad = idea("https://example.invalid/token=DO_NOT_LEAK",
               "Private SECRET")
    huge = idea(TED, "very long title " * 300)
    wrong = idea(CFPB, "Private complaint", kind="unknown")
    result = history.record_idea_history(
        bundle(DAY, [bad, huge, wrong]),
        path=tmp_path / "ledger.sqlite3",
    )
    assert result["current_source_items_recorded"] == 0
    assert "DO_NOT_LEAK" not in repr(result)
    assert "Private SECRET" not in repr(result)


def test_retention_removes_unseen_expired_day_not_reactivate_tender(tmp_path):
    db = tmp_path / "ledger.sqlite3"
    first = idea(TED, "Old tender")
    later = idea("https://ted.europa.eu/en/notice/-/detail/807274-2026",
                 "New tender")
    history.record_idea_history(
        bundle(DAY - timedelta(days=100), [first]), path=db,
    )
    result = history.record_idea_history(bundle(DAY, [later]), path=db)
    assert result["current_source_items_recorded"] == 1
    assert result["previously_observed_but_not_in_current_sample"] == []


def test_opt_in_flags_must_require_execute_and_idea_map():
    runner = CliRunner()
    denied = runner.invoke(cli, [
        "intelligence", "discover", "--workflow-briefs",
        "--idea-map", "--record-idea-history",
    ])
    assert denied.exit_code != 0
    denied_no_ideas = runner.invoke(cli, [
        "intelligence", "discover", "--record-idea-history",
    ])
    assert denied_no_ideas.exit_code != 0
