import pytest
from fastmcp import Client
from mcp_trendpulse.server import mcp
from mcp_trendpulse.news import (
    download_article_with_playwright,
    save_article_to_json,
    download_article,
    BrowserManager,
)
from pathlib import Path


@pytest.fixture
def mcp_server():
    yield mcp


async def test_smoke(mcp_server):
    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        assert isinstance(tools, list)


async def test_download_article():
    async with BrowserManager():
        article = await download_article("nytimes.com")
        assert article is None
        article = await download_article_with_playwright(
            "https://archive.nytimes.com/www.nytimes.com/learning/general/onthisday/big/0720.html"
        )
        assert article is not None
        article_path = Path(__file__).parent / Path("test.json")
        save_article_to_json(article, str(article_path))
        assert article_path.exists()
        article_path.unlink()
    with pytest.raises(RuntimeError):
        article = await download_article_with_playwright("nytimes.com")


def _articles(result):
    return result.structured_content.get("result", [])


async def test_get_news_by_keyword(mcp_server):
    async with Client(mcp_server) as client:
        params = {"keyword": "AI", "period": 3, "max_results": 2}
        result = await client.call_tool("get_news_by_keyword", params)
        articles = _articles(result)
        assert isinstance(articles, list)
        assert len(articles) <= 2
        for article in articles:
            assert "title" in article
            assert "url" in article


async def test_get_news_by_location(mcp_server):
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


async def test_get_news_by_topic(mcp_server):
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


async def test_get_top_news(mcp_server):
    async with Client(mcp_server) as client:
        params = {"period": 2, "max_results": 2}
        result = await client.call_tool("get_top_news", params)
        articles = _articles(result)
        assert isinstance(articles, list)
        assert len(articles) <= 2
        for article in articles:
            assert "title" in article
            assert "url" in article


async def test_get_trending_terms(mcp_server):
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


from unittest.mock import patch, MagicMock
import pandas as pd

class MockNewsArticle:
    def __init__(self, title, url, source, picture=None, time=None, snippet=None):
        self.title = title
        self.url = url
        self.source = source
        self.picture = picture
        self.time = time
        self.snippet = snippet

class MockTrendKeyword:
    def __init__(self, keyword, volume, volume_growth_pct, started_timestamp, news=None):
        self.keyword = keyword
        self.volume = volume
        self.volume_growth_pct = volume_growth_pct
        self.started_timestamp = started_timestamp
        self.news = news or []

class MockTrendKeywordLite:
    def __init__(self, keyword, volume, trend_keywords=None, link=None, started=None, picture=None, news=None):
        self.keyword = keyword
        self.volume = volume
        self.trend_keywords = trend_keywords or []
        self.link = link or ""
        self.started = started
        self.picture = picture
        self.news = news or []


async def test_get_trends(mcp_server):
    dates = pd.date_range(start='2021-07-11', periods=5, freq='W')
    mock_df = pd.DataFrame({
        'artificial intelligence': [45.0, 46.0, 47.0, 48.0, 50.0]
    }, index=pd.DatetimeIndex(dates, name='time [UTC]'))

    with patch('mcp_trendpulse.news.tr') as mock_tr:
        mock_tr.interest_over_time.return_value = mock_df

        async with Client(mcp_server) as client:
            params = {
                "keyword": "artificial intelligence",
                "source": "google search",
                "data_mode": "weekly",
                "geo": "US"
            }
            result = await client.call_tool("get_trends", params)
            trend_points = _articles(result)
            assert isinstance(trend_points, list)
            assert len(trend_points) == 5
            assert trend_points[0]["keyword"] == "artificial intelligence"
            assert trend_points[0]["value"] == 45.0
            assert trend_points[0]["date"] == "2021-07-11"
            assert trend_points[-1]["value"] == 50.0


async def test_get_growth(mcp_server):
    dates = pd.date_range(start='2025-07-01', periods=53, freq='W')
    values = [20.0] * 10 + [40.0] * 20 + [80.0] * 23
    mock_df = pd.DataFrame({
        'electric vehicles': values
    }, index=pd.DatetimeIndex(dates, name='time [UTC]'))

    with patch('mcp_trendpulse.news.tr') as mock_tr:
        mock_tr.interest_over_time.return_value = mock_df

        async with Client(mcp_server) as client:
            params = {
                "keyword": "electric vehicles",
                "source": "google search",
                "percent_growth": ["3M", "1Y"]
            }
            result = await client.call_tool("get_growth", params)
            growth_results = _articles(result)
            assert isinstance(growth_results, list)
            assert len(growth_results) == 1
            assert growth_results[0]["keyword"] == "electric vehicles"
            growth_dict = growth_results[0]["growth"]
            assert "3M" in growth_dict
            assert "1Y" in growth_dict
            assert growth_dict["1Y"] == 300.0


async def test_get_ranked_trends(mcp_server):
    mock_trends = [
        MockTrendKeyword("switzerland vs colombia", 500000, 1000.0, [1783389000], [
            MockNewsArticle("Switzerland Beats Colombia", "https://news.com/1", "News Source", "https://img.com/1", 1783389100, "Switzerland won.")
        ]),
        MockTrendKeyword("hybrid cars", 100000, 50.0, [1783389010])
    ]

    with patch('mcp_trendpulse.news.tr') as mock_tr:
        mock_tr.trending_now.return_value = mock_trends

        async with Client(mcp_server) as client:
            params = {
                "source": "google search",
                "sort": "wow_pct_change",
                "limit": 10
            }
            result = await client.call_tool("get_ranked_trends", params)
            ranked_trends = _articles(result)
            assert isinstance(ranked_trends, list)
            assert len(ranked_trends) == 2
            assert ranked_trends[0]["keyword"] == "switzerland vs colombia"
            assert ranked_trends[0]["growth_pct"] == 1000.0
            assert len(ranked_trends[0]["news"]) == 1
            assert ranked_trends[0]["news"][0]["title"] == "Switzerland Beats Colombia"

            params["sort"] = "volume"
            result = await client.call_tool("get_ranked_trends", params)
            ranked_trends_vol = _articles(result)
            assert ranked_trends_vol[0]["keyword"] == "switzerland vs colombia"


async def test_get_top_trends(mcp_server):
    mock_trends_lite = [
        MockTrendKeywordLite("switzerland vs colombia", "500K+", ["switzerland", "colombia"], "https://trends.com/rss", 1783389000, "https://img.com/1", [
            MockNewsArticle("Switzerland Beats Colombia", "https://news.com/1", "News Source", "https://img.com/1", 1783389100, "Switzerland won.")
        ])
    ]

    with patch('mcp_trendpulse.news.tr') as mock_tr:
        mock_tr.trending_now_by_rss.return_value = mock_trends_lite
        mock_tr.daily_trends_deprecated_by_rss.return_value = mock_trends_lite

        async with Client(mcp_server) as client:
            params = {
                "type": "Google Trends",
                "limit": 5
            }
            result = await client.call_tool("get_top_trends", params)
            top_trends = _articles(result)
            assert isinstance(top_trends, list)
            assert len(top_trends) == 1
            assert top_trends[0]["keyword"] == "switzerland vs colombia"
            assert top_trends[0]["volume"] == "500K+"
            assert len(top_trends[0]["news"]) == 1

            params["type"] = "Daily Trends"
            result = await client.call_tool("get_top_trends", params)
            daily_trends = _articles(result)
            assert len(daily_trends) == 1
            assert daily_trends[0]["keyword"] == "switzerland vs colombia"

