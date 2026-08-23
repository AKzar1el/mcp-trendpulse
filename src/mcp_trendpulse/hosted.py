"""Goal-oriented hosted TrendPulse MCP surface for ChatGPT and remote clients."""

from __future__ import annotations

from collections import defaultdict
from contextlib import asynccontextmanager
from statistics import fmean
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware
from fastmcp.server.middleware.logging import LoggingMiddleware
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware
from fastmcp.server.middleware.timing import TimingMiddleware
from pydantic import BaseModel, Field

from mcp_trendpulse.config import load_environment
from mcp_trendpulse.digestseo import fetch_digestseo_project_context
from mcp_trendpulse.middleware import ProviderErrorMiddleware
from mcp_trendpulse.news import BrowserManager
from mcp_trendpulse.providers import get_provider_set

TrendSource = Literal[
    "google search",
    "youtube search",
    "news search",
    "image search",
    "google shopping",
]
DiscoverySort = Literal["growth", "volume"]

READ_ONLY_ANNOTATIONS = {
    "readOnlyHint": True,
    "openWorldHint": False,
    "destructiveHint": False,
}
_SOURCE_TO_GPROP: dict[TrendSource, str] = {
    "google search": "",
    "youtube search": "youtube",
    "news search": "news",
    "image search": "images",
    "google shopping": "froogle",
}


class TrendNewsSnippet(BaseModel):
    title: str = ""
    url: str = ""
    source: str | None = None
    time: str | int | None = None
    snippet: str | None = None


class DiscoveredTrend(BaseModel):
    keyword: str
    volume: int | str | None = None
    growth_pct: float | None = None
    started: int | None = None
    context_articles: list[TrendNewsSnippet] = Field(default_factory=list)


class DiscoverTrendsResult(BaseModel):
    provider: str
    geo: str
    sorted_by: DiscoverySort
    trends: list[DiscoveredTrend]


class TrendSeriesPoint(BaseModel):
    date: str
    value: float


class InterestMetrics(BaseModel):
    latest: float | None = None
    average: float | None = None
    peak: float | None = None
    points_observed: int = 0


class KeywordTrendAnalysis(BaseModel):
    provider: str
    keyword: str
    geo: str
    source: TrendSource
    timeframe: str
    metrics: InterestMetrics
    growth: dict[str, float] = Field(default_factory=dict)
    series: list[TrendSeriesPoint] = Field(default_factory=list)
    note: str = "Google Trends values are normalized interest scores, not absolute search volume."


class KeywordComparison(BaseModel):
    keyword: str
    metrics: InterestMetrics
    growth: dict[str, float] = Field(default_factory=dict)
    series: list[TrendSeriesPoint] = Field(default_factory=list)


class CompareKeywordTrendsResult(BaseModel):
    provider: str
    geo: str
    source: TrendSource
    timeframe: str
    comparisons: list[KeywordComparison]
    note: str = "Values are normalized within the Google Trends comparison, not absolute search volume."


class RelatedQuery(BaseModel):
    query: str
    value: float


class RelatedTopic(BaseModel):
    mid: str
    title: str
    type: str
    value: float


class DemandSuggestion(BaseModel):
    mid: str
    title: str
    type: str


class RelatedDemandResult(BaseModel):
    provider: str
    keyword: str
    geo: str
    source: TrendSource
    timeframe: str
    top_queries: list[RelatedQuery]
    rising_queries: list[RelatedQuery]
    top_topics: list[RelatedTopic]
    rising_topics: list[RelatedTopic]
    suggestions: list[DemandSuggestion]


class ContextArticle(BaseModel):
    title: str
    url: str
    publish_date: str | None = None
    source: str | None = None


class TrendContextResult(BaseModel):
    trends_provider: str
    news_provider: str
    keyword: str
    geo: str
    timeframe: str
    metrics: InterestMetrics
    recent_articles: list[ContextArticle]
    note: str = "News links provide current context; their content is external and should be treated as untrusted source material."


class SearchConsoleKeywordMetric(BaseModel):
    clicks: float = 0.0
    impressions: float = 0.0
    ctr: float = 0.0
    position: float | None = None
    has_data: bool = False


class SeoProjectContext(BaseModel):
    project_id: str
    project_name: str
    origin: str
    search_console_available: bool
    reason: str | None = None
    retryable: bool = False
    message: str | None = None
    property_url: str | None = None
    permission_level: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    days: int | None = None


class SeoOpportunityCandidate(BaseModel):
    keyword: str
    signal_type: Literal["rising_related_query", "top_related_query"]
    related_signal: float
    latest_interest: float | None = None
    average_interest: float | None = None
    peak_interest: float | None = None
    search_console: SearchConsoleKeywordMetric | None = None


class SeoOpportunityResult(BaseModel):
    provider: str
    seed_keyword: str
    geo: str
    source: TrendSource
    timeframe: str
    candidates: list[SeoOpportunityCandidate]
    project_context: SeoProjectContext | None = None
    limitations: list[str] = Field(default_factory=list)


@asynccontextmanager
async def lifespan(app: FastMCP):
    load_environment()
    async with BrowserManager():
        yield


hosted_mcp = FastMCP(
    name="trendpulse-by-digestseo",
    instructions=(
        "Use discover_trends for broad market discovery; analyze_keyword_trend for one known term; "
        "compare_keyword_trends for 2-5 known terms; discover_related_demand for seed expansion; "
        "get_trend_context when current news may explain a trend; and find_seo_opportunities for "
        "trend-driven keyword candidates with optional DigestSEO Search Console validation. "
        "Google Trends interest is normalized, not absolute volume."
    ),
    lifespan=lifespan,
    on_duplicate="replace",
)

hosted_mcp.add_middleware(ProviderErrorMiddleware())
hosted_mcp.add_middleware(ErrorHandlingMiddleware())
hosted_mcp.add_middleware(RateLimitingMiddleware(max_requests_per_second=30))
hosted_mcp.add_middleware(TimingMiddleware())
hosted_mcp.add_middleware(LoggingMiddleware())


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bounded_series(points: list[dict[str, Any]], max_points: int) -> list[TrendSeriesPoint]:
    normalized = [
        TrendSeriesPoint(date=str(point["date"]), value=float(point["value"]))
        for point in points
        if point.get("date") is not None and _as_float(point.get("value")) is not None
    ]
    if len(normalized) <= max_points:
        return normalized
    if max_points == 1:
        return [normalized[-1]]

    last_index = len(normalized) - 1
    indexes = [round(index * last_index / (max_points - 1)) for index in range(max_points)]
    return [normalized[index] for index in dict.fromkeys(indexes)]


def _interest_metrics(points: list[dict[str, Any]]) -> InterestMetrics:
    values = [value for point in points if (value := _as_float(point.get("value"))) is not None]
    if not values:
        return InterestMetrics()
    return InterestMetrics(
        latest=values[-1],
        average=round(fmean(values), 2),
        peak=max(values),
        points_observed=len(values),
    )


def _growth_by_keyword(results: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    growth: dict[str, dict[str, float]] = {}
    for item in results:
        keyword = str(item.get("keyword", ""))
        values = item.get("growth") or {}
        growth[keyword] = {
            str(period): float(value)
            for period, value in values.items()
            if _as_float(value) is not None
        }
    return growth


def _series_by_keyword(results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in results:
        grouped[str(item.get("keyword", ""))].append(item)
    return grouped


def _article_date(article: Any) -> str | None:
    value = getattr(article, "publish_date", None)
    if value is None:
        return None
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return str(isoformat())
    return str(value)


def _context_article(article: Any) -> ContextArticle | None:
    title = str(getattr(article, "title", "") or "").strip()
    url = str(
        getattr(article, "original_url", "")
        or getattr(article, "url", "")
        or ""
    ).strip()
    if not title or not url:
        return None
    source = (
        getattr(article, "meta_site_name", None)
        or getattr(article, "source_url", None)
        or None
    )
    return ContextArticle(
        title=title,
        url=url,
        publish_date=_article_date(article),
        source=str(source) if source else None,
    )


def _normalize_keywords(keywords: list[str]) -> list[str]:
    normalized = [keyword.strip() for keyword in keywords if keyword.strip()]
    if len(normalized) != len(keywords):
        raise ValueError("Keywords must not be empty.")
    if len(set(normalized)) != len(normalized):
        raise ValueError("Keywords must be unique.")
    return normalized


def _search_console_context(
    payload: dict[str, Any],
) -> tuple[SeoProjectContext, dict[str, SearchConsoleKeywordMetric]]:
    project = payload.get("project") if isinstance(payload.get("project"), dict) else {}
    gsc = payload.get("gsc") if isinstance(payload.get("gsc"), dict) else {}
    project_id = str(project.get("id") or "").strip()
    if not project_id:
        raise ValueError("DigestSEO context response did not include a project.")

    property_data = gsc.get("property") if isinstance(gsc.get("property"), dict) else {}
    window = gsc.get("window") if isinstance(gsc.get("window"), dict) else {}
    context = SeoProjectContext(
        project_id=project_id,
        project_name=str(project.get("name") or ""),
        origin=str(project.get("origin") or ""),
        search_console_available=bool(gsc.get("available")),
        reason=str(gsc.get("reason")) if gsc.get("reason") else None,
        retryable=bool(gsc.get("retryable")),
        message=str(gsc.get("message")) if gsc.get("message") else None,
        property_url=str(property_data.get("siteUrl")) if property_data.get("siteUrl") else None,
        permission_level=(
            str(property_data.get("permissionLevel"))
            if property_data.get("permissionLevel")
            else None
        ),
        start_date=str(window.get("startDate")) if window.get("startDate") else None,
        end_date=str(window.get("endDate")) if window.get("endDate") else None,
        days=int(window["days"]) if isinstance(window.get("days"), int) else None,
    )

    metrics_by_keyword: dict[str, SearchConsoleKeywordMetric] = {}
    for item in gsc.get("metrics") if isinstance(gsc.get("metrics"), list) else []:
        if not isinstance(item, dict):
            continue
        keyword = str(item.get("keyword") or "").strip()
        if not keyword:
            continue
        metrics_by_keyword[keyword] = SearchConsoleKeywordMetric(
            clicks=_as_float(item.get("clicks")) or 0.0,
            impressions=_as_float(item.get("impressions")) or 0.0,
            ctr=_as_float(item.get("ctr")) or 0.0,
            position=_as_float(item.get("position")),
            has_data=bool(item.get("hasData")),
        )
    return context, metrics_by_keyword


def _seo_limitations(project_context: SeoProjectContext | None) -> list[str]:
    limitations = ["Candidates are trend signals, not absolute keyword-volume estimates."]
    if project_context is None:
        limitations.append(
            "No site-specific Search Console position, click, impression, or conversion data was requested."
        )
    elif project_context.search_console_available:
        limitations.extend(
            [
                "Search Console metrics are exact-query finalized historical site performance, not search volume or conversion forecasts.",
                "Zero exact-query impressions mean no Search Console data was observed in the returned window, not zero market demand.",
            ]
        )
    else:
        limitations.append(
            "Search Console context was unavailable for this project, so the candidates remain trend-only signals."
        )
    return limitations


@hosted_mcp.tool(
    description=(
        "Discover broad, currently trending search topics in a geographic market. Use this when the user has no specific seed keyword yet and wants emerging topics ranked by growth or volume."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    timeout=60,
)
async def discover_trends(
    geo: Annotated[str, Field(description="Geographic market, typically an ISO country code such as US, GB, or DE.")] = "US",
    sort_by: Annotated[DiscoverySort, Field(description="Rank by recent growth or current trend volume.")] = "growth",
    limit: Annotated[int, Field(description="Maximum trends to return.", ge=1, le=20)] = 10,
) -> DiscoverTrendsResult:
    providers = get_provider_set()
    sort = "wow_pct_change" if sort_by == "growth" else "volume"
    rows = await providers.trends.get_ranked_trends(
        source="google search",
        sort=sort,
        limit=limit,
        geo=geo,
    )

    trends: list[DiscoveredTrend] = []
    for row in rows[:limit]:
        context_articles = [
            TrendNewsSnippet(
                title=str(article.get("title", "")),
                url=str(article.get("url", "")),
                source=str(article["source"]) if article.get("source") else None,
                time=article.get("time"),
                snippet=str(article["snippet"]) if article.get("snippet") else None,
            )
            for article in (row.get("news") or [])[:3]
        ]
        trends.append(
            DiscoveredTrend(
                keyword=str(row.get("keyword", "")),
                volume=row.get("volume"),
                growth_pct=_as_float(row.get("growth_pct")),
                started=row.get("started") if isinstance(row.get("started"), int) else None,
                context_articles=context_articles,
            )
        )

    return DiscoverTrendsResult(
        provider=providers.trends.provider_id,
        geo=geo,
        sorted_by=sort_by,
        trends=trends,
    )


@hosted_mcp.tool(
    description=(
        "Analyze one known keyword's Google Trends trajectory. Use this for direction, recent/average/peak normalized interest, growth windows, and a bounded time series; do not use it to compare multiple keywords."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    timeout=60,
)
async def analyze_keyword_trend(
    keyword: Annotated[str, Field(description="Single keyword or topic phrase to analyze.", min_length=1, max_length=200)],
    geo: Annotated[str, Field(description="Geographic market such as US or GB.")] = "US",
    source: Annotated[TrendSource, Field(description="Google Trends search property.")] = "google search",
    timeframe: Annotated[str, Field(description="Google Trends window such as 'today 12-m', 'today 90-d', 'today 5-y', or an exact date range.")] = "today 12-m",
    max_points: Annotated[int, Field(description="Maximum time-series points returned after deterministic downsampling.", ge=10, le=120)] = 60,
) -> KeywordTrendAnalysis:
    keyword = keyword.strip()
    providers = get_provider_set()
    points = await providers.trends.get_trends(
        keyword=keyword,
        source=source,
        geo=geo,
        timeframe=timeframe,
    )
    growth_rows = await providers.trends.get_growth(
        keyword=keyword,
        source=source,
        percent_growth=["3M", "1Y"],
        geo=geo,
    )
    growth = _growth_by_keyword(growth_rows).get(keyword, {})

    return KeywordTrendAnalysis(
        provider=providers.trends.provider_id,
        keyword=keyword,
        geo=geo,
        source=source,
        timeframe=timeframe,
        metrics=_interest_metrics(points),
        growth=growth,
        series=_bounded_series(points, max_points),
    )


@hosted_mcp.tool(
    description=(
        "Compare 2-5 known keywords on the same Google Trends scale and window. Use this when relative momentum between alternatives matters; use analyze_keyword_trend for only one keyword."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    timeout=60,
)
async def compare_keyword_trends(
    keywords: Annotated[list[str], Field(description="Two to five unique keywords to compare on one normalized Trends request.", min_length=2, max_length=5)],
    geo: Annotated[str, Field(description="Geographic market such as US or GB.")] = "US",
    source: Annotated[TrendSource, Field(description="Google Trends search property.")] = "google search",
    timeframe: Annotated[str, Field(description="Google Trends window shared by all keywords.")] = "today 12-m",
    max_points_per_keyword: Annotated[int, Field(description="Maximum returned points for each keyword.", ge=10, le=80)] = 40,
) -> CompareKeywordTrendsResult:
    keywords = _normalize_keywords(keywords)
    providers = get_provider_set()
    points = await providers.trends.get_trends(
        keyword=keywords,
        source=source,
        geo=geo,
        timeframe=timeframe,
    )
    growth_rows = await providers.trends.get_growth(
        keyword=keywords,
        source=source,
        percent_growth=["3M", "1Y"],
        geo=geo,
    )
    grouped = _series_by_keyword(points)
    growth = _growth_by_keyword(growth_rows)

    comparisons = [
        KeywordComparison(
            keyword=keyword,
            metrics=_interest_metrics(grouped.get(keyword, [])),
            growth=growth.get(keyword, {}),
            series=_bounded_series(grouped.get(keyword, []), max_points_per_keyword),
        )
        for keyword in keywords
    ]
    return CompareKeywordTrendsResult(
        provider=providers.trends.provider_id,
        geo=geo,
        source=source,
        timeframe=timeframe,
        comparisons=comparisons,
    )


@hosted_mcp.tool(
    description=(
        "Expand one seed keyword into related search demand. Use this for top/rising queries, related topics, and entity suggestions; it does not return a time-series analysis."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    timeout=60,
)
async def discover_related_demand(
    keyword: Annotated[str, Field(description="Seed keyword or topic phrase.", min_length=1, max_length=200)],
    geo: Annotated[str, Field(description="Geographic market such as US or GB.")] = "US",
    source: Annotated[TrendSource, Field(description="Google Trends search property used for related-demand data.")] = "google search",
    timeframe: Annotated[str, Field(description="Google Trends window such as 'today 12-m'.")] = "today 12-m",
    limit: Annotated[int, Field(description="Maximum items returned in each related-demand section.", ge=1, le=15)] = 10,
) -> RelatedDemandResult:
    keyword = keyword.strip()
    providers = get_provider_set()
    gprop = _SOURCE_TO_GPROP[source]
    queries = await providers.trends.get_related_queries(
        keyword=keyword,
        timeframe=timeframe,
        geo=geo,
        gprop=gprop,
    )
    topics = await providers.trends.get_related_topics(
        keyword=keyword,
        timeframe=timeframe,
        geo=geo,
        gprop=gprop,
    )
    suggestions = await providers.trends.get_suggestions(keyword=keyword)

    return RelatedDemandResult(
        provider=providers.trends.provider_id,
        keyword=keyword,
        geo=geo,
        source=source,
        timeframe=timeframe,
        top_queries=[RelatedQuery(**item) for item in (queries.get("top") or [])[:limit]],
        rising_queries=[RelatedQuery(**item) for item in (queries.get("rising") or [])[:limit]],
        top_topics=[RelatedTopic(**item) for item in (topics.get("top") or [])[:limit]],
        rising_topics=[RelatedTopic(**item) for item in (topics.get("rising") or [])[:limit]],
        suggestions=[DemandSuggestion(**item) for item in suggestions[:limit]],
    )


@hosted_mcp.tool(
    description=(
        "Add current-news context to one keyword and return a compact recent trend snapshot. Use this when the user asks why a term may be moving now or wants sources to investigate; use analyze_keyword_trend for trend metrics without news."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    timeout=75,
)
async def get_trend_context(
    keyword: Annotated[str, Field(description="Keyword or topic to contextualize.", min_length=1, max_length=200)],
    geo: Annotated[str, Field(description="Geographic market for the trend snapshot.")] = "US",
    news_period_days: Annotated[int, Field(description="How many recent days of news to inspect.", ge=1, le=30)] = 7,
    max_articles: Annotated[int, Field(description="Maximum article links returned.", ge=1, le=8)] = 5,
) -> TrendContextResult:
    keyword = keyword.strip()
    providers = get_provider_set()
    points = await providers.trends.get_trends(
        keyword=keyword,
        source="google search",
        geo=geo,
        timeframe="today 90-d",
    )
    articles = await providers.news.get_news_by_keyword(
        keyword=keyword,
        period=news_period_days,
        max_results=max_articles,
        nlp=False,
    )
    context_articles = [
        item
        for article in articles[:max_articles]
        if (item := _context_article(article)) is not None
    ]
    return TrendContextResult(
        trends_provider=providers.trends.provider_id,
        news_provider=providers.news.provider_id,
        keyword=keyword,
        geo=geo,
        timeframe="today 90-d",
        metrics=_interest_metrics(points),
        recent_articles=context_articles,
    )


@hosted_mcp.tool(
    description=(
        "Find trend-driven SEO keyword candidates from one seed. Use this for rising related queries that are checked against current Google Trends interest. If project_id is supplied, annotate candidates with exact-query Search Console metrics for that authenticated DigestSEO project; without it results remain trend-only. Do not treat either signal as absolute search volume."
    ),
    annotations=READ_ONLY_ANNOTATIONS,
    timeout=75,
)
async def find_seo_opportunities(
    seed_keyword: Annotated[str, Field(description="Seed keyword defining the SEO topic space.", min_length=1, max_length=200)],
    geo: Annotated[str, Field(description="Geographic market such as US or GB.")] = "US",
    source: Annotated[TrendSource, Field(description="Google Trends search property.")] = "google search",
    timeframe: Annotated[str, Field(description="Window used for related demand and trend validation.")] = "today 12-m",
    limit: Annotated[int, Field(description="Maximum validated opportunity candidates. Google Trends comparisons are capped at five keywords.", ge=1, le=5)] = 5,
    project_id: Annotated[
        str | None,
        Field(
            description="Optional DigestSEO Site Audit project ID owned by the authenticated account. Enables a 28-day exact-query Search Console validation pass.",
            min_length=1,
            max_length=128,
            pattern=r"^[A-Za-z0-9_-]+$",
        ),
    ] = None,
) -> SeoOpportunityResult:
    seed_keyword = seed_keyword.strip()
    providers = get_provider_set()
    related = await providers.trends.get_related_queries(
        keyword=seed_keyword,
        timeframe=timeframe,
        geo=geo,
        gprop=_SOURCE_TO_GPROP[source],
    )

    candidate_rows: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for signal_type, rows in (
        ("rising_related_query", related.get("rising") or []),
        ("top_related_query", related.get("top") or []),
    ):
        for row in rows:
            query = str(row.get("query", "")).strip()
            if not query or query in seen or query == seed_keyword:
                continue
            seen.add(query)
            candidate_rows.append((signal_type, row))
            if len(candidate_rows) == limit:
                break
        if len(candidate_rows) == limit:
            break

    candidate_keywords = [str(row.get("query", "")) for _, row in candidate_rows]
    trend_rows = (
        await providers.trends.get_trends(
            keyword=candidate_keywords,
            source=source,
            geo=geo,
            timeframe=timeframe,
        )
        if candidate_keywords
        else []
    )
    grouped = _series_by_keyword(trend_rows)

    candidates: list[SeoOpportunityCandidate] = []
    for signal_type, row in candidate_rows:
        keyword = str(row.get("query", ""))
        metrics = _interest_metrics(grouped.get(keyword, []))
        candidates.append(
            SeoOpportunityCandidate(
                keyword=keyword,
                signal_type=signal_type,
                related_signal=float(row.get("value", 0.0)),
                latest_interest=metrics.latest,
                average_interest=metrics.average,
                peak_interest=metrics.peak,
            )
        )

    project_context: SeoProjectContext | None = None
    if project_id is not None:
        context_payload = await fetch_digestseo_project_context(
            project_id=project_id,
            keywords=candidate_keywords,
            days=28,
        )
        project_context, search_console_by_keyword = _search_console_context(context_payload)
        for candidate in candidates:
            candidate.search_console = search_console_by_keyword.get(candidate.keyword)

    return SeoOpportunityResult(
        provider=providers.trends.provider_id,
        seed_keyword=seed_keyword,
        geo=geo,
        source=source,
        timeframe=timeframe,
        candidates=candidates,
        project_context=project_context,
        limitations=_seo_limitations(project_context),
    )
