"""M01 Google Trending Now RSS: provider reuse, safety, caching, and coverage."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from click.testing import CliRunner

from mcp_trendpulse import intelligence_rss
from mcp_trendpulse.cli import cli
from mcp_trendpulse.errors import ProviderRateLimitError, ProviderUnavailableError
from mcp_trendpulse.intelligence_core import BudgetCache
from mcp_trendpulse.intelligence_signal import TrendSignal

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
START = int(datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc).timestamp())


class FakeTrends:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    async def get_trending_terms(self, geo="US", full_data=False):
        self.calls.append((geo, full_data))
        if isinstance(self.rows, Exception):
            raise self.rows
        return self.rows


def row(term="Umetna inteligenca", volume="2K+", *, started=START, news=None):
    return {
        "keyword": term, "volume": volume, "started": started,
        "news": news if news is not None else [{
            "title": "AI &amp; tech news", "url": "https://example.org/story",
            "source": "Example &amp; Co",
        }],
    }


@pytest.mark.asyncio
async def test_two_independent_countries_keep_feed_language_unknown(tmp_path):
    store = BudgetCache(tmp_path)
    us = FakeTrends([row("AI agents", "10K+")])
    gb = FakeTrends([row("agent workflows", "500+")])
    first = await intelligence_rss.discover_trending_rss(
        "US", execute=True, cache=store, provider=us, observed_at=NOW,
    )
    second = await intelligence_rss.discover_trending_rss(
        "GB", execute=True, cache=store, provider=gb, observed_at=NOW,
    )
    for output, geo, provider in ((first, "US", us), (second, "GB", gb)):
        assert output["status"] == "observed"
        assert provider.calls == [(geo, True)]
        assert output["site_property_required"] is False
        assert output["country"] == geo and output["language"] is None
        assert output["source_url"].endswith("?geo=" + geo)
        assert output["source_requests_performed"] == 1
        assert output["network_performed"] is True
        signal = TrendSignal.model_validate(output["trends"][0]["signal"])
        assert signal.country == geo and signal.language is None
        assert signal.metric_unit == "approximate_search_bucket"
        assert signal.value is None
        assert signal.provenance.method == "public_rss"
        assert signal.provenance.is_observed_search_query is False
        assert signal.published_at == datetime.fromtimestamp(START, tz=timezone.utc)


@pytest.mark.asyncio
async def test_durable_cache_same_country_repeated_run_never_refetches(tmp_path):
    store = BudgetCache(tmp_path)
    provider = FakeTrends([row()])
    first = await intelligence_rss.discover_trending_rss(
        "US", execute=True, cache=store, provider=provider, observed_at=NOW,
    )
    repeated = await intelligence_rss.discover_trending_rss(
        "US", execute=True, cache=BudgetCache(tmp_path),
        provider=provider, observed_at=NOW,
    )
    assert len(provider.calls) == 1
    assert not first["cache_hit"] and repeated["cache_hit"]
    assert first["trends"] == repeated["trends"]
    assert first["observed_at"] == repeated["observed_at"]
    assert repeated["network_performed"] is False
    assert repeated["source_requests_performed"] == 0


@pytest.mark.asyncio
async def test_same_day_duplicate_titles_preserve_first_label_and_no_numeric_volume(tmp_path):
    provider = FakeTrends([row("  AI  agents ", "2K+"),
                           row("ai agents", "500+"), row("Different", "100+")])
    result = await intelligence_rss.discover_trending_rss(
        "US", execute=True, cache=BudgetCache(tmp_path),
        provider=provider, observed_at=NOW,
    )
    assert result["records_observed"] == 2
    assert result["duplicates_removed"] == 1
    assert result["trends"][0]["signal"]["raw_term"] == "AI agents"
    assert result["trends"][0]["signal"]["normalized_term"] == "ai agents"
    assert result["trends"][0]["signal"]["value"] is None
    assert result["trends"][0]["signal"]["value_label"] == "2K+"


@pytest.mark.asyncio
async def test_source_escapes_news_and_drops_insecure_or_secret_url(tmp_path):
    provider = FakeTrends([row(news=[
        {"title": "Private", "url": "https://example.org/?api_key=SECRET"},
        {"title": "Unsafe", "url": "javascript:alert(1)"},
        {"title": "Safe &amp; public", "url": "https://example.org/ok",
         "source": "Publisher &amp; News"},
        {"title": "Safe &amp; public", "url": "https://example.org/ok"},
    ])])
    result = await intelligence_rss.discover_trending_rss(
        "US", execute=True, cache=BudgetCache(tmp_path),
        provider=provider, observed_at=NOW,
    )
    news = result["trends"][0]["related_news"]
    assert news == [{"title": "Safe & public", "url": "https://example.org/ok",
                     "source": "Publisher & News"}]
    assert "SECRET" not in json.dumps(result)


@pytest.mark.asyncio
async def test_no_date_does_not_invent_feed_publication_time(tmp_path):
    provider = FakeTrends([row(started=None)])
    result = await intelligence_rss.discover_trending_rss(
        "US", execute=True, cache=BudgetCache(tmp_path),
        provider=provider, observed_at=NOW,
    )
    item = result["trends"][0]["signal"]
    assert item["published_at"] is None
    assert item["period"]["start_date"] == NOW.date().isoformat()


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_rows", [
    None, {"unexpected": "error"}, "malformed XML",
    [{"volume": "500+"}], [row(volume="NaN")], [row(term="")],
])
async def test_bad_or_malformed_rss_never_becomes_zero_demand(tmp_path, bad_rows):
    result = await intelligence_rss.discover_trending_rss(
        "US", execute=True, cache=BudgetCache(tmp_path),
        provider=FakeTrends(bad_rows), observed_at=NOW,
    )
    assert result["status"] == "invalid_source_shape"
    assert result["records_observed"] == 0
    assert not result["trends"]


@pytest.mark.asyncio
async def test_observed_empty_is_distinct_from_source_failure(tmp_path):
    empty = await intelligence_rss.discover_trending_rss(
        "US", execute=True, cache=BudgetCache(tmp_path / "one"),
        provider=FakeTrends([]), observed_at=NOW,
    )
    failed = await intelligence_rss.discover_trending_rss(
        "US", execute=True, cache=BudgetCache(tmp_path / "two"),
        provider=FakeTrends(ProviderUnavailableError("google_trends", "trending_now_by_rss")),
        observed_at=NOW,
    )
    assert empty["status"] == "observed_empty"
    assert failed["status"] == "provider_unavailable"
    assert "trend presence UNKNOWN" in intelligence_rss.format_rss_report(failed)


@pytest.mark.asyncio
async def test_google_429_prevents_repeat_request_with_shared_cooldown(tmp_path):
    cache = BudgetCache(tmp_path)
    provider = FakeTrends(ProviderRateLimitError("google_trends", "trending_now_by_rss"))
    first = await intelligence_rss.discover_trending_rss(
        "US", execute=True, cache=cache, provider=provider, observed_at=NOW,
    )
    second = await intelligence_rss.discover_trending_rss(
        "GB", execute=True, cache=cache, provider=provider, observed_at=NOW,
    )
    assert first["status"] == "provider_rate_limited"
    assert second["status"] == "provider_cooldown"
    assert provider.calls == [("US", True)]


@pytest.mark.asyncio
async def test_utc_day_cap_fails_closed_before_provider_and_does_not_bypass(tmp_path):
    store = BudgetCache(tmp_path)
    for _ in range(intelligence_rss.MAX_FREE_REQUESTS_PER_UTC_DAY):
        store.reserve(intelligence_rss.SOURCE_BUDGET_ID,
                      intelligence_rss.MAX_FREE_REQUESTS_PER_UTC_DAY)
    provider = FakeTrends([row()])
    result = await intelligence_rss.discover_trending_rss(
        "US", execute=True, cache=store, provider=provider, observed_at=NOW,
    )
    assert result["status"] == "local_daily_budget_exhausted"
    assert result["source_requests_performed"] == 0
    assert provider.calls == []


@pytest.mark.asyncio
async def test_corrupted_cache_is_not_reused_as_verified_source_data(tmp_path):
    store = BudgetCache(tmp_path)
    original = await intelligence_rss.discover_trending_rss(
        "US", execute=True, cache=store,
        provider=FakeTrends([row()]), observed_at=NOW,
    )
    assert original["status"] == "observed"
    bad = dict(original)
    bad["trends"] = [{**original["trends"][0],
                      "signal": {**original["trends"][0]["signal"],
                                 "value": 9999}}]
    import hashlib
    key = hashlib.sha256("mjau_rss_v1_US".encode()).hexdigest()
    store.save(key, bad, 900)
    replacement_provider = FakeTrends([row("replacement")])
    current = await intelligence_rss.discover_trending_rss(
        "US", execute=True, cache=store, provider=replacement_provider,
        observed_at=NOW,
    )
    assert current["status"] == "observed"
    assert not current["cache_hit"]
    assert current["trends"][0]["signal"]["raw_term"] == "replacement"
    assert replacement_provider.calls == [("US", True)]


@pytest.mark.asyncio
async def test_partial_coverage_does_not_claim_complete_feed(tmp_path):
    provider = FakeTrends([row("Valid"), row("Invalid", "wrong traffic")])
    result = await intelligence_rss.discover_trending_rss(
        "US", execute=True, cache=BudgetCache(tmp_path),
        provider=provider, observed_at=NOW,
    )
    assert result["status"] == "observed_partial"
    assert result["records_rejected"] == 1
    assert result["records_observed"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(("row_count", "expected_status"), [
    (intelligence_rss.MAX_OUTPUT_ROWS, "observed"),
    (intelligence_rss.MAX_OUTPUT_ROWS + 1, "observed_partial"),
])
async def test_output_cap_marks_feed_partial_when_source_has_more_rows(
    tmp_path, row_count, expected_status,
):
    cache = BudgetCache(tmp_path)
    provider = FakeTrends([
        row(f"Topic {n}") for n in range(row_count)
    ])
    first = await intelligence_rss.discover_trending_rss(
        "US", execute=True, cache=cache, provider=provider, observed_at=NOW,
    )
    assert first["status"] == expected_status
    assert first["records_observed"] == intelligence_rss.MAX_OUTPUT_ROWS
    repeated = await intelligence_rss.discover_trending_rss(
        "US", execute=True, cache=cache, provider=provider, observed_at=NOW,
    )
    assert repeated["status"] == expected_status
    assert repeated["cache_hit"] is True
    assert len(provider.calls) == 1


@pytest.mark.parametrize("bad_geo", ["WORLD", "us", "U;", "U", "U S", ""])
def test_invalid_geo_rejected_before_network(bad_geo):
    with pytest.raises(ValueError):
        intelligence_rss._geo(bad_geo)


def test_cli_plan_is_offline_and_uses_no_provider(monkeypatch):
    from mcp_trendpulse import providers

    monkeypatch.setattr(
        providers, "get_provider_set",
        lambda: (_ for _ in ()).throw(AssertionError("Offline CLI invoked provider")),
    )
    cli_result = CliRunner().invoke(
        cli, ["intelligence", "trending-now", "--geo", "SI", "--format", "json"]
    )
    assert cli_result.exit_code == 0, cli_result.output
    parsed = json.loads(cli_result.output)
    assert parsed["status"] == "planned"
    assert parsed["country"] == "SI"
    assert parsed["network_performed"] is False
    assert parsed["site_property_required"] is False


def test_cli_invalid_market_fails_before_network():
    result = CliRunner().invoke(cli, [
        "intelligence", "trending-now", "--geo", "WORLD", "--execute",
    ])
    assert result.exit_code != 0
