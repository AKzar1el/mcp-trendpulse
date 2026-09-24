import io
import sys
from datetime import date, timedelta
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


def test_trending_command_uses_utf8_when_stdout_is_redirected(monkeypatch):
    raw_output = io.BytesIO()
    redirected_stdout = io.TextIOWrapper(raw_output, encoding="cp1250", errors="strict")
    monkeypatch.setattr(sys, "stdout", redirected_stdout)

    with patch(
        "mcp_trendpulse.cli.get_trending_terms",
        new=AsyncMock(return_value=[{"keyword": "한국", "volume": "1K+"}]),
    ):
        cli_module.cli.main(args=["trending", "--geo", "US"], standalone_mode=False)

    redirected_stdout.flush()
    assert "한국" in raw_output.getvalue().decode("utf-8")


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
        start = date(2025, 9, 14)
        points = []
        for week in range(53):
            current_period = week >= 49
            point_date = (start + timedelta(weeks=week)).isoformat()
            points.extend(
                [
                    {
                        "date": point_date,
                        "value": base if current_period else base / 2,
                        "keyword": "ChatGPT",
                    },
                    {"date": point_date, "value": base // 2, "keyword": "Claude"},
                ]
            )
        return points

    async def get_growth(self, **kwargs):
        return [
            {"keyword": "ChatGPT", "growth": {"3M": 5.0, "1Y": -1.25}},
            {"keyword": "Claude", "growth": {"3M": -15.5, "1Y": 300.0}},
        ]


class FakeBriefProviders:
    def __init__(self):
        self.trends = FakeBriefTrendsProvider()


def test_brief_pack_emits_two_market_evidence_tables():
    runner = CliRunner()
    providers = FakeBriefProviders()
    providers.trends.get_growth = AsyncMock(side_effect=AssertionError("default brief pack should reuse trend points"))
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
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
    assert result.output.count("Latest complete Trends point: **2026-09-13**") == 2
    assert "## US" in result.output
    assert "## GB" in result.output
    assert "| ChatGPT | 80 | +100.00% | +100.00% |" in result.output
    assert "| Claude | 40 | +0.00% | +0.00% |" in result.output
    assert "| ChatGPT | 60 | +100.00% | +100.00% |" in result.output
    assert "| Claude | 30 | +0.00% | +0.00% |" in result.output
    assert "do not compare index values directly across markets" in result.output
    providers.trends.get_growth.assert_not_awaited()


def test_brief_pack_keeps_dedicated_growth_fetch_for_custom_timeframe():
    runner = CliRunner()
    providers = FakeBriefProviders()
    providers.trends.get_growth = AsyncMock(
        return_value=[
            {"keyword": "ChatGPT", "growth": {"3M": 5.0, "1Y": -1.25}},
            {"keyword": "Claude", "growth": {"3M": -15.5, "1Y": 300.0}},
        ]
    )

    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = runner.invoke(
            cli_module.cli,
            [
                "brief-pack",
                "--keyword", "ChatGPT",
                "--keyword", "Claude",
                "--market", "US",
                "--timeframe", "today 5-y",
            ],
        )

    assert result.exit_code == 0
    assert "| ChatGPT | 80 | +5.00% | -1.25% |" in result.output
    assert "| Claude | 40 | -15.50% | +300.00% |" in result.output
    providers.trends.get_growth.assert_awaited_once_with(
        keyword=["ChatGPT", "Claude"],
        source="google search",
        percent_growth=["3M", "1Y"],
        geo="US",
    )


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
