import socket
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_trendpulse import news
from mcp_trendpulse.server import get_article_content


def _address_info(*addresses):
    results = []
    for address in addresses:
        family = socket.AF_INET6 if ":" in address else socket.AF_INET
        sockaddr = (address, 443, 0, 0) if family == socket.AF_INET6 else (address, 443)
        results.append((family, socket.SOCK_STREAM, 6, "", sockaddr))
    return results


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


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/article",
        "http://127.0.0.1/article",
        "http://[::1]/article",
        "http://10.0.0.1/article",
        "http://172.16.0.1/article",
        "http://192.168.0.1/article",
        "http://169.254.169.254/latest/meta-data",
        "http://[fe80::1]/article",
        "http://224.0.0.1/article",
    ],
)
def test_article_target_validator_rejects_non_public_ip_literals(url):
    with pytest.raises(ValueError, match="globally routable|localhost"):
        news.ArticleTargetValidator().validate_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://93.184.216.34/article",
        "https://[2606:4700:4700::1111]/article",
    ],
)
def test_article_target_validator_accepts_public_ip_literals(url):
    assert news.ArticleTargetValidator().validate_url(url) == url


def test_article_target_validator_accepts_dns_name_with_public_ipv4_and_ipv6():
    with patch("mcp_trendpulse.news.socket.getaddrinfo", return_value=_address_info("93.184.216.34", "2606:4700:4700::1111")):
        validator = news.ArticleTargetValidator()
        url = "https://example.com/article"

        assert validator.validate_url(url) == url
        assert validator.validate_url(url) == url


def test_article_target_validator_rejects_dns_name_with_any_non_public_address():
    with patch("mcp_trendpulse.news.socket.getaddrinfo", return_value=_address_info("93.184.216.34", "10.0.0.1")):
        with pytest.raises(ValueError, match="globally routable"):
            news.ArticleTargetValidator().validate_url("https://example.com/article")


def test_article_target_validator_fails_closed_when_dns_resolution_fails():
    with patch("mcp_trendpulse.news.socket.getaddrinfo", side_effect=socket.gaierror):
        with pytest.raises(ValueError, match="could not be resolved safely"):
            news.ArticleTargetValidator().validate_url("https://example.com/article")


def test_scraper_rejects_private_redirect_before_requesting_it():
    response = SimpleNamespace(status_code=302, headers={"Location": "http://10.0.0.1/private"}, text="")
    scraper = MagicMock()
    scraper.get.return_value = response

    with (
        patch("mcp_trendpulse.news.socket.getaddrinfo", return_value=_address_info("93.184.216.34")),
        patch("mcp_trendpulse.news.get_scraper", return_value=scraper),
    ):
        with pytest.raises(ValueError, match="globally routable"):
            news.download_article_with_scraper("https://example.com/article")

    scraper.get.assert_called_once_with("https://example.com/article", timeout=10, allow_redirects=False)


async def test_download_article_rejects_private_google_news_destination():
    with (
        patch("mcp_trendpulse.news.socket.getaddrinfo", return_value=_address_info("142.250.191.14")),
        patch("mcp_trendpulse.news.decode_url", return_value="http://10.0.0.1/private"),
        patch("mcp_trendpulse.news.download_article_with_scraper") as scraper_download,
    ):
        with pytest.raises(ValueError, match="globally routable"):
            await news.download_article("https://news.google.com/rss/articles/CBMi")

    scraper_download.assert_not_called()


async def test_playwright_route_guard_aborts_private_subrequests():
    route = SimpleNamespace(
        request=SimpleNamespace(url="http://127.0.0.1/private"),
        abort=AsyncMock(),
        continue_=AsyncMock(),
    )

    await news.guard_playwright_route(route, news.ArticleTargetValidator())

    route.abort.assert_awaited_once_with("blockedbyclient")
    route.continue_.assert_not_awaited()
