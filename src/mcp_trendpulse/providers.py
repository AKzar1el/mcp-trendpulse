from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, ClassVar, Protocol

import newspaper

from mcp_trendpulse import news


class NewsProvider(Protocol):
    """Provider contract for article discovery and retrieval."""

    provider_id: str

    async def get_news_by_keyword(
        self,
        keyword: str,
        period: int = 7,
        max_results: int = 10,
        nlp: bool = True,
        report_progress: news.ProgressCallback | None = None,
    ) -> list[newspaper.Article]: ...

    async def get_news_by_location(
        self,
        location: str,
        period: int = 7,
        max_results: int = 10,
        nlp: bool = True,
        report_progress: news.ProgressCallback | None = None,
    ) -> list[newspaper.Article]: ...

    async def get_news_by_topic(
        self,
        topic: str,
        period: int = 7,
        max_results: int = 10,
        nlp: bool = True,
        report_progress: news.ProgressCallback | None = None,
    ) -> list[newspaper.Article]: ...

    async def get_top_news(
        self,
        period: int = 3,
        max_results: int = 10,
        nlp: bool = True,
        report_progress: news.ProgressCallback | None = None,
    ) -> list[newspaper.Article]: ...

    async def get_news_by_site(
        self,
        site: str,
        period: int = 7,
        max_results: int = 10,
        nlp: bool = True,
        report_progress: news.ProgressCallback | None = None,
    ) -> list[newspaper.Article]: ...

    def validate_article_url(self, url: str) -> str: ...

    async def download_article(self, url: str) -> newspaper.Article | None: ...


class TrendsProvider(Protocol):
    """Provider contract for search-interest and trend discovery data."""

    provider_id: str

    async def get_trending_terms(
        self,
        geo: str = "US",
        full_data: bool = False,
    ) -> list[dict[str, Any]]: ...

    async def get_trends(
        self,
        keyword: str | list[str],
        source: str = "google search",
        data_mode: str = "weekly",
        geo: str = "US",
        timeframe: str | None = None,
        cat: int = 0,
    ) -> list[dict[str, Any]]: ...

    async def get_growth(
        self,
        keyword: str | list[str],
        source: str = "google search",
        percent_growth: list[str] | None = None,
        geo: str = "US",
    ) -> list[dict[str, Any]]: ...

    async def get_ranked_trends(
        self,
        source: str = "google search",
        sort: str = "wow_pct_change",
        limit: int = 20,
        geo: str = "US",
    ) -> list[dict[str, Any]]: ...

    async def get_top_trends(
        self,
        type: str = "Google Trends",
        limit: int = 20,
        geo: str = "US",
    ) -> list[dict[str, Any]]: ...

    async def get_interest_by_region(
        self,
        keywords: str | list[str],
        timeframe: str = "today 12-m",
        geo: str = "US",
        cat: int = 0,
        gprop: str = "",
        resolution: str = "REGION",
        inc_low_vol: bool = False,
    ) -> list[dict[str, Any]]: ...

    async def get_related_queries(
        self,
        keyword: str,
        timeframe: str = "today 12-m",
        geo: str = "US",
        cat: int = 0,
        gprop: str = "",
    ) -> dict[str, list[dict[str, Any]]]: ...

    async def get_related_topics(
        self,
        keyword: str,
        timeframe: str = "today 12-m",
        geo: str = "US",
        cat: int = 0,
        gprop: str = "",
    ) -> dict[str, list[dict[str, Any]]]: ...

    async def get_suggestions(
        self,
        keyword: str,
        language: str | None = None,
    ) -> list[dict[str, Any]]: ...

    async def get_categories(self) -> list[dict[str, Any]]: ...


@dataclass(frozen=True, slots=True)
class CommunityNewsProvider:
    """Adapter exposing the existing Community news implementation."""

    provider_id: ClassVar[str] = "google_news"

    async def get_news_by_keyword(
        self,
        keyword: str,
        period: int = 7,
        max_results: int = 10,
        nlp: bool = True,
        report_progress: news.ProgressCallback | None = None,
    ) -> list[newspaper.Article]:
        return await news.get_news_by_keyword(
            keyword=keyword,
            period=period,
            max_results=max_results,
            nlp=nlp,
            report_progress=report_progress,
        )

    async def get_news_by_location(
        self,
        location: str,
        period: int = 7,
        max_results: int = 10,
        nlp: bool = True,
        report_progress: news.ProgressCallback | None = None,
    ) -> list[newspaper.Article]:
        return await news.get_news_by_location(
            location=location,
            period=period,
            max_results=max_results,
            nlp=nlp,
            report_progress=report_progress,
        )

    async def get_news_by_topic(
        self,
        topic: str,
        period: int = 7,
        max_results: int = 10,
        nlp: bool = True,
        report_progress: news.ProgressCallback | None = None,
    ) -> list[newspaper.Article]:
        return await news.get_news_by_topic(
            topic=topic,
            period=period,
            max_results=max_results,
            nlp=nlp,
            report_progress=report_progress,
        )

    async def get_top_news(
        self,
        period: int = 3,
        max_results: int = 10,
        nlp: bool = True,
        report_progress: news.ProgressCallback | None = None,
    ) -> list[newspaper.Article]:
        return await news.get_top_news(
            period=period,
            max_results=max_results,
            nlp=nlp,
            report_progress=report_progress,
        )

    async def get_news_by_site(
        self,
        site: str,
        period: int = 7,
        max_results: int = 10,
        nlp: bool = True,
        report_progress: news.ProgressCallback | None = None,
    ) -> list[newspaper.Article]:
        return await news.get_news_by_site(
            site=site,
            period=period,
            max_results=max_results,
            nlp=nlp,
            report_progress=report_progress,
        )

    def validate_article_url(self, url: str) -> str:
        return news.validate_article_url(url)

    async def download_article(self, url: str) -> newspaper.Article | None:
        return await news.download_article(url)


def _plain_mapping(value: Any) -> dict[str, Any]:
    """Copy provider objects into transport-neutral plain mappings."""
    if isinstance(value, dict):
        result = dict(value)
    else:
        try:
            result = dict(vars(value))
        except TypeError as exc:
            raise TypeError("Trend provider item must expose mapping-like data.") from exc

    related_news = result.get("news")
    if related_news:
        result["news"] = [_plain_mapping(article) for article in related_news]
    return result


@dataclass(frozen=True, slots=True)
class CommunityTrendsProvider:
    """Adapter exposing the existing Community trends implementation."""

    provider_id: ClassVar[str] = "google_trends"

    async def get_trending_terms(
        self,
        geo: str = "US",
        full_data: bool = False,
    ) -> list[dict[str, Any]]:
        results = await news.get_trending_terms(geo=geo, full_data=full_data)
        return [_plain_mapping(item) for item in results]

    async def get_trends(
        self,
        keyword: str | list[str],
        source: str = "google search",
        data_mode: str = "weekly",
        geo: str = "US",
        timeframe: str | None = None,
        cat: int = 0,
    ) -> list[dict[str, Any]]:
        return await news.get_trends(
            keyword=keyword,
            source=source,
            data_mode=data_mode,
            geo=geo,
            timeframe=timeframe,
            cat=cat,
        )

    async def get_growth(
        self,
        keyword: str | list[str],
        source: str = "google search",
        percent_growth: list[str] | None = None,
        geo: str = "US",
    ) -> list[dict[str, Any]]:
        return await news.get_growth(
            keyword=keyword,
            source=source,
            percent_growth=percent_growth,
            geo=geo,
        )

    async def get_ranked_trends(
        self,
        source: str = "google search",
        sort: str = "wow_pct_change",
        limit: int = 20,
        geo: str = "US",
    ) -> list[dict[str, Any]]:
        return await news.get_ranked_trends(
            source=source,
            sort=sort,
            limit=limit,
            geo=geo,
        )

    async def get_top_trends(
        self,
        type: str = "Google Trends",
        limit: int = 20,
        geo: str = "US",
    ) -> list[dict[str, Any]]:
        return await news.get_top_trends(type=type, limit=limit, geo=geo)

    async def get_interest_by_region(
        self,
        keywords: str | list[str],
        timeframe: str = "today 12-m",
        geo: str = "US",
        cat: int = 0,
        gprop: str = "",
        resolution: str = "REGION",
        inc_low_vol: bool = False,
    ) -> list[dict[str, Any]]:
        return await news.get_interest_by_region(
            keywords=keywords,
            timeframe=timeframe,
            geo=geo,
            cat=cat,
            gprop=gprop,
            resolution=resolution,
            inc_low_vol=inc_low_vol,
        )

    async def get_related_queries(
        self,
        keyword: str,
        timeframe: str = "today 12-m",
        geo: str = "US",
        cat: int = 0,
        gprop: str = "",
    ) -> dict[str, list[dict[str, Any]]]:
        return await news.get_related_queries(
            keyword=keyword,
            timeframe=timeframe,
            geo=geo,
            cat=cat,
            gprop=gprop,
        )

    async def get_related_topics(
        self,
        keyword: str,
        timeframe: str = "today 12-m",
        geo: str = "US",
        cat: int = 0,
        gprop: str = "",
    ) -> dict[str, list[dict[str, Any]]]:
        return await news.get_related_topics(
            keyword=keyword,
            timeframe=timeframe,
            geo=geo,
            cat=cat,
            gprop=gprop,
        )

    async def get_suggestions(
        self,
        keyword: str,
        language: str | None = None,
    ) -> list[dict[str, Any]]:
        return await news.get_suggestions(keyword=keyword, language=language)

    async def get_categories(self) -> list[dict[str, Any]]:
        return await news.get_categories()


@dataclass(frozen=True, slots=True)
class ProviderSet:
    """News/trends provider selection for one execution context."""

    news: NewsProvider
    trends: TrendsProvider


COMMUNITY_PROVIDERS = ProviderSet(
    news=CommunityNewsProvider(),
    trends=CommunityTrendsProvider(),
)
_provider_set: ContextVar[ProviderSet] = ContextVar(
    "trendpulse_provider_set",
    default=COMMUNITY_PROVIDERS,
)


def get_provider_set() -> ProviderSet:
    """Return providers selected for the current async execution context."""
    return _provider_set.get()


@contextmanager
def use_provider_set(providers: ProviderSet) -> Iterator[ProviderSet]:
    """Temporarily select providers without mutating process-global state."""
    token = _provider_set.set(providers)
    try:
        yield providers
    finally:
        _provider_set.reset(token)
