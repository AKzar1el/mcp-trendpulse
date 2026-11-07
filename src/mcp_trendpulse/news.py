"""
# news.py
This module provides functions to find and download news articles using Google News.
It allows searching for articles by keyword, location, or topic, and can also retrieve google trending terms.
It uses the `gnews` library to search for news articles and trendspy to get Google Trends data.
Untrusted article requests use a public-IP-pinned HTTP transport. The browser
fallback is disabled until it can enforce the same network boundary.
"""

import copy
import re
import json
import asyncio
import ipaddress
import socket
import threading
from math import isfinite
from time import perf_counter
from html import unescape
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
import pandas
from gnews import GNews
from gnews.gnews import SECTIONS as GNEWS_SECTIONS, TOPICS as GNEWS_TOPICS
import newspaper  # newspaper4k
from googlenewsdecoder import gnewsdecoder
import cloudscraper
from requests.adapters import HTTPAdapter
from urllib3.response import HTTPResponse
from playwright.async_api import async_playwright, Browser, Playwright
from trendspy import Trends, TrendKeywordLite
from typing import Any, Optional, cast, overload, Literal, Awaitable
from contextlib import asynccontextmanager, AsyncContextDecorator
import logging
from collections.abc import Callable
from urllib.parse import quote, urljoin, urlsplit

from mcp_trendpulse.config import (
    GOOGLE_NEWS_MAX_RESULTS,
    GOOGLE_TRENDS_MAX_RESULTS,
    get_browser_sandbox_enabled,
    get_google_news_country,
    get_google_news_language,
    get_google_trends_delay,
)
from mcp_trendpulse.errors import (
    ProviderError,
    ProviderRateLimitError,
    ProviderUnavailableError,
    classify_provider_exception,
)
from mcp_trendpulse.provider_metrics import provider_metrics
from mcp_trendpulse.trends_rate_control import (
    install_trends_session_pacing,
    trends_interest_cache,
    trends_request_pacer,
)

logger = logging.getLogger(__name__)

for logname in logging.root.manager.loggerDict:
    if logname.startswith("newspaper"):
        logging.getLogger(logname).setLevel(logging.ERROR)

_scraper_local = threading.local()
_trends_local = threading.local()

_INVALID_TREND_VOLUME = -1
_TREND_VOLUME_PATTERN = re.compile(
    r"^(?P<number>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)(?P<suffix>[KMB])?\+?$",
    re.IGNORECASE,
)
_SEARCH_SOURCE_MAP = {
    "google search": "",
    "youtube search": "youtube",
    "news search": "news",
    "image search": "images",
    "google shopping": "froogle",
}
_ALLOWED_DATA_MODES = frozenset({"weekly", "daily", "monthly"})
_ALLOWED_RANK_SORTS = frozenset({"recent_growth_pct", "wow_pct_change", "volume"})
_ALLOWED_TOP_TREND_TYPES = frozenset({"google trends", "daily trends", "daily"})
_ALLOWED_GOOGLE_PROPERTIES = frozenset(_SEARCH_SOURCE_MAP.values())
_ALLOWED_REGION_RESOLUTIONS = frozenset({"COUNTRY", "REGION", "CITY", "DMA"})


def _validated_trend_result_limit(limit: int) -> int:
    if not 1 <= limit <= GOOGLE_TRENDS_MAX_RESULTS:
        raise ValueError(f"Trend result limit must be between 1 and {GOOGLE_TRENDS_MAX_RESULTS}.")
    return limit


_ARTICLE_TITLE_PLACEHOLDERS = frozenset(
    {
        "access denied",
        "are you a robot?",
        "attention required",
        "attention required!",
        "checking your browser...",
        "just a moment...",
    }
)
_ARTICLE_CHALLENGE_BODY_MARKERS = (
    "why have i been blocked?",
    "why did this happen?",
    "verification successful",
    "this website is using a security service to protect itself from online attacks",
    "cloudflare ray id",
    "make sure your browser supports javascript and cookies",
    "block reference id:",
)
_ARTICLE_STRONG_CHALLENGE_BODY_MARKERS = (
    "performing security verification",
    "this website uses a security service to protect against malicious bots",
    "this page is displayed while the website verifies you are not a bot",
)
_ARTICLE_SHELL_TEXT_PLACEHOLDERS = frozenset(
    {
        "there are no new alerts at this time",
    }
)
_SUPPORTED_NEWS_TOPICS = frozenset(
    topic.upper() for topic in (*GNEWS_TOPICS, *GNEWS_SECTIONS.keys())
)


def _decode_provider_text(value):
    """Decode HTML entities in provider-owned display text while preserving non-strings."""
    return unescape(value) if isinstance(value, str) else value


def _google_property(source: str) -> str:
    normalized = source.strip().lower()
    try:
        return _SEARCH_SOURCE_MAP[normalized]
    except KeyError as exc:
        allowed = ", ".join(sorted(_SEARCH_SOURCE_MAP))
        raise ValueError(f"Unsupported search source {source!r}; expected one of: {allowed}.") from exc


def _validated_google_property(gprop: str) -> str:
    normalized = gprop.strip().lower()
    if normalized not in _ALLOWED_GOOGLE_PROPERTIES:
        allowed = ", ".join(repr(value) for value in sorted(_ALLOWED_GOOGLE_PROPERTIES))
        raise ValueError(f"Unsupported Google property {gprop!r}; expected one of: {allowed}.")
    return normalized


def _validated_region_resolution(resolution: str) -> str:
    normalized = resolution.strip().upper()
    if normalized not in _ALLOWED_REGION_RESOLUTIONS:
        allowed = ", ".join(sorted(_ALLOWED_REGION_RESOLUTIONS))
        raise ValueError(f"Unsupported region resolution {resolution!r}; expected one of: {allowed}.")
    return normalized


def _restore_feed_title_if_placeholder(article: newspaper.Article, gnews_article: dict) -> None:
    """Prefer Google News' title when extraction returns a generic challenge-page title."""
    feed_title = str(gnews_article.get("title") or "").strip()
    article_title = str(getattr(article, "title", "") or "").strip()
    if feed_title and (not article_title or article_title.casefold() in _ARTICLE_TITLE_PLACEHOLDERS):
        article.title = feed_title


def _restore_feed_publisher_if_missing(article: newspaper.Article, gnews_article: dict) -> None:
    """Retain feed publisher attribution only when extraction provided no site name."""
    if str(getattr(article, "meta_site_name", "") or "").strip():
        return
    publisher = gnews_article.get("publisher")
    name = publisher.get("title") if isinstance(publisher, dict) else None
    if isinstance(name, str):
        normalized = _decode_provider_text(name).strip()
        if normalized and len(normalized) <= 200:
            article.meta_site_name = normalized


def _is_challenge_page(article: newspaper.Article) -> bool:
    """Reject known anti-bot pages instead of returning their challenge copy as news."""
    title = str(getattr(article, "title", "") or "").strip().casefold()
    text = str(getattr(article, "text", "") or "").casefold()
    strong_marker_count = sum(marker in text for marker in _ARTICLE_STRONG_CHALLENGE_BODY_MARKERS)
    return strong_marker_count >= 2 or (
        title in _ARTICLE_TITLE_PLACEHOLDERS
        and any(marker in text for marker in _ARTICLE_CHALLENGE_BODY_MARKERS)
    )


def _is_unusable_article_page(article: newspaper.Article) -> bool:
    """Reject challenge pages and known publisher UI shells with no article content."""
    if _is_challenge_page(article):
        return True
    text = " ".join(str(getattr(article, "text", "") or "").casefold().split())
    return text in _ARTICLE_SHELL_TEXT_PLACEHOLDERS



def _strip_known_article_shell_prefix(article: newspaper.Article | None) -> None:
    """Remove a standalone known publisher shell prefix from substantive article text."""
    if article is None:
        return
    text = str(getattr(article, "text", "") or "").lstrip()
    folded = text.casefold()
    for placeholder in _ARTICLE_SHELL_TEXT_PLACEHOLDERS:
        if not folded.startswith(placeholder):
            continue
        boundary = len(placeholder)
        if boundary < len(text) and text[boundary].isspace():
            remainder = text[boundary:].lstrip()
            if remainder:
                article.text = remainder
        return

def _get_trends_client() -> Trends:
    """Return one lazily-created TrendSpy client per worker thread."""
    client = getattr(_trends_local, "instance", None)
    if client is None:
        client = Trends(request_delay=get_google_trends_delay())
        install_trends_session_pacing(client, trends_request_pacer)
        _trends_local.instance = client
    return client


class _ThreadLocalTrendsProxy:
    """Resolve TrendSpy attributes and normalize provider failures per worker thread."""

    def __getattr__(self, name: str):
        client = _get_trends_client()
        attribute = getattr(client, name)
        if not callable(attribute):
            return attribute
        coordinated = bool(getattr(getattr(client, "session", None), "_trendpulse_paced", False))

        def provider_call(*args, **kwargs):
            def invoke():
                if coordinated:
                    trends_request_pacer.ensure_available(name)
                try:
                    result = attribute(*args, **kwargs)
                    if coordinated:
                        trends_request_pacer.note_success()
                    return result
                except ProviderError as exc:
                    if coordinated and isinstance(exc, ProviderRateLimitError):
                        trends_request_pacer.note_rate_limit(exc)
                    raise
                except (ValueError, TypeError):
                    raise
                except Exception as exc:
                    classified = classify_provider_exception(
                        exc,
                        provider="google_trends",
                        operation=name,
                    )
                    if coordinated and isinstance(classified, ProviderRateLimitError):
                        trends_request_pacer.note_rate_limit(exc)
                    raise classified from exc

            if coordinated:
                return trends_interest_cache.get_or_load(name, args, kwargs, invoke)
            return invoke()

        return provider_call


tr = _ThreadLocalTrendsProxy()

TRENDS_OPERATION_TIMEOUT_SECONDS = 30
TRENDS_MAX_ACTIVE_WORKERS = 4
_TRENDS_WORKER_SLOTS = threading.BoundedSemaphore(TRENDS_MAX_ACTIVE_WORKERS)
_trends_worker_tasks: set[asyncio.Task] = set()


def _run_trends_with_slot(slot: threading.BoundedSemaphore, invoke: Callable[[], Any]):
    try:
        return invoke()
    finally:
        # Caller cancellation cannot interrupt a synchronous TrendSpy request.
        slot.release()


def _finish_trends_worker(task: asyncio.Task) -> None:
    _trends_worker_tasks.discard(task)
    if not task.cancelled():
        task.exception()


async def _call_trends_async(operation: str, invoke: Callable[[], Any]):
    """Limit actual blocking TrendSpy workers, not merely waiting async callers."""
    slot = _TRENDS_WORKER_SLOTS
    if not slot.acquire(blocking=False):
        provider_metrics.count("trends_worker_saturation")
        raise ProviderUnavailableError("google_trends", operation)
    try:
        worker = asyncio.create_task(asyncio.to_thread(_run_trends_with_slot, slot, invoke))
    except BaseException:
        slot.release()
        raise
    _trends_worker_tasks.add(worker)
    worker.add_done_callback(_finish_trends_worker)
    try:
        return await asyncio.wait_for(asyncio.shield(worker), timeout=TRENDS_OPERATION_TIMEOUT_SECONDS)
    except TimeoutError as exc:
        provider_metrics.count("trends_worker_timeout")
        raise classify_provider_exception(
            exc, provider="google_trends", operation=operation
        ) from exc


def _call_related_queries_with_unavailable_retry(**kwargs):
    """Retry one transient related-query failure with a fresh TrendSpy client."""
    try:
        return tr.related_queries(**kwargs)
    except ProviderUnavailableError:
        if hasattr(_trends_local, "instance"):
            delattr(_trends_local, "instance")
        return tr.related_queries(**kwargs)


def parse_trending_volume(volume: object) -> int:
    """Convert an abbreviated Google Trends volume to an integer sort key."""
    if volume is None:
        return _INVALID_TREND_VOLUME

    volume_match = _TREND_VOLUME_PATTERN.fullmatch(str(volume).strip())
    if not volume_match:
        return _INVALID_TREND_VOLUME

    try:
        numeric_value = Decimal(volume_match.group("number").replace(",", ""))
    except InvalidOperation:
        return _INVALID_TREND_VOLUME

    multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(
        (volume_match.group("suffix") or "").upper(), 1
    )
    normalized_value = numeric_value * multiplier
    if not normalized_value.is_finite() or normalized_value != normalized_value.to_integral_value():
        return _INVALID_TREND_VOLUME
    return int(normalized_value)


def get_scraper():
    scraper_instance = getattr(_scraper_local, "instance", None)
    if scraper_instance is None:
        try:
            scraper_instance = cloudscraper.create_scraper(
                interpreter="js2py",
                delay=5,
                browser="chrome",
                debug=False,
            )
            # All requests, including challenge retries, must use a dial-pinned
            # transport. Environment proxies must not change the egress route.
            scraper_instance.trust_env = False
            scraper_instance.proxies = {}
            scraper_instance.mount("http://", ArticlePinnedHTTPAdapter())
            scraper_instance.mount("https://", ArticlePinnedHTTPAdapter())
        except Exception as e:
            logger.error(f"Failed to initialize cloudscraper: {e}")
            return None
        _scraper_local.instance = scraper_instance
    return scraper_instance


class _DeferredUrlGNews(GNews):
    """Leave Google News RSS links unresolved for TrendPulse's article pipeline."""

    def _process(self, item):
        feed_source = item.get("source")
        source_url = feed_source.get("href") if isinstance(feed_source, dict) else None
        if not isinstance(source_url, str):
            if self._exclude_websites:
                return None
            source_url = ""
        excluded_patterns = [
            rf"^https?://(?:www\.)?{re.escape(website.lower())}(?::\d+)?(?=[/?#]|$)"
            for website in self._exclude_websites
        ]
        if any(re.match(pattern, source_url, re.IGNORECASE) for pattern in excluded_patterns):
            return None

        url = item.get("link")
        if not url:
            return None
        return {
            "title": item.get("title", ""),
            "description": self._clean(item.get("description", "")),
            "published date": item.get("published", ""),
            "url": url,
            "publisher": item.get("source", " "),
        }

def _new_google_news(period: int, max_results: int) -> GNews:
    """Create an isolated Google News client for one request."""
    # GNews drops its configured date window when paginating over 100 items.
    if not 1 <= max_results <= GOOGLE_NEWS_MAX_RESULTS:
        raise ValueError(f"Google News max_results must be between 1 and {GOOGLE_NEWS_MAX_RESULTS}.")
    client = _DeferredUrlGNews(
        language=get_google_news_language(),
        country=get_google_news_country(),
    )
    client.period = f"{period}d"
    client.max_results = max_results
    return client


ProgressCallback = Callable[[float, Optional[float]], Awaitable[None]]
GOOGLE_NEWS_OPERATION_TIMEOUT_SECONDS = 30
GOOGLE_NEWS_MAX_INFLIGHT_OPERATIONS = 4
_GOOGLE_NEWS_WORKER_SLOTS = threading.BoundedSemaphore(GOOGLE_NEWS_MAX_INFLIGHT_OPERATIONS)
_google_news_worker_tasks: set[asyncio.Task] = set()

def _call_google_news(client: GNews, operation: str, *args, **kwargs):
    """Run one GNews operation and normalize upstream failures."""
    started = perf_counter()
    provider_metrics.count("news_feed_request")
    try:
        return getattr(client, operation)(*args, **kwargs)
    except (ProviderError, ValueError, TypeError) as exc:
        provider_metrics.count("news_feed_error")
        if isinstance(exc, ProviderRateLimitError):
            provider_metrics.count("news_feed_429")
        raise
    except Exception as exc:
        classified = classify_provider_exception(
            exc,
            provider="google_news",
            operation=operation,
        )
        provider_metrics.count("news_feed_error")
        if isinstance(classified, ProviderRateLimitError):
            provider_metrics.count("news_feed_429")
        raise classified from exc
    finally:
        provider_metrics.observe_ms("news_feed", max(0.0, (perf_counter() - started) * 1000))


def _call_google_news_with_worker_slot(slot: threading.BoundedSemaphore, client: GNews, operation: str, *args, **kwargs):
    try:
        return _call_google_news(client, operation, *args, **kwargs)
    finally:
        # A timed-out async caller cannot stop the already-running sync provider.
        slot.release()


def _finish_google_news_worker(task: asyncio.Task) -> None:
    _google_news_worker_tasks.discard(task)
    if not task.cancelled():
        # Consume failures from a worker that outlived its timed-out caller.
        task.exception()


async def _call_google_news_async(client: GNews, operation: str, *args, **kwargs):
    """Bound both caller wait and still-running synchronous GNews operations."""
    slot = _GOOGLE_NEWS_WORKER_SLOTS
    if not slot.acquire(blocking=False):
        provider_metrics.count("news_feed_saturation")
        raise ProviderUnavailableError("google_news", operation)

    try:
        worker = asyncio.create_task(
            asyncio.to_thread(_call_google_news_with_worker_slot, slot, client, operation, *args, **kwargs)
        )
    except BaseException:
        slot.release()
        raise
    # Shield the worker from caller cancellation so its slot is not reused
    # until the blocking operation actually finishes.
    _google_news_worker_tasks.add(worker)
    worker.add_done_callback(_finish_google_news_worker)
    try:
        return await asyncio.wait_for(
            asyncio.shield(worker),
            timeout=GOOGLE_NEWS_OPERATION_TIMEOUT_SECONDS,
        )
    except (TimeoutError, asyncio.TimeoutError) as exc:
        provider_metrics.count("news_feed_timeout")
        raise classify_provider_exception(
            exc,
            provider="google_news",
            operation=operation,
        ) from exc


_ALLOWED_ARTICLE_URL_SCHEMES = {"http", "https"}
_MAX_ARTICLE_REDIRECTS = 10
ARTICLE_HTTP_TIMEOUT_SECONDS = 12
ARTICLE_HTTP_DOWNLOAD_DEADLINE_SECONDS = 30
ARTICLE_BROWSER_NAVIGATION_TIMEOUT_MS = 15_000
ARTICLE_MAX_HTML_BYTES = 5 * 1024 * 1024
ARTICLE_PROCESS_CONCURRENCY = 4
ARTICLE_PROGRESS_CALLBACK_TIMEOUT_SECONDS = 5
ARTICLE_PROGRESS_MAX_ACTIVE_TASKS = 4
_article_progress_tasks: set[asyncio.Task] = set()
ARTICLE_PREFLIGHT_TIMEOUT_SECONDS = 10
ARTICLE_PREFLIGHT_MAX_ACTIVE_WORKERS = 4
_ARTICLE_PREFLIGHT_WORKER_SLOTS = threading.BoundedSemaphore(ARTICLE_PREFLIGHT_MAX_ACTIVE_WORKERS)
_article_preflight_worker_tasks: set[asyncio.Task] = set()
ARTICLE_NLP_TIMEOUT_SECONDS = 8
ARTICLE_NLP_MAX_ACTIVE_WORKERS = 4
_ARTICLE_NLP_WORKER_SLOTS = threading.BoundedSemaphore(ARTICLE_NLP_MAX_ACTIVE_WORKERS)
_article_nlp_worker_tasks: set[asyncio.Task] = set()
ARTICLE_SCRAPER_TIMEOUT_SECONDS = 35
ARTICLE_SCRAPER_MAX_ACTIVE_WORKERS = 4
_ARTICLE_SCRAPER_WORKER_SLOTS = threading.BoundedSemaphore(ARTICLE_SCRAPER_MAX_ACTIVE_WORKERS)
_article_scraper_worker_tasks: set[asyncio.Task] = set()
_ARTICLE_RESPONSE_CHUNK_SIZE = 64 * 1024
_UNSUPPORTED_ARTICLE_CONTENT_TYPES = {
    "application/gzip",
    "application/json",
    "application/octet-stream",
    "application/pdf",
    "application/x-gzip",
    "application/zip",
}
_UNSUPPORTED_ARTICLE_CONTENT_TYPE_PREFIXES = ("audio/", "image/", "video/")


def validate_article_url(url: str) -> str:
    """Return a syntactically valid HTTP(S) article URL without accessing the network."""
    if not isinstance(url, str) or any(char.isspace() or ord(char) < 32 for char in url):
        raise ValueError("Article URL must be a valid HTTP(S) URL.")

    try:
        parsed_url = urlsplit(url)
        hostname = parsed_url.hostname
        parsed_url.port
    except ValueError as exc:
        raise ValueError("Article URL must be a valid HTTP(S) URL.") from exc

    if (
        parsed_url.scheme not in _ALLOWED_ARTICLE_URL_SCHEMES
        or not hostname
        or parsed_url.username is not None
        or parsed_url.password is not None
    ):
        raise ValueError("Article URL must be a valid HTTP(S) URL.")

    return url


class ArticleTargetValidator:
    """Validate article hosts resolve exclusively to globally routable addresses."""

    def __init__(self):
        self._resolved_hosts: dict[str, tuple[ipaddress.IPv4Address | ipaddress.IPv6Address, ...]] = {}

    @staticmethod
    def _normalize_hostname(hostname: str) -> str:
        normalized = hostname.rstrip(".").lower()
        if not normalized:
            raise ValueError("Article URL must include a hostname.")
        try:
            return normalized.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise ValueError("Article URL hostname is invalid.") from exc

    @staticmethod
    def _require_public_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
        if (
            not address.is_global
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_unspecified
            or address.is_reserved
            or getattr(address, "is_site_local", False)
        ):
            raise ValueError("Article URL target must resolve to globally routable IP addresses.")

    def _resolve_hostname(self, hostname: str) -> tuple[ipaddress.IPv4Address | ipaddress.IPv6Address, ...]:
        if hostname in self._resolved_hosts:
            return self._resolved_hosts[hostname]

        try:
            address_info = socket.getaddrinfo(
                hostname,
                None,
                family=socket.AF_UNSPEC,
                type=socket.SOCK_STREAM,
            )
            addresses = tuple({ipaddress.ip_address(info[4][0]) for info in address_info})
        except (OSError, ValueError) as exc:
            raise ValueError("Article URL hostname could not be resolved safely.") from exc

        if not addresses:
            raise ValueError("Article URL hostname could not be resolved safely.")

        for address in addresses:
            self._require_public_address(address)

        self._resolved_hosts[hostname] = addresses
        return addresses

    def validate_url(self, url: str) -> str:
        """Validate a syntactically valid article URL and its outbound network target."""
        url = validate_article_url(url)
        hostname = self._normalize_hostname(urlsplit(url).hostname or "")
        if hostname == "localhost" or hostname.endswith(".localhost"):
            raise ValueError("Article URL must not target localhost.")

        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            self._resolve_hostname(hostname)
        else:
            self._require_public_address(address)

        return url


class ArticlePinnedHTTPAdapter(HTTPAdapter):
    """Connect only to a vetted public IP, retaining URL-host TLS verification."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._target_validator = ArticleTargetValidator()

    def get_connection_with_tls_context(self, request, verify, proxies=None, cert=None):
        if proxies:
            raise ValueError("Article transport cannot use a proxy.")
        if verify is False:
            raise ValueError("Article transport requires TLS certificate verification.")

        url = self._target_validator.validate_url(request.url)
        parsed = urlsplit(url)
        hostname = self._target_validator._normalize_hostname(parsed.hostname or "")
        try:
            literal = ipaddress.ip_address(hostname)
        except ValueError:
            addresses = self._target_validator._resolve_hostname(hostname)
        else:
            self._target_validator._require_public_address(literal)
            addresses = (literal,)

        # urllib3 resolves the pool host, which is an IP literal, not the DNS
        # name that might have changed after the validator's DNS lookup.
        address = sorted(addresses, key=lambda ip: (ip.version, int(ip)))[0]
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        host_header = f"[{hostname}]" if ":" in hostname else hostname
        if port != (443 if parsed.scheme == "https" else 80):
            host_header += f":{port}"
        request.headers["Host"] = host_header

        _, pool_kwargs = self.build_connection_pool_key_attributes(request, verify, cert)
        pool_kwargs = dict(pool_kwargs)
        if parsed.scheme == "https":
            # SNI and certificate hostname validation stay on the original
            # requested host, even though TCP connects to a vetted IP.
            pool_kwargs.update(server_hostname=hostname, assert_hostname=hostname)
        return self.poolmanager.connection_from_host(
            host=str(address), port=port, scheme=parsed.scheme, pool_kwargs=pool_kwargs
        )


class BrowserManager(AsyncContextDecorator):
    _playwright: Optional[Playwright] = None
    _browser: Optional[Browser] = None
    _lock = asyncio.Lock()
    _class_contexts: int = 0

    @classmethod
    async def _get_browser(cls) -> Browser:
        if cls._browser is None:
            async with cls._lock:
                if cls._browser is None:
                    logger.info("Starting browser...")
                    try:
                        cls._playwright = await async_playwright().start()
                        cls._browser = await cls._playwright.chromium.launch(
                            headless=True,
                            chromium_sandbox=get_browser_sandbox_enabled(),
                        )
                    except Exception as exc:
                        logger.critical("Browser startup failed", exc_info=exc)
                        await cls._shutdown()
                        raise RuntimeError(
                            "Unable to start Playwright Chromium. Ensure Playwright browser binaries are installed "
                            "(run 'playwright install chromium')."
                        ) from exc
        return cast(Browser, cls._browser)

    @classmethod
    async def _shutdown(cls):
        logger.info("Shutting down browser...")
        if cls._browser:
            try:
                await cls._browser.close()
            except Exception:
                pass
            cls._browser = None
        if cls._playwright:
            try:
                await cls._playwright.stop()
            except Exception:
                pass
            cls._playwright = None

    @classmethod
    def browser_context(cls):
        @asynccontextmanager
        async def _browser_context_cm():
            if cls._class_contexts == 0:
                raise RuntimeError("BrowserManager used without context. Wrap in 'async with BrowserManager()'.")
            browser_inst = await cls._get_browser()
            context = await browser_inst.new_context(service_workers="block")
            logger.debug("Created browser context...")
            try:
                yield context
            finally:
                logger.debug("Closing browser context...")
                await context.close()

        return _browser_context_cm()

    async def __aenter__(self):
        type(self)._class_contexts += 1
        return self

    async def __aexit__(self, *exc):
        type(self)._class_contexts -= 1
        if type(self)._class_contexts == 0:
            await self._shutdown()
        return False


async def guard_playwright_route(route, target_validator: ArticleTargetValidator) -> Optional[ValueError]:
    """Never let the unsupported browser route open an unpinned socket."""
    await route.abort("blockedbyclient")
    return ValueError("Article browser transport is disabled until pinned browser egress is available.")


async def download_article_with_playwright(
    url: str,
    target_validator: Optional[ArticleTargetValidator] = None,
) -> newspaper.Article | None:
    """
    Fail closed until Chromium requests have connection-level egress pinning.
    """
    raise ValueError("Article browser transport is disabled until pinned browser egress is available.")


def _is_unsupported_article_response(response) -> bool:
    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
    return content_type in _UNSUPPORTED_ARTICLE_CONTENT_TYPES or content_type.startswith(
        _UNSUPPORTED_ARTICLE_CONTENT_TYPE_PREFIXES
    )


def _read_article_response(response, url: str, *, deadline: float) -> Optional[str]:
    content_length = response.headers.get("Content-Length")
    try:
        if content_length is not None and int(content_length) > ARTICLE_MAX_HTML_BYTES:
            logger.warning("Rejected article response from %s because its declared size exceeds the HTML size limit", url)
            return None
    except ValueError:
        pass

    if _is_unsupported_article_response(response):
        logger.warning("Rejected non-HTML article response from %s", url)
        return None

    body = bytearray()
    raw_response = getattr(response, "raw", None)
    if isinstance(raw_response, HTTPResponse):
        # read1 may return partial bytes; iter_content's read(64 KiB) can
        # block indefinitely while a peer trickles bytes below that size.
        def partial_chunks():
            while True:
                chunk = raw_response.read1(amt=_ARTICLE_RESPONSE_CHUNK_SIZE, decode_content=True)
                if not chunk:
                    break
                yield chunk

        chunks = partial_chunks()
    else:
        chunks = response.iter_content(chunk_size=_ARTICLE_RESPONSE_CHUNK_SIZE)

    for chunk in chunks:
        # A per-socket read timeout alone cannot stop a steady slow-drip stream.
        if perf_counter() >= deadline:
            logger.warning("Aborted article response after the total HTTP download deadline")
            return None
        if not chunk:
            continue
        body.extend(chunk)
        if len(body) > ARTICLE_MAX_HTML_BYTES:
            logger.warning("Rejected article response from %s because it exceeds the HTML size limit", url)
            return None

    if perf_counter() >= deadline:
        logger.warning("Aborted article response after the total HTTP download deadline")
        return None
    return body.decode(response.encoding or "utf-8", errors="replace")


def download_article_with_scraper(
    url: str,
    target_validator: Optional[ArticleTargetValidator] = None,
) -> newspaper.Article | None:
    """Download an article while validating every redirect target before requesting it."""
    target_validator = target_validator or ArticleTargetValidator()
    url = target_validator.validate_url(url)

    try:
        scraper_inst = get_scraper()
        if scraper_inst is None:
            return None

        deadline = perf_counter() + ARTICLE_HTTP_DOWNLOAD_DEADLINE_SECONDS
        for _ in range(_MAX_ARTICLE_REDIRECTS):
            remaining = deadline - perf_counter()
            if remaining <= 0:
                logger.warning("Aborted article download after the total HTTP deadline")
                return None
            response = scraper_inst.get(
                url,
                timeout=min(ARTICLE_HTTP_TIMEOUT_SECONDS, remaining),
                allow_redirects=False,
                stream=True,
            )
            try:
                if perf_counter() >= deadline:
                    logger.warning("Aborted article download after the total HTTP deadline")
                    return None
                if 300 <= response.status_code < 400:
                    location = response.headers.get("Location")
                    if not location:
                        return None
                    url = target_validator.validate_url(urljoin(url, location))
                    continue

                if response.status_code < 400:
                    html = _read_article_response(response, url, deadline=deadline)
                    if html is None:
                        return None
                    return newspaper.article(url, input_html=html)

                logger.debug(f"Failed to download article with cloudscraper from {url}, status code: {response.status_code}")
                return None
            finally:
                response.close()
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        logger.debug(f"Error downloading article with cloudscraper from {url}\n {e.args}")
        return None


def decode_url(url: str) -> Optional[str]:
    if url.startswith("https://news.google.com/rss/"):
        try:
            decoded_url = gnewsdecoder(url)
            if decoded_url.get("status") or decoded_url.get("success") is True:
                return decoded_url["decoded_url"]
            else:
                logger.debug("Failed to decode Google News RSS link:")
        except Exception as err:
            logger.warning(f"Error while decoding url {url}\n {err.args}")
    return None


def _run_article_preflight_with_slot(
    slot: threading.BoundedSemaphore, operation: Callable, *args
):
    try:
        return operation(*args)
    finally:
        # Cancelled callers do not stop DNS resolution or RSS decoding threads.
        slot.release()


def _finish_article_preflight_worker(task: asyncio.Task) -> None:
    _article_preflight_worker_tasks.discard(task)
    if not task.cancelled():
        task.exception()


async def _call_article_preflight(operation: Callable, *args):
    """Bound physical DNS/RSS workers, not merely time spent awaiting them."""
    slot = _ARTICLE_PREFLIGHT_WORKER_SLOTS
    if not slot.acquire(blocking=False):
        provider_metrics.count("article_preflight_saturation")
        raise ValueError("Article preflight capacity exhausted.")
    try:
        worker = asyncio.create_task(
            asyncio.to_thread(_run_article_preflight_with_slot, slot, operation, *args)
        )
    except BaseException:
        slot.release()
        raise
    _article_preflight_worker_tasks.add(worker)
    worker.add_done_callback(_finish_article_preflight_worker)
    try:
        return await asyncio.wait_for(
            asyncio.shield(worker), timeout=ARTICLE_PREFLIGHT_TIMEOUT_SECONDS
        )
    except (TimeoutError, asyncio.TimeoutError) as exc:
        provider_metrics.count("article_preflight_timeout")
        raise ValueError("Article preflight exceeded its deadline.") from exc


def _run_article_scraper_with_slot(
    slot: threading.BoundedSemaphore, url: str, target_validator: ArticleTargetValidator
) -> newspaper.Article | None:
    try:
        return download_article_with_scraper(url, target_validator)
    finally:
        # Async cancellation cannot interrupt an already-running HTTP scraper.
        slot.release()


def _finish_article_scraper_worker(task: asyncio.Task) -> None:
    _article_scraper_worker_tasks.discard(task)
    if not task.cancelled():
        task.exception()


async def _download_article_with_worker_slot(
    url: str, target_validator: ArticleTargetValidator
) -> newspaper.Article | None:
    slot = _ARTICLE_SCRAPER_WORKER_SLOTS
    if not slot.acquire(blocking=False):
        provider_metrics.count("article_scraper_saturation")
        logger.warning("Article scraper capacity exhausted; preserving worker limit")
        return None
    try:
        worker = asyncio.create_task(
            asyncio.to_thread(_run_article_scraper_with_slot, slot, url, target_validator)
        )
    except BaseException:
        slot.release()
        raise
    _article_scraper_worker_tasks.add(worker)
    worker.add_done_callback(_finish_article_scraper_worker)
    try:
        return await asyncio.wait_for(asyncio.shield(worker), timeout=ARTICLE_SCRAPER_TIMEOUT_SECONDS)
    except (TimeoutError, asyncio.TimeoutError):
        provider_metrics.count("article_scraper_timeout")
        logger.warning("Article scraper exceeded caller deadline; still-running worker remains counted")
        return None


async def download_article(url: str) -> newspaper.Article | None:
    """
    Download an article from a given URL using newspaper4k and cloudscraper (async).
    """
    target_validator = ArticleTargetValidator()
    url = await _call_article_preflight(target_validator.validate_url, url)
    if url.startswith("https://news.google.com/rss/"):
        try:
            decoded = await _call_article_preflight(decode_url, url)
        except ValueError:
            # A timed-out or saturated decoder must not trigger an unsafe fetch.
            return None
        if decoded is None:
            return None
        url = await _call_article_preflight(target_validator.validate_url, decoded)
    article = await _download_article_with_worker_slot(url, target_validator)
    _strip_known_article_shell_prefix(article)
    if article is None or not article.text or _is_unusable_article_page(article):
        logger.debug("Article HTTP transport did not return usable text; unsafe browser fallback is disabled")
        return None
    if article is not None and _is_unusable_article_page(article):
        logger.debug(f"Rejected unusable article page from {url}")
        return None
    return article


def _run_article_nlp_with_slot(
    slot: threading.BoundedSemaphore,
    article: newspaper.Article,
    nlp_runner: Callable[[newspaper.Article], None] | None = None,
):
    try:
        if nlp_runner is None:
            article.nlp()
        else:
            nlp_runner(article)
        return getattr(article, "summary", ""), getattr(article, "keywords", [])
    finally:
        slot.release()


def _finish_article_nlp_worker(task: asyncio.Task) -> None:
    _article_nlp_worker_tasks.discard(task)
    if not task.cancelled():
        task.exception()


async def _enrich_article_nlp(
    article: newspaper.Article,
    idx: int,
    *,
    nlp_runner: Callable[[newspaper.Article], None] | None = None,
) -> None:
    """Bound physical NLP work; only copy completed enrichment onto the returned article."""
    slot = _ARTICLE_NLP_WORKER_SLOTS
    if not slot.acquire(blocking=False):
        provider_metrics.count("article_nlp_saturation")
        return

    try:
        # newspaper.nlp mutates its Article; an abandoned thread must never
        # mutate the article already returned to an MCP caller.
        detached = copy.copy(article)
        # A shallow clone still shares the mutable keywords list.
        detached.keywords = list(getattr(article, "keywords", []) or [])
        worker = asyncio.create_task(
            asyncio.to_thread(_run_article_nlp_with_slot, slot, detached, nlp_runner)
        )
    except BaseException:
        slot.release()
        raise

    _article_nlp_worker_tasks.add(worker)
    worker.add_done_callback(_finish_article_nlp_worker)
    try:
        summary, keywords = await asyncio.wait_for(
            asyncio.shield(worker), timeout=ARTICLE_NLP_TIMEOUT_SECONDS
        )
    except (TimeoutError, asyncio.TimeoutError):
        provider_metrics.count("article_nlp_timeout")
        logger.warning("NLP enrichment timed out for article %d; preserving extracted text", idx)
    except Exception as exc:
        article.summary = ""
        article.keywords = []
        logger.warning(
            "NLP enrichment failed for article %d (%s); preserving extracted text without enrichment",
            idx,
            type(exc).__name__,
        )
    else:
        article.summary = summary
        article.keywords = keywords


def _finish_article_progress_task(task: asyncio.Task) -> None:
    _article_progress_tasks.discard(task)
    if not task.cancelled():
        task.exception()  # Consume late failures from a client that ignores cancellation.


async def _report_article_progress_with_deadline(
    callback: ProgressCallback, completed: int, total: int
) -> None:
    if len(_article_progress_tasks) >= ARTICLE_PROGRESS_MAX_ACTIVE_TASKS:
        raise TimeoutError("Article progress callback capacity exhausted")
    task = asyncio.create_task(callback(completed, total))
    _article_progress_tasks.add(task)
    task.add_done_callback(_finish_article_progress_task)
    try:
        done, _ = await asyncio.wait((task,), timeout=ARTICLE_PROGRESS_CALLBACK_TIMEOUT_SECONDS)
        if not done:
            raise TimeoutError("Article progress callback exceeded its deadline")
        task.result()
    finally:
        if not task.done():
            task.cancel()


async def process_gnews_articles(
    gnews_articles: list[dict],
    nlp: bool = True,
    report_progress: Optional[ProgressCallback] = None,
    max_concurrency: int = ARTICLE_PROCESS_CONCURRENCY,
    period: Optional[int] = None,
    now: Optional[datetime] = None,
) -> list[newspaper.Article]:
    """
    Process Google News articles with bounded concurrency while preserving input order.
    Optionally report progress via report_progress callback.
    """
    total = len(gnews_articles)
    if total == 0:
        return []

    reference_now = _parse_news_publish_date(now) if now is not None else datetime.now(timezone.utc)
    cutoff = reference_now - timedelta(days=period) if period is not None else None
    semaphore = asyncio.Semaphore(max(1, max_concurrency))
    progress_lock = asyncio.Lock()
    completed_count = 0
    progress_enabled = True

    async def process_one(idx: int, gnews_article: dict) -> tuple[int, newspaper.Article | None]:
        nonlocal completed_count, progress_enabled
        try:
            async with semaphore:
                raw_url = gnews_article.get("url")
                if not isinstance(raw_url, str) or not raw_url.strip():
                    logger.debug("Skipping Google News provider item %d with missing or invalid URL", idx)
                    return idx, None
                url = raw_url.strip()
                feed_publish_date = _parse_news_publish_date(gnews_article.get("published date"))
                if cutoff is not None and feed_publish_date is not None and (
                    feed_publish_date < cutoff or feed_publish_date > reference_now
                ):
                    return idx, None

                try:
                    article = await download_article(url)
                except ValueError as exc:
                    logger.debug(
                        "Skipping unusable Google News provider item %s: %s",
                        url,
                        exc,
                    )
                    return idx, None
                except Exception as exc:
                    # One publisher transport failure must not discard other articles.
                    logger.warning(
                        "Skipping Google News item %d after article download error (%s)",
                        idx,
                        type(exc).__name__,
                    )
                    return idx, None
                if article is None or not article.text:
                    logger.debug(f"Failed to download article from {url}:\n{article}")
                    return idx, None
                if _is_unusable_article_page(article):
                    logger.debug(f"Rejected unusable article page from {url}")
                    return idx, None

                article_publish_date = _parse_news_publish_date(getattr(article, "publish_date", None))
                effective_publish_date = article_publish_date or feed_publish_date
                if cutoff is not None and (
                    effective_publish_date is None
                    or effective_publish_date < cutoff
                    or effective_publish_date > reference_now
                ):
                    return idx, None
                if article_publish_date is None and feed_publish_date is not None:
                    article.publish_date = feed_publish_date

                _restore_feed_title_if_placeholder(article, gnews_article)
                _restore_feed_publisher_if_missing(article, gnews_article)

                if nlp:
                    await _enrich_article_nlp(article, idx)
                return idx, article
        finally:
            if report_progress:
                # Count completed input items, including rejected articles, in finish order.
                async with progress_lock:
                    completed_count += 1
                    if progress_enabled:
                        try:
                            # Progress is advisory; a stalled client must not block articles.
                            await _report_article_progress_with_deadline(
                                report_progress, completed_count, total
                            )
                        except Exception as exc:
                            # Optional client progress must not erase downloaded articles.
                            progress_enabled = False
                            logger.warning(
                                "Disabling unavailable Google News progress reporter (%s)",
                                type(exc).__name__,
                            )

    processed = await asyncio.gather(
        *(process_one(idx, gnews_article) for idx, gnews_article in enumerate(gnews_articles))
    )

    articles = []
    for idx, article in processed:
        if article is None:
            continue
        articles.append(article)
    return articles


async def _rss_headlines_from_feed(
    method: str,
    query: str | None,
    period: int,
    max_results: int,
    now: Optional[datetime] = None,
) -> list[dict[str, object]]:
    """Convert a Google News RSS feed to dated, explicitly limited metadata."""
    client = _new_google_news(period, max_results)
    items = await _call_google_news_async(client, method, *((query,) if query is not None else ()))
    reference_now = _parse_news_publish_date(now) if now is not None else datetime.now(timezone.utc)
    cutoff = reference_now - timedelta(days=period)
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in items or []:
        if not isinstance(item, dict):
            continue
        title = _decode_provider_text(item.get("title"))
        link = item.get("url")
        if not isinstance(title, str) or not title.strip() or not isinstance(link, str):
            continue
        try:
            parsed = urlsplit(link)
            hostname = parsed.hostname
        except ValueError:
            # One malformed upstream link must not discard the other headlines.
            continue
        if (
            parsed.scheme != "https"
            or hostname != "news.google.com"
            or parsed.username is not None
            or parsed.password is not None
            or not parsed.path.startswith("/rss/articles/")
            or link in seen
        ):
            continue
        published = _parse_news_publish_date(item.get("published date"))
        if published is None or not cutoff <= published <= reference_now:
            continue
        publisher = item.get("publisher")
        publisher_name = publisher.get("title") if isinstance(publisher, dict) else None
        result.append({
            "title": title.strip(),
            "url": link,
            "publish_date": published.isoformat(),
            "meta_site_name": _decode_provider_text(publisher_name) if isinstance(publisher_name, str) else None,
            "meta_data": {
                "content_level": "rss_headline_only",
                "source": "google_news_rss",
            },
        })
        seen.add(link)
        if len(result) >= max_results:
            break
    return result


async def get_rss_headlines_by_keyword(
    keyword: str,
    period: int = 7,
    max_results: int = 10,
    now: Optional[datetime] = None,
) -> list[dict[str, object]]:
    """Return dated keyword RSS metadata without article extraction."""
    keyword = _required_news_lookup(keyword, "keyword")
    return await _rss_headlines_from_feed("get_news", keyword, period, max_results, now)


async def get_rss_headlines_by_location(
    location: str,
    period: int = 7,
    max_results: int = 10,
    now: Optional[datetime] = None,
) -> list[dict[str, object]]:
    """Return dated location RSS metadata without article extraction."""
    location = _required_news_lookup(location, "location")
    return await _rss_headlines_from_feed(
        "get_news_by_location", quote(location, safe=""), period, max_results, now
    )


async def get_rss_headlines_by_site(
    site: str,
    period: int = 7,
    max_results: int = 10,
    now: Optional[datetime] = None,
) -> list[dict[str, object]]:
    """Return dated publisher-site RSS metadata without article extraction."""
    site = _required_news_lookup(site, "site")
    return await _rss_headlines_from_feed("get_news_by_site", site, period, max_results, now)


async def get_rss_headlines_by_topic(
    topic: str,
    period: int = 7,
    max_results: int = 10,
    now: Optional[datetime] = None,
) -> list[dict[str, object]]:
    """Return dated topic RSS metadata without article extraction."""
    topic = _required_news_lookup(topic, "topic").upper()
    if topic not in _SUPPORTED_NEWS_TOPICS:
        raise ValueError(f"Unsupported news topic: {topic!r}.")
    return await _rss_headlines_from_feed("get_news_by_topic", topic, period, max_results, now)


async def get_rss_headlines_for_top_news(
    period: int = 3,
    max_results: int = 10,
    now: Optional[datetime] = None,
) -> list[dict[str, object]]:
    """Return dated top-news RSS metadata without publisher article extraction."""
    return await _rss_headlines_from_feed("get_top_news", None, period, max_results, now)


async def get_news_by_keyword(
    keyword: str,
    period=7,
    max_results: int = 10,
    nlp: bool = True,
    report_progress: Optional[ProgressCallback] = None,
) -> list[newspaper.Article]:
    """
    Find articles by keyword using Google News.
    """
    keyword = _required_news_lookup(keyword, "keyword")
    google_news = _new_google_news(period, max_results)
    gnews_articles = await _call_google_news_async(google_news, "get_news", keyword)
    if not gnews_articles:
        logger.debug(f"No articles found for keyword '{keyword}' in the last {period} days.")
        return []
    return await process_gnews_articles(
        gnews_articles,
        nlp=nlp,
        report_progress=report_progress,
        period=period,
    )


async def get_top_news(
    period: int = 3,
    max_results: int = 10,
    nlp: bool = True,
    report_progress: Optional[ProgressCallback] = None,
) -> list[newspaper.Article]:
    """
    Get top news stories from Google News.
    """
    google_news = _new_google_news(period, max_results)
    gnews_articles = await _call_google_news_async(google_news, "get_top_news")
    if not gnews_articles:
        logger.debug("No top news articles found.")
        return []
    return await process_gnews_articles(
        gnews_articles,
        nlp=nlp,
        report_progress=report_progress,
        period=period,
    )


async def get_news_by_location(
    location: str,
    period=7,
    max_results: int = 10,
    nlp: bool = True,
    report_progress: Optional[ProgressCallback] = None,
) -> list[newspaper.Article]:
    """Find articles by location using Google News."""
    location = _required_news_lookup(location, "location")
    google_news = _new_google_news(period, max_results)
    encoded_location = quote(location, safe="")
    gnews_articles = await _call_google_news_async(
        google_news,
        "get_news_by_location",
        encoded_location,
    )
    if not gnews_articles:
        gnews_articles = await _call_google_news_async(google_news, "get_news", location)
    if not gnews_articles:
        logger.debug(f"No articles found for location '{location}' in the last {period} days.")
        return []
    return await process_gnews_articles(
        gnews_articles,
        nlp=nlp,
        report_progress=report_progress,
        period=period,
    )


async def get_news_by_topic(
    topic: str,
    period=7,
    max_results: int = 10,
    nlp: bool = True,
    report_progress: Optional[ProgressCallback] = None,
) -> list[newspaper.Article]:
    """Find articles by topic using Google News.
    topic is one of
    WORLD, NATION, BUSINESS, TECHNOLOGY, ENTERTAINMENT, SPORTS, SCIENCE, HEALTH,
    POLITICS, CELEBRITIES, TV, MUSIC, MOVIES, THEATER, SOCCER, CYCLING, MOTOR SPORTS,
    TENNIS, COMBAT SPORTS, BASKETBALL, BASEBALL, FOOTBALL, SPORTS BETTING, WATER SPORTS,
    HOCKEY, GOLF, CRICKET, RUGBY, ECONOMY, PERSONAL FINANCE, FINANCE, DIGITAL CURRENCIES,
    MOBILE, ENERGY, GAMING, INTERNET SECURITY, GADGETS, VIRTUAL REALITY, ROBOTICS, NUTRITION,
    PUBLIC HEALTH, MENTAL HEALTH, MEDICINE, SPACE, WILDLIFE, ENVIRONMENT, NEUROSCIENCE, PHYSICS,
    GEOLOGY, PALEONTOLOGY, SOCIAL SCIENCES, EDUCATION, JOBS, ONLINE EDUCATION, HIGHER EDUCATION,
    VEHICLES, ARTS-DESIGN, BEAUTY, FOOD, TRAVEL, SHOPPING, HOME, OUTDOORS, FASHION.
    """
    topic = _required_news_lookup(topic, "topic").upper()
    if topic not in _SUPPORTED_NEWS_TOPICS:
        raise ValueError(f"Unsupported news topic: {topic!r}.")
    google_news = _new_google_news(period, max_results)
    gnews_articles = await _call_google_news_async(google_news, "get_news_by_topic", topic)
    if not gnews_articles:
        logger.debug(f"No articles found for topic '{topic}' in the last {period} days.")
        return []
    return await process_gnews_articles(
        gnews_articles,
        nlp=nlp,
        report_progress=report_progress,
        period=period,
    )


@overload
async def get_trending_terms(geo: str = "US", full_data: Literal[False] = False) -> list[dict[str, str]]: ...


@overload
async def get_trending_terms(geo: str = "US", full_data: Literal[True] = True) -> list[TrendKeywordLite]: ...


async def get_trending_terms(geo: str = "US", full_data: bool = False) -> list[dict[str, str]] | list[TrendKeywordLite]:
    """
    Returns google trends for a specific geo location.
    """
    trends = cast(
        list[TrendKeywordLite],
        await _call_trends_async("trending_now_by_rss", lambda: tr.trending_now_by_rss(geo=geo)),
    )
    for trend in trends:
        trend.keyword = _decode_provider_text(trend.keyword)
        if hasattr(trend, "picture_source"):
            trend.picture_source = _decode_provider_text(trend.picture_source)
        for article in getattr(trend, "news", None) or []:
            article.title = _decode_provider_text(article.title)
            article.source = _decode_provider_text(article.source)
            article.snippet = _decode_provider_text(article.snippet)
    trends = sorted(trends, key=lambda trend: parse_trending_volume(trend.volume), reverse=True)
    if not full_data:
        return [{"keyword": trend.keyword, "volume": trend.volume} for trend in trends]
    return trends


def save_article_to_json(
    article: newspaper.Article,
    filename: Optional[str] = None,
    *,
    fail_if_exists: bool = False,
    raise_on_error: bool = False,
) -> None:
    """Save an article to JSON, optionally refusing to replace an existing file."""
    def sanitize_filename(title: str) -> str:
        """Generate safe filename from article title (max 50 chars, no special chars)."""
        sanitized_title = re.sub(r'[\\/*?:"<>|\s]', "_", title)[:50]
        return sanitized_title + ".json"

    def normalize_collections(value):
        if isinstance(value, (set, frozenset)):
            try:
                value = sorted(value)
            except TypeError:
                value = list(value)
            return [normalize_collections(item) for item in value]
        if isinstance(value, list):
            return [normalize_collections(item) for item in value]
        if isinstance(value, tuple):
            return tuple(normalize_collections(item) for item in value)
        if isinstance(value, dict):
            return {key: normalize_collections(item) for key, item in value.items()}
        return value

    if not filename:
        if not article.title:
            logger.warning("Cannot save article: no title or filename provided")
            return
        filename = sanitize_filename(article.title)

    article_data = {
        "title": article.title,
        "authors": article.authors,
        "publish_date": str(article.publish_date) if article.publish_date else None,
        "top_image": article.top_image,
        "images": article.images,
        "text": article.text,
        "url": article.original_url,
        "summary": article.summary,
        "keywords": article.keywords,
        "keyword_scores": article.keyword_scores,
        "tags": article.tags,
        "meta_keywords": article.meta_keywords,
        "meta_description": article.meta_description,
        "canonical_link": article.canonical_link,
        "meta_data": article.meta_data,
        "meta_lang": article.meta_lang,
        "source_url": article.source_url,
    }

    payload = json.dumps(normalize_collections(article_data), indent=4)
    try:
        with open(filename, "x" if fail_if_exists else "w", encoding="utf-8") as f:
            f.write(payload)
        logger.debug(f"Article saved to {filename}")
    except OSError as e:
        logger.error(f"Failed to save article to {filename}: {e}")
        if raise_on_error:
            raise


def _completed_trends_frame(df: pandas.DataFrame) -> pandas.DataFrame:
    """Exclude provider rows explicitly marked partial from decision metrics."""
    if "isPartial" not in df.columns:
        return df
    completed = df.loc[~df["isPartial"].fillna(False).astype(bool)]
    return completed


def _finite_trend_number(value: object) -> float | None:
    """Exclude missing, unparseable, and nonfinite provider measurements."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) else None


def _related_trend_value(value: object) -> tuple[float | None, bool]:
    """Keep Google's Breakout label without pretending it is a measured percentage."""
    if isinstance(value, str) and value.strip().casefold() == "breakout":
        return None, True
    return _finite_trend_number(value), False


def _trends_frame_to_points(df: pandas.DataFrame, keywords: list[str]) -> list[dict]:
    """Flatten one completed Trends frame into the package's stable point shape."""
    results: list[dict] = []
    intraday = False
    if isinstance(df.index, pandas.DatetimeIndex):
        days = df.index.normalize()
        intraday = not df.index.equals(days) or days.has_duplicates
    for dt, row in df.iterrows():
        if intraday:
            date_str = dt.isoformat()
        else:
            date_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]
        for keyword in keywords:
            if keyword in df.columns:
                value = _finite_trend_number(row[keyword])
                if value is None:
                    continue
                results.append({
                    "date": date_str,
                    "value": value,
                    "keyword": keyword,
                })
    return results


def _growth_window_days(window: str) -> int:
    """Parse a growth window without silently relabeling unsupported input."""
    match = re.fullmatch(r"([1-9]\d*)([DWMY])", window.strip().upper())
    if not match:
        raise ValueError(
            f"Invalid growth window {window!r}; expected a positive integer followed by D, W, M, or Y (for example '90D', '3M', or '1Y')."
        )
    amount = int(match.group(1))
    unit = match.group(2)
    return amount * {"D": 1, "W": 7, "M": 30, "Y": 365}[unit]


def _growth_fetch_timeframe(windows: list[str]) -> str:
    """Choose a provider range that actually covers the longest requested window."""
    max_days = max((_growth_window_days(window) for window in windows), default=365)
    if max_days <= 365:
        return "today 12-m"
    if max_days <= 365 * 5:
        return "today 5-y"
    return "all"


def _growth_from_trend_points(
    points: list[dict],
    keywords: list[str],
    percent_growth: list[str],
) -> list[dict]:
    """Calculate growth from already-fetched completed Trends points."""
    results: list[dict] = []
    for keyword in keywords:
        keyword_points = sorted(
            (
                point
                for point in points
                if point.get("keyword") == keyword
                and point.get("date") is not None
                and _finite_trend_number(point.get("value")) is not None
            ),
            key=lambda point: str(point["date"]),
        )
        if not keyword_points:
            continue

        dates = pandas.to_datetime([point["date"] for point in keyword_points])
        series = pandas.Series(
            [float(point["value"]) for point in keyword_points],
            index=dates,
            dtype=float,
        )
        if series.index.has_duplicates:
            # Repeated provider timestamps must neither crash nearest lookup
            # nor give the same observation extra weight in window averages.
            series = series.groupby(level=0, sort=True).mean()
        current_val = float(series.tail(4).mean())
        latest_date = series.index[-1]

        # Avoid labeling a truncated provider history as full-window growth.
        # Allow one sample interval for weekly/monthly bucket alignment.
        sample_gaps = series.index.to_series().diff().dropna()
        positive_gaps = sample_gaps[sample_gaps > pandas.Timedelta(0)]
        observed_interval = (
            max(positive_gaps.median(), positive_gaps.iloc[-1])
            if not positive_gaps.empty
            else None
        )
        edge_slack = (
            min(pandas.Timedelta(days=31), sample_gaps.median() + pandas.Timedelta(days=1))
            if not sample_gaps.empty
            else pandas.Timedelta(0)
        )
        growth_dict: dict[str, float | None] = {}
        for window in percent_growth:
            window_span = pandas.Timedelta(days=_growth_window_days(window))
            # Weekly/monthly samples cannot support daily growth. One day of
            # bounded slack accommodates 28-31-day calendar-month buckets.
            alignment_slack = min(pandas.Timedelta(days=1), window_span / 10)
            if observed_interval is None or observed_interval > window_span + alignment_slack:
                growth_dict[window] = None
                continue
            target_date = latest_date - window_span
            if target_date < series.index[0] - edge_slack:
                growth_dict[window] = None
                continue
            indices = series.index.get_indexer([target_date], method="nearest")
            idx = len(series) - 1 if len(indices) == 0 or indices[0] < 0 else indices[0]
            start_idx = max(0, idx - 2)
            end_idx = min(len(series), idx + 2)
            past_val = float(series.iloc[start_idx:end_idx].mean())

            if past_val > 0:
                growth_pct = ((current_val - past_val) / past_val) * 100
            else:
                # A zero baseline cannot define a percentage, even for 0 -> 0.
                growth_pct = None
            finite_growth = _finite_trend_number(growth_pct)
            growth_dict[window] = round(finite_growth, 2) if finite_growth is not None else None

        results.append({"keyword": keyword, "growth": growth_dict})
    return results


def _required_news_lookup(value: str, label: str) -> str:
    """Normalize one news lookup value and reject requests with no query text."""
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"News lookup {label} must not be empty.")
    return normalized


def _parse_news_publish_date(value: object) -> Optional[datetime]:
    """Normalize provider/article publication dates to UTC."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
    else:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _comparison_keywords(keyword: str | list[str]) -> list[str]:
    """Keep comparison requests inside the provider's one-to-five-keyword contract."""
    raw_keywords = [keyword] if isinstance(keyword, str) else keyword
    keywords = [value.strip() for value in raw_keywords]
    if not 1 <= len(keywords) <= 5:
        raise ValueError("Google Trends comparisons require between 1 and 5 keywords.")
    if any(not value for value in keywords):
        raise ValueError("Google Trends keywords must not be empty.")
    if len(set(keywords)) != len(keywords):
        raise ValueError("Google Trends comparison keywords must be unique.")
    return keywords


def _required_seed_keyword(keyword: str) -> str:
    """Normalize one seed term and reject requests with no actual query text."""
    normalized = keyword.strip()
    if not normalized:
        raise ValueError("Google Trends seed keyword must not be empty.")
    return normalized


async def get_trends(
    keyword: str | list[str],
    source: str = "google search",
    data_mode: str = "weekly",
    geo: str = "US",
    timeframe: Optional[str] = None,
    cat: int = 0,
) -> list[dict]:
    """
    Pull search interest over time for keywords.

    ``timeframe`` accepts the ranges supported by TrendsPy, including ``today
    12-m``, ``today 5-y``, ``all``, custom relative windows such as ``today
    90-d``, and ``YYYY-MM-DD YYYY-MM-DD``. When it is omitted, the legacy
    ``data_mode`` defaults are retained for backwards compatibility.
    """
    gprop = _google_property(source)

    if timeframe is None:
        normalized_data_mode = data_mode.strip().lower()
        if normalized_data_mode not in _ALLOWED_DATA_MODES:
            allowed = ", ".join(sorted(_ALLOWED_DATA_MODES))
            raise ValueError(
                f"Unsupported data_mode {data_mode!r}; expected one of: {allowed}."
            )
        timeframe = "today 5-y"
        if normalized_data_mode == "daily":
            timeframe = "today 3-m"
        elif normalized_data_mode == "monthly":
            timeframe = "all"

    keywords = _comparison_keywords(keyword)

    df = await _call_trends_async(
        "interest_over_time",
        lambda: tr.interest_over_time(keywords, timeframe=timeframe, geo=geo, cat=cat, gprop=gprop)
    )

    df = _completed_trends_frame(df)
    if df.empty:
        return []

    return _trends_frame_to_points(df, keywords)


async def get_growth(
    keyword: str | list[str],
    source: str = "google search",
    percent_growth: list[str] = None,
    geo: str = "US",
) -> list[dict]:
    """
    Measure interest growth over specified windows.
    """
    if percent_growth is None:
        percent_growth = ["3M", "1Y"]

    keywords = _comparison_keywords(keyword)

    timeframe = _growth_fetch_timeframe(percent_growth)

    gprop = _google_property(source)

    df = await _call_trends_async(
        "interest_over_time",
        lambda: tr.interest_over_time(keywords, timeframe=timeframe, geo=geo, gprop=gprop)
    )

    df = _completed_trends_frame(df)
    if df.empty:
        return []

    points = _trends_frame_to_points(df, keywords)
    return _growth_from_trend_points(points, keywords, percent_growth)


async def get_ranked_trends(
    source: str = "google search",
    sort: str = "recent_growth_pct",
    limit: int = 20,
    geo: str = "US",
) -> list[dict]:
    """
    Rank the current 24-hour Trending Now feed by provider-reported growth or volume.

    The provider does not supply a week-over-week comparison window;
    wow_pct_change remains a legacy alias for recent_growth_pct.
    """
    limit = _validated_trend_result_limit(limit)
    normalized_source = source.strip().lower()
    if normalized_source != "google search":
        raise ValueError("get_ranked_trends supports only source='google search'.")
    normalized_sort = sort.strip().lower()
    if normalized_sort not in _ALLOWED_RANK_SORTS:
        allowed = ", ".join(sorted(_ALLOWED_RANK_SORTS))
        raise ValueError(f"Unsupported sort {sort!r}; expected one of: {allowed}.")

    trends = await _call_trends_async(
        "trending_now",
        lambda: tr.trending_now(geo=geo, hours=24)
    )

    if normalized_sort in ("recent_growth_pct", "wow_pct_change"):
        sorted_trends = sorted(
            trends,
            key=lambda t: t.volume_growth_pct if t.volume_growth_pct is not None else -1,
            reverse=True
        )
    elif normalized_sort == "volume":
        sorted_trends = sorted(
            trends,
            key=lambda t: t.volume if t.volume is not None else -1,
            reverse=True
        )
    else:
        sorted_trends = trends

    sorted_trends = sorted_trends[:limit]

    results = []
    for t in sorted_trends:
        started_ts = t.started_timestamp[0] if (t.started_timestamp and len(t.started_timestamp) > 0) else None

        news_out = []
        if t.news:
            for article in t.news:
                news_out.append({
                    "title": _decode_provider_text(article.title),
                    "url": article.url,
                    "source": _decode_provider_text(article.source),
                    "picture": article.picture,
                    "time": article.time,
                    "snippet": _decode_provider_text(article.snippet)
                })

        results.append({
            "keyword": _decode_provider_text(t.keyword),
            "volume": t.volume,
            "growth_pct": t.volume_growth_pct,
            "started": started_ts,
            "news": news_out
        })
    return results


async def get_top_trends(
    type: str = "Google Trends",
    limit: int = 20,
    geo: str = "US",
) -> list[dict]:
    """
    Get top trends from Google Trends realtime or 24-hour Trending Now feeds.
    """
    limit = _validated_trend_result_limit(limit)
    normalized_type = type.strip().lower()
    if normalized_type not in _ALLOWED_TOP_TREND_TYPES:
        raise ValueError(
            "Unsupported trend type "
            f"{type!r}; expected 'Google Trends' or 'Daily Trends'."
        )

    if normalized_type in ("daily trends", "daily"):
        trends = await _call_trends_async(
            "trending_now", lambda: tr.trending_now(geo=geo, hours=24)
        )
    else:
        trends = await _call_trends_async(
            "trending_now_by_rss", lambda: tr.trending_now_by_rss(geo=geo)
        )

    trends = trends[:limit]

    results = []
    for t in trends:
        news_out = []
        if t.news:
            for article in t.news:
                news_out.append({
                    "title": _decode_provider_text(article.title),
                    "url": article.url,
                    "source": _decode_provider_text(article.source),
                    "picture": article.picture,
                    "time": article.time,
                    "snippet": _decode_provider_text(article.snippet)
                })
        started = getattr(t, "started", None)
        started_timestamp = getattr(t, "started_timestamp", None)
        if started is None and started_timestamp:
            started = started_timestamp[0]
        volume = getattr(t, "volume", None)
        if volume is not None and not isinstance(volume, str):
            volume = str(volume)
        results.append({
            "keyword": _decode_provider_text(t.keyword),
            "volume": volume,
            "link": getattr(t, "link", None),
            "started": started,
            "picture": getattr(t, "picture", None),
            "news": news_out
        })
    return results


async def get_news_by_site(
    site: str,
    period: int = 7,
    max_results: int = 10,
    nlp: bool = True,
    report_progress: Optional[ProgressCallback] = None,
) -> list[newspaper.Article]:
    """Find articles from a specific publisher site using Google News."""
    site = _required_news_lookup(site, "site")
    google_news = _new_google_news(period, max_results)
    gnews_articles = await _call_google_news_async(google_news, "get_news_by_site", site)
    if not gnews_articles:
        logger.debug(f"No articles found for site '{site}' in the last {period} days.")
        return []
    return await process_gnews_articles(
        gnews_articles,
        nlp=nlp,
        report_progress=report_progress,
        period=period,
    )


async def get_interest_by_region(
    keywords: str | list[str],
    timeframe: str = "today 12-m",
    geo: str = "US",
    cat: int = 0,
    gprop: str = "",
    resolution: str = "REGION",
    inc_low_vol: bool = False,
) -> list[dict]:
    """Retrieves geographical interest data based on keywords and other parameters."""
    gprop = _validated_google_property(gprop)
    resolution = _validated_region_resolution(resolution)
    kw_list = _comparison_keywords(keywords)
    df = await _call_trends_async(
        "interest_by_region",
        lambda: tr.interest_by_region(
            keywords=kw_list,
            timeframe=timeframe,
            geo=geo,
            cat=cat,
            gprop=gprop,
            resolution=resolution,
            inc_low_vol=inc_low_vol,
        )
    )
    if df.empty:
        return []
    results = []
    for _, row in df.iterrows():
        values = {}
        for kw in kw_list:
            if kw in df.columns:
                value = _finite_trend_number(row[kw])
                if value is not None:
                    values[kw] = value
        if not values:
            continue
        region = {
            "geoName": str(row["geoName"]),
            "values": values
        }
        if "geoCode" in df.columns and pandas.notna(row["geoCode"]):
            region["geoCode"] = str(row["geoCode"])
        if "lat" in df.columns and (latitude := _finite_trend_number(row["lat"])) is not None:
            region["lat"] = latitude
        if "lng" in df.columns and (longitude := _finite_trend_number(row["lng"])) is not None:
            region["lng"] = longitude
        results.append(region)
    return results


async def get_related_queries(
    keyword: str,
    timeframe: str = "today 12-m",
    geo: str = "US",
    cat: int = 0,
    gprop: str = "",
) -> dict[str, list[dict]]:
    """Retrieves related queries for a single search term."""
    keyword = _required_seed_keyword(keyword)
    gprop = _validated_google_property(gprop)
    res = await _call_trends_async(
        "related_queries",
        lambda: _call_related_queries_with_unavailable_retry(
            keyword=keyword,
            timeframe=timeframe,
            geo=geo,
            cat=cat,
            gprop=gprop,
            headers={"referer": "https://www.google.com/"}
        )
    )
    out = {"top": [], "rising": []}
    for key in ("top", "rising"):
        df = res.get(key)
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                value, is_breakout = _related_trend_value(row["value"])
                if value is None and not is_breakout:
                    continue
                item = {
                    "query": str(row["query"]),
                    "value": value
                }
                if is_breakout:
                    item["is_breakout"] = True
                out[key].append(item)
    return out


async def get_related_topics(
    keyword: str,
    timeframe: str = "today 12-m",
    geo: str = "US",
    cat: int = 0,
    gprop: str = "",
) -> dict[str, list[dict]]:
    """Retrieves related topics for a single search term."""
    keyword = _required_seed_keyword(keyword)
    gprop = _validated_google_property(gprop)
    res = await _call_trends_async(
        "related_topics",
        lambda: tr.related_topics(
            keyword=keyword,
            timeframe=timeframe,
            geo=geo,
            cat=cat,
            gprop=gprop,
            headers={"referer": "https://www.google.com/"}
        )
    )
    out = {"top": [], "rising": []}
    for key in ("top", "rising"):
        df = res.get(key)
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                value, is_breakout = _related_trend_value(row["value"])
                if value is None and not is_breakout:
                    continue
                item = {
                    "mid": str(row["mid"]),
                    "title": str(row["title"]),
                    "type": str(row["type"]),
                    "value": value
                }
                if is_breakout:
                    item["is_breakout"] = True
                out[key].append(item)
    return out


async def get_suggestions(keyword: str, language: Optional[str] = None) -> list[dict]:
    """Retrieves autocomplete suggestions for a search term."""
    keyword = _required_seed_keyword(keyword)
    df = await _call_trends_async(
        "suggestions",
        lambda: tr.suggestions(keyword=keyword, language=language)
    )
    if df.empty:
        return []
    results = []
    for _, row in df.iterrows():
        results.append({
            "mid": str(row["mid"]),
            "title": str(row["title"]),
            "type": str(row["type"])
        })
    return results


async def get_categories() -> list[dict]:
    """Retrieves category list from Google Trends."""
    cats = await _call_trends_async(
        "categories",
        lambda: tr.categories()
    )
    return cats
