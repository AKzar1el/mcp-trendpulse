import click
import asyncio
from collections import defaultdict


from mcp_trendpulse.config import load_environment
from mcp_trendpulse.news import (
    get_news_by_keyword,
    get_news_by_location,
    get_news_by_topic,
    get_trending_terms,
    get_top_news,
    save_article_to_json,
    BrowserManager,
)
from mcp_trendpulse.providers import get_provider_set


@click.group()
def cli():
    load_environment()


@cli.command(help=get_news_by_keyword.__doc__)
@click.argument("keyword")
@click.option("--period", type=int, default=7, help="Period in days to search for articles.")
@click.option(
    "--max-results",
    "max_results",
    type=int,
    default=10,
    help="Maximum number of results to return.",
)
@click.option("--no-nlp", is_flag=True, default=False, help="Disable NLP processing for articles.")
def keyword(keyword, period, max_results, no_nlp):
    @BrowserManager()
    async def _keyword():
        articles = await get_news_by_keyword(keyword, period=period, max_results=max_results, nlp=not no_nlp)
        print_articles(articles)
        click.echo(f"Found {len(articles)} articles for keyword '{keyword}'.")

    asyncio.run(_keyword())


@cli.command(help=get_news_by_location.__doc__)
@click.argument("location")
@click.option("--period", type=int, default=7, help="Period in days to search for articles.")
@click.option(
    "--max-results",
    "max_results",
    type=int,
    default=10,
    help="Maximum number of results to return.",
)
@click.option("--no-nlp", is_flag=True, default=False, help="Disable NLP processing for articles.")
def location(location, period, max_results, no_nlp):
    @BrowserManager()
    async def _location():
        articles = await get_news_by_location(location, period=period, max_results=max_results, nlp=not no_nlp)
        print_articles(articles)
        click.echo(f"Found {len(articles)} articles for location '{location}'.")

    asyncio.run(_location())


@cli.command(help=get_news_by_topic.__doc__)
@click.argument("topic")
@click.option("--period", type=int, default=7, help="Period in days to search for articles.")
@click.option(
    "--max-results",
    "max_results",
    type=int,
    default=10,
    help="Maximum number of results to return.",
)
@click.option("--no-nlp", is_flag=True, default=False, help="Disable NLP processing for articles.")
def topic(topic, period, max_results, no_nlp):
    @BrowserManager()
    async def _topic():
        articles = await get_news_by_topic(topic, period=period, max_results=max_results, nlp=not no_nlp)
        print_articles(articles)
        click.echo(f"Found {len(articles)} articles for topic '{topic}'.")

    asyncio.run(_topic())


@cli.command(help=get_trending_terms.__doc__)
@click.option("--geo", type=str, default="US", help="Country code, e.g. 'US', 'GB', 'IN', etc.")
@click.option("--full-data", is_flag=True, default=False, help="Return full data for each trend.")
def trending(geo, full_data):
    # Browser not used for Google Trends
    async def _trending():
        trending_terms = await get_trending_terms(geo=geo, full_data=full_data)
        if trending_terms:
            click.echo("Trending terms:")
            for term in trending_terms:
                if isinstance(term, dict):
                    click.echo(f"{term['keyword']:<40} - {term['volume']}")
                else:
                    click.echo(term)
        else:
            click.echo("No trending terms found.")

    asyncio.run(_trending())


@cli.command(help=get_top_news.__doc__)
@click.option("--period", type=int, default=3, help="Period in days to search for top articles.")
@click.option(
    "--max-results",
    "max_results",
    type=int,
    default=10,
    help="Maximum number of results to return.",
)
@click.option("--no-nlp", is_flag=True, default=False, help="Disable NLP processing for articles.")
def top(period, max_results, no_nlp):
    @BrowserManager()
    async def _top():
        articles = await get_top_news(max_results=max_results, period=period, nlp=not no_nlp)
        print_articles(articles)
        click.echo(f"Found {len(articles)} top articles.")

    asyncio.run(_top())


@cli.command("brief-pack", help="Build the core trend/growth evidence table for a TrendPulse Demand Brief.")
@click.option("--keyword", "keywords", multiple=True, required=True, help="Keyword or phrase; repeat up to five times.")
@click.option("--market", "markets", multiple=True, required=True, help="Market code such as US or GB; repeat up to twice.")
@click.option("--timeframe", type=str, default="today 12-m", show_default=True, help="Shared Google Trends timeframe.")
def brief_pack(keywords, markets, timeframe):
    """Emit a deterministic Markdown evidence pack for human Demand Brief fulfillment."""
    cleaned_keywords = [value.strip() for value in keywords if value.strip()]
    cleaned_markets = [value.strip().upper() for value in markets if value.strip()]
    if not 1 <= len(cleaned_keywords) <= 5 or len(cleaned_keywords) != len(keywords):
        raise click.UsageError("Provide between one and five non-empty --keyword values.")
    if len(set(cleaned_keywords)) != len(cleaned_keywords):
        raise click.UsageError("Keywords must be unique.")
    if not 1 <= len(cleaned_markets) <= 2 or len(cleaned_markets) != len(markets):
        raise click.UsageError("Provide one or two non-empty --market values.")
    if len(set(cleaned_markets)) != len(cleaned_markets):
        raise click.UsageError("Markets must be unique.")

    async def _build():
        providers = get_provider_set()
        click.echo("# TrendPulse Demand Brief evidence pack")
        click.echo()
        click.echo(f"Timeframe: **{timeframe}** | Google Trends property: **Google Search**")
        click.echo("Data source: **Google Trends** (https://trends.google.com/trends/)")
        click.echo()
        click.echo("> Google Trends values are normalized relative-interest indices, not absolute search volume. Compare terms within the same market request; do not compare index values directly across markets.")

        for market in cleaned_markets:
            points = await providers.trends.get_trends(
                keyword=cleaned_keywords,
                source="google search",
                geo=market,
                timeframe=timeframe,
            )
            growth_rows = await providers.trends.get_growth(
                keyword=cleaned_keywords,
                source="google search",
                percent_growth=["3M", "1Y"],
                geo=market,
            )

            series = defaultdict(list)
            for point in points:
                series[str(point.get("keyword", ""))].append(point)
            latest_trends_date = max(
                (str(point["date"])[:10] for point in points if point.get("date")),
                default=None,
            )
            growth = {
                str(row.get("keyword", "")): row.get("growth") or {}
                for row in growth_rows
            }

            click.echo()
            click.echo(f"## {market}")
            if latest_trends_date:
                click.echo()
                click.echo(f"Latest complete Trends point: **{latest_trends_date}**")
            click.echo()
            click.echo("| Keyword | Latest index | 3M growth | 1Y growth |")
            click.echo("| --- | ---: | ---: | ---: |")
            for keyword in cleaned_keywords:
                keyword_points = series.get(keyword, [])
                latest = keyword_points[-1].get("value") if keyword_points else None
                keyword_growth = growth.get(keyword, {})
                click.echo(
                    f"| {keyword} | {_brief_value(latest)} | {_brief_percent(keyword_growth.get('3M'))} | {_brief_percent(keyword_growth.get('1Y'))} |"
                )

    asyncio.run(_build())


def _brief_value(value):
    if value is None:
        return "n/a"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:g}"


def _brief_percent(value):
    if value is None:
        return "n/a"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:+.2f}%"


def print_articles(articles):
    for article in articles:
        click.echo(f"Title: {article.title}")
        click.echo(f"URL: {article.original_url}")
        click.echo(f"Authors: {article.authors}")
        click.echo(f"Publish Date: {article.publish_date}")
        click.echo(f"Top Image: {article.top_image}")
        click.echo(f"Summary: {article.summary}\n")
        save_article_to_json(article)


if __name__ == "__main__":
    cli()
