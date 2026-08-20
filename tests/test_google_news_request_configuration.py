import asyncio
from unittest.mock import AsyncMock

import pytest

from mcp_trendpulse import news


class FakeGNews:
    def __init__(self, **configuration):
        self.configuration = configuration
        self.calls = []

    def get_news(self, keyword):
        self.calls.append(("get_news", keyword))
        return [{"url": f"https://example.com/{keyword}"}]

    def get_top_news(self):
        self.calls.append(("get_top_news", None))
        return [{"url": "https://example.com/top"}]

    def get_news_by_location(self, location):
        self.calls.append(("get_news_by_location", location))
        return [{"url": f"https://example.com/{location}"}]

    def get_news_by_topic(self, topic):
        self.calls.append(("get_news_by_topic", topic))
        return [{"url": f"https://example.com/{topic}"}]

    def get_news_by_site(self, site):
        self.calls.append(("get_news_by_site", site))
        return [{"url": f"https://example.com/{site}"}]


def test_create_google_news_client_uses_requested_configuration(monkeypatch):
    created_clients = []

    def create_fake_client(**configuration):
        client = FakeGNews(**configuration)
        created_clients.append(client)
        return client

    monkeypatch.setattr(news, "GNews", create_fake_client)

    client = news.create_google_news_client(period=14, max_results=25)

    assert client is created_clients[0]
    assert client.configuration == {
        "language": "en",
        "period": "14d",
        "max_results": 25,
    }


@pytest.mark.parametrize(
    ("operation", "value", "method_name"),
    [
        ("keyword", "climate", "get_news"),
        ("location", "Ljubljana", "get_news_by_location"),
        ("topic", "TECHNOLOGY", "get_news_by_topic"),
        ("top", None, "get_top_news"),
        ("site", "example.com", "get_news_by_site"),
    ],
)
async def test_news_operations_use_a_client_with_their_requested_settings(
    monkeypatch, operation, value, method_name
):
    created_clients = []

    def create_fake_client(period, max_results):
        client = FakeGNews(language="en", period=f"{period}d", max_results=max_results)
        created_clients.append(client)
        return client

    monkeypatch.setattr(news, "create_google_news_client", create_fake_client)
    monkeypatch.setattr(news, "process_gnews_articles", AsyncMock(return_value=[]))

    if operation == "keyword":
        await news.get_news_by_keyword(value, period=5, max_results=12, nlp=False)
    elif operation == "location":
        await news.get_news_by_location(value, period=5, max_results=12, nlp=False)
    elif operation == "topic":
        await news.get_news_by_topic(value, period=5, max_results=12, nlp=False)
    elif operation == "top":
        await news.get_top_news(period=5, max_results=12, nlp=False)
    else:
        await news.get_news_by_site(value, period=5, max_results=12, nlp=False)

    assert len(created_clients) == 1
    assert created_clients[0].configuration == {
        "language": "en",
        "period": "5d",
        "max_results": 12,
    }
    assert created_clients[0].calls == [(method_name, value)]


async def test_concurrent_news_requests_do_not_share_configuration(monkeypatch):
    created_clients = []

    def create_fake_client(period, max_results):
        client = FakeGNews(language="en", period=f"{period}d", max_results=max_results)
        created_clients.append(client)
        return client

    async def process_articles(*args, **kwargs):
        await asyncio.sleep(0)
        return []

    monkeypatch.setattr(news, "create_google_news_client", create_fake_client)
    monkeypatch.setattr(news, "process_gnews_articles", process_articles)

    await asyncio.gather(
        news.get_news_by_keyword("first", period=1, max_results=2, nlp=False),
        news.get_news_by_keyword("second", period=30, max_results=40, nlp=False),
    )

    assert len(created_clients) == 2
    assert created_clients[0] is not created_clients[1]
    assert {
        (client.configuration["period"], client.configuration["max_results"], client.calls[0])
        for client in created_clients
    } == {
        ("1d", 2, ("get_news", "first")),
        ("30d", 40, ("get_news", "second")),
    }
