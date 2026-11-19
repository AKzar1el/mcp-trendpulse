"""Deterministic falsification tests for the opt-in top-20 topic landscape.

The grouped pages cover only the top 20 topic IDs per mature period.
Missing topics are never called zero, declining, or non-existent.
"""
from __future__ import annotations

from datetime import date
from urllib.parse import parse_qs, urlsplit

import pytest

from mcp_trendpulse import intelligence_broad_scan as broad
from mcp_trendpulse import intelligence_discovery as discovery
from mcp_trendpulse import intelligence_trends as trends
from mcp_trendpulse.intelligence_core import (
    IntelligenceError, _bounded_openalex_topic_groups,
    _is_openalex_topic_group_plan, plan_source,
)
from mcp_trendpulse.intelligence_evidence import (
    UnexpectedSourceShape, evidence_projection,
)


def _group_response(counts: dict[str, tuple[str, int]], total: int = 100000):
    return {
        "source": "openalex", "status": "observed",
        "data": {
            "meta": {"count": total},
            "group_by": [
                {
                    "key": "https://openalex.org/" + code,
                    "key_display_name": label,
                    "count": count,
                } for code, (label, count) in counts.items()
            ],
        },
    }


def _source():
    day = date.today().isoformat()
    return {
        "source": "openalex", "status": "observed",
        "observations": {"record_count": 2, "sample": [
            {
                "id": f"https://openalex.org/W{4500000001 + i}",
                "display_name": "A synthetic source-backed paper",
                "publication_date": day,
                "primary_topic": {
                    "id": "https://openalex.org/T11333",
                    "display_name": "Example Repeated Research Topic",
                },
            } for i in range(2)
        ]},
    }


def test_openalex_grouped_evidence_projection_allows_no_results_array():
    payload = {
        "meta": {"count": 100000},
        "group_by": [{"key": "https://openalex.org/T12345",
                      "key_display_name": "Research topic", "count": 100}],
    }
    projected = evidence_projection("openalex", payload)
    assert projected["sample"] == []
    assert projected["record_count"] == 0
    with pytest.raises(UnexpectedSourceShape):
        evidence_projection("openalex", {"group_by": payload["group_by"]})
    with pytest.raises(UnexpectedSourceShape):
        evidence_projection("openalex", {"meta": {"count": 1}})


def test_group_plan_fixed_free_origin_and_identical_source_population():
    template = plan_source("openalex", discover=True, limit=1,
                           lookback_days=30, env={})
    period = trends.completed_periods(date(2026, 11, 19), 30)[1]
    plan = broad._group_plan(template, period)
    q = parse_qs(urlsplit(plan.url).query)
    assert plan.source == "openalex"
    assert plan.budget_per_day == template.budget_per_day == 20
    assert plan.url.startswith("https://api.openalex.org/works?")
    assert q["group_by"] == ["primary_topic.id"]
    assert q["per_page"] == ["100"]
    assert _is_openalex_topic_group_plan(plan) is True
    assert q["filter"] == [
        "from_publication_date:2026-09-07,"
        "to_publication_date:2026-10-06,"
        "type:article|review|book|book-chapter"
    ]
    assert "search" not in q
    assert "api_key" not in q
    assert "from_updated_date" not in plan.url
    assert "from_created_date" not in plan.url


def test_invalid_provider_group_shapes_never_create_trend():
    assert broad._read_group_counts({"status": "unavailable"}) is None
    assert broad._read_group_counts(_group_response({
        "T11111": ("Topic A", 100001)
    })) is None
    assert broad._read_group_counts(_group_response({
        "T11111": ("Topic A", True)
    })) is None
    assert broad._read_group_counts(_group_response({
        "T11111": ("Topic A", -1)
    })) is None
    assert broad._read_group_counts(_group_response({
        "UNTRUSTED": ("Private fake topic", 100)
    })) is None
    too_many = _group_response({
        f"T{i+10000}": (f"Topic {i}", 10 + i) for i in range(101)
    })
    assert broad._read_group_counts(too_many) is None
    assert broad._read_group_counts(_group_response({
        "T11111": ("Topic A", 100)
    }))["topic_groups"]["T11111"]["count"] == 100


def test_broad_scan_measures_shared_top100_not_missing_groups_as_zero(monkeypatch):
    counts = [
        {
            "T11111": ("Rising Mixed-Field Research", 100),
            "T22222": ("Stable Engineering Research", 200),
        },
        {
            "T11111": ("Rising Mixed-Field Research", 125),
            "T22222": ("Stable Engineering Research", 200),
        },
        {
            "T11111": ("Rising Mixed-Field Research", 170),
            "T22222": ("Stable Engineering Research", 201),
            "T33333": ("Newly appearing only in top-twenty list", 500),
        },
    ]
    calls = []
    periods = trends.completed_periods(date.today(), 30)
    def fake_collect(plan, **kwargs):
        assert kwargs["fetch"] and kwargs["timeout"] == 20
        assert plan.source == "openalex"
        q = parse_qs(urlsplit(plan.url).query)
        assert q["group_by"] == ["primary_topic.id"]
        idx = [x["through"] for x in periods].index(
            q["filter"][0].split("to_publication_date:")[1][:10]
        )
        calls.append(idx)
        return _group_response(counts[idx])
    monkeypatch.setattr(broad, "collect", fake_collect)
    result = broad.scan_openalex_topic_landscape(
        as_of=date.today(), lookback_days=30, env={},
        probe_recent_missing=False,
    )
    assert calls == [0, 1, 2]
    assert result["status"] == "observed_bounded_top100_overlap"
    assert result["source_requests"] == 3
    assert result["max_source_requests"] == 9
    assert result["topic_groups_observed_per_period"] == [2, 2, 3]
    assert result["compared_topic_ids_present_in_all_three_pages"] == 2
    assert result["not_comparable_groups_due_to_ranking_truncation"] == 1
    assert result["recent_top100_missing_older_rankings"] == 1
    assert result["history_probe_candidate_count"] == 0
    assert result["buyer_or_market_growth_verified"] is False
    assert result["not_a_complete_niche_scan"] is True
    signals = result["rising_or_accelerating_watchlist"]
    assert len(signals) == 1
    assert signals[0]["topic_id"] == "T11111"
    assert signals[0]["label"] == "Rising Mixed-Field Research"
    assert signals[0]["topic_counts"] == [100, 125, 170]
    assert signals[0]["source_topic_reference"] == "https://openalex.org/T11111"
    rendered = "\n".join(broad.format_broad_topic_scan(result))
    assert "UNKNOWN, not zero or decline" in rendered
    assert "T11111" in rendered
    assert "T33333" not in rendered
    assert "NOT verified" in rendered


def test_failed_source_window_never_counts_unknown_as_decline(monkeypatch):
    called = 0
    def fake_collect(*_args, **_kwargs):
        nonlocal called
        called += 1
        return ({"source": "openalex", "status": "unavailable",
                 "http_status": 429} if called == 2 else
                _group_response({"T11111": ("Research", 50)}))
    monkeypatch.setattr(broad, "collect", fake_collect)
    result = broad.scan_openalex_topic_landscape(
        as_of=date.today(), lookback_days=30, env={},
    )
    assert called == 3
    assert result["source_requests"] == 3
    assert result["status"] == "unavailable_or_partial_source_pages"
    assert result["rising_or_accelerating_watchlist"] == []
    assert result["topic_groups_observed_per_period"] == [1, None, 1]
    assert "no broad topic direction inferred" in "\n".join(
        broad.format_broad_topic_scan(result)
    )


def test_grouped_response_100_projections_survive_without_raw_metadata():
    original = {
        "meta": {"count": 100000, "private": "DROP_ME"},
        "results": [{"arbitrary": "DROP_ME"}],
        "raw_personal": "DROP_ME",
        "group_by": [
            {"key": f"https://openalex.org/T{i+10000}",
             "key_display_name": f"Topic {i}",
             "count": i + 50, "untrusted": "DROP_ME"}
            for i in range(100)
        ],
    }
    reduced = _bounded_openalex_topic_groups(original)
    assert reduced["meta"] == {"count": 100000}
    assert len(reduced["group_by"]) == 100
    assert reduced["group_by"][99]["key"] == "https://openalex.org/T10099"
    assert reduced["group_by"][99]["key_display_name"] == "Topic 99"
    assert "DROP_ME" not in repr(reduced)
    assert broad._read_group_counts({
        "source": "openalex", "status": "observed", "data": reduced,
    })["groups_received"] == 100
    with pytest.raises(IntelligenceError):
        _bounded_openalex_topic_groups({
            **original,
            "group_by": original["group_by"] + [original["group_by"][0]],
        })


def test_ranking_gap_is_measured_with_three_actual_source_counts(monkeypatch):
    """An absent ranked topic is not 'new' until three source counts exist."""
    periods = trends.completed_periods(date.today(), 30)
    groups = [
        {"T11111": ("Established Stable Work", 200)},
        {"T11111": ("Established Stable Work", 201)},
        {"T11111": ("Established Stable Work", 202),
         "T22222": ("Emergent User Problem Research", 50)},
    ]
    called = []
    def fake_collect(plan, **kwargs):
        assert plan.source == "openalex" and kwargs["fetch"]
        assert plan.budget_per_day == 20
        query = parse_qs(urlsplit(plan.url).query)
        period = [p["through"] for p in periods].index(
            query["filter"][0].split("to_publication_date:")[1][:10]
        )
        if query.get("group_by"):
            assert query["per_page"] == ["100"]
            called.append(("groups", period))
            return _group_response(groups[period])
        assert query["per_page"] == ["1"]
        assert "primary_topic.id:T22222" in query["filter"][0]
        called.append(("count", period))
        return {"source": "openalex", "status": "observed",
                "data": {"meta": {"count": [0, 1, 50][period]}}}
    monkeypatch.setattr(broad, "collect", fake_collect)
    result = broad.scan_openalex_topic_landscape(
        as_of=date.today(), lookback_days=30, env={},
    )
    assert result["status"] == "observed_bounded_top100_overlap"
    assert result["source_requests"] == 6
    assert result["max_source_requests"] == 9
    assert result["grouped_source_requests"] == 3
    assert result["historical_probe_source_requests"] == 3
    assert result["history_probe_candidate_count"] == 1
    assert result["history_probe_measured"] == 1
    assert result["history_probe_unavailable"] == 0
    assert called == [
        ("groups", 0), ("groups", 1), ("groups", 2),
        ("count", 0), ("count", 1), ("count", 2),
    ]
    row = result["rising_or_accelerating_watchlist"][0]
    assert row["topic_id"] == "T22222"
    assert row["topic_counts"] == [0, 1, 50]
    assert row["direction"] == "newly_observed_research_activity"
    assert row["historical_cells_verified_by_direct_count"] is True
    assert row["market_growth_verified"] is False
    assert result["buyer_or_market_growth_verified"] is False
    rendered = "\n".join(broad.format_broad_topic_scan(result))
    assert "three additional source-count checks" in rendered
    assert "undefined (measured zero first-period baseline)" in rendered
    assert "+inf" not in rendered


def test_missing_top100_ranking_can_hide_stable_topic_not_false_emergence(
    monkeypatch,
):
    periods = trends.completed_periods(date.today(), 30)
    groups = [
        {"T11111": ("Always Established", 200)},
        {"T11111": ("Always Established", 201)},
        {"T11111": ("Always Established", 202),
         "T22222": ("Unranked Previously", 50)},
    ]
    def fake_collect(plan, **_kwargs):
        q = parse_qs(urlsplit(plan.url).query)
        index = [p["through"] for p in periods].index(
            q["filter"][0].split("to_publication_date:")[1][:10]
        )
        if "group_by" in q:
            return _group_response(groups[index])
        return {"source": "openalex", "status": "observed",
                "data": {"meta": {"count": [48, 49, 50][index]}}}
    monkeypatch.setattr(broad, "collect", fake_collect)
    res = broad.scan_openalex_topic_landscape(
        as_of=date.today(), lookback_days=30, env={},
    )
    assert res["history_probe_measured"] == 1
    assert res["rising_or_accelerating_watchlist"] == []
    assert res["history_probe_results"][0]["research_direction"] == (
        "approximately_stable_research_share"
    )
    assert res["omitted_group_not_equivalent_to_zero_count"] is True


@pytest.mark.parametrize("recent_topic_count,response_count,status", [
    (60, None, "unavailable_source_count"),
    (60, 110, "inconsistent_source_snapshots"),
])
def test_missing_history_or_count_mismatch_cannot_manufacture_growth(
    monkeypatch, recent_topic_count, response_count, status,
):
    periods = trends.completed_periods(date.today(), 30)
    def fake_collect(plan, **_kwargs):
        q = parse_qs(urlsplit(plan.url).query)
        index = [p["through"] for p in periods].index(
            q["filter"][0].split("to_publication_date:")[1][:10]
        )
        if "group_by" in q:
            groups = {"T11111": ("Old Established", 200)}
            if index == 2:
                groups["T22222"] = ("New Ranking Entry", recent_topic_count)
            return _group_response(groups)
        if response_count is None and index == 1:
            return {"source": "openalex", "status": "unavailable",
                    "http_status": 429}
        count = [0, 1, response_count][index]
        return {"source": "openalex", "status": "observed",
                "data": {"meta": {"count": count}}}
    monkeypatch.setattr(broad, "collect", fake_collect)
    scan = broad.scan_openalex_topic_landscape(
        as_of=date.today(), lookback_days=30, env={},
    )
    assert scan["history_probe_candidate_count"] == 1
    assert scan["history_probe_results"][0]["status"] == status
    assert scan["rising_or_accelerating_watchlist"] == []
    assert scan["history_probe_measured"] == 0
    assert scan["source_requests"] <= 6


def test_only_two_recent_gaps_probed_at_most_six_extra_requests(monkeypatch):
    periods = trends.completed_periods(date.today(), 30)
    calls = []
    def fake_collect(plan, **_kwargs):
        q = parse_qs(urlsplit(plan.url).query)
        index = [p["through"] for p in periods].index(
            q["filter"][0].split("to_publication_date:")[1][:10]
        )
        if "group_by" in q:
            groups = {"T11111": ("Base Stable Topic", 300)}
            if index == 2:
                for j in range(3):
                    groups[f"T{22222+j}"] = (f"Newly Ranked Topic {j}", 80-j*10)
            calls.append(("group", index))
            return _group_response(groups)
        calls.append(("probe", index))
        topic = q["filter"][0].split("primary_topic.id:")[1]
        recent_counts = {"T22222":80,"T22223":70}
        return {"source": "openalex", "status": "observed",
                "data": {"meta": {"count": (
                    recent_counts[topic] if index == 2 else 0
                )}}}
    monkeypatch.setattr(broad, "collect", fake_collect)
    scan = broad.scan_openalex_topic_landscape(
        as_of=date.today(), lookback_days=30, env={},
    )
    assert scan["source_requests"] == 9
    assert scan["historical_probe_source_requests"] == 6
    assert scan["history_probe_candidate_count"] == 2
    assert [p["topic_id"] for p in scan["history_probe_results"]] == [
        "T22222", "T22223",
    ]
    assert "T22224" not in repr(scan["history_probe_results"])
    assert len([x for x in calls if x[0] == "probe"]) == 6
    assert len(scan["rising_or_accelerating_watchlist"]) == 2


def test_broad_scan_is_explicit_and_plan_only_mode_is_network_free(monkeypatch):
    def forbidden(*_a, **_kw):
        raise AssertionError("No network access allowed in plan-only mode")
    monkeypatch.setattr(broad, "collect", forbidden)
    monkeypatch.setattr(discovery, "collect", forbidden)
    monkeypatch.setattr(trends, "collect", forbidden)
    with pytest.raises(ValueError):
        discovery.discover_current(
            execute=False, broad_topic_scan=True, measure_trends=False,
            env={},
        )
    plan = discovery.discover_current(
        execute=False, broad_topic_scan=True, measure_trends=True,
        ted_date_slices=3, limit=20, env={},
    )
    assert plan["network_performed"] is False
    assert plan["request_count"] == 5
    assert plan["max_requests_with_trend_measurement"] == 23
    assert plan["trend_evidence"]["max_additional_source_requests"] == 18
    assert plan["trend_evidence"]["most_represented_topic_group_cap"] == 100
    assert plan["trend_evidence"]["max_recent_ranking_gap_history_probes"] == 2
    assert plan["trend_evidence"]["broad_topic_scan_opted_in"] is True


def test_broad_scan_augmentation_cannot_upgrade_research_to_product_demand(
    monkeypatch,
):
    base = _source()
    def fake_original(plan, **_kwargs):
        if plan.source == "openalex":
            return base
        return {"source": plan.source, "status": "observed",
                "observations": {"record_count": 0, "sample": []}}
    def fake_counts(plan, **_kwargs):
        q = parse_qs(urlsplit(plan.url).query)
        pos = [p["through"] for p in trends.completed_periods(
            date.today(), 30
        )].index(q["filter"][0].split("to_publication_date:")[1][:10])
        topic = "primary_topic.id:" in q["filter"][0]
        return {"source": "openalex", "status": "observed",
                "data": {"meta": {"count": [10, 13, 18][pos]
                                  if topic else 100000}}}
    group_counts = [50, 65, 100]
    def fake_groups(plan, **_kwargs):
        q = parse_qs(urlsplit(plan.url).query)
        pos = [p["through"] for p in trends.completed_periods(
            date.today(), 30
        )].index(q["filter"][0].split("to_publication_date:")[1][:10])
        return _group_response({
            "T11999": ("Additional growing source topic", group_counts[pos])
        })
    monkeypatch.setattr(discovery, "collect", fake_original)
    monkeypatch.setattr(trends, "collect", fake_counts)
    monkeypatch.setattr(broad, "collect", fake_groups)
    result = discovery.discover_current(
        execute=True, measure_trends=True, broad_topic_scan=True,
        lookback_days=30, limit=20, env={},
    )
    assert result["queries_budgeted"] == 3 + 6 + 3
    assert result["trend_evidence"]["additional_source_requests"] == 9
    assert result["trend_evidence"]["broad_topic_scan"]["status"] == (
        "observed_bounded_top100_overlap"
    )
    watchlist = result["trend_evidence"]["idea_watchlist"]
    assert {x["topic_id"] for x in watchlist} == {"T11333", "T11999"}
    assert all(x["product_opportunity_verified"] is False for x in watchlist)
    assert all(x["keyword_search_demand_verified"] is False for x in watchlist)
    assert result["paid_buyers_verified"] is False
    assert result["growth_rate_verified"] is False
    txt = discovery.format_discovery_report(result)
    assert "BROADER TOPIC MOMENTUM SCAN" in txt
    assert "PRODUCT-IDEA RESEARCH WATCHLIST" in txt
