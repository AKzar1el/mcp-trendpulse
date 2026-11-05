"""No-network regressions for blocking TrendSpy worker lifetime."""

import asyncio
import threading

import pytest

from mcp_trendpulse import news
from mcp_trendpulse.errors import ProviderTimeoutError, ProviderUnavailableError


class NoNetworkTrends:
    def __getattr__(self, operation):
        def fail(*args, **kwargs):
            raise AssertionError(f"Unexpected provider call: {operation}")

        return fail


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("call", "operation"),
    [
        (lambda: news.get_trending_terms(), "trending_now_by_rss"),
        (lambda: news.get_trends("alpha"), "interest_over_time"),
        (lambda: news.get_growth("alpha"), "interest_over_time"),
        (lambda: news.get_ranked_trends(), "trending_now"),
        (lambda: news.get_top_trends(type="Daily Trends"), "trending_now"),
        (lambda: news.get_interest_by_region("alpha"), "interest_by_region"),
        (lambda: news.get_related_queries("alpha"), "related_queries"),
        (lambda: news.get_related_topics("alpha"), "related_topics"),
        (lambda: news.get_suggestions("alpha"), "suggestions"),
        (lambda: news.get_categories(), "categories"),
    ],
)
async def test_every_trends_endpoint_respects_shared_physical_saturation(monkeypatch, call, operation):
    slots = threading.BoundedSemaphore(1)
    assert slots.acquire(blocking=False)
    monkeypatch.setattr(news, "_TRENDS_WORKER_SLOTS", slots, raising=False)
    monkeypatch.setattr(news, "tr", NoNetworkTrends())
    try:
        with pytest.raises(ProviderUnavailableError) as error:
            await call()
        assert error.value.provider == "google_trends"
        assert error.value.operation == operation
    finally:
        slots.release()


@pytest.mark.asyncio
async def test_cancelled_mixed_callers_do_not_release_physical_slots_early(monkeypatch):
    slots = threading.BoundedSemaphore(2)
    monkeypatch.setattr(news, "_TRENDS_WORKER_SLOTS", slots, raising=False)
    entered = threading.Event()
    release = threading.Event()
    lock = threading.Lock()
    active = 0
    peak = 0

    class BlockingTrends:
        def _fetch(self, **kwargs):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
                if active == 2:
                    entered.set()
            try:
                assert release.wait(timeout=5)
                return []
            finally:
                with lock:
                    active -= 1

        trending_now = _fetch
        trending_now_by_rss = _fetch

        def categories(self):
            return []

    monkeypatch.setattr(news, "tr", BlockingTrends())
    tasks = [
        asyncio.create_task(news.get_trending_terms()),
        asyncio.create_task(news.get_top_trends(type="Daily Trends")),
    ]
    try:
        assert await asyncio.to_thread(entered.wait, 3)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        assert peak == 2
        assert active == 2
        with pytest.raises(ProviderUnavailableError):
            await news.get_categories()
    finally:
        release.set()
        await asyncio.gather(*tasks, return_exceptions=True)

    for _ in range(100):
        if active == 0 and slots.acquire(blocking=False):
            slots.release()
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("Physical workers did not return their slots")
    assert await news.get_categories() == []
    assert peak == 2


@pytest.mark.asyncio
async def test_trends_timeout_does_not_reuse_still_running_worker_slot(monkeypatch):
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(news, "_TRENDS_WORKER_SLOTS", slots, raising=False)
    monkeypatch.setattr(news, "TRENDS_OPERATION_TIMEOUT_SECONDS", 0.04, raising=False)
    entered = threading.Event()
    release = threading.Event()

    class BlockingTrends:
        def trending_now_by_rss(self, **kwargs):
            entered.set()
            assert release.wait(timeout=5)
            return []

        def categories(self):
            return []

    monkeypatch.setattr(news, "tr", BlockingTrends())
    try:
        with pytest.raises(ProviderTimeoutError) as error:
            await news.get_trending_terms()
        assert error.value.operation == "trending_now_by_rss"
        assert entered.is_set()
        with pytest.raises(ProviderUnavailableError):
            await news.get_categories()
    finally:
        release.set()

    for _ in range(100):
        if slots.acquire(blocking=False):
            slots.release()
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("Timed-out physical worker did not return its slot")
    assert await news.get_categories() == []
