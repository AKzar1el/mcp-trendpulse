"""Regression: inconclusive research growth can still receive source follow-up.

The 2026-11-20 source output had normalized XAI share 639->657->808
per million, but an early-rising heuristic missed its 2.8% first step.
Corroboration must not be gated solely on the promoted growth watchlist.
"""
from __future__ import annotations

from datetime import date

import pytest

from mcp_trendpulse import intelligence_auto_hunt as hunt
from mcp_trendpulse import intelligence_corroboration as issue
from mcp_trendpulse import intelligence_discovery as discover
from mcp_trendpulse import intelligence_trends as trends
from mcp_trendpulse.intelligence_followup import (
    format_source_followups, select_source_followups,
)


CORPUS = [637_000, 715_000, 622_500]


def source_topic(
    code: str, label: str, counts: list[int],
    corpus: list[int] | None = None,
) -> dict:
    normalized = corpus or CORPUS
    classified = trends.classify_publication_momentum(counts, normalized)
    return {
        "topic_id": code, "label": label,
        "topic_counts": counts, "corpus_counts": normalized,
        "recent_research_examples": [],
        **classified,
    }


def actual_nov20_topics() -> list[dict]:
    return [
        source_topic(
            "T12026", "Explainable Artificial Intelligence (XAI)",
            [407, 470, 503],
        ),
        source_topic(
            "T10339", "Advanced Numerical Methods in Computational Mathematics",
            [185, 189, 191],
        ),
    ]


def test_real_field_inconclusive_source_counts_still_eligible_for_exploration():
    topics = actual_nov20_topics()
    assert [r["direction"] for r in topics] == ["inconclusive", "inconclusive"]
    assert topics[0]["two_interval_direction_consistent"] is True
    assert topics[1]["two_interval_direction_consistent"] is False
    evidence = {"topics": topics, "idea_watchlist": []}
    out = select_source_followups(evidence)
    assert out["status"] == "source_measured_topics_selected"
    assert out["max_auto_topics"] == 2
    assert out["product_idea_watchlist_unchanged"] is True
    assert evidence["idea_watchlist"] == []
    assert [r["topic_id"] for r in out["topics"]] == ["T12026"]
    selected = out["topics"][0]
    assert selected["research_direction"] == "inconclusive"
    assert selected["included_in_product_idea_watchlist"] is False
    assert selected["selection_basis"] == (
        "exploratory_monotonic_below_trend_threshold"
    )
    assert selected["commercial_demand_verified"] is False
    report = "\n".join(format_source_followups(out))
    assert "exploratory only" in report
    assert "does not upgrade" in report


def test_volatility_and_rebound_preserved_as_source_audit_not_auto_probes():
    oral = source_topic(
        "T13590", "Oral History Memory Narrative Analysis",
        [78, 69, 1078],
    )
    glioma = source_topic(
        "T10129", "Glioma Diagnosis and Treatment",
        [589, 477, 1161],
    )
    assert oral["direction"] == "abrupt_publication_spike_needs_validation"
    assert glioma["direction"] == "volatile_rebound_needs_validation"
    out = select_source_followups({
        "idea_watchlist": [],
        "topics": [oral, glioma, actual_nov20_topics()[1]],
    })
    assert out["status"] == "no_eligible_measured_followup_topics"
    assert out["topics"] == []


def test_incomplete_denominators_invalid_counts_and_near_flat_are_not_followups():
    candidates = [
        source_topic("T12345", "Climate Energy Management", [8, 7, 13]),
        source_topic("T12346", "Computer Vision Security", [10, 10, 11],
                     [1000, 1000, 1000]),
        source_topic("T12347", "Data Integrity Research", [2, 10, 21]),
        source_topic("T12348", "Funded Research Partnerships", [11, 12, 15]),
    ]
    # The last example is a real monotonic increase; its research direction
    # may qualify for the original watchlist depending on source baseline.
    candidates[3]["research_share_measured"] = False
    candidates[0]["topic_counts"] = [8, None, 13]
    candidates[1]["trajectory_integrity_flag"] = "publisher_batch_unverified"
    out = select_source_followups({
        "idea_watchlist": [], "topics": candidates,
    })
    assert out["topics"] == []


def test_rising_research_watchlist_keeps_first_priority_and_no_duplicate_topics():
    measured = actual_nov20_topics()
    out = select_source_followups({
        "topics": measured,
        "idea_watchlist": [
            {
                "topic_id": "T12121",
                "label": "Intelligent Privacy Operations",
                "research_direction": "early_rising_research_watchlist",
            },
            {
                "topic_id": "T12026",
                "label": "Explainable Artificial Intelligence",
                "research_direction": "early_rising_research_watchlist",
            },
        ],
    })
    assert [r["topic_id"] for r in out["topics"]] == ["T12121", "T12026"]
    assert all(r["included_in_product_idea_watchlist"] for r in out["topics"])
    assert all(r["selection_basis"] == "existing_rising_research_watchlist"
               for r in out["topics"])


def test_selected_topic_provenance_is_kept_per_github_query(monkeypatch):
    originals = select_source_followups({
        "idea_watchlist": [{
            "topic_id": "T12121", "label": "Intelligent Privacy Operations",
            "research_direction": "early_rising_research_watchlist",
        }],
        "topics": actual_nov20_topics(),
    })["topics"]
    queries = []
    def fake_collect(plan, **kwargs):
        queries.append(plan.url)
        return {"source": "github_issues", "status": "observed",
                "data": {"total_count": len(queries),
                         "incomplete_results": False}}
    monkeypatch.setattr(issue, "collect", fake_collect)
    out = issue.corroborate_research_issue_mentions(
        originals, as_of=date(2026, 11, 20),
        lookback_days=30, env={},
    )
    assert out["source_requests"] == 4
    assert len(queries) == 4
    assert out["topics"][0]["selection_basis"] == (
        "existing_rising_research_watchlist"
    )
    assert out["topics"][0]["research_direction"] == (
        "early_rising_research_watchlist"
    )
    assert out["topics"][1]["selection_basis"] == (
        "exploratory_monotonic_below_trend_threshold"
    )
    assert out["topics"][1]["research_direction"] == "inconclusive"
    assert out["topics"][1]["included_in_product_idea_watchlist"] is False
    assert out["not_customer_pain_verified"] is True
    lines = "\n".join(issue.format_issue_corroboration(out))
    assert "exploratory_monotonic_below_trend_threshold" in lines


def test_selected_topic_label_and_classification_survive_existing_hunter(
    monkeypatch,
):
    selected = select_source_followups({
        "idea_watchlist": [], "topics": actual_nov20_topics(),
    })["topics"]
    called = []
    def fake_hunter(topics, sources, **kwargs):
        called.append((topics, sources, kwargs))
        return {"topics": [{
            "topic": topics[0].lower(),
            "source_coverage": [
                {"source": "cordis", "status": "observed",
                 "records_accepted": 0, "topical_title_matches": 0,
                 "recent_eligible_matches": 0},
                {"source": "usaspending", "status": "unavailable",
                 "records_accepted": 0, "topical_title_matches": 0,
                 "recent_eligible_matches": 0},
            ],
            "evidence": [],
            "status": "insufficient_topical_observation",
        }]}
    monkeypatch.setattr(hunt, "hunt_current", fake_hunter)
    out = hunt.investigate_discovered_topics(
        selected, as_of=date(2026, 11, 20),
        lookback_days=30, env={},
    )
    assert called[0][0] == ["Explainable Artificial Intelligence"]
    assert called[0][1] == ["cordis", "usaspending"]
    assert out["source_request_budget"] == 2
    assert out["status"] == "partially_available_source_context"
    assert out["topics"][0]["research_direction"] == "inconclusive"
    assert out["topics"][0]["selection_basis"] == (
        "exploratory_monotonic_below_trend_threshold"
    )
    assert out["topics"][0]["source_coverage"][1]["status"] == "unavailable"
    assert "NOT a validated product trend" in "\n".join(
        hunt.format_discovered_source_context(out)
    )


def test_both_opt_in_paths_receive_only_measured_exploratory_topic(
    monkeypatch,
):
    measured = actual_nov20_topics()
    seen = {"github": None, "other": None}
    def fake_collect(plan, **kwargs):
        return {"source": plan.source, "status": "observed",
                "observations": {"record_count": 0, "sample": []}}
    monkeypatch.setattr(discover, "collect", fake_collect)
    def fake_measure(*_args, **_kwargs):
        return {
            "status": "observed",
            "idea_watchlist": [],
            "topics": measured,
            "additional_source_requests": 9,
            "max_additional_source_requests": 9,
            "buyer_spending_or_market_growth_verified": False,
        }
    monkeypatch.setattr(trends, "measure_discovered_research_trends", fake_measure)
    def fake_issues(topics, **_kwargs):
        seen["github"] = topics
        return {"source_requests": 2, "topics": []}
    def fake_other(topics, **_kwargs):
        seen["other"] = topics
        return {"source_request_budget": 2, "topics": []}
    monkeypatch.setattr(issue, "corroborate_research_issue_mentions", fake_issues)
    monkeypatch.setattr(hunt, "investigate_discovered_topics", fake_other)
    result = discover.discover_current(
        execute=True, measure_trends=True, corroborate_issues=True,
        cross_source_hunt=True, limit=20, lookback_days=30, env={},
    )
    assert result["queries_budgeted"] == 3 + 9 + 2 + 2
    evidence = result["trend_evidence"]
    assert evidence["idea_watchlist"] == []
    assert evidence["additional_source_requests"] == 13
    assert evidence["max_additional_source_requests"] == 17
    assert len(seen["github"]) == len(seen["other"]) == 1
    assert seen["github"][0]["topic_id"] == "T12026"
    assert seen["other"][0]["selection_basis"] == (
        "exploratory_monotonic_below_trend_threshold"
    )
    assert evidence["source_followup_selection"]["topics"][0][
        "included_in_product_idea_watchlist"
    ] is False
    assert result["growth_rate_verified"] is False
    assert result["paid_buyers_verified"] is False


def test_default_and_unmeasured_or_volatility_flows_never_force_followups(
    monkeypatch,
):
    # The helper is invoked only after explicit flag opt-in.
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Corroboration is opt-in only")
    monkeypatch.setattr(issue, "corroborate_research_issue_mentions", forbidden)
    monkeypatch.setattr(hunt, "investigate_discovered_topics", forbidden)
    monkeypatch.setattr(discover, "collect", lambda plan, **_k: {
        "source": plan.source, "status": "observed",
        "observations": {"record_count": 0, "sample": []},
    })
    out = discover.discover_current(execute=True, env={})
    assert out["queries_budgeted"] == 3
    assert "trend_evidence" not in out


@pytest.mark.parametrize("invalid", [None, [], "bad", {"topics": None}])
def test_invalid_followup_inputs_fail_closed(invalid):
    with pytest.raises(ValueError):
        select_source_followups(invalid)
