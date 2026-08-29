from typing import Annotated, Optional, Any, TYPE_CHECKING
from fastmcp import FastMCP, Context
from fastmcp.server.dependencies import get_http_request
from fastmcp.server.middleware.timing import TimingMiddleware
from fastmcp.server.middleware.logging import LoggingMiddleware
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware
from pydantic import BaseModel, Field, model_serializer
from mcp_trendpulse.config import load_environment
from mcp_trendpulse.news import BrowserManager
from mcp_trendpulse.middleware import ProviderErrorMiddleware
from mcp_trendpulse.providers import get_provider_set
from newspaper import settings as newspaper_settings
from newspaper.article import Article
from contextlib import asynccontextmanager


class BaseModelClean(BaseModel):
    @model_serializer
    def serializer(self, **kwargs) -> dict[str, Any]:
        return {
            field: getattr(self, field)
            for field in self.model_fields_set
            if getattr(self, field, None) is not None
        }

    if TYPE_CHECKING:

        def model_dump(self, **kwargs) -> dict[str, Any]: ...


class ArticleOut(BaseModelClean):
    title: Annotated[str, Field(description="Title of the article.")]
    url: Annotated[str, Field(description="Original article URL.")]
    read_more_link: Annotated[Optional[str], Field(description="Link to read more about the article.")] = None
    language: Annotated[Optional[str], Field(description="Language code of the article.")] = None
    meta_img: Annotated[Optional[str], Field(description="Meta image URL.")] = None
    movies: Annotated[Optional[list[str]], Field(description="List of movie URLs or IDs.")] = None
    meta_favicon: Annotated[Optional[str], Field(description="Favicon URL from meta data.")] = None
    meta_site_name: Annotated[Optional[str], Field(description="Site name from meta data.")] = None
    authors: Annotated[Optional[list[str]], Field(description="list of authors.")] = None
    publish_date: Annotated[Optional[str], Field(description="Publish date in ISO format.")] = None
    top_image: Annotated[Optional[str], Field(description="URL of the top image.")] = None
    images: Annotated[Optional[list[str]], Field(description="list of image URLs.")] = None
    text: Annotated[Optional[str], Field(description="Full text of the article.")] = None
    summary: Annotated[Optional[str], Field(description="Summary of the article.")] = None
    keywords: Annotated[Optional[list[str]], Field(description="Extracted keywords.")] = None
    tags: Annotated[Optional[list[str]], Field(description="Tags for the article.")] = None
    meta_keywords: Annotated[Optional[list[str]], Field(description="Meta keywords from the article.")] = None
    meta_description: Annotated[Optional[str], Field(description="Meta description from the article.")] = None
    canonical_link: Annotated[Optional[str], Field(description="Canonical link for the article.")] = None
    meta_data: Annotated[Optional[dict[str, str | int]], Field(description="Meta data dictionary.")] = None
    meta_lang: Annotated[Optional[str], Field(description="Language of the article.")] = None
    source_url: Annotated[Optional[str], Field(description="Source URL if different from original.")] = None


class TrendingTermArticleOut(BaseModelClean):
    title: Annotated[str, Field(description="Article title.")] = ""
    url: Annotated[str, Field(description="Article URL.")] = ""
    source: Annotated[Optional[str], Field(description="News source name.")] = None
    picture: Annotated[Optional[str], Field(description="URL to article image.")] = None
    time: Annotated[Optional[str | int], Field(description="Publication time or timestamp.")] = None
    snippet: Annotated[Optional[str], Field(description="Article preview text.")] = None


class TrendingTermOut(BaseModelClean):
    keyword: Annotated[str, Field(description="Trending keyword.")]
    volume: Annotated[Optional[str], Field(description="Search volume.")] = None
    trend_keywords: Annotated[Optional[list[str]], Field(description="Related keywords.")] = None
    link: Annotated[Optional[str], Field(description="URL to more information.")] = None
    started: Annotated[Optional[int], Field(description="Unix timestamp when the trend started.")] = None
    picture: Annotated[Optional[str], Field(description="URL to related image.")] = None
    picture_source: Annotated[Optional[str], Field(description="Source of the picture.")] = None
    news: Annotated[
        Optional[list[TrendingTermArticleOut]],
        Field(description="Related news articles."),
    ] = None


class TrendPoint(BaseModelClean):
    date: Annotated[str, Field(description="ISO date string (YYYY-MM-DD) of the trend data point.")]
    value: Annotated[float, Field(description="Search interest score (0-100).")]
    keyword: Annotated[str, Field(description="The keyword for this data point.")]


class KeywordGrowthOut(BaseModelClean):
    keyword: Annotated[str, Field(description="The keyword being analyzed.")]
    growth: Annotated[dict[str, float], Field(description="A dictionary mapping the growth period (e.g. '3M', '1Y') to the growth percentage.")]


class RankedTrendOut(BaseModelClean):
    keyword: Annotated[str, Field(description="The trending keyword.")]
    volume: Annotated[Optional[int], Field(description="Search volume count.")] = None
    growth_pct: Annotated[Optional[float], Field(description="Percentage growth in volume.")] = None
    started: Annotated[Optional[int], Field(description="Unix timestamp when trend started.")] = None
    news: Annotated[Optional[list[TrendingTermArticleOut]], Field(description="Related news articles.")] = None


class TopTrendOut(BaseModelClean):
    keyword: Annotated[str, Field(description="The trending keyword.")]
    volume: Annotated[Optional[str], Field(description="Approximate search volume.")] = None
    link: Annotated[Optional[str], Field(description="URL to more information.")] = None
    started: Annotated[Optional[int], Field(description="Unix timestamp when trend started.")] = None
    picture: Annotated[Optional[str], Field(description="URL to related image.")] = None
    news: Annotated[Optional[list[TrendingTermArticleOut]], Field(description="Related news articles.")] = None


class RegionInterestOut(BaseModelClean):
    geo_name: Annotated[str, Field(description="Name of the geographic region.")]
    geo_code: Annotated[str, Field(description="ISO code of the region.")]
    values: Annotated[dict[str, float], Field(description="Search interest score (0-100) per keyword.")]


class RelatedQueryItem(BaseModelClean):
    query: Annotated[str, Field(description="The related search term.")]
    value: Annotated[float, Field(description="Relative search value (0-100) or growth percentage.")]


class RelatedQueriesOut(BaseModelClean):
    top: Annotated[list[RelatedQueryItem], Field(description="Top related queries.")]
    rising: Annotated[list[RelatedQueryItem], Field(description="Rising related queries.")]


class RelatedTopicItem(BaseModelClean):
    mid: Annotated[str, Field(description="Google Trends topic entity ID (e.g. /m/05z1_).")]
    title: Annotated[str, Field(description="Display title of the topic.")]
    type: Annotated[str, Field(description="Type of the topic entity.")]
    value: Annotated[float, Field(description="Relative search value (0-100) or growth percentage.")]


class RelatedTopicsOut(BaseModelClean):
    top: Annotated[list[RelatedTopicItem], Field(description="Top related topics.")]
    rising: Annotated[list[RelatedTopicItem], Field(description="Rising related topics.")]


class SuggestionItem(BaseModelClean):
    mid: Annotated[str, Field(description="Google Trends topic entity ID (e.g. /m/05z1_).")]
    title: Annotated[str, Field(description="Display title of the entity.")]
    type: Annotated[str, Field(description="Type of the entity.")]


class CategoryItem(BaseModelClean):
    id: Annotated[int, Field(description="Category ID to be used in queries.")]
    name: Annotated[str, Field(description="Display name of the category.")]


@asynccontextmanager
async def lifespan(app: FastMCP):
    load_environment()
    async with BrowserManager():
        yield


mcp = FastMCP(
    name="mcp-trendpulse",
    instructions="This server provides tools to search, analyze, and summarize Google News articles and Google Trends",
    lifespan=lifespan,
    on_duplicate="replace",
)

mcp.add_middleware(ProviderErrorMiddleware())
mcp.add_middleware(ErrorHandlingMiddleware())  # Handle errors first
mcp.add_middleware(RateLimitingMiddleware(max_requests_per_second=50))
mcp.add_middleware(TimingMiddleware())  # Time actual execution
mcp.add_middleware(LoggingMiddleware())  # Log everything

READ_ONLY_OPEN_WORLD_ANNOTATIONS = {
    "readOnlyHint": True,
    "openWorldHint": True,
    "destructiveHint": False,
}


def set_newspaper_article_fields(full_data: bool = False):
    if full_data:
        newspaper_settings.article_json_fields = [
            "url",
            "read_more_link",
            "language",
            "title",
            "top_image",
            "meta_img",
            "images",
            "movies",
            "keywords",
            "keyword_scores",
            "meta_keywords",
            "tags",
            "authors",
            "publish_date",
            "summary",
            "meta_description",
            "meta_lang",
            "meta_favicon",
            "meta_site_name",
            "canonical_link",
            "text",
        ]
    else:
        newspaper_settings.article_json_fields = [
            "url",
            "title",
            "publish_date",
            "summary",
        ]


def is_session_active(ctx: Context) -> bool:
    try:
        return ctx.request_context is not None and ctx.session is not None
    except Exception:
        return False


def can_use_llm_sampling(ctx: Context) -> bool:
    """Allow sampling locally while disabling it for the stateless hosted app."""
    if not is_session_active(ctx):
        return False
    if getattr(ctx, "transport", "stdio") != "streamable-http":
        return True
    try:
        request = get_http_request()
    except RuntimeError:
        return False
    return bool(getattr(request.app.state, "trendpulse_sampling_enabled", True))


async def llm_summarize_article(article: Article, ctx: Context) -> bool:
    if not can_use_llm_sampling(ctx):
        article.summary = "No summary available."
        return False

    if article.text:
        prompt = f"Please provide a concise summary of the following news article:\n\n{article.text}"
        try:
            response = await ctx.sample(prompt)
            summary = getattr(response, "text", None)
            if not summary or not summary.strip():
                await ctx.warning("LLM Sampling response is empty. Unable to summarize article.")
                article.summary = "No summary available."
                return False
            else:
                article.summary = summary
                return True
        except Exception as err:
            article.summary = "No summary available."
            try:
                await ctx.debug(f"Failed to use LLM sampling for article summary:\n{err.args}")
            except Exception:
                pass
            return False
    else:
        article.summary = "No summary available."
        return False


async def summarize_articles(articles: list[Article], ctx: Context) -> None:
    total_articles = len(articles)
    for idx, article in enumerate(articles):
        if not await llm_summarize_article(article, ctx):
            try:
                article.nlp()
                if not article.summary or not article.summary.strip():
                    article.summary = "No summary available."
            except Exception:
                article.summary = "No summary available."
        if is_session_active(ctx):
            try:
                await ctx.report_progress(idx, total_articles)
            except Exception:
                pass


@mcp.tool(
    description=(
        "Find recent Google News articles for a free-form keyword or phrase. Use this for ad-hoc subject searches; "
        "use get_news_by_topic for a predefined topic category or get_news_by_site for one publisher."
    ),
    tags={"news", "articles", "keyword"},
    annotations=READ_ONLY_OPEN_WORLD_ANNOTATIONS,
)
async def get_news_by_keyword(
    ctx: Context,
    keyword: Annotated[str, Field(description="Search term to find articles.")],
    period: Annotated[int, Field(description="Number of days to look back for articles.", ge=1)] = 7,
    max_results: Annotated[int, Field(description="Maximum number of results to return.", ge=1)] = 10,
    full_data: Annotated[
        bool,
        Field(
            description="Return full data for each article. If False a summary should be created by setting the summarize flag"
        ),
    ] = False,
    summarize: Annotated[
        bool,
        Field(
            description="Generate a summary of the article, will first try LLM Sampling but if unavailable will use nlp"
        ),
    ] = True,
) -> list[ArticleOut]:
    set_newspaper_article_fields(full_data)

    async def progress_callback(progress: float, total: Optional[float]):
        if is_session_active(ctx):
            try:
                await ctx.report_progress(progress, total)
            except Exception:
                pass

    articles = await get_provider_set().news.get_news_by_keyword(
        keyword=keyword,
        period=period,
        max_results=max_results,
        nlp=False,
        report_progress=progress_callback,
    )
    if summarize:
        await summarize_articles(articles, ctx)
    if is_session_active(ctx):
        try:
            await ctx.report_progress(progress=len(articles), total=len(articles))
        except Exception:
            pass
    return [ArticleOut(**a.to_json(False)) for a in articles]


@mcp.tool(
    description=(
        "Find recent Google News articles about a place-focused location such as a city, state, or country. "
        "Use this when geography is the primary filter; use get_news_by_keyword for general subject searches."
    ),
    tags={"news", "articles", "location"},
    annotations=READ_ONLY_OPEN_WORLD_ANNOTATIONS,
)
async def get_news_by_location(
    ctx: Context,
    location: Annotated[str, Field(description="Name of city/state/country.")],
    period: Annotated[int, Field(description="Number of days to look back for articles.", ge=1)] = 7,
    max_results: Annotated[int, Field(description="Maximum number of results to return.", ge=1)] = 10,
    full_data: Annotated[
        bool,
        Field(
            description="Return full data for each article. If False a summary should be created by setting the summarize flag"
        ),
    ] = False,
    summarize: Annotated[
        bool,
        Field(
            description="Generate a summary of the article, will first try LLM Sampling but if unavailable will use nlp"
        ),
    ] = True,
) -> list[ArticleOut]:
    set_newspaper_article_fields(full_data)

    async def progress_callback(progress: float, total: Optional[float]):
        if is_session_active(ctx):
            try:
                await ctx.report_progress(progress, total)
            except Exception:
                pass

    articles = await get_provider_set().news.get_news_by_location(
        location=location,
        period=period,
        max_results=max_results,
        nlp=False,
        report_progress=progress_callback,
    )
    if summarize:
        await summarize_articles(articles, ctx)
    if is_session_active(ctx):
        try:
            await ctx.report_progress(progress=len(articles), total=len(articles))
        except Exception:
            pass
    return [ArticleOut(**a.to_json(False)) for a in articles]


@mcp.tool(
    description=(
        "Find recent Google News articles from a predefined Google News topic category. Use this for topic category "
        "browsing such as BUSINESS, TECHNOLOGY, or SPORTS; use get_news_by_keyword for a free-form query."
    ),
    tags={"news", "articles", "topic"},
    annotations=READ_ONLY_OPEN_WORLD_ANNOTATIONS,
)
async def get_news_by_topic(
    ctx: Context,
    topic: Annotated[str, Field(description="Topic to search for articles.")],
    period: Annotated[int, Field(description="Number of days to look back for articles.", ge=1)] = 7,
    max_results: Annotated[int, Field(description="Maximum number of results to return.", ge=1)] = 10,
    full_data: Annotated[
        bool,
        Field(
            description="Return full data for each article. If False a summary should be created by setting the summarize flag"
        ),
    ] = False,
    summarize: Annotated[
        bool,
        Field(
            description="Generate a summary of the article, will first try LLM Sampling but if unavailable will use nlp"
        ),
    ] = True,
) -> list[ArticleOut]:
    set_newspaper_article_fields(full_data)

    async def progress_callback(progress: float, total: Optional[float]):
        if is_session_active(ctx):
            try:
                await ctx.report_progress(progress, total)
            except Exception:
                pass

    articles = await get_provider_set().news.get_news_by_topic(
        topic=topic,
        period=period,
        max_results=max_results,
        nlp=False,
        report_progress=progress_callback,
    )
    if summarize:
        await summarize_articles(articles, ctx)
    if is_session_active(ctx):
        try:
            await ctx.report_progress(progress=len(articles), total=len(articles))
        except Exception:
            pass
    return [ArticleOut(**a.to_json(False)) for a in articles]


@mcp.tool(
    description=(
        "Return general headline and top-news stories from Google News without a keyword or topic seed. Use this for "
        "a broad news snapshot; use the keyword, location, topic, or site tools when the user gives a filter."
    ),
    tags={"news", "articles", "top"},
    annotations=READ_ONLY_OPEN_WORLD_ANNOTATIONS,
)
async def get_top_news(
    ctx: Context,
    period: Annotated[int, Field(description="Number of days to look back for top articles.", ge=1)] = 3,
    max_results: Annotated[int, Field(description="Maximum number of results to return.", ge=1)] = 10,
    full_data: Annotated[
        bool,
        Field(
            description="Return full data for each article. If False a summary should be created by setting the summarize flag"
        ),
    ] = False,
    summarize: Annotated[
        bool,
        Field(
            description="Generate a summary of the article, will first try LLM Sampling but if unavailable will use nlp"
        ),
    ] = True,
) -> list[ArticleOut]:
    set_newspaper_article_fields(full_data)

    async def progress_callback(progress: float, total: Optional[float]):
        if is_session_active(ctx):
            try:
                await ctx.report_progress(progress, total)
            except Exception:
                pass

    articles = await get_provider_set().news.get_top_news(
        period=period,
        max_results=max_results,
        nlp=False,
        report_progress=progress_callback,
    )
    if summarize:
        await summarize_articles(articles, ctx)
    if is_session_active(ctx):
        try:
            await ctx.report_progress(progress=len(articles), total=len(articles))
        except Exception:
            pass
    return [ArticleOut(**a.to_json(False)) for a in articles]


@mcp.tool(
    description=(
        "Return terms that are trending now for a geography, optionally with related news metadata. Use this for "
        "current trend discovery; use get_trends when the user wants historical interest over time for known keywords."
    ),
    tags={"trends", "google", "trending"},
    annotations=READ_ONLY_OPEN_WORLD_ANNOTATIONS,
)
async def get_trending_terms(
    geo: Annotated[
        str,
        Field(
            description=(
                "Geographic target for trending terms. Supports four levels of granularity:\n"
                "- Worldwide: empty string ''\n"
                "- Country: ISO 3166-1 alpha-2 code, e.g. 'US', 'GB', 'CA'\n"
                "- Subdivision (state/province/region): ISO 3166-2 format 'CC-XX' or 'CC-XXX', e.g. 'US-CA' (California), 'BE-BRU' (Brussels)\n"
                "- US metro area: bare Nielsen DMA code (numeric string), e.g. '807' (San Francisco Bay Area), '501' (New York City)"
            )
        ),
    ] = "US",
    full_data: Annotated[
        bool,
        Field(description="Return full data for each trend including related news stories."),
    ] = False,
) -> list[TrendingTermOut]:
    if not full_data:
        trends = await get_provider_set().trends.get_trending_terms(geo=geo, full_data=False)
        return [TrendingTermOut(keyword=str(tt["keyword"]), volume=tt["volume"]) for tt in trends]
    trends = await get_provider_set().trends.get_trending_terms(geo=geo, full_data=True)
    trends_out = []
    for trend in trends:
        trend_data = dict(trend)
        if "news" in trend_data:
            trend_data["news"] = [
                TrendingTermArticleOut(**article) for article in trend_data["news"]
            ]
        trends_out.append(TrendingTermOut(**trend_data))
    return trends_out


@mcp.tool(
    description=(
        "Return historical Google Trends interest-over-time points for one or more known keywords. Use this for "
        "trajectory and comparisons across a timeframe; values are normalized 0-100 interest scores, not absolute "
        "search volume. Use get_trending_terms for what is trending now."
    ),
    tags={"trends", "google", "history"},
    annotations=READ_ONLY_OPEN_WORLD_ANNOTATIONS,
)
async def get_trends(
    keyword: Annotated[str | list[str], Field(description="Search keyword(s) to analyze.")],
    source: Annotated[str, Field(description="Search source: 'google search', 'youtube search', 'news search', 'image search', 'google shopping'.")] = "google search",
    data_mode: Annotated[str, Field(description="Legacy resolution hint used only when timeframe is omitted: 'weekly', 'daily', 'monthly'.")] = "weekly",
    geo: Annotated[str, Field(description="Geographic region code (e.g. 'US').")] = "US",
    timeframe: Annotated[Optional[str], Field(description="Explicit TrendsPy range, for example 'today 12-m', 'today 90-d', 'all', or 'YYYY-MM-DD YYYY-MM-DD'. Overrides data_mode when supplied.")] = None,
    cat: Annotated[int, Field(description="Google Trends category ID; use 0 for all categories or a value from get_categories.")] = 0,
) -> list[TrendPoint]:
    results = await get_provider_set().trends.get_trends(
        keyword=keyword,
        source=source,
        data_mode=data_mode,
        geo=geo,
        timeframe=timeframe,
        cat=cat,
    )
    return [TrendPoint(**item) for item in results]


@mcp.tool(
    description=(
        "Estimate momentum for one or more known keywords across requested growth windows. Use this when percentage "
        "growth is the goal; use get_trends when the user needs the underlying historical time series."
    ),
    tags={"trends", "google", "growth"},
    annotations=READ_ONLY_OPEN_WORLD_ANNOTATIONS,
)
async def get_growth(
    keyword: Annotated[str | list[str], Field(description="Search keyword(s) to analyze.")],
    source: Annotated[str, Field(description="Search source: 'google search', 'youtube search', etc.")] = "google search",
    percent_growth: Annotated[Optional[list[str]], Field(description="Timeframes to calculate growth (e.g. ['3M', '1Y']).")] = None,
    geo: Annotated[str, Field(description="Geographic region code (e.g. 'US').")] = "US",
) -> list[KeywordGrowthOut]:
    results = await get_provider_set().trends.get_growth(
        keyword=keyword,
        source=source,
        percent_growth=percent_growth,
        geo=geo
    )
    return [KeywordGrowthOut(**item) for item in results]


@mcp.tool(
    description=(
        "Return currently trending keywords ranked by week-over-week growth or volume. Use this when explicit ranked "
        "order matters; use get_top_trends for a simpler current feed and get_trends for historical series."
    ),
    tags={"trends", "google", "ranked"},
    annotations=READ_ONLY_OPEN_WORLD_ANNOTATIONS,
)
async def get_ranked_trends(
    source: Annotated[str, Field(description="Search source: 'google search'.")] = "google search",
    sort: Annotated[str, Field(description="Field to sort by: 'wow_pct_change', 'volume'.")] = "wow_pct_change",
    limit: Annotated[int, Field(description="Maximum number of trends to return.", ge=1)] = 20,
    geo: Annotated[str, Field(description="Geographic region code (e.g. 'US').")] = "US",
) -> list[RankedTrendOut]:
    results = await get_provider_set().trends.get_ranked_trends(
        source=source,
        sort=sort,
        limit=limit,
        geo=geo
    )
    for r in results:
        if "news" in r and r["news"]:
            r["news"] = [TrendingTermArticleOut(**art) for art in r["news"]]
    return [RankedTrendOut(**item) for item in results]


@mcp.tool(
    description=(
        "Return a bounded current topic discovery feed from Google Trends RSS, including related news where available. "
        "Use this for current top or daily trends; use get_ranked_trends when explicit ranking by growth or volume matters."
    ),
    tags={"trends", "google", "top"},
    annotations=READ_ONLY_OPEN_WORLD_ANNOTATIONS,
)
async def get_top_trends(
    type: Annotated[str, Field(description="Type of trends: 'Google Trends' (realtime), 'Daily Trends' (daily).")] = "Google Trends",
    limit: Annotated[int, Field(description="Maximum number of trends to return.", ge=1)] = 20,
    geo: Annotated[str, Field(description="Geographic region code (e.g. 'US').")] = "US",
) -> list[TopTrendOut]:
    results = await get_provider_set().trends.get_top_trends(
        type=type,
        limit=limit,
        geo=geo
    )
    for r in results:
        if "news" in r and r["news"]:
            r["news"] = [TrendingTermArticleOut(**art) for art in r["news"]]
    return [TopTrendOut(**item) for item in results]


@mcp.tool(
    description=(
        "Find recent Google News articles from one publisher domain. Use this when the user wants source-specific "
        "coverage; use get_news_by_keyword for cross-publisher subject search."
    ),
    tags={"news", "articles", "site"},
    annotations=READ_ONLY_OPEN_WORLD_ANNOTATIONS,
)
async def get_news_by_site(
    ctx: Context,
    site: Annotated[str, Field(description="Domain of the news site, e.g. 'cnn.com'.")],
    period: Annotated[int, Field(description="Number of days to look back for articles.", ge=1)] = 7,
    max_results: Annotated[int, Field(description="Maximum number of results to return.", ge=1)] = 10,
    full_data: Annotated[
        bool,
        Field(
            description="Return full data for each article. If False a summary should be created by setting the summarize flag"
        ),
    ] = False,
    summarize: Annotated[
        bool,
        Field(
            description="Generate a summary of the article, will first try LLM Sampling but if unavailable will use nlp"
        ),
    ] = True,
) -> list[ArticleOut]:
    set_newspaper_article_fields(full_data)

    async def progress_callback(progress: float, total: Optional[float]):
        if is_session_active(ctx):
            try:
                await ctx.report_progress(progress, total)
            except Exception:
                pass

    articles = await get_provider_set().news.get_news_by_site(
        site=site,
        period=period,
        max_results=max_results,
        nlp=False,
        report_progress=progress_callback,
    )
    if summarize:
        await summarize_articles(articles, ctx)
    if is_session_active(ctx):
        try:
            await ctx.report_progress(progress=len(articles), total=len(articles))
        except Exception:
            pass
    return [ArticleOut(**a.to_json(False)) for a in articles]


@mcp.tool(
    description=(
        "Download and parse one specific news article when you already have an article URL. Use it to retrieve article "
        "text or metadata or summarize that URL; do not use it for discovery - use the news search tools instead."
    ),
    tags={"news", "articles", "scrape"},
    annotations=READ_ONLY_OPEN_WORLD_ANNOTATIONS,
)
async def get_article_content(
    ctx: Context,
    url: Annotated[str, Field(description="The URL of the news article to download and parse.")],
    full_data: Annotated[
        bool,
        Field(
            description="Return full data for the article. If False a summary should be created by setting the summarize flag"
        ),
    ] = False,
    summarize: Annotated[
        bool,
        Field(
            description="Generate a summary of the article, will first try LLM Sampling but if unavailable will use nlp"
        ),
    ] = True,
) -> Optional[ArticleOut]:
    url = get_provider_set().news.validate_article_url(url)
    set_newspaper_article_fields(full_data)
    article = await get_provider_set().news.download_article(url)
    if not article:
        return None
    if summarize:
        await summarize_articles([article], ctx)
    return ArticleOut(**article.to_json(False))


@mcp.tool(
    description=(
        "Return geographic Google Trends interest for one or more known keywords at country, region, city, or DMA "
        "resolution. Use this to compare where demand is strongest; use get_trends for interest over time instead."
    ),
    tags={"trends", "google", "region"},
    annotations=READ_ONLY_OPEN_WORLD_ANNOTATIONS,
)
async def get_interest_by_region(
    keywords: Annotated[str | list[str], Field(description="Search keyword(s) to analyze.")],
    timeframe: Annotated[str, Field(description="Timeframe for search volume analysis (e.g., 'today 12-m').")] = "today 12-m",
    geo: Annotated[str, Field(description="Geographic region code (e.g. 'US' or empty '' for worldwide).")] = "US",
    cat: Annotated[int, Field(description="Category ID (default: 0 for all).")] = 0,
    gprop: Annotated[str, Field(description="Google property filter (e.g., '', 'youtube', 'news', 'images', 'froogle').")] = "",
    resolution: Annotated[str, Field(description="Geographic resolution: 'COUNTRY', 'REGION', 'CITY', or 'DMA'.")] = "REGION",
    inc_low_vol: Annotated[bool, Field(description="Include regions with low search volume.")] = False,
) -> list[RegionInterestOut]:
    results = await get_provider_set().trends.get_interest_by_region(
        keywords=keywords,
        timeframe=timeframe,
        geo=geo,
        cat=cat,
        gprop=gprop,
        resolution=resolution,
        inc_low_vol=inc_low_vol,
    )
    return [RegionInterestOut(
        geo_name=item["geoName"],
        geo_code=item["geoCode"],
        values=item["values"]
    ) for item in results]


@mcp.tool(
    description=(
        "Return top and rising literal search queries related to one seed keyword. Use this for query expansion; use "
        "get_related_topics for topic entities or get_suggestions for autocomplete candidates."
    ),
    tags={"trends", "google", "queries"},
    annotations=READ_ONLY_OPEN_WORLD_ANNOTATIONS,
)
async def get_related_queries(
    keyword: Annotated[str, Field(description="Search keyword to analyze.")],
    timeframe: Annotated[str, Field(description="Timeframe for search volume analysis (e.g., 'today 12-m').")] = "today 12-m",
    geo: Annotated[str, Field(description="Geographic region code (e.g. 'US').")] = "US",
    cat: Annotated[int, Field(description="Category ID (default: 0 for all).")] = 0,
    gprop: Annotated[str, Field(description="Google property filter (e.g., '', 'youtube', 'news', 'images', 'froogle').")] = "",
) -> RelatedQueriesOut:
    results = await get_provider_set().trends.get_related_queries(
        keyword=keyword,
        timeframe=timeframe,
        geo=geo,
        cat=cat,
        gprop=gprop,
    )
    return RelatedQueriesOut(
        top=[RelatedQueryItem(**item) for item in results["top"]],
        rising=[RelatedQueryItem(**item) for item in results["rising"]],
    )


@mcp.tool(
    description=(
        "Return top and rising Google Trends topic entities related to one seed keyword. Use this for entity or topic "
        "expansion; use get_related_queries for literal search queries."
    ),
    tags={"trends", "google", "topics"},
    annotations=READ_ONLY_OPEN_WORLD_ANNOTATIONS,
)
async def get_related_topics(
    keyword: Annotated[str, Field(description="Search keyword to analyze.")],
    timeframe: Annotated[str, Field(description="Timeframe for search volume analysis (e.g., 'today 12-m').")] = "today 12-m",
    geo: Annotated[str, Field(description="Geographic region code (e.g. 'US').")] = "US",
    cat: Annotated[int, Field(description="Category ID (default: 0 for all).")] = 0,
    gprop: Annotated[str, Field(description="Google property filter (e.g., '', 'youtube', 'news', 'images', 'froogle').")] = "",
) -> RelatedTopicsOut:
    results = await get_provider_set().trends.get_related_topics(
        keyword=keyword,
        timeframe=timeframe,
        geo=geo,
        cat=cat,
        gprop=gprop,
    )
    return RelatedTopicsOut(
        top=[RelatedTopicItem(**item) for item in results["top"]],
        rising=[RelatedTopicItem(**item) for item in results["rising"]],
    )


@mcp.tool(
    description=(
        "Return Google Trends autocomplete suggestions for a seed keyword. Use this for lightweight autocomplete or "
        "entity candidates; use get_related_queries when you need top or rising demand signals."
    ),
    tags={"trends", "google", "suggestions"},
    annotations=READ_ONLY_OPEN_WORLD_ANNOTATIONS,
)
async def get_suggestions(
    keyword: Annotated[str, Field(description="Query string to autocomplete.")],
    language: Annotated[Optional[str], Field(description="Language code, e.g. 'en'.")] = None,
) -> list[SuggestionItem]:
    results = await get_provider_set().trends.get_suggestions(
        keyword=keyword,
        language=language,
    )
    return [SuggestionItem(**item) for item in results]


@mcp.tool(
    description=(
        "Return Google Trends category IDs and names for use in the cat parameter of trend tools. Call this when a "
        "category filter is needed; do not guess category IDs."
    ),
    tags={"trends", "google", "categories"},
    annotations=READ_ONLY_OPEN_WORLD_ANNOTATIONS,
)
async def get_categories() -> list[CategoryItem]:
    results = await get_provider_set().trends.get_categories()
    return [CategoryItem(**item) for item in results]


def main():
    mcp.run()