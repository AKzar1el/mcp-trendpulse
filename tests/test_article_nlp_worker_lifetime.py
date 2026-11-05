"""Offline regressions for slow optional newspaper NLP enrichment."""

import asyncio
import threading
from unittest.mock import AsyncMock

import pytest

from mcp_trendpulse import news


@pytest.mark.asyncio
async def test_timed_out_nlp_preserves_article_without_late_mutation(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    class SlowArticle:
        title = "Real article"
        text = "Useful extracted article content"
        publish_date = None
        summary = ""
        keywords = []

        def nlp(self):
            started.set()
            try:
                release.wait(2)
                self.summary = "late and untrustworthy"
                self.keywords = ["late"]
            finally:
                finished.set()

    article = SlowArticle()
    monkeypatch.setattr(news, "download_article", AsyncMock(return_value=article))
    monkeypatch.setattr(news, "ARTICLE_NLP_TIMEOUT_SECONDS", 0.03, raising=False)
    try:
        result = await asyncio.wait_for(
            news.process_gnews_articles([{"url": "https://example.com/one"}], nlp=True),
            timeout=0.5,
        )
        assert result == [article]
        assert started.is_set() and not finished.is_set()
        assert article.summary == ""
        assert article.keywords == []
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 1)
    assert article.summary == ""
    assert article.keywords == []


@pytest.mark.asyncio
async def test_unfinished_nlp_worker_reserves_slot_after_caller_timeout(monkeypatch):
    release = threading.Event()
    started = threading.Event()
    finished = threading.Event()

    class Article:
        title = "Real article"
        text = "Useful extracted article content"
        publish_date = None
        summary = ""
        keywords = []

        def __init__(self, slow=False):
            self.slow = slow
            self.calls = 0

        def nlp(self):
            self.calls += 1
            if self.slow:
                started.set()
                try:
                    release.wait(2)
                finally:
                    finished.set()
            self.summary = "enriched"

    first, second = Article(slow=True), Article()
    monkeypatch.setattr(news, "_ARTICLE_NLP_WORKER_SLOTS", threading.BoundedSemaphore(1), raising=False)
    monkeypatch.setattr(news, "ARTICLE_NLP_TIMEOUT_SECONDS", 0.03, raising=False)
    monkeypatch.setattr(news, "download_article", AsyncMock(side_effect=[first, second]))
    try:
        assert await asyncio.wait_for(
            news.process_gnews_articles([{"url": "https://example.com/slow"}], nlp=True),
            timeout=0.5,
        ) == [first]
        assert started.is_set() and not finished.is_set()
        assert await asyncio.wait_for(
            news.process_gnews_articles([{"url": "https://example.com/second"}], nlp=True),
            timeout=0.5,
        ) == [second]
        assert second.calls == 0
        assert second.summary == ""
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 1)
