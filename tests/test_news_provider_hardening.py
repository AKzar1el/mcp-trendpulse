from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from mcp_trendpulse import news


async def test_location_news_quotes_location_and_falls_back_to_search(monkeypatch):
    location_call = Mock(return_value=[])
    search_call = Mock(return_value=[{"url": "https://example.com/article"}])
    client = SimpleNamespace(
        get_news_by_location=location_call,
        get_news=search_call,
    )

    async def run_in_thread(function, *args, **kwargs):
        return function(*args, **kwargs)

    process = AsyncMock(return_value=[])
    monkeypatch.setattr(news, "_new_google_news", lambda period, max_results: client)
    monkeypatch.setattr(news.asyncio, "to_thread", run_in_thread)
    monkeypatch.setattr(news, "process_gnews_articles", process)

    await news.get_news_by_location("New York", period=2, max_results=3, nlp=False)

    location_call.assert_called_once_with("New%20York")
    search_call.assert_called_once_with("New York")
    process.assert_awaited_once()
    assert process.await_args.kwargs["period"] == 2


async def test_process_gnews_articles_enforces_requested_period(monkeypatch):
    now = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
    feed_items = [
        {
            "url": "https://example.com/current",
            "published date": "Sun, 20 Sep 2026 10:00:00 GMT",
        },
        {
            "url": "https://example.com/stale-feed",
            "published date": "Tue, 09 Jun 2026 10:00:00 GMT",
        },
        {
            "url": "https://example.com/stale-article",
            "published date": "Sun, 20 Sep 2026 09:00:00 GMT",
        },
        {
            "url": "https://example.com/undated",
        },
    ]
    current = SimpleNamespace(text="Current article", publish_date=None)
    stale = SimpleNamespace(
        text="Old article surfaced again",
        publish_date=datetime(2026, 6, 9, 10, 0, tzinfo=timezone.utc),
    )
    undated = SimpleNamespace(text="Article with no usable date", publish_date=None)
    download = AsyncMock(
        side_effect=lambda url: {
            "https://example.com/current": current,
            "https://example.com/stale-article": stale,
            "https://example.com/undated": undated,
        }.get(url)
    )
    monkeypatch.setattr(news, "download_article", download)

    result = await news.process_gnews_articles(
        feed_items,
        nlp=False,
        period=1,
        now=now,
    )

    assert result == [current]
    assert current.publish_date == datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc)
    assert [call.args[0] for call in download.await_args_list] == [
        "https://example.com/current",
        "https://example.com/stale-article",
        "https://example.com/undated",
    ]


async def test_process_gnews_articles_skips_one_unresolvable_provider_item(monkeypatch):
    valid = SimpleNamespace(
        title="Valid article",
        text="Valid article body",
        publish_date=None,
    )

    async def download(url):
        if url.endswith("/unresolvable"):
            raise ValueError("Article URL hostname could not be resolved safely.")
        return valid

    monkeypatch.setattr(news, "download_article", download)

    result = await news.process_gnews_articles(
        [
            {"url": "https://example.invalid/unresolvable", "title": "Broken provider item"},
            {"url": "https://example.com/valid", "title": "Valid article"},
        ],
        nlp=False,
    )

    assert result == [valid]


async def test_process_gnews_articles_restores_feed_title_for_challenge_placeholder(monkeypatch):
    article = SimpleNamespace(
        title="Attention Required!",
        text="Valid article body",
        publish_date=None,
    )
    monkeypatch.setattr(news, "download_article", AsyncMock(return_value=article))

    result = await news.process_gnews_articles(
        [
            {
                "url": "https://example.com/article",
                "title": "Actual article title",
            }
        ],
        nlp=False,
    )

    assert result == [article]
    assert article.title == "Actual article title"


async def test_process_gnews_articles_rejects_anti_bot_challenge_page(monkeypatch):
    article = SimpleNamespace(
        title="Attention Required!",
        text=(
            "Why have I been blocked? This website is using a security service to protect itself "
            "from online attacks. Cloudflare Ray ID 1234."
        ),
        publish_date=None,
    )
    monkeypatch.setattr(news, "download_article", AsyncMock(return_value=article))

    result = await news.process_gnews_articles(
        [
            {
                "url": "https://example.com/article",
                "title": "Actual article title",
            }
        ],
        nlp=False,
    )

    assert result == []
    assert article.title == "Attention Required!"


async def test_process_gnews_articles_rejects_robot_challenge_page(monkeypatch):
    article = SimpleNamespace(
        title="Are you a robot?",
        text=(
            "Why did this happen? Please make sure your browser supports JavaScript and cookies. "
            "Block reference ID: abc123."
        ),
        publish_date=None,
    )
    monkeypatch.setattr(news, "download_article", AsyncMock(return_value=article))

    result = await news.process_gnews_articles(
        [
            {
                "url": "https://example.com/article",
                "title": "Real Bloomberg headline",
            }
        ],
        nlp=False,
    )

    assert result == []


async def test_process_gnews_articles_rejects_verification_successful_challenge_page(monkeypatch):
    article = SimpleNamespace(
        title="Just a moment...",
        text="Verification successful. Waiting for example.com to respond",
        publish_date=None,
    )
    monkeypatch.setattr(news, "download_article", AsyncMock(return_value=article))

    result = await news.process_gnews_articles(
        [
            {
                "url": "https://example.com/article",
                "title": "Real publisher headline",
            }
        ],
        nlp=False,
    )

    assert result == []


async def test_process_gnews_articles_preserves_real_extracted_title(monkeypatch):
    article = SimpleNamespace(
        title="Publisher's canonical title",
        text="Valid article body",
        publish_date=None,
    )
    monkeypatch.setattr(news, "download_article", AsyncMock(return_value=article))

    result = await news.process_gnews_articles(
        [
            {
                "url": "https://example.com/article",
                "title": "Google News feed title",
            }
        ],
        nlp=False,
    )

    assert result == [article]
    assert article.title == "Publisher's canonical title"


async def test_invalid_news_topic_is_rejected_before_provider_call(monkeypatch):
    provider_factory = Mock()
    monkeypatch.setattr(news, "_new_google_news", provider_factory)

    with pytest.raises(ValueError, match="Unsupported news topic"):
        await news.get_news_by_topic("NOT_A_REAL_TOPIC", nlp=False)

    provider_factory.assert_not_called()
