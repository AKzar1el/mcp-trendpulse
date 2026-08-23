import json
from types import SimpleNamespace

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from mcp_trendpulse import news, server
from mcp_trendpulse.errors import (
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    classify_provider_exception,
)


class RateLimitError(RuntimeError):
    def __init__(self):
        super().__init__("upstream rejected the request")
        self.response = SimpleNamespace(status_code=429)


def test_classify_provider_exception_uses_stable_categories():
    rate_limit = classify_provider_exception(
        RateLimitError(),
        provider="google_trends",
        operation="trending_now_by_rss",
    )
    assert isinstance(rate_limit, ProviderRateLimitError)

    timeout = classify_provider_exception(
        TimeoutError("socket timed out"),
        provider="google_news",
        operation="get_news",
    )
    assert isinstance(timeout, ProviderTimeoutError)

    unavailable = classify_provider_exception(
        RuntimeError("provider parser failed"),
        provider="google_trends",
        operation="interest_over_time",
    )
    assert isinstance(unavailable, ProviderUnavailableError)


@pytest.mark.asyncio
async def test_google_news_timeout_is_not_reported_as_empty_results(monkeypatch):
    class FailingGoogleNews:
        def get_news(self, keyword):
            raise TimeoutError("network timeout")

    monkeypatch.setattr(news, "_new_google_news", lambda period, max_results: FailingGoogleNews())

    with pytest.raises(ProviderTimeoutError) as exc_info:
        await news.get_news_by_keyword("python", nlp=False)

    assert exc_info.value.provider == "google_news"
    assert exc_info.value.operation == "get_news"


@pytest.mark.asyncio
async def test_google_trends_rate_limit_is_not_reported_as_empty_results(monkeypatch):
    class FailingTrends:
        def trending_now_by_rss(self, *, geo):
            raise RateLimitError()

    monkeypatch.setattr(news, "_get_trends_client", lambda: FailingTrends())

    with pytest.raises(ProviderRateLimitError) as exc_info:
        await news.get_trending_terms("US")

    assert exc_info.value.provider == "google_trends"
    assert exc_info.value.operation == "trending_now_by_rss"


@pytest.mark.asyncio
async def test_empty_provider_result_remains_a_successful_empty_result(monkeypatch):
    class EmptyTrends:
        def trending_now_by_rss(self, *, geo):
            return []

    monkeypatch.setattr(news, "_get_trends_client", lambda: EmptyTrends())

    assert await news.get_trending_terms("US") == []


@pytest.mark.asyncio
async def test_provider_error_middleware_returns_controlled_tool_error(monkeypatch):
    async def fail_trending_terms(*, geo, full_data):
        raise ProviderRateLimitError("google_trends", "trending_now_by_rss")

    monkeypatch.setattr(news, "get_trending_terms", fail_trending_terms)

    async with Client(server.mcp) as client:
        with pytest.raises(ToolError) as exc_info:
            await client.call_tool("get_trending_terms", {"geo": "US"})

    message = str(exc_info.value)
    payload_start = message.find("{")
    payload = json.loads(message[payload_start:])
    assert payload == {
        "code": "provider_rate_limited",
        "message": "The upstream provider is rate limiting requests. Try again later.",
        "operation": "trending_now_by_rss",
        "provider": "google_trends",
        "retryable": True,
    }
