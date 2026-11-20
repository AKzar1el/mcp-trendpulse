"""Independent checks from original workflow labels, never static market seeds."""
from __future__ import annotations

from datetime import date

import pytest

from mcp_trendpulse import intelligence_discovery as discovery
from mcp_trendpulse import intelligence_workflow_followup as followup

ASOF = date(2026, 11, 20)


def brief(ident, kind, title):
    return {"brief_id": ident, "kind": kind, "source_published_workflow_clue": title}


def two_briefs():
    return {"briefs": [
        brief("1234567890abcd", "published_software_it_procurement_to_investigate",
              "Battery recycling monitoring software"),
        brief("fedcba98765432", "recurring_public_consumer_issue_to_investigate",
              "Debt collection — Attempts to collect debt not owed"),
    ]}


def test_source_phrase_selection_prefers_problem_then_buyer_and_no_static_seeds():
    selection = followup.select_workflow_followups(two_briefs())
    assert [row["source_derived_phrase"] for row in selection] == [
        "debt collection", "battery recycling",
    ]
    assert [r["origin"] for r in selection] == [
        "observed_cfpb_problem_category", "observed_ted_software_it_notice_title",
    ]
    assert followup.select_workflow_followups({"briefs": []}) == []
    assert followup.select_workflow_followups({"briefs": [
        brief("abcdef12345678", "recurring_public_consumer_issue_to_investigate",
              "AI or IT software")
    ]}) == []


def test_existing_hunter_receives_only_source_phrases_and_preserves_honest_dates(
    monkeypatch,
):
    calls = []
    def fake_hunt(topics, sources, **kwargs):
        calls.append((topics, sources, kwargs))
        return {"topics": [
            {
                "topic": "battery recycling",
                "status": "current_single_source_activity",
                "source_coverage": [
                    {"source": "usaspending", "status": "observed",
                     "records_accepted": 3, "topical_title_matches": 2,
                     "recent_eligible_matches": 0},
                    {"source": "github_issues", "status": "observed",
                     "records_accepted": 5, "topical_title_matches": 1,
                     "recent_eligible_matches": 1},
                ],
                "evidence": [
                    {"source": "github_issues",
                     "title": "Battery recycling tracking failure",
                     "reference": "https://github.com/sample/repository/issues/112",
                     "event_date": "2026-11-18"},
                ],
                "context_examples": [
                    {"source": "usaspending", "title": "Battery recycling record",
                     "reference": "https://www.usaspending.gov/search",
                     "reason": "timestamp_not_comparable_recent_market_event"},
                ],
            },
            {
                "topic": "debt collection",
                "status": "insufficient_topical_observation",
                "source_coverage": [
                    {"source": "github_issues", "status": "observed",
                     "records_accepted": 2, "topical_title_matches": 0,
                     "recent_eligible_matches": 0},
                    {"source": "usaspending", "status": "unavailable",
                     "http_status": 503, "reason": "SECRET_DO_NOT_ECHO"},
                ],
                "evidence": [],
            },
        ]}
    monkeypatch.setattr(followup, "hunt_current", fake_hunt)
    report = followup.investigate_workflow_briefs(
        two_briefs(), as_of=ASOF, lookback_days=30, env={},
    )
    assert calls[0][0] == ["debt collection", "battery recycling"]
    assert calls[0][1] == ["github_issues", "usaspending"]
    assert calls[0][2]["execute"] is True
    assert calls[0][2]["lookback_days"] == 30
    assert report["source_requests_budgeted"] == 4
    assert report["status"] == "partial_independent_source_coverage"
    buyer = report["topics"][1]
    assert buyer["github_issue_examples"][0]["reference"].endswith("/issues/112")
    assert buyer["usaspending_context_only_examples"][0]["record_last_modified_is_not_new_award"]
    assert buyer["same_workflow_or_buyer_independently_verified"] is False
    assert report["topics"][0]["source_coverage"][1]["http_status"] == 503
    assert "SECRET_DO_NOT_ECHO" not in repr(report)
    shown = "\n".join(followup.format_workflow_followup(report))
    assert "NOT exact award" in shown
    assert "NOT market-demand verified" in shown
    assert "SECRET_DO_NOT_ECHO" not in shown


def test_untrusted_urls_are_never_copied_from_public_result(monkeypatch):
    def fake_hunt(*_a, **_kw):
        return {"topics": [{
            "topic": "debt collection",
            "source_coverage": [
                {"source": "github_issues", "status": "observed"},
                {"source": "usaspending", "status": "observed"},
            ],
            "evidence": [{"source": "github_issues", "title": "secret",
                          "reference": "https://evil.example/private?id=SECRET",
                          "event_date": "2026-11-18"}],
            "context_examples": [{"source": "usaspending", "title": "secret",
                                   "reference": "https://evil.example/signal",
                                   "reason": "publication_date_unavailable"}],
        }]}
    monkeypatch.setattr(followup, "hunt_current", fake_hunt)
    source = {"briefs": [two_briefs()["briefs"][1]]}
    out = followup.investigate_workflow_briefs(
        source, as_of=ASOF, lookback_days=30, env={},
    )
    assert out["topics"][0]["github_issue_examples"] == []
    assert out["topics"][0]["usaspending_context_only_examples"] == []
    assert "evil.example" not in repr(out)


def test_empty_input_does_not_call_hunter_or_seed_existing_default_topics(monkeypatch):
    monkeypatch.setattr(followup, "hunt_current",
                        lambda *_a, **_kw: (_ for _ in ()).throw(
                            AssertionError("No source phrases, no requests")))
    report = followup.investigate_workflow_briefs(
        {"briefs": []}, as_of=ASOF, lookback_days=30, env={},
    )
    assert report["status"] == "no_safe_source_derived_phrases"
    assert report["source_requests_budgeted"] == 0
    assert "No fallback seeds" in "\n".join(followup.format_workflow_followup(report))


def test_explicit_opt_in_required_and_plan_only_bounded_without_network(monkeypatch):
    monkeypatch.setattr(discovery, "collect",
                        lambda *_a, **_kw: (_ for _ in ()).throw(
                            AssertionError("Plan-only must not fetch")))
    with pytest.raises(ValueError, match="workflow-cross-check"):
        discovery.discover_current(execute=False, workflow_cross_check=True, env={})
    with pytest.raises(ValueError, match="workflow_cross_check"):
        discovery.discover_current(
            execute=False, workflow_briefs=True,
            workflow_cross_check="yes", env={},
        )
    plan = discovery.discover_current(
        execute=False, workflow_briefs=True,
        workflow_cross_check=True, env={},
    )
    assert plan["request_count"] == 3
    assert plan["max_requests_with_workflow_cross_check"] == 7
    assert plan["workflow_briefs"]["independent_source_checks"][
        "max_additional_source_requests"
    ] == 4
    assert plan["workflow_briefs"]["independent_source_checks"][
        "requires_execute_for_source_derived_phrases"
    ] is True


def test_workflow_cross_check_execute_reuses_existing_bounded_sources(monkeypatch):
    today = date.today().isoformat()
    calls = []
    def fake_collect(plan, **kw):
        calls.append(plan.source)
        if plan.source == "cfpb":
            items = [
                {"public_complaint_id": "101", "product": "Debt collection",
                 "issue": "Attempts to collect debt not owed", "date_received": today},
                {"public_complaint_id": "102", "product": "Debt collection",
                 "issue": "Attempts to collect debt not owed", "date_received": today},
            ]
        else:
            items = []
        return {"source": plan.source, "status": "observed",
                "observations": {"sample": items, "record_count": len(items)}}
    monkeypatch.setattr(discovery, "collect", fake_collect)
    observed = []
    def fake_hunt(topics, sources, **kw):
        observed.append((topics, sources))
        return {"topics": [{
            "topic": topics[0], "status": "insufficient_topical_observation",
            "source_coverage": [{"source": s, "status": "observed"}
                                for s in sources],
            "evidence": [],
        }]}
    monkeypatch.setattr(followup, "hunt_current", fake_hunt)
    report = discovery.discover_current(
        execute=True, workflow_briefs=True,
        workflow_cross_check=True, env={},
    )
    assert calls == ["openalex", "cfpb", "ted"]
    assert observed[0][0] == ["debt collection"]
    assert report["workflow_briefs"]["independent_source_checks"][
        "source_requests_budgeted"
    ] == 2
    assert report["queries_budgeted"] == 5
    assert report["workflow_briefs"]["source_requests_added"] == 0
    assert report["workflow_briefs"]["product_market_fit_verified"] is False
    assert "SOURCE-DERIVED INDEPENDENT CHECK" in discovery.format_discovery_report(report)
