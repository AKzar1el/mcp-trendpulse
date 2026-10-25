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
