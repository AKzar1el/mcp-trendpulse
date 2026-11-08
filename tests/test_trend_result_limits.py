"""Offline bounds for community ranked/top Trends tools and direct providers."""

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
