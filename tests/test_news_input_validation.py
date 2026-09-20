from unittest.mock import patch

import pytest
from fastmcp import Client

from mcp_trendpulse import news, server


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool", "argument"),
    [
        (news.get_news_by_keyword, "keyword"),
        (news.get_news_by_location, "location"),
        (news.get_news_by_topic, "topic"),
        (news.get_news_by_site, "site"),
    ],
)
async def test_news_lookup_tools_reject_blank_input_before_provider_call(tool, argument):
    with patch.object(news, "_new_google_news") as provider_factory:
        with pytest.raises(ValueError, match="must not be empty"):
            await tool(**{argument: "   "}, period=1, max_results=1, nlp=False)

    provider_factory.assert_not_called()


@pytest.mark.asyncio
async def test_news_tool_schemas_require_nonblank_lookup_text():
    async with Client(server.mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    for tool_name, field_name in (
        ("get_news_by_keyword", "keyword"),
        ("get_news_by_location", "location"),
        ("get_news_by_topic", "topic"),
        ("get_news_by_site", "site"),
    ):
        schema = tools[tool_name].inputSchema["properties"][field_name]
        assert schema["minLength"] == 1
        assert schema["pattern"] == r".*\S.*"
