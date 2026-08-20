import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from mcp_trendpulse import server


ARTICLE_TOOL_NAMES = (
    "get_news_by_keyword",
    "get_news_by_location",
    "get_news_by_topic",
    "get_top_news",
    "get_news_by_site",
)
TREND_TOOL_NAMES = ("get_ranked_trends", "get_top_trends")


def _static_tool_schemas(filename: str) -> dict[str, dict]:
    path = Path(__file__).parents[1] / filename
    return {tool["name"]: tool["inputSchema"] for tool in json.loads(path.read_text())["tools"]}


async def test_result_count_bounds_are_exposed_in_runtime_and_registry_schemas():
    async with Client(server.mcp) as client:
        runtime_schemas = {tool.name: tool.inputSchema for tool in await client.list_tools()}

    for schemas in (
        runtime_schemas,
        _static_tool_schemas("server.json"),
        _static_tool_schemas("manifest.json"),
    ):
        for tool_name in ARTICLE_TOOL_NAMES:
            assert schemas[tool_name]["properties"]["max_results"]["maximum"] == 20
        for tool_name in TREND_TOOL_NAMES:
            assert schemas[tool_name]["properties"]["limit"]["maximum"] == 100


async def test_article_result_count_maximum_and_default_are_accepted():
    provider = AsyncMock(return_value=[])

    with patch.object(server.news, "get_news_by_keyword", provider):
        async with Client(server.mcp) as client:
            await client.call_tool(
                "get_news_by_keyword",
                {"keyword": "python", "max_results": 20},
            )
            await client.call_tool("get_news_by_keyword", {"keyword": "python"})

    assert provider.await_args_list[0].kwargs["max_results"] == 20
    assert provider.await_args_list[1].kwargs["max_results"] == 10


async def test_trend_result_count_maximum_and_default_are_accepted():
    provider = AsyncMock(return_value=[])

    with patch.object(server.news, "get_ranked_trends", provider):
        async with Client(server.mcp) as client:
            await client.call_tool("get_ranked_trends", {"limit": 100})
            await client.call_tool("get_ranked_trends", {})

    assert provider.await_args_list[0].kwargs["limit"] == 100
    assert provider.await_args_list[1].kwargs["limit"] == 20


@pytest.mark.parametrize(
    ("tool_name", "arguments", "provider_name", "message"),
    [
        (
            "get_news_by_keyword",
            {"keyword": "python", "max_results": 21},
            "get_news_by_keyword",
            "less than or equal to 20",
        ),
        (
            "get_ranked_trends",
            {"limit": 101},
            "get_ranked_trends",
            "less than or equal to 100",
        ),
    ],
)
async def test_result_count_above_maximum_is_rejected_before_provider_work(
    tool_name: str,
    arguments: dict[str, int | str],
    provider_name: str,
    message: str,
):
    provider = AsyncMock()

    with patch.object(server.news, provider_name, provider):
        async with Client(server.mcp) as client:
            with pytest.raises(ToolError, match=message):
                await client.call_tool(tool_name, arguments)

    provider.assert_not_awaited()


async def test_existing_normal_result_count_calls_remain_unchanged():
    article_provider = AsyncMock(return_value=[])
    trend_provider = AsyncMock(return_value=[])

    with (
        patch.object(server.news, "get_news_by_keyword", article_provider),
        patch.object(server.news, "get_top_trends", trend_provider),
    ):
        async with Client(server.mcp) as client:
            await client.call_tool(
                "get_news_by_keyword",
                {"keyword": "python", "max_results": 2},
            )
            await client.call_tool("get_top_trends", {"limit": 5})

    assert article_provider.await_args.kwargs["max_results"] == 2
    assert trend_provider.await_args.kwargs["limit"] == 5
