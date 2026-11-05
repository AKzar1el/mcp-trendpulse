"""Connection-time public-address pinning for untrusted article HTTP fetches.

The caller's ArticleTargetValidator is the authority for DNS/public IP checks.
urllib3 still sees the original hostname for HTTPS SNI and certificate validation.
An IP literal is used only for the TCP connect, never as the TLS hostname.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin

from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.exceptions import NewConnectionError


class PublicAddressPinnedAdapter(HTTPAdapter):
    """Keep URL hostname and TLS validation while connecting to vetted IPs."""

    def __init__(self, validator):
        self._validator = validator
        super().__init__()

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        validator = self._validator

        def pinned_socket(conn):
            hostname = validator._normalize_hostname(conn.host)
            # This check also rejects localhost, even on unexpected internal fetches.
            validator.validate_url("https://" + hostname + "/")
            try:
                candidate = ipaddress.ip_address(hostname)
            except ValueError:
                addresses = validator._resolve_hostname(hostname)
            else:
                validator._require_public_address(candidate)
                addresses = (candidate,)
            if not addresses:
                raise NewConnectionError(conn, "No safe address for article host")

            failure = None
            for address in addresses:
                validator._require_public_address(address)
                family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
                raw = socket.socket(family, socket.SOCK_STREAM)
                try:
                    for option in conn.socket_options or ():
                        raw.setsockopt(*option)
                    if conn.source_address:
                        raw.bind(conn.source_address)
                    raw.settimeout(conn.timeout)
                    raw.connect((str(address), conn.port))
                    return raw
                except OSError as exc:
                    failure = exc
                    raw.close()
            raise NewConnectionError(conn, "All verified public addresses failed") from failure

        class PinnedHTTPConnection(HTTPConnection):
            def _new_conn(self):
                return pinned_socket(self)

        class PinnedHTTPSConnection(HTTPSConnection):
            def _new_conn(self):
                return pinned_socket(self)

        class PinnedHTTPPool(HTTPConnectionPool):
            ConnectionCls = PinnedHTTPConnection

        class PinnedHTTPSPool(HTTPSConnectionPool):
            ConnectionCls = PinnedHTTPSConnection

        super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)
        # Per-adapter maps: never change urllib3's global pool classes.
        self.poolmanager.pool_classes_by_scheme = {
            **self.poolmanager.pool_classes_by_scheme,
            "http": PinnedHTTPPool,
            "https": PinnedHTTPSPool,
        }

    def proxy_manager_for(self, proxy, proxy_headers=None):
        # A remote proxy's eventual destination cannot be pinned by this adapter.
        raise ValueError("Proxy-backed article downloads require a separately enforced egress policy")


def secure_article_session(session, validator):
    """Mount only on actual Requests sessions (test doubles remain isolated)."""
    if not isinstance(session, Session):
        return session
    if session.proxies:
        raise ValueError("Explicit article proxies cannot guarantee vetted destination IPs")

    previous = {scheme: session.adapters.get(scheme) for scheme in ("https://", "http://")}
    adapter = PublicAddressPinnedAdapter(validator)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    # Preserve Requests environment-selected proxies and CA bundles.
    # The pinned adapter rejects proxy use instead of silently bypassing it.
    for old in set(previous.values()):
        if old is not None and old is not adapter:
            old.close()
    return session




@dataclass(frozen=True)
class SafeArticleResource:
    status: int
    headers: dict[str, str]
    body: bytes


def fetch_public_article_resource(
    session,
    validator,
    url: str,
    method: str,
    browser_headers: dict[str, str],
    *,
    max_bytes: int,
    timeout: float,
    max_redirects: int,
) -> SafeArticleResource:
    """Fetch a browser resource exclusively over the pinned Python HTTP transport.

    Redirects are handled here, not released to a browser's network stack.
    Unsafe browser-initiated POST/PUT/etc are intentionally rejected.
    """
    if method not in ("GET", "HEAD"):
        raise ValueError("Only safe article resource methods are supported")
    forwarding = {
        name: value
        for name, value in browser_headers.items()
        if name.lower() in {"accept", "accept-language", "user-agent", "referer", "range"}
    }
    current = url
    for _ in range(max_redirects + 1):
        current = validator.validate_url(current)
        with session.request(
            method,
            current,
            headers=forwarding,
            timeout=timeout,
            allow_redirects=False,
            stream=True,
            proxies={},
        ) as response:
            status = response.status_code
            if 300 <= status < 400:
                destination = response.headers.get("Location")
                if not destination:
                    raise ValueError("Article resource redirect omitted Location")
                current = validator.validate_url(urljoin(current, destination))
                continue
            declared = response.headers.get("Content-Length")
            if declared is not None:
                try:
                    if int(declared) > max_bytes:
                        raise ValueError("Article resource exceeds byte limit")
                except ValueError as exc:
                    if str(exc) == "Article resource exceeds byte limit":
                        raise
            chunks = bytearray()
            for chunk in response.iter_content(chunk_size=65536):
                chunks.extend(chunk)
                if len(chunks) > max_bytes:
                    raise ValueError("Article resource exceeds byte limit")
            # Requests has already decoded compressed/chunked content.
            hop_by_hop = {
                "content-encoding", "content-length", "transfer-encoding", "connection",
                "keep-alive", "proxy-authenticate", "proxy-authorization", "trailer",
                "upgrade",
            }
            outbound = {
                name: value for name, value in response.headers.items()
                if name.lower() not in hop_by_hop
            }
            return SafeArticleResource(status=status, headers=outbound, body=bytes(chunks))
    raise ValueError("Article resource exceeded redirect limit")
