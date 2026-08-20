import asyncio
from datetime import datetime

from newspaper import settings as newspaper_settings

from mcp_trendpulse import server


class OutputArticle:
    def __init__(self, url="https://example.com/article"):
        self.url = url
        self.original_url = url
        self.read_more_link = "https://example.com/read-more"
        self.language = "en"
        self.title = "Article title"
        self.meta_img = "https://example.com/meta.jpg"
        self.movies = ["https://example.com/movie"]
        self.meta_favicon = "https://example.com/favicon.ico"
        self.meta_site_name = "Example News"
        self.authors = ["Article author"]
        self.publish_date = datetime(2026, 8, 20, 12, 0, 0)
        self.top_image = "https://example.com/top.jpg"
        self.images = ["https://example.com/image.jpg"]
        self.text = "Article body"
        self.summary = "Article summary"
        self.keywords = ["article"]
        self.tags = {"beta", "alpha"}
        self.meta_keywords = ["meta"]
        self.meta_description = "Article description"
        self.canonical_link = "https://example.com/canonical"
        self.meta_data = {"og": {"tags": {"beta", "alpha"}}}
        self.meta_lang = "en"
        self.source_url = "https://example.com"

    def to_json(self, _as_string):
        return {
            field: getattr(self, field, None)
            for field in newspaper_settings.article_json_fields
        }


def test_article_to_output_keeps_compact_fields_compact():
    output = server.article_to_output(OutputArticle(), full_data=False).model_dump()

    assert output == {
        "url": "https://example.com/article",
        "title": "Article title",
        "publish_date": "2026-08-20T12:00:00",
        "summary": "Article summary",
    }


def test_article_to_output_includes_supported_full_fields():
    output = server.article_to_output(OutputArticle(), full_data=True).model_dump()

    assert set(output) == set(server.ArticleOut.model_fields)
    assert output["publish_date"] == "2026-08-20T12:00:00"
    assert output["tags"] == ["alpha", "beta"]
    assert output["meta_data"] == {"og": {"tags": ["alpha", "beta"]}}


async def test_overlapping_article_requests_keep_output_fields_request_local(monkeypatch):
    async def get_articles(**kwargs):
        await asyncio.sleep(0)
        return [OutputArticle(url=f"https://example.com/{kwargs['keyword']}")]

    sentinel_fields = ["title"]
    monkeypatch.setattr(newspaper_settings, "article_json_fields", sentinel_fields)
    monkeypatch.setattr(server.news, "get_news_by_keyword", get_articles)

    compact, full = await asyncio.gather(
        server.get_news_by_keyword(None, "compact", full_data=False, summarize=False),
        server.get_news_by_keyword(None, "full", full_data=True, summarize=False),
    )

    assert set(compact[0].model_dump()) == {"url", "title", "publish_date", "summary"}
    assert set(full[0].model_dump()) == set(server.ArticleOut.model_fields)
    assert newspaper_settings.article_json_fields == sentinel_fields
