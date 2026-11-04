from unittest.mock import patch

import pytest
from click.testing import CliRunner
from fastmcp import Client

from mcp_trendpulse import cli as cli_module
from mcp_trendpulse import news, server
from mcp_trendpulse.config import GOOGLE_NEWS_MAX_RESULTS


@pytest.mark.parametrize("max_results", [0, 101, 1000])
def test_news_factory_rejects_out_of_range_before_upstream_client(max_results):
    with patch.object(news, "_DeferredUrlGNews") as client_factory:
        with pytest.raises(ValueError, match="between 1 and 100"):
            news._new_google_news(period=7, max_results=max_results)
    client_factory.assert_not_called()


@pytest.mark.parametrize("max_results", [1, 100])
def test_news_factory_preserves_period_at_valid_boundaries(max_results):
    with patch.object(news, "_DeferredUrlGNews") as client_factory:
        client = news._new_google_news(period=7, max_results=max_results)
    assert client is client_factory.return_value
    assert client.period == "7d"
    assert client.max_results == max_results


async def test_news_mcp_schemas_expose_the_provider_safe_limit():
    async with Client(server.mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}

    assert GOOGLE_NEWS_MAX_RESULTS == 100
    for name in (
        "get_news_by_keyword",
        "get_news_by_location",
        "get_news_by_topic",
        "get_top_news",
        "get_news_by_site",
    ):
        limits = tools[name].inputSchema["properties"]["max_results"]
        assert limits["minimum"] == 1
        assert limits["maximum"] == GOOGLE_NEWS_MAX_RESULTS


@pytest.mark.parametrize(
    "command",
    [
        ("keyword", "ai"),
        ("location", "Ljubljana"),
        ("topic", "TECHNOLOGY"),
        ("top",),
        ("site", "example.com"),
    ],
)
@pytest.mark.parametrize("max_results", [0, 101])
def test_news_cli_rejects_out_of_range_without_provider_calls(command, max_results):
    with patch.object(cli_module, "get_provider_set") as provider:
        result = CliRunner().invoke(
            cli_module.cli,
            [*command, "--max-results", str(max_results), "--headlines-only"],
        )
    assert result.exit_code == 2
    assert "Invalid value for '--max-results'" in result.output
    provider.assert_not_called()
