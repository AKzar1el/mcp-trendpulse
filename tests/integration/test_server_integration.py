"""Live MCP provider smoke tests.

Run explicitly with: ``uv run pytest tests/integration -m integration``.
"""

from pathlib import Path

import pytest
from fastmcp import Client

from mcp_trendpulse import server
from mcp_trendpulse.news import BrowserManager, download_article, download_article_with_playwright, save_article_to_json


pytestmark = [pytest.mark.integration, pytest.mark.network]

mcp = server.mcp


@pytest.fixture
def mcp_server():
    yield mcp


def _articles(result):
    return result.structured_content.get("result", [])


@pytest.mark.browser
async def test_download_article_from_live_publisher(tmp_path: Path):
    article_url = "https://archive.nytimes.com/www.nytimes.com/learning/general/onthisday/big/0720.html"

    async with BrowserManager():
        article = await download_article(article_url)
        assert article is not None
        article = await download_article_with_playwright(article_url)
        assert article is not None
        article_path = tmp_path / "article.json"
        save_article_to_json(article, str(article_path))
        assert article_path.exists()


@pytest.mark.browser
async def test_get_news_by_keyword_uses_google_news(mcp_server):
    async with Client(mcp_server) as client:
        params = {"keyword": "AI", "period": 3, "max_results": 2}
        result = await client.call_tool("get_news_by_keyword", params)
        articles = _articles(result)
        assert isinstance(articles, list)
        assert len(articles) <= 2
        for article in articles:
            assert "title" in article
            assert "url" in article


@pytest.mark.browser
async def test_get_news_by_location_uses_google_news(mcp_server):
    async with Client(mcp_server) as client:
        params = {"location": "California", "period": 3, "max_results": 2}
        result = await client.call_tool("get_news_by_location", params)
        articles = _articles(result)
        assert isinstance(articles, list)
        assert len(articles) <= 2
        for article in articles:
            assert "title" in article
            assert "url" in article
        params = {"location": "Mars", "period": 3, "max_results": 2}
        result = await client.call_tool("get_news_by_location", params)
        assert _articles(result) == []


@pytest.mark.browser
async def test_get_news_by_topic_uses_google_news(mcp_server):
    async with Client(mcp_server) as client:
        params = {"topic": "TECHNOLOGY", "period": 3, "max_results": 2}
        result = await client.call_tool("get_news_by_topic", params)
        articles = _articles(result)
        assert isinstance(articles, list)
        assert len(articles) <= 2
        for article in articles:
            assert "title" in article
            assert "url" in article
        params = {"topic": "CATS", "period": 3, "max_results": 2}
        result = await client.call_tool("get_news_by_topic", params)
        assert _articles(result) == []


@pytest.mark.browser
async def test_get_top_news_uses_google_news(mcp_server):
    async with Client(mcp_server) as client:
        params = {"period": 2, "max_results": 2}
        result = await client.call_tool("get_top_news", params)
        articles = _articles(result)
        assert isinstance(articles, list)
        assert len(articles) <= 2
        for article in articles:
            assert "title" in article
            assert "url" in article


async def test_get_trending_terms_uses_google_trends(mcp_server):
    async with Client(mcp_server) as client:
        params = {"geo": "US", "full_data": True}
        result = await client.call_tool("get_trending_terms", params)
        for item in _articles(result):
            assert "keyword" in item
            assert "volume" in item
            assert "link" in item
        params = {"geo": "US", "full_data": False}
        result = await client.call_tool("get_trending_terms", params)
        for item in _articles(result):
            assert "keyword" in item
            assert "volume" in item
        params = {"geo": "USA", "full_data": True}
        result = await client.call_tool("get_trending_terms", params)
        assert _articles(result) == []
