"""Red/green no-network validation for Google Trends Trending Now geo selectors.

The real integration probe previously sent a malformed 3-letter country
identifier (USA) to Google and received HTTP 400. Invalid selectors must be
rejected before a provider reservation or HTTP request, while valid country,
subdivision, DMA and worldwide selectors retain their documented behavior.
"""
from __future__ import annotations

import pytest

from mcp_trendpulse import news, server


@pytest.mark.asyncio
@pytest.mark.parametrize("geo", [
    "USA", "ZZZ", "US-CA-CA", "US/CA", "US\nCA",
    "https://example.com", "US;geo=GB", 807, None, False,
])
async def test_news_invalid_trending_geo_makes_no_network_call(monkeypatch, geo):
    called = []

    async def forbidden_provider_call(*_args, **_kwargs):
        called.append(True)
        raise AssertionError("invalid geography reached the provider")

    monkeypatch.setattr(news, "_call_trends_async", forbidden_provider_call)
    with pytest.raises(ValueError, match="geo"):
        await news.get_trending_terms(geo=geo)
    assert called == []


@pytest.mark.asyncio
@pytest.mark.parametrize("geo", ["USA", "US/CA", "US-CA-CA", "ZZZ"])
async def test_mcp_invalid_geo_rejected_before_provider_is_created(monkeypatch, geo):
    def forbidden_provider():
        raise AssertionError("invalid geography reached provider selection")

    monkeypatch.setattr(server, "get_provider_set", forbidden_provider)
    with pytest.raises(ValueError, match="geo"):
        await server.get_trending_terms(geo=geo)


@pytest.mark.asyncio
@pytest.mark.parametrize("geo", ["USA", "US/CA", "US-CA-CA", "ZZZ"])
async def test_top_trends_invalid_geo_makes_no_provider_call(monkeypatch, geo):
    async def forbidden(*_args, **_kwargs):
        raise AssertionError("invalid geo reached the trends API")

    monkeypatch.setattr(news, "_call_trends_async", forbidden)
    with pytest.raises(ValueError, match="geo"):
        await news.get_top_trends(geo=geo)
    monkeypatch.setattr(
        server, "get_provider_set",
        lambda: (_ for _ in ()).throw(AssertionError("provider selected")),
    )
    with pytest.raises(ValueError, match="geo"):
        await server.get_top_trends(geo=geo)

@pytest.mark.asyncio
@pytest.mark.parametrize("geo, normalized", [
    ("", ""), ("us", "US"), ("SI", "SI"), ("gb", "GB"),
    ("US-CA", "US-CA"), ("be-bru", "BE-BRU"),
    ("AR-C", "AR-C"), ("807", "807"),
])
async def test_supported_trending_geos_reach_provider_normalized(monkeypatch, geo, normalized):
    observed = []
    class Provider:
        async def get_trending_terms(self, *, geo, full_data):
            observed.append((geo, full_data))
            return [{"keyword": "Example trend", "volume": "1000+"}]
    class Providers:
        trends = Provider()

    monkeypatch.setattr(server, "get_provider_set", lambda: Providers())
    response = await server.get_trending_terms(geo=geo, full_data=False)
    assert observed == [(normalized, False)]
    assert len(response) == 1 and response[0].keyword == "Example trend"
