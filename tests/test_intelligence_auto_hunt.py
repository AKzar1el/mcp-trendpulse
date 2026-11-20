"""Tests for reuse of other existing free intelligence source adapters."""
from __future__ import annotations

from datetime import date
from urllib.parse import parse_qs, urlsplit

import pytest

from mcp_trendpulse import intelligence_auto_hunt as context
from mcp_trendpulse import intelligence_discovery as discovery
from mcp_trendpulse import intelligence_trends as trends


AS_OF = date(2026, 11, 19)


def idea(topic_id="T12026", label="Explainable Artificial Intelligence (XAI)"):
    return {
        "topic_id": topic_id, "label": label,
        "research_direction": "early_rising_research_watchlist",
        "product_opportunity_verified": False,
    }


def stub(name, *, cordis=1, usaspending=1):
    return {
        "topic": name.lower(),
        "status": "context_only_not_recent_activity",
        "source_coverage": [
            {
                "source": "cordis",
                "status": "observed",
                "records_accepted": 5,
                "topical_title_matches": cordis,
                "recent_eligible_matches": 0,
                "context_only_matches": cordis,
            },
            {
                "source": "usaspending",
                "status": "observed",
                "records_accepted": 5,
                "topical_title_matches": usaspending,
                "recent_eligible_matches": usaspending,
                "context_only_matches": 0,
            },
        ],
        "evidence": [
            {
                "source": "usaspending",
                "title": f"{name} federal procurement",
                "reference": "https://www.usaspending.gov/award/CONT_AWD_example",
                "event_date": "2026-11-10",
            },
        ],
    }


def test_no_explicitly_measured_research_topics_means_no_rotating_hunter_seed(
    monkeypatch,
):
    def forbid(*_a, **_kwargs):
        raise AssertionError("Must not substitute static/rotating seed topics")
    monkeypatch.setattr(context, "hunt_current", forbid)
    result = context.investigate_discovered_topics(
        [], as_of=AS_OF, lookback_days=30, env={},
    )
    assert result["source_request_budget"] == 0
    assert result["status"] == "no_research_topic_to_investigate"
    assert result["no_predefined_keyword_seeds"] is True
    assert "no predefined sector seeds" in "\n".join(
        context.format_discovered_source_context(result)
    )


def test_reuses_exact_existing_hunter_with_two_other_provider_sources(
    monkeypatch,
):
    calls = []
    def fake_hunt(topics, sources, **kwargs):
        calls.append((topics, sources, kwargs))
        return {"topics": [stub(topics[0])]}
    monkeypatch.setattr(context, "hunt_current", fake_hunt)
    result = context.investigate_discovered_topics(
        [idea()], as_of=AS_OF, lookback_days=30, env={},
    )
    assert calls[0][0] == ["Explainable Artificial Intelligence"]
    assert calls[0][1] == ["cordis", "usaspending"]
    assert calls[0][2]["execute"] is True
    assert calls[0][2]["as_of"] == "2026-11-19"
    assert calls[0][2]["lookback_days"] == 30
    assert calls[0][2]["env"] == {}
    assert result["status"] == "observed_bounded_source_context"
    assert result["source_request_budget"] == 2
    assert result["max_source_request_budget"] == 4
    assert [r["source"] for r in result["topics"][0]["source_coverage"]] == [
        "cordis", "usaspending",
    ]
    assert result["topics"][0]["source_coverage"][0][
        "topical_title_matches_in_sample"
    ] == 1
    assert result["topics"][0]["source_examples"][0]["source"] == "usaspending"
    assert result["product_or_market_growth_verified"] is False
    assert result["independent_buyer_demand_verified"] is False
    assert result["seo_keyword_growth_verified"] is False
    formatted = "\n".join(context.format_discovered_source_context(result))
    assert "CORDIS + USAspending" in formatted
    assert "Research-derived topic phrases only" in formatted
    assert "1 topic-title overlap(s)" in formatted
    assert "not independent paying customers" in formatted
    assert "https://www.usaspending.gov/award/" in formatted


def test_context_only_records_include_exact_project_links_and_safe_exclusion_reasons(
    monkeypatch,
):
    checked = stub("Explainable Artificial Intelligence")
    checked["evidence"] = []
    checked["source_coverage"][0]["recent_eligible_matches"] = 0
    checked["source_coverage"][1]["recent_eligible_matches"] = 0
    checked["context_examples"] = [
        {
            "source": "cordis",
            "title": "Explainable Artificial Intelligence EU-funded research",
            "reference": "https://cordis.europa.eu/project/id/101123330",
            "event_date": None,
            "reason": "timestamp_not_comparable_recent_market_event",
        },
        {
            "source": "usaspending",
            "title": "Explainable Artificial Intelligence federal contract",
            "reference": "https://www.usaspending.gov/search",
            "event_date": "2026-11-18",
            "reason": "timestamp_not_comparable_recent_market_event",
        },
        {
            "source": "cordis",
            "title": "MALICIOUS REMOTE LINK",
            "reference": "https://evil.example/?secret=leak",
            "event_date": None,
            "reason": "publication_date_unavailable",
        },
    ]
    monkeypatch.setattr(context, "hunt_current", lambda *_a, **_kw: {
        "topics": [checked],
    })
    result = context.investigate_discovered_topics(
        [idea()], as_of=AS_OF, lookback_days=30, env={},
    )
    topic = result["topics"][0]
    assert topic["source_examples"] == []
    assert len(topic["source_context_examples"]) == 2
    assert all(r["not_recent_market_activity"] for r in topic["source_context_examples"])
    assert topic["source_context_examples"][0]["reference_specificity"] == (
        "exact_official_project_record"
    )
    assert topic["source_context_examples"][1]["reference_specificity"] == (
        "provider_search_or_home_landing_only"
    )
    printed = "\n".join(context.format_discovered_source_context(result))
    assert "CONTEXT-ONLY SOURCE RECORDS" in printed
    assert "Exact published project fact sheet" in printed
    assert "NOT an exact record permalink" in printed
    assert "timestamp_not_comparable_recent_market_event" in printed
    assert "evil.example" not in repr(result)
    assert "recent market activity" in printed
    assert topic["source_context_exclusions_are_auditable"] is True
    assert result["product_or_market_growth_verified"] is False


def test_hunter_may_reorder_topics_but_labels_and_evidence_are_joined_by_phrase(
    monkeypatch,
):
    a = "Explainable Artificial Intelligence"
    b = "Computer Vision Interpretability"
    def fake_hunt(topics, sources, **kwargs):
        assert topics == [a, b]
        return {"topics": [stub(b, cordis=2, usaspending=0),
                           stub(a, cordis=0, usaspending=1)]}
    monkeypatch.setattr(context, "hunt_current", fake_hunt)
    result = context.investigate_discovered_topics([
        idea(), idea("T12345", b),
    ], as_of=AS_OF, lookback_days=30, env={})
    assert result["source_request_budget"] == 4
    assert [row["topic_id"] for row in result["topics"]] == [
        "T12026", "T12345",
    ]
    assert result["topics"][0]["source_coverage"][0][
        "topical_title_matches_in_sample"
    ] == 0
    assert result["topics"][1]["source_coverage"][0][
        "topical_title_matches_in_sample"
    ] == 2


def test_duplicate_and_invalid_provider_labels_cannot_create_queries(
    monkeypatch,
):
    calls = []
    def fake_hunt(topics, sources, **kwargs):
        calls.extend(topics)
        return {"topics": [stub(p) for p in topics]}
    monkeypatch.setattr(context, "hunt_current", fake_hunt)
    result = context.investigate_discovered_topics([
        idea("T12026"),
        idea("T12345", "Explainable Artificial Intelligence"),
        idea("T12346", "XAI"),
        idea("T12347", '"malicious" is:issue'),
        idea("T12348", "Research Data Integration"),
        idea("T12349", "Latest Fancy Research"),
    ], as_of=AS_OF, lookback_days=30, env={})
    assert calls == [
        "Explainable Artificial Intelligence", "Research Data Integration",
    ]
    assert result["source_request_budget"] == 4
    assert len(result["topics"]) == 2
    assert len(result["source_ids"]) == 2


def test_partial_source_coverage_not_reported_as_no_demand(monkeypatch):
    bad = stub("Explainable Artificial Intelligence")
    bad["source_coverage"][1]["status"] = "unavailable"
    def fake_hunt(*_a, **_kwargs):
        return {"topics": [bad]}
    monkeypatch.setattr(context, "hunt_current", fake_hunt)
    result = context.investigate_discovered_topics(
        [idea()], as_of=AS_OF, lookback_days=30, env={},
    )
    assert result["status"] == "partially_available_source_context"
    assert result["source_request_budget"] == 2
    assert result["topics"][0]["source_coverage"][1]["status"] == "unavailable"
    report = "\n".join(context.format_discovered_source_context(result))
    assert "NOT zero market interest" in report


def test_source_unavailability_preserves_safe_reason_not_arbitrary_provider_text(
    monkeypatch,
):
    checked = stub("Explainable Artificial Intelligence")
    checked["source_coverage"][0].update({
        "status": "rate_limited", "http_status": 429,
        "reason": "Bearer-secret-value-NEVER-ECHO",
    })
    checked["source_coverage"][1].update({
        "status": "unavailable", "http_status": "bad-status",
        "reason": "TimeoutError",
    })
    monkeypatch.setattr(context, "hunt_current", lambda *_a, **_kw: {
        "topics": [checked],
    })
    result = context.investigate_discovered_topics(
        [idea()], as_of=AS_OF, lookback_days=30, env={},
    )
    providers = result["topics"][0]["source_coverage"]
    assert result["topics"][0]["topic_id"] == "T12026"
    assert result["topics"][0]["research_direction"] == (
        "early_rising_research_watchlist"
    )
    assert result["status"] == "partially_available_source_context"
    assert providers[0]["http_status"] == 429
    assert "reason" not in providers[0]
    assert providers[1]["reason"] == "TimeoutError"
    assert "http_status" not in providers[1]
    report = "\n".join(context.format_discovered_source_context(result))
    assert "cordis: rate_limited (HTTP 429)" in report
    assert "usaspending: unavailable (TimeoutError)" in report
    assert "NOT zero market interest" in report
    assert "Bearer-secret-value" not in report
    assert "Bearer-secret-value" not in repr(result)
    assert result["product_or_market_growth_verified"] is False


def test_plan_only_is_zero_network_with_added_source_budget(monkeypatch):
    def forbidden(*_a, **_kwargs):
        raise AssertionError("Plan-only must never fetch source data")
    monkeypatch.setattr(context, "hunt_current", forbidden)
    monkeypatch.setattr(discovery, "collect", forbidden)
    with pytest.raises(ValueError):
        discovery.discover_current(
            execute=False, measure_trends=False,
            cross_source_hunt=True, env={},
        )
    plan = discovery.discover_current(
        execute=False, measure_trends=True, broad_topic_scan=True,
        corroborate_issues=True, cross_source_hunt=True,
        lookback_days=30, ted_date_slices=3, env={},
    )
    assert plan["network_performed"] is False
    assert plan["source_count"] == 3
    assert plan["request_count"] == 5
    assert plan["max_requests_with_trend_measurement"] == 31
    assert plan["trend_evidence"]["max_additional_source_requests"] == 26
    assert plan["trend_evidence"]["max_additional_other_source_requests"] == 4
    assert plan["trend_evidence"]["cross_source_hunt_source_ids"] == [
        "cordis", "usaspending",
    ]
    assert plan["trend_evidence"]["cross_source_hunt_opted_in"] is True


def test_default_discovery_remains_only_three_primary_sources(monkeypatch):
    observed = []
    def fake_collect(plan, **_kwargs):
        observed.append(plan.source)
        return {"source": plan.source, "status": "observed",
                "observations": {"record_count": 0, "sample": []}}
    monkeypatch.setattr(discovery, "collect", fake_collect)
    monkeypatch.setattr(context, "hunt_current", lambda *_a, **_kw:
                        (_ for _ in ()).throw(AssertionError("not opted in")))
    result = discovery.discover_current(execute=True, env={})
    assert observed == ["openalex", "cfpb", "ted"]
    assert result["queries_budgeted"] == 3
    assert "trend_evidence" not in result
    rendered = discovery.format_discovery_report(result)
    assert "AVAILABLE INTELLIGENCE ADAPTERS: 25 catalogued" in rendered
    assert "baseline queries only OpenAlex, CFPB and TED" in rendered


def test_integrated_dynamic_research_workflows_use_extra_sources_only_opt_in(
    monkeypatch,
):
    as_of = date.today()
    works = [{
        "id": f"https://openalex.org/W{5000000000+i}",
        "display_name": "Explainable evaluation research",
        "publication_date": as_of.isoformat(),
        "primary_topic": {
            "id": "https://openalex.org/T12026",
            "display_name": "Explainable Artificial Intelligence (XAI)",
        },
    } for i in range(2)]
    def fake_collect(plan, **_kwargs):
        if plan.source == "openalex":
            return {"source": "openalex", "status": "observed",
                    "observations": {"record_count": 2, "sample": works}}
        return {"source": plan.source, "status": "observed",
                "observations": {"record_count": 0, "sample": []}}
    periods = trends.completed_periods(as_of, 30)
    def counts(plan, **_kwargs):
        query = parse_qs(urlsplit(plan.url).query)["filter"][0]
        idx = [p["through"] for p in periods].index(
            query.split("to_publication_date:")[1][:10]
        )
        return {"source": "openalex", "status": "observed",
                "data": {"meta": {"count": [12, 16, 30][idx]
                                  if "primary_topic.id:" in query
                                  else 100_000}}}
    calls = []
    def fake_hunt(topics, sources, **kwargs):
        calls.append((topics, sources, kwargs))
        return {"topics": [stub(topics[0])]}
    monkeypatch.setattr(discovery, "collect", fake_collect)
    monkeypatch.setattr(trends, "collect", counts)
    monkeypatch.setattr(context, "hunt_current", fake_hunt)
    result = discovery.discover_current(
        execute=True, measure_trends=True, cross_source_hunt=True,
        lookback_days=30, limit=20, env={},
    )
    assert len(calls) == 1
    assert calls[0][0] == ["Explainable Artificial Intelligence"]
    assert calls[0][1] == ["cordis", "usaspending"]
    assert result["queries_budgeted"] == 3 + 6 + 2
    evidence = result["trend_evidence"]
    assert evidence["additional_source_requests"] == 8
    assert evidence["max_additional_source_requests"] == 9 + 4
    assert evidence["topics"][0]["direction"] == "accelerating_research_share"
    assert evidence["other_source_context"]["source_request_budget"] == 2
    assert evidence["other_source_context"]["source_ids"] == [
        "cordis", "usaspending",
    ]
    assert evidence["other_source_context"]["product_or_market_growth_verified"] is False
    assert result["growth_rate_verified"] is False
    assert result["paid_buyers_verified"] is False
    report = discovery.format_discovery_report(result)
    assert "ADDITIONAL EXISTING SOURCES" in report
    assert "25 catalogued" in report
