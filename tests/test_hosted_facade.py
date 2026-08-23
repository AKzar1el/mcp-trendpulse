from types import SimpleNamespace

import pytest
from fastmcp import Client

from mcp_trendpulse import hosted, server
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

    async def get_news_by_keyword(self, keyword, period=7, max_results=10, **kwargs):
        return [
            SimpleNamespace(
                title=f"{keyword} article {index}",
                original_url=f"https://example.com/{index}",
                publish_date="2026-08-23",
                meta_site_name="Example News",
            )
            for index in range(max_results + 3)
        ]


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


async def test_discover_trends_is_bounded_and_preserves_provider_metadata(fake_providers):
    with use_provider_set(fake_providers):
        result = await hosted.discover_trends(geo="US", sort_by="growth", limit=3)

    assert result.provider == "fake_trends"
    assert result.geo == "US"
    assert result.sorted_by == "growth"
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


async def test_compare_rejects_duplicate_keywords(fake_providers):
    with use_provider_set(fake_providers), pytest.raises(ValueError, match="unique"):
        await hosted.compare_keyword_trends(
            keywords=["same", "same"],
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


async def test_trend_context_combines_trend_and_news_provider_metadata(fake_providers):
    with use_provider_set(fake_providers):
        result = await hosted.get_trend_context(
            keyword="AI search",
            geo="US",
            max_articles=2,
        )

    assert result.trends_provider == "fake_trends"
    assert result.news_provider == "fake_news"
    assert result.metrics.points_observed == 30
    assert len(result.recent_articles) == 2
    assert result.recent_articles[0].source == "Example News"
    assert result.recent_articles[0].url == "https://example.com/0"


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
