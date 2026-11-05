"""Offline lifecycle tests for article URL validation and RSS decoding threads."""

import asyncio
import threading

import pytest

from mcp_trendpulse import news


@pytest.mark.asyncio
async def test_article_dns_timeout_retains_physical_worker_slot(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    calls: list[str] = []

    class SlowValidator:
        def validate_url(self, url: str) -> str:
            calls.append(url)
            if len(calls) == 1:
                started.set()
                try:
                    release.wait(2)
                finally:
                    finished.set()
            return url

    async def no_scraper(url, target_validator):
        return None

    monkeypatch.setattr(news, "ArticleTargetValidator", SlowValidator)
    monkeypatch.setattr(news, "_download_article_with_worker_slot", no_scraper)
    monkeypatch.setattr(news, "_ARTICLE_PREFLIGHT_WORKER_SLOTS", threading.BoundedSemaphore(1), raising=False)
    monkeypatch.setattr(news, "ARTICLE_PREFLIGHT_TIMEOUT_SECONDS", 0.03, raising=False)

    try:
        with pytest.raises(ValueError, match="preflight.*deadline"):
            await asyncio.wait_for(news.download_article("https://example.com/slow"), timeout=0.5)
        assert started.is_set() and not finished.is_set()

        with pytest.raises(ValueError, match="preflight.*capacity"):
            await asyncio.wait_for(news.download_article("https://example.com/second"), timeout=0.5)
        assert calls == ["https://example.com/slow"]
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 1)


@pytest.mark.asyncio
async def test_cancelled_dns_validation_retains_physical_worker_slot(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    calls: list[str] = []

    class SlowValidator:
        def validate_url(self, url: str) -> str:
            calls.append(url)
            if len(calls) == 1:
                started.set()
                try:
                    release.wait(2)
                finally:
                    finished.set()
            return url

    async def no_scraper(url, target_validator):
        return None

    monkeypatch.setattr(news, "ArticleTargetValidator", SlowValidator)
    monkeypatch.setattr(news, "_download_article_with_worker_slot", no_scraper)
    monkeypatch.setattr(news, "_ARTICLE_PREFLIGHT_WORKER_SLOTS", threading.BoundedSemaphore(1), raising=False)

    task = asyncio.create_task(news.download_article("https://example.com/slow"))
    try:
        assert await asyncio.to_thread(started.wait, 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        with pytest.raises(ValueError, match="preflight.*capacity"):
            await asyncio.wait_for(news.download_article("https://example.com/second"), timeout=0.5)
        assert calls == ["https://example.com/slow"]
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 1)


@pytest.mark.asyncio
async def test_rss_decoder_timeout_retains_slot_and_returns_no_article(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()
    calls: list[str] = []

    class Validator:
        def validate_url(self, url: str) -> str:
            return url

    def slow_decoder(url: str) -> str | None:
        calls.append(url)
        if len(calls) == 1:
            started.set()
            try:
                release.wait(2)
            finally:
                finished.set()
        return "https://example.com/decoded"

    async def no_scraper(url, target_validator):
        return None

    monkeypatch.setattr(news, "ArticleTargetValidator", Validator)
    monkeypatch.setattr(news, "decode_url", slow_decoder)
    monkeypatch.setattr(news, "_download_article_with_worker_slot", no_scraper)
    monkeypatch.setattr(news, "_ARTICLE_PREFLIGHT_WORKER_SLOTS", threading.BoundedSemaphore(1), raising=False)
    monkeypatch.setattr(news, "ARTICLE_PREFLIGHT_TIMEOUT_SECONDS", 0.03, raising=False)

    url = "https://news.google.com/rss/articles/test"
    try:
        assert await asyncio.wait_for(news.download_article(url), timeout=0.5) is None
        assert started.is_set() and not finished.is_set()
        # A blocked decoder occupies the shared preflight capacity; refuse a
        # second request at validation instead of starting another DNS worker.
        with pytest.raises(ValueError, match="preflight.*capacity"):
            await asyncio.wait_for(news.download_article(url), timeout=0.5)
        assert calls == [url]
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 1)
