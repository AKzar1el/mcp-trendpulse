from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from mcp_trendpulse import cli as cli_module


class NoopBrowserManager:
    def __call__(self, function):
        return function


class MockArticle:
    title = "CLI article"
    original_url = "https://example.com/article"
    authors = ["CLI author"]
    publish_date = "2026-08-20"
    top_image = "https://example.com/image.jpg"
    summary = "CLI summary"


def test_keyword_command_emits_article_fields_and_result_count():
    runner = CliRunner()
    article = MockArticle()
    with (
        patch("mcp_trendpulse.cli.BrowserManager", return_value=NoopBrowserManager()),
        patch("mcp_trendpulse.cli.get_news_by_keyword", new=AsyncMock(return_value=[article])) as get_news,
        patch("mcp_trendpulse.cli.save_article_to_json") as save_article,
    ):
        result = runner.invoke(cli_module.cli, ["keyword", "python", "--no-nlp"])

    assert result.exit_code == 0
    assert "Title: CLI article" in result.output
    assert "URL: https://example.com/article" in result.output
    assert "Authors: ['CLI author']" in result.output
    assert "Summary: CLI summary" in result.output
    assert "Found 1 articles for keyword 'python'." in result.output
    get_news.assert_awaited_once_with("python", period=7, max_results=10, nlp=False)
    save_article.assert_called_once_with(article)


def test_trending_command_emits_results():
    runner = CliRunner()
    with patch(
        "mcp_trendpulse.cli.get_trending_terms",
        new=AsyncMock(return_value=[{"keyword": "AI", "volume": "1M"}]),
    ) as get_trending_terms:
        result = runner.invoke(cli_module.cli, ["trending", "--geo", "GB"])

    assert result.exit_code == 0
    assert "Trending terms:" in result.output
    assert "AI" in result.output
    assert "1M" in result.output
    get_trending_terms.assert_awaited_once_with(geo="GB", full_data=False)


def test_trending_command_emits_no_results_message():
    runner = CliRunner()
    with patch("mcp_trendpulse.cli.get_trending_terms", new=AsyncMock(return_value=[])):
        result = runner.invoke(cli_module.cli, ["trending"])

    assert result.exit_code == 0
    assert result.output == "No trending terms found.\n"
