"""Offline bounds for community ranked/top Trends tools and direct providers."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastmcp import Client

from mcp_trendpulse import news, server
from mcp_trendpulse.config import GOOGLE_TRENDS_MAX_RESULTS


@pytest.mark.asyncio
@pytest.mark.parametrize("fetch", [news.get_ranked_trends, news.get_top_trends])
@pytest.mark.parametrize("limit", [-1, 0, 101, 100000])
async def test_invalid_trend_result_limit_is_rejected_before_provider_call(
    monkeypatch, fetch, limit
):
    upstream = AsyncMock(side_effect=AssertionError("provider must not be called"))
    monkeypatch.setattr(news, "_call_trends_async", upstream)
    with pytest.raises(ValueError, match="between 1 and 100"):
        await fetch(limit=limit)
    upstream.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("fetch", [news.get_ranked_trends, news.get_top_trends])
@pytest.mark.parametrize("limit", [1, 20, 100])
async def test_valid_trend_result_limits_bound_offline_feed(monkeypatch, fetch, limit):
    feed = [
        SimpleNamespace(
            keyword=f"trend-{i}",
            volume=i,
            volume_growth_pct=float(i),
            started_timestamp=[],
            news=[],
            link=None,
            started=None,
            picture=None,
        )
        for i in range(150)
    ]
    upstream = AsyncMock(return_value=feed)
    monkeypatch.setattr(news, "_call_trends_async", upstream)
    result = await fetch(limit=limit)
    assert len(result) == limit
    upstream.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("fetch", [news.get_ranked_trends, news.get_top_trends])
async def test_trending_feed_ignores_malformed_rows_before_result_limit(monkeypatch, fetch):
    valid = SimpleNamespace(
        keyword="  useful trend  ",
        volume=250,
        volume_growth_pct=50,
        started_timestamp=[],
        news=[],
        link=None,
        started=None,
        picture=None,
    )
    feed = [
        None,
        SimpleNamespace(volume=999, volume_growth_pct=99, news=[]),
        SimpleNamespace(keyword=42, volume=999, volume_growth_pct=99, news=[]),
        valid,
    ]
    upstream = AsyncMock(return_value=feed)
    monkeypatch.setattr(news, "_call_trends_async", upstream)

    result = await fetch(limit=1)

    assert len(result) == 1
    assert result[0]["keyword"] == "useful trend"
    upstream.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("fetch", [news.get_ranked_trends, news.get_top_trends])
@pytest.mark.parametrize("blank_keyword", ["&nbsp;", " &#160; ", "&#xA0;", "&#9;", "&#10;"])
async def test_trending_feeds_skip_entity_decoded_blank_keywords_before_limit(
    monkeypatch, fetch, blank_keyword
):
    blank = SimpleNamespace(keyword=blank_keyword, volume=9999, volume_growth_pct=9999)
    valid = SimpleNamespace(keyword=" Useful &amp; safe ", volume=50,
                            volume_growth_pct=50, started_timestamp=[], news=[])
    upstream = AsyncMock(return_value=[blank, valid])
    monkeypatch.setattr(news, "_call_trends_async", upstream)

    result = await fetch(limit=1)

    assert [item["keyword"] for item in result] == ["Useful & safe"]
    assert blank.keyword == blank_keyword
    assert valid.keyword == " Useful &amp; safe "
    upstream.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("fetch", [news.get_ranked_trends, news.get_top_trends])
@pytest.mark.parametrize("payload", [None, 42, "not a feed", {"keyword": "invalid root"}])
async def test_trending_feeds_ignore_nonsequence_provider_payload(monkeypatch, fetch, payload):
    upstream = AsyncMock(return_value=payload)
    monkeypatch.setattr(news, "_call_trends_async", upstream)

    assert await fetch(limit=5) == []
    upstream.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("fetch", [news.get_ranked_trends, news.get_top_trends])
async def test_trending_feeds_isolate_malformed_nested_news(monkeypatch, fetch):
    article = SimpleNamespace(
        title="Valid &amp; useful",
        url="https://example.com/story",
        source="Example &amp; News",
        picture=None,
        time=None,
        snippet="A &amp; B",
    )
    trend = SimpleNamespace(
        keyword="useful trend",
        volume=100,
        volume_growth_pct=25,
        started_timestamp=[],
        started=None,
        link=None,
        picture=None,
        news=[
            None,
            SimpleNamespace(url="https://example.com/no-title"),
            SimpleNamespace(title="Missing URL"),
            article,
        ],
    )
    monkeypatch.setattr(news, "_call_trends_async", AsyncMock(return_value=[trend]))

    result = await fetch(limit=1)

    assert result[0]["news"] == [
        {
            "title": "Valid & useful",
            "url": "https://example.com/story",
            "source": "Example & News",
            "picture": None,
            "time": None,
            "snippet": "A & B",
        }
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("fetch", [news.get_ranked_trends, news.get_top_trends])
@pytest.mark.parametrize("blank_title", ["&nbsp;", " &#160; ", "&#x2003;", "&#9;", "&#10;"])
async def test_trending_feeds_skip_news_titles_blank_after_entity_decoding(
    monkeypatch, fetch, blank_title
):
    blank = SimpleNamespace(title=blank_title, url="https://example.com/blank")
    valid = SimpleNamespace(title="Useful &amp; verified", url="https://example.com/valid")
    trend = SimpleNamespace(
        keyword="useful trend", volume=100, volume_growth_pct=25,
        started_timestamp=[], started=None, link=None, picture=None,
        news=[blank, valid],
    )
    monkeypatch.setattr(news, "_call_trends_async", AsyncMock(return_value=[trend]))

    result = await fetch(limit=1)

    assert len(result) == 1
    assert result[0]["news"] == [
        {"title": "Useful & verified", "url": "https://example.com/valid",
         "source": None, "picture": None, "time": None, "snippet": None}
    ]
    assert blank.title == blank_title
    assert valid.title == "Useful &amp; verified"


@pytest.mark.asyncio
@pytest.mark.parametrize("fetch", [news.get_ranked_trends, news.get_top_trends])
@pytest.mark.parametrize(
    "unsafe_url",
    [
        "javascript:alert(1)",
        "data:text/html,unsafe",
        "ftp://example.com/story",
        "//example.com/story",
        "https://user:password@example.com/story",
        "https://[invalid/story",
    ],
)
async def test_trending_feeds_ignore_unsafe_provider_news_urls(monkeypatch, fetch, unsafe_url):
    def article(url):
        return SimpleNamespace(title="Article", url=url, source="Publisher", picture=None,
                               time=None, snippet="Snippet")

    trend = SimpleNamespace(
        keyword="useful trend", volume=100, volume_growth_pct=25,
        started_timestamp=[], started=None, link="https://trends.google.com/trending",
        picture=None, news=[article(unsafe_url), article("https://example.com/story")],
    )
    monkeypatch.setattr(news, "_call_trends_async", AsyncMock(return_value=[trend]))

    result = await fetch(limit=1)

    assert [item["url"] for item in result[0]["news"]] == ["https://example.com/story"]


@pytest.mark.asyncio
@pytest.mark.parametrize("fetch", [news.get_ranked_trends, news.get_top_trends])
@pytest.mark.parametrize(
    ("picture", "expected"),
    [
        ("javascript:alert(1)", None),
        ("data:image/png;base64,AA", None),
        ("//example.com/photo.png", None),
        ("https://user:pass@example.com/photo.png", None),
        ("https://[invalid/photo.png", None),
        ("https://example.com/photo.png", "https://example.com/photo.png"),
    ],
)
async def test_trending_feeds_validate_optional_article_pictures(monkeypatch, fetch, picture, expected):
    article = SimpleNamespace(title="Story", url="https://example.com/story", picture=picture)
    trend = SimpleNamespace(keyword="topic", volume=100, volume_growth_pct=5,
                            started_timestamp=[], started=None, link=None,
                            picture=None, news=[article])
    monkeypatch.setattr(news, "_call_trends_async", AsyncMock(return_value=[trend]))

    result = await fetch(limit=1)

    assert result[0]["news"][0]["picture"] == expected
    assert article.picture == picture


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("picture", "expected"),
    [
        ("javascript:alert(1)", None),
        ("data:image/svg+xml,unsafe", None),
        ("https://user:pass@example.com/photo.png", None),
        ("https://example.com/photo.png", "https://example.com/photo.png"),
    ],
)
async def test_top_trends_validates_optional_trend_pictures(monkeypatch, picture, expected):
    trend = SimpleNamespace(keyword="topic", volume=100, started=None,
                            started_timestamp=[], link=None, picture=picture, news=[])
    monkeypatch.setattr(news, "_call_trends_async", AsyncMock(return_value=[trend]))

    result = await news.get_top_trends(limit=1)

    assert result[0]["picture"] == expected
    assert trend.picture == picture


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("link", "expected"),
    [
        ("javascript:alert(1)", None),
        ("//example.com/story", None),
        ("https://user:password@example.com/story", None),
        ("https://[invalid/story", None),
        ("http://example.com/trend", "http://example.com/trend"),
        ("https://trends.google.com/trending", "https://trends.google.com/trending"),
    ],
)
async def test_top_trends_exposes_only_http_provider_links(monkeypatch, link, expected):
    trend = SimpleNamespace(keyword="trend", volume=100, started=None,
                            started_timestamp=[], link=link, picture=None, news=[])
    monkeypatch.setattr(news, "_call_trends_async", AsyncMock(return_value=[trend]))

    result = await news.get_top_trends(limit=1)

    assert result[0]["link"] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("fetch", [news.get_ranked_trends, news.get_top_trends])
async def test_trending_feeds_ignore_noniterable_optional_news(monkeypatch, fetch):
    trend = SimpleNamespace(
        keyword="useful trend", volume=100, volume_growth_pct=25,
        started_timestamp=[], started=None, link=None, picture=None, news=42,
    )
    monkeypatch.setattr(news, "_call_trends_async", AsyncMock(return_value=[trend]))

    result = await fetch(limit=1)

    assert result[0]["keyword"] == "useful trend"
    assert result[0]["news"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("fetch", [news.get_ranked_trends, news.get_top_trends])
@pytest.mark.parametrize(
    ("started_timestamp", "expected"),
    [
        ("2026-11-08T12:00:00Z", "2026-11-08T12:00:00Z"),
        (1762603200, 1762603200),
        (["2026-11-08T12:00:00Z"], "2026-11-08T12:00:00Z"),
        (("2026-11-08T12:00:00Z",), "2026-11-08T12:00:00Z"),
        (datetime(2026, 11, 8, 12, tzinfo=timezone.utc), datetime(2026, 11, 8, 12, tzinfo=timezone.utc)),
        ([], None),
        ({"unexpected": "mapping"}, None),
        (True, None),
        (float("nan"), None),
        ("   ", None),
    ],
)
async def test_trending_feeds_normalize_started_timestamp_shapes(
    monkeypatch, fetch, started_timestamp, expected
):
    trend = SimpleNamespace(
        keyword="useful trend", volume=100, volume_growth_pct=25,
        started_timestamp=started_timestamp, started=None,
        link=None, picture=None, news=[],
    )
    monkeypatch.setattr(news, "_call_trends_async", AsyncMock(return_value=[trend]))

    result = await fetch(limit=1)

    assert result[0]["started"] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "started",
    [[], {}, True, float("nan"), "  ", object()],
)
async def test_top_trends_rejects_malformed_started_and_uses_timestamp_fallback(
    monkeypatch, started
):
    trend = SimpleNamespace(
        keyword="useful trend", volume=100, started=started,
        started_timestamp=["2026-11-08T12:00:00Z"], link=None,
        picture=None, news=[],
    )
    monkeypatch.setattr(news, "_call_trends_async", AsyncMock(return_value=[trend]))

    result = await news.get_top_trends(limit=1)

    assert result[0]["started"] == "2026-11-08T12:00:00Z"
    assert trend.started is started


@pytest.mark.asyncio
async def test_top_trends_keeps_valid_started_over_timestamp_fallback(monkeypatch):
    trend = SimpleNamespace(
        keyword="useful trend", volume=100,
        started="2026-11-09T12:00:00Z",
        started_timestamp="2026-11-08T12:00:00Z",
        link=None, picture=None, news=[],
    )
    monkeypatch.setattr(news, "_call_trends_async", AsyncMock(return_value=[trend]))

    result = await news.get_top_trends(limit=1)

    assert result[0]["started"] == "2026-11-09T12:00:00Z"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("sort", "expected"),
    [
        ("recent_growth_pct", ["good", "string", "declining"]),
        ("volume", ["string", "good", "declining"]),
    ],
)
async def test_ranked_trends_normalizes_provider_metrics_and_sorts_missing_last(
    monkeypatch, sort, expected
):
    def trend(keyword, growth, volume):
        return SimpleNamespace(
            keyword=keyword,
            volume_growth_pct=growth,
            volume=volume,
            started_timestamp=[],
            news=[],
        )

    feed = [
        trend("nan", float("nan"), float("nan")),
        trend("declining", -25, 0),
        trend("boolean", True, False),
        trend("string", "12.5", "250"),
        trend("inf", float("inf"), "100K+"),
        trend("good", 50, 100),
    ]
    monkeypatch.setattr(news, "_call_trends_async", AsyncMock(return_value=feed))

    result = await news.get_ranked_trends(sort=sort)

    assert [item["keyword"] for item in result[:3]] == expected
    assert [item["keyword"] for item in result[3:]] == ["nan", "boolean", "inf"]
    by_keyword = {item["keyword"]: item for item in result}
    assert by_keyword["string"]["growth_pct"] == 12.5
    assert by_keyword["string"]["volume"] == 250
    assert by_keyword["declining"]["growth_pct"] == -25.0
    assert by_keyword["declining"]["volume"] == 0
    for keyword in ("nan", "boolean", "inf"):
        assert by_keyword[keyword]["growth_pct"] is None
        assert by_keyword[keyword]["volume"] is None


@pytest.mark.asyncio
async def test_community_trend_mcp_schemas_expose_shared_limit():
    async with Client(server.mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    assert GOOGLE_TRENDS_MAX_RESULTS == 100
    for name in ("get_ranked_trends", "get_top_trends"):
        limits = tools[name].inputSchema["properties"]["limit"]
        assert limits["minimum"] == 1
        assert limits["maximum"] == GOOGLE_TRENDS_MAX_RESULTS
