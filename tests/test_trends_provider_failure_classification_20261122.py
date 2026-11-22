"""Live-reproduced provider JSON NoneType failure in ranked Trends (2026-11-22).

All tests operate with an injected TrendSpy fake: no paid API, DNS or Google calls.
"""
import json
from types import SimpleNamespace

import pytest

from mcp_trendpulse import news
from mcp_trendpulse.errors import ProviderRateLimitError, ProviderUnavailableError


@pytest.mark.asyncio
async def test_ranked_feed_provider_json_none_typeerror_is_controlled(monkeypatch):
    def broken(**_kwargs):
        # Mirrors the actual raw upstream error observed in connected MCP.
        return json.loads(None)

    monkeypatch.setattr(news, "tr", SimpleNamespace(trending_now=broken))
    with pytest.raises(ProviderUnavailableError) as caught:
        await news.get_ranked_trends(geo="US", sort="recent_growth_pct", limit=4)
    assert caught.value.provider == "google_trends"
    assert caught.value.operation == "trending_now"
    assert "NoneType" not in caught.value.public_message


@pytest.mark.asyncio
async def test_ranked_feed_throttling_has_machine_readable_provider_error(monkeypatch):
    def throttled(**_kwargs):
        raise RuntimeError("HTTP 429 Too Many Requests")

    monkeypatch.setattr(news, "tr", SimpleNamespace(trending_now=throttled))
    with pytest.raises(ProviderRateLimitError) as caught:
        await news.get_ranked_trends(geo="US", limit=2)
    assert caught.value.retryable is True
    assert caught.value.code.value == "provider_rate_limited"


@pytest.mark.asyncio
async def test_ranked_feed_rejects_invalid_geo_without_invoking_provider(monkeypatch):
    def never_called(**_kwargs):
        raise AssertionError("Provider call should not happen for invalid geo")

    monkeypatch.setattr(news, "tr", SimpleNamespace(trending_now=never_called))
    with pytest.raises(ValueError, match="Invalid Google Trends geo"):
        await news.get_ranked_trends(geo="../../internal", limit=2)


@pytest.mark.asyncio
async def test_ranked_feed_still_rejects_user_sort_before_provider(monkeypatch):
    monkeypatch.setattr(
        news, "tr",
        SimpleNamespace(trending_now=lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("Provider should never be called for invalid sort"))),
    )
    with pytest.raises(ValueError, match="Unsupported sort"):
        await news.get_ranked_trends(geo="US", sort="invalid_sort", limit=2)


@pytest.mark.asyncio
async def test_ranked_feed_healthy_provider_still_returns_bounded_result(monkeypatch):
    row = SimpleNamespace(
        keyword="software testing", volume_growth_pct=250.0,
        volume="10K+", started_timestamp=1730000000, news=[],
    )
    monkeypatch.setattr(
        news, "tr", SimpleNamespace(trending_now=lambda **kwargs: [row]),
    )
    result = await news.get_ranked_trends(geo="US", limit=1)
    assert [x["keyword"] for x in result] == ["software testing"]
    assert result[0]["growth_pct"] == 250.0


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_geo", ["../internal", "http://127.0.0.1", "US/..", "US US", "1234"])
async def test_ranked_feed_malformed_geography_is_never_forwarded(monkeypatch, bad_geo):
    def never(**_kwargs):
        raise AssertionError("Invalid location reached provider")

    monkeypatch.setattr(news, "tr", SimpleNamespace(trending_now=never))
    with pytest.raises(ValueError, match="Invalid Google Trends geo"):
        await news.get_ranked_trends(geo=bad_geo, limit=1)


@pytest.mark.asyncio
async def test_ranked_feed_normalizes_country_before_source_call(monkeypatch):
    received = []
    def healthy(**kwargs):
        received.append(kwargs)
        return []
    monkeypatch.setattr(news, "tr", SimpleNamespace(trending_now=healthy))
    assert await news.get_ranked_trends(geo="us", limit=1) == []
    assert received == [{"geo": "US", "hours": 24}]


@pytest.mark.asyncio
async def test_typed_provider_receipt_is_preserved_without_double_wrapping(monkeypatch):
    source_error = ProviderRateLimitError("google_trends", "trending_now")

    def broken(**_kwargs):
        raise source_error

    monkeypatch.setattr(news, "tr", SimpleNamespace(trending_now=broken))
    with pytest.raises(ProviderRateLimitError) as caught:
        await news.get_ranked_trends(geo="US", limit=1)
    assert caught.value is source_error


@pytest.mark.asyncio
async def test_worker_semaphore_recovers_after_sequential_source_failures(monkeypatch):
    def failed(**_kwargs):
        raise TypeError("upstream JSON NoneType")

    monkeypatch.setattr(news, "tr", SimpleNamespace(trending_now=failed))
    for _ in range(news.TRENDS_MAX_ACTIVE_WORKERS + 1):
        with pytest.raises(ProviderUnavailableError):
            await news.get_ranked_trends(geo="US", limit=1)

    row = SimpleNamespace(keyword="recovered", volume_growth_pct=1.0,
                          volume="100", news=[], started_timestamp=None)
    monkeypatch.setattr(news, "tr", SimpleNamespace(trending_now=lambda **_kwargs: [row]))
    actual = await news.get_ranked_trends(geo="US", limit=1)
    assert actual[0]["keyword"] == "recovered"


@pytest.mark.asyncio
async def test_related_daily_feed_uses_the_same_sanitized_exception_contract(monkeypatch):
    def broken(**_kwargs):
        raise TypeError("upstream returned no JSON document")

    monkeypatch.setattr(news, "tr", SimpleNamespace(trending_now=broken))
    with pytest.raises(ProviderUnavailableError) as caught:
        await news.get_top_trends(type="Daily Trends", geo="US", limit=1)
    assert caught.value.provider == "google_trends"
    assert caught.value.operation == "trending_now"


@pytest.mark.asyncio
@pytest.mark.parametrize(("upstream_method", "invoke", "operation"), [
    ("interest_over_time", lambda: news.get_trends(keyword="AI", geo="US", timeframe="today 3-m"), "interest_over_time"),
    ("interest_over_time", lambda: news.get_growth(keyword="AI", geo="US", percent_growth=["3M"]), "interest_over_time"),
    ("interest_by_region", lambda: news.get_interest_by_region(keywords="AI", geo="US", resolution="REGION"), "interest_by_region"),
    ("related_queries", lambda: news.get_related_queries(keyword="AI"), "related_queries"),
    ("related_topics", lambda: news.get_related_topics(keyword="AI"), "related_topics"),
    ("suggestions", lambda: news.get_suggestions(keyword="AI"), "suggestions"),
    ("categories", lambda: news.get_categories(), "categories"),
    ("trending_now_by_rss", lambda: news.get_top_trends(type="Google Trends", geo="US", limit=2), "trending_now_by_rss"),
    ("trending_now_by_rss", lambda: news.get_trending_terms(geo="US", full_data=False), "trending_now_by_rss"),
])
async def test_other_trendspy_endpoints_share_sanitized_provider_exception(
    monkeypatch, upstream_method, invoke, operation,
):
    def broken(*_args, **_kwargs):
        raise TypeError("the JSON object must be str, bytes or bytearray, not NoneType")

    monkeypatch.setattr(news, "tr", SimpleNamespace(**{upstream_method: broken}))
    with pytest.raises(ProviderUnavailableError) as caught:
        await invoke()
    assert caught.value.operation == operation
    assert caught.value.provider == "google_trends"
