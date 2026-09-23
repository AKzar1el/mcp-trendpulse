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


class FakeBriefTrendsProvider:
    async def get_trends(self, **kwargs):
        geo = kwargs["geo"]
        base = 80 if geo == "US" else 60
        return [
            {"date": "2026-09-06", "value": base, "keyword": "ChatGPT"},
            {"date": "2026-09-06", "value": base // 2, "keyword": "Claude"},
        ]

    async def get_growth(self, **kwargs):
        return [
            {"keyword": "ChatGPT", "growth": {"3M": 5.0, "1Y": -1.25}},
            {"keyword": "Claude", "growth": {"3M": -15.5, "1Y": 300.0}},
        ]


class FakeBriefProviders:
    trends = FakeBriefTrendsProvider()


def test_brief_pack_emits_two_market_evidence_tables():
    runner = CliRunner()
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=FakeBriefProviders()):
        result = runner.invoke(
            cli_module.cli,
            [
                "brief-pack",
                "--keyword", "ChatGPT",
                "--keyword", "Claude",
                "--market", "US",
                "--market", "GB",
            ],
        )

    assert result.exit_code == 0
    assert "# TrendPulse Demand Brief evidence pack" in result.output
    assert "Google Trends property: **Google Search**" in result.output
    assert "Data source: **Google Trends** (https://trends.google.com/trends/)" in result.output
    assert result.output.count("Latest complete Trends point: **2026-09-06**") == 2
    assert "## US" in result.output
    assert "## GB" in result.output
    assert "| ChatGPT | 80 | +5.00% | -1.25% |" in result.output
    assert "| Claude | 30 | -15.50% | +300.00% |" in result.output
    assert "do not compare index values directly across markets" in result.output


def test_brief_pack_enforces_offer_keyword_and_market_limits():
    runner = CliRunner()
    too_many_keywords = [item for value in ["a", "b", "c", "d", "e", "f"] for item in ("--keyword", value)]
    result = runner.invoke(cli_module.cli, ["brief-pack", *too_many_keywords, "--market", "US"])
    assert result.exit_code == 2
    assert "one and five" in result.output

    result = runner.invoke(
        cli_module.cli,
        ["brief-pack", "--keyword", "AI", "--market", "US", "--market", "GB", "--market", "DE"],
    )
    assert result.exit_code == 2
    assert "one or two" in result.output
