import asyncio
import json

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from mcp_trendpulse import hosted
from mcp_trendpulse.errors import (
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from mcp_trendpulse.providers import ProviderSet, use_provider_set


class UnusedNewsProvider:
    provider_id = "unused_news"


class BarrierTrendsProvider:
    provider_id = "barrier_trends"

    def __init__(self, expected_concurrency: int):
        self.expected_concurrency = expected_concurrency
        self.active = 0
        self.max_active = 0
        self.release = asyncio.Event()

    async def get_trends(self, keyword, **kwargs):
        assert isinstance(keyword, str)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        if self.active >= self.expected_concurrency:
            self.release.set()
        try:
            await self.release.wait()
            await asyncio.sleep(0)
            return [
                {"date": "2026-08-20", "value": 25.0, "keyword": keyword},
                {"date": "2026-08-21", "value": 50.0, "keyword": keyword},
                {"date": "2026-08-22", "value": 75.0, "keyword": keyword},
            ]
        finally:
            self.active -= 1

    async def get_growth(self, keyword, **kwargs):
        assert isinstance(keyword, str)
        return [{"keyword": keyword, "growth": {"3M": 20.0, "1Y": 40.0}}]


class FailingTrendsProvider:
    provider_id = "failing_trends"

    def __init__(self, error):
        self.error = error

    async def get_ranked_trends(self, **kwargs):
        raise self.error


@pytest.mark.asyncio
async def test_hosted_analysis_allows_independent_concurrent_provider_reads():
    concurrency = 12
    trends = BarrierTrendsProvider(expected_concurrency=concurrency)
    providers = ProviderSet(news=UnusedNewsProvider(), trends=trends)

    async def analyze(index: int):
        return await hosted.analyze_keyword_trend(
            keyword=f"keyword-{index}",
            geo="US",
            timeframe="today 90-d",
            max_points=10,
        )

    with use_provider_set(providers):
        results = await asyncio.wait_for(
            asyncio.gather(*(analyze(index) for index in range(concurrency))),
            timeout=2.0,
        )

    assert trends.max_active == concurrency
    assert [result.keyword for result in results] == [
        f"keyword-{index}" for index in range(concurrency)
    ]
    assert all(result.provider == "barrier_trends" for result in results)
    assert all(result.metrics.latest == 75.0 for result in results)
    assert all(result.growth == {"3M": 20.0, "1Y": 40.0} for result in results)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_code", "expected_retryable"),
    [
        (
            ProviderRateLimitError("google_trends", "trending_now"),
            "provider_rate_limited",
            True,
        ),
        (
            ProviderTimeoutError("google_trends", "trending_now"),
            "provider_timeout",
            True,
        ),
        (
            ProviderUnavailableError("google_trends", "trending_now"),
            "provider_unavailable",
            True,
        ),
    ],
)
async def test_hosted_provider_failures_are_stable_client_visible_tool_errors(
    monkeypatch,
    error,
    expected_code,
    expected_retryable,
):
    providers = ProviderSet(
        news=UnusedNewsProvider(),
        trends=FailingTrendsProvider(error),
    )
    monkeypatch.setattr(hosted, "get_provider_set", lambda: providers)

    async with Client(hosted.hosted_mcp) as client:
        with pytest.raises(ToolError) as exc_info:
            await client.call_tool(
                "discover_trends",
                {"geo": "US", "sort_by": "growth", "limit": 3},
            )

    message = str(exc_info.value)
    payload_start = message.find("{")
    assert payload_start >= 0
    payload = json.loads(message[payload_start:])
    assert payload["code"] == expected_code
    assert payload["provider"] == "google_trends"
    assert payload["operation"] == "trending_now"
    assert payload["retryable"] is expected_retryable
    assert payload["message"]
