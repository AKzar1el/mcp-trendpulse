from unittest.mock import AsyncMock, patch

import pytest

from mcp_trendpulse import news
from mcp_trendpulse.server import get_article_content


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/article",
        "http://example.com/article",
        "https://localhost/article",
    ],
)
def test_validate_article_url_accepts_http_and_https(url):
    assert news.validate_article_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/foo",
        "data:text/plain,article",
        "javascript:alert(1)",
        "gopher://example.com",
        "dict://example.com",
        "smb://example.com/share",
        "example.com/article",
        "https:///article",
        "https://user:password@example.com/article",
        "https://[example.com",
    ],
)
def test_validate_article_url_rejects_invalid_urls(url):
    with pytest.raises(ValueError, match="valid HTTP\\(S\\) URL"):
        news.validate_article_url(url)


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.com/foo"])
async def test_download_article_does_not_download_rejected_urls(url):
    with (
        patch("mcp_trendpulse.news.download_article_with_scraper") as scraper_download,
        patch("mcp_trendpulse.news.download_article_with_playwright", new_callable=AsyncMock) as playwright_download,
    ):
        with pytest.raises(ValueError, match="valid HTTP\\(S\\) URL"):
            await news.download_article(url)

    scraper_download.assert_not_called()
    playwright_download.assert_not_called()


async def test_get_article_content_rejects_invalid_url_before_downloading():
    with patch("mcp_trendpulse.news.download_article", new_callable=AsyncMock) as download:
        with pytest.raises(ValueError, match="valid HTTP\\(S\\) URL"):
            await get_article_content(None, "file:///etc/passwd")

    download.assert_not_called()


async def test_download_article_revalidates_decoded_google_news_url():
    google_news_url = "https://news.google.com/rss/articles/CBMi"
    with (
        patch("mcp_trendpulse.news.decode_url", return_value="file:///etc/passwd") as decode,
        patch("mcp_trendpulse.news.download_article_with_scraper") as scraper_download,
        patch("mcp_trendpulse.news.download_article_with_playwright", new_callable=AsyncMock) as playwright_download,
    ):
        with pytest.raises(ValueError, match="valid HTTP\\(S\\) URL"):
            await news.download_article(google_news_url)

    decode.assert_called_once_with(google_news_url)
    scraper_download.assert_not_called()
    playwright_download.assert_not_called()
