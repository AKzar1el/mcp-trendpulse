import csv
import errno
import io
import json
import sys
from contextlib import redirect_stdout
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner
import pytest
from types import SimpleNamespace

from mcp_trendpulse import cli as cli_module
from mcp_trendpulse.errors import (
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


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


class _SimulatedTTY(io.StringIO):
    def isatty(self):
        return True


@pytest.mark.parametrize("tty", [False, True])
@pytest.mark.parametrize("field", ["title", "url", "meta_site_name", "publish_date"])
def test_rss_text_cannot_emit_terminal_controls_or_forged_labels(field, tty):
    injected = "safe\x1b[2J\r\b\nPublisher: forged\x9b31m\x1b]0;fake\x07"
    item = {
        "title": "Headline", "url": "https://news.google.com/rss/articles/valid",
        "meta_site_name": "Publisher", "publish_date": "2026-11-23",
        "meta_data": {"source": "google_news_rss", "content_level": "rss_headline_only"},
    }
    item[field] = injected
    output = _SimulatedTTY() if tty else io.StringIO()
    with redirect_stdout(output):
        cli_module.print_rss_headlines([item], output_format="text")
    rendered = output.getvalue()

    assert all(char not in rendered for char in ("\x1b", "\r", "\b", "\x9b", "\x07"))
    assert "\\x1b[2J" in rendered
    assert "\\nPublisher: forged" in rendered
    assert not any(line == "Publisher: forged" for line in rendered.splitlines())
    assert "Content level: rss_headline_only" in rendered


@pytest.mark.parametrize("tty", [False, True])
@pytest.mark.parametrize("field", ["title", "original_url", "authors", "publish_date", "top_image", "summary"])
def test_article_text_cannot_emit_terminal_controls_or_forged_labels(field, tty):
    injected = "safe\x1b[2J\r\b\nTitle: forged\x9b31m\x1b]0;fake\x07"
    article = SimpleNamespace(
        title="Headline", original_url="https://example.com/article", authors=["Example"],
        publish_date="2026-11-23", top_image="https://example.com/image", summary="Summary",
    )
    setattr(article, field, injected)
    output = _SimulatedTTY() if tty else io.StringIO()
    with redirect_stdout(output):
        cli_module.print_articles([article])
    rendered = output.getvalue()

    assert all(char not in rendered for char in ("\x1b", "\r", "\b", "\x9b", "\x07"))
    assert "\\x1b[2J" in rendered
    assert not any(line == "Title: forged" for line in rendered.splitlines())
    if field == "summary":
        assert "\n    Title: forged" in rendered
    else:
        assert "\\nTitle: forged" in rendered


def test_rss_json_preserves_raw_evidence_when_text_display_is_escaped():
    raw_title = "Headline\x1b[2J\nAnother line"
    item = {
        "title": raw_title, "url": "https://news.google.com/rss/articles/valid",
        "meta_site_name": "Publisher", "publish_date": "2026-11-23",
        "meta_data": {"source": "google_news_rss", "content_level": "rss_headline_only"},
    }
    output = io.StringIO()
    with redirect_stdout(output):
        cli_module.print_rss_headlines([item], output_format="json")
    assert json.loads(output.getvalue())["headlines"][0]["title"] == raw_title


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


def test_brief_pack_watch_json_is_directly_consumable_by_manual_watch(tmp_path):
    from mcp_trendpulse.trend_watch import WatchStore, parse_evidence

    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(return_value=[
        {"date": (date.today() - timedelta(weeks=7 - index)).isoformat(),
         "keyword": "ChatGPT", "value": 20 if index < 6 else 80}
        for index in range(8)
    ])
    providers.trends.get_growth = AsyncMock(side_effect=AssertionError("Watch export must use one Trends request"))
    target = tmp_path / "watch-evidence.json"
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--market", "US",
            "--format", "watch-json", "--watch-evidence-file", str(target),
        ])

    assert result.exit_code == 0, result.output
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["keyword"] == "ChatGPT" and data["market"] == "US"
    assert data["source"] == "Google Trends"
    assert len(data["points"]) == 8
    assert parse_evidence(target.read_bytes(), keyword="ChatGPT", market="US")
    rule = WatchStore(tmp_path / "watch-rules").create(keyword="ChatGPT", market="US", window=2)
    assert WatchStore(tmp_path / "watch-rules").evaluate_and_record(rule.id, target.read_bytes()).status == "triggered"
    providers.trends.get_trends.assert_awaited_once()
    providers.trends.get_growth.assert_not_awaited()


@pytest.mark.parametrize("extra", [
    ["--keyword", "Claude"],
    ["--market", "GB"],
])
def test_brief_pack_watch_json_rejects_mixed_series_before_provider_call(extra):
    with patch("mcp_trendpulse.cli.get_provider_set") as get_providers:
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--market", "US",
            *extra, "--format", "watch-json",
        ])
    assert result.exit_code != 0
    assert "one keyword and one market" in result.output.lower()
    get_providers.assert_not_called()


@pytest.mark.parametrize("point", [
    {"date": "2026-09-01T10:00:00Z", "keyword": "ChatGPT", "value": 40},
    {"date": "2026-09-01", "keyword": "ChatGPT", "value": 101},
    {"date": "2026-09-01", "keyword": "Other", "value": 40},
    {"date": "2026-09-01", "keyword": "ChatGPT", "value": True},
])
def test_brief_pack_watch_json_fails_closed_on_incompatible_series(tmp_path, point):
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(return_value=[point])
    target = tmp_path / "watch.json"
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--market", "US",
            "--format", "watch-json", "--watch-evidence-file", str(target),
        ])
    assert result.exit_code != 0
    assert not target.exists()


def test_brief_pack_watch_json_never_overwrites_existing_file_before_fetch(tmp_path):
    target = tmp_path / "watch.json"
    target.write_text("owner data", encoding="utf-8")
    with patch("mcp_trendpulse.cli.get_provider_set") as get_providers:
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--market", "US",
            "--format", "watch-json", "--watch-evidence-file", str(target),
        ])
    assert result.exit_code != 0
    assert target.read_text(encoding="utf-8") == "owner data"
    get_providers.assert_not_called()


def test_brief_pack_watch_json_removes_partial_evidence_after_write_failure(tmp_path):
    target = tmp_path / "watch.json"
    original_open = Path.open
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(return_value=[
        {"date": f"2026-09-{day:02d}", "keyword": "ChatGPT", "value": day * 4}
        for day in range(1, 9)
    ])

    class InterruptedWrite:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.handle.close()

        def write(self, payload):
            self.handle.write(payload[:8])
            self.handle.flush()
            raise OSError(errno.ENOSPC, "simulated disk full")

    def fail_mid_write(path, mode="r", *args, **kwargs):
        handle = original_open(path, mode, *args, **kwargs)
        if path == target and mode == "x":
            return InterruptedWrite(handle)
        return handle

    with (
        patch.object(Path, "open", fail_mid_write),
        patch("mcp_trendpulse.cli.get_provider_set", return_value=providers),
    ):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--market", "US",
            "--format", "watch-json", "--watch-evidence-file", str(target),
        ])

    assert result.exit_code != 0
    assert "not saved" in result.output.lower()
    assert not target.exists(), "A truncated file must not masquerade as valid Watch evidence"


def test_brief_pack_watch_json_stdout_retains_partial_marker():
    from mcp_trendpulse.trend_watch import parse_evidence

    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(return_value=[
        {"keyword": "ChatGPT", "date": "2026-09-08", "value": 25, "isPartial": True},
        {"keyword": "ChatGPT", "date": "2026-09-01", "value": 20},
    ])
    providers.trends.get_growth = AsyncMock(side_effect=AssertionError("No growth fetch for Watch output"))
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--market", "US", "--format", "watch-json",
        ])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["points"] == [
        {"date": "2026-09-01", "value": 20.0},
        {"date": "2026-09-08", "value": 25.0, "isPartial": True},
    ]
    assert len(parse_evidence(result.output.encode("utf-8"), keyword="ChatGPT", market="US")) == 1
    providers.trends.get_growth.assert_not_awaited()


def test_brief_pack_watch_json_rejects_duplicate_dates_without_writing(tmp_path):
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(return_value=[
        {"keyword": "ChatGPT", "date": "2026-09-01", "value": 20},
        {"keyword": "ChatGPT", "date": "2026-09-01", "value": 30},
    ])
    target = tmp_path / "watch.json"
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--market", "US",
            "--format", "watch-json", "--watch-evidence-file", str(target),
        ])
    assert result.exit_code != 0
    assert "duplicate" in result.output.lower()
    assert not target.exists()


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


def test_brief_pack_markdown_summarizes_two_market_primary_evidence_without_ranking():
    providers = FakeBriefProviders()
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--keyword", "Claude",
            "--market", "US", "--market", "GB",
        ])

    assert result.exit_code == 0, result.output
    assert "## Cross-market evidence coverage" in result.output
    assert "| US | 2/2 | 2026-09-13 | observed |" in result.output
    assert "| GB | 2/2 | 2026-09-13 | observed |" in result.output
    assert "coverage and freshness only" in result.output
    assert "not a ranking" in result.output


def test_brief_pack_markdown_coverage_counts_valid_zero_and_missing_primary():
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(return_value=[
        {"date": "2026-09-13", "keyword": "ChatGPT", "value": 0},
        {"date": "2026-09-13", "keyword": "Claude", "value": None},
    ])
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--keyword", "Claude",
            "--market", "US", "--market", "GB",
        ])

    assert result.exit_code == 0, result.output
    assert "| US | 1/2 | 2026-09-13 | observed |" in result.output
    assert "| GB | 1/2 | 2026-09-13 | observed |" in result.output
    assert providers.trends.get_trends.await_count == 2


def test_brief_pack_markdown_coverage_distinguishes_rate_limit_from_skipped_market():
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(
        side_effect=ProviderRateLimitError("google_trends", "get_trends")
    )
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--market", "US", "--market", "GB",
            "--allow-partial",
        ])

    assert result.exit_code == 1, result.output
    assert "| US | 0/1 | n/a | unavailable |" in result.output
    assert "| GB | 0/1 | n/a | not attempted |" in result.output
    assert "INCOMPLETE EVIDENCE" in result.output
    providers.trends.get_trends.assert_awaited_once()


def test_brief_pack_markdown_coverage_preserves_primary_when_growth_times_out():
    providers = FakeBriefProviders()
    providers.trends.get_growth = AsyncMock(
        side_effect=ProviderTimeoutError("google_trends", "get_growth")
    )
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--market", "US", "--market", "GB",
            "--timeframe", "today 5-y", "--allow-partial",
        ])

    assert result.exit_code == 1, result.output
    assert "| US | 1/1 | 2026-09-13 | growth unavailable |" in result.output
    assert "| GB | 1/1 | 2026-09-13 | growth unavailable |" in result.output
    assert "INCOMPLETE EVIDENCE" in result.output
    assert providers.trends.get_growth.await_count == 2


def test_brief_pack_markdown_coverage_discloses_missing_primary_and_growth_failure():
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(side_effect=[
        [],
        [{"date": "2026-09-13", "keyword": "ChatGPT", "value": 50}],
    ])
    providers.trends.get_growth = AsyncMock(
        side_effect=ProviderTimeoutError("google_trends", "get_growth")
    )
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--market", "US", "--market", "GB",
            "--timeframe", "today 5-y", "--allow-partial",
        ])

    assert result.exit_code == 1, result.output
    assert "| US | 0/1 | n/a | no primary evidence; growth unavailable |" in result.output
    assert "| GB | 1/1 | 2026-09-13 | growth unavailable |" in result.output
    assert providers.trends.get_trends.await_count == 2
    assert providers.trends.get_growth.await_count == 2


def test_brief_pack_markdown_one_market_has_no_cross_market_summary():
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=FakeBriefProviders()):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--market", "US",
        ])

    assert result.exit_code == 0, result.output
    assert "Cross-market evidence coverage" not in result.output


def test_brief_pack_json_exports_typed_attributed_two_market_evidence():
    providers = FakeBriefProviders()
    providers.trends.get_growth = AsyncMock(side_effect=AssertionError("default brief pack must reuse trend points"))
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(
            cli_module.cli,
            ["brief-pack", "--keyword", "ChatGPT", "--keyword", "Claude", "--market", "US", "--market", "GB", "--format", "json"],
        )

    assert result.exit_code == 0, result.output
    evidence = json.loads(result.output)
    assert evidence["schema_version"] == 1
    assert evidence["source"] == "Google Trends"
    assert evidence["source_url"] == "https://trends.google.com/trends/"
    assert evidence["property"] == "Google Search"
    assert evidence["timeframe"] == "today 12-m"
    assert "not absolute search volume" in evidence["comparability_note"]
    assert len(evidence["markets"]) == 2
    assert [row["market"] for row in evidence["markets"]] == ["US", "GB"]
    assert evidence["markets"][0]["latest_complete_trends_point"] == "2026-09-13"
    assert evidence["markets"][0]["growth_basis"] == "selected_timeframe"
    assert evidence["markets"][0]["keywords"][0] == {
        "keyword": "ChatGPT", "latest_index": 80.0,
        "latest_observation": "2026-09-13", "growth_3m_pct": 100.0, "growth_1y_pct": 100.0,
    }
    assert evidence["markets"][1]["keywords"][0]["latest_index"] == 60.0
    providers.trends.get_growth.assert_not_awaited()


def test_brief_pack_csv_exports_attributed_two_market_rows():
    providers = FakeBriefProviders()
    providers.trends.get_growth = AsyncMock(side_effect=AssertionError("CSV must reuse current Trends points"))
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--keyword", "Claude",
            "--market", "US", "--market", "GB", "--format", "csv",
        ])

    assert result.exit_code == 0, result.output
    rows = list(csv.DictReader(io.StringIO(result.output)))
    assert len(rows) == 4
    assert [(r["market"], r["keyword"]) for r in rows] == [
        ("US", "ChatGPT"), ("US", "Claude"), ("GB", "ChatGPT"), ("GB", "Claude"),
    ]
    assert rows[0]["source"] == "Google Trends"
    assert rows[0]["property"] == "Google Search"
    assert rows[0]["timeframe"] == "today 12-m"
    assert rows[0]["growth_basis"] == "selected_timeframe"
    assert "not absolute search volume" in rows[0]["comparability_note"]
    assert rows[0]["latest_index"] == "80.0"
    assert rows[0]["latest_observation"] == "2026-09-13"
    assert rows[0]["growth_3m_pct"] == "100.0"
    assert rows[0]["status"] == "observed"
    assert rows[0]["incomplete"] == "false"
    assert rows[2]["latest_index"] == "60.0"
    providers.trends.get_growth.assert_not_awaited()


def test_brief_pack_csv_partial_rate_limit_keeps_error_and_nonzero_exit():
    providers = FakeBriefProviders()
    original = providers.trends.get_trends

    async def get_trends(**kwargs):
        if kwargs["geo"] == "GB":
            raise ProviderRateLimitError("google_trends", "get_trends")
        return await original(**kwargs)

    providers.trends.get_trends = AsyncMock(side_effect=get_trends)
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--market", "US", "--market", "GB",
            "--format", "csv", "--allow-partial",
        ])

    assert result.exit_code == 1, result.output
    rows = list(csv.DictReader(io.StringIO(result.output)))
    assert len(rows) == 2
    assert rows[0]["market"] == "US" and rows[0]["status"] == "observed"
    assert rows[0]["incomplete"] == "true"
    assert rows[1]["market"] == "GB" and rows[1]["status"] == "unavailable"
    assert rows[1]["latest_index"] == ""
    assert rows[1]["error_code"] == "provider_rate_limited"
    assert rows[1]["retryable"] == "true"
    assert rows[1]["incomplete"] == "true"
    assert providers.trends.get_trends.await_count == 2


def test_brief_pack_csv_secondary_rate_limit_preserves_primary_and_stops():
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(side_effect=providers.trends.get_trends)
    providers.trends.get_growth = AsyncMock(
        side_effect=ProviderRateLimitError("google_trends", "get_growth")
    )
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--market", "US", "--market", "GB",
            "--timeframe", "today 5-y", "--format", "csv", "--allow-partial",
        ])

    assert result.exit_code == 1, result.output
    rows = list(csv.DictReader(io.StringIO(result.output)))
    assert len(rows) == 2
    assert rows[0]["status"] == "observed"
    assert rows[0]["latest_index"] == "80.0"
    assert rows[0]["growth_3m_pct"] == ""
    assert rows[0]["growth_basis"] == "separate_lookback_requests"
    assert rows[0]["error_component"] == "growth"
    assert rows[0]["error_code"] == "provider_rate_limited"
    assert rows[1]["market"] == "GB" and rows[1]["status"] == "not_attempted"
    assert rows[1]["error_code"] == "not_attempted_due_to_rate_limit"
    providers.trends.get_trends.assert_awaited_once()
    providers.trends.get_growth.assert_awaited_once()


def test_brief_pack_csv_quotes_and_neutralizes_formula_like_keyword():
    keyword = '=HYPERLINK("https://example.com","open")'
    provider = SimpleNamespace(trends=SimpleNamespace(
        get_trends=AsyncMock(return_value=[
            {"date": "2026-09-06", "keyword": keyword, "value": 35},
            {"date": "2026-09-13", "keyword": keyword, "value": 70},
        ]),
    ))
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=provider):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", keyword, "--market", "US", "--format", "csv",
        ])

    assert result.exit_code == 0, result.output
    rows = list(csv.DictReader(io.StringIO(result.output)))
    assert len(rows) == 1
    assert rows[0]["keyword"] == "'" + keyword
    assert rows[0]["latest_index"] == "70.0"


@pytest.mark.parametrize("older_date,latest_date", [
    ("2026-11-14", "2026-11-15"),
    ("2026-11-15T12:00:00Z", "2026-11-15T15:00:00Z"),
])
def test_brief_pack_csv_exposes_per_keyword_market_temporal_alignment(older_date, latest_date):
    provider = SimpleNamespace(trends=SimpleNamespace(get_trends=AsyncMock(return_value=[
        {"date": older_date, "keyword": "Alpha", "value": 40},
        {"date": latest_date, "keyword": "Beta", "value": 70},
    ])))
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=provider):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "Alpha", "--keyword", "Beta",
            "--keyword", "Missing", "--market", "US", "--format", "csv",
        ])

    assert result.exit_code == 0, result.output
    rows = list(csv.DictReader(io.StringIO(result.output)))
    assert [row["status"] for row in rows] == [
        "observed", "observed", "no_valid_observation",
    ]
    assert [row["observation_alignment"] for row in rows] == [
        "older_than_market_latest", "market_latest", "",
    ]
    assert "older than market latest" in rows[0]["warnings"]


@pytest.mark.parametrize("output_format", ["json", "csv"])
def test_brief_pack_writes_new_utf8_evidence_file_without_shell_redirect(tmp_path, output_format):
    keyword = "café trends"
    target = tmp_path / f"evidence.{output_format}"
    provider = SimpleNamespace(trends=SimpleNamespace(get_trends=AsyncMock(return_value=[
        {"date": "2026-09-06", "keyword": keyword, "value": 15},
        {"date": "2026-09-13", "keyword": keyword, "value": 30},
    ])))
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=provider):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", keyword, "--market", "US", "--format", output_format,
            "--output-file", str(target),
        ])

    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert "Wrote Demand Brief evidence" in result.stderr
    raw = target.read_bytes()
    assert b"\xef\xbb\xbf" not in raw[:3]
    assert keyword.encode("utf-8") in raw
    if output_format == "json":
        assert json.loads(raw)["markets"][0]["keywords"][0]["keyword"] == keyword
    else:
        assert list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))[0]["keyword"] == keyword
    provider.trends.get_trends.assert_awaited_once()


@pytest.mark.parametrize("output_format", ["json", "csv", "markdown"])
def test_brief_pack_file_export_refuses_to_overwrite_before_provider_call(tmp_path, output_format):
    target = tmp_path / "existing.txt"
    target.write_bytes(b"precious existing evidence")
    provider = SimpleNamespace(trends=SimpleNamespace(get_trends=AsyncMock()))
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=provider):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "AI", "--market", "US", "--format", output_format,
            "--output-file", str(target),
        ])

    assert result.exit_code != 0
    assert "new file" in result.output
    assert target.read_bytes() == b"precious existing evidence"
    provider.trends.get_trends.assert_not_awaited()


@pytest.mark.parametrize("output_format", ["watch-json"])
def test_brief_pack_file_export_rejects_unsupported_formats_before_query(tmp_path, output_format):
    provider = SimpleNamespace(trends=SimpleNamespace(get_trends=AsyncMock()))
    target = tmp_path / "evidence.txt"
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=provider):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "AI", "--market", "US", "--format", output_format,
            "--output-file", str(target),
        ])

    assert result.exit_code != 0
    assert "--output-file requires --format json, csv or markdown" in result.output
    assert not target.exists()
    provider.trends.get_trends.assert_not_awaited()


def test_brief_pack_file_export_keeps_partial_csv_and_nonzero_status(tmp_path):
    target = tmp_path / "partial.csv"
    providers = FakeBriefProviders()
    original = providers.trends.get_trends

    async def limited(**kwargs):
        if kwargs["geo"] == "GB":
            raise ProviderRateLimitError("google_trends", "get_trends")
        return await original(**kwargs)

    providers.trends.get_trends = AsyncMock(side_effect=limited)
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--market", "US", "--market", "GB",
            "--format", "csv", "--allow-partial", "--output-file", str(target),
        ])

    assert result.exit_code == 1, result.output
    assert result.stdout == ""
    assert "incomplete Demand Brief evidence" in result.stderr
    rows = list(csv.DictReader(io.StringIO(target.read_text(encoding="utf-8"))))
    assert [(row["status"], row["incomplete"]) for row in rows] == [
        ("observed", "true"), ("unavailable", "true"),
    ]
    assert rows[1]["error_code"] == "provider_rate_limited"
    assert providers.trends.get_trends.await_count == 2


def test_brief_pack_file_export_strict_provider_error_creates_no_file(tmp_path):
    target = tmp_path / "never-created.json"
    provider = SimpleNamespace(trends=SimpleNamespace(get_trends=AsyncMock(
        side_effect=ProviderRateLimitError("google_trends", "get_trends")
    )))
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=provider):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "AI", "--market", "US", "--format", "json",
            "--output-file", str(target),
        ])

    assert result.exit_code != 0
    assert not target.exists()


def test_brief_pack_markdown_file_matches_stdout_with_utf8_and_no_bom(tmp_path):
    keyword = "caf\u00e9 trends"
    target = tmp_path / "brief.md"
    provider = SimpleNamespace(trends=SimpleNamespace(get_trends=AsyncMock(return_value=[
        {"date": "2026-09-06", "keyword": keyword, "value": 15},
        {"date": "2026-09-13", "keyword": keyword, "value": 30},
    ])))
    args = ["brief-pack", "--keyword", keyword, "--market", "US", "--format", "markdown"]
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=provider):
        stdout_result = CliRunner().invoke(cli_module.cli, args)
        saved_result = CliRunner().invoke(cli_module.cli, [*args, "--output-file", str(target)])

    assert stdout_result.exit_code == 0, stdout_result.output
    assert saved_result.exit_code == 0, saved_result.output
    assert saved_result.stdout == ""
    assert "Wrote Demand Brief evidence" in saved_result.stderr
    raw = target.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert keyword.encode("utf-8") in raw
    assert raw.decode("utf-8") == stdout_result.stdout


def test_brief_pack_markdown_file_preserves_partial_output_and_nonzero_exit(tmp_path):
    target = tmp_path / "incomplete.md"
    providers = FakeBriefProviders()
    original = providers.trends.get_trends

    async def limited(**kwargs):
        if kwargs["geo"] == "GB":
            raise ProviderRateLimitError("google_trends", "get_trends")
        return await original(**kwargs)

    providers.trends.get_trends = AsyncMock(side_effect=limited)
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--market", "US", "--market", "GB",
            "--format", "markdown", "--allow-partial", "--output-file", str(target),
        ])

    assert result.exit_code == 1, result.output
    assert result.stdout == ""
    assert "incomplete Demand Brief evidence" in result.stderr
    markdown = target.read_text(encoding="utf-8")
    assert "## US" in markdown
    assert "## GB" in markdown
    assert "NOT ATTEMPTED" not in markdown  # GB was queried, then rate-limited.
    assert "INCOMPLETE EVIDENCE" in markdown
    assert providers.trends.get_trends.await_count == 2


def test_brief_pack_markdown_file_strict_error_leaves_no_partial_file(tmp_path):
    target = tmp_path / "strict.md"
    providers = SimpleNamespace(trends=SimpleNamespace(get_trends=AsyncMock(
        side_effect=ProviderRateLimitError("google_trends", "get_trends")
    )))
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "AI", "--market", "US",
            "--format", "markdown", "--output-file", str(target),
        ])

    assert result.exit_code == 1
    assert "provider_rate_limited" in result.output
    assert result.stdout == ""
    assert not target.exists()


@pytest.mark.parametrize("output_format", ["json", "markdown"])
@pytest.mark.parametrize(
    ("error", "code", "advice"),
    [
        (ProviderRateLimitError("google_trends", "interest_over_time"), "provider_rate_limited", "Try again later"),
        (ProviderTimeoutError("google_trends", "interest_over_time"), "provider_timeout", "Try again"),
    ],
)
def test_brief_pack_reports_actionable_upstream_failure(output_format, error, code, advice):
    provider = SimpleNamespace(trends=SimpleNamespace(get_trends=AsyncMock(side_effect=error)))
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=provider):
        result = CliRunner().invoke(
            cli_module.cli,
            ["brief-pack", "--keyword", "Example", "--market", "US", "--format", output_format],
        )

    assert result.exit_code == 1
    assert f"Error: {code}:" in result.output
    assert advice in result.output
    assert "Traceback" not in result.output
    if output_format == "json":
        assert not result.output.startswith("{\"schema_version\"")
    provider.trends.get_trends.assert_awaited_once()


@pytest.mark.parametrize("output_format", ["json", "markdown"])
def test_brief_pack_opt_in_salvages_successful_market_and_marks_rate_limited_market(output_format):
    providers = FakeBriefProviders()
    original = providers.trends.get_trends

    async def get_trends(**kwargs):
        if kwargs["geo"] == "GB":
            raise ProviderRateLimitError("google_trends", "get_trends")
        return await original(**kwargs)

    providers.trends.get_trends = AsyncMock(side_effect=get_trends)
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--market", "US", "--market", "GB",
            "--format", output_format, "--allow-partial",
        ])

    assert result.exit_code == 1, result.output
    assert providers.trends.get_trends.await_count == 2
    if output_format == "json":
        payload = json.loads(result.output)
        assert payload["schema_version"] == 1
        assert payload["incomplete"] is True
        assert [row["market"] for row in payload["markets"]] == ["US"]
        assert payload["markets"][0]["keywords"][0]["latest_index"] == 80.0
        assert payload["failed_markets"] == [{
            "market": "GB", "code": "provider_rate_limited", "retryable": True,
            "message": "The upstream provider is rate limiting requests. Try again later.",
        }]
    else:
        assert "## US" in result.output and "| ChatGPT | 80 |" in result.output
        assert "## GB" in result.output and "provider_rate_limited" in result.output
        assert "INCOMPLETE" in result.output


def test_brief_pack_partial_stops_after_rate_limit_without_querying_another_market():
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(
        side_effect=ProviderRateLimitError("google_trends", "get_trends")
    )
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--market", "US", "--market", "GB",
            "--format", "json", "--allow-partial",
        ])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["markets"] == []
    assert [row["market"] for row in payload["failed_markets"]] == ["US", "GB"]
    assert payload["failed_markets"][0]["code"] == "provider_rate_limited"
    assert payload["failed_markets"][1]["code"] == "not_attempted_due_to_rate_limit"
    providers.trends.get_trends.assert_awaited_once()


def test_brief_pack_partial_continues_once_after_timeout_and_preserves_second_market():
    providers = FakeBriefProviders()
    original = providers.trends.get_trends

    async def get_trends(**kwargs):
        if kwargs["geo"] == "US":
            raise ProviderTimeoutError("google_trends", "get_trends")
        return await original(**kwargs)

    providers.trends.get_trends = AsyncMock(side_effect=get_trends)
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--market", "US", "--market", "GB",
            "--format", "json", "--allow-partial",
        ])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert [row["market"] for row in payload["markets"]] == ["GB"]
    assert payload["markets"][0]["keywords"][0]["latest_index"] == 60.0
    assert payload["failed_markets"][0]["code"] == "provider_timeout"
    assert providers.trends.get_trends.await_count == 2


def test_brief_pack_partial_all_markets_unavailable_never_invents_observations():
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(
        side_effect=ProviderUnavailableError("google_trends", "get_trends")
    )
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--market", "US", "--market", "GB",
            "--format", "json", "--allow-partial",
        ])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["markets"] == []
    assert payload["incomplete"] is True
    assert [row["code"] for row in payload["failed_markets"]] == [
        "provider_unavailable", "provider_unavailable",
    ]
    assert providers.trends.get_trends.await_count == 2


def test_brief_pack_partial_custom_timeframe_handles_growth_fetch_failure():
    providers = FakeBriefProviders()
    providers.trends.get_growth = AsyncMock(
        side_effect=[ProviderTimeoutError("google_trends", "get_growth"), [
            {"keyword": "ChatGPT", "growth": {"3M": 5.0, "1Y": 8.0}},
        ]]
    )
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--market", "US", "--market", "GB",
            "--timeframe", "today 5-y", "--format", "json", "--allow-partial",
        ])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert [row["market"] for row in payload["markets"]] == ["US", "GB"]
    assert payload["markets"][0]["keywords"][0]["latest_index"] == 80.0
    assert payload["markets"][0]["keywords"][0]["growth_3m_pct"] is None
    assert payload["markets"][1]["keywords"][0]["growth_3m_pct"] == 5.0
    assert any("growth" in warning.lower() for warning in payload["markets"][0]["warnings"])
    assert payload["failed_markets"][0]["component"] == "growth"
    assert payload["failed_markets"][0]["code"] == "provider_timeout"
    assert providers.trends.get_growth.await_count == 2


@pytest.mark.parametrize("output_format", ["json", "markdown"])
def test_brief_pack_partial_growth_rate_limit_preserves_primary_and_stops(output_format):
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(side_effect=providers.trends.get_trends)
    providers.trends.get_growth = AsyncMock(
        side_effect=ProviderRateLimitError("google_trends", "get_growth")
    )
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--market", "US", "--market", "GB",
            "--timeframe", "today 5-y", "--format", output_format, "--allow-partial",
        ])

    assert result.exit_code == 1, result.output
    providers.trends.get_trends.assert_awaited_once()
    providers.trends.get_growth.assert_awaited_once()
    if output_format == "json":
        payload = json.loads(result.output)
        assert payload["incomplete"] is True
        assert [row["market"] for row in payload["markets"]] == ["US"]
        assert payload["markets"][0]["keywords"][0]["latest_index"] == 80.0
        assert payload["markets"][0]["keywords"][0]["growth_3m_pct"] is None
        assert [row["market"] for row in payload["failed_markets"]] == ["US", "GB"]
        assert payload["failed_markets"][0]["component"] == "growth"
        assert payload["failed_markets"][0]["code"] == "provider_rate_limited"
        assert payload["failed_markets"][1]["code"] == "not_attempted_due_to_rate_limit"
    else:
        assert "## US" in result.output and "| ChatGPT | 80 | n/a | n/a |" in result.output
        assert "Growth unavailable" in result.output
        assert "## GB" in result.output and "NOT ATTEMPTED" in result.output
        assert "INCOMPLETE" in result.output


def test_brief_pack_partial_mixed_secondary_errors_preserve_both_primary_markets():
    providers = FakeBriefProviders()
    original_get_trends = providers.trends.get_trends
    providers.trends.get_trends = AsyncMock(side_effect=original_get_trends)
    providers.trends.get_growth = AsyncMock(side_effect=[
        ProviderTimeoutError("google_trends", "get_growth"),
        ProviderRateLimitError("google_trends", "get_growth"),
    ])

    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--market", "US", "--market", "GB",
            "--timeframe", "today 5-y", "--format", "json", "--allow-partial",
        ])

    assert result.exit_code == 1, result.output
    evidence = json.loads(result.output)
    assert evidence["incomplete"] is True
    assert [market["market"] for market in evidence["markets"]] == ["US", "GB"]
    assert [market["keywords"][0]["latest_index"] for market in evidence["markets"]] == [80.0, 60.0]
    for market in evidence["markets"]:
        assert market["keywords"][0]["growth_3m_pct"] is None
        assert market["keywords"][0]["growth_1y_pct"] is None
        assert any("Growth unavailable" in warning for warning in market["warnings"])
    assert [(failure["market"], failure["component"], failure["code"])
            for failure in evidence["failed_markets"]] == [
        ("US", "growth", "provider_timeout"),
        ("GB", "growth", "provider_rate_limited"),
    ]
    assert providers.trends.get_trends.await_count == 2
    assert providers.trends.get_growth.await_count == 2


def test_brief_pack_strict_growth_rate_limit_keeps_fail_fast_behavior():
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(side_effect=providers.trends.get_trends)
    providers.trends.get_growth = AsyncMock(
        side_effect=ProviderRateLimitError("google_trends", "get_growth")
    )
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--market", "US", "--market", "GB",
            "--timeframe", "today 5-y", "--format", "json",
        ])
    assert result.exit_code != 0
    assert not result.output.startswith("{")
    providers.trends.get_trends.assert_awaited_once()
    providers.trends.get_growth.assert_awaited_once()


def test_brief_pack_partial_all_success_keeps_original_json_schema_and_success_exit():
    providers = FakeBriefProviders()
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--market", "US", "--market", "GB",
            "--format", "json", "--allow-partial",
        ])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["schema_version"] == 1
    assert "incomplete" not in payload and "failed_markets" not in payload
    assert len(payload["markets"]) == 2


def test_brief_pack_strict_mode_keeps_fail_fast_json_behavior():
    providers = FakeBriefProviders()
    original = providers.trends.get_trends

    async def get_trends(**kwargs):
        if kwargs["geo"] == "GB":
            raise ProviderRateLimitError("google_trends", "get_trends")
        return await original(**kwargs)

    providers.trends.get_trends = AsyncMock(side_effect=get_trends)
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--market", "US", "--market", "GB",
            "--format", "json",
        ])

    assert result.exit_code != 0
    assert not result.output.startswith("{")
    assert providers.trends.get_trends.await_count == 2


def test_brief_pack_json_excludes_invalid_indices_without_inventing_latest_evidence():
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(return_value=[
        {"date": "2026-09-10", "keyword": "ChatGPT", "value": True},
        {"date": "2026-09-13", "keyword": "Claude", "value": float("nan")},
        {"keyword": "Claude", "value": 50},
        "malformed",
    ])
    providers.trends.get_growth = AsyncMock(return_value=[
        {"keyword": "ChatGPT", "growth": {"3M": float("inf"), "1Y": -11.5}},
        {"keyword": "Claude", "growth": {"3M": True, "1Y": None}},
    ])
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(
            cli_module.cli,
            ["brief-pack", "--keyword", "ChatGPT", "--keyword", "Claude", "--market", "US", "--timeframe", "today 5-y", "--format", "json"],
        )

    assert result.exit_code == 0, result.output
    assert "NaN" not in result.output and "Infinity" not in result.output
    market = json.loads(result.output)["markets"][0]
    assert market["growth_basis"] == "separate_lookback_requests"
    assert market["latest_complete_trends_point"] is None
    assert market["keywords"] == [
        {"keyword": "ChatGPT", "latest_index": None, "latest_observation": None, "growth_3m_pct": None, "growth_1y_pct": -11.5},
        {"keyword": "Claude", "latest_index": None, "latest_observation": None, "growth_3m_pct": None, "growth_1y_pct": None},
    ]
    assert any("malformed Trends rows" in warning for warning in market["warnings"])
    assert any("invalid dates" in warning for warning in market["warnings"])
    assert any("no validated primary" in warning for warning in market["warnings"])
    assert not any("older" in warning for warning in market["warnings"])
    assert any("Excluded 2 Trends observations with invalid relative-interest indices" in warning for warning in market["warnings"])
    assert any("separate Google Trends lookback" in warning for warning in market["warnings"])
    providers.trends.get_growth.assert_awaited_once()


@pytest.mark.parametrize(
    ("error_type", "code"),
    [
        (ProviderRateLimitError, "provider_rate_limited"),
        (ProviderTimeoutError, "provider_timeout"),
        (ProviderUnavailableError, "provider_unavailable"),
    ],
)
@pytest.mark.parametrize("output_format", ["markdown", "json"])
def test_brief_pack_retains_primary_evidence_when_optional_growth_fails(error_type, code, output_format):
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(return_value=[
        {"date": "2026-09-13", "value": 48, "keyword": "ChatGPT"},
    ])
    providers.trends.get_growth = AsyncMock(side_effect=error_type("Google Trends", "get_growth"))
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(
            cli_module.cli,
            ["brief-pack", "--keyword", "ChatGPT", "--market", "US", "--timeframe", "today 5-y", "--format", output_format, "--allow-partial"],
        )

    assert result.exit_code == 1, result.output
    if output_format == "json":
        payload = json.loads(result.output)
        assert payload["incomplete"] is True
        assert payload["failed_markets"][0]["component"] == "growth"
        market = payload["markets"][0]
        assert market["keywords"] == [{
            "keyword": "ChatGPT", "latest_index": 48.0, "latest_observation": "2026-09-13",
            "growth_3m_pct": None, "growth_1y_pct": None,
        }]
        assert any(code in warning and "unavailable" in warning for warning in market["warnings"])
    else:
        assert "| ChatGPT | 48 | n/a | n/a |" in result.output
        assert code in result.output and "growth unavailable" in result.output.lower()
        assert "INCOMPLETE EVIDENCE" in result.output
    providers.trends.get_growth.assert_awaited_once()


def test_brief_pack_growth_failure_is_scoped_to_its_market():
    providers = FakeBriefProviders()
    providers.trends.get_growth = AsyncMock(side_effect=[
        ProviderTimeoutError("Google Trends", "get_growth"),
        [{"keyword": "ChatGPT", "growth": {"3M": 10.0, "1Y": 20.0}}],
    ])
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(
            cli_module.cli,
            ["brief-pack", "--keyword", "ChatGPT", "--market", "US", "--market", "GB", "--timeframe", "today 5-y", "--format", "json", "--allow-partial"],
        )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["incomplete"] is True
    assert payload["failed_markets"][0]["component"] == "growth"
    first, second = payload["markets"]
    assert first["keywords"][0]["growth_3m_pct"] is None
    assert any("provider_timeout" in warning for warning in first["warnings"])
    assert second["keywords"][0]["growth_3m_pct"] == 10.0
    assert second["keywords"][0]["growth_1y_pct"] == 20.0
    assert not any("growth unavailable" in warning for warning in second["warnings"])
    assert providers.trends.get_growth.await_count == 2


@pytest.mark.parametrize("output_format", ["json", "markdown"])
def test_brief_pack_discloses_absent_primary_even_with_separate_growth(output_format):
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(return_value=[])
    providers.trends.get_growth = AsyncMock(return_value=[
        {"keyword": "ChatGPT", "growth": {"3M": 15.0, "1Y": 22.0}},
    ])
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(
            cli_module.cli,
            ["brief-pack", "--keyword", "ChatGPT", "--market", "US",
             "--timeframe", "today 5-y", "--format", output_format],
        )

    assert result.exit_code == 0, result.output
    warning = "ChatGPT: no validated primary Google Trends interest observations in US"
    if output_format == "json":
        market = json.loads(result.output)["markets"][0]
        assert market["keywords"][0] == {
            "keyword": "ChatGPT", "latest_index": None, "latest_observation": None,
            "growth_3m_pct": 15.0, "growth_1y_pct": 22.0,
        }
        assert any(warning in item and "growth" in item for item in market["warnings"])
    else:
        assert warning in result.output
        assert "| ChatGPT | n/a | +15.00% | +22.00% |" in result.output
    providers.trends.get_growth.assert_awaited_once()


@pytest.mark.parametrize("output_format", ["json", "markdown"])
def test_brief_pack_discloses_only_missing_keyword_and_preserves_valid_zero(output_format):
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(return_value=[
        {"date": "2026-09-13", "keyword": "ChatGPT", "value": 0},
        {"date": "2026-09-13", "keyword": "Claude", "value": True},
    ])
    providers.trends.get_growth = AsyncMock(return_value=[
        {"keyword": "ChatGPT", "growth": {"3M": 1.0, "1Y": 2.0}},
        {"keyword": "Claude", "growth": {"3M": 3.0, "1Y": 4.0}},
    ])
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(
            cli_module.cli,
            ["brief-pack", "--keyword", "ChatGPT", "--keyword", "Claude",
             "--market", "US", "--timeframe", "today 5-y", "--format", output_format],
        )

    assert result.exit_code == 0, result.output
    warning = "Claude: no validated primary Google Trends interest observations in US"
    if output_format == "json":
        market = json.loads(result.output)["markets"][0]
        assert market["keywords"][0]["latest_index"] == 0.0
        assert market["keywords"][1]["latest_index"] is None
        assert any(warning in item for item in market["warnings"])
        assert not any("ChatGPT: no validated" in item for item in market["warnings"])
    else:
        assert "| ChatGPT | 0 | +1.00% | +2.00% |" in result.output
        assert "| Claude | n/a | +3.00% | +4.00% |" in result.output
        assert warning in result.output
        assert "ChatGPT: no validated" not in result.output


@pytest.mark.parametrize("output_format", ["json", "markdown"])
def test_brief_pack_uses_latest_valid_interest_when_newer_row_is_invalid(output_format):
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(return_value=[
        {"date": "2026-09-10", "keyword": "ChatGPT", "value": 65},
        {"date": "2026-09-13", "keyword": "ChatGPT", "value": True},
    ])
    providers.trends.get_growth = AsyncMock(return_value=[
        {"keyword": "ChatGPT", "growth": {"3M": 15.0, "1Y": 22.0}},
    ])
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(
            cli_module.cli,
            ["brief-pack", "--keyword", "ChatGPT", "--market", "US",
             "--timeframe", "today 5-y", "--format", output_format],
        )

    assert result.exit_code == 0, result.output
    if output_format == "json":
        market = json.loads(result.output)["markets"][0]
        assert market["keywords"][0] == {
            "keyword": "ChatGPT", "latest_index": 65.0,
            "latest_observation": "2026-09-10",
            "growth_3m_pct": 15.0, "growth_1y_pct": 22.0,
        }
        assert market["latest_complete_trends_point"] == "2026-09-10"
        assert not any("ChatGPT" in warning and "older" in warning for warning in market["warnings"])
    else:
        assert "| ChatGPT | 65 | +15.00% | +22.00% |" in result.output
        assert "Latest complete Trends point: **2026-09-10**" in result.output
        assert "ChatGPT: last observation" not in result.output
    providers.trends.get_growth.assert_awaited_once()


@pytest.mark.parametrize("output_format", ["json", "markdown"])
@pytest.mark.parametrize(
    ("observations", "expected_market_date"),
    [
        (
            [
                {"date": "2026-09-10", "keyword": "ChatGPT", "value": 65},
                {"date": "2026-09-13", "keyword": "ChatGPT", "value": True},
            ],
            "2026-09-10",
        ),
        (
            [
                {"date": "2026-09-10", "keyword": "ChatGPT", "value": 65},
                {"date": "2026-09-13", "keyword": "Unrequested", "value": 85},
            ],
            "2026-09-10",
        ),
        (
            [
                {"date": "2026-09-10", "keyword": "ChatGPT", "value": 65},
                {"date": "2026-09-13", "keyword": "ChatGPT", "value": 0},
            ],
            "2026-09-13",
        ),
        (
            [
                {"date": "2026-09-13", "keyword": "ChatGPT", "value": True},
                {"date": "2026-09-14", "keyword": "Unrequested", "value": 85},
            ],
            None,
        ),
    ],
    ids=["invalid-later", "other-keyword-later", "valid-zero-later", "no-valid-requested"],
)
def test_brief_pack_market_date_uses_valid_requested_observation(
    output_format, observations, expected_market_date,
):
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(return_value=observations)
    providers.trends.get_growth = AsyncMock(return_value=[])
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(
            cli_module.cli,
            ["brief-pack", "--keyword", "ChatGPT", "--market", "US",
             "--timeframe", "today 5-y", "--format", output_format],
        )

    assert result.exit_code == 0, result.output
    if output_format == "json":
        market = json.loads(result.output)["markets"][0]
        assert market["latest_complete_trends_point"] == expected_market_date
    elif expected_market_date is None:
        assert "Latest complete Trends point:" not in result.output
    else:
        assert f"Latest complete Trends point: **{expected_market_date}**" in result.output
    providers.trends.get_growth.assert_awaited_once()


def test_brief_pack_escapes_missing_primary_keyword_in_markdown_warning():
    keyword = "AI |\n<img src=x>"
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(return_value=[])
    providers.trends.get_growth = AsyncMock(return_value=[])
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(
            cli_module.cli,
            ["brief-pack", "--keyword", keyword, "--market", "US", "--timeframe", "today 5-y"],
        )

    assert result.exit_code == 0, result.output
    assert "> AI \\| &lt;img src=x&gt;: no validated primary" in result.output
    assert "<img src=x>" not in result.output


def test_brief_pack_does_not_hide_primary_provider_failure():
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(side_effect=ProviderUnavailableError("Google Trends", "get_trends"))
    providers.trends.get_growth = AsyncMock()
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(
            cli_module.cli,
            ["brief-pack", "--keyword", "ChatGPT", "--market", "US", "--timeframe", "today 5-y", "--format", "json"],
        )

    assert result.exit_code != 0
    assert "Error: provider_unavailable:" in result.output
    assert not result.output.startswith("{")
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


@pytest.mark.parametrize("value", [True, False, -1, -0.5, 100.01, 101])
def test_brief_pack_rejects_invalid_relative_interest_indices(value):
    # A Demand Brief must not present booleans or out-of-range provider values as evidence.
    assert cli_module._brief_value(value) == "n/a"


@pytest.mark.parametrize("value", [True, False])
def test_brief_pack_rejects_boolean_growth_percentages(value):
    assert cli_module._brief_percent(value) == "n/a"


def test_brief_pack_accepts_valid_interest_bounds_and_negative_growth():
    assert cli_module._brief_value(0) == "0"
    assert cli_module._brief_value(100) == "100"
    assert cli_module._brief_percent(-25) == "-25.00%"


def test_brief_pack_omits_malformed_trend_rows_but_preserves_valid_evidence():
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(return_value=[
        None,
        "invalid row",
        {"date": "2026-09-13", "value": 42, "keyword": "ChatGPT"},
    ])
    providers.trends.get_growth = AsyncMock(return_value=[
        {"keyword": "ChatGPT", "growth": {"3M": 5, "1Y": -1}},
    ])
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(
            cli_module.cli,
            ["brief-pack", "--keyword", "ChatGPT", "--market", "US", "--timeframe", "today 5-y"],
        )

    assert result.exit_code == 0, result.output
    assert "Excluded 2 malformed Trends rows" in result.output
    assert "| ChatGPT | 42 | +5.00% | -1.00% |" in result.output


def test_brief_pack_explains_invalid_provider_containers_instead_of_crashing():
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(return_value=None)
    providers.trends.get_growth = AsyncMock(return_value=None)
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(
            cli_module.cli,
            ["brief-pack", "--keyword", "ChatGPT", "--market", "US", "--timeframe", "today 5-y"],
        )

    assert result.exit_code == 0, result.output
    assert "invalid observation container" in result.output
    assert "invalid growth response" in result.output
    assert "Latest complete Trends point" not in result.output
    assert "| ChatGPT | n/a | n/a | n/a |" in result.output


def test_brief_pack_omits_malformed_growth_entries_without_losing_series():
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(return_value=[
        {"date": "2026-09-13", "value": 42, "keyword": "ChatGPT"},
    ])
    providers.trends.get_growth = AsyncMock(return_value=[
        None,
        {"keyword": "ChatGPT", "growth": "malformed growth"},
    ])
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(
            cli_module.cli,
            ["brief-pack", "--keyword", "ChatGPT", "--market", "US", "--timeframe", "today 5-y"],
        )

    assert result.exit_code == 0, result.output
    assert "Excluded 2 malformed growth entries" in result.output
    assert "| ChatGPT | 42 | n/a | n/a |" in result.output


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


@pytest.mark.parametrize("output_format", ["json", "markdown"])
@pytest.mark.parametrize("allow_partial", [False, True])
def test_brief_pack_uses_latest_valid_index_not_later_invalid_value(output_format, allow_partial):
    providers = FakeBriefProviders()
    providers.trends.get_trends = AsyncMock(return_value=[
        {"date": "2026-11-14", "keyword": "ChatGPT", "value": 75},
        {"date": "2026-11-15", "keyword": "ChatGPT", "value": 101},
    ])
    providers.trends.get_growth = AsyncMock(return_value=[])
    args = [
        "brief-pack", "--keyword", "ChatGPT", "--market", "US",
        "--timeframe", "today 5-y", "--format", output_format,
    ]
    if allow_partial:
        args.append("--allow-partial")
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers):
        result = CliRunner().invoke(cli_module.cli, args)

    assert result.exit_code == 0, result.output
    if output_format == "json":
        evidence = json.loads(result.output)
        assert evidence["markets"][0]["latest_complete_trends_point"] == "2026-11-14"
        assert evidence["markets"][0]["keywords"][0]["latest_index"] == 75.0
        assert evidence["markets"][0]["keywords"][0]["latest_observation"] == "2026-11-14"
        assert any(
            "Excluded 1 Trends observation with invalid relative-interest indices" in warning
            for warning in evidence["markets"][0]["warnings"]
        )
    else:
        assert "Latest complete Trends point: **2026-11-14**" in result.output
        assert "| ChatGPT | 75 | n/a | n/a |" in result.output
        assert "2026-11-15" not in result.output
        assert "Excluded 1 Trends observation with invalid relative-interest indices" in result.output
    providers.trends.get_trends.assert_awaited_once()
    providers.trends.get_growth.assert_awaited_once()


def test_brief_pack_excludes_invalid_index_from_default_growth_computation():
    providers = FakeBriefProviders()
    good = {"date": "2026-11-14", "keyword": "ChatGPT", "value": 75}
    providers.trends.get_trends = AsyncMock(return_value=[
        good, {"date": "2026-11-15", "keyword": "ChatGPT", "value": True},
    ])
    providers.trends.get_growth = AsyncMock(
        side_effect=AssertionError("default timeframe must reuse valid points")
    )
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=providers), patch(
        "mcp_trendpulse.cli._growth_from_trend_points",
        return_value=[{"keyword": "ChatGPT", "growth": {"3M": None, "1Y": None}}],
    ) as growth:
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--market", "US",
        ])

    assert result.exit_code == 0, result.output
    assert "| ChatGPT | 75 | n/a | n/a |" in result.output
    growth.assert_called_once_with([good], ["ChatGPT"], ["3M", "1Y"])
    providers.trends.get_growth.assert_not_awaited()


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


def test_brief_pack_rejects_case_variant_duplicate_keywords_without_provider_calls():
    with patch("mcp_trendpulse.cli.get_provider_set") as get_providers:
        result = CliRunner().invoke(
            cli_module.cli,
            ["brief-pack", "--keyword", "TrendPulse", "--keyword", " trendpulse ", "--market", "US"],
        )

    assert result.exit_code == 2
    assert "Keywords must be unique" in result.output
    get_providers.assert_not_called()


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


@pytest.mark.parametrize(
    ("command", "method"),
    [
        (["keyword", "python"], "get_rss_headlines_by_keyword"),
        (["location", "London"], "get_rss_headlines_by_location"),
        (["topic", "TECHNOLOGY"], "get_rss_headlines_by_topic"),
        (["top"], "get_rss_headlines_for_top_news"),
        (["site", "bbc.com"], "get_rss_headlines_by_site"),
    ],
)
def test_cli_rss_json_has_only_labeled_metadata(command, method):
    headline = {
        "title": "=Potential formula", "url": "https://news.google.com/rss/articles/example",
        "meta_site_name": "Example News", "publish_date": "2026-10-25T09:00:00+00:00",
        "meta_data": {"content_level": "rss_headline_only", "source": "google_news_rss"},
        "summary": "forbidden article summary", "text": "forbidden article text",
    }
    provider = AsyncMock(return_value=[headline])
    with (
        patch("mcp_trendpulse.cli.get_provider_set", return_value=SimpleNamespace(
            news=SimpleNamespace(**{method: provider})
        )),
        patch("mcp_trendpulse.cli.BrowserManager", side_effect=AssertionError("no browser")),
        patch("mcp_trendpulse.cli.save_article_to_json", side_effect=AssertionError("no article file")),
    ):
        result = CliRunner().invoke(cli_module.cli, [*command, "--headlines-only", "--format", "json"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report == {
        "schema_version": 1, "source": "google_news_rss",
        "content_level": "rss_headline_only", "count": 1,
        "headlines": [{
            "title": "=Potential formula", "url": headline["url"],
            "publisher": "Example News", "publish_date": headline["publish_date"],
        }],
    }
    provider.assert_awaited_once()


@pytest.mark.parametrize("command", [
    ["keyword", "python"], ["location", "London"], ["topic", "TECHNOLOGY"],
    ["top"], ["site", "bbc.com"],
])
def test_cli_rss_json_requires_headlines_only_without_calling_provider(command):
    with (
        patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("no provider call")),
        patch("mcp_trendpulse.cli.BrowserManager", side_effect=AssertionError("no browser")),
    ):
        result = CliRunner().invoke(cli_module.cli, [*command, "--format", "json"])
    assert result.exit_code == 2
    assert "--format json requires --headlines-only" in result.output


def test_cli_rss_json_empty_is_parseable_and_without_text_footer():
    provider = AsyncMock(return_value=[])
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=SimpleNamespace(
        news=SimpleNamespace(get_rss_headlines_for_top_news=provider)
    )):
        result = CliRunner().invoke(cli_module.cli, ["top", "--headlines-only", "--format", "json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "schema_version": 1, "source": "google_news_rss",
        "content_level": "rss_headline_only", "count": 0, "headlines": [],
    }


def test_cli_rss_json_rejects_mixed_unlabeled_evidence_without_partial_document():
    valid = {
        "title": "Real headline", "url": "https://news.google.com/rss/articles/valid",
        "publish_date": "2026-10-25T09:00:00+00:00",
        "meta_data": {"content_level": "rss_headline_only", "source": "google_news_rss"},
    }
    invalid = {**valid, "meta_data": {"content_level": "article_full", "source": "google_news_rss"}}
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=SimpleNamespace(
        news=SimpleNamespace(get_rss_headlines_by_keyword=AsyncMock(return_value=[valid, invalid]))
    )):
        result = CliRunner().invoke(cli_module.cli, ["keyword", "ai", "--headlines-only", "--format", "json"])
    assert result.exit_code != 0
    assert "Unexpected RSS headline evidence level" in result.output
    assert "schema_version" not in result.output


@pytest.mark.parametrize(
    ("command", "method"),
    [
        (["keyword", "python"], "get_rss_headlines_by_keyword"),
        (["location", "London"], "get_rss_headlines_by_location"),
        (["topic", "TECHNOLOGY"], "get_rss_headlines_by_topic"),
        (["top"], "get_rss_headlines_for_top_news"),
        (["site", "bbc.com"], "get_rss_headlines_by_site"),
    ],
)
def test_cli_rss_csv_spreadsheet_safe_metadata_only(command, method):
    headline = {
        "title": " \t=HYPERLINK(\"https://example.com\")", "url": "https://news.google.com/rss/a",
        "meta_site_name": "+Unsafe publisher", "publish_date": "2026-10-25T09:00:00+00:00",
        "meta_data": {"content_level": "rss_headline_only", "source": "google_news_rss"},
        "summary": "forbidden article summary", "text": "forbidden article text",
    }
    provider = AsyncMock(return_value=[headline])
    with (
        patch("mcp_trendpulse.cli.get_provider_set", return_value=SimpleNamespace(
            news=SimpleNamespace(**{method: provider})
        )),
        patch("mcp_trendpulse.cli.BrowserManager", side_effect=AssertionError("no browser")),
        patch("mcp_trendpulse.cli.save_article_to_json", side_effect=AssertionError("no export")),
    ):
        result = CliRunner().invoke(cli_module.cli, [*command, "--headlines-only", "--format", "csv"])
    assert result.exit_code == 0, result.output
    rows = list(csv.DictReader(io.StringIO(result.output)))
    assert len(rows) == 1
    assert rows[0] == {
        "source": "google_news_rss", "content_level": "rss_headline_only",
        "title": "' \t=HYPERLINK(\"https://example.com\")",
        "url": headline["url"], "publisher": "'+Unsafe publisher",
        "publish_date": headline["publish_date"],
    }
    assert "forbidden" not in result.output
    assert "Found " not in result.output
    provider.assert_awaited_once()


@pytest.mark.parametrize("command", [
    ["keyword", "ai"], ["location", "London"], ["topic", "TECHNOLOGY"],
    ["top"], ["site", "bbc.com"],
])
def test_cli_rss_csv_requires_headline_mode_without_provider_call(command):
    with (
        patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("no provider")),
        patch("mcp_trendpulse.cli.BrowserManager", side_effect=AssertionError("no browser")),
    ):
        result = CliRunner().invoke(cli_module.cli, [*command, "--format", "csv"])
    assert result.exit_code == 2
    assert "--format csv requires --headlines-only" in result.output


def test_cli_rss_csv_empty_result_has_header_and_no_footer():
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=SimpleNamespace(
        news=SimpleNamespace(get_rss_headlines_for_top_news=AsyncMock(return_value=[]))
    )):
        result = CliRunner().invoke(cli_module.cli, ["top", "--headlines-only", "--format", "csv"])
    assert result.exit_code == 0, result.output
    assert list(csv.reader(io.StringIO(result.output))) == [[
        "source", "content_level", "title", "url", "publisher", "publish_date",
    ]]


def test_cli_rss_csv_rejects_unlabeled_evidence_without_partial_output():
    valid = {
        "title": "Valid", "url": "https://news.google.com/rss/a", "publish_date": "2026-10-25",
        "meta_data": {"content_level": "rss_headline_only", "source": "google_news_rss"},
    }
    invalid = {**valid, "meta_data": {"content_level": "article_full", "source": "google_news_rss"}}
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=SimpleNamespace(
        news=SimpleNamespace(get_rss_headlines_by_keyword=AsyncMock(return_value=[valid, invalid]))
    )):
        result = CliRunner().invoke(cli_module.cli, ["keyword", "ai", "--headlines-only", "--format", "csv"])
    assert result.exit_code != 0
    assert "Unexpected RSS headline evidence level" in result.output
    assert "source,content_level,title" not in result.output


@pytest.mark.parametrize(
    ("command", "method"),
    [
        (["keyword", "python"], "get_rss_headlines_by_keyword"),
        (["location", "London"], "get_rss_headlines_by_location"),
        (["topic", "TECHNOLOGY"], "get_rss_headlines_by_topic"),
        (["top"], "get_rss_headlines_for_top_news"),
        (["site", "bbc.com"], "get_rss_headlines_by_site"),
    ],
)
@pytest.mark.parametrize("output_format", ["json", "csv"])
def test_cli_rss_structured_output_file_is_new_utf8_metadata_only(
    command, method, output_format, tmp_path,
):
    headline = {
        "title": "=Potential formula \u00e9", "url": "https://news.google.com/rss/articles/example",
        "meta_site_name": "+Publisher", "publish_date": "2026-11-19T08:00:00+00:00",
        "meta_data": {"source": "google_news_rss", "content_level": "rss_headline_only"},
        "text": "private article text", "summary": "private article summary",
    }
    provider = AsyncMock(return_value=[headline])
    destination = tmp_path / f"headlines.{output_format}"
    with (
        patch("mcp_trendpulse.cli.get_provider_set", return_value=SimpleNamespace(
            news=SimpleNamespace(**{method: provider})
        )),
        patch("mcp_trendpulse.cli.BrowserManager", side_effect=AssertionError("no browser")),
    ):
        result = CliRunner().invoke(cli_module.cli, [
            *command, "--headlines-only", "--format", output_format,
            "--output-file", str(destination),
        ])
    assert result.exit_code == 0, result.output
    assert destination.is_file()
    contents = destination.read_bytes()
    assert not contents.startswith(b"\xef\xbb\xbf")
    assert "private article" not in contents.decode("utf-8")
    assert "Found " not in contents.decode("utf-8")
    if output_format == "json":
        report = json.loads(contents)
        assert report["source"] == "google_news_rss"
        assert report["content_level"] == "rss_headline_only"
        assert report["headlines"][0]["title"] == headline["title"]
    else:
        row, = list(csv.DictReader(io.StringIO(contents.decode("utf-8"))))
        assert row["title"] == "'=Potential formula \u00e9"
        assert row["publisher"] == "'+Publisher"
    assert "=Potential formula" not in result.output
    provider.assert_awaited_once()


@pytest.mark.parametrize("output_format", ["json", "csv"])
def test_cli_rss_structured_output_file_empty_result_is_complete(output_format, tmp_path):
    destination = tmp_path / "empty-export"
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=SimpleNamespace(
        news=SimpleNamespace(get_rss_headlines_for_top_news=AsyncMock(return_value=[]))
    )):
        result = CliRunner().invoke(cli_module.cli, [
            "top", "--headlines-only", "--format", output_format,
            "--output-file", str(destination),
        ])
    assert result.exit_code == 0, result.output
    contents = destination.read_text(encoding="utf-8")
    if output_format == "json":
        assert json.loads(contents)["headlines"] == []
    else:
        assert list(csv.reader(io.StringIO(contents))) == [[
            "source", "content_level", "title", "url", "publisher", "publish_date",
        ]]


@pytest.mark.parametrize("command", [
    ["keyword", "ai"], ["location", "London"], ["topic", "TECHNOLOGY"],
    ["top"], ["site", "bbc.com"],
])
def test_cli_rss_output_file_rejects_unstructured_mode_before_provider(command, tmp_path):
    destination = tmp_path / "not-created.json"
    with patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("no provider")):
        result = CliRunner().invoke(cli_module.cli, [
            *command, "--headlines-only", "--output-file", str(destination),
        ])
    assert result.exit_code == 2
    assert "--output-file requires --format json or csv" in result.output
    assert not destination.exists()


def test_cli_rss_output_file_refuses_overwrite_before_provider(tmp_path):
    destination = tmp_path / "existing.csv"
    destination.write_text("existing content", encoding="utf-8")
    with patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("no provider")):
        result = CliRunner().invoke(cli_module.cli, [
            "top", "--headlines-only", "--format", "csv", "--output-file", str(destination),
        ])
    assert result.exit_code != 0
    assert "new file" in result.output
    assert destination.read_text(encoding="utf-8") == "existing content"


def test_cli_rss_output_file_rejects_missing_parent_before_provider(tmp_path):
    destination = tmp_path / "missing" / "news.json"
    with patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("no provider")):
        result = CliRunner().invoke(cli_module.cli, [
            "top", "--headlines-only", "--format", "json", "--output-file", str(destination),
        ])
    assert result.exit_code != 0
    assert "existing directory" in result.output
    assert not destination.exists()


def test_cli_rss_output_file_invalid_evidence_never_creates_partial_file(tmp_path):
    valid = {
        "title": "Valid", "url": "https://news.google.com/rss/a", "publish_date": "2026-11-19",
        "meta_data": {"content_level": "rss_headline_only", "source": "google_news_rss"},
    }
    invalid = {**valid, "meta_data": {"content_level": "article_full", "source": "google_news_rss"}}
    destination = tmp_path / "news.json"
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=SimpleNamespace(
        news=SimpleNamespace(get_rss_headlines_by_keyword=AsyncMock(return_value=[valid, invalid]))
    )):
        result = CliRunner().invoke(cli_module.cli, [
            "keyword", "ai", "--headlines-only", "--format", "json",
            "--output-file", str(destination),
        ])
    assert result.exit_code != 0
    assert "Unexpected RSS headline evidence level" in result.output
    assert not destination.exists()


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


def _saved_mock_brief(tmp_path):
    target = tmp_path / "brief.json"
    with patch("mcp_trendpulse.cli.get_provider_set", return_value=FakeBriefProviders()):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-pack", "--keyword", "ChatGPT", "--keyword", "Claude",
            "--market", "US", "--market", "GB", "--format", "json",
            "--output-file", str(target),
        ])
    assert result.exit_code == 0, result.output
    return target


def test_brief_review_freshness_flags_stale_primary_evidence_offline(tmp_path):
    evidence = _saved_mock_brief(tmp_path)
    with patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("offline only")):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-review", "--evidence", str(evidence), "--as-of", "2026-09-30",
            "--max-age-days", "7", "--format", "json",
        ])
    assert result.exit_code == 2, result.output
    report = json.loads(result.output)
    assert report["needs_human_review"] is True
    assert report["freshness_policy"] == {"as_of": "2026-09-30", "max_age_days": 7}
    assert all(market["stale_keywords"] == 2 for market in report["markets"])
    assert all(market["future_keywords"] == 0 for market in report["markets"])
    assert "latest_index" not in result.output
    assert report["source_authenticated"] is False


def test_brief_review_freshness_current_evidence_and_saved_csv(tmp_path):
    evidence = _saved_mock_brief(tmp_path)
    saved = tmp_path / "freshness.csv"
    result = CliRunner().invoke(cli_module.cli, [
        "brief-review", "--evidence", str(evidence), "--as-of", "2026-09-20",
        "--max-age-days", "7", "--format", "csv", "--output-file", str(saved),
    ])
    assert result.exit_code == 0, result.output
    rows = list(csv.DictReader(io.StringIO(saved.read_text(encoding="utf-8"))))
    assert len(rows) == 2
    assert all(row["stale_keywords"] == "0" and row["future_keywords"] == "0" for row in rows)
    assert all(row["freshness_as_of"] == "2026-09-20" for row in rows)
    assert all(row["freshness_max_age_days"] == "7" for row in rows)
    assert saved.read_bytes().startswith(b"market,")


def test_brief_review_freshness_future_date_requires_human_review(tmp_path):
    evidence = _saved_mock_brief(tmp_path)
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    payload["markets"][0]["keywords"][0]["latest_observation"] = "2026-10-01"
    evidence.write_text(json.dumps(payload), encoding="utf-8")
    result = CliRunner().invoke(cli_module.cli, [
        "brief-review", "--evidence", str(evidence), "--as-of", "2026-09-30",
        "--max-age-days", "30", "--format", "markdown",
    ])
    assert result.exit_code == 2, result.output
    assert "future" in result.output.lower()
    assert "ChatGPT" in result.output
    assert "not authenticated" in result.output.lower()


@pytest.mark.parametrize("flags", [
    ["--as-of", "2026-09-30"],
    ["--max-age-days", "7"],
    ["--as-of", "2026-02-30", "--max-age-days", "7"],
    ["--as-of", "2026-09-30", "--max-age-days", "-1"],
])
def test_brief_review_freshness_rejects_invalid_policy_without_output(tmp_path, flags):
    evidence = _saved_mock_brief(tmp_path)
    saved = tmp_path / "must-not-exist.txt"
    result = CliRunner().invoke(cli_module.cli, [
        "brief-review", "--evidence", str(evidence), *flags,
        "--output-file", str(saved),
    ])
    assert result.exit_code != 0
    assert not saved.exists()


def test_brief_review_markdown_handoff_escapes_declared_markup_and_stays_offline(tmp_path):
    evidence = _saved_mock_brief(tmp_path)
    data = json.loads(evidence.read_text(encoding="utf-8"))
    data["timeframe"] = 'today | <script>alert("x")</script> **bold**'
    evidence.write_text(json.dumps(data), encoding="utf-8")
    original = evidence.read_bytes()
    with patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("provider called")):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-review", "--evidence", str(evidence), "--format", "markdown",
        ])
    assert result.exit_code == 0, result.output
    assert result.output.startswith("# Saved Demand Brief readiness review")
    assert "| US | 2/2 |" in result.output and "| GB | 2/2 |" in result.output
    assert "not authenticated" in result.output and "not search volume" in result.output
    assert "&lt;script&gt;" in result.output and "<script>" not in result.output
    assert r"\|" in result.output and r"\*\*bold\*\*" in result.output
    assert evidence.read_bytes() == original


def test_brief_review_markdown_failed_market_is_unknown_and_exit_two(tmp_path):
    evidence = _saved_mock_brief(tmp_path)
    data = json.loads(evidence.read_text(encoding="utf-8"))
    data["markets"] = [m for m in data["markets"] if m["market"] != "GB"]
    data["failed_markets"] = [{
        "market": "GB", "component": None, "code": "rate_limited",
        "retryable": True, "message": "private provider details",
    }]
    data["incomplete"] = True
    evidence.write_text(json.dumps(data), encoding="utf-8")
    result = CliRunner().invoke(cli_module.cli, [
        "brief-review", "--evidence", str(evidence), "--format", "markdown",
    ])
    assert result.exit_code == 2, result.output
    assert "| GB | unknown |" in result.output
    assert "rate_limited" in result.output and "private provider details" not in result.output
    assert "NEEDS HUMAN REVIEW" in result.output


def test_brief_compare_markdown_exposes_older_after_and_unknown_without_indices(tmp_path):
    before = _saved_mock_brief(tmp_path)
    earlier = json.loads(before.read_text(encoding="utf-8"))
    for market in earlier["markets"]:
        market["keywords"][0]["keyword"] = "**ChatGPT** | risky"
    before.write_text(json.dumps(earlier), encoding="utf-8")
    later = json.loads(json.dumps(earlier))
    later["markets"][0]["keywords"][0]["latest_observation"] = "2021-01-01"
    later["markets"] = [m for m in later["markets"] if m["market"] != "GB"]
    later["failed_markets"] = [{
        "market": "GB", "component": None, "code": "timeout",
        "retryable": True, "message": "secret error details",
    }]
    later["incomplete"] = True
    after = tmp_path / "after.json"
    after.write_text(json.dumps(later), encoding="utf-8")
    with patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("provider called")):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-compare", "--before", str(before), "--after", str(after),
            "--format", "markdown",
        ])
    assert result.exit_code == 2, result.output
    assert result.output.startswith("# Saved Demand Brief evidence comparison")
    assert "| GB | 2/2 | unknown | unknown |" in result.output
    assert "older in declared after-file" in result.output
    assert r"\*\*ChatGPT\*\* \| risky" in result.output
    assert "NEEDS HUMAN REVIEW" in result.output
    assert "not authenticated" in result.output and "normalized" in result.output
    assert "secret error details" not in result.output


def test_brief_compare_checklist_identifies_offsetting_keyword_changes_offline(tmp_path):
    before = _saved_mock_brief(tmp_path)
    previous = json.loads(before.read_text(encoding="utf-8"))
    us_before = next(m for m in previous["markets"] if m["market"] == "US")
    us_before["keywords"][0]["latest_index"] = None
    us_before["keywords"][0]["latest_observation"] = None
    before.write_text(json.dumps(previous), encoding="utf-8")
    current = json.loads(json.dumps(previous))
    us_after = next(m for m in current["markets"] if m["market"] == "US")
    us_after["keywords"][0]["latest_index"] = 45
    us_after["keywords"][0]["latest_observation"] = "2026-09-20"
    us_after["keywords"][1]["latest_index"] = None
    us_after["keywords"][1]["latest_observation"] = None
    after = tmp_path / "after.json"
    after.write_text(json.dumps(current), encoding="utf-8")
    with patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("provider called")):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-compare", "--before", str(before), "--after", str(after),
            "--format", "checklist",
        ])
    assert result.exit_code == 2, result.output
    assert "# Demand Brief comparison action checklist" in result.output
    assert "US / Claude: Primary evidence lost" in result.output
    assert "US / ChatGPT: Primary evidence gained" in result.output
    assert "GB / Claude: Primary evidence lost" not in result.output
    assert "not authenticated" in result.output
    assert "normalized" in result.output


def test_brief_compare_checklist_failed_market_is_unknown_and_private_error_hidden(tmp_path):
    before = _saved_mock_brief(tmp_path)
    after_data = json.loads(before.read_text(encoding="utf-8"))
    after_data["markets"] = [m for m in after_data["markets"] if m["market"] == "US"]
    after_data["failed_markets"] = [{
        "market": "GB", "component": None, "code": "rate_limited",
        "retryable": True, "message": "private provider failure detail",
    }]
    after_data["incomplete"] = True
    after = tmp_path / "after.json"
    after.write_text(json.dumps(after_data), encoding="utf-8")
    with patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("provider called")):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-compare", "--before", str(before), "--after", str(after),
            "--format", "checklist",
        ])
    assert result.exit_code == 2, result.output
    assert "GB: After-file primary coverage unknown, not zero" in result.output
    assert "rate_limited" in result.output
    assert "Do not bypass provider rate limits" in result.output
    assert "private provider failure detail" not in result.output
    assert "GB / ChatGPT: Primary evidence lost" not in result.output


def test_brief_compare_checklist_freshness_dates_escaped_labels_and_new_file(tmp_path):
    before = _saved_mock_brief(tmp_path)
    previous = json.loads(before.read_text(encoding="utf-8"))
    for market in previous["markets"]:
        market["keywords"][0]["keyword"] = "**Risk** | query"
    before.write_text(json.dumps(previous), encoding="utf-8")
    current = json.loads(json.dumps(previous))
    us_after = next(m for m in current["markets"] if m["market"] == "US")
    us_after["keywords"][0]["latest_observation"] = "2021-01-01"
    us_after["warnings"].append("sensitive warning body")
    after = tmp_path / "after.json"
    after.write_text(json.dumps(current), encoding="utf-8")
    destination = tmp_path / "changes.md"
    args = [
        "brief-compare", "--before", str(before), "--after", str(after),
        "--format", "checklist", "--as-of", "2026-09-30",
        "--max-age-days", "7",
    ]
    with patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("provider called")):
        report = CliRunner().invoke(cli_module.cli, args)
        saved = CliRunner().invoke(cli_module.cli, [*args, "--output-file", str(destination)])
    assert report.exit_code == saved.exit_code == 2
    assert "older primary observation" in report.output
    assert "stale primary observation" in report.output
    assert r"\*\*Risk\*\* \| query" in report.output
    assert "Review 1 saved warning(s)" in report.output
    assert "sensitive warning body" not in report.output
    assert destination.read_bytes() == report.output.encode("utf-8")
    again = CliRunner().invoke(cli_module.cli, [*args, "--output-file", str(destination)])
    assert again.exit_code == 1
    assert destination.read_bytes() == report.output.encode("utf-8")


def test_brief_compare_checklist_clean_evidence_keeps_manual_review_caveat(tmp_path):
    before = _saved_mock_brief(tmp_path)
    after = tmp_path / "after.json"
    after.write_bytes(before.read_bytes())
    result = CliRunner().invoke(cli_module.cli, [
        "brief-compare", "--before", str(before), "--after", str(after),
        "--format", "checklist",
    ])
    assert result.exit_code == 0, result.output
    assert "No primary availability regressions" in result.output
    assert "Independently verify" in result.output
    assert "not authenticated" in result.output


def test_brief_review_valid_saved_two_market_evidence_is_offline(tmp_path):
    target = _saved_mock_brief(tmp_path)
    with patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("unexpected provider call")):
        result = CliRunner().invoke(cli_module.cli, ["brief-review", "--evidence", str(target)])
    assert result.exit_code == 0, result.output
    assert "US: 2/2" in result.output and "GB: 2/2" in result.output
    assert "structurally complete" in result.output
    assert "not authenticated" in result.output
    assert target.exists()


def test_brief_review_missing_primary_observation_exits_with_review_required(tmp_path):
    target = _saved_mock_brief(tmp_path)
    data = json.loads(target.read_text(encoding="utf-8"))
    data["markets"][0]["keywords"][1]["latest_index"] = None
    data["markets"][0]["keywords"][1]["latest_observation"] = None
    target.write_text(json.dumps(data), encoding="utf-8")
    result = CliRunner().invoke(cli_module.cli, ["brief-review", "--evidence", str(target)])
    assert result.exit_code == 2
    assert "US: 1/2" in result.output and "NEEDS HUMAN REVIEW" in result.output


def test_brief_review_checklist_names_missing_primary_keywords_offline(tmp_path):
    target = _saved_mock_brief(tmp_path)
    saved = json.loads(target.read_text(encoding="utf-8"))
    saved["markets"][0]["keywords"][1]["latest_index"] = None
    saved["markets"][0]["keywords"][1]["latest_observation"] = None
    target.write_text(json.dumps(saved), encoding="utf-8")
    with patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("no provider calls")):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-review", "--evidence", str(target), "--format", "checklist",
        ])
    assert result.exit_code == 2, result.output
    assert "# Demand Brief evidence-gap checklist" in result.output
    assert "US / Claude" in result.output
    assert "Missing primary observation" in result.output
    assert "GB / Claude" not in result.output
    assert "not authenticated" in result.output
    assert "search volume" in result.output


def test_brief_review_checklist_failed_market_and_rate_limit_are_not_zeros(tmp_path):
    target = _saved_mock_brief(tmp_path)
    saved = json.loads(target.read_text(encoding="utf-8"))
    saved["markets"] = [m for m in saved["markets"] if m["market"] == "US"]
    saved["failed_markets"] = [{
        "market": "GB", "component": None, "code": "rate_limited",
        "retryable": True, "message": "private provider failure message",
    }]
    saved["incomplete"] = True
    target.write_text(json.dumps(saved), encoding="utf-8")
    result = CliRunner().invoke(cli_module.cli, [
        "brief-review", "--evidence", str(target), "--format", "checklist",
    ])
    assert result.exit_code == 2, result.output
    assert "GB: no primary market evidence" in result.output
    assert "rate_limited" in result.output
    assert "Do not bypass provider rate limits" in result.output
    assert "0/2" not in result.output
    assert "private provider failure message" not in result.output


def test_brief_review_checklist_freshness_and_escaped_keyword(tmp_path):
    target = _saved_mock_brief(tmp_path)
    saved = json.loads(target.read_text(encoding="utf-8"))
    for market in saved["markets"]:
        market["keywords"][0]["keyword"] = "**Risk** | query"
    target.write_text(json.dumps(saved), encoding="utf-8")
    result = CliRunner().invoke(cli_module.cli, [
        "brief-review", "--evidence", str(target), "--format", "checklist",
        "--as-of", "2026-09-30", "--max-age-days", "7",
    ])
    assert result.exit_code == 2, result.output
    assert r"\*\*Risk\*\* \| query" in result.output
    assert "stale primary observation" in result.output
    assert "2026-09-30" in result.output


def test_brief_review_checklist_complete_saves_utf8_without_overwrite(tmp_path):
    target = _saved_mock_brief(tmp_path)
    output = tmp_path / "checklist.md"
    original = target.read_bytes()
    args = ["brief-review", "--evidence", str(target), "--format", "checklist"]
    baseline = CliRunner().invoke(cli_module.cli, args)
    assert baseline.exit_code == 0, baseline.output
    assert "No primary-evidence gaps detected" in baseline.output
    saved = CliRunner().invoke(cli_module.cli, [*args, "--output-file", str(output)])
    assert saved.exit_code == 0
    assert output.read_bytes() == baseline.output.encode("utf-8")
    assert target.read_bytes() == original
    again = CliRunner().invoke(cli_module.cli, [*args, "--output-file", str(output)])
    assert again.exit_code == 1 and output.read_bytes() == baseline.output.encode("utf-8")


def test_brief_review_partial_growth_failure_does_not_hide_primary_evidence(tmp_path):
    target = _saved_mock_brief(tmp_path)
    data = json.loads(target.read_text(encoding="utf-8"))
    data["incomplete"] = True
    data["failed_markets"] = [{
        "market": "GB", "component": "growth", "code": "timeout",
        "retryable": True, "message": "provider timeout",
    }]
    target.write_text(json.dumps(data), encoding="utf-8")
    result = CliRunner().invoke(cli_module.cli, ["brief-review", "--evidence", str(target)])
    assert result.exit_code == 2
    assert "GB: 2/2" in result.output and "growth unavailable" in result.output
    assert "NEEDS HUMAN REVIEW" in result.output


@pytest.mark.parametrize("corruption", ["version", "missing", "boolean", "nan", "duplicate"])
def test_brief_review_rejects_malformed_saved_evidence_without_provider_calls(tmp_path, corruption):
    target = _saved_mock_brief(tmp_path)
    data = json.loads(target.read_text(encoding="utf-8"))
    if corruption == "version":
        data["schema_version"] = 2
    elif corruption == "missing":
        del data["markets"][0]["keywords"][0]["latest_index"]
    elif corruption == "boolean":
        data["markets"][0]["keywords"][0]["latest_index"] = True
    if corruption == "duplicate":
        raw = target.read_text(encoding="utf-8").replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1')
    elif corruption == "nan":
        raw = target.read_text(encoding="utf-8").replace('"schema_version": 1', '"schema_version": NaN')
    else:
        raw = json.dumps(data)
    target.write_text(raw, encoding="utf-8")
    with patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("unexpected provider call")):
        result = CliRunner().invoke(cli_module.cli, ["brief-review", "--evidence", str(target)])
    assert result.exit_code != 0
    assert "review failed" in result.output.lower()


def test_brief_review_rejects_oversized_file_without_loading_entire_input(tmp_path):
    from mcp_trendpulse.brief_review import MAX_EVIDENCE_BYTES

    target = tmp_path / "too-big.json"
    target.write_bytes(b" " * (MAX_EVIDENCE_BYTES + 5))
    result = CliRunner().invoke(cli_module.cli, ["brief-review", "--evidence", str(target)])
    assert result.exit_code != 0
    assert "exceeds 1 MiB" in result.output


def test_brief_review_json_reports_structured_complete_coverage_offline(tmp_path):
    target = _saved_mock_brief(tmp_path)
    before = target.read_bytes()
    with patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("unexpected provider call")):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-review", "--evidence", str(target), "--format", "json",
        ])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["schema_version"] == 1
    assert data["assessment"] == "structurally_complete"
    assert data["needs_human_review"] is False
    assert data["source_authenticated"] is False
    assert data["failed_markets"] == []
    assert [(m["market"], m["observed_keywords"], m["total_keywords"]) for m in data["markets"]] == [
        ("US", 2, 2), ("GB", 2, 2),
    ]
    assert all(m["status"] == "observed" and m["growth_unavailable"] is False for m in data["markets"])
    assert any("not search volume" in caution for caution in data["caveats"])
    assert target.read_bytes() == before


def test_brief_review_json_incomplete_primary_evidence_preserves_exit_two(tmp_path):
    target = _saved_mock_brief(tmp_path)
    data = json.loads(target.read_text(encoding="utf-8"))
    data["markets"][0]["keywords"][1]["latest_index"] = None
    data["markets"][0]["keywords"][1]["latest_observation"] = None
    target.write_text(json.dumps(data), encoding="utf-8")
    result = CliRunner().invoke(cli_module.cli, [
        "brief-review", "--evidence", str(target), "--format", "json",
    ])
    assert result.exit_code == 2
    report = json.loads(result.output)
    assert report["assessment"] == "needs_human_review"
    assert report["needs_human_review"] is True
    assert report["markets"][0]["observed_keywords"] == 1
    assert report["markets"][0]["status"] == "missing_primary_evidence"


def test_brief_review_json_keeps_growth_failure_separate_from_primary_evidence(tmp_path):
    target = _saved_mock_brief(tmp_path)
    data = json.loads(target.read_text(encoding="utf-8"))
    data["incomplete"] = True
    data["failed_markets"] = [{
        "market": "GB", "component": "growth", "code": "timeout",
        "retryable": True, "message": "provider timeout",
    }]
    target.write_text(json.dumps(data), encoding="utf-8")
    result = CliRunner().invoke(cli_module.cli, [
        "brief-review", "--evidence", str(target), "--format", "json",
    ])
    assert result.exit_code == 2
    report = json.loads(result.output)
    assert report["markets"][1]["status"] == "observed"
    assert report["markets"][1]["growth_unavailable"] is True
    assert report["failed_markets"] == [{"market": "GB", "component": "growth", "code": "timeout"}]
    assert "provider timeout" not in result.output


def test_brief_review_csv_exports_offline_market_readiness_without_raw_indices(tmp_path):
    target = _saved_mock_brief(tmp_path)
    document = json.loads(target.read_text(encoding="utf-8"))
    document["timeframe"] = "=HYPERLINK(\"https://example.invalid\")"
    target.write_text(json.dumps(document), encoding="utf-8")
    with patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("provider called")):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-review", "--evidence", str(target), "--format", "csv",
        ])
    assert result.exit_code == 0, result.output
    rows = list(csv.DictReader(io.StringIO(result.output)))
    assert {row["market"] for row in rows} == {"US", "GB"}
    assert all(row["timeframe"].startswith("'=HYPERLINK(") for row in rows)
    assert all(row["observed_keywords"] == row["total_keywords"] == "2" for row in rows)
    assert all(row["source_authenticated"] == "false" for row in rows)
    assert all(row["needs_human_review"] == "false" for row in rows)
    assert all("not search volume" in row["caveats"] for row in rows)
    assert "latest_index" not in result.output and "42.0" not in result.output


def test_brief_review_csv_failed_only_market_preserves_unknown_not_zero(tmp_path):
    target = _saved_mock_brief(tmp_path)
    document = json.loads(target.read_text(encoding="utf-8"))
    document["markets"] = [item for item in document["markets"] if item["market"] == "US"]
    document["failed_markets"] = [{
        "market": "GB", "component": None, "code": "rate_limited",
        "retryable": True, "message": "private provider message",
    }]
    document["incomplete"] = True
    target.write_text(json.dumps(document), encoding="utf-8")
    result = CliRunner().invoke(cli_module.cli, [
        "brief-review", "--evidence", str(target), "--format", "csv",
    ])
    assert result.exit_code == 2, result.output
    rows = {row["market"]: row for row in csv.DictReader(io.StringIO(result.output))}
    assert rows["GB"]["status"] == "no_market_evidence"
    assert rows["GB"]["observed_keywords"] == rows["GB"]["total_keywords"] == ""
    assert rows["GB"]["failure_code"] == "rate_limited"
    assert rows["GB"]["needs_human_review"] == "true"
    assert "private provider message" not in result.output


@pytest.mark.parametrize("output_format", ["text", "json", "csv", "markdown"])
def test_brief_review_can_save_exact_utf8_output_without_provider_calls(tmp_path, output_format):
    evidence = _saved_mock_brief(tmp_path)
    destination = tmp_path / f"review-{output_format}.txt"
    args = ["brief-review", "--evidence", str(evidence), "--format", output_format]
    baseline = CliRunner().invoke(cli_module.cli, args)
    original = evidence.read_bytes()
    with patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("provider called")):
        result = CliRunner().invoke(cli_module.cli, [*args, "--output-file", str(destination)])
    assert baseline.exit_code == result.exit_code == 0, result.output
    assert destination.read_bytes() == baseline.output.encode("utf-8")
    assert evidence.read_bytes() == original
    assert "Wrote Demand Brief review" in result.output


def test_brief_review_csv_saves_incomplete_report_and_refuses_overwrite_or_invalid_input(tmp_path):
    evidence = _saved_mock_brief(tmp_path)
    document = json.loads(evidence.read_text(encoding="utf-8"))
    document["markets"][0]["keywords"][1]["latest_index"] = None
    document["markets"][0]["keywords"][1]["latest_observation"] = None
    evidence.write_text(json.dumps(document), encoding="utf-8")
    target = tmp_path / "review.csv"
    args = ["brief-review", "--evidence", str(evidence), "--format", "csv", "--output-file", str(target)]
    first = CliRunner().invoke(cli_module.cli, args)
    assert first.exit_code == 2, first.output
    assert any(row["needs_human_review"] == "true" for row in csv.DictReader(io.StringIO(target.read_text(encoding="utf-8"))))
    before = target.read_bytes()
    second = CliRunner().invoke(cli_module.cli, args)
    assert second.exit_code == 1 and target.read_bytes() == before
    invalid = tmp_path / "invalid.csv"
    evidence.write_bytes(b"invalid-json")
    third = CliRunner().invoke(cli_module.cli, [*args[:-1], str(invalid)])
    assert third.exit_code == 1 and not invalid.exists()


def test_brief_review_output_file_removes_partial_file_on_write_error(tmp_path):
    evidence = _saved_mock_brief(tmp_path)
    target = tmp_path / "partial-review.csv"
    original_open = Path.open

    class PartialWriter:
        def __enter__(self):
            self.handle = original_open(target, "x", encoding="utf-8", newline="\n")
            return self

        def write(self, content):
            self.handle.write(content[:12])
            raise OSError(errno.ENOSPC, "simulated disk full")

        def __exit__(self, *_):
            self.handle.close()

    def faulting_open(path, mode="r", *args, **kwargs):
        if path == target and mode == "x":
            return PartialWriter()
        return original_open(path, mode, *args, **kwargs)

    with patch.object(Path, "open", new=faulting_open):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-review", "--evidence", str(evidence), "--format", "csv", "--output-file", str(target),
        ])
    assert result.exit_code == 1
    assert "not saved" in result.output.lower()
    assert not target.exists()


@pytest.mark.parametrize("format_name", ["json", "csv", "keyword-csv", "markdown", "text"])
def test_brief_compare_optional_after_freshness_policy_flags_stale_without_provider_calls(tmp_path, format_name):
    before = _saved_mock_brief(tmp_path)
    after = tmp_path / "after.json"
    after.write_bytes(before.read_bytes())
    original = before.read_bytes(), after.read_bytes()
    with patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("offline only")):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-compare", "--before", str(before), "--after", str(after),
            "--as-of", "2026-09-30", "--max-age-days", "7", "--format", format_name,
        ])
    assert result.exit_code == 2, result.output
    if format_name == "json":
        report = json.loads(result.output)
        assert report["freshness_policy"] == {"as_of": "2026-09-30", "max_age_days": 7}
        assert all(len(m["after_freshness_exceptions"]) == 2 for m in report["markets"])
        assert report["needs_human_review"] is True
    else:
        assert "stale" in result.output.lower()
        assert "2026-09-30" in result.output
    assert "latest_index" not in result.output
    assert (before.read_bytes(), after.read_bytes()) == original


def test_brief_compare_current_freshness_and_future_markdown(tmp_path):
    before = _saved_mock_brief(tmp_path)
    after = tmp_path / "after.json"
    record = json.loads(before.read_text(encoding="utf-8"))
    record["markets"][0]["keywords"][0]["latest_observation"] = "2026-10-01"
    after.write_text(json.dumps(record), encoding="utf-8")
    result = CliRunner().invoke(cli_module.cli, [
        "brief-compare", "--before", str(before), "--after", str(after),
        "--as-of", "2026-09-30", "--max-age-days", "30", "--format", "markdown",
    ])
    assert result.exit_code == 2, result.output
    assert "future" in result.output
    assert "ChatGPT" in result.output
    assert "not authenticated" in result.output


def test_brief_compare_after_freshness_failed_provider_remains_unknown(tmp_path):
    before = _saved_mock_brief(tmp_path)
    after = tmp_path / "after.json"
    data = json.loads(before.read_text(encoding="utf-8"))
    data["markets"] = [m for m in data["markets"] if m["market"] != "GB"]
    data["failed_markets"] = [{
        "market": "GB", "component": None, "code": "rate_limited",
        "retryable": True, "message": "private provider detail",
    }]
    data["incomplete"] = True
    after.write_text(json.dumps(data), encoding="utf-8")
    result = CliRunner().invoke(cli_module.cli, [
        "brief-compare", "--before", str(before), "--after", str(after),
        "--as-of", "2026-09-30", "--max-age-days", "7", "--format", "csv",
    ])
    assert result.exit_code == 2, result.output
    rows = {row["market"]: row for row in csv.DictReader(io.StringIO(result.output))}
    assert rows["GB"]["after_observed_keywords"] == ""
    assert rows["GB"]["after_stale_keywords"] == ""
    assert rows["GB"]["after_future_keywords"] == ""
    assert rows["GB"]["after_failure_code"] == "rate_limited"
    assert "private provider detail" not in result.output


@pytest.mark.parametrize("flags", [
    ["--as-of", "2026-09-30"],
    ["--max-age-days", "7"],
    ["--as-of", "2026-02-30", "--max-age-days", "7"],
])
def test_brief_compare_invalid_freshness_rejects_before_output(tmp_path, flags):
    before = _saved_mock_brief(tmp_path)
    after = tmp_path / "after.json"
    after.write_bytes(before.read_bytes())
    target = tmp_path / "never-created.csv"
    result = CliRunner().invoke(cli_module.cli, [
        "brief-compare", "--before", str(before), "--after", str(after),
        *flags, "--format", "csv", "--output-file", str(target),
    ])
    assert result.exit_code != 0
    assert not target.exists()


def test_brief_compare_offline_json_tracks_primary_coverage_without_indices(tmp_path):
    before = _saved_mock_brief(tmp_path)
    after = tmp_path / "after.json"
    evidence = json.loads(before.read_text(encoding="utf-8"))
    evidence["markets"][0]["keywords"][1]["latest_index"] = None
    evidence["markets"][0]["keywords"][1]["latest_observation"] = None
    before.write_text(json.dumps(evidence), encoding="utf-8")
    evidence["markets"][0]["keywords"][1]["latest_index"] = 42
    evidence["markets"][0]["keywords"][1]["latest_observation"] = "2026-11-18"
    after.write_text(json.dumps(evidence), encoding="utf-8")
    original = before.read_bytes(), after.read_bytes()
    with patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("provider called")):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-compare", "--before", str(before), "--after", str(after), "--format", "json",
        ])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["comparison"] == "coverage_only"
    assert report["source_authenticated"] is False
    us = next(m for m in report["markets"] if m["market"] == "US")
    assert us["before"]["observed_keywords"] == 1
    assert us["after"]["observed_keywords"] == 2
    assert us["primary_coverage_change"] == 1
    assert "42" not in result.output  # No relative-interest index comparison
    assert any("not compare" in caveat for caveat in report["caveats"])
    assert (before.read_bytes(), after.read_bytes()) == original


def test_brief_compare_current_missing_evidence_preserves_exit_two(tmp_path):
    before = _saved_mock_brief(tmp_path)
    after = tmp_path / "after.json"
    evidence = json.loads(before.read_text(encoding="utf-8"))
    evidence["markets"][1]["keywords"][0]["latest_index"] = None
    evidence["markets"][1]["keywords"][0]["latest_observation"] = None
    after.write_text(json.dumps(evidence), encoding="utf-8")
    result = CliRunner().invoke(cli_module.cli, [
        "brief-compare", "--before", str(before), "--after", str(after),
    ])
    assert result.exit_code == 2
    assert "GB: 2/2 -> 1/2" in result.output
    assert "current snapshot needs human review" in result.output.lower()


def test_brief_compare_flags_regressed_observation_dates_even_with_complete_coverage(tmp_path):
    before = _saved_mock_brief(tmp_path)
    after = tmp_path / "after.json"
    earlier = json.loads(before.read_text(encoding="utf-8"))
    earlier["markets"][0]["keywords"][0]["latest_observation"] = "2026-11-18"
    before.write_text(json.dumps(earlier), encoding="utf-8")
    later = json.loads(json.dumps(earlier))
    later["markets"][0]["keywords"][0]["latest_observation"] = "2026-11-17"
    after.write_text(json.dumps(later), encoding="utf-8")
    original = before.read_bytes(), after.read_bytes()

    with patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("provider called")):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-compare", "--before", str(before), "--after", str(after), "--format", "json",
        ])
    assert result.exit_code == 2, result.output
    report = json.loads(result.output)
    assert report["needs_human_review"] is True
    us = next(item for item in report["markets"] if item["market"] == "US")
    assert us["primary_coverage_change"] == 0
    assert us["older_observations"] == [
        {"keyword": "ChatGPT", "before_date": "2026-11-18", "after_date": "2026-11-17"}
    ]
    assert report["source_authenticated"] is False
    assert (before.read_bytes(), after.read_bytes()) == original
    text_result = CliRunner().invoke(cli_module.cli, [
        "brief-compare", "--before", str(before), "--after", str(after),
    ])
    assert text_result.exit_code == 2
    assert "ChatGPT 2026-11-18 -> 2026-11-17 (review)" in text_result.output
    assert "declared observation dates regressed" in text_result.output


def test_brief_compare_date_regression_csv_is_unknown_for_missing_market_and_timestamps(tmp_path):
    before = _saved_mock_brief(tmp_path)
    after = tmp_path / "after.json"
    earlier = json.loads(before.read_text(encoding="utf-8"))
    earlier["markets"][0]["keywords"][0]["latest_observation"] = "2026-11-18"
    earlier["markets"][0]["keywords"][1]["latest_observation"] = "2026-11-18T18:00:00+01:00"
    before.write_text(json.dumps(earlier), encoding="utf-8")
    later = json.loads(json.dumps(earlier))
    later["markets"][0]["keywords"][0]["latest_observation"] = "2026-11-17"
    later["markets"][0]["keywords"][1]["latest_observation"] = "2026-11-17T20:00:00Z"
    later["markets"] = [market for market in later["markets"] if market["market"] != "GB"]
    later["failed_markets"] = [{
        "market": "GB", "component": None, "code": "rate_limited",
        "retryable": True, "message": "private provider error",
    }]
    later["incomplete"] = True
    after.write_text(json.dumps(later), encoding="utf-8")

    result = CliRunner().invoke(cli_module.cli, [
        "brief-compare", "--before", str(before), "--after", str(after), "--format", "keyword-csv",
    ])
    assert result.exit_code == 2, result.output
    rows = list(csv.DictReader(io.StringIO(result.output)))
    us = {row["keyword"]: row for row in rows if row["market"] == "US"}
    assert us["ChatGPT"]["observation_date_change"] == "older_after"
    assert us["Claude"]["observation_date_change"] == "unknown"
    assert all(row["observation_date_change"] == "unknown" for row in rows if row["market"] == "GB")
    assert "private provider error" not in result.output
    market_result = CliRunner().invoke(cli_module.cli, [
        "brief-compare", "--before", str(before), "--after", str(after), "--format", "csv",
    ])
    assert market_result.exit_code == 2
    market_rows = {row["market"]: row for row in csv.DictReader(io.StringIO(market_result.output))}
    assert market_rows["US"]["older_observation_keyword_count"] == "1"
    assert market_rows["GB"]["older_observation_keyword_count"] == ""


@pytest.mark.parametrize("later_date, expected", [
    ("2026-11-18", "unchanged"),
    ("2026-11-19", "newer_after"),
    ("2026-11-17T23:00:00Z", "unknown"),
])
def test_brief_compare_does_not_flag_nonregressed_or_mixed_precision_dates(tmp_path, later_date, expected):
    before = _saved_mock_brief(tmp_path)
    after = tmp_path / "after.json"
    earlier = json.loads(before.read_text(encoding="utf-8"))
    earlier["markets"][0]["keywords"][0]["latest_observation"] = "2026-11-18"
    before.write_text(json.dumps(earlier), encoding="utf-8")
    later = json.loads(json.dumps(earlier))
    later["markets"][0]["keywords"][0]["latest_observation"] = later_date
    after.write_text(json.dumps(later), encoding="utf-8")
    result = CliRunner().invoke(cli_module.cli, [
        "brief-compare", "--before", str(before), "--after", str(after), "--format", "keyword-csv",
    ])
    assert result.exit_code == 0, result.output
    rows = list(csv.DictReader(io.StringIO(result.output)))
    row = next(row for row in rows if row["market"] == "US" and row["keyword"] == "ChatGPT")
    assert row["observation_date_change"] == expected
    assert row["needs_human_review"] == "false"


@pytest.mark.parametrize("mismatch", ["timeframe", "keywords", "market"])
def test_brief_compare_rejects_incompatible_snapshot_scopes(tmp_path, mismatch):
    before = _saved_mock_brief(tmp_path)
    after = tmp_path / "after.json"
    evidence = json.loads(before.read_text(encoding="utf-8"))
    if mismatch == "timeframe":
        evidence["timeframe"] = "today 3-m"
    elif mismatch == "keywords":
        for market in evidence["markets"]:
            market["keywords"][0]["keyword"] = "Different phrase"
    else:
        evidence["markets"][0]["market"] = "CA"
    after.write_text(json.dumps(evidence), encoding="utf-8")
    result = CliRunner().invoke(cli_module.cli, [
        "brief-compare", "--before", str(before), "--after", str(after),
    ])
    assert result.exit_code == 1
    assert "not comparable" in result.output.lower()


def test_brief_compare_rejects_oversized_snapshot_and_invalid_duplicate_json(tmp_path):
    from mcp_trendpulse.brief_review import MAX_EVIDENCE_BYTES

    before = _saved_mock_brief(tmp_path)
    after = tmp_path / "after.json"
    after.write_bytes(b" " * (MAX_EVIDENCE_BYTES + 1))
    result = CliRunner().invoke(cli_module.cli, [
        "brief-compare", "--before", str(before), "--after", str(after),
    ])
    assert result.exit_code == 1 and "exceeds 1 MiB" in result.output
    after.write_text(before.read_text(encoding="utf-8").replace(
        '"schema_version": 1', '"schema_version": 1, "schema_version": 1'
    ), encoding="utf-8")
    result = CliRunner().invoke(cli_module.cli, [
        "brief-compare", "--before", str(before), "--after", str(after),
    ])
    assert result.exit_code == 1 and "Duplicate JSON key" in result.output


def test_brief_compare_primary_provider_failure_does_not_fabricate_delta(tmp_path):
    before = _saved_mock_brief(tmp_path)
    after = tmp_path / "after.json"
    evidence = json.loads(before.read_text(encoding="utf-8"))
    evidence["markets"] = [market for market in evidence["markets"] if market["market"] != "GB"]
    evidence["failed_markets"] = [{
        "market": "GB", "component": None, "code": "rate_limited",
        "retryable": True, "message": "private provider error message",
    }]
    evidence["incomplete"] = True
    after.write_text(json.dumps(evidence), encoding="utf-8")
    result = CliRunner().invoke(cli_module.cli, [
        "brief-compare", "--before", str(before), "--after", str(after), "--format", "json",
    ])
    assert result.exit_code == 2
    report = json.loads(result.output)
    gb = next(m for m in report["markets"] if m["market"] == "GB")
    assert gb["before"]["observed_keywords"] == 2
    assert gb["after"]["observed_keywords"] is None
    assert gb["after"]["failure_code"] == "rate_limited"
    assert gb["primary_coverage_change"] is None
    assert "private provider error message" not in result.output


def test_brief_compare_csv_exports_safe_market_coverage_without_provider_calls(tmp_path):
    before = _saved_mock_brief(tmp_path)
    after = tmp_path / "after.json"
    evidence = json.loads(before.read_text(encoding="utf-8"))
    evidence["timeframe"] = "  =HYPERLINK(\"https://unsafe.example\")"
    evidence["markets"][0]["keywords"][1]["latest_index"] = None
    evidence["markets"][0]["keywords"][1]["latest_observation"] = None
    before.write_text(json.dumps(evidence), encoding="utf-8")
    evidence["markets"][0]["keywords"][1]["latest_index"] = 42
    evidence["markets"][0]["keywords"][1]["latest_observation"] = "2026-11-18"
    after.write_text(json.dumps(evidence), encoding="utf-8")
    originals = before.read_bytes(), after.read_bytes()
    with patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("provider called")):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-compare", "--before", str(before), "--after", str(after), "--format", "csv",
        ])
    assert result.exit_code == 0, result.output
    rows = list(csv.DictReader(io.StringIO(result.output)))
    assert [row["market"] for row in rows] == ["GB", "US"]
    us = rows[1]
    assert us["before_observed_keywords"] == "1"
    assert us["after_observed_keywords"] == "2"
    assert us["primary_coverage_change"] == "1"
    assert us["timeframe"].lstrip().startswith("'=")
    assert us["source_authenticated"] == "false"
    assert us["needs_human_review"] == "false"
    assert "normalized" in us["caveats"].lower()
    assert "42" not in result.output
    assert (before.read_bytes(), after.read_bytes()) == originals


def test_brief_compare_csv_preserves_partial_exit_and_unknown_delta(tmp_path):
    before = _saved_mock_brief(tmp_path)
    after = tmp_path / "after.json"
    evidence = json.loads(before.read_text(encoding="utf-8"))
    evidence["markets"] = [m for m in evidence["markets"] if m["market"] != "GB"]
    evidence["failed_markets"] = [{
        "market": "GB", "component": None, "code": "rate_limited",
        "retryable": True, "message": "private error data",
    }]
    evidence["incomplete"] = True
    after.write_text(json.dumps(evidence), encoding="utf-8")
    result = CliRunner().invoke(cli_module.cli, [
        "brief-compare", "--before", str(before), "--after", str(after), "--format", "csv",
    ])
    assert result.exit_code == 2
    rows = list(csv.DictReader(io.StringIO(result.output)))
    gb = next(row for row in rows if row["market"] == "GB")
    assert gb["before_observed_keywords"] == "2"
    assert gb["after_observed_keywords"] == ""
    assert gb["primary_coverage_change"] == ""
    assert gb["after_failure_code"] == "rate_limited"
    assert gb["needs_human_review"] == "true"
    assert "private error data" not in result.output


def test_brief_compare_keyword_csv_exposes_offsetting_primary_coverage_changes(tmp_path):
    before = _saved_mock_brief(tmp_path)
    after = tmp_path / "after.json"
    baseline = json.loads(before.read_text(encoding="utf-8"))
    earlier = json.loads(json.dumps(baseline))
    earlier["markets"][0]["keywords"][0]["latest_index"] = None
    earlier["markets"][0]["keywords"][0]["latest_observation"] = None
    before.write_text(json.dumps(earlier), encoding="utf-8")
    later = json.loads(json.dumps(baseline))
    later["markets"][0]["keywords"][1]["latest_index"] = None
    later["markets"][0]["keywords"][1]["latest_observation"] = None
    after.write_text(json.dumps(later), encoding="utf-8")
    original = before.read_bytes(), after.read_bytes()
    with patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("provider called")):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-compare", "--before", str(before), "--after", str(after), "--format", "keyword-csv",
        ])
    assert result.exit_code == 2, result.output
    rows = list(csv.DictReader(io.StringIO(result.output)))
    assert len(rows) == 4
    us = {row["keyword"]: row for row in rows if row["market"] == "US"}
    assert us["ChatGPT"]["primary_availability_change"] == "gained"
    assert us["Claude"]["primary_availability_change"] == "lost"
    assert us["ChatGPT"]["before_primary_available"] == "false"
    assert us["ChatGPT"]["after_primary_available"] == "true"
    assert all(row["source_authenticated"] == "false" for row in rows)
    assert all("normalized" in row["caveats"] for row in rows)
    assert "42" not in result.output
    assert (before.read_bytes(), after.read_bytes()) == original


def test_brief_compare_keyword_csv_preserves_unknown_and_escapes_formula_labels(tmp_path):
    before = _saved_mock_brief(tmp_path)
    after = tmp_path / "after.json"
    earlier = json.loads(before.read_text(encoding="utf-8"))
    for market in earlier["markets"]:
        market["keywords"][0]["keyword"] = '=HYPERLINK("https://example.test")'
    before.write_text(json.dumps(earlier), encoding="utf-8")
    later = json.loads(json.dumps(earlier))
    later["markets"] = [market for market in later["markets"] if market["market"] != "GB"]
    later["failed_markets"] = [{
        "market": "GB", "component": None, "code": "rate_limited",
        "retryable": True, "message": "private provider message",
    }]
    later["incomplete"] = True
    after.write_text(json.dumps(later), encoding="utf-8")
    result = CliRunner().invoke(cli_module.cli, [
        "brief-compare", "--before", str(before), "--after", str(after), "--format", "keyword-csv",
    ])
    assert result.exit_code == 2, result.output
    rows = list(csv.DictReader(io.StringIO(result.output)))
    gb = [row for row in rows if row["market"] == "GB"]
    assert len(gb) == 2
    assert all(row["primary_availability_change"] == "unknown" for row in gb)
    assert all(row["after_primary_available"] == "" for row in gb)
    assert all(row["after_failure_code"] == "rate_limited" for row in gb)
    assert any(row["keyword"].startswith("'=HYPERLINK(") for row in rows)
    assert "private provider message" not in result.output


@pytest.mark.parametrize("output_format", ["text", "json", "csv", "keyword-csv", "markdown"])
def test_brief_compare_can_save_exact_utf8_output_without_provider_calls(tmp_path, output_format):
    before = _saved_mock_brief(tmp_path)
    after = tmp_path / "after.json"
    after.write_bytes(before.read_bytes())
    target = tmp_path / f"comparison-{output_format}.txt"
    args = ["brief-compare", "--before", str(before), "--after", str(after),
            "--format", output_format]
    baseline = CliRunner().invoke(cli_module.cli, args)
    originals = before.read_bytes(), after.read_bytes()
    with patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("provider called")):
        result = CliRunner().invoke(cli_module.cli, [*args, "--output-file", str(target)])
    assert baseline.exit_code == result.exit_code == 0, result.output
    assert target.read_bytes() == baseline.output.encode("utf-8")
    assert (before.read_bytes(), after.read_bytes()) == originals
    assert "Wrote Demand Brief comparison" in result.output


def test_brief_compare_saves_incomplete_report_but_retains_exit_two(tmp_path):
    before = _saved_mock_brief(tmp_path)
    after = tmp_path / "after.json"
    document = json.loads(before.read_text(encoding="utf-8"))
    document["markets"][0]["keywords"][0]["latest_index"] = None
    document["markets"][0]["keywords"][0]["latest_observation"] = None
    after.write_text(json.dumps(document), encoding="utf-8")
    target = tmp_path / "review.csv"
    result = CliRunner().invoke(cli_module.cli, [
        "brief-compare", "--before", str(before), "--after", str(after),
        "--format", "csv", "--output-file", str(target),
    ])
    assert result.exit_code == 2, result.output
    rows = list(csv.DictReader(io.StringIO(target.read_text(encoding="utf-8"))))
    assert next(row for row in rows if row["market"] == "US")["needs_human_review"] == "true"


def test_brief_compare_output_file_refuses_overwrite_and_invalid_input(tmp_path):
    before = _saved_mock_brief(tmp_path)
    after = tmp_path / "after.json"
    after.write_bytes(before.read_bytes())
    target = tmp_path / "comparison.csv"
    target.write_bytes(b"OWNER DATA")
    args = ["brief-compare", "--before", str(before), "--after", str(after),
            "--format", "csv", "--output-file", str(target)]
    result = CliRunner().invoke(cli_module.cli, args)
    assert result.exit_code == 1
    assert target.read_bytes() == b"OWNER DATA"
    missing = tmp_path / "not-created.csv"
    evidence = json.loads(after.read_text(encoding="utf-8"))
    evidence["timeframe"] = "today 3-m"
    after.write_text(json.dumps(evidence), encoding="utf-8")
    result = CliRunner().invoke(cli_module.cli, [*args[:-1], str(missing)])
    assert result.exit_code == 1
    assert not missing.exists()


def test_brief_compare_output_file_removes_its_partial_file_on_write_error(tmp_path):
    before = _saved_mock_brief(tmp_path)
    after = tmp_path / "after.json"
    after.write_bytes(before.read_bytes())
    target = tmp_path / "interrupted.csv"
    original_open = Path.open

    class PartialWriter:
        def __enter__(self):
            self.handle = original_open(target, "x", encoding="utf-8", newline="\n")
            return self

        def write(self, content):
            self.handle.write(content[:12])
            raise OSError(errno.ENOSPC, "simulated disk full")

        def __exit__(self, *_):
            self.handle.close()

    def faulting_open(path, mode="r", *args, **kwargs):
        if path == target and mode == "x":
            return PartialWriter()
        return original_open(path, mode, *args, **kwargs)

    with patch.object(Path, "open", new=faulting_open):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-compare", "--before", str(before), "--after", str(after),
            "--format", "csv", "--output-file", str(target),
        ])
    assert result.exit_code == 1
    assert "not saved" in result.output.lower()
    assert not target.exists()


def test_brief_audit_multi_file_json_distinguishes_unknown_market_offline(tmp_path):
    good = _saved_mock_brief(tmp_path)
    incomplete = tmp_path / "incomplete.json"
    saved = json.loads(good.read_text(encoding="utf-8"))
    saved["markets"] = [saved["markets"][0]]
    saved["failed_markets"] = [{
        "market": "GB", "component": None, "code": "rate_limited",
        "retryable": True, "message": "private upstream failure body",
    }]
    saved["incomplete"] = True
    incomplete.write_text(json.dumps(saved), encoding="utf-8")
    with patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("provider called")):
        result = CliRunner().invoke(cli_module.cli, [
            "brief-audit", "--evidence", str(good), "--evidence", str(incomplete),
            "--format", "json",
        ])
    assert result.exit_code == 2, result.output
    report = json.loads(result.output)
    assert report["schema_version"] == 1
    assert report["summary"] == {"files": 2, "structurally_complete": 1, "needs_human_review": 1}
    assert report["files"][0]["primary_responded_coverage"] == "4/4"
    assert report["files"][1]["failed_market_count"] == 1
    assert report["files"][1]["market_coverage"] == "partial_unknown"
    assert report["source_authenticated"] is False
    assert "private upstream failure body" not in result.output


def test_brief_audit_csv_escapes_untrusted_filename_and_never_infers_volume(tmp_path):
    good = _saved_mock_brief(tmp_path)
    renamed = tmp_path / "=financial.csv.json"
    renamed.write_bytes(good.read_bytes())
    result = CliRunner().invoke(cli_module.cli, [
        "brief-audit", "--evidence", str(renamed), "--format", "csv",
    ])
    assert result.exit_code == 0, result.output
    assert "'=financial.csv.json" in result.output
    assert "search volume" in result.output
    assert "4/4" in result.output


def test_brief_audit_all_failed_markets_have_unknown_not_zero_coverage(tmp_path):
    good = _saved_mock_brief(tmp_path)
    saved = json.loads(good.read_text(encoding="utf-8"))
    saved["markets"] = []
    saved["failed_markets"] = [
        {"market": code, "component": None, "code": "unavailable",
         "retryable": True, "message": "private details"}
        for code in ("US", "GB")
    ]
    saved["incomplete"] = True
    good.write_text(json.dumps(saved), encoding="utf-8")
    result = CliRunner().invoke(cli_module.cli, [
        "brief-audit", "--evidence", str(good), "--format", "json",
    ])
    assert result.exit_code == 2, result.output
    item = json.loads(result.output)["files"][0]
    assert item["market_coverage"] == "partial_unknown"
    assert item["primary_responded_coverage"] == "unknown"
    assert item["failed_market_count"] == 2


def test_brief_audit_markdown_reports_stale_evidence_and_escapes_names(tmp_path):
    good = _saved_mock_brief(tmp_path)
    unsafe = tmp_path / "#risk#.json"
    unsafe.write_bytes(good.read_bytes())
    result = CliRunner().invoke(cli_module.cli, [
        "brief-audit", "--evidence", str(unsafe), "--format", "markdown",
        "--as-of", "2026-11-19", "--max-age-days", "1",
    ])
    assert result.exit_code == 2, result.output
    assert "\\#risk\\#\\.json" in result.output
    assert "freshness" in result.output.lower()
    assert "not authenticated" in result.output


def test_brief_audit_rejects_duplicate_invalid_and_overlimit_without_writing(tmp_path):
    good = _saved_mock_brief(tmp_path)
    output = tmp_path / "audit.csv"
    duplicate = CliRunner().invoke(cli_module.cli, [
        "brief-audit", "--evidence", str(good), "--evidence", str(good),
        "--format", "csv", "--output-file", str(output),
    ])
    assert duplicate.exit_code == 1 and "duplicate" in duplicate.output.lower()
    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"schema_version":1}', encoding="utf-8")
    bad = CliRunner().invoke(cli_module.cli, [
        "brief-audit", "--evidence", str(good), "--evidence", str(invalid),
        "--format", "csv", "--output-file", str(output),
    ])
    assert bad.exit_code == 1 and "evidence #2" in bad.output
    assert not output.exists()
    too_many = CliRunner().invoke(cli_module.cli, [
        "brief-audit", *[item for _ in range(13) for item in ("--evidence", str(good))],
    ])
    assert too_many.exit_code == 1 and "12" in too_many.output


def test_brief_audit_writes_utf8_new_file_and_refuses_overwrite(tmp_path):
    good = _saved_mock_brief(tmp_path)
    second = tmp_path / "second.json"
    second.write_bytes(good.read_bytes())
    output = tmp_path / "audit.json"
    args = ["brief-audit", "--evidence", str(good), "--evidence", str(second),
            "--format", "json", "--output-file", str(output)]
    result = CliRunner().invoke(cli_module.cli, args)
    assert result.exit_code == 0, result.output
    assert output.read_bytes().startswith(b'{')
    assert len(json.loads(output.read_text(encoding="utf-8"))["files"]) == 2
    again = CliRunner().invoke(cli_module.cli, args)
    assert again.exit_code == 1
    assert len(json.loads(output.read_text(encoding="utf-8"))["files"]) == 2
