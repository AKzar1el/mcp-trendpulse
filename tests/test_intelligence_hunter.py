"""Falsification tests for current, keyless, evidence-attributed trend hunting.

All organizations, dates, titles, and workflows are fabricated test fixtures,
NOT real company demand or a predictive training dataset.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest

from mcp_trendpulse import intelligence_hunter as hunter
from mcp_trendpulse.intelligence_core import IntelligenceError, plan_source

ASOF = "2026-11-19"


def observed(source, entries):
    return {
        "source": source, "status": "observed",
        "observations": {"record_count": len(entries), "sample": entries},
    }


def issue(text="Battery recycling workflow failure", *, day="2026-11-17",
          issue_id=189):
    return {
        "id": issue_id, "title": text, "created_at": f"{day}T12:30:00Z",
        "html_url": f"https://github.com/example/energy/issues/{issue_id}",
    }


def article(text="Battery recycling study", day="2026-11-18", work="W2741809807"):
    return {
        "id": "https://openalex.org/" + work, "display_name": text,
        "publication_date": day,
    }


def batch(topic="battery recycling", *snapshots):
    return {"topic": topic, "snapshots": list(snapshots)}


def report(*batches, days=30):
    return hunter.summarize_current_hunt(list(batches), as_of=ASOF, lookback_days=days)


def test_cross_source_dated_activity_ranked_without_inventing_growth():
    r = report(batch(
        "battery recycling",
        observed("github_issues", [issue()]),
        observed("openalex", [article()]),
    ))
    row = r["topics"][0]
    assert row["status"] == "current_cross_source_activity"
    assert row["investigation_priority"] == 3
    assert row["recent_dated_records_in_sample"] == 2
    assert row["recent_7_day_records_in_sample"] == 2
    assert row["distinct_recent_source_classes"] == 2
    assert row["latest_supported_event_date"] == "2026-11-18"
    assert row["trend_growth_direction"] == "unknown_without_comparable_baseline"
    assert row["buying_intent_confirmed"] is False
    assert row["success_probability"] is None
    assert r["longitudinal_history_required_for_current_triage"] is False
    assert r["buyer_outcomes_verified"] == 0
    assert r["paid_apis_used"] is False
    assert r["active_multi_source_topics"] == 1
    assert len(row["evidence"]) == 2


def test_single_source_dated_mention_is_not_cross_source_research():
    r = report(batch("battery recycling", observed("github_issues", [issue()])))
    row = r["topics"][0]
    assert row["status"] == "current_single_source_activity"
    assert row["investigation_priority"] == 2
    assert row["recent_independent_provider_types"] == 1


def test_undated_research_grants_are_context_not_live_growth():
    r = report(batch("battery recycling", observed("cordis", [
        {"id": "GRANT00001", "title": "Battery recycling innovation"},
    ])))
    row = r["topics"][0]
    assert row["status"] == "context_only_not_recent_activity"
    assert row["topical_context_records"] == 1
    assert row["recent_dated_records_in_sample"] == 0


def test_modified_award_record_is_not_fresh_award_purchase():
    r = report(batch("battery recycling", observed("usaspending", [{
        "Award ID": "GRANT00001", "Awarding Agency": "Government Buyer",
        "Recipient Name": "Supplier", "Award Amount": 10000,
        "Last Modified Date": "2026-11-19",
        "Description": "Battery recycling operating contract",
    }])))
    x = r["topics"][0]
    assert x["status"] == "context_only_not_recent_activity"
    assert x["recent_dated_records_in_sample"] == 0
    assert x["buying_intent_confirmed"] is False


def test_date_boundary_and_future_proof_cannot_inflate_activity():
    r = report(batch("battery recycling",
                     observed("github_issues", [issue(day="2026-09-14")]),
                     observed("openalex", [
                         article(day="2026-11-20"),
                         article("Battery recycling technology", "2026-11-01", "W2741809808"),
                     ])))
    x = r["topics"][0]
    assert x["recent_dated_records_in_sample"] == 1
    assert x["latest_supported_event_date"] == "2026-11-01"
    assert x["status"] == "current_single_source_activity"


def test_unrelated_topic_and_one_shared_token_are_rejected():
    r = report(batch("battery recycling", observed("github_issues", [
        issue("Battery storage trial"), issue("Recycling waste stream", issue_id=190),
    ])))
    x = r["topics"][0]
    assert x["status"] == "insufficient_topical_observation"
    assert x["recent_dated_records_in_sample"] == 0


def test_provider_failure_retains_successful_sources_but_is_degraded():
    r = report(batch("battery recycling",
                     {"source": "openalex", "status": "unavailable"},
                     observed("github_issues", [issue()])))
    x = r["topics"][0]
    assert x["status"] == "current_single_source_activity"
    assert x["provider_coverage_degraded"] is True
    assert any(row["source"] == "openalex" and row["source_health"] == "not_verified"
               for row in x["source_coverage"])


def test_unsupported_or_unavailable_sources_dont_claim_no_demand():
    x = report(batch("battery recycling", {
        "source": "openalex", "status": "unavailable",
    }))["topics"][0]
    assert x["status"] == "no_usable_provider_coverage"
    assert x["investigation_priority"] == 0


def test_rank_by_distinct_recent_sources_not_arbitrary_seed_order():
    batches = [
        batch("cloud cost management", observed("github_issues", [issue(
            "Cloud cost management problem", issue_id=199)])),
        batch("battery recycling", observed("github_issues", [issue()]),
              observed("openalex", [article()])),
    ]
    x = report(*batches)["topics"]
    assert [row["topic"] for row in x] == ["battery recycling", "cloud cost management"]


def test_bounded_related_phrases_need_two_independent_classes():
    b = batch("battery recycling",
              observed("github_issues", [issue(
                  "Battery recycling material recovery system")]),
              observed("openalex", [article(
                  "Battery recycling material recovery findings")]))
    suggestions = report(b)["discovered_related_phrases"]
    assert any(x["phrase"] == "material recovery" and
               x["distinct_source_classes"] == 2 for x in suggestions)
    assert not any(x["phrase"] == "battery recycling" for x in suggestions)


def test_seed_rotation_is_deterministic_and_not_a_validated_trend():
    today = date(2026, 11, 19)
    a = hunter._topics(None, today)
    b = hunter._topics(None, today)
    assert a == b
    assert len(a) == 3
    assert len(set(a)) == 3
    assert len(hunter.SEED_TOPICS) == 18


@pytest.mark.parametrize("bad", [None, False, 0, 6, 91, "30", -1])
def test_strict_lookback_limits_in_source_planner(bad):
    with pytest.raises(IntelligenceError):
        plan_source("openalex", keyword="battery", env={}, lookback_days=bad if bad is not None else 0)


def test_hunt_lookback_uses_only_free_recent_source_filters():
    cutoff = (date.today() - timedelta(days=29)).isoformat()
    oa = plan_source("openalex", keyword="battery", env={}, lookback_days=29)
    q = parse_qs(urlsplit(oa.url).query)
    assert q["filter"] == [f"from_publication_date:{cutoff}"]
    assert q["sort"] == ["publication_date:desc"]
    assert "from_updated_date" not in oa.url
    assert "from_created_date" not in oa.url
    assert "api_key=" not in oa.url
    gh = plan_source("github_issues", keyword="battery", env={}, lookback_days=29)
    query = parse_qs(urlsplit(gh.url).query)
    assert f"created:>={cutoff}" in query["q"][0]
    assert query["sort"] == ["created"]
    complaint = plan_source("cfpb", keyword="credit card", env={}, lookback_days=29)
    assert parse_qs(urlsplit(complaint.url).query)["date_received_min"] == [cutoff]


def test_default_plan_only_hunter_makes_no_network_or_secret_access(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Planning must not call collect")
    monkeypatch.setattr(hunter, "collect", forbidden)
    response = hunter.hunt_current(
        ["battery recycling"], ["openalex", "github_issues"],
        as_of=ASOF, env={}, execute=False)
    assert response["network_performed"] is False
    assert response["status"] == "planned"
    assert response["request_count"] == 2
    assert all(call["status"] == "planned" for call in response["topics"][0]["calls"])
    assert "Authorization" not in json.dumps(response)


def test_missing_local_companies_house_key_abstains_without_secrets(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No configured key means no network")
    monkeypatch.setattr(hunter, "collect", forbidden)
    r = hunter.hunt_current(
        ["battery recycling"], ["companies_house"],
        as_of=ASOF, execute=True, env={},
    )
    x = r["topics"][0]
    assert x["status"] == "no_usable_provider_coverage"
    assert x["source_coverage"][0]["source"] == "companies_house"
    assert r["provider_credentials_disclosed"] is False


def test_live_hunter_integrates_collector_outputs_without_network_in_test(monkeypatch):
    def fixture(plan, **_):
        if plan.source == "github_issues":
            sample = [issue()]
        else:
            sample = [article()]
        return observed(plan.source, sample)
    monkeypatch.setattr(hunter, "collect", fixture)
    r = hunter.hunt_current(
        ["battery recycling"], ["github_issues", "openalex"],
        as_of=ASOF, execute=True, env={})
    assert r["topics"][0]["status"] == "current_cross_source_activity"
    assert r["network_performed"] is True
    assert r["provider_credentials_disclosed"] is False
    assert r["source_request_budget"] == 2


@pytest.mark.parametrize("bad", [
    ["battery recycling", "battery recycling"],
    ["bad?topic"], ["credit \" OR *"], [" x "],
    [None], list(hunter.SEED_TOPICS[:5]),
])
def test_invalid_or_duplicate_topics_fail_closed(bad):
    with pytest.raises(ValueError):
        hunter.hunt_current(topics=bad, env={}, execute=False)


@pytest.mark.parametrize("bad", [
    ["epo"], ["rsshub_local"], ["openalex", "openalex"],
    ["github_issues", "openalex", "cordis", "usaspending", "cfpb", "gleif"],
])
def test_invalid_sources_or_overwide_hunt_fail_closed(bad):
    with pytest.raises(ValueError):
        hunter.hunt_current(["battery recycling"], bad, env={}, execute=False)


def test_optional_minimal_history_is_secure_and_idempotent(tmp_path):
    r = report(batch("battery recycling",
                     observed("github_issues", [issue()]),
                     observed("openalex", [article()])))
    r["requested_source_ids"] = ["github_issues", "openalex"]
    store = tmp_path / "hunter_history.sqlite"
    first = hunter.record_hunt_history(r, store)
    again = hunter.record_hunt_history(r, store)
    assert first["topics_saved"] == 1
    assert again["topics_saved"] == 1
    assert first["no_raw_records_or_keys_saved"] is True
    with sqlite3.connect(store) as connection:
        rows = connection.execute(
            "SELECT as_of, topic_hash, query_hash, recent_sample_records, "
            "recent_source_classes FROM hunter_snapshots"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == ASOF
    assert rows[0][3:] == (2, 2)
    assert len(rows[0][1]) == 64
    assert len(rows[0][2]) == 64
    assert "battery recycling" not in store.read_bytes().decode("latin1")
    assert "https://openalex.org" not in store.read_bytes().decode("latin1")


def test_history_rejects_planned_or_fake_reports(tmp_path):
    with pytest.raises(ValueError):
        hunter.record_hunt_history({"status": "planned"}, tmp_path / "x.db")


def test_hunter_input_snapshot_boundary_errors_visible():
    with pytest.raises(ValueError):
        report(batch("battery recycling", {"source": "nonsense", "status": "observed"}))
