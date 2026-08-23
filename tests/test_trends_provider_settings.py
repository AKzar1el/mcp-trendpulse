import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from mcp_trendpulse import news
from mcp_trendpulse.config import DEFAULT_GOOGLE_TRENDS_DELAY, get_google_trends_delay


class FakeTrend:
    def __init__(self, keyword: str, volume: str):
        self.keyword = keyword
        self.volume = volume


class FakeTrends:
    instances: list["FakeTrends"] = []

    def __init__(self, *, request_delay: float):
        self.request_delay = request_delay
        self.created_thread = threading.get_ident()
        self.calls: list[tuple[str, int]] = []
        type(self).instances.append(self)

    def trending_now_by_rss(self, *, geo: str):
        self.calls.append((geo, threading.get_ident()))
        return [FakeTrend("alpha", "100K"), FakeTrend("beta", "2M")]


def test_google_trends_delay_defaults_and_invalid_values():
    assert get_google_trends_delay({}) == DEFAULT_GOOGLE_TRENDS_DELAY
    assert get_google_trends_delay({"GOOGLE_TRENDS_DELAY": "1.25"}) == 1.25
    assert get_google_trends_delay({"GOOGLE_TRENDS_DELAY": "invalid"}) == DEFAULT_GOOGLE_TRENDS_DELAY


@pytest.mark.asyncio
async def test_trending_terms_creates_provider_lazily_off_event_loop(monkeypatch):
    event_loop_thread = threading.get_ident()
    FakeTrends.instances = []
    monkeypatch.setenv("GOOGLE_TRENDS_DELAY", "1.5")
    monkeypatch.setattr(news, "Trends", FakeTrends)
    monkeypatch.setattr(news, "_trends_local", threading.local())

    result = await news.get_trending_terms("US")

    assert result == [
        {"keyword": "beta", "volume": "2M"},
        {"keyword": "alpha", "volume": "100K"},
    ]
    assert len(FakeTrends.instances) == 1
    instance = FakeTrends.instances[0]
    assert instance.request_delay == 1.5
    assert instance.created_thread != event_loop_thread
    assert instance.calls == [("US", instance.created_thread)]


def test_trends_provider_is_reused_per_thread_but_not_shared(monkeypatch):
    FakeTrends.instances = []
    monkeypatch.setattr(news, "Trends", FakeTrends)
    monkeypatch.setattr(news, "_trends_local", threading.local())
    monkeypatch.setattr(news, "get_google_trends_delay", lambda: 2.0)
    barrier = threading.Barrier(2)

    def worker():
        first = news._get_trends_client()
        barrier.wait(timeout=2)
        second = news._get_trends_client()
        return first, second

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: worker(), range(2)))

    assert len(FakeTrends.instances) == 2
    assert all(first is second for first, second in results)
    assert results[0][0] is not results[1][0]
