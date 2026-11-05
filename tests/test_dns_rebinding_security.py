"""Network-blocked regression tests for DNS rebinding in article transports.

Every socket connect is intercepted before packets can leave the process.
The first DNS resolution is public; a subsequent independent transport
resolution would resolve the same name to loopback.
"""

import asyncio
import ipaddress
import socket
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from mcp_trendpulse import news


def _dns_result(ip, port):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port or 443))]


def _rebound_resolver():
    calls = []

    def resolve(host, port, *args, **kwargs):
        if host != "example.com":
            raise AssertionError(f"Unexpected DNS target: {host}")
        calls.append(host)
        address = "93.184.216.34" if len(calls) == 1 else "127.0.0.1"
        return _dns_result(address, port)

    return resolve, calls


def test_scraper_never_connects_to_private_ip_after_public_dns_preflight():
    resolver, dns_calls = _rebound_resolver()
    attempted_addresses = []

    def block_every_socket_connect(_sock, address):
        attempted_addresses.append(address[0])
        raise OSError("Network disabled by deterministic security test")

    scraper = news.get_scraper()
    scraper.trust_env = False  # Prevent ambient host proxy settings during this isolated test.

    with (
        patch("socket.getaddrinfo", side_effect=resolver),
        patch.object(socket.socket, "connect", block_every_socket_connect),
        patch("mcp_trendpulse.news.get_scraper", return_value=scraper),
    ):
        article = news.download_article_with_scraper("https://example.com/article")

    assert article is None
    assert dns_calls  # The validation really ran.
    assert not any(
        not ipaddress.ip_address(ip).is_global for ip in attempted_addresses
    ), f"Transport attempted untrusted destination: {attempted_addresses}"


def test_browser_route_never_releases_unpinned_rebound_hostname():
    asyncio.run(_exercise_browser_route())


async def _exercise_browser_route():
    resolver, dns_calls = _rebound_resolver()
    attempted_addresses = []

    async def simulate_unpinned_chromium_continue():
        # In the real browser, route.continue_ releases a separate hostname
        # connection; simulate its independent resolution without sending packets.
        result = resolver("example.com", 443)
        attempted_addresses.append(result[0][4][0])

    route = SimpleNamespace(
        request=SimpleNamespace(url="https://example.com/article"),
        continue_=AsyncMock(side_effect=simulate_unpinned_chromium_continue),
        abort=AsyncMock(),
        fulfill=AsyncMock(),
    )
    validator = news.ArticleTargetValidator()
    with patch("socket.getaddrinfo", side_effect=resolver):
        validator.validate_url(route.request.url)
        await news.guard_playwright_route(route, validator)

    assert dns_calls
    assert not any(
        not ipaddress.ip_address(ip).is_global for ip in attempted_addresses
    ), f"Browser route released unpinned destination: {attempted_addresses}"



def test_pinned_https_adapter_keeps_original_hostname_for_tls_identity():
    from unittest.mock import MagicMock
    from mcp_trendpulse.article_safe_transport import PublicAddressPinnedAdapter

    validator = news.ArticleTargetValidator()
    with (
        patch("socket.getaddrinfo", return_value=_dns_result("93.184.216.34", 443)),
        patch("mcp_trendpulse.article_safe_transport.socket.socket") as fake_socket,
    ):
        fake_socket.return_value = MagicMock()
        adapter = PublicAddressPinnedAdapter(validator)
        try:
            pool = adapter.poolmanager.connection_from_url("https://example.com/article")
            connection = pool._new_conn()
            connection._new_conn()
            fake_socket.return_value.connect.assert_called_once_with(("93.184.216.34", 443))
            assert connection.host == "example.com"
            assert connection.assert_hostname is not False
            assert connection.cert_reqs != "CERT_NONE"
        finally:
            adapter.close()


def test_browser_guard_fulfills_only_via_supplied_verified_resource_fetcher():
    from mcp_trendpulse.article_safe_transport import SafeArticleResource

    async def run_case():
        route = SimpleNamespace(
            request=SimpleNamespace(url="https://example.com/article", method="GET", headers={}),
            continue_=AsyncMock(),
            fulfill=AsyncMock(),
            abort=AsyncMock(),
        )
        called = []
        def fetcher(url, method, headers):
            called.append((url, method, headers))
            return SafeArticleResource(
                status=200, headers={"content-type": "text/html"}, body=b"<body>Safe</body>"
            )
        with patch("socket.getaddrinfo", return_value=_dns_result("93.184.216.34", 443)):
            result = await news.guard_playwright_route(route, news.ArticleTargetValidator(), fetcher)
        assert result is None
        assert called == [("https://example.com/article", "GET", {})]
        route.fulfill.assert_awaited_once_with(
            status=200,
            headers={"content-type": "text/html"},
            body=b"<body>Safe</body>",
        )
        route.continue_.assert_not_awaited()
        route.abort.assert_not_awaited()
    asyncio.run(run_case())


def test_resource_redirect_rejects_private_target_before_second_request():
    import pytest
    from unittest.mock import MagicMock
    from mcp_trendpulse.article_safe_transport import fetch_public_article_resource

    response = MagicMock()
    response.__enter__.return_value = response
    response.status_code = 302
    response.headers = {"Location": "http://127.0.0.1/private"}
    session = MagicMock()
    session.request.return_value = response
    with patch("socket.getaddrinfo", return_value=_dns_result("93.184.216.34", 443)):
        with pytest.raises(ValueError):
            fetch_public_article_resource(
                session,
                news.ArticleTargetValidator(),
                "https://example.com/article",
                "GET",
                {},
                max_bytes=1024,
                timeout=3,
                max_redirects=3,
            )
    session.request.assert_called_once()


def test_explicit_proxy_is_rejected_when_connected_ip_cannot_be_enforced():
    import pytest
    from requests import Session
    from mcp_trendpulse.article_safe_transport import secure_article_session

    with Session() as session:
        session.proxies["https"] = "http://proxy.example.invalid:3128"
        with pytest.raises(ValueError, match="proxies"):
            secure_article_session(session, news.ArticleTargetValidator())
