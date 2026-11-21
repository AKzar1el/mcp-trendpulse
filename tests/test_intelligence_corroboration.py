"""Free-only source-corroboration tests: lexical evidence != customer demand."""
from __future__ import annotations

from datetime import date
from urllib.parse import parse_qs, urlsplit

import pytest

from mcp_trendpulse import intelligence_corroboration as cor
from mcp_trendpulse import intelligence_discovery as discovery
from mcp_trendpulse import intelligence_trends as trends
from mcp_trendpulse.intelligence_core import (
    _bounded_github_issue_count, _is_github_issue_count_plan, plan_source,
)
from mcp_trendpulse.intelligence_evidence import UnexpectedSourceShape


def _idea(code="T12026", label="Explainable Artificial Intelligence (XAI)"):
    return {"topic_id": code, "label": label,
            "research_direction": "early_rising_research_watchlist",
            "product_opportunity_verified": False}


def _search_count(n: int, *, incomplete=False):
    return {"source": "github_issues", "status": "observed", "data": {
        "total_count": n, "incomplete_results": incomplete,
    }}


def test_source_topic_phrase_disallows_provider_punctuation_or_query_injection():
    assert cor.source_phrase("Explainable Artificial Intelligence (XAI)") == (
        "Explainable Artificial Intelligence"
    )
    assert cor.source_phrase("Oral History, Memory, Narrative Analysis") == (
        "Oral History Memory Narrative Analysis"
    )
    for name in [
        "XAI", "", "foo", "x", "AI", 123, '"hack" is:issue created:>2020',
        "Secret\nquery", "T12026", "T13590", "A" * 200,
    ]:
        assert cor.source_phrase(name) == ""


def test_issue_count_plan_uses_existing_free_source_and_exact_closed_open_dates():
    p = plan_source("github_issues", keyword="research", limit=1, env={})
    windows = trends.completed_periods(date(2026, 11, 19), 30)[-2:]
    q = cor.issue_count_plan(
        p, "Explainable Artificial Intelligence", windows[-1],
    )
    parts = urlsplit(q.url)
    params = parse_qs(parts.query)
    assert (parts.scheme, parts.hostname, parts.path) == (
        "https", "api.github.com", "/search/issues",
    )
    assert q.source == "github_issues"
    assert q.budget_per_day == 12 == p.budget_per_day
    assert params["per_page"] == ["1"]
    assert params["q"] == [
        '"Explainable Artificial Intelligence" in:title,body '
        'is:issue is:public created:2026-10-07..2026-11-05'
    ]
    assert "is:open" not in params["q"][0]
    assert _is_github_issue_count_plan(q) is True
    assert _is_github_issue_count_plan(p) is False
    with pytest.raises(ValueError):
        cor.issue_count_plan(
            p, '"XAI" is:issue', windows[0],
        )


def test_safe_aggregate_cache_projection_discards_all_issue_contents_and_users():
    raw = {
        "total_count": 7, "incomplete_results": False,
        "items": [{
            "id": 123,
            "title": "SENSITIVE_ISSUE_TITLE",
            "body": "SENSITIVE_PRIVATE_TEXT",
            "user": {"email": "secret@example.invalid"},
            "html_url": "https://github.com/owner/repo/issues/1",
        }],
        "author": "SENSITIVE",
        "secret_token": "DROP",
    }
    reduced = _bounded_github_issue_count(raw)
    assert reduced == {"total_count": 7, "incomplete_results": False}
    assert "SENSITIVE" not in repr(reduced)
    assert "secret@example.invalid" not in repr(reduced)


@pytest.mark.parametrize("payload", [
    None, [], {},
    {"total_count": None, "incomplete_results": False, "items": []},
    {"total_count": True, "incomplete_results": False, "items": []},
    {"total_count": -1, "incomplete_results": False, "items": []},
    {"total_count": 4, "incomplete_results": "false", "items": []},
    {"total_count": 4, "incomplete_results": False, "items": {}},
    {"total_count": 4, "incomplete_results": False, "items": [{}, {}]},
])
def test_invalid_issue_count_shape_not_misinterpreted_as_zero(payload):
    with pytest.raises(UnexpectedSourceShape):
        _bounded_github_issue_count(payload)


def test_two_source_dates_per_auto_topic_not_arbitrary_keywords(monkeypatch):
    observed = []
    def fake_collect(plan, **kwargs):
        assert kwargs["fetch"] is True and kwargs["timeout"] == 20
        assert kwargs["env"] == {}
        assert _is_github_issue_count_plan(plan)
        q = parse_qs(urlsplit(plan.url).query)["q"][0]
        observed.append(q)
        return _search_count(4 if "2026-10-07..2026-11-05" in q else 2)
    monkeypatch.setattr(cor, "collect", fake_collect)
    out = cor.corroborate_research_issue_mentions(
        [_idea()], as_of=date(2026, 11, 19),
        lookback_days=30, env={},
    )
    assert out["status"] == "observed_complete_lexical_counts"
    assert out["source_requests"] == 2
    assert out["max_source_requests"] == 4
    assert out["topics"][0]["source_created_issue_counts"] == [2, 4]
    assert len(out["topics"][0]["source_search_urls"]) == 2
    assert out["not_customer_pain_verified"] is True
    assert out["not_independent_users_or_buyers_verified"] is True
    assert out["not_market_or_search_growth_verified"] is True
    assert out["not_normalized_by_all_github_issues"] is True
    assert observed == [
        '"Explainable Artificial Intelligence" in:title,body is:issue is:public '
        'created:2026-09-07..2026-10-06',
        '"Explainable Artificial Intelligence" in:title,body is:issue is:public '
        'created:2026-10-07..2026-11-05',
    ]
    rendered = "\n".join(cor.format_issue_corroboration(out))
    assert "2 → 4" in rendered
    assert "NOT verified unmet needs" in rendered
    assert "different measures" in rendered
    assert "github.com/search?" in rendered


def test_incomplete_or_rate_limited_counts_do_not_claim_zero_or_adoption(
    monkeypatch,
):
    seen = []
    def fake_collect(plan, **_kwargs):
        seen.append(plan.url)
        return (_search_count(14, incomplete=True) if len(seen) == 1 else
                {"source": "github_issues", "status": "unavailable",
                 "http_status": 429})
    monkeypatch.setattr(cor, "collect", fake_collect)
    out = cor.corroborate_research_issue_mentions(
        [_idea()], as_of=date(2026, 11, 19),
        lookback_days=30, env={},
    )
    assert out["source_requests"] == 2
    assert out["status"] == "partial_or_unavailable_source"
    assert out["topics"][0]["source_created_issue_counts"] == [None, None]
    assert out["topics"][0]["market_and_product_adoption_verified"] is False
    txt = "\n".join(cor.format_issue_corroboration(out))
    assert "cannot infer zero discussion" in txt
    assert "14" not in txt


def test_no_rising_research_topic_means_no_extra_network_queries(monkeypatch):
    def forbidden(*_a, **_kwargs):
        raise AssertionError("No source queries without eligible topics")
    monkeypatch.setattr(cor, "collect", forbidden)
    out = cor.corroborate_research_issue_mentions(
        [], as_of=date(2026, 11, 19), lookback_days=30, env={},
    )
    assert out["status"] == "no_eligible_research_topics"
    assert out["source_requests"] == 0
    assert out["topics"] == []


def test_at_most_two_source_topics_and_four_queries(monkeypatch):
    queries = []
    def fake_collect(plan, **_kwargs):
        queries.append(plan.url)
        return _search_count(0)
    monkeypatch.setattr(cor, "collect", fake_collect)
    result = cor.corroborate_research_issue_mentions(
        [
            _idea("T12026", "Explainable Artificial Intelligence"),
            _idea("T12121", "Computer Vision Interpretability"),
            _idea("T12222", "Digital Trust Management"),
        ],
        as_of=date(2026, 11, 19), lookback_days=30, env={},
    )
    assert result["source_requests"] == 4
    assert len(queries) == 4
    assert [t["topic_id"] for t in result["topics"]] == [
        "T12026", "T12121",
    ]
    assert all(t["source_created_issue_counts"] == [0, 0]
               for t in result["topics"])
    assert result["not_customer_pain_verified"] is True


def test_discovery_opt_in_plan_is_network_free_and_capped(monkeypatch):
    def forbid(*_a, **_kw):
        raise AssertionError("Plan-only must never fetch")
    monkeypatch.setattr(discovery, "collect", forbid)
    monkeypatch.setattr(cor, "collect", forbid)
    with pytest.raises(ValueError):
        discovery.discover_current(
            execute=False, measure_trends=False,
            corroborate_issues=True, env={},
        )
    p = discovery.discover_current(
        execute=False, measure_trends=True, broad_topic_scan=True,
        corroborate_issues=True, ted_date_slices=3, env={},
    )
    assert p["network_performed"] is False
    assert p["max_requests_with_trend_measurement"] == 27
    assert p["trend_evidence"]["max_additional_source_requests"] == 22
    assert p["trend_evidence"]["max_additional_github_issue_searches"] == 4
    assert p["trend_evidence"]["corroborate_issues_opted_in"] is True


def test_original_default_without_flag_has_no_github_issue_corroboration(
    monkeypatch,
):
    def fake_collect(plan, **_kwargs):
        if plan.source == "openalex":
            return {"source": "openalex", "status": "observed",
                    "observations": {"record_count": 0, "sample": []}}
        return {"source": plan.source, "status": "observed",
                "observations": {"record_count": 0, "sample": []}}
    monkeypatch.setattr(discovery, "collect", fake_collect)
    monkeypatch.setattr(cor, "collect", lambda *_a, **_kw:
                        (_ for _ in ()).throw(AssertionError("not opted in")))
    result = discovery.discover_current(execute=True, env={})
    assert result["queries_budgeted"] == 3
    assert "trend_evidence" not in result


def test_discovery_optional_issue_counts_are_separate_from_trend_rating(
    monkeypatch,
):
    as_of = date.today()
    works = [
        {
            "id": f"https://openalex.org/W{5000000000 + n}",
            "display_name": "Explainability system in practice",
            "publication_date": as_of.isoformat(),
            "primary_topic": {
                "id": "https://openalex.org/T12026",
                "display_name": "Explainable Artificial Intelligence (XAI)",
            },
        } for n in range(2)
    ]
    def from_existing(plan, **_kwargs):
        if plan.source == "openalex":
            return {"source": "openalex", "status": "observed",
                    "observations": {"record_count": 2, "sample": works}}
        return {"source": plan.source, "status": "observed",
                "observations": {"record_count": 0, "sample": []}}
    periods = trends.completed_periods(as_of, 30)
    def research_counts(plan, **_kwargs):
        query = parse_qs(urlsplit(plan.url).query)["filter"][0]
        i = [p["through"] for p in periods].index(
            query.split("to_publication_date:")[1][:10]
        )
        return {"source": "openalex", "status": "observed",
                "data": {"meta": {"count": (
                    [12, 17, 30][i]
                    if "primary_topic.id:" in query else 100_000
                )}}}
    seen = []
    def issue_counts(plan, **_kwargs):
        seen.append(plan.url)
        return _search_count(len(seen) * 2)
    monkeypatch.setattr(discovery, "collect", from_existing)
    monkeypatch.setattr(trends, "collect", research_counts)
    monkeypatch.setattr(cor, "collect", issue_counts)
    result = discovery.discover_current(
        execute=True, measure_trends=True,
        corroborate_issues=True, lookback_days=30, limit=20, env={},
    )
    assert result["network_performed"] is True
    assert result["queries_budgeted"] == 3 + 6 + 2
    evidence = result["trend_evidence"]
    assert evidence["additional_source_requests"] == 8
    assert evidence["max_additional_source_requests"] == 9 + 4
    assert evidence["topics"][0]["direction"] == "accelerating_research_share"
    assert evidence["issue_text_corroboration"]["topics"][0][
        "source_created_issue_counts"
    ] == [2, 4]
    assert evidence["buyer_spending_or_market_growth_verified"] is False
    assert result["growth_rate_verified"] is False
    assert result["paid_buyers_verified"] is False
    assert len(seen) == 2
    rendered = discovery.format_discovery_report(result)
    assert "INDEPENDENT DEVELOPER DISCUSSION CHECK" in rendered
    assert "not verified product" not in repr(evidence).lower()
