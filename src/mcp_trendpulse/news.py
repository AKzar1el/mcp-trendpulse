"""
# news.py
This module provides functions to find and download news articles using Google News.
It allows searching for articles by keyword, location, or topic, and can also retrieve google trending terms.
It uses the `gnews` library to search for news articles and trendspy to get Google Trends data.
It will fallback to using Playwright for websites that are difficult to scrape with newspaper4k or cloudscraper.
"""

import os
import re
import json
import asyncio
import ipaddress
import socket
from decimal import Decimal, InvalidOperation
import pandas
from gnews import GNews
import newspaper  # newspaper4k
from googlenewsdecoder import gnewsdecoder
import cloudscraper
from playwright.async_api import async_playwright, Browser, Playwright
from trendspy import Trends, TrendKeywordLite
from typing import Optional, cast, overload, Literal, Awaitable
from contextlib import asynccontextmanager, AsyncContextDecorator
import logging
from collections.abc import Callable
from urllib.parse import urljoin, urlsplit

logger = logging.getLogger(__name__)

for logname in logging.root.manager.loggerDict:
    if logname.startswith("newspaper"):
        logging.getLogger(logname).setLevel(logging.ERROR)

try:
    google_trends_delay = float(os.environ.get("GOOGLE_TRENDS_DELAY", "2.0"))
except ValueError:
    logger.warning("Invalid GOOGLE_TRENDS_DELAY environment variable, using default 2.0")
    google_trends_delay = 2.0

tr = Trends(request_delay=google_trends_delay)

_scraper_instance = None

_INVALID_TREND_VOLUME = -1
_TREND_VOLUME_PATTERN = re.compile(
    r"^(?P<number>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)(?P<suffix>[KMB])?\+?$",
    re.IGNORECASE,
)


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
    global _scraper_instance
    if _scraper_instance is None:
        try:
            _scraper_instance = cloudscraper.create_scraper(
                interpreter="js2py",
                delay=5,
                browser="chrome",
                debug=False,
            )
        except Exception as e:
            logger.error(f"Failed to initialize cloudscraper: {e}")
            return None
    return _scraper_instance


scraper = None


def _new_google_news(period: int, max_results: int) -> GNews:
    """Create an isolated Google News client for one request."""
    client = GNews(language="en")
    client.period = f"{period}d"
    client.max_results = max_results
    return client


ProgressCallback = Callable[[float, Optional[float]], Awaitable[None]]

_ALLOWED_ARTICLE_URL_SCHEMES = {"http", "https"}
_MAX_ARTICLE_REDIRECTS = 10
ARTICLE_HTTP_TIMEOUT_SECONDS = 12
ARTICLE_BROWSER_NAVIGATION_TIMEOUT_MS = 15_000
ARTICLE_MAX_HTML_BYTES = 5 * 1024 * 1024
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
                        cls._browser = await cls._playwright.chromium.launch(headless=True)
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
    """Allow only browser requests whose targets passed article network validation."""
    try:
        await asyncio.to_thread(target_validator.validate_url, route.request.url)
    except ValueError as exc:
        await route.abort("blockedbyclient")
        return exc
    else:
        await route.continue_()
        return None


async def download_article_with_playwright(
    url: str,
    target_validator: Optional[ArticleTargetValidator] = None,
) -> newspaper.Article | None:
    """
    Download an article using Playwright to handle complex websites (async).
    """
    target_validator = target_validator or ArticleTargetValidator()
    url = target_validator.validate_url(url)
    blocked_target_error: Optional[ValueError] = None

    async def route_handler(route) -> None:
        nonlocal blocked_target_error
        error = await guard_playwright_route(route, target_validator)
        if error is not None:
            blocked_target_error = error

    async with BrowserManager.browser_context() as context:
        try:
            await context.route("**/*", route_handler)
            page = await context.new_page()
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=ARTICLE_BROWSER_NAVIGATION_TIMEOUT_MS,
            )
            if blocked_target_error:
                raise blocked_target_error
            await asyncio.sleep(2)  # Wait for the page to load completely
            if blocked_target_error:
                raise blocked_target_error
            content = await page.content()
            if len(content.encode("utf-8")) > ARTICLE_MAX_HTML_BYTES:
                logger.warning("Rejected browser article content from %s because it exceeds the HTML size limit", url)
                return None
            article = newspaper.article(url, input_html=content)
            return article
        except ValueError:
            raise
        except Exception as e:
            logger.warning(f"Error downloading article with Playwright from {url}\n {e.args}")
            return None


def _is_unsupported_article_response(response) -> bool:
    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
    return content_type in _UNSUPPORTED_ARTICLE_CONTENT_TYPES or content_type.startswith(
        _UNSUPPORTED_ARTICLE_CONTENT_TYPE_PREFIXES
    )


def _read_article_response(response, url: str) -> Optional[str]:
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
    for chunk in response.iter_content(chunk_size=_ARTICLE_RESPONSE_CHUNK_SIZE):
        if not chunk:
            continue
        body.extend(chunk)
        if len(body) > ARTICLE_MAX_HTML_BYTES:
            logger.warning("Rejected article response from %s because it exceeds the HTML size limit", url)
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

        for _ in range(_MAX_ARTICLE_REDIRECTS):
            response = scraper_inst.get(
                url,
                timeout=ARTICLE_HTTP_TIMEOUT_SECONDS,
                allow_redirects=False,
                stream=True,
            )
            try:
                if 300 <= response.status_code < 400:
                    location = response.headers.get("Location")
                    if not location:
                        return None
                    url = target_validator.validate_url(urljoin(url, location))
                    continue

                if response.status_code < 400:
                    html = _read_article_response(response, url)
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
            if decoded_url.get("status"):
                return decoded_url["decoded_url"]
            else:
                logger.debug("Failed to decode Google News RSS link:")
        except Exception as err:
            logger.warning(f"Error while decoding url {url}\n {err.args}")
    return None


async def download_article(url: str) -> newspaper.Article | None:
    """
    Download an article from a given URL using newspaper4k and cloudscraper (async).
    """
    target_validator = ArticleTargetValidator()
    url = target_validator.validate_url(url)
    if url.startswith("https://news.google.com/rss/"):
        decoded = decode_url(url)
        if decoded is None:
            return None
        url = target_validator.validate_url(decoded)
    article = download_article_with_scraper(url, target_validator)
    if article is None or not article.text:
        logger.debug("Attempting to download article with playwright")
        article = await download_article_with_playwright(url, target_validator)
    return article


async def process_gnews_articles(
    gnews_articles: list[dict],
    nlp: bool = True,
    report_progress: Optional[ProgressCallback] = None,
) -> list[newspaper.Article]:
    """
    Process a list of Google News articles and download them (async).
    Optionally report progress via report_progress callback.
    """
    articles = []
    total = len(gnews_articles)
    for idx, gnews_article in enumerate(gnews_articles):
        article = await download_article(gnews_article["url"])
        if article is None or not article.text:
            logger.debug(f"Failed to download article from {gnews_article['url']}:\n{article}")
            continue
        if nlp:
            article.nlp()
        articles.append(article)
        if report_progress:
            await report_progress(idx, total)
    return articles


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
    google_news = _new_google_news(period, max_results)
    gnews_articles = await asyncio.to_thread(google_news.get_news, keyword)
    if not gnews_articles:
        logger.debug(f"No articles found for keyword '{keyword}' in the last {period} days.")
        return []
    return await process_gnews_articles(gnews_articles, nlp=nlp, report_progress=report_progress)


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
    gnews_articles = await asyncio.to_thread(google_news.get_top_news)
    if not gnews_articles:
        logger.debug("No top news articles found.")
        return []
    return await process_gnews_articles(gnews_articles, nlp=nlp, report_progress=report_progress)


async def get_news_by_location(
    location: str,
    period=7,
    max_results: int = 10,
    nlp: bool = True,
    report_progress: Optional[ProgressCallback] = None,
) -> list[newspaper.Article]:
    """Find articles by location using Google News."""
    google_news = _new_google_news(period, max_results)
    gnews_articles = await asyncio.to_thread(google_news.get_news_by_location, location)
    if not gnews_articles:
        logger.debug(f"No articles found for location '{location}' in the last {period} days.")
        return []
    return await process_gnews_articles(gnews_articles, nlp=nlp, report_progress=report_progress)


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
    google_news = _new_google_news(period, max_results)
    gnews_articles = await asyncio.to_thread(google_news.get_news_by_topic, topic)
    if not gnews_articles:
        logger.debug(f"No articles found for topic '{topic}' in the last {period} days.")
        return []
    return await process_gnews_articles(gnews_articles, nlp=nlp, report_progress=report_progress)


@overload
async def get_trending_terms(geo: str = "US", full_data: Literal[False] = False) -> list[dict[str, str]]: ...


@overload
async def get_trending_terms(geo: str = "US", full_data: Literal[True] = True) -> list[TrendKeywordLite]: ...


async def get_trending_terms(geo: str = "US", full_data: bool = False) -> list[dict[str, str]] | list[TrendKeywordLite]:
    """
    Returns google trends for a specific geo location.
    """
    try:
        trends = cast(list[TrendKeywordLite], tr.trending_now_by_rss(geo=geo))
        trends = sorted(trends, key=lambda trend: parse_trending_volume(trend.volume), reverse=True)
        if not full_data:
            return [{"keyword": trend.keyword, "volume": trend.volume} for trend in trends]
        return trends
    except Exception as e:
        logger.warning(f"Error fetching trending terms: {e}")
        return []


def save_article_to_json(article: newspaper.Article, filename: Optional[str] = None) -> None:
    """Save an article to a JSON file."""
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

    try:
        with open(filename, "w") as f:
            json.dump(normalize_collections(article_data), f, indent=4)
        logger.debug(f"Article saved to {filename}")
    except (OSError, IOError) as e:
        logger.error(f"Failed to save article to {filename}: {e}")


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
    source_map = {
        "google search": "",
        "youtube search": "youtube",
        "news search": "news",
        "image search": "images",
        "google shopping": "froogle",
    }
    gprop = source_map.get(source.lower(), "")

    if timeframe is None:
        timeframe = "today 5-y"
        if data_mode.lower() == "daily":
            timeframe = "today 3-m"
        elif data_mode.lower() == "monthly":
            timeframe = "all"

    keywords = [keyword] if isinstance(keyword, str) else keyword

    loop = asyncio.get_running_loop()
    df = await loop.run_in_executor(
        None,
        lambda: tr.interest_over_time(keywords, timeframe=timeframe, geo=geo, cat=cat, gprop=gprop)
    )

    if df.empty:
        return []

    results = []
    for dt, row in df.iterrows():
        date_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]
        for kw in keywords:
            if kw in df.columns:
                results.append({
                    "date": date_str,
                    "value": float(row[kw]),
                    "keyword": kw
                })
    return results


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

    keywords = [keyword] if isinstance(keyword, str) else keyword

    timeframe = "today 12-m"
    for pg in percent_growth:
        if "Y" in pg:
            try:
                years = int(pg.replace("Y", ""))
                if years > 1:
                    timeframe = "today 5-y"
            except Exception:
                pass

    source_map = {
        "google search": "",
        "youtube search": "youtube",
        "news search": "news",
        "image search": "images",
        "google shopping": "froogle",
    }
    gprop = source_map.get(source.lower(), "")

    loop = asyncio.get_running_loop()
    df = await loop.run_in_executor(
        None,
        lambda: tr.interest_over_time(keywords, timeframe=timeframe, geo=geo, gprop=gprop)
    )

    if df.empty:
        return []

    results = []
    for kw in keywords:
        if kw not in df.columns:
            continue

        series = df[kw]
        current_val = float(series.tail(4).mean())

        growth_dict = {}
        for pg in percent_growth:
            latest_date = df.index[-1]
            if pg.endswith("M"):
                try:
                    months = int(pg[:-1])
                except ValueError:
                    months = 3
                days_offset = months * 30
            elif pg.endswith("Y"):
                try:
                    years = int(pg[:-1])
                except ValueError:
                    years = 1
                days_offset = years * 365
            elif pg.endswith("W"):
                try:
                    weeks = int(pg[:-1])
                except ValueError:
                    weeks = 1
                days_offset = weeks * 7
            elif pg.endswith("D"):
                try:
                    days_offset = int(pg[:-1])
                except ValueError:
                    days_offset = 90
            else:
                days_offset = 90

            target_date = latest_date - pandas.Timedelta(days=days_offset)
            indices = df.index.get_indexer([target_date], method='nearest')
            if len(indices) == 0 or indices[0] < 0:
                idx = len(df) - 1
            else:
                idx = indices[0]

            start_idx = max(0, idx - 2)
            end_idx = min(len(df), idx + 2)
            past_val = float(series.iloc[start_idx:end_idx].mean())

            if past_val > 0:
                growth_pct = ((current_val - past_val) / past_val) * 100
            else:
                growth_pct = current_val * 100 if current_val > 0 else 0.0

            growth_dict[pg] = round(growth_pct, 2)

        results.append({
            "keyword": kw,
            "growth": growth_dict
        })
    return results


async def get_ranked_trends(
    source: str = "google search",
    sort: str = "wow_pct_change",
    limit: int = 20,
    geo: str = "US",
) -> list[dict]:
    """
    Get ranked trending keywords on Google Search.
    """
    loop = asyncio.get_running_loop()
    trends = await loop.run_in_executor(
        None,
        lambda: tr.trending_now(geo=geo, hours=24)
    )

    if sort == "wow_pct_change":
        sorted_trends = sorted(
            trends,
            key=lambda t: t.volume_growth_pct if t.volume_growth_pct is not None else -1,
            reverse=True
        )
    elif sort == "volume":
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
                    "title": article.title,
                    "url": article.url,
                    "source": article.source,
                    "picture": article.picture,
                    "time": article.time,
                    "snippet": article.snippet
                })

        results.append({
            "keyword": t.keyword,
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
    Get top trends using RSS trending feeds.
    """
    loop = asyncio.get_running_loop()
    if type.lower() in ("daily trends", "daily"):
        trends = await loop.run_in_executor(
            None,
            lambda: tr.daily_trends_deprecated_by_rss(geo=geo)
        )
    else:
        trends = await loop.run_in_executor(
            None,
            lambda: tr.trending_now_by_rss(geo=geo)
        )

    trends = trends[:limit]

    results = []
    for t in trends:
        news_out = []
        if t.news:
            for article in t.news:
                news_out.append({
                    "title": article.title,
                    "url": article.url,
                    "source": article.source,
                    "picture": article.picture,
                    "time": article.time,
                    "snippet": article.snippet
                })
        results.append({
            "keyword": t.keyword,
            "volume": t.volume,
            "link": t.link,
            "started": t.started,
            "picture": t.picture,
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
    google_news = _new_google_news(period, max_results)
    gnews_articles = await asyncio.to_thread(google_news.get_news_by_site, site)
    if not gnews_articles:
        logger.debug(f"No articles found for site '{site}' in the last {period} days.")
        return []
    return await process_gnews_articles(gnews_articles, nlp=nlp, report_progress=report_progress)


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
    kw_list = [keywords] if isinstance(keywords, str) else keywords
    loop = asyncio.get_running_loop()
    df = await loop.run_in_executor(
        None,
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
                values[kw] = float(row[kw])
        results.append({
            "geoName": str(row["geoName"]),
            "geoCode": str(row["geoCode"]),
            "values": values
        })
    return results


async def get_related_queries(
    keyword: str,
    timeframe: str = "today 12-m",
    geo: str = "US",
    cat: int = 0,
    gprop: str = "",
) -> dict[str, list[dict]]:
    """Retrieves related queries for a single search term."""
    loop = asyncio.get_running_loop()
    res = await loop.run_in_executor(
        None,
        lambda: tr.related_queries(
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
                out[key].append({
                    "query": str(row["query"]),
                    "value": float(row["value"])
                })
    return out


async def get_related_topics(
    keyword: str,
    timeframe: str = "today 12-m",
    geo: str = "US",
    cat: int = 0,
    gprop: str = "",
) -> dict[str, list[dict]]:
    """Retrieves related topics for a single search term."""
    loop = asyncio.get_running_loop()
    res = await loop.run_in_executor(
        None,
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
                out[key].append({
                    "mid": str(row["mid"]),
                    "title": str(row["title"]),
                    "type": str(row["type"]),
                    "value": float(row["value"])
                })
    return out


async def get_suggestions(keyword: str, language: Optional[str] = None) -> list[dict]:
    """Retrieves autocomplete suggestions for a search term."""
    loop = asyncio.get_running_loop()
    df = await loop.run_in_executor(
        None,
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
    loop = asyncio.get_running_loop()
    cats = await loop.run_in_executor(
        None,
        lambda: tr.categories()
    )
    return cats
