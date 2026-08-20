import inspect
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest
from fastmcp import Client
from mcp_trendpulse import server


mcp = server.mcp


@pytest.fixture
def mcp_server():
    yield mcp


async def test_smoke(mcp_server):
    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        assert isinstance(tools, list)


def _articles(result):
    return result.structured_content.get("result", [])


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


class MockArticle:
    def __init__(self, title="Mock Title", url="https://mock.com", text="Mock body content.", summary="Mock summary."):
        self.title = title
        self.original_url = url
        self.text = text
        self.summary = summary
        self.authors = ["Mock Author"]
        self.publish_date = None
        self.top_image = None
        self.images = []
        self.tags = []

    def parse(self):
        pass

    def nlp(self):
        pass

    def to_json(self, *args, **kwargs):
        return {
            "title": self.title,
            "url": self.original_url,
            "text": self.text,
            "summary": self.summary,
            "authors": self.authors,
        }


class MockSamplingContext:
    def __init__(self, text=None, error=None):
        self.request_context = object()
        self.session = object()
        self.result = SimpleNamespace(text=text)
        self.error = error
        self.sample_calls = 0
        self.warnings = []

    async def sample(self, prompt):
        self.sample_calls += 1
        if self.error:
            raise self.error
        return self.result

    async def warning(self, message):
        self.warnings.append(message)


class SequentialSamplingContext(MockSamplingContext):
    def __init__(self, outcomes):
        super().__init__()
        self.outcomes = iter(outcomes)

    async def sample(self, prompt):
        self.sample_calls += 1
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(text=outcome)


class BrokenProgressSamplingContext(MockSamplingContext):
    async def report_progress(self, progress, total):
        raise RuntimeError("progress unavailable")


class SummarizableMockArticle(MockArticle):
    def __init__(self, nlp_summary="NLP summary", nlp_error=None):
        super().__init__(summary=None)
        self.nlp_summary = nlp_summary
        self.nlp_error = nlp_error
        self.nlp_calls = 0

    def nlp(self):
        self.nlp_calls += 1
        if self.nlp_error:
            raise self.nlp_error
        self.summary = self.nlp_summary


def test_server_module_imports():
    assert server.mcp is mcp


async def test_llm_summarize_article_uses_sampling_result_text():
    article = MockArticle(summary=None)
    ctx = MockSamplingContext("summary")

    assert await server.llm_summarize_article(article, ctx) is True

    assert article.summary == "summary"
    assert ctx.warnings == []


@pytest.mark.parametrize("text", [None, "", " \t\n"])
async def test_llm_summarize_article_rejects_empty_sampling_result_text(text):
    article = MockArticle(summary=None)
    ctx = MockSamplingContext(text)

    assert await server.llm_summarize_article(article, ctx) is False

    assert article.summary == "No summary available."
    assert ctx.warnings == ["LLM Sampling response is empty. Unable to summarize article."]


def test_llm_summarize_article_has_no_text_content_type_check():
    assert "TextContent" not in inspect.getsource(server.llm_summarize_article)


async def test_summarize_articles_skips_nlp_after_successful_sampling():
    article = SummarizableMockArticle()

    await server.summarize_articles([article], MockSamplingContext("LLM summary"))

    assert article.summary == "LLM summary"
    assert article.nlp_calls == 0


async def test_summarize_articles_uses_nlp_after_sampling_exception():
    article = SummarizableMockArticle()

    await server.summarize_articles([article], MockSamplingContext(error=RuntimeError("sampling unavailable")))

    assert article.summary == "NLP summary"
    assert article.nlp_calls == 1


async def test_summarize_articles_uses_nlp_after_empty_sampling_response():
    article = SummarizableMockArticle()

    await server.summarize_articles([article], MockSamplingContext(""))

    assert article.summary == "NLP summary"
    assert article.nlp_calls == 1


async def test_summarize_articles_uses_nlp_without_an_active_sampling_session():
    article = SummarizableMockArticle()
    ctx = MockSamplingContext("LLM summary")
    ctx.request_context = None

    await server.summarize_articles([article], ctx)

    assert article.summary == "NLP summary"
    assert article.nlp_calls == 1
    assert ctx.sample_calls == 0


async def test_summarize_articles_sets_safe_summary_when_sampling_and_nlp_fail():
    article = SummarizableMockArticle(nlp_error=RuntimeError("NLP unavailable"))

    await server.summarize_articles([article], MockSamplingContext(error=RuntimeError("sampling unavailable")))

    assert article.summary == "No summary available."
    assert article.nlp_calls == 1


async def test_summarize_articles_falls_back_per_article():
    sampled_article = SummarizableMockArticle(nlp_summary="NLP summary A")
    fallback_article = SummarizableMockArticle(nlp_summary="NLP summary B")
    ctx = SequentialSamplingContext(["LLM summary A", RuntimeError("sampling unavailable")])

    await server.summarize_articles([sampled_article, fallback_article], ctx)

    assert sampled_article.summary == "LLM summary A"
    assert sampled_article.nlp_calls == 0
    assert fallback_article.summary == "NLP summary B"
    assert fallback_article.nlp_calls == 1


async def test_summarize_articles_tolerates_progress_reporting_failure():
    article = SummarizableMockArticle()

    await server.summarize_articles([article], BrokenProgressSamplingContext("LLM summary"))

    assert article.summary == "LLM summary"
    assert article.nlp_calls == 0


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


async def test_get_news_by_site(mcp_server):
    mock_articles = [MockArticle(title="Site News 1", url="https://nytimes.com/1")]
    with patch("mcp_trendpulse.news.get_news_by_site") as mock_get:
        mock_get.return_value = mock_articles
        async with Client(mcp_server) as client:
            params = {"site": "nytimes.com", "period": 3, "max_results": 2}
            result = await client.call_tool("get_news_by_site", params)
            articles = _articles(result)
            assert isinstance(articles, list)
            assert len(articles) == 1
            assert articles[0]["title"] == "Site News 1"
            assert articles[0]["url"] == "https://nytimes.com/1"


async def test_get_article_content(mcp_server):
    mock_art = MockArticle(title="Article content title", text="Body text of the article.")
    with patch("mcp_trendpulse.news.download_article") as mock_download:
        mock_download.return_value = mock_art
        async with Client(mcp_server) as client:
            params = {
                "url": "https://nytimes.com/1",
                "summarize": False,
                "full_data": True
            }
            result = await client.call_tool("get_article_content", params)
            article = result.structured_content.get("result")
            assert article is not None
            assert article["title"] == "Article content title"
            assert article["text"] == "Body text of the article."


async def test_get_interest_by_region(mcp_server):
    mock_df = pd.DataFrame({
        "geoName": ["California", "Texas"],
        "geoCode": ["US-CA", "US-TX"],
        "python": [100.0, 80.0]
    })
    with patch('mcp_trendpulse.news.tr') as mock_tr:
        mock_tr.interest_by_region.return_value = mock_df
        async with Client(mcp_server) as client:
            params = {
                "keywords": "python",
                "geo": "US",
                "resolution": "REGION"
            }
            result = await client.call_tool("get_interest_by_region", params)
            regions = _articles(result)
            assert isinstance(regions, list)
            assert len(regions) == 2
            assert regions[0]["geo_name"] == "California"
            assert regions[0]["geo_code"] == "US-CA"
            assert regions[0]["values"]["python"] == 100.0


async def test_get_related_queries(mcp_server):
    mock_res = {
        "top": pd.DataFrame({"query": ["python download", "python tutorial"], "value": [100, 50]}),
        "rising": pd.DataFrame({"query": ["python 3.12", "python pillow"], "value": [120, 80]})
    }
    with patch('mcp_trendpulse.news.tr') as mock_tr:
        mock_tr.related_queries.return_value = mock_res
        async with Client(mcp_server) as client:
            params = {"keyword": "python"}
            result = await client.call_tool("get_related_queries", params)
            res_dict = result.structured_content
            assert res_dict is not None
            assert len(res_dict["top"]) == 2
            assert res_dict["top"][0]["query"] == "python download"
            assert res_dict["top"][0]["value"] == 100.0
            assert len(res_dict["rising"]) == 2
            assert res_dict["rising"][0]["query"] == "python 3.12"
            assert res_dict["rising"][0]["value"] == 120.0


async def test_get_related_topics(mcp_server):
    mock_res = {
        "top": pd.DataFrame({"mid": ["/m/05z1_", "/m/020s1"], "title": ["Python", "Programming language"], "type": ["Language", "Field"], "value": [100, 80]}),
        "rising": pd.DataFrame({"mid": ["/g/11bc5zy143"], "title": ["FastAPI"], "type": ["Web framework"], "value": [50000]})
    }
    with patch('mcp_trendpulse.news.tr') as mock_tr:
        mock_tr.related_topics.return_value = mock_res
        async with Client(mcp_server) as client:
            params = {"keyword": "python"}
            result = await client.call_tool("get_related_topics", params)
            res_dict = result.structured_content
            assert res_dict is not None
            assert len(res_dict["top"]) == 2
            assert res_dict["top"][0]["title"] == "Python"
            assert res_dict["top"][0]["mid"] == "/m/05z1_"
            assert len(res_dict["rising"]) == 1
            assert res_dict["rising"][0]["title"] == "FastAPI"


async def test_get_suggestions(mcp_server):
    mock_df = pd.DataFrame({
        "mid": ["/m/05z1_"],
        "title": ["Python"],
        "type": ["Programming language"]
    })
    with patch('mcp_trendpulse.news.tr') as mock_tr:
        mock_tr.suggestions.return_value = mock_df
        async with Client(mcp_server) as client:
            params = {"keyword": "python"}
            result = await client.call_tool("get_suggestions", params)
            suggestions = _articles(result)
            assert isinstance(suggestions, list)
            assert len(suggestions) == 1
            assert suggestions[0]["mid"] == "/m/05z1_"
            assert suggestions[0]["title"] == "Python"


async def test_get_categories(mcp_server):
    mock_cats = [{"name": "All categories", "id": 0}, {"name": "Arts & Entertainment", "id": 3}]
    with patch('mcp_trendpulse.news.tr') as mock_tr:
        mock_tr.categories.return_value = mock_cats
        async with Client(mcp_server) as client:
            result = await client.call_tool("get_categories", {})
            cats = _articles(result)
            assert isinstance(cats, list)
            assert len(cats) == 2
            assert cats[0]["name"] == "All categories"
            assert cats[0]["id"] == 0


