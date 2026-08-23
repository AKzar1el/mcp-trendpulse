from unittest.mock import AsyncMock

import pytest

from mcp_trendpulse import news


class FakeGNews:
    instances: list["FakeGNews"] = []

    def __init__(self, *, language: str = "en"):
        self.language = language
        self.period = None
        self.max_results = None
        self.calls: list[tuple[str, str | None]] = []
        type(self).instances.append(self)

    def get_news(self, keyword: str):
        self.calls.append(("keyword", keyword))
        return [{"url": f"https://example.com/{keyword}"}]

    def get_top_news(self):
        self.calls.append(("top", None))
        return [{"url": "https://example.com/top"}]

    def get_news_by_location(self, location: str):
        self.calls.append(("location", location))
        return [{"url": f"https://example.com/{location}"}]

    def get_news_by_topic(self, topic: str):
        self.calls.append(("topic", topic))
        return [{"url": f"https://example.com/{topic}"}]

    def get_news_by_site(self, site: str):
        self.calls.append(("site", site))
        return [{"url": f"https://example.com/{site}"}]


@pytest.fixture(autouse=True)
def reset_instances():
    FakeGNews.instances = []


@pytest.mark.asyncio
async def test_news_queries_use_request_scoped_clients(monkeypatch):
    monkeypatch.setattr(news, "GNews", FakeGNews)
    process = AsyncMock(return_value=[])
    monkeypatch.setattr(news, "process_gnews_articles", process)

    await news.get_news_by_keyword("alpha", period=2, max_results=3, nlp=False)
    await news.get_top_news(period=4, max_results=5, nlp=False)
    await news.get_news_by_location("Ljubljana", period=6, max_results=7, nlp=False)
    await news.get_news_by_topic("TECHNOLOGY", period=8, max_results=9, nlp=False)
    await news.get_news_by_site("example.com", period=10, max_results=11, nlp=False)

    assert len(FakeGNews.instances) == 5
    assert [(client.period, client.max_results) for client in FakeGNews.instances] == [
        ("2d", 3),
        ("4d", 5),
        ("6d", 7),
        ("8d", 9),
        ("10d", 11),
    ]
    assert [client.calls for client in FakeGNews.instances] == [
        [("keyword", "alpha")],
        [("top", None)],
        [("location", "Ljubljana")],
        [("topic", "TECHNOLOGY")],
        [("site", "example.com")],
    ]
    assert process.await_count == 5


@pytest.mark.asyncio
async def test_empty_provider_result_skips_article_processing(monkeypatch):
    class EmptyGNews(FakeGNews):
        def get_news(self, keyword: str):
            self.calls.append(("keyword", keyword))
            return []

    monkeypatch.setattr(news, "GNews", EmptyGNews)
    process = AsyncMock(return_value=[])
    monkeypatch.setattr(news, "process_gnews_articles", process)

    result = await news.get_news_by_keyword("nothing", period=1, max_results=1)

    assert result == []
    process.assert_not_awaited()
