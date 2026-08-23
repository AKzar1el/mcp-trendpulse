import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from mcp_trendpulse import server
from mcp_trendpulse.errors import ProviderUnavailableError
from mcp_trendpulse.providers import (
    COMMUNITY_PROVIDERS,
    CommunityNewsProvider,
    CommunityTrendsProvider,
    ProviderSet,
    get_provider_set,
    use_provider_set,
)


def test_default_provider_set_uses_existing_community_providers():
    providers = get_provider_set()

    assert providers is COMMUNITY_PROVIDERS
    assert providers.news.provider_id == "google_news"
    assert providers.trends.provider_id == "google_trends"


async def test_community_news_provider_delegates_without_changing_arguments():
    articles = [object()]
    callback = AsyncMock()
    underlying = AsyncMock(return_value=articles)

    with patch("mcp_trendpulse.providers.news.get_news_by_keyword", new=underlying):
        result = await CommunityNewsProvider().get_news_by_keyword(
            keyword="agent search",
            period=5,
            max_results=7,
            nlp=False,
            report_progress=callback,
        )

    assert result is articles
    underlying.assert_awaited_once_with(
        keyword="agent search",
        period=5,
        max_results=7,
        nlp=False,
        report_progress=callback,
    )


async def test_community_trends_provider_normalizes_full_trends_to_plain_mappings():
    article = SimpleNamespace(
        title="Trend story",
        url="https://example.com/story",
        source="Example",
    )
    trend = SimpleNamespace(
        keyword="AI agents",
        volume="100K+",
        news=[article],
    )
    underlying = AsyncMock(return_value=[trend])

    with patch("mcp_trendpulse.providers.news.get_trending_terms", new=underlying):
        result = await CommunityTrendsProvider().get_trending_terms(
            geo="US",
            full_data=True,
        )

    assert result == [
        {
            "keyword": "AI agents",
            "volume": "100K+",
            "news": [
                {
                    "title": "Trend story",
                    "url": "https://example.com/story",
                    "source": "Example",
                }
            ],
        }
    ]
    underlying.assert_awaited_once_with(geo="US", full_data=True)


async def test_provider_adapter_preserves_structured_provider_errors():
    error = ProviderUnavailableError("google_trends", "interest_over_time")
    underlying = AsyncMock(side_effect=error)

    with (
        patch("mcp_trendpulse.providers.news.get_trends", new=underlying),
        pytest.raises(ProviderUnavailableError) as raised,
    ):
        await CommunityTrendsProvider().get_trends("agent search")

    assert raised.value is error
    assert raised.value.provider == "google_trends"
    assert raised.value.operation == "interest_over_time"


async def test_provider_scope_isolated_between_concurrent_tasks_and_restored():
    default = get_provider_set()
    first = ProviderSet(
        news=SimpleNamespace(provider_id="news-first"),
        trends=SimpleNamespace(provider_id="trends-first"),
    )
    second = ProviderSet(
        news=SimpleNamespace(provider_id="news-second"),
        trends=SimpleNamespace(provider_id="trends-second"),
    )
    barrier = asyncio.Event()
    entered = 0
    entered_lock = asyncio.Lock()

    async def worker(selected: ProviderSet) -> tuple[str, str]:
        nonlocal entered
        with use_provider_set(selected):
            async with entered_lock:
                entered += 1
                if entered == 2:
                    barrier.set()
            await barrier.wait()
            await asyncio.sleep(0)
            active = get_provider_set()
            return active.news.provider_id, active.trends.provider_id

    first_result, second_result = await asyncio.gather(
        worker(first),
        worker(second),
    )

    assert first_result == ("news-first", "trends-first")
    assert second_result == ("news-second", "trends-second")
    assert get_provider_set() is default


class FakeTrendsProvider:
    provider_id = "fake_trends"

    def __init__(self):
        self.calls = []

    async def get_trends(self, **kwargs):
        self.calls.append(kwargs)
        return [
            {
                "date": "2026-08-23",
                "value": 77.0,
                "keyword": "provider boundary",
            }
        ]


async def test_server_tool_uses_context_selected_trends_provider():
    fake_trends = FakeTrendsProvider()
    selected = ProviderSet(
        news=COMMUNITY_PROVIDERS.news,
        trends=fake_trends,
    )

    with use_provider_set(selected):
        result = await server.get_trends(
            keyword="provider boundary",
            source="google search",
            data_mode="daily",
            geo="US",
            timeframe="today 7-d",
            cat=0,
        )

    assert [item.model_dump() for item in result] == [
        {
            "date": "2026-08-23",
            "value": 77.0,
            "keyword": "provider boundary",
        }
    ]
    assert fake_trends.calls == [
        {
            "keyword": "provider boundary",
            "source": "google search",
            "data_mode": "daily",
            "geo": "US",
            "timeframe": "today 7-d",
            "cat": 0,
        }
    ]
