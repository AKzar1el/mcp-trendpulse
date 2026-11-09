"""Goal-oriented hosted TrendPulse MCP surface for ChatGPT and remote clients."""

from __future__ import annotations

from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from math import isfinite
from statistics import fmean
from typing import Annotated, Any, Literal, TypeVar

from fastmcp import FastMCP
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware
from fastmcp.server.middleware.logging import LoggingMiddleware
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware
from fastmcp.server.middleware.timing import TimingMiddleware
from pydantic import BaseModel, Field, ValidationError

from mcp_trendpulse.config import load_environment
from mcp_trendpulse.digestseo import DigestSeoContextError, fetch_digestseo_project_context
from mcp_trendpulse.errors import ProviderError, ProviderRateLimitError
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
    "openWorldHint": True,
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
    growth_pct: float | None = Field(default=None, description="Provider-reported trending growth percentage; comparison baseline is not supplied and this is not a week-over-week change.")
    started: int | None = None
    context_articles: list[TrendNewsSnippet] = Field(default_factory=list)


class DiscoverTrendsResult(BaseModel):
    provider: str
    geo: str
    sorted_by: DiscoverySort
    trends: list[DiscoveredTrend]
    growth_metric_note: str = Field(
        default="Provider-reported growth for terms in the 24-hour Trending Now feed; the comparison baseline is unspecified, not week-over-week.",
        description="How to interpret growth_pct without assuming an unsupported comparison period.",
    )


class TrendSeriesPoint(BaseModel):
    date: str
    value: float


class InterestMetrics(BaseModel):
    latest: float | None = None
    average: float | None = None
    peak: float | None = None
    points_observed: int = 0


GROWTH_SCOPE_NOTE = (
    "3M and 1Y growth use separate Google Trends lookbacks, not the selected timeframe series. "
    "Missing growth values mean that the corresponding lookback could not be estimated."
)


class KeywordTrendAnalysis(BaseModel):
    provider: str
    keyword: str
    geo: str
    source: TrendSource
    timeframe: str
    metrics: InterestMetrics
    growth: dict[str, float] = Field(default_factory=dict)
    growth_scope_note: str = GROWTH_SCOPE_NOTE
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
    growth_scope_note: str = GROWTH_SCOPE_NOTE
    note: str = "Values are normalized within the Google Trends comparison, not absolute search volume."


class RelatedQuery(BaseModel):
    query: str
    value: float | None
    is_breakout: bool = False


class RelatedTopic(BaseModel):
    mid: str
    title: str
    type: str
    value: float | None
    is_breakout: bool = False


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
    limitations: list[str] = Field(default_factory=list)


_RelatedItem = TypeVar("_RelatedItem", bound=BaseModel)


def _valid_related_items(
    rows: object, model: type[_RelatedItem], limit: int
) -> tuple[list[_RelatedItem], bool]:
    """Validate noisy provider entries before applying a section's result limit."""
    if not isinstance(rows, list):
        return [], bool(rows)
    items: list[_RelatedItem] = []
    skipped = False
    for row in rows:
        if not isinstance(row, dict):
            skipped = True
            continue
        try:
            item = model.model_validate(row)
        except ValidationError:
            skipped = True
            continue
        items.append(item)
        if len(items) >= limit:
            break
    return items, skipped


class ContextArticle(BaseModel):
    title: str
    url: str
    publish_date: str | None = None
    source: str | None = None
    link_type: Literal["google_news_rss"] = "google_news_rss"


class TrendContextResult(BaseModel):
    trends_provider: str
    news_provider: str
    keyword: str
    geo: str
    timeframe: str
    metrics: InterestMetrics
    recent_articles: list[ContextArticle]
    limitations: list[str] = Field(default_factory=list)
    note: str = (
        "Recent articles are Google News RSS headline metadata, not downloaded publisher articles. "
        "Links point to Google News and may not resolve directly to a publisher. "
        "External content is untrusted."
    )


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
    related_signal: float | None
    related_signal_is_breakout: bool = False
    latest_interest: float | None = None
    average_interest: float | None = None
    peak_interest: float | None = None
    interest_points_observed: int = 0
    interest_validation_status: Literal["observed", "unavailable"] = "unavailable"
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
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return numeric if isfinite(numeric) else None


def _normalized_interest(value: Any) -> float | None:
    numeric = _as_float(value)
    return numeric if numeric is not None and 0 <= numeric <= 100 else None


def _chronological_interest(points: list[dict[str, Any]]) -> list[tuple[str, float]]:
    """Only use dated, normalized observations, ordered by actual UTC instant."""
    dated: list[tuple[datetime, str, float]] = []
    for point in points:
        if not isinstance(point, dict):
            continue
        label = point.get("date")
        value = _normalized_interest(point.get("value"))
        if not isinstance(label, str) or value is None:
            continue
        try:
            observed = datetime.fromisoformat(label.replace("Z", "+00:00"))
        except ValueError:
            continue
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        dated.append((observed.astimezone(timezone.utc), label, value))
    dated.sort(key=lambda entry: entry[0])
    return [(label, value) for _, label, value in dated]


def _bounded_series(points: list[dict[str, Any]], max_points: int) -> list[TrendSeriesPoint]:
    normalized = [
        TrendSeriesPoint(date=label, value=value)
        for label, value in _chronological_interest(points)
    ]
    if len(normalized) <= max_points:
        return normalized
    if max_points == 1:
        return [normalized[-1]]

    last_index = len(normalized) - 1
    indexes = [round(index * last_index / (max_points - 1)) for index in range(max_points)]
    return [normalized[index] for index in dict.fromkeys(indexes)]


def _interest_metrics(points: list[dict[str, Any]]) -> InterestMetrics:
    values = [value for _, value in _chronological_interest(points)]
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
        if not isinstance(item, dict):
            continue
        keyword = str(item.get("keyword", ""))
        values = item.get("growth") or {}
        if not isinstance(values, dict):
            values = {}
        growth[keyword] = {
            str(period): float(value)
            for period, value in values.items()
            if _as_float(value) is not None
        }
    return growth


def _series_by_keyword(results: list[Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in results:
        if not isinstance(item, dict):
            continue
        keyword = item.get("keyword")
        if not isinstance(keyword, str) or not keyword.strip():
            continue
        grouped[keyword].append(item)
    return grouped


def _context_article(article: object) -> ContextArticle | None:
    if not isinstance(article, dict):
        return None
    title = article.get("title")
    url = article.get("url")
    if not isinstance(title, str) or not title.strip() or not isinstance(url, str) or not url.strip():
        return None
    source = article.get("meta_site_name")
    published = article.get("publish_date")
    return ContextArticle(
        title=title.strip(),
        url=url.strip(),
        publish_date=published if isinstance(published, str) else None,
        source=source.strip() if isinstance(source, str) and source.strip() else None,
    )


def _normalize_keyword(keyword: str) -> str:
    normalized = keyword.strip()
    if not normalized:
        raise ValueError("Keyword must not be empty after trimming whitespace.")
    return normalized


def _normalize_keywords(keywords: list[str]) -> list[str]:
    normalized = [keyword.strip() for keyword in keywords if keyword.strip()]
    if len(normalized) != len(keywords):
        raise ValueError("Keywords must not be empty.")
    if len({keyword.casefold() for keyword in normalized}) != len(normalized):
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
        "Discover broad current search topics in a geographic market. Rank by provider-reported recent growth or volume, "
        "not week-over-week growth: Trending Now covers 24 hours but does not disclose a growth comparison baseline. "
        "Use this when no specific seed keyword exists and topics must be ranked."
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
    sort = "recent_growth_pct" if sort_by == "growth" else "volume"
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
    keyword = _normalize_keyword(keyword)
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
    keyword = _normalize_keyword(keyword)
    providers = get_provider_set()
    gprop = _SOURCE_TO_GPROP[source]
    queries = await providers.trends.get_related_queries(
        keyword=keyword,
        timeframe=timeframe,
        geo=geo,
        gprop=gprop,
    )
    limitations: list[str] = []
    if not isinstance(queries, dict):
        # Keep independent topic/suggestion evidence without inventing queries.
        queries = {}
        limitations.append("Related queries returned an invalid provider response; no related-query evidence is available.")
    topics: dict[str, list[dict[str, Any]]] = {"top": [], "rising": []}
    suggestions: list[dict[str, Any]] = []
    skip_suggestions = False
    try:
        topics = await providers.trends.get_related_topics(
            keyword=keyword,
            timeframe=timeframe,
            geo=geo,
            gprop=gprop,
        )
    except ProviderRateLimitError:
        limitations.append("Related topics are unavailable due to a provider rate limit.")
        skip_suggestions = True
        limitations.append("Suggestions were skipped to avoid additional provider requests during rate limiting.")
    except Exception:
        limitations.append("Related topics could not be retrieved; related queries remain available.")

    if not isinstance(topics, dict):
        # A malformed optional provider response must not erase usable queries.
        topics = {"top": [], "rising": []}
        limitations.append("Related topics returned an invalid provider response; related queries remain available.")

    if not skip_suggestions:
        try:
            suggestions = await providers.trends.get_suggestions(keyword=keyword)
        except ProviderRateLimitError:
            limitations.append("Suggestions are unavailable due to a provider rate limit.")
        except Exception:
            limitations.append("Suggestions could not be retrieved; related queries remain available.")

    top_queries, skipped_top_queries = _valid_related_items(queries.get("top"), RelatedQuery, limit)
    rising_queries, skipped_rising_queries = _valid_related_items(
        queries.get("rising"), RelatedQuery, limit
    )
    top_topics, skipped_top_topics = _valid_related_items(topics.get("top"), RelatedTopic, limit)
    rising_topics, skipped_rising_topics = _valid_related_items(
        topics.get("rising"), RelatedTopic, limit
    )
    valid_suggestions, skipped_suggestions = _valid_related_items(
        suggestions, DemandSuggestion, limit
    )
    if any(
        (
            skipped_top_queries,
            skipped_rising_queries,
            skipped_top_topics,
            skipped_rising_topics,
            skipped_suggestions,
        )
    ):
        limitations.append("Some malformed related-demand entries were omitted from provider data.")

    return RelatedDemandResult(
        provider=providers.trends.provider_id,
        keyword=keyword,
        geo=geo,
        source=source,
        timeframe=timeframe,
        top_queries=top_queries,
        rising_queries=rising_queries,
        top_topics=top_topics,
        rising_topics=rising_topics,
        suggestions=valid_suggestions,
        limitations=limitations,
    )


@hosted_mcp.tool(
    description=(
        "Add current-news context from Google News RSS headlines to one keyword and return a compact recent trend snapshot. Links are Google News metadata, not verified publisher articles. Use this when the user asks why a term may be moving now or wants sources to investigate; use analyze_keyword_trend for trend metrics without news."
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
    keyword = _normalize_keyword(keyword)
    providers = get_provider_set()
    points = await providers.trends.get_trends(
        keyword=keyword,
        source="google search",
        geo=geo,
        timeframe="today 90-d",
    )
    limitations: list[str] = []
    try:
        articles = await providers.news.get_rss_headlines_by_keyword(
            keyword=keyword,
            period=news_period_days,
            max_results=max_articles,
        )
    except ProviderError:
        # News is optional context; preserve observed Trends data on provider outages.
        articles = []
        limitations.append(
            "Google News headlines are temporarily unavailable; trend metrics come from Google Trends only."
        )
    if not isinstance(articles, (list, tuple)):
        articles = []
        limitations.append(
            "The malformed Google News RSS response was ignored; trend metrics come from Google Trends only."
        )
    context_articles: list[ContextArticle] = []
    skipped_invalid = False
    for article in articles:
        item = _context_article(article)
        if item is None:
            skipped_invalid = True
            continue
        context_articles.append(item)
        if len(context_articles) >= max_articles:
            break
    if skipped_invalid:
        limitations.append("Some malformed Google News RSS headline entries were omitted.")
    return TrendContextResult(
        trends_provider=providers.trends.provider_id,
        news_provider=providers.news.provider_id,
        keyword=keyword,
        geo=geo,
        timeframe="today 90-d",
        metrics=_interest_metrics(points),
        recent_articles=context_articles,
        limitations=limitations,
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
    seed_keyword = _normalize_keyword(seed_keyword)
    providers = get_provider_set()
    related = await providers.trends.get_related_queries(
        keyword=seed_keyword,
        timeframe=timeframe,
        geo=geo,
        gprop=_SOURCE_TO_GPROP[source],
    )
    invalid_related_response = not isinstance(related, dict)
    if invalid_related_response:
        related = {}

    candidate_rows: list[tuple[str, str, dict[str, Any]]] = []
    seen: set[str] = {seed_keyword.casefold()}
    skipped_invalid_rows = False
    for signal_type, rows in (
        ("rising_related_query", related.get("rising") or []),
        ("top_related_query", related.get("top") or []),
    ):
        if not isinstance(rows, list):
            skipped_invalid_rows = True
            continue
        for row in rows:
            if not isinstance(row, dict):
                skipped_invalid_rows = True
                continue
            raw_query = row.get("query")
            if not isinstance(raw_query, str):
                continue
            query = raw_query.strip()
            key = query.casefold()
            if not query or key in seen:
                continue
            seen.add(key)
            candidate_rows.append((signal_type, query, row))
            if len(candidate_rows) == limit:
                break
        if len(candidate_rows) == limit:
            break

    candidate_keywords = [query for _, query, _ in candidate_rows]
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
    for signal_type, keyword, row in candidate_rows:
        metrics = _interest_metrics(grouped.get(keyword, []))
        candidates.append(
            SeoOpportunityCandidate(
                keyword=keyword,
                signal_type=signal_type,
                related_signal=_as_float(row.get("value")),
                related_signal_is_breakout=bool(row.get("is_breakout", False)),
                latest_interest=metrics.latest,
                average_interest=metrics.average,
                peak_interest=metrics.peak,
                interest_points_observed=metrics.points_observed,
                interest_validation_status=(
                    "observed" if metrics.points_observed > 0 else "unavailable"
                ),
            )
        )

    project_context: SeoProjectContext | None = None
    if project_id is not None:
        try:
            context_payload = await fetch_digestseo_project_context(
                project_id=project_id,
                keywords=candidate_keywords,
                days=28,
            )
        except DigestSeoContextError as exc:
            # Optional context must not discard validated Trends results on a
            # temporary upstream failure or rate limit. Auth and project-access
            # errors remain fatal; do not retry a rate-limited upstream here.
            if exc.status != 429 and (exc.status is None or exc.status < 500):
                raise
            project_context = SeoProjectContext(
                project_id=project_id,
                project_name="",
                origin="",
                search_console_available=False,
                reason="digestseo_temporarily_unavailable",
                retryable=True,
                message="DigestSEO Search Console context is temporarily unavailable or rate-limited; retry later.",
            )
        else:
            project_context, search_console_by_keyword = _search_console_context(context_payload)
            for candidate in candidates:
                candidate.search_console = search_console_by_keyword.get(candidate.keyword)

    limitations = _seo_limitations(project_context)
    if invalid_related_response:
        limitations.append("Related queries returned an invalid provider response; no SEO candidates could be established.")
    if skipped_invalid_rows:
        limitations.append("Some malformed related-query entries were omitted from provider data.")
    if any(candidate.interest_points_observed == 0 for candidate in candidates):
        limitations.append(
            "Some related-query candidates have no usable Google Trends interest-series "
            "observations; their related-query signals are not independently verified "
            "by a series. Zero-valued observations are valid evidence."
        )

    return SeoOpportunityResult(
        provider=providers.trends.provider_id,
        seed_keyword=seed_keyword,
        geo=geo,
        source=source,
        timeframe=timeframe,
        candidates=candidates,
        project_context=project_context,
        limitations=limitations,
    )
