"""Offline regressions for article scraper work outliving an async caller."""

import asyncio
import threading

import pytest

from mcp_trendpulse import news


class _Validator:
    def validate_url(self, url: str) -> str:
        return url


class _Article:
    title = "Real article"
    text = "Substantial extracted article content"


@pytest.mark.asyncio
async def test_timed_out_scraper_keeps_physical_worker_slot(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    calls: list[str] = []

    def slow_scraper(url, target_validator):
        calls.append(url)
        if len(calls) == 1:
            started.set()
            try:
                release.wait(2)
            finally:
                finished.set()
        return _Article()

    monkeypatch.setattr(news, "ArticleTargetValidator", _Validator)
    monkeypatch.setattr(news, "download_article_with_scraper", slow_scraper)
    monkeypatch.setattr(news, "_ARTICLE_SCRAPER_WORKER_SLOTS", threading.BoundedSemaphore(1), raising=False)
    monkeypatch.setattr(news, "ARTICLE_SCRAPER_TIMEOUT_SECONDS", 0.03, raising=False)

    try:
        assert await asyncio.wait_for(
            news.download_article("https://example.com/slow"), timeout=0.5
        ) is None
        assert started.is_set() and not finished.is_set()
        assert await asyncio.wait_for(
            news.download_article("https://example.com/second"), timeout=0.5
        ) is None
        assert calls == ["https://example.com/slow"]
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 1)


@pytest.mark.asyncio
async def test_cancelled_scraper_keeps_physical_worker_slot(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    calls: list[str] = []

    def slow_scraper(url, target_validator):
        calls.append(url)
        if len(calls) == 1:
            started.set()
            try:
                release.wait(2)
            finally:
                finished.set()
        return _Article()

    monkeypatch.setattr(news, "ArticleTargetValidator", _Validator)
    monkeypatch.setattr(news, "download_article_with_scraper", slow_scraper)
    monkeypatch.setattr(news, "_ARTICLE_SCRAPER_WORKER_SLOTS", threading.BoundedSemaphore(1), raising=False)

    task = asyncio.create_task(news.download_article("https://example.com/slow"))
    try:
        assert await asyncio.to_thread(started.wait, 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert await asyncio.wait_for(
            news.download_article("https://example.com/second"), timeout=0.5
        ) is None
        assert calls == ["https://example.com/slow"]
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 1)
