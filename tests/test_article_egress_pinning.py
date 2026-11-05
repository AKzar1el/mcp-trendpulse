"""Offline transport-boundary tests for untrusted article downloads."""

import socket
import threading
from unittest.mock import MagicMock, patch

import pytest
from requests import Request, Session

from mcp_trendpulse import news


def _address_info(address: str):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]


def test_http_adapter_pins_the_verified_ip_not_the_original_dns_name():
    adapter = news.ArticlePinnedHTTPAdapter()
    request = Request("GET", "https://example.com/article").prepare()
    pool = MagicMock()
    adapter.poolmanager.connection_from_host = MagicMock(return_value=pool)
    with patch("mcp_trendpulse.news.socket.getaddrinfo", side_effect=[
        _address_info("93.184.216.34"),
        _address_info("127.0.0.1"),
    ]) as dns:
        assert adapter.get_connection_with_tls_context(request, True) is pool
    assert dns.call_count == 1
    args, kwargs = adapter.poolmanager.connection_from_host.call_args
    assert kwargs["host"] == "93.184.216.34"
    assert kwargs["scheme"] == "https"
    assert kwargs["pool_kwargs"]["server_hostname"] == "example.com"
    assert kwargs["pool_kwargs"]["assert_hostname"] == "example.com"
    assert request.headers["Host"] == "example.com"


def test_real_urllib3_pool_keeps_original_tls_sni_and_cert_requirement():
    adapter = news.ArticlePinnedHTTPAdapter()
    request = Request("GET", "https://example.com/article").prepare()
    with patch("mcp_trendpulse.news.socket.getaddrinfo", return_value=_address_info("93.184.216.34")):
        pool = adapter.get_connection_with_tls_context(request, True)
    adapter.cert_verify(pool, request.url, True, None)
    connection = pool._new_conn()  # Instantiates connection only; no socket is opened.
    assert pool.host == "93.184.216.34"
    assert connection.server_hostname == "example.com"
    assert connection.assert_hostname == "example.com"
    assert str(pool.cert_reqs).endswith("CERT_REQUIRED")


def test_http_adapter_pins_public_http_without_tls_settings():
    adapter = news.ArticlePinnedHTTPAdapter()
    request = Request("GET", "http://example.com/article").prepare()
    adapter.poolmanager.connection_from_host = MagicMock()
    with patch("mcp_trendpulse.news.socket.getaddrinfo", return_value=_address_info("93.184.216.34")):
        adapter.get_connection_with_tls_context(request, True)
    kwargs = adapter.poolmanager.connection_from_host.call_args.kwargs
    assert kwargs["host"] == "93.184.216.34"
    assert kwargs["scheme"] == "http"
    assert "server_hostname" not in kwargs["pool_kwargs"]
    assert request.headers["Host"] == "example.com"


def test_http_adapter_can_pin_public_ipv6_with_original_dns_identity():
    adapter = news.ArticlePinnedHTTPAdapter()
    request = Request("GET", "https://example.com/article").prepare()
    address_info = [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2606:4700:4700::1111", 443, 0, 0))]
    with patch("mcp_trendpulse.news.socket.getaddrinfo", return_value=address_info):
        pool = adapter.get_connection_with_tls_context(request, True)
    assert pool.host == "2606:4700:4700::1111"
    assert pool._new_conn().server_hostname == "example.com"


def test_cloudscraper_session_installs_pinned_adapter_for_both_schemes():
    session = Session()
    with (
        patch("mcp_trendpulse.news._scraper_local", threading.local()),
        patch("mcp_trendpulse.news.cloudscraper.create_scraper", return_value=session),
    ):
        assert news.get_scraper() is session
    assert isinstance(session.get_adapter("http://example.com"), news.ArticlePinnedHTTPAdapter)
    assert isinstance(session.get_adapter("https://example.com"), news.ArticlePinnedHTTPAdapter)
    assert session.trust_env is False
    assert session.proxies == {}


def test_http_adapter_rejects_private_ipv4_mapped_ipv6_literal():
    adapter = news.ArticlePinnedHTTPAdapter()
    request = Request("GET", "https://[::ffff:127.0.0.1]/article").prepare()
    adapter.poolmanager.connection_from_host = MagicMock()
    with pytest.raises(ValueError, match="globally routable"):
        adapter.get_connection_with_tls_context(request, True)
    adapter.poolmanager.connection_from_host.assert_not_called()


@pytest.mark.parametrize("unsafe", ["127.0.0.1", "10.1.2.3", "169.254.169.254"])
def test_http_adapter_never_creates_pool_for_rebound_private_destination(unsafe):
    adapter = news.ArticlePinnedHTTPAdapter()
    request = Request("GET", "https://example.com/article").prepare()
    adapter.poolmanager.connection_from_host = MagicMock()
    with patch("mcp_trendpulse.news.socket.getaddrinfo", return_value=_address_info(unsafe)):
        with pytest.raises(ValueError, match="globally routable"):
            adapter.get_connection_with_tls_context(request, True)
    adapter.poolmanager.connection_from_host.assert_not_called()


def test_http_adapter_rejects_proxy_and_disabled_tls_verification():
    adapter = news.ArticlePinnedHTTPAdapter()
    request = Request("GET", "https://example.com/article").prepare()
    adapter.poolmanager.connection_from_host = MagicMock()
    with pytest.raises(ValueError, match="proxy"):
        adapter.get_connection_with_tls_context(request, True, proxies={"https": "http://proxy.example:3128"})
    with pytest.raises(ValueError, match="TLS"):
        adapter.get_connection_with_tls_context(request, False)
    adapter.poolmanager.connection_from_host.assert_not_called()


@pytest.mark.asyncio
async def test_browser_article_transport_fails_closed_without_pinned_egress():
    with patch("mcp_trendpulse.news.BrowserManager.browser_context") as browser:
        with pytest.raises(ValueError, match="browser.*disabled|pinned.*browser"):
            await news.download_article_with_playwright("https://93.184.216.34/article")
    browser.assert_not_called()
