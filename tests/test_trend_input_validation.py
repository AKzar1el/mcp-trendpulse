from unittest.mock import patch

import pytest
from fastmcp import Client

from mcp_trendpulse import news, server


@pytest.mark.asyncio
async def test_get_trends_rejects_unsupported_source_before_provider_call():
    with patch.object(news.tr, "interest_over_time") as request:
        with pytest.raises(ValueError, match="Unsupported search source"):
            await news.get_trends("python", source="web search")
    request.assert_not_called()


@pytest.mark.asyncio
async def test_get_trends_rejects_unsupported_legacy_data_mode_before_provider_call():
    with patch.object(news.tr, "interest_over_time") as request:
        with pytest.raises(ValueError, match="Unsupported data_mode"):
            await news.get_trends("python", data_mode="hourly")
    request.assert_not_called()


@pytest.mark.asyncio
async def test_get_growth_rejects_unsupported_source_before_provider_call():
    with patch.object(news.tr, "interest_over_time") as request:
        with pytest.raises(ValueError, match="Unsupported search source"):
            await news.get_growth("python", source="web search")
    request.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", [news.get_trends, news.get_growth])
async def test_trends_comparison_rejects_keyword_counts_outside_provider_limit(tool):
    with patch.object(news.tr, "interest_over_time") as request:
        with pytest.raises(ValueError, match="between 1 and 5 keywords"):
            await tool([])
        with pytest.raises(ValueError, match="between 1 and 5 keywords"):
            await tool(["one", "two", "three", "four", "five", "six"])

    request.assert_not_called()


@pytest.mark.asyncio
async def test_interest_by_region_rejects_keyword_counts_outside_provider_limit():
    with patch.object(news.tr, "interest_by_region") as request:
        with pytest.raises(ValueError, match="between 1 and 5 keywords"):
            await news.get_interest_by_region([])
        with pytest.raises(ValueError, match="between 1 and 5 keywords"):
            await news.get_interest_by_region(["one", "two", "three", "four", "five", "six"])

    request.assert_not_called()


@pytest.mark.asyncio
async def test_ranked_trends_rejects_unsupported_source_and_sort_before_provider_call():
    with patch.object(news.tr, "trending_now") as request:
        with pytest.raises(ValueError, match="supports only source"):
            await news.get_ranked_trends(source="youtube search")
        with pytest.raises(ValueError, match="Unsupported sort"):
            await news.get_ranked_trends(sort="recent")
    request.assert_not_called()


@pytest.mark.asyncio
async def test_top_trends_rejects_unknown_feed_before_provider_call():
    with patch.object(news.tr, "trending_now_by_rss") as realtime, patch.object(
        news.tr, "daily_trends_deprecated_by_rss"
    ) as daily:
        with pytest.raises(ValueError, match="Unsupported trend type"):
            await news.get_top_trends(type="hourly")
    realtime.assert_not_called()
    daily.assert_not_called()


@pytest.mark.asyncio
async def test_region_and_related_tools_reject_invalid_filters_before_provider_call():
    with patch.object(news.tr, "interest_by_region") as region_request:
        with pytest.raises(ValueError, match="Unsupported region resolution"):
            await news.get_interest_by_region("python", resolution="bad")
        with pytest.raises(ValueError, match="Unsupported Google property"):
            await news.get_interest_by_region("python", gprop="bogus")
    region_request.assert_not_called()

    with patch.object(news.tr, "related_queries") as query_request:
        with pytest.raises(ValueError, match="Unsupported Google property"):
            await news.get_related_queries("python", gprop="bogus")
    query_request.assert_not_called()

    with patch.object(news.tr, "related_topics") as topic_request:
        with pytest.raises(ValueError, match="Unsupported Google property"):
            await news.get_related_topics("python", gprop="bogus")
    topic_request.assert_not_called()


@pytest.mark.asyncio
async def test_region_filters_normalize_supported_direct_provider_values():
    with patch.object(news.tr, "interest_by_region") as request:
        request.return_value.empty = True
        await news.get_interest_by_region("python", gprop=" YouTube ", resolution=" region ")

    request.assert_called_once()
    assert request.call_args.kwargs["gprop"] == "youtube"
    assert request.call_args.kwargs["resolution"] == "REGION"


@pytest.mark.asyncio
async def test_tool_schemas_expose_supported_value_enums():
    async with Client(server.mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    assert tools["get_trends"].inputSchema["properties"]["source"]["enum"] == [
        "google search",
        "youtube search",
        "news search",
        "image search",
        "google shopping",
    ]
    assert tools["get_trends"].inputSchema["properties"]["data_mode"]["enum"] == [
        "weekly",
        "daily",
        "monthly",
    ]
    assert tools["get_ranked_trends"].inputSchema["properties"]["sort"]["enum"] == [
        "wow_pct_change",
        "volume",
    ]
    assert tools["get_top_trends"].inputSchema["properties"]["type"]["enum"] == [
        "Google Trends",
        "Daily Trends",
    ]

    assert tools["get_interest_by_region"].inputSchema["properties"]["gprop"]["enum"] == [
        "",
        "youtube",
        "news",
        "images",
        "froogle",
    ]
    assert tools["get_interest_by_region"].inputSchema["properties"]["resolution"]["enum"] == [
        "COUNTRY",
        "REGION",
        "CITY",
        "DMA",
    ]
    for tool_name in ("get_related_queries", "get_related_topics"):
        assert tools[tool_name].inputSchema["properties"]["gprop"]["enum"] == [
            "",
            "youtube",
            "news",
            "images",
            "froogle",
        ]


@pytest.mark.asyncio
async def test_trends_tool_schemas_expose_provider_keyword_count_limit():
    async with Client(server.mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    for tool_name in ("get_trends", "get_growth"):
        keyword_schema = tools[tool_name].inputSchema["properties"]["keyword"]
        list_schema = next(option for option in keyword_schema["anyOf"] if option.get("type") == "array")
        assert list_schema["minItems"] == 1
        assert list_schema["maxItems"] == 5

    region_schema = tools["get_interest_by_region"].inputSchema["properties"]["keywords"]
    region_list_schema = next(option for option in region_schema["anyOf"] if option.get("type") == "array")
    assert region_list_schema["minItems"] == 1
    assert region_list_schema["maxItems"] == 5
