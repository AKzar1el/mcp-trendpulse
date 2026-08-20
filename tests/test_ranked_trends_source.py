import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from mcp_trendpulse import news, server


async def test_ranked_trends_accepts_google_search():
    with patch.object(news.tr, "trending_now", return_value=[]) as trending_now:
        results = await news.get_ranked_trends(source="google search")

    assert results == []
    trending_now.assert_called_once_with(geo="US", hours=24)


@pytest.mark.parametrize("source", ["youtube search", "arbitrary"])
async def test_ranked_trends_provider_rejects_unsupported_source(source: str):
    trending_now = Mock()

    with patch.object(news.tr, "trending_now", trending_now):
        with pytest.raises(ValueError, match="only supports source='google search'"):
            await news.get_ranked_trends(source=source)  # type: ignore[arg-type]

    trending_now.assert_not_called()


async def test_ranked_trends_tool_schema_allows_only_google_search():
    async with Client(server.mcp) as client:
        tools = {tool.name: tool.inputSchema for tool in await client.list_tools()}

    source_schema = tools["get_ranked_trends"]["properties"]["source"]
    assert source_schema["const"] == "google search"

    for filename in ("server.json", "manifest.json"):
        registry = json.loads((Path(__file__).parents[1] / filename).read_text())
        static_schema = next(
            tool["inputSchema"]["properties"]["source"]
            for tool in registry["tools"]
            if tool["name"] == "get_ranked_trends"
        )
        assert static_schema["const"] == "google search"
        assert static_schema["description"] == source_schema["description"]


async def test_ranked_trends_tool_rejects_unsupported_source_before_provider_work():
    provider = AsyncMock()

    with patch.object(server.news, "get_ranked_trends", provider):
        async with Client(server.mcp) as client:
            with pytest.raises(ToolError, match="google search"):
                await client.call_tool("get_ranked_trends", {"source": "youtube search"})

    provider.assert_not_awaited()
