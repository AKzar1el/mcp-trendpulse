import json
import time
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


class TrendsQuotaExceededError(RuntimeError):
    pass


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
async def test_google_news_call_has_a_caller_visible_timeout(monkeypatch):
    class BlockingGoogleNews:
        def get_news(self, keyword):
            time.sleep(0.1)
            return []

    monkeypatch.setattr(news, "GOOGLE_NEWS_OPERATION_TIMEOUT_SECONDS", 0.01)

    with pytest.raises(ProviderTimeoutError) as exc_info:
        await news._call_google_news_async(BlockingGoogleNews(), "get_news", "python")

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


def test_related_queries_classifies_quota_exhaustion_as_rate_limit_without_retry(monkeypatch):
    attempts = []

    class QuotaLimitedTrends:
        def related_queries(self, **kwargs):
            attempts.append(kwargs)
            raise TrendsQuotaExceededError("API quota exceeded for related queries/topics")

    monkeypatch.setattr(news, "_get_trends_client", lambda: QuotaLimitedTrends())

    with pytest.raises(ProviderRateLimitError) as exc_info:
        news._call_related_queries_with_unavailable_retry(keyword="python", geo="US")

    assert exc_info.value.provider == "google_trends"
    assert exc_info.value.operation == "related_queries"
    assert len(attempts) == 1


def test_related_queries_retries_unavailable_once_with_fresh_client(monkeypatch):
    attempts = []

    class FailingTrends:
        def related_queries(self, **kwargs):
            attempts.append(("failed", kwargs))
            raise ProviderUnavailableError("google_trends", "related_queries")

    class WorkingTrends:
        def related_queries(self, **kwargs):
            attempts.append(("worked", kwargs))
            return {"top": None, "rising": None}

    clients = iter((FailingTrends(), WorkingTrends()))
    monkeypatch.setattr(news, "_get_trends_client", lambda: next(clients))

    result = news._call_related_queries_with_unavailable_retry(keyword="python", geo="US")

    assert result == {"top": None, "rising": None}
    assert [label for label, _ in attempts] == ["failed", "worked"]


def test_related_queries_does_not_retry_rate_limits(monkeypatch):
    attempts = []

    class RateLimitedTrends:
        def related_queries(self, **kwargs):
            attempts.append(kwargs)
            raise ProviderRateLimitError("google_trends", "related_queries")

    monkeypatch.setattr(news, "_get_trends_client", lambda: RateLimitedTrends())

    with pytest.raises(ProviderRateLimitError):
        news._call_related_queries_with_unavailable_retry(keyword="python", geo="US")

    assert len(attempts) == 1


def test_related_queries_propagates_second_unavailable_failure(monkeypatch):
    attempts = []

    class FailingTrends:
        def related_queries(self, **kwargs):
            attempts.append(kwargs)
            raise ProviderUnavailableError("google_trends", "related_queries")

    monkeypatch.setattr(news, "_get_trends_client", lambda: FailingTrends())

    with pytest.raises(ProviderUnavailableError):
        news._call_related_queries_with_unavailable_retry(keyword="python", geo="US")

    assert len(attempts) == 2


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
