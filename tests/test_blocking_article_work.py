from types import SimpleNamespace
from unittest.mock import AsyncMock

from mcp_trendpulse import news, server


class ValidArticleTarget:
    def validate_url(self, url):
        return url


class NlpArticle:
    def __init__(self):
        self.text = "Article body"
        self.summary = ""
        self.nlp_calls = 0

    def nlp(self):
        self.nlp_calls += 1
        self.summary = "Local summary"


async def test_download_article_offloads_google_news_decoding_and_scraping(monkeypatch):
    thread_calls = []
    article = SimpleNamespace(text="Article body")

    async def run_in_thread(function, *args, **kwargs):
        thread_calls.append((function, args, kwargs))
        return function(*args, **kwargs)

    def decode_google_news_url(url):
        return "https://example.com/article"

    def download_with_scraper(url, target_validator):
        assert url == "https://example.com/article"
        assert isinstance(target_validator, ValidArticleTarget)
        return article

    monkeypatch.setattr(news, "ArticleTargetValidator", ValidArticleTarget)
    monkeypatch.setattr(news, "decode_url", decode_google_news_url)
    monkeypatch.setattr(news, "download_article_with_scraper", download_with_scraper)
    monkeypatch.setattr(news.asyncio, "to_thread", run_in_thread)

    result = await news.download_article("https://news.google.com/rss/articles/example")

    assert result is article
    assert [function.__name__ for function, _, _ in thread_calls] == [
        "validate_url",
        "decode_google_news_url",
        "validate_url",
        "download_with_scraper",
    ]
    assert thread_calls[0][0].__self__ is thread_calls[2][0].__self__
    assert [args for _, args, _ in thread_calls] == [
        ("https://news.google.com/rss/articles/example",),
        ("https://news.google.com/rss/articles/example",),
        ("https://example.com/article",),
        ("https://example.com/article", thread_calls[0][0].__self__),
    ]


async def test_process_gnews_articles_offloads_nlp_before_reporting_progress(monkeypatch):
    events = []
    article = NlpArticle()

    async def run_in_thread(function, *args, **kwargs):
        events.append("nlp")
        return function(*args, **kwargs)

    async def report_progress(progress, total):
        events.append((progress, total))

    monkeypatch.setattr(news.asyncio, "to_thread", run_in_thread)
    monkeypatch.setattr(news, "download_article", AsyncMock(return_value=article))

    result = await news.process_gnews_articles(
        [{"url": "https://example.com/article"}],
        nlp=True,
        report_progress=report_progress,
    )

    assert result == [article]
    assert article.nlp_calls == 1
    assert events == ["nlp", (0, 1)]


async def test_summarize_articles_offloads_nlp_fallback(monkeypatch):
    thread_calls = []
    article = NlpArticle()

    async def run_in_thread(function, *args, **kwargs):
        thread_calls.append((function, args, kwargs))
        return function(*args, **kwargs)

    monkeypatch.setattr(server.asyncio, "to_thread", run_in_thread)

    await server.summarize_articles([article], None)

    assert article.summary == "Local summary"
    assert article.nlp_calls == 1
    assert thread_calls == [(article.nlp, (), {})]
