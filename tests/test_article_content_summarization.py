from unittest.mock import AsyncMock, patch

from mcp_trendpulse import news, server


class ArticleWithForbiddenNlp:
    def __init__(self):
        self.title = "Article title"
        self.original_url = "https://93.184.216.34/article"
        self.text = "Article body content."
        self.summary = ""
        self.authors = ["Article author"]
        self.parse_calls = 0
        self.nlp_calls = 0

    def parse(self):
        self.parse_calls += 1

    def nlp(self):
        self.nlp_calls += 1
        raise AssertionError("nlp() must not run")

    def to_json(self, _full_data):
        return {
            "title": self.title,
            "url": self.original_url,
            "text": self.text,
            "summary": self.summary,
            "authors": self.authors,
        }


async def test_get_article_content_skips_summarization_when_disabled():
    article = ArticleWithForbiddenNlp()
    with (
        patch("mcp_trendpulse.news.download_article", new=AsyncMock(return_value=article)),
        patch("mcp_trendpulse.server.summarize_articles", new_callable=AsyncMock) as summarize_articles,
        patch("nltk.download") as download_nltk_resource,
    ):
        result = await server.get_article_content(
            None,
            "https://93.184.216.34/article",
            full_data=True,
            summarize=False,
        )

    assert result is not None
    assert result.title == "Article title"
    assert result.url == article.original_url
    assert result.text == "Article body content."
    assert result.authors == ["Article author"]
    assert article.parse_calls == 0
    assert article.nlp_calls == 0
    summarize_articles.assert_not_awaited()
    download_nltk_resource.assert_not_called()


async def test_get_article_content_uses_summarization_when_enabled():
    article = ArticleWithForbiddenNlp()
    with (
        patch("mcp_trendpulse.news.download_article", new=AsyncMock(return_value=article)),
        patch("mcp_trendpulse.server.summarize_articles", new_callable=AsyncMock) as summarize_articles,
    ):
        result = await server.get_article_content(
            None,
            "https://93.184.216.34/article",
            summarize=True,
        )

    assert result is not None
    assert result.title == "Article title"
    assert result.url == article.original_url
    assert result.text == "Article body content."
    assert result.authors == ["Article author"]
    assert article.parse_calls == 0
    assert article.nlp_calls == 0
    summarize_articles.assert_awaited_once_with([article], None)


async def test_process_gnews_articles_does_not_reparse_downloaded_article():
    article = ArticleWithForbiddenNlp()
    with patch("mcp_trendpulse.news.download_article", new=AsyncMock(return_value=article)):
        articles = await news.process_gnews_articles(
            [{"url": "https://93.184.216.34/article"}],
            nlp=False,
        )

    assert articles == [article]
    assert article.title == "Article title"
    assert article.original_url == "https://93.184.216.34/article"
    assert article.text == "Article body content."
    assert article.authors == ["Article author"]
    assert article.parse_calls == 0
