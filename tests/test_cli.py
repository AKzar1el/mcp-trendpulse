import io
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner
import pytest
from types import SimpleNamespace

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
    save_article.assert_not_called()


@pytest.mark.parametrize(
    ("command", "argument", "provider"),
    [
        ("keyword", "python", "get_news_by_keyword"),
        ("location", "London", "get_news_by_location"),
        ("topic", "TECHNOLOGY", "get_news_by_topic"),
        ("site", "example.com", "get_news_by_site"),
        ("top", None, "get_top_news"),
    ],
)
def test_article_cli_explicit_json_export_uses_exclusive_mode(tmp_path, command, argument, provider):
    article = MockArticle()
    args = [command] + ([argument] if argument else []) + ["--save-json-dir", str(tmp_path)]
    with (
        patch("mcp_trendpulse.cli.BrowserManager", return_value=NoopBrowserManager()),
        patch(f"mcp_trendpulse.cli.{provider}", new=AsyncMock(return_value=[article])),
        patch("mcp_trendpulse.cli.save_article_to_json") as save_article,
    ):
        result = CliRunner().invoke(cli_module.cli, args)

    assert result.exit_code == 0, result.output
    save_article.assert_called_once()
    saved_args, saved_kwargs = save_article.call_args
    assert saved_args[0] is article
    assert Path(saved_args[1]).parent == tmp_path
    assert Path(saved_args[1]).name.startswith("CLI_article-")
    assert saved_kwargs == {"fail_if_exists": True, "raise_on_error": True}


def test_article_cli_refuses_existing_json_without_overwriting(tmp_path):
    article = MockArticle()
    path = tmp_path / cli_module._article_export_filename(article)
    path.write_text("existing contents", encoding="utf-8")
    with (
        patch("mcp_trendpulse.cli.BrowserManager", return_value=NoopBrowserManager()),
        patch("mcp_trendpulse.cli.get_news_by_keyword", new=AsyncMock(return_value=[article])),
        patch("mcp_trendpulse.cli.save_article_to_json") as save_article,
    ):
        result = CliRunner().invoke(cli_module.cli, ["keyword", "python", "--save-json-dir", str(tmp_path)])

    assert result.exit_code != 0
    assert "refusing to overwrite" in result.output
    assert path.read_text(encoding="utf-8") == "existing contents"
    save_article.assert_not_called()


def test_article_cli_detects_duplicate_export_destinations(tmp_path):
    articles = [MockArticle(), MockArticle()]
    with (
        patch("mcp_trendpulse.cli.BrowserManager", return_value=NoopBrowserManager()),
        patch("mcp_trendpulse.cli.get_news_by_keyword", new=AsyncMock(return_value=articles)),
        patch("mcp_trendpulse.cli.save_article_to_json") as save_article,
    ):
        result = CliRunner().invoke(cli_module.cli, ["keyword", "python", "--save-json-dir", str(tmp_path)])

    assert result.exit_code != 0
    assert "Duplicate article URLs" in result.output
    assert list(tmp_path.iterdir()) == []
    save_article.assert_not_called()


def test_article_export_different_urls_same_title_get_distinct_filenames():
    first = SimpleNamespace(title="A/B", original_url="https://example.com/1")
    second = SimpleNamespace(title="A/B", original_url="https://example.com/2")
    assert cli_module._article_export_filename(first) != cli_module._article_export_filename(second)
    assert cli_module._article_export_filename(first).startswith("A_B-")


def test_keyword_cli_json_export_is_opt_in_and_non_clobbering(tmp_path, monkeypatch):
    article = SimpleNamespace(
        title="Interesting article", original_url="https://example.com/interesting",
        authors=[], publish_date=None, top_image="", images=set(), text="Article text",
        summary="Summary", keywords=[], keyword_scores={}, tags=set(), meta_keywords=[],
        meta_description="", canonical_link="", meta_data={}, meta_lang="en", source_url="https://example.com",
    )
    monkeypatch.chdir(tmp_path)
    with (
        patch("mcp_trendpulse.cli.BrowserManager", return_value=NoopBrowserManager()),
        patch("mcp_trendpulse.cli.get_news_by_keyword", new=AsyncMock(return_value=[article])),
    ):
        output_only = CliRunner().invoke(cli_module.cli, ["keyword", "example"])
        assert output_only.exit_code == 0, output_only.output
        assert list(tmp_path.glob("*.json")) == []

        args = ["keyword", "example", "--save-json-dir", str(tmp_path)]
        first_export = CliRunner().invoke(cli_module.cli, args)
        assert first_export.exit_code == 0, first_export.output
        saved = list(tmp_path.glob("*.json"))
        assert len(saved) == 1
        original_bytes = saved[0].read_bytes()
        assert json.loads(original_bytes)["url"] == article.original_url

        second_export = CliRunner().invoke(cli_module.cli, args)
        assert second_export.exit_code != 0
        assert "refusing to overwrite" in second_export.output
        assert saved[0].read_bytes() == original_bytes


@pytest.mark.parametrize("command,argument", [("keyword", "ai"), ("location", "London"),
                                          ("topic", "WORLD"), ("top", None), ("site", "example.com")])
def test_article_cli_headline_mode_rejects_json_export(tmp_path, command, argument):
    args = [command] + ([argument] if argument else [])
    result = CliRunner().invoke(cli_module.cli, args + ["--headlines-only", "--save-json-dir", str(tmp_path)])
    assert result.exit_code != 0
    assert "not supported with --headlines-only" in result.output


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


def test_brief_pack_escapes_untrusted_keyword_markdown_table_cell():
    keyword = "AI | **Retail**\n<img src=x>"
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(
        return_value=[{"date": "2026-09-13", "value": 42, "keyword": keyword}]
    )
    providers.trends.get_growth = AsyncMock(
        return_value=[{"keyword": keyword, "growth": {"3M": 5, "1Y": 1}}]
    )
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(
            cli_module.cli,
            ["brief-pack", "--keyword", keyword, "--market", "US", "--timeframe", "today 5-y"],
        )

    assert result.exit_code == 0, result.output
    assert "| AI \\| \\*\\*Retail\\*\\* &lt;img src=x&gt; | 42 | +5.00% | +1.00% |" in result.output
    assert "<img src=x>" not in result.output
    assert result.output.count("| 42 |") == 1


def test_brief_pack_does_not_present_nonfinite_provider_values_as_evidence():
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(return_value=[
        {"date": "2026-09-13", "value": float("nan"), "keyword": "ChatGPT"},
        {"date": "2026-09-13", "value": 42, "keyword": "Claude"},
    ])
    providers.trends.get_growth = AsyncMock(return_value=[
        {"keyword": "ChatGPT", "growth": {"3M": float("inf"), "1Y": float("-inf")}},
        {"keyword": "Claude", "growth": {"3M": 5.0, "1Y": -1.25}},
    ])
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(
            cli_module.cli,
            ["brief-pack", "--keyword", "ChatGPT", "--keyword", "Claude", "--market", "US", "--timeframe", "today 5-y"],
        )

    assert result.exit_code == 0, result.output
    assert "| ChatGPT | n/a | n/a | n/a |" in result.output
    assert "| Claude | 42 | +5.00% | -1.25% |" in result.output
    providers.trends.get_growth.assert_awaited_once()


def test_brief_pack_rejects_nonnumeric_provider_values_in_numeric_columns():
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(return_value=[
        {"date": "2026-11-04", "value": "9 | fake column", "keyword": "ChatGPT"},
    ])
    providers.trends.get_growth = AsyncMock(return_value=[
        {"keyword": "ChatGPT", "growth": {"3M": "<img src=x>", "1Y": "unknown"}},
    ])
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(
            cli_module.cli,
            ["brief-pack", "--keyword", "ChatGPT", "--market", "US", "--timeframe", "today 5-y"],
        )

    assert result.exit_code == 0, result.output
    assert "| ChatGPT | n/a | n/a | n/a |" in result.output
    assert "fake column" not in result.output
    assert "<img src=x>" not in result.output
    providers.trends.get_growth.assert_awaited_once()


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
    assert "3M and 1Y growth use separate Google Trends lookback requests" in result.output
    assert "not calculated from the selected today 5-y time series" in result.output
    providers.trends.get_growth.assert_awaited_once_with(
        keyword=["ChatGPT", "Claude"],
        source="google search",
        percent_growth=["3M", "1Y"],
        geo="US",
    )


def test_brief_pack_escapes_timeframe_markdown_without_changing_provider_argument():
    timeframe = "today 5-y\n<img src=x> | **[injected]**"
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(
        return_value=[{"date": "2026-11-01", "value": 80, "keyword": "Example"}]
    )
    providers.trends.get_growth = AsyncMock(return_value=[])
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(
            cli_module.cli,
            ["brief-pack", "--keyword", "Example", "--market", "US", "--timeframe", timeframe],
        )

    assert result.exit_code == 0, result.output
    assert "<img src=x>" not in result.output
    assert "Timeframe: **today 5-y &lt;img src=x&gt; \\|" in result.output
    assert "selected today 5-y &lt;img src=x&gt; \\|" in result.output
    assert r"\*\*\[injected\]\*\*" in result.output
    providers.trends.get_trends.assert_awaited_once_with(
        keyword=["Example"],
        source="google search",
        geo="US",
        timeframe=timeframe,
    )
    providers.trends.get_growth.assert_awaited_once()


@pytest.mark.parametrize(
    "market",
    ["US\n<img src=x>", "US | extra column", "US**bold", "USA", "US--CA"],
)
def test_brief_pack_rejects_malformed_market_before_provider_calls(market):
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(side_effect=AssertionError("invalid market reached provider"))
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(
            cli_module.cli,
            ["brief-pack", "--keyword", "Example", "--market", market],
        )

    assert result.exit_code == 2, result.output
    assert "Invalid --market" in result.output
    providers.trends.get_trends.assert_not_awaited()


@pytest.mark.parametrize("market,expected", [("US", "US"), ("us-ca", "US-CA"), ("US-CA-803", "US-CA-803")])
def test_brief_pack_accepts_country_and_subregion_market_codes(market, expected):
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(
        return_value=[{"date": "2026-11-01", "keyword": "Example", "value": 80}]
    )
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(
            cli_module.cli,
            ["brief-pack", "--keyword", "Example", "--market", market],
        )

    assert result.exit_code == 0, result.output
    assert f"## {expected}" in result.output
    providers.trends.get_trends.assert_awaited_once_with(
        keyword=["Example"], source="google search", geo=expected, timeframe="today 12-m"
    )


def test_brief_pack_labels_stale_keyword_observations_and_uses_latest_by_date():
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(
        return_value=[
            {"date": "2026-09-13", "keyword": "ChatGPT", "value": 80},
            {"date": "2026-08-30", "keyword": "Claude", "value": 40},
            {"date": "2026-08-23", "keyword": "Claude", "value": 20},
        ]
    )
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(
            cli_module.cli,
            ["brief-pack", "--keyword", "ChatGPT", "--keyword", "Claude", "--market", "US", "--timeframe", "today 5-y"],
        )

    assert result.exit_code == 0, result.output
    assert "| Claude | 40 | -15.50% | +300.00% |" in result.output
    assert "Claude: last observation **2026-08-30** (market latest **2026-09-13**)" in result.output
    assert "Latest complete Trends point: **2026-09-13**" in result.output


def test_brief_pack_does_not_treat_invalid_dates_as_latest_observations():
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(return_value=[
        {"date": "2026-11-01", "keyword": "Example", "value": 80},
        {"date": "bad-date", "keyword": "Example", "value": 10},
        {"date": "2026-02-30", "keyword": "Other", "value": 90},
    ])
    providers.trends.get_growth = AsyncMock(return_value=[])
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "Example", "--keyword", "Other",
            "--market", "US", "--timeframe", "today 5-y",
        ])

    assert result.exit_code == 0, result.output
    assert "Latest complete Trends point: **2026-11-01**" in result.output
    assert "| Example | 80 | n/a | n/a |" in result.output
    assert "| Other | n/a | n/a | n/a |" in result.output
    assert "Excluded 2 Trends observations with invalid dates" in result.output
    assert "bad-date" not in result.output
    providers.trends.get_trends.assert_awaited_once()
    providers.trends.get_growth.assert_awaited_once()


def test_brief_pack_excludes_invalid_dates_from_default_growth_computation():
    providers = FakeBriefProviders()
    providers.trends.get_growth = AsyncMock(side_effect=AssertionError("default timeframe must reuse valid points"))
    good = {"date": "2026-11-01", "keyword": "Example", "value": 70}
    providers.trends.get_trends = AsyncMock(return_value=[
        {"date": "bad-date", "keyword": "Example", "value": 10}, good,
    ])
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers), patch(
        "mcp_trendpulse.cli._growth_from_trend_points",
        return_value=[{"keyword": "Example", "growth": {"3M": None, "1Y": None}}],
    ) as growth:
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "Example", "--market", "US",
        ])

    assert result.exit_code == 0, result.output
    assert "| Example | 70 | n/a | n/a |" in result.output
    growth.assert_called_once_with([good], ["Example"], ["3M", "1Y"])
    providers.trends.get_growth.assert_not_awaited()


def test_brief_pack_does_not_invent_latest_date_when_all_dates_invalid():
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(return_value=[
        {"date": "2026-02-30", "keyword": "Example", "value": 99},
    ])
    providers.trends.get_growth = AsyncMock(return_value=[])
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "Example", "--market", "US", "--timeframe", "today 5-y",
        ])

    assert result.exit_code == 0, result.output
    assert "Latest complete Trends point" not in result.output
    assert "| Example | n/a | n/a | n/a |" in result.output
    assert "Excluded 1 Trends observation with invalid dates" in result.output


def test_brief_pack_accepts_valid_iso_timestamp_as_dated_observation():
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(return_value=[
        {"date": "2026-11-01T12:30:00Z", "keyword": "Example", "value": 80},
    ])
    providers.trends.get_growth = AsyncMock(return_value=[])
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "Example", "--market", "US", "--timeframe", "today 5-y",
        ])

    assert result.exit_code == 0, result.output
    assert "Latest complete Trends point: **2026-11-01T12:30:00Z**" in result.output
    assert "| Example | 80 | n/a | n/a |" in result.output
    assert "Excluded" not in result.output


def test_brief_pack_selects_latest_hourly_point_not_first_same_day_point():
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(return_value=[
        {"date": "2026-11-07T10:00:00Z", "keyword": "Example", "value": 10},
        {"date": "2026-11-07T23:00:00+00:00", "keyword": "Example", "value": 80},
        {"date": "2026-11-08T00:30:00+02:00", "keyword": "Other", "value": 50},
    ])
    providers.trends.get_growth = AsyncMock(return_value=[])
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "Example", "--keyword", "Other",
            "--market", "US", "--timeframe", "now 1-d",
        ])

    assert result.exit_code == 0, result.output
    assert "Latest complete Trends point: **2026-11-07T23:00:00Z**" in result.output
    assert "| Example | 80 | n/a | n/a |" in result.output
    assert "| Other | 50 | n/a | n/a |" in result.output
    assert (
        "Other: last observation **2026-11-07T22:30:00Z** "
        "(market latest **2026-11-07T23:00:00Z**)"
    ) in result.output


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

@pytest.mark.parametrize(
    ("command", "method", "kwargs"),
    [
        (["keyword", "python"], "get_rss_headlines_by_keyword", {"keyword": "python", "period": 7, "max_results": 10}),
        (["location", "London"], "get_rss_headlines_by_location", {"location": "London", "period": 7, "max_results": 10}),
        (["topic", "TECHNOLOGY"], "get_rss_headlines_by_topic", {"topic": "TECHNOLOGY", "period": 7, "max_results": 10}),
        (["top"], "get_rss_headlines_for_top_news", {"period": 3, "max_results": 10}),
        (["site", "bbc.com"], "get_rss_headlines_by_site", {"site": "bbc.com", "period": 7, "max_results": 10}),
    ],
)
def test_cli_headlines_are_labeled_without_article_extraction(command, method, kwargs):
    headline = {
        "title": "Real feed headline", "url": "https://news.google.com/rss/articles/example",
        "meta_site_name": "Example News", "publish_date": "2026-10-25T09:00:00+00:00",
        "meta_data": {"content_level": "rss_headline_only", "source": "google_news_rss"},
    }
    provider = AsyncMock(return_value=[headline])
    news = SimpleNamespace(**{method: provider})
    with (
        patch("mcp_trendpulse.cli.get_provider_set", return_value=SimpleNamespace(news=news)),
        patch("mcp_trendpulse.cli.BrowserManager", side_effect=AssertionError("RSS must not open browser")),
        patch("mcp_trendpulse.cli.save_article_to_json", side_effect=AssertionError("RSS must not save article")),
    ):
        result = CliRunner().invoke(cli_module.cli, [*command, "--headlines-only"])
    assert result.exit_code == 0, result.output
    assert "Title: Real feed headline" in result.output
    assert "Google News URL: https://news.google.com/rss/articles/example" in result.output
    assert "Publisher: Example News" in result.output
    assert "Content level: rss_headline_only (metadata, not article text)" in result.output
    assert "Summary:" not in result.output
    provider.assert_awaited_once_with(**kwargs)


def test_cli_rejects_unlabeled_rss_claims():
    news = SimpleNamespace(get_rss_headlines_by_keyword=AsyncMock(return_value=[{
        "title": "Not RSS", "meta_data": {"content_level": "article_full", "source": "google_news_rss"},
    }]))
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=SimpleNamespace(news=news)):
        result = CliRunner().invoke(cli_module.cli, ["keyword", "ai", "--headlines-only"])
    assert result.exit_code != 0
    assert "Unexpected RSS headline evidence level" in result.output



@pytest.mark.parametrize(
    ("command", "api_name"),
    [
        ("keyword", "get_news_by_keyword"),
        ("location", "get_news_by_location"),
        ("site", "get_news_by_site"),
        ("topic", "get_news_by_topic"),
        ("top", "get_top_news"),
        ("trending", "get_trending_terms"),
    ],
)
def test_cli_help_preserves_news_api_docstrings(command, api_name):
    from inspect import cleandoc

    from mcp_trendpulse import news

    assert cleandoc(cli_module.cli.commands[command].help) == cleandoc(
        getattr(news, api_name).__doc__
    )


def test_cli_help_remains_lazy_in_fresh_python_process():
    import subprocess

    script = (
        "import sys; from click.testing import CliRunner; "
        "from mcp_trendpulse.cli import cli; "
        "result = CliRunner().invoke(cli, ['keyword', '--help']); "
        "assert result.exit_code == 0, result.output; "
        "assert 'mcp_trendpulse.news' not in sys.modules"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
