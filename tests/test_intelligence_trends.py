"""Synthetic falsification of opt-in, source-measured OpenAlex research trends.

None of these tests infers market adoption, buyer budgets, or a reliable
general population trend from the latest twenty source samples.
"""
from __future__ import annotations

from datetime import date, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest

from mcp_trendpulse import intelligence_discovery as discovery
from mcp_trendpulse import intelligence_trends as trends
from mcp_trendpulse.intelligence_core import plan_source


def _work(work_number: int, code: str, label: str, day: str) -> dict:
    return {
        "id": f"https://openalex.org/W{work_number}",
        "display_name": f"Research title for {label}",
        "publication_date": day,
        "primary_topic": {
            "id": f"https://openalex.org/{code}",
            "display_name": label,
        },
    }


def _snapshot(rows: list[dict]) -> dict:
    return {
        "source": "openalex",
        "status": "observed",
        "observations": {"record_count": len(rows), "sample": rows},
    }


def _two_topics(day: str) -> dict:
    return _snapshot([
        _work(4414937598, "T11636", "Explainable Artificial Intelligence", day),
        _work(4414937599, "T11636", "Explainable Artificial Intelligence", day),
        _work(4414940001, "T10283", "Numerical Simulation and Analysis", day),
        _work(4414940002, "T10283", "Numerical Simulation and Analysis", day),
    ])


def test_three_mature_periods_are_disjoint_and_avoid_most_recent_14_days():
    as_of = date(2026, 11, 19)
    periods = trends.completed_periods(as_of, 30)
    assert periods == [
        {"from": "2026-08-08", "through": "2026-09-06"},
        {"from": "2026-09-07", "through": "2026-10-06"},
        {"from": "2026-10-07", "through": "2026-11-05"},
    ]
    for left, right in zip(periods, periods[1:]):
        assert date.fromisoformat(left["through"]) + timedelta(days=1) == date.fromisoformat(right["from"])
    assert (as_of - date.fromisoformat(periods[-1]["through"])).days == 14


@pytest.mark.parametrize("days", [0, 1, 6, 91, True, 14.5, "30"])
def test_invalid_trend_window_rejected(days):
    with pytest.raises(ValueError):
        trends.completed_periods(date(2026, 11, 19), days)


def test_auto_topic_detection_never_uses_name_guessing_or_duplicate_works():
    day = date.today().isoformat()
    rows = _two_topics(day)["observations"]["sample"]
    bad = _work(4414941000, "T00000", "Title with wrong ID", day)
    bad["primary_topic"]["id"] = "WRONG-PRIVATE-ID"
    rows.extend([
        rows[0].copy(),
        bad,
        _work(4414941001, "T11111", "One lonely research topic", day),
        _work(4414941002, "T12345", "Too old to count", "2025-01-01"),
    ])
    selected = trends.discovered_topic_ids(
        _snapshot(rows), as_of=date.today(), lookback_days=30,
    )
    assert [x["topic_id"] for x in selected] == ["T10283", "T11636"]
    assert all(x["sample_work_count"] == 2 for x in selected)
    assert "WRONG-PRIVATE-ID" not in repr(selected)


def test_topic_count_plan_is_free_keyless_fixed_origin_and_mature():
    original = plan_source(
        "openalex", discover=True, lookback_days=30, limit=1, env={},
    )
    period = trends.completed_periods(date(2026, 11, 19), 30)[1]
    target = trends._count_plan(original, period, "T11636")
    parts = urlsplit(target.url)
    query = parse_qs(parts.query)
    assert parts.hostname == "api.openalex.org"
    assert parts.path == "/works"
    assert query["per_page"] == ["1"]
    assert query["select"] == ["id"]
    assert query["filter"] == [
        "from_publication_date:2026-09-07,"
        "to_publication_date:2026-10-06,"
        "type:article|review|book|book-chapter,"
        "primary_topic.id:T11636"
    ]
    assert "search" not in query
    assert "from_created_date" not in target.url
    assert "from_updated_date" not in target.url
    assert "api_key=" not in target.url
    assert target.source == "openalex"
    assert target.budget_per_day == original.budget_per_day == 20


@pytest.mark.parametrize("bad", [
    "artificial intelligence", "../T11636", "T123%2F", "T", "T123",
    "T1 OR buyers", "https://evil.example/T11636",
])
def test_unsafe_or_guessed_topic_ids_rejected(bad):
    original = plan_source(
        "openalex", discover=True, lookback_days=30, limit=1, env={},
    )
    period = trends.completed_periods(date(2026, 11, 19), 30)[0]
    with pytest.raises(ValueError):
        trends._count_plan(original, period, bad)


@pytest.mark.parametrize("topic,corpus,direction", [
    ([10, 15, 30], [100000] * 3, "accelerating_research_share"),
    ([10, 11, 18], [100000] * 3, "rising_research_share"),
    ([20, 21, 21], [100000] * 3, "approximately_stable_research_share"),
    ([50, 40, 20], [100000] * 3, "declining_research_share"),
    ([1, 2, 18], [100000] * 3, "newly_observed_research_activity"),
    ([1, 3, 4], [100000] * 3, "insufficient_volume"),
    ([10, 20, 15], [100000] * 3, "inconclusive"),
    ([396, 478, 499], [628356, 711639, 624923],
     "early_rising_research_watchlist"),
    ([100, 94, 78], [100000] * 3, "early_declining_research_watchlist"),
    ([None, 20, 30], [100000] * 3, "unavailable"),
    ([10, 20, 30], [100000, None, 100000], "unavailable"),
    ([10, 20, 30], [100000, 0, 100000], "unavailable"),
    ([10, 200, 30], [100000, 100, 100000], "unavailable"),
])
def test_directional_trend_heuristics_are_transparent_and_bounded(topic, corpus, direction):
    result = trends.classify_publication_momentum(topic, corpus)
    assert result["direction"] == direction
    assert result["market_growth_verified"] is False
    if direction == "unavailable":
        assert result["research_share_measured"] is False
    else:
        assert result["research_share_measured"] is True
        assert len(result["share_per_million"]) == 3
        assert len(result["period_over_period_share_ratios"]) == 2


def test_real_field_xai_research_watchlist_not_false_market_growth():
    measured = trends.classify_publication_momentum(
        [396, 478, 499], [628356, 711639, 624923],
    )
    assert measured["direction"] == "early_rising_research_watchlist"
    assert 26 <= measured["oldest_to_recent_share_change_percent"] <= 28
    assert 17 <= measured["latest_interval_share_change_percent"] <= 21
    assert measured["research_share_measured"] is True
    assert measured["market_growth_verified"] is False


def test_source_paper_examples_are_bounded_public_and_no_fake_product_adoption():
    today = date.today().isoformat()
    source = _two_topics(today)
    topics = trends.discovered_topic_ids(
        source, as_of=date.today(), lookback_days=30,
    )
    assert len(topics) == 2
    assert all(len(t["recent_research_examples"]) == 2 for t in topics)
    assert all(p["reference"].startswith("https://openalex.org/W")
               for topic in topics for p in topic["recent_research_examples"])
    assert all(0 < len(p["title"]) <= 115 for topic in topics
               for p in topic["recent_research_examples"])
    assert all(p["title"].startswith("Research title for")
               for topic in topics for p in topic["recent_research_examples"])


def test_full_trend_measurement_uses_nine_bounded_existing_openalex_requests(monkeypatch):
    day = date.today().isoformat()
    source = _two_topics(day)
    requested = []
    # Corpus for all equal periods is 100k matching works, with count-only
    # page=1 responses. Latest-20 work samples are not the denominator.
    topic_counts = {"T10283": [10, 11, 18], "T11636": [10, 15, 30]}
    def fake_collect(plan, **kwargs):
        assert kwargs["fetch"] is True
        assert kwargs["timeout"] <= 20
        assert plan.source == "openalex"
        qs = parse_qs(urlsplit(plan.url).query)
        filters = qs["filter"][0]
        interval = filters.split("to_publication_date:")[1][:10]
        periods = trends.completed_periods(date.today(), 30)
        index = [p["through"] for p in periods].index(interval)
        found = [k for k in topic_counts if "primary_topic.id:" + k in filters]
        count = topic_counts[found[0]][index] if found else 100000
        requested.append((found[0] if found else "corpus", index))
        return {"source": "openalex", "status": "observed",
                "data": {"meta": {"count": count}, "results": [{"id": "https://openalex.org/W1234"}]}}
    monkeypatch.setattr(trends, "collect", fake_collect)
    out = trends.measure_discovered_research_trends(
        source, as_of=date.today(), lookback_days=30, env={},
    )
    assert out["status"] == "observed"
    assert out["additional_source_requests"] == 9
    assert len(requested) == 9
    assert requested[:3] == [("corpus", 0), ("corpus", 1), ("corpus", 2)]
    assert out["auto_selected_topic_count"] == 2
    assert out["max_additional_source_requests"] == 9
    assert [r["direction"] for r in out["topics"]] == [
        "rising_research_share", "accelerating_research_share"
    ]
    assert [r["topic_counts"] for r in out["topics"]] == [
        [10, 11, 18], [10, 15, 30]
    ]
    assert out["buyer_spending_or_market_growth_verified"] is False
    assert out["other_source_topic_direction_unmeasured"] == ["cfpb", "ted"]
    assert len(out["idea_watchlist"]) == 2
    assert all(x["product_opportunity_verified"] is False
               and x["keyword_search_demand_verified"] is False
               for x in out["idea_watchlist"])
    formatted = "\n".join(trends.format_research_trends(out))
    assert "PRODUCT-IDEA RESEARCH WATCHLIST" in formatted
    assert "Research clue" in formatted
    assert "Source topic assignments changed" in formatted


def test_source_count_contract_failures_never_invent_decline(monkeypatch):
    source = _two_topics(date.today().isoformat())
    def unavailable(plan, **kwargs):
        return {"source": "openalex", "status": "unavailable", "http_status": 429}
    monkeypatch.setattr(trends, "collect", unavailable)
    out = trends.measure_discovered_research_trends(
        source, as_of=date.today(), lookback_days=30, env={},
    )
    assert out["status"] == "unavailable_corpus_denominator"
    assert out["additional_source_requests"] == 3
    assert all(x["direction"] == "unavailable" for x in out["topics"])
    assert all(x["topic_counts"] == [None, None, None] for x in out["topics"])
    assert out["buyer_spending_or_market_growth_verified"] is False


def test_missing_topic_id_does_not_trigger_network(monkeypatch):
    source = _snapshot([
        {"id": "https://openalex.org/W12345", "publication_date": date.today().isoformat(),
         "primary_topic": {"display_name": "Nice but unverified research topic"}}
    ])
    def prohibit(*args, **kwargs):
        raise AssertionError("No guessed topic, no request")
    monkeypatch.setattr(trends, "collect", prohibit)
    out = trends.measure_discovered_research_trends(
        source, as_of=date.today(), lookback_days=30, env={},
    )
    assert out["additional_source_requests"] == 0
    assert out["status"] == "no_repeated_provider_topic_ids"


def test_opt_in_discovery_plan_does_not_call_any_endpoint(monkeypatch):
    def prohibit(*_args, **_kwargs):
        raise AssertionError("Planning can never fetch")
    monkeypatch.setattr(discovery, "collect", prohibit)
    monkeypatch.setattr(trends, "collect", prohibit)
    plan = discovery.discover_current(
        execute=False, ted_date_slices=3, measure_trends=True, env={},
    )
    assert plan["status"] == "planned"
    assert plan["network_performed"] is False
    assert plan["request_count"] == 5
    assert plan["max_requests_with_trend_measurement"] == 14
    assert plan["trend_evidence"]["max_additional_source_requests"] == 9
    assert plan["trend_evidence"]["requires_execute"] is True


def test_full_discovery_opt_in_measures_not_buyers(monkeypatch):
    now = date.today().isoformat()
    original_sources = {
        "openalex": _two_topics(now),
        "cfpb": {"source": "cfpb", "status": "observed",
                 "observations": {"sample": [], "record_count": 0}},
        "ted": {"source": "ted", "status": "observed",
                "observations": {"sample": [], "record_count": 0}},
    }
    monkeypatch.setattr(
        discovery, "collect",
        lambda plan, **kwargs: original_sources[plan.source],
    )
    # The measured counts use the same provider source but are identifiable
    # only through the trusted count-only query and cannot reach buyers.
    def count_response(plan, **_kwargs):
        qs = parse_qs(urlsplit(plan.url).query)
        query = qs["filter"][0]
        idx = [p["through"] for p in trends.completed_periods(
            date.today(), 30
        )].index(query.split("to_publication_date:")[1][:10])
        found = "primary_topic.id:" in query
        return {"source": "openalex", "status": "observed",
                "data": {"meta": {"count": [10, 12, 18][idx] if found else 100000}}}
    monkeypatch.setattr(trends, "collect", count_response)
    result = discovery.discover_current(
        execute=True, limit=20, ted_date_slices=1, measure_trends=True,
        lookback_days=30, env={},
    )
    assert result["queries_budgeted"] == 12
    assert result["trend_evidence"]["status"] == "observed"
    assert result["growth_rate_verified"] is False
    assert result["paid_buyers_verified"] is False
    assert result["trend_evidence"]["buyer_spending_or_market_growth_verified"] is False
    rendered = discovery.format_discovery_report(result)
    assert "MEASURED RESEARCH TREND DIRECTIONS" in rendered
    assert "Topic works per million comparable publications" in rendered
    assert "NOT verified market" in rendered or "NOT verified market, search" in rendered
    assert "MEASURED RESEARCH" not in discovery.format_discovery_report(
        discovery.summarize_discovery(list(original_sources.values()), as_of=now)
    )


def test_default_discover_remains_three_requests_and_no_trend_measurement(monkeypatch):
    source = _two_topics(date.today().isoformat())
    calls = []
    def fake_collect(plan, **_kwargs):
        calls.append(plan.source)
        return source if plan.source == "openalex" else {
            "source": plan.source, "status": "observed",
            "observations": {"sample": [], "record_count": 0}
        }
    monkeypatch.setattr(discovery, "collect", fake_collect)
    out = discovery.discover_current(execute=True, env={})
    assert calls == ["openalex", "cfpb", "ted"]
    assert out["queries_budgeted"] == 3
    assert "trend_evidence" not in out
