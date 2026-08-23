import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock

import pytest

from mcp_trendpulse import news


class FakeArticle:
    def __init__(self, label: str):
        self.label = label
        self.title = label
        self.text = f"text for {label}"
        self.nlp_calls = 0

    def nlp(self):
        self.nlp_calls += 1


@pytest.mark.asyncio
async def test_process_gnews_articles_bounds_concurrency_and_preserves_order(monkeypatch):
    active = 0
    peak = 0
    lock = asyncio.Lock()
    delays = {
        "first": 0.04,
        "second": 0.01,
        "third": 0.02,
        "fourth": 0.01,
    }

    async def fake_download(url: str):
        nonlocal active, peak
        label = url.rsplit("/", 1)[-1]
        async with lock:
            active += 1
            peak = max(peak, active)
        try:
            await asyncio.sleep(delays[label])
            return FakeArticle(label)
        finally:
            async with lock:
                active -= 1

    monkeypatch.setattr(news, "download_article", fake_download)

    inputs = [
        {"url": "https://example.com/first"},
        {"url": "https://example.com/second"},
        {"url": "https://example.com/third"},
        {"url": "https://example.com/fourth"},
    ]
    result = await news.process_gnews_articles(inputs, nlp=True, max_concurrency=2)

    assert peak == 2
    assert [article.label for article in result] == ["first", "second", "third", "fourth"]
    assert all(article.nlp_calls == 1 for article in result)


@pytest.mark.asyncio
async def test_process_gnews_articles_preserves_success_progress_indices(monkeypatch):
    async def fake_download(url: str):
        if url.endswith("/missing"):
            return None
        return FakeArticle(url.rsplit("/", 1)[-1])

    monkeypatch.setattr(news, "download_article", fake_download)
    report_progress = AsyncMock()

    result = await news.process_gnews_articles(
        [
            {"url": "https://example.com/first"},
            {"url": "https://example.com/missing"},
            {"url": "https://example.com/third"},
        ],
        nlp=False,
        report_progress=report_progress,
        max_concurrency=2,
    )

    assert [article.label for article in result] == ["first", "third"]
    assert [call.args for call in report_progress.await_args_list] == [(0, 3), (2, 3)]


@pytest.mark.asyncio
async def test_download_article_offloads_blocking_validation_and_scraper(monkeypatch):
    event_loop_thread = threading.get_ident()
    worker_threads: list[tuple[str, int]] = []
    article = FakeArticle("article")

    class FakeValidator:
        def validate_url(self, url: str) -> str:
            worker_threads.append(("validate", threading.get_ident()))
            return url

    def fake_scraper_download(url: str, target_validator):
        worker_threads.append(("scraper", threading.get_ident()))
        return article

    monkeypatch.setattr(news, "ArticleTargetValidator", FakeValidator)
    monkeypatch.setattr(news, "download_article_with_scraper", fake_scraper_download)

    result = await news.download_article("https://example.com/article")

    assert result is article
    assert {kind for kind, _ in worker_threads} == {"validate", "scraper"}
    assert all(thread_id != event_loop_thread for _, thread_id in worker_threads)


def test_scraper_is_reused_per_thread_but_not_shared_between_threads(monkeypatch):
    created: list[object] = []
    barrier = threading.Barrier(2)

    def fake_create_scraper(**kwargs):
        scraper = object()
        created.append(scraper)
        return scraper

    monkeypatch.setattr(news, "_scraper_local", threading.local())
    monkeypatch.setattr(news.cloudscraper, "create_scraper", fake_create_scraper)

    def worker():
        first = news.get_scraper()
        barrier.wait(timeout=2)
        second = news.get_scraper()
        return first, second

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: worker(), range(2)))

    assert len(created) == 2
    assert all(first is second for first, second in results)
    assert results[0][0] is not results[1][0]
