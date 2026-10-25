from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from mcp_trendpulse import news, providers, server


GOOGLE_LINK = "https://news.google.com/rss/articles/CBMTest"
NOW = datetime(2026, 10, 25, 2, 40, tzinfo=timezone.utc)


async def test_rss_headlines_are_labeled_filtered_and_never_extracted(monkeypatch):
    rows = [
        {
            "title": "AI &amp; Discovery",
            "url": GOOGLE_LINK,
            "published date": "Sun, 25 Oct 2026 01:30:00 GMT",
            "publisher": {"title": "Publisher &amp; Co"},
            "description": "A feed teaser is not article text",
        },
        {"title": "duplicate", "url": GOOGLE_LINK, "published date": "Sun, 25 Oct 2026 01:30:00 GMT"},
        {"title": "stale", "url": "https://news.google.com/rss/articles/stale", "published date": "Mon, 20 Oct 2025 00:00:00 GMT"},
        {"title": "future", "url": "https://news.google.com/rss/articles/future", "published date": "Sun, 25 Oct 2026 04:00:00 GMT"},
        {"title": "bad domain", "url": "https://evil.example/rss/articles/fake", "published date": "Sun, 25 Oct 2026 01:30:00 GMT"},
        {"title": "no date", "url": "https://news.google.com/rss/articles/undated"},
        {"title": "bad path", "url": "https://news.google.com/news/fake", "published date": "Sun, 25 Oct 2026 01:30:00 GMT"},
    ]
    operation = AsyncMock(return_value=rows)
    forbidden_download = AsyncMock(side_effect=AssertionError("article extraction forbidden"))
    monkeypatch.setattr(news, "_new_google_news", lambda period, max_results: object())
    monkeypatch.setattr(news, "_call_google_news_async", operation)
    monkeypatch.setattr(news, "download_article", forbidden_download)

    result = await news.get_rss_headlines_by_keyword("OpenAI", period=2, max_results=10, now=NOW)
    assert len(result) == 1
    assert result[0]["title"] == "AI & Discovery"
    assert result[0]["url"] == GOOGLE_LINK
    assert result[0]["meta_site_name"] == "Publisher & Co"
    assert result[0]["meta_data"] == {
        "content_level": "rss_headline_only",
        "source": "google_news_rss",
    }
    assert result[0]["publish_date"].startswith("2026-10-25T01:30:00")
    assert "text" not in result[0] and "summary" not in result[0]
    forbidden_download.assert_not_awaited()
    operation.assert_awaited_once()


async def test_rss_headlines_limit_after_validity_filter(monkeypatch):
    rows = [
        {"title": "A", "url": "https://news.google.com/rss/articles/A", "published date": "Sun, 25 Oct 2026 01:30:00 GMT"},
        {"title": "B", "url": "https://news.google.com/rss/articles/B", "published date": "Sun, 25 Oct 2026 01:30:00 GMT"},
    ]
    monkeypatch.setattr(news, "_new_google_news", lambda period, max_results: object())
    monkeypatch.setattr(news, "_call_google_news_async", AsyncMock(return_value=rows))
    result = await news.get_rss_headlines_by_keyword("OpenAI", period=1, max_results=1, now=NOW)
    assert [item["title"] for item in result] == ["A"]


async def test_rss_headlines_reject_blank_keyword_without_provider_call(monkeypatch):
    operation = AsyncMock()
    monkeypatch.setattr(news, "_call_google_news_async", operation)
    with pytest.raises(ValueError):
        await news.get_rss_headlines_by_keyword("   ")
    operation.assert_not_awaited()


async def test_rss_headlines_server_is_explicit_metadata_only(monkeypatch):
    provider = SimpleNamespace(
        get_rss_headlines_by_keyword=AsyncMock(return_value=[{
            "title": "A headline",
            "url": GOOGLE_LINK,
            "publish_date": "2026-10-25T01:30:00+00:00",
            "meta_site_name": "Example publisher",
            "meta_data": {"source": "google_news_rss", "content_level": "rss_headline_only"},
        }]),
    )
    monkeypatch.setattr(server, "get_provider_set", lambda: SimpleNamespace(news=provider))
    forbidden_summary = AsyncMock(side_effect=AssertionError("summary is forbidden"))
    monkeypatch.setattr(server, "summarize_articles", forbidden_summary)
    monkeypatch.setattr(server, "set_newspaper_article_fields", Mock(side_effect=AssertionError("article fields should not be touched")))
    result = await server.get_news_by_keyword(
        None, keyword="OpenAI", period=1, max_results=4, headlines_only=True
    )
    assert len(result) == 1
    assert result[0].title == "A headline"
    assert result[0].url == GOOGLE_LINK
    assert result[0].meta_data["content_level"] == "rss_headline_only"
    assert result[0].text is None and result[0].summary is None
    forbidden_summary.assert_not_awaited()
    provider.get_rss_headlines_by_keyword.assert_awaited_once_with(
        keyword="OpenAI", period=1, max_results=4
    )


async def test_community_adapter_forwards_rss_only(monkeypatch):
    operation = AsyncMock(return_value=[])
    monkeypatch.setattr(news, "get_rss_headlines_by_keyword", operation)
    adapter = providers.CommunityNewsProvider()
    assert await adapter.get_rss_headlines_by_keyword("OpenAI", period=2, max_results=3) == []
    operation.assert_awaited_once_with(keyword="OpenAI", period=2, max_results=3)


async def test_topic_rss_headlines_are_labeled_and_never_download(monkeypatch):
    feed = AsyncMock(return_value=[{
        "title": "Latest &amp; Technology",
        "url": GOOGLE_LINK,
        "published date": "Sun, 25 Oct 2026 01:30:00 GMT",
        "publisher": {"title": "Tech Publisher"},
    }])
    forbidden = AsyncMock(side_effect=AssertionError("article extraction forbidden"))
    monkeypatch.setattr(news, "_new_google_news", lambda period, max_results: object())
    monkeypatch.setattr(news, "_call_google_news_async", feed)
    monkeypatch.setattr(news, "download_article", forbidden)
    rows = await news.get_rss_headlines_by_topic("technology", period=2, max_results=3, now=NOW)
    assert len(rows) == 1
    assert rows[0]["title"] == "Latest & Technology"
    assert rows[0]["url"] == GOOGLE_LINK
    assert rows[0]["meta_data"]["content_level"] == "rss_headline_only"
    assert "text" not in rows[0] and "summary" not in rows[0]
    assert feed.await_args.args[1:] == ("get_news_by_topic", "TECHNOLOGY")
    forbidden.assert_not_awaited()


async def test_topic_rss_rejects_unknown_topic_before_fetch(monkeypatch):
    feed = AsyncMock()
    monkeypatch.setattr(news, "_call_google_news_async", feed)
    with pytest.raises(ValueError, match="Unsupported news topic"):
        await news.get_rss_headlines_by_topic("invented-topic")
    feed.assert_not_awaited()


async def test_topic_headline_only_server_skips_article_and_summary(monkeypatch):
    provider = SimpleNamespace(get_rss_headlines_by_topic=AsyncMock(return_value=[{
        "title": "Technology report",
        "url": GOOGLE_LINK,
        "publish_date": "2026-10-25T01:30:00+00:00",
        "meta_site_name": "Tech Publisher",
        "meta_data": {"content_level": "rss_headline_only", "source": "google_news_rss"},
    }]))
    monkeypatch.setattr(server, "get_provider_set", lambda: SimpleNamespace(news=provider))
    summary = AsyncMock(side_effect=AssertionError("summary must not run"))
    monkeypatch.setattr(server, "summarize_articles", summary)
    monkeypatch.setattr(server, "set_newspaper_article_fields", Mock(side_effect=AssertionError("article fields must not change")))
    result = await server.get_news_by_topic(None, topic="TECHNOLOGY", period=1, max_results=2, headlines_only=True)
    assert len(result) == 1
    assert result[0].title == "Technology report"
    assert result[0].meta_data["content_level"] == "rss_headline_only"
    assert result[0].text is None and result[0].summary is None
    provider.get_rss_headlines_by_topic.assert_awaited_once_with(topic="TECHNOLOGY", period=1, max_results=2)
    summary.assert_not_awaited()


async def test_community_adapter_forwards_topic_rss_only(monkeypatch):
    fn = AsyncMock(return_value=[])
    monkeypatch.setattr(news, "get_rss_headlines_by_topic", fn)
    assert await providers.CommunityNewsProvider().get_rss_headlines_by_topic("TECHNOLOGY", period=2, max_results=3) == []
    fn.assert_awaited_once_with(topic="TECHNOLOGY", period=2, max_results=3)


async def test_top_news_rss_headlines_no_query_argument_and_no_extraction(monkeypatch):
    feed = AsyncMock(return_value=[{
        "title": "World &amp; research",
        "url": GOOGLE_LINK,
        "published date": "Sun, 25 Oct 2026 01:30:00 GMT",
        "publisher": {"title": "News publisher"},
    }])
    forbidden_download = AsyncMock(side_effect=AssertionError("article extraction forbidden"))
    monkeypatch.setattr(news, "_new_google_news", lambda period, max_results: object())
    monkeypatch.setattr(news, "_call_google_news_async", feed)
    monkeypatch.setattr(news, "download_article", forbidden_download)
    rows = await news.get_rss_headlines_for_top_news(period=2, max_results=3, now=NOW)
    assert len(rows) == 1
    assert rows[0]["title"] == "World & research"
    assert rows[0]["url"] == GOOGLE_LINK
    assert rows[0]["meta_data"]["content_level"] == "rss_headline_only"
    assert "text" not in rows[0] and "summary" not in rows[0]
    assert feed.await_args.args[1:] == ("get_top_news",)
    forbidden_download.assert_not_awaited()


async def test_top_news_headline_only_server_skips_article_and_summary(monkeypatch):
    provider = SimpleNamespace(get_rss_headlines_for_top_news=AsyncMock(return_value=[{
        "title": "World research",
        "url": GOOGLE_LINK,
        "publish_date": "2026-10-25T01:30:00+00:00",
        "meta_site_name": "Publisher",
        "meta_data": {"content_level": "rss_headline_only", "source": "google_news_rss"},
    }]))
    monkeypatch.setattr(server, "get_provider_set", lambda: SimpleNamespace(news=provider))
    summary = AsyncMock(side_effect=AssertionError("summary must not run"))
    monkeypatch.setattr(server, "summarize_articles", summary)
    monkeypatch.setattr(server, "set_newspaper_article_fields", Mock(side_effect=AssertionError("article fields must not change")))
    result = await server.get_top_news(None, period=1, max_results=2, headlines_only=True)
    assert len(result) == 1
    assert result[0].title == "World research"
    assert result[0].text is None and result[0].summary is None
    assert result[0].meta_data["content_level"] == "rss_headline_only"
    provider.get_rss_headlines_for_top_news.assert_awaited_once_with(period=1, max_results=2)
    summary.assert_not_awaited()


async def test_community_adapter_forwards_top_news_rss_only(monkeypatch):
    fn = AsyncMock(return_value=[])
    monkeypatch.setattr(news, "get_rss_headlines_for_top_news", fn)
    assert await providers.CommunityNewsProvider().get_rss_headlines_for_top_news(period=2, max_results=3) == []
    fn.assert_awaited_once_with(period=2, max_results=3)
