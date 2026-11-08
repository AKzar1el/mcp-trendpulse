import gzip
import io
import socket
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from urllib3.response import HTTPResponse

from mcp_trendpulse import news
from mcp_trendpulse.server import get_article_content


def _address_info(*addresses):
    results = []
    for address in addresses:
        family = socket.AF_INET6 if ":" in address else socket.AF_INET
        sockaddr = (address, 443, 0, 0) if family == socket.AF_INET6 else (address, 443)
        results.append((family, socket.SOCK_STREAM, 6, "", sockaddr))
    return results


def _article_response(status_code=200, headers=None, chunks=()):
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {"Content-Type": "text/html"}
    response.encoding = "utf-8"
    response.iter_content.return_value = chunks
    return response


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
    response = SimpleNamespace(status_code=302, headers={"Location": "http://10.0.0.1/private"}, close=MagicMock())
    scraper = MagicMock()
    scraper.get.return_value = response

    with (
        patch("mcp_trendpulse.news.socket.getaddrinfo", return_value=_address_info("93.184.216.34")),
        patch("mcp_trendpulse.news.get_scraper", return_value=scraper),
    ):
        with pytest.raises(ValueError, match="globally routable"):
            news.download_article_with_scraper("https://example.com/article")

    scraper.get.assert_called_once_with(
        "https://example.com/article",
        timeout=news.ARTICLE_HTTP_TIMEOUT_SECONDS,
        allow_redirects=False,
        stream=True,
    )


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


async def test_playwright_route_guard_aborts_public_subrequests_without_egress_pin():
    route = SimpleNamespace(
        request=SimpleNamespace(url="https://93.184.216.34/article"),
        abort=AsyncMock(),
        continue_=AsyncMock(),
    )
    await news.guard_playwright_route(route, news.ArticleTargetValidator())
    route.abort.assert_awaited_once_with("blockedbyclient")
    route.continue_.assert_not_awaited()


def test_scraper_streams_articles_with_an_explicit_timeout():
    response = _article_response(chunks=[b"<html>article</html>"])
    scraper = MagicMock()
    scraper.get.return_value = response
    article = MagicMock()

    with (
        patch("mcp_trendpulse.news.get_scraper", return_value=scraper),
        patch("mcp_trendpulse.news.newspaper.article", return_value=article) as parse_article,
    ):
        assert news.download_article_with_scraper("https://93.184.216.34/article") is article

    scraper.get.assert_called_once_with(
        "https://93.184.216.34/article",
        timeout=news.ARTICLE_HTTP_TIMEOUT_SECONDS,
        allow_redirects=False,
        stream=True,
    )
    parse_article.assert_called_once_with("https://93.184.216.34/article", input_html="<html>article</html>")
    response.close.assert_called_once()


def test_scraper_rejects_declared_oversized_article_response():
    response = _article_response(headers={"Content-Type": "text/html", "Content-Length": str(news.ARTICLE_MAX_HTML_BYTES + 1)})
    scraper = MagicMock()
    scraper.get.return_value = response

    with (
        patch("mcp_trendpulse.news.get_scraper", return_value=scraper),
        patch("mcp_trendpulse.news.newspaper.article") as parse_article,
    ):
        assert news.download_article_with_scraper("https://93.184.216.34/article") is None

    response.iter_content.assert_not_called()
    parse_article.assert_not_called()
    response.close.assert_called_once()


def test_scraper_rejects_streamed_oversized_article_response():
    response = _article_response(chunks=[b"a" * news.ARTICLE_MAX_HTML_BYTES, b"a"])
    scraper = MagicMock()
    scraper.get.return_value = response

    with (
        patch("mcp_trendpulse.news.get_scraper", return_value=scraper),
        patch("mcp_trendpulse.news.newspaper.article") as parse_article,
    ):
        assert news.download_article_with_scraper("https://93.184.216.34/article") is None

    parse_article.assert_not_called()
    response.close.assert_called_once()


@pytest.mark.parametrize("content_type", ["application/pdf", "application/json"])
def test_scraper_rejects_non_html_article_response(content_type):
    response = _article_response(headers={"Content-Type": content_type})
    scraper = MagicMock()
    scraper.get.return_value = response

    with (
        patch("mcp_trendpulse.news.get_scraper", return_value=scraper),
        patch("mcp_trendpulse.news.newspaper.article") as parse_article,
    ):
        assert news.download_article_with_scraper("https://93.184.216.34/article") is None

    response.iter_content.assert_not_called()
    parse_article.assert_not_called()


def test_scraper_timeout_returns_article_download_failure():
    scraper = MagicMock()
    scraper.get.side_effect = TimeoutError("request timed out")

    with patch("mcp_trendpulse.news.get_scraper", return_value=scraper):
        assert news.download_article_with_scraper("https://93.184.216.34/article") is None


def test_scraper_stops_slow_drip_stream_before_parsing():
    clock = {"elapsed": 0, "chunks": 0}

    def slowly_arriving_chunks():
        for _ in range(100):
            clock["elapsed"] += 4
            clock["chunks"] += 1
            yield b"<p>article</p>"

    response = _article_response(chunks=slowly_arriving_chunks())
    scraper = MagicMock()
    scraper.get.return_value = response

    with (
        patch("mcp_trendpulse.news.perf_counter", side_effect=lambda: clock["elapsed"]),
        patch("mcp_trendpulse.news.get_scraper", return_value=scraper),
        patch("mcp_trendpulse.news.newspaper.article") as parse_article,
    ):
        assert news.download_article_with_scraper("https://93.184.216.34/article") is None

    assert clock["chunks"] < 100
    parse_article.assert_not_called()
    response.close.assert_called_once()


def test_article_response_checks_deadline_between_partial_transport_reads():
    clock = {"elapsed": 0, "reads": 0}
    response = _article_response()
    response.iter_content.side_effect = AssertionError("buffered 64KiB read must not be used")
    response.raw = HTTPResponse(body=io.BytesIO(b""), preload_content=False)

    def slowly_arriving_byte(*, amt, decode_content):
        assert amt == news._ARTICLE_RESPONSE_CHUNK_SIZE
        assert decode_content is True
        clock["elapsed"] += 4
        clock["reads"] += 1
        return b"x"

    response.raw.read1 = slowly_arriving_byte
    with patch("mcp_trendpulse.news.perf_counter", side_effect=lambda: clock["elapsed"]):
        assert news._read_article_response(response, "https://example.com/article", deadline=30) is None

    assert clock["reads"] == 8
    response.iter_content.assert_not_called()


def test_article_response_partial_reads_keep_gzip_decoding():
    html = "<html><body>Compressed article</body></html>"
    response = _article_response(headers={"Content-Type": "text/html", "Content-Encoding": "gzip"})
    response.iter_content.side_effect = AssertionError("buffered 64KiB read must not be used")
    response.raw = HTTPResponse(
        body=io.BytesIO(gzip.compress(html.encode("utf-8"))),
        headers={"Content-Encoding": "gzip"},
        preload_content=False,
    )

    assert news._read_article_response(response, "https://example.com/article", deadline=news.perf_counter() + 30) == html
    response.iter_content.assert_not_called()


def test_article_response_ignores_unsupported_declared_character_encoding():
    html = "<html><body>Publisher article</body></html>"
    response = _article_response(chunks=[html.encode("utf-8")])
    response.encoding = "publisher-invalid-charset"

    assert news._read_article_response(
        response, "https://example.com/article", deadline=news.perf_counter() + 30
    ) == html


def test_scraper_shares_download_deadline_across_redirects():
    clock = {"elapsed": 0}
    responses = []

    def slow_redirect(_url, **_kwargs):
        clock["elapsed"] += 11
        response = _article_response(status_code=302, headers={"Location": "/next"})
        responses.append(response)
        return response

    scraper = MagicMock()
    scraper.get.side_effect = slow_redirect

    with (
        patch("mcp_trendpulse.news.perf_counter", side_effect=lambda: clock["elapsed"]),
        patch("mcp_trendpulse.news.get_scraper", return_value=scraper),
    ):
        assert news.download_article_with_scraper("https://93.184.216.34/article") is None

    assert scraper.get.call_count <= 3
    assert scraper.get.call_args_list[-1].kwargs["timeout"] < news.ARTICLE_HTTP_TIMEOUT_SECONDS
    assert all(response.close.call_count == 1 for response in responses)


async def test_playwright_navigation_cannot_open_unpinned_socket():
    with patch("mcp_trendpulse.news.BrowserManager.browser_context") as browser:
        with pytest.raises(ValueError, match="browser transport is disabled"):
            await news.download_article_with_playwright("https://93.184.216.34/article")
    browser.assert_not_called()


async def test_playwright_does_not_parse_unverified_browser_html():
    with patch("mcp_trendpulse.news.newspaper.article") as parse_article:
        with pytest.raises(ValueError, match="browser transport is disabled"):
            await news.download_article_with_playwright("https://93.184.216.34/article")
    parse_article.assert_not_called()


async def test_playwright_rejects_external_article_even_when_public_literal():
    with patch("mcp_trendpulse.news.BrowserManager.browser_context") as browser:
        with pytest.raises(ValueError, match="browser transport is disabled"):
            await news.download_article_with_playwright("http://93.184.216.34/article")
    browser.assert_not_called()
