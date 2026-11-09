import pytest
from fastmcp import Client

from mcp_trendpulse import hosted, server
from mcp_trendpulse.digestseo import DigestSeoContextError
from mcp_trendpulse.errors import (
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from mcp_trendpulse.providers import ProviderSet, use_provider_set


HOSTED_TOOL_NAMES = {
    "discover_trends",
    "analyze_keyword_trend",
    "compare_keyword_trends",
    "discover_related_demand",
    "get_trend_context",
    "find_seo_opportunities",
}
COMMUNITY_ONLY_TOOL_NAMES = {
    "get_news_by_keyword",
    "get_news_by_location",
    "get_news_by_topic",
    "get_top_news",
    "get_trending_terms",
    "get_trends",
    "get_growth",
    "get_ranked_trends",
    "get_top_trends",
    "get_news_by_site",
    "get_article_content",
    "get_interest_by_region",
    "get_related_queries",
    "get_related_topics",
    "get_suggestions",
    "get_categories",
}


class FakeTrendsProvider:
    provider_id = "fake_trends"

    async def get_ranked_trends(self, **kwargs):
        return [
            {
                "keyword": f"trend-{index}",
                "volume": 1000 - index,
                "growth_pct": 250.0 - index,
                "started": 1_700_000_000 + index,
                "news": [
                    {
                        "title": f"Story {index}",
                        "url": f"https://example.com/story-{index}",
                        "source": "Example",
                        "snippet": "Context snippet",
                    }
                ],
            }
            for index in range(30)
        ]

    async def get_trends(self, keyword, **kwargs):
        keywords = [keyword] if isinstance(keyword, str) else keyword
        rows = []
        for keyword_index, term in enumerate(keywords):
            for point_index in range(30):
                rows.append(
                    {
                        "date": f"2026-07-{point_index + 1:02d}",
                        "value": float((point_index + keyword_index * 7) % 101),
                        "keyword": term,
                    }
                )
        return rows

    async def get_growth(self, keyword, **kwargs):
        keywords = [keyword] if isinstance(keyword, str) else keyword
        return [
            {
                "keyword": term,
                "growth": {"3M": 12.5 + index, "1Y": 40.0 + index},
            }
            for index, term in enumerate(keywords)
        ]

    async def get_related_queries(self, keyword, **kwargs):
        return {
            "top": [
                {"query": f"{keyword} top {index}", "value": float(100 - index)}
                for index in range(20)
            ],
            "rising": [
                {"query": f"{keyword} rising {index}", "value": float(500 - index)}
                for index in range(20)
            ],
        }

    async def get_related_topics(self, keyword, **kwargs):
        return {
            "top": [
                {
                    "mid": f"/m/top{index}",
                    "title": f"Top topic {index}",
                    "type": "Topic",
                    "value": float(100 - index),
                }
                for index in range(20)
            ],
            "rising": [
                {
                    "mid": f"/m/rising{index}",
                    "title": f"Rising topic {index}",
                    "type": "Topic",
                    "value": float(400 - index),
                }
                for index in range(20)
            ],
        }

    async def get_suggestions(self, keyword, language=None):
        return [
            {
                "mid": f"/m/suggestion{index}",
                "title": f"{keyword} suggestion {index}",
                "type": "Topic",
            }
            for index in range(20)
        ]


class FakeNewsProvider:
    provider_id = "fake_news"

    def __init__(self):
        self.rss_calls = []

    async def get_rss_headlines_by_keyword(self, keyword, period=7, max_results=10):
        self.rss_calls.append((keyword, period, max_results))
        return [
            {
                "title": f"{keyword} headline {index}",
                "url": f"https://news.google.com/rss/articles/{index}",
                "publish_date": "2026-08-23T00:00:00+00:00",
                "meta_site_name": "Example News",
            }
            for index in range(max_results + 3)
        ]

    async def get_news_by_keyword(self, **kwargs):
        raise AssertionError("Hosted trend context must not download publisher articles")


@pytest.fixture
def fake_providers() -> ProviderSet:
    return ProviderSet(
        news=FakeNewsProvider(),
        trends=FakeTrendsProvider(),
    )


async def test_hosted_catalog_exposes_only_six_goal_oriented_tools():
    async with Client(hosted.hosted_mcp) as client:
        tools = await client.list_tools()

    by_name = {tool.name: tool for tool in tools}
    assert set(by_name) == HOSTED_TOOL_NAMES
    assert not (set(by_name) & COMMUNITY_ONLY_TOOL_NAMES)

    for tool in tools:
        assert tool.description
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.openWorldHint is True
        assert tool.annotations.destructiveHint is False
        output_schema = getattr(tool, "outputSchema", None) or getattr(
            tool, "output_schema", None
        )
        assert output_schema
        assert output_schema["type"] == "object"

    seo_schema = by_name["find_seo_opportunities"].inputSchema
    assert "project_id" in seo_schema["properties"]
    assert "project_id" not in seo_schema.get("required", [])


async def test_community_catalog_remains_separate_from_hosted_catalog():
    async with Client(server.mcp) as client:
        tools = await client.list_tools()

    assert {tool.name for tool in tools} == COMMUNITY_ONLY_TOOL_NAMES


@pytest.mark.parametrize(
    ("tool_name", "required_phrases"),
    [
        ("discover_trends", ("no specific seed", "ranked")),
        ("analyze_keyword_trend", ("one known keyword", "do not use it to compare")),
        ("compare_keyword_trends", ("2-5 known keywords", "relative momentum")),
        ("discover_related_demand", ("seed keyword", "does not return a time-series")),
        ("get_trend_context", ("current-news context", "why a term may be moving")),
        ("find_seo_opportunities", ("SEO keyword candidates", "without it results remain trend-only")),
    ],
)
async def test_tool_descriptions_encode_selection_boundaries(tool_name, required_phrases):
    async with Client(hosted.hosted_mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    description = tools[tool_name].description.lower()
    for phrase in required_phrases:
        assert phrase.lower() in description


@pytest.mark.parametrize(
    ("tool_name", "keyword_arg"),
    [
        ("analyze_keyword_trend", "keyword"),
        ("discover_related_demand", "keyword"),
        ("get_trend_context", "keyword"),
        ("find_seo_opportunities", "seed_keyword"),
    ],
)
async def test_hosted_single_keyword_tools_reject_blank_input_before_provider_use(
    monkeypatch, tool_name, keyword_arg
):
    def unexpected_provider_access():
        raise AssertionError("Blank keywords must not reach providers")

    monkeypatch.setattr(hosted, "get_provider_set", unexpected_provider_access)
    with pytest.raises(ValueError, match="Keyword must not be empty"):
        await getattr(hosted, tool_name)(**{keyword_arg: " \t "})


async def test_discover_trends_is_bounded_and_preserves_provider_metadata(fake_providers, monkeypatch):
    called_with = {}
    original = fake_providers.trends.get_ranked_trends

    async def capture_ranked_trends(**kwargs):
        called_with.update(kwargs)
        return await original(**kwargs)

    monkeypatch.setattr(fake_providers.trends, "get_ranked_trends", capture_ranked_trends)
    with use_provider_set(fake_providers):
        result = await hosted.discover_trends(geo="US", sort_by="growth", limit=3)

    assert called_with["sort"] == "recent_growth_pct"
    assert result.provider == "fake_trends"
    assert result.geo == "US"
    assert result.sorted_by == "growth"
    assert "comparison baseline is unspecified" in result.growth_metric_note
    assert "not week-over-week" in result.growth_metric_note
    assert [item.keyword for item in result.trends] == ["trend-0", "trend-1", "trend-2"]
    assert all(len(item.context_articles) <= 3 for item in result.trends)


async def test_analyze_and_compare_return_bounded_series(fake_providers):
    with use_provider_set(fake_providers):
        analysis = await hosted.analyze_keyword_trend(
            keyword="agent search",
            geo="US",
            timeframe="today 12-m",
            max_points=10,
        )
        comparison = await hosted.compare_keyword_trends(
            keywords=["agent search", "answer engine optimization"],
            geo="US",
            timeframe="today 12-m",
            max_points_per_keyword=10,
        )

    assert analysis.provider == "fake_trends"
    assert analysis.metrics.points_observed == 30
    assert len(analysis.series) <= 10
    assert analysis.series[0].date == "2026-07-01"
    assert analysis.series[-1].date == "2026-07-30"
    assert analysis.growth == {"3M": 12.5, "1Y": 40.0}

    assert [item.keyword for item in comparison.comparisons] == [
        "agent search",
        "answer engine optimization",
    ]
    assert all(item.metrics.points_observed == 30 for item in comparison.comparisons)
    assert all(len(item.series) <= 10 for item in comparison.comparisons)


async def test_hosted_growth_note_is_independent_of_selected_series_timeframe(fake_providers):
    with use_provider_set(fake_providers):
        analysis = await hosted.analyze_keyword_trend(
            keyword="agent search", timeframe="now 1-d"
        )
        comparison = await hosted.compare_keyword_trends(
            keywords=["agent search", "answer engine optimization"], timeframe="today 5-y"
        )

    for response in (analysis, comparison):
        note = response.model_dump()["growth_scope_note"]
        assert "3M" in note and "1Y" in note
        assert "separate" in note.lower()
        assert "selected timeframe" in note.lower()
    assert analysis.timeframe == "now 1-d"
    assert comparison.timeframe == "today 5-y"


def test_hosted_excludes_nonfinite_trend_numbers():
    assert hosted._as_float("nan") is None
    assert hosted._as_float("-Infinity") is None
    points = [
        {"date": "2026-10-01", "value": 25},
        {"date": "2026-10-02", "value": float("nan")},
        {"date": "2026-10-03", "value": float("inf")},
        {"date": "2026-10-04", "value": "75"},
    ]
    metrics = hosted._interest_metrics(points)
    assert (metrics.latest, metrics.average, metrics.peak, metrics.points_observed) == (75.0, 50.0, 75.0, 2)
    assert [point.value for point in hosted._bounded_series(points, max_points=10)] == [25.0, 75.0]
    assert hosted._growth_by_keyword([
        {"keyword": "seo", "growth": {"3M": float("nan"), "1Y": 15.0, "2Y": float("inf")}}
    ]) == {"seo": {"1Y": 15.0}}


def test_hosted_excludes_out_of_range_normalized_interest_points():
    # Google Trends interest is a normalized 0-100 score, not arbitrary volume.
    points = [
        {"date": "2026-11-01", "value": -4},
        {"date": "2026-11-02", "value": 0},
        {"date": "2026-11-03", "value": 100},
        {"date": "2026-11-04", "value": 125},
    ]
    metrics = hosted._interest_metrics(points)
    assert (metrics.latest, metrics.average, metrics.peak, metrics.points_observed) == (100.0, 50.0, 100.0, 2)
    assert [point.value for point in hosted._bounded_series(points, 10)] == [0.0, 100.0]
    assert hosted._interest_metrics(points[:1] + points[-1:]).points_observed == 0


def test_hosted_ignores_boolean_provider_interest_and_growth_values():
    assert hosted._as_float(True) is None
    assert hosted._as_float(False) is None
    points = [
        {"date": "2026-11-01", "value": True},
        {"date": "2026-11-02", "value": False},
        {"date": "2026-11-03", "value": 0.0},
        {"date": "2026-11-04", "value": 43.5},
    ]
    assert [point.value for point in hosted._bounded_series(points, 10)] == [0.0, 43.5]
    metrics = hosted._interest_metrics(points)
    assert (metrics.latest, metrics.average, metrics.peak, metrics.points_observed) == (43.5, 21.75, 43.5, 2)
    assert hosted._growth_by_keyword([
        {"keyword": "seo", "growth": {"3M": True, "6M": False, "1Y": 12.5}}
    ]) == {"seo": {"1Y": 12.5}}


def test_hosted_growth_ignores_malformed_provider_rows_and_mappings():
    # Optional growth data must not abort the usable trend-series response.
    assert hosted._growth_by_keyword([
        None,
        {"keyword": "one", "growth": ["not a mapping"]},
        {"keyword": "two", "growth": {"3M": 9.5}},
        {"keyword": "three", "growth": "unavailable"},
        {"keyword": "four", "growth": {"3M": "NaN", "1Y": 2}},
    ]) == {"one": {}, "two": {"3M": 9.5}, "three": {}, "four": {"1Y": 2.0}}

async def test_compare_preserves_valid_trends_when_provider_returns_malformed_rows(
    fake_providers, monkeypatch
):
    async def mixed_trends(keyword, **kwargs):
        return [
            None,
            ["unexpected row"],
            {"keyword": keyword[0], "date": "2026-11-01", "value": 25},
            {"keyword": keyword[1], "date": "2026-11-01", "value": 0},
            {"keyword": None, "date": "2026-11-02", "value": 80},
        ]

    monkeypatch.setattr(fake_providers.trends, "get_trends", mixed_trends)
    with use_provider_set(fake_providers):
        result = await hosted.compare_keyword_trends(keywords=["first", "second"])

    assert [entry.metrics.latest for entry in result.comparisons] == [25.0, 0.0]
    assert [entry.metrics.points_observed for entry in result.comparisons] == [1, 1]
    assert [entry.series[0].value for entry in result.comparisons] == [25.0, 0.0]


async def test_seo_opportunities_keep_valid_interest_when_provider_returns_malformed_rows(
    fake_providers, monkeypatch
):
    async def mixed_trends(keyword, **kwargs):
        return [
            None,
            "unexpected row",
            {"keyword": keyword[0], "date": "2026-11-01", "value": 35},
            {"keyword": keyword[1], "date": "2026-11-01", "value": 0},
        ]

    monkeypatch.setattr(fake_providers.trends, "get_trends", mixed_trends)
    with use_provider_set(fake_providers):
        result = await hosted.find_seo_opportunities(seed_keyword="seo", limit=2)

    assert [item.latest_interest for item in result.candidates] == [35.0, 0.0]
    assert [item.interest_validation_status for item in result.candidates] == [
        "observed", "observed"
    ]


@pytest.mark.parametrize("keywords", [["same", "same"], ["same", " SAME "]])
async def test_compare_rejects_duplicate_keywords(fake_providers, keywords):
    with use_provider_set(fake_providers), pytest.raises(ValueError, match="unique"):
        await hosted.compare_keyword_trends(
            keywords=keywords,
        )


async def test_related_demand_caps_every_section(fake_providers):
    with use_provider_set(fake_providers):
        result = await hosted.discover_related_demand(
            keyword="technical seo",
            limit=2,
        )

    assert result.provider == "fake_trends"
    assert len(result.top_queries) == 2
    assert len(result.rising_queries) == 2
    assert len(result.top_topics) == 2
    assert len(result.rising_topics) == 2
    assert len(result.suggestions) == 2
    assert result.limitations == []


async def test_related_demand_skips_malformed_provider_rows_before_section_limits(
    fake_providers, monkeypatch
):
    async def related_queries(**kwargs):
        return {
            "top": [None, {"query": "missing value"}, {"query": "valid top", "value": 80}],
            "rising": [42, {"query": "valid rising", "value": None, "is_breakout": True}],
        }

    async def related_topics(**kwargs):
        return {
            "top": [
                [],
                {"mid": "/m/valid", "title": "Valid topic", "type": "Topic", "value": 40},
            ],
            "rising": [
                {"mid": "/m/missing"},
                {"mid": "/m/rising", "title": "Rising topic", "type": "Topic", "value": 90},
            ],
        }

    async def suggestions(**kwargs):
        return [None, {"mid": "/m/s", "title": "Valid suggestion", "type": "Topic"}]

    monkeypatch.setattr(fake_providers.trends, "get_related_queries", related_queries)
    monkeypatch.setattr(fake_providers.trends, "get_related_topics", related_topics)
    monkeypatch.setattr(fake_providers.trends, "get_suggestions", suggestions)

    with use_provider_set(fake_providers):
        result = await hosted.discover_related_demand(keyword="seed", limit=1)

    assert [item.query for item in result.top_queries] == ["valid top"]
    assert [item.query for item in result.rising_queries] == ["valid rising"]
    assert result.rising_queries[0].is_breakout is True
    assert [item.title for item in result.top_topics] == ["Valid topic"]
    assert [item.title for item in result.rising_topics] == ["Rising topic"]
    assert [item.title for item in result.suggestions] == ["Valid suggestion"]
    assert any("malformed" in message.lower() for message in result.limitations)


async def test_breakout_demand_is_preserved_without_fabricated_percentage(fake_providers, monkeypatch):
    async def breakout_queries(**kwargs):
        return {"top": [], "rising": [{"query": "breakout query", "value": None,
                                       "is_breakout": True}]}

    async def breakout_topics(**kwargs):
        return {"top": [], "rising": [{"mid": "/m/breakout", "title": "Breakout topic",
                                       "type": "Topic", "value": None,
                                       "is_breakout": True}]}

    monkeypatch.setattr(fake_providers.trends, "get_related_queries", breakout_queries)
    monkeypatch.setattr(fake_providers.trends, "get_related_topics", breakout_topics)
    with use_provider_set(fake_providers):
        related = await hosted.discover_related_demand(keyword="seed")
        seo = await hosted.find_seo_opportunities(seed_keyword="seed")

    assert related.rising_queries[0].value is None
    assert related.rising_queries[0].is_breakout is True
    assert related.rising_topics[0].value is None
    assert related.rising_topics[0].is_breakout is True
    assert seo.candidates[0].keyword == "breakout query"
    assert seo.candidates[0].related_signal is None
    assert seo.candidates[0].related_signal_is_breakout is True


@pytest.mark.parametrize(
    ("failed_enrichment", "topic_count", "suggestion_count"),
    [("get_related_topics", 0, 2), ("get_suggestions", 2, 0)],
)
async def test_related_demand_preserves_queries_on_optional_failure(
    fake_providers, monkeypatch, failed_enrichment, topic_count, suggestion_count
):
    async def unavailable(*args, **kwargs):
        raise RuntimeError("optional provider temporarily unavailable")

    monkeypatch.setattr(fake_providers.trends, failed_enrichment, unavailable)
    with use_provider_set(fake_providers):
        result = await hosted.discover_related_demand(keyword="technical seo", limit=2)

    assert len(result.top_queries) == 2
    assert len(result.rising_queries) == 2
    assert len(result.top_topics) == topic_count
    assert len(result.suggestions) == suggestion_count
    assert len(result.limitations) == 1
    assert ("topics" if failed_enrichment == "get_related_topics" else "suggestions") in result.limitations[0].lower()


@pytest.mark.parametrize("malformed_topics", [None, ["unexpected provider row"]])
async def test_related_demand_preserves_queries_on_malformed_optional_topics(
    fake_providers, monkeypatch, malformed_topics
):
    async def invalid_topics(**kwargs):
        return malformed_topics

    monkeypatch.setattr(fake_providers.trends, "get_related_topics", invalid_topics)
    with use_provider_set(fake_providers):
        result = await hosted.discover_related_demand(keyword="technical seo", limit=2)

    assert len(result.top_queries) == 2
    assert len(result.rising_queries) == 2
    assert result.top_topics == []
    assert result.rising_topics == []
    assert len(result.suggestions) == 2
    assert any("topics" in item and "invalid" in item for item in result.limitations)


@pytest.mark.parametrize("malformed_queries", [None, ["unexpected provider payload"]])
async def test_related_demand_preserves_independent_enrichment_on_invalid_queries(
    fake_providers, monkeypatch, malformed_queries
):
    async def invalid_queries(**kwargs):
        return malformed_queries

    monkeypatch.setattr(fake_providers.trends, "get_related_queries", invalid_queries)
    with use_provider_set(fake_providers):
        result = await hosted.discover_related_demand(keyword="technical seo", limit=2)

    assert result.top_queries == []
    assert result.rising_queries == []
    assert len(result.top_topics) == 2
    assert len(result.suggestions) == 2
    assert any("related queries" in item.lower() and "invalid" in item for item in result.limitations)


async def test_related_demand_skips_extra_lookup_after_optional_rate_limit(fake_providers, monkeypatch):
    suggestion_calls = []

    async def rate_limited(*args, **kwargs):
        raise ProviderRateLimitError("google_trends", "related_topics")

    async def tracked_suggestions(*args, **kwargs):
        suggestion_calls.append(True)
        return []

    monkeypatch.setattr(fake_providers.trends, "get_related_topics", rate_limited)
    monkeypatch.setattr(fake_providers.trends, "get_suggestions", tracked_suggestions)
    with use_provider_set(fake_providers):
        result = await hosted.discover_related_demand(keyword="technical seo", limit=2)

    assert len(result.top_queries) == 2
    assert result.top_topics == []
    assert result.suggestions == []
    assert suggestion_calls == []
    assert any("rate limit" in limitation for limitation in result.limitations)


async def test_related_demand_still_surfaces_primary_query_failure(fake_providers, monkeypatch):
    async def unavailable(*args, **kwargs):
        raise RuntimeError("primary query fetch unavailable")

    monkeypatch.setattr(fake_providers.trends, "get_related_queries", unavailable)
    with use_provider_set(fake_providers), pytest.raises(RuntimeError, match="primary query"):
        await hosted.discover_related_demand(keyword="technical seo")


async def test_trend_context_combines_trend_and_news_provider_metadata(fake_providers):
    with use_provider_set(fake_providers):
        result = await hosted.get_trend_context(
            keyword="AI search",
            geo="US",
            news_period_days=3,
            max_articles=2,
        )

    assert result.trends_provider == "fake_trends"
    assert result.news_provider == "fake_news"
    assert result.metrics.points_observed == 30
    assert len(result.recent_articles) == 2
    assert result.recent_articles[0].source == "Example News"
    assert result.recent_articles[0].url == "https://news.google.com/rss/articles/0"
    assert result.recent_articles[0].link_type == "google_news_rss"
    assert result.recent_articles[0].publish_date == "2026-08-23T00:00:00+00:00"
    assert fake_providers.news.rss_calls == [("AI search", 3, 2)]
    assert "not downloaded publisher articles" in result.note
    assert result.limitations == []


async def test_trend_context_handles_empty_rss_headlines(fake_providers, monkeypatch):
    async def no_headlines(keyword, period, max_results):
        return []

    monkeypatch.setattr(fake_providers.news, "get_rss_headlines_by_keyword", no_headlines)
    with use_provider_set(fake_providers):
        result = await hosted.get_trend_context(keyword="AI search")

    assert result.recent_articles == []
    assert result.metrics.points_observed == 30


@pytest.mark.parametrize("malformed_payload", [None, {"title": "not a list"}, "not a list"])
async def test_trend_context_preserves_trends_when_rss_container_is_malformed(
    fake_providers, monkeypatch, malformed_payload
):
    async def malformed_headlines(**kwargs):
        return malformed_payload

    monkeypatch.setattr(
        fake_providers.news, "get_rss_headlines_by_keyword", malformed_headlines
    )
    with use_provider_set(fake_providers):
        result = await hosted.get_trend_context(keyword="AI search")

    assert result.metrics.points_observed == 30
    assert result.recent_articles == []
    assert any("malformed Google News RSS response" in note for note in result.limitations)


@pytest.mark.parametrize(
    "error_type", [ProviderRateLimitError, ProviderTimeoutError, ProviderUnavailableError]
)
async def test_trend_context_preserves_trends_when_optional_news_fails(
    fake_providers, monkeypatch, error_type
):
    async def unavailable(*args, **kwargs):
        raise error_type("google_news", "rss_headlines")

    monkeypatch.setattr(fake_providers.news, "get_rss_headlines_by_keyword", unavailable)
    with use_provider_set(fake_providers):
        result = await hosted.get_trend_context(keyword="AI search")

    assert result.metrics.points_observed == 30
    assert result.recent_articles == []
    assert result.news_provider == "fake_news"
    assert any("temporarily unavailable" in note for note in result.limitations)


async def test_trend_context_does_not_hide_unclassified_news_errors(fake_providers, monkeypatch):
    async def broken(*args, **kwargs):
        raise RuntimeError("unexpected news integration defect")

    monkeypatch.setattr(fake_providers.news, "get_rss_headlines_by_keyword", broken)
    with use_provider_set(fake_providers), pytest.raises(RuntimeError, match="integration defect"):
        await hosted.get_trend_context(keyword="AI search")


async def test_trend_context_skips_malformed_rss_rows_and_keeps_valid_headlines(
    fake_providers, monkeypatch
):
    async def rss_with_malformed_rows(**kwargs):
        return [
            None,
            {"title": "No URL"},
            ["invalid article"],
            {"title": "First valid headline", "url": "https://news.google.com/rss/articles/first"},
            {"title": "Second valid headline", "url": "https://news.google.com/rss/articles/second"},
        ]

    monkeypatch.setattr(
        fake_providers.news, "get_rss_headlines_by_keyword", rss_with_malformed_rows
    )
    with use_provider_set(fake_providers):
        result = await hosted.get_trend_context(keyword="AI search", max_articles=2)

    assert result.metrics.points_observed == 30
    assert [article.title for article in result.recent_articles] == [
        "First valid headline",
        "Second valid headline",
    ]
    assert all(article.link_type == "google_news_rss" for article in result.recent_articles)
    assert any("malformed" in limitation.lower() for limitation in result.limitations)


async def test_find_seo_opportunities_remains_trend_only_without_project(fake_providers):
    with use_provider_set(fake_providers):
        result = await hosted.find_seo_opportunities(
            seed_keyword="technical seo",
            geo="US",
            limit=3,
        )

    assert result.provider == "fake_trends"
    assert len(result.candidates) == 3
    assert all(item.signal_type == "rising_related_query" for item in result.candidates)
    assert all(item.latest_interest is not None for item in result.candidates)
    assert all(item.search_console is None for item in result.candidates)
    assert result.project_context is None
    assert any("No site-specific Search Console" in limitation for limitation in result.limitations)


async def test_find_seo_opportunities_ignores_invalid_and_duplicate_related_queries(
    fake_providers, monkeypatch
):
    trend_calls = []

    async def related_queries(**kwargs):
        return {
            "rising": [
                {"query": "  SEO TOOLS  ", "value": 400},
                {"query": "  Sitemap Generator  ", "value": 300},
                {"query": "sitemap generator", "value": 250},
                {"query": None, "value": 220},
                {"value": 200},
                {"query": 123, "value": 190},
                {"query": " Schema Validator ", "value": 180},
            ],
            "top": [{"query": "Hreflang checker", "value": 100}],
        }

    async def record_trends(keyword, **kwargs):
        trend_calls.append(keyword)
        return [
            {"keyword": term, "date": "2026-10-01", "value": 42}
            for term in keyword
        ]

    monkeypatch.setattr(fake_providers.trends, "get_related_queries", related_queries)
    monkeypatch.setattr(fake_providers.trends, "get_trends", record_trends)
    with use_provider_set(fake_providers):
        result = await hosted.find_seo_opportunities(
            seed_keyword="seo tools", limit=3
        )

    expected = ["Sitemap Generator", "Schema Validator", "Hreflang checker"]
    assert [candidate.keyword for candidate in result.candidates] == expected
    assert [candidate.signal_type for candidate in result.candidates] == [
        "rising_related_query",
        "rising_related_query",
        "top_related_query",
    ]
    assert trend_calls == [expected]
    assert all(candidate.interest_points_observed == 1 for candidate in result.candidates)


async def test_find_seo_opportunities_skips_non_mapping_related_rows(fake_providers, monkeypatch):
    async def related_queries(**kwargs):
        return {
            "rising": [None, 42, {"query": "valid rising", "value": 100}],
            "top": [["malformed"], {"query": "valid top", "value": 50}],
        }

    monkeypatch.setattr(fake_providers.trends, "get_related_queries", related_queries)
    with use_provider_set(fake_providers):
        result = await hosted.find_seo_opportunities(seed_keyword="seed", limit=2)

    assert [candidate.keyword for candidate in result.candidates] == ["valid rising", "valid top"]
    assert [candidate.interest_points_observed for candidate in result.candidates] == [30, 30]


@pytest.mark.parametrize("malformed_queries", [None, ["unexpected provider payload"]])
async def test_find_seo_opportunities_labels_invalid_related_query_container(
    fake_providers, monkeypatch, malformed_queries
):
    async def invalid_queries(**kwargs):
        return malformed_queries

    async def unexpected_trends(**kwargs):
        raise AssertionError("No Trends validation is possible without related keywords")

    monkeypatch.setattr(fake_providers.trends, "get_related_queries", invalid_queries)
    monkeypatch.setattr(fake_providers.trends, "get_trends", unexpected_trends)
    with use_provider_set(fake_providers):
        result = await hosted.find_seo_opportunities(seed_keyword="technical seo")

    assert result.candidates == []
    assert any("related queries" in item.lower() and "invalid" in item for item in result.limitations)


async def test_find_seo_opportunities_preserves_valid_section_when_other_is_malformed(
    fake_providers, monkeypatch
):
    async def mixed_queries(**kwargs):
        return {"rising": 42, "top": [{"query": "valid keyword", "value": 80}]}

    monkeypatch.setattr(fake_providers.trends, "get_related_queries", mixed_queries)
    with use_provider_set(fake_providers):
        result = await hosted.find_seo_opportunities(seed_keyword="seed")

    assert [candidate.keyword for candidate in result.candidates] == ["valid keyword"]
    assert result.candidates[0].interest_points_observed == 30
    assert any("malformed related-query" in item for item in result.limitations)


async def test_find_seo_opportunities_distinguishes_missing_interest_from_zero(
    fake_providers, monkeypatch
):
    trend_calls = []

    async def sparse_trends(keyword, **kwargs):
        trend_calls.append((keyword, kwargs))
        return [
            {"keyword": keyword[1], "date": "2026-10-01", "value": float("nan")},
            {"keyword": keyword[2], "date": "2026-10-01", "value": 0},
            {"keyword": keyword[3], "date": "2026-10-01", "value": 32},
        ]

    monkeypatch.setattr(fake_providers.trends, "get_trends", sparse_trends)
    with use_provider_set(fake_providers):
        result = await hosted.find_seo_opportunities(seed_keyword="seo", limit=4)

    assert len(trend_calls) == 1
    assert trend_calls[0][0] == [f"seo rising {index}" for index in range(4)]
    assert len(result.candidates) == 4
    assert all(candidate.signal_type == "rising_related_query" for candidate in result.candidates)
    assert [candidate.interest_points_observed for candidate in result.candidates] == [0, 0, 1, 1]
    assert [candidate.interest_validation_status for candidate in result.candidates] == [
        "unavailable", "unavailable", "observed", "observed"
    ]
    assert result.candidates[2].latest_interest == 0
    assert result.candidates[0].latest_interest is None
    assert any("no usable" in item for item in result.limitations)


async def test_find_seo_opportunities_adds_exact_query_gsc_annotations(
    fake_providers,
    monkeypatch,
):
    captured = {}

    async def fake_context(**kwargs):
        captured.update(kwargs)
        return {
            "project": {
                "id": "project_123",
                "name": "DigestSEO",
                "origin": "https://digestseo.com",
            },
            "gsc": {
                "available": True,
                "reason": None,
                "retryable": False,
                "message": None,
                "property": {
                    "siteUrl": "sc-domain:digestseo.com",
                    "permissionLevel": "siteOwner",
                },
                "window": {
                    "startDate": "2026-07-24",
                    "endDate": "2026-08-20",
                    "days": 28,
                },
                "metrics": [
                    {
                        "keyword": "technical seo rising 0",
                        "clicks": 12,
                        "impressions": 340,
                        "ctr": 0.035294,
                        "position": 8.4,
                        "hasData": True,
                    },
                    {
                        "keyword": "technical seo rising 1",
                        "clicks": 0,
                        "impressions": 0,
                        "ctr": 0,
                        "position": None,
                        "hasData": False,
                    },
                ],
            },
        }

    monkeypatch.setattr(hosted, "fetch_digestseo_project_context", fake_context)
    with use_provider_set(fake_providers):
        result = await hosted.find_seo_opportunities(
            seed_keyword="technical seo",
            geo="US",
            limit=2,
            project_id="project_123",
        )

    assert captured == {
        "project_id": "project_123",
        "keywords": ["technical seo rising 0", "technical seo rising 1"],
        "days": 28,
    }
    assert result.project_context is not None
    assert result.project_context.project_id == "project_123"
    assert result.project_context.origin == "https://digestseo.com"
    assert result.project_context.search_console_available is True
    assert result.project_context.property_url == "sc-domain:digestseo.com"
    assert result.project_context.days == 28

    first = result.candidates[0].search_console
    second = result.candidates[1].search_console
    assert first is not None
    assert first.clicks == 12
    assert first.impressions == 340
    assert first.position == 8.4
    assert first.has_data is True
    assert second is not None
    assert second.has_data is False
    assert second.impressions == 0
    assert any("exact-query" in limitation for limitation in result.limitations)
    assert any("not search volume" in limitation for limitation in result.limitations)


async def test_find_seo_opportunities_degrades_when_gsc_is_unavailable(
    fake_providers,
    monkeypatch,
):
    async def fake_context(**kwargs):
        return {
            "project": {
                "id": "project_123",
                "name": "Example",
                "origin": "https://example.com",
            },
            "gsc": {
                "available": False,
                "reason": "no_matching_property",
                "retryable": False,
                "message": "No Search Console property connected to this project origin.",
                "property": None,
                "window": None,
                "metrics": [],
            },
        }

    monkeypatch.setattr(hosted, "fetch_digestseo_project_context", fake_context)
    with use_provider_set(fake_providers):
        result = await hosted.find_seo_opportunities(
            seed_keyword="technical seo",
            limit=2,
            project_id="project_123",
        )

    assert result.project_context is not None
    assert result.project_context.search_console_available is False
    assert result.project_context.reason == "no_matching_property"
    assert all(candidate.search_console is None for candidate in result.candidates)
    assert any("remain trend-only" in limitation for limitation in result.limitations)


@pytest.mark.parametrize("status", [429, 502, 503, 504])
async def test_find_seo_opportunities_preserves_trends_on_transient_digestseo_error(
    fake_providers, monkeypatch, status
):
    async def failing_context(**kwargs):
        raise DigestSeoContextError("Temporary upstream failure", code="upstream_failure", status=status)

    monkeypatch.setattr(hosted, "fetch_digestseo_project_context", failing_context)
    with use_provider_set(fake_providers):
        result = await hosted.find_seo_opportunities(
            seed_keyword="technical seo", limit=2, project_id="project_123"
        )

    assert len(result.candidates) == 2
    assert all(candidate.interest_points_observed > 0 for candidate in result.candidates)
    assert all(candidate.search_console is None for candidate in result.candidates)
    assert result.project_context is not None
    assert result.project_context.project_id == "project_123"
    assert result.project_context.search_console_available is False
    assert result.project_context.retryable is True
    assert result.project_context.reason == "digestseo_temporarily_unavailable"
    assert any("remain trend-only" in limitation for limitation in result.limitations)


@pytest.mark.parametrize("status", [400, 401, 403, 404])
async def test_find_seo_opportunities_does_not_hide_digestseo_client_errors(
    fake_providers, monkeypatch, status
):
    error = DigestSeoContextError("Permission or request failure", status=status)

    async def failing_context(**kwargs):
        raise error

    monkeypatch.setattr(hosted, "fetch_digestseo_project_context", failing_context)
    with use_provider_set(fake_providers), pytest.raises(DigestSeoContextError) as caught:
        await hosted.find_seo_opportunities(seed_keyword="technical seo", project_id="project_123")
    assert caught.value is error


def test_hosted_interest_metrics_and_bounded_series_use_observation_time_not_provider_order():
    # These two instants cross offsets; lexical timestamp order is not UTC order.
    points = [
        {"date": "2026-11-01T01:15:00+00:00", "value": 20},
        {"date": "2026-11-01T01:30:00+01:00", "value": 80},
        {"date": "not-a-timestamp", "value": 99},
        {"date": "2026-10-31", "value": 10},
    ]

    metrics = hosted._interest_metrics(points)
    series = hosted._bounded_series(points, max_points=3)

    assert metrics.latest == 20
    assert metrics.average == 36.67
    assert metrics.peak == 80
    assert metrics.points_observed == 3
    assert [(item.date, item.value) for item in series] == [
        ("2026-10-31", 10),
        ("2026-11-01T01:30:00+01:00", 80),
        ("2026-11-01T01:15:00+00:00", 20),
    ]
    assert hosted._bounded_series(points, max_points=1)[0].value == 20
