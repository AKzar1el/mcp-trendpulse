import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_trendpulse import news


class FakeArticle:
    def __init__(self, label: str):
        self.label = label
        self.title = label
        self.text = f"text for {label}"
        self.nlp_calls = 0
        self.summary = ""
        self.keywords = []

    def nlp(self):
        self.nlp_calls += 1
        self.summary = f"summary for {self.label}"
        self.keywords = [self.label]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "extracted_publisher, expected_publisher",
    [("", "Example & Journal"), ("Original Publisher", "Original Publisher")],
)
async def test_article_publisher_uses_feed_only_when_extraction_is_missing(
    monkeypatch, extracted_publisher, expected_publisher
):
    article = FakeArticle("News item")
    article.meta_site_name = extracted_publisher
    monkeypatch.setattr(news, "download_article", AsyncMock(return_value=article))

    result = await news.process_gnews_articles(
        [{"url": "https://example.com/article", "publisher": {"title": "Example &amp; Journal"}}],
        nlp=False,
    )

    assert len(result) == 1
    assert result[0].meta_site_name == expected_publisher


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
    assert [article.summary for article in result] == [f"summary for {label}" for label in delays]
    assert [article.keywords for article in result] == [[label] for label in delays]
    assert all(article.nlp_calls == 0 for article in result)  # NLP ran on detached copies.


@pytest.mark.asyncio
async def test_process_gnews_articles_preserves_other_items_when_one_nlp_fails(monkeypatch):
    class BrokenNlpArticle(FakeArticle):
        def nlp(self):
            self.nlp_calls += 1
            self.summary = "partial, untrustworthy summary"
            self.keywords = ["partial"]
            raise RuntimeError("article enrichment failed")

    async def fake_download(url: str):
        label = url.rsplit("/", 1)[-1]
        return BrokenNlpArticle(label) if label == "bad" else FakeArticle(label)

    monkeypatch.setattr(news, "download_article", fake_download)
    report_progress = AsyncMock()
    result = await news.process_gnews_articles(
        [
            {"url": "https://example.com/first"},
            {"url": "https://example.com/bad"},
            {"url": "https://example.com/third"},
        ],
        nlp=True,
        report_progress=report_progress,
        max_concurrency=2,
    )

    assert [article.label for article in result] == ["first", "bad", "third"]
    assert [article.summary for article in result] == ["summary for first", "", "summary for third"]
    assert [article.nlp_calls for article in result] == [0, 0, 0]
    assert result[1].text == "text for bad"
    assert result[1].summary == ""
    assert result[1].keywords == []
    assert [call.args for call in report_progress.await_args_list] == [(1, 3), (2, 3), (3, 3)]


@pytest.mark.asyncio
async def test_process_gnews_articles_counts_skipped_items_in_progress(monkeypatch):
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
    assert [call.args for call in report_progress.await_args_list] == [(1, 3), (2, 3), (3, 3)]


@pytest.mark.asyncio
async def test_process_gnews_articles_reports_all_stale_items(monkeypatch):
    download = AsyncMock(side_effect=AssertionError("stale items must not be downloaded"))
    monkeypatch.setattr(news, "download_article", download)
    progress = AsyncMock()
    result = await news.process_gnews_articles(
        [
            {"url": "https://example.com/stale-1", "published date": "2024-01-01"},
            {"url": "https://example.com/stale-2", "published date": "2024-01-02"},
        ],
        nlp=False,
        report_progress=progress,
        period=2,
        now=news.datetime(2026, 11, 6, tzinfo=news.timezone.utc),
    )
    assert result == []
    assert [call.args for call in progress.await_args_list] == [(1, 2), (2, 2)]
    download.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_gnews_articles_progress_tracks_out_of_order_failures(monkeypatch):
    async def fake_download(url):
        if url.endswith("/first"):
            await asyncio.sleep(0.03)
            return FakeArticle("first")
        if url.endswith("/invalid"):
            raise ValueError("invalid provider URL")
        return None

    monkeypatch.setattr(news, "download_article", fake_download)
    progress = AsyncMock()
    result = await news.process_gnews_articles(
        [
            {"url": "https://example.com/first"},
            {"url": "https://example.com/invalid"},
            {"url": "https://example.com/missing"},
        ],
        nlp=False,
        report_progress=progress,
        max_concurrency=3,
    )
    assert [article.label for article in result] == ["first"]
    assert [call.args for call in progress.await_args_list] == [(1, 3), (2, 3), (3, 3)]


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


@pytest.mark.asyncio
async def test_download_article_does_not_retry_challenge_page_with_unpinned_browser(monkeypatch):
    scraper_article = FakeArticle("Attention Required!")
    scraper_article.text = (
        "Why have I been blocked? This website is using a security service to protect itself "
        "from online attacks. Cloudflare Ray ID 1234."
    )
    browser_article = FakeArticle("Real article title")
    playwright_download = AsyncMock(return_value=browser_article)

    class FakeValidator:
        def validate_url(self, url: str) -> str:
            return url

    monkeypatch.setattr(news, "ArticleTargetValidator", FakeValidator)
    monkeypatch.setattr(news, "download_article_with_scraper", lambda url, target_validator: scraper_article)
    monkeypatch.setattr(news, "download_article_with_playwright", playwright_download)

    result = await news.download_article("https://example.com/article")

    assert result is None
    playwright_download.assert_not_awaited()


@pytest.mark.asyncio
async def test_download_article_rejects_challenge_page_after_playwright_fallback(monkeypatch):
    challenge_article = FakeArticle("Are you a robot?")
    challenge_article.text = (
        "Why did this happen? Please make sure your browser supports JavaScript and cookies. "
        "Block reference ID: abc123."
    )

    class FakeValidator:
        def validate_url(self, url: str) -> str:
            return url

    monkeypatch.setattr(news, "ArticleTargetValidator", FakeValidator)
    monkeypatch.setattr(news, "download_article_with_scraper", lambda url, target_validator: challenge_article)
    monkeypatch.setattr(news, "download_article_with_playwright", AsyncMock(return_value=challenge_article))

    result = await news.download_article("https://example.com/article")

    assert result is None


@pytest.mark.asyncio
async def test_download_article_does_not_retry_publisher_shell_with_unpinned_browser(monkeypatch):
    scraper_article = FakeArticle("Real publisher headline")
    scraper_article.text = "There are no new alerts at this time"
    browser_article = FakeArticle("Real publisher headline")
    browser_article.text = "The actual article body is available after the rendered page loads."
    playwright_download = AsyncMock(return_value=browser_article)

    class FakeValidator:
        def validate_url(self, url: str) -> str:
            return url

    monkeypatch.setattr(news, "ArticleTargetValidator", FakeValidator)
    monkeypatch.setattr(news, "download_article_with_scraper", lambda url, target_validator: scraper_article)
    monkeypatch.setattr(news, "download_article_with_playwright", playwright_download)

    result = await news.download_article("https://example.com/article")

    assert result is None
    playwright_download.assert_not_awaited()


@pytest.mark.asyncio
async def test_download_article_strips_shell_prefix_from_substantive_scraper_text(monkeypatch):
    article = FakeArticle("Where the U.S. and China differ on global AI regulation")
    article.text = (
        "There are no new alerts at this time "
        "NBC News reports substantive details about global AI regulation."
    )
    playwright_download = AsyncMock()

    class FakeValidator:
        def validate_url(self, url: str) -> str:
            return url

    monkeypatch.setattr(news, "ArticleTargetValidator", FakeValidator)
    monkeypatch.setattr(news, "download_article_with_scraper", lambda url, target_validator: article)
    monkeypatch.setattr(news, "download_article_with_playwright", playwright_download)

    result = await news.download_article("https://example.com/article")

    assert result is article
    assert article.text == "NBC News reports substantive details about global AI regulation."
    playwright_download.assert_not_awaited()


@pytest.mark.asyncio
async def test_download_article_preserves_natural_sentence_starting_with_shell_phrase(monkeypatch):
    article = FakeArticle("Emergency system remains quiet during policy debate")
    original_text = (
        "There are no new alerts at this time, but officials say the policy debate "
        "is changing quickly and published a detailed update for residents."
    )
    article.text = original_text

    class FakeValidator:
        def validate_url(self, url: str) -> str:
            return url

    monkeypatch.setattr(news, "ArticleTargetValidator", FakeValidator)
    monkeypatch.setattr(news, "download_article_with_scraper", lambda url, target_validator: article)

    result = await news.download_article("https://example.com/article")

    assert result is article
    assert article.text == original_text


def test_scraper_is_reused_per_thread_but_not_shared_between_threads(monkeypatch):
    created: list[object] = []
    barrier = threading.Barrier(2)

    def fake_create_scraper(**kwargs):
        scraper = MagicMock()
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
    assert all(scraper.trust_env is False and scraper.proxies == {} for scraper in created)
    assert all(scraper.mount.call_count == 2 for scraper in created)
