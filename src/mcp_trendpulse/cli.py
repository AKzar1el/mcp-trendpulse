import asyncio
import hashlib
import html
import json
import re
import sys
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path

import click
from mcp_trendpulse.config import GOOGLE_NEWS_MAX_RESULTS, load_environment
from mcp_trendpulse.errors import ProviderError, ProviderErrorCode
# Delay heavyweight news/browser/NLP imports until a CLI command needs them.
# Click help text preserves the underlying news API documentation.
def _news_export(name):
    from mcp_trendpulse import news
    return getattr(news, name)

def get_provider_set(*args, **kwargs):
    from mcp_trendpulse.providers import get_provider_set as provider_set
    return provider_set(*args, **kwargs)

def _growth_from_trend_points(*args, **kwargs):
    return _news_export('_growth_from_trend_points')(*args, **kwargs)
_growth_from_trend_points.__doc__ = 'Calculate growth from already-fetched completed Trends points.'

async def get_news_by_keyword(*args, **kwargs):
    return await _news_export('get_news_by_keyword')(*args, **kwargs)
get_news_by_keyword.__doc__ = '\n    Find articles by keyword using Google News.\n    '

async def get_news_by_location(*args, **kwargs):
    return await _news_export('get_news_by_location')(*args, **kwargs)
get_news_by_location.__doc__ = 'Find articles by location using Google News.'

async def get_news_by_site(*args, **kwargs):
    return await _news_export('get_news_by_site')(*args, **kwargs)
get_news_by_site.__doc__ = 'Find articles from a specific publisher site using Google News.'

async def get_news_by_topic(*args, **kwargs):
    return await _news_export('get_news_by_topic')(*args, **kwargs)
get_news_by_topic.__doc__ = 'Find articles by topic using Google News.\n    topic is one of\n    WORLD, NATION, BUSINESS, TECHNOLOGY, ENTERTAINMENT, SPORTS, SCIENCE, HEALTH,\n    POLITICS, CELEBRITIES, TV, MUSIC, MOVIES, THEATER, SOCCER, CYCLING, MOTOR SPORTS,\n    TENNIS, COMBAT SPORTS, BASKETBALL, BASEBALL, FOOTBALL, SPORTS BETTING, WATER SPORTS,\n    HOCKEY, GOLF, CRICKET, RUGBY, ECONOMY, PERSONAL FINANCE, FINANCE, DIGITAL CURRENCIES,\n    MOBILE, ENERGY, GAMING, INTERNET SECURITY, GADGETS, VIRTUAL REALITY, ROBOTICS, NUTRITION,\n    PUBLIC HEALTH, MENTAL HEALTH, MEDICINE, SPACE, WILDLIFE, ENVIRONMENT, NEUROSCIENCE, PHYSICS,\n    GEOLOGY, PALEONTOLOGY, SOCIAL SCIENCES, EDUCATION, JOBS, ONLINE EDUCATION, HIGHER EDUCATION,\n    VEHICLES, ARTS-DESIGN, BEAUTY, FOOD, TRAVEL, SHOPPING, HOME, OUTDOORS, FASHION.\n    '

async def get_trending_terms(*args, **kwargs):
    return await _news_export('get_trending_terms')(*args, **kwargs)
get_trending_terms.__doc__ = '\n    Returns google trends for a specific geo location.\n    '

async def get_top_news(*args, **kwargs):
    return await _news_export('get_top_news')(*args, **kwargs)
get_top_news.__doc__ = '\n    Get top news stories from Google News.\n    '

def save_article_to_json(*args, **kwargs):
    return _news_export('save_article_to_json')(*args, **kwargs)
save_article_to_json.__doc__ = 'Save an article to a JSON file.'

def BrowserManager(*args, **kwargs):
    return _news_export('BrowserManager')(*args, **kwargs)


def _configure_redirected_output():
    """Use UTF-8 for redirected CLI output without changing interactive consoles."""
    for stream in (sys.stdout, sys.stderr):
        if stream.isatty():
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="strict")
        except (OSError, ValueError):
            pass


@click.group()
def cli():
    _configure_redirected_output()
    load_environment()


@cli.command("bigquery-sql", help="Print Google public Trends Top 25 SQL without starting a query or spending credits.")
@click.option("--country", required=True, help="Two-letter ISO country code, e.g. US or GB.")
@click.option("--kind", type=click.Choice(["top", "rising"]), default="top", show_default=True)
@click.option("--limit", type=click.IntRange(1, 25), default=25, show_default=True)
@click.option("--snapshot-date", default=None, help="Optional YYYY-MM-DD snapshot date.")
@click.option("--region-code", default=None, help="Optional international ISO 3166-2 subdivision.")
@click.option("--dma-id", default=None, help="Optional US three-digit Designated Market Area.")
def bigquery_sql(country, kind, limit, snapshot_date, region_code, dma_id):
    """Generate read-only BigQuery SQL but never run a BigQuery job."""
    from mcp_trendpulse.bigquery_trends import build_discovery_sql

    try:
        sql = build_discovery_sql(
            country=country.strip().upper(),
            kind=kind,
            limit=limit,
            snapshot_date=snapshot_date,
            region_code=region_code,
            dma_id=dma_id,
        )
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc
    click.echo(sql)


@cli.command(
    "bigquery-discover",
    help="Preview public Trends rankings; opt in to capped jobs on a verified no-billing sandbox.",
)
@click.option("--country", required=True, help="Source-supported ISO country code, e.g. US or GB.")
@click.option("--kind", type=click.Choice(["top", "rising"]), default="top", show_default=True)
@click.option("--limit", type=click.IntRange(1, 25), default=10, show_default=True)
@click.option("--snapshot-date", default=None, help="YYYY-MM-DD from the last 30 days; defaults to yesterday.")
@click.option("--region-code", default=None, help="International ISO 3166-2 subdivision.")
@click.option("--dma-id", default=None, help="US three-digit Designated Market Area.")
@click.option("--project-id", default=None,
              help="Operator-owned Google Cloud sandbox project; never used without --execute.")
@click.option("--execute", is_flag=True,
              help="Allow dry run and one bounded public query only if project has NO billing account.")
@click.option("--format", "output_format", type=click.Choice(["json", "text"]),
              default="json", show_default=True)
def bigquery_discover(country, kind, limit, snapshot_date, region_code, dma_id,
                      project_id, execute, output_format):
    """Discover public source terms without a site property or paid fallback."""
    from mcp_trendpulse.bigquery_trends import discover_sandbox_trends

    try:
        result = discover_sandbox_trends(
            country=country.strip().upper(), kind=kind, limit=limit,
            snapshot_date=snapshot_date, region_code=region_code, dma_id=dma_id,
            project_id=project_id, execute=execute,
        )
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc
    if output_format == "json":
        click.echo(json.dumps(result, ensure_ascii=False, allow_nan=False, sort_keys=True))
        return
    click.echo(
        f"Google Trends BigQuery {result['kind']} {result['country']} / "
        f"{result['snapshot_date']}: {result['status']}"
    )
    click.echo(f"Preview only: {not execute}; no billing account allowed.")
    if result.get("reason"):
        click.echo(f"Unavailable: {result['reason']}")
    if result["dry_run_estimated_bytes"] is not None:
        click.echo(f"Dry-run bytes: {result['dry_run_estimated_bytes']}")
    for signal in result["signals"]:
        click.echo(f"  {signal['raw_term']} (rank {int(signal['value'])})")
    if not execute:
        click.echo("No Google credentials used. Use --execute and --project-id only on a billing-free sandbox.")


@cli.group("watch", help="Manage local manual Trend Watch rules; no polling or external alerts.")
def watch():
    """Trend Watch operates on user-supplied JSON evidence only."""


@watch.command("create")
@click.option("--keyword", required=True, help="Watch query (stored locally, not uploaded).")
@click.option("--market", required=True, help="ISO country code.")
@click.option("--growth-pct", type=click.FloatRange(1, 1000), default=30.0, show_default=True)
@click.option("--minimum-interest", type=click.FloatRange(0, 100), default=20.0, show_default=True)
@click.option("--window", type=click.IntRange(2, 12), default=4, show_default=True)
@click.option("--cooldown-days", type=click.IntRange(1, 90), default=7, show_default=True)
def watch_create(keyword, market, growth_pct, minimum_interest, window, cooldown_days):
    from mcp_trendpulse.trend_watch import WatchStore

    try:
        rule = WatchStore().create(
            keyword=keyword,
            market=market.strip().upper(),
            growth_pct=growth_pct,
            minimum_interest=minimum_interest,
            window=window,
            cooldown_days=cooldown_days,
        )
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(asdict(rule), sort_keys=True))


@watch.command("list")
def watch_list():
    from mcp_trendpulse.trend_watch import WatchStore

    try:
        rules = WatchStore().list_rules()
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps([asdict(rule) for rule in rules], sort_keys=True))


@watch.command("remove")
@click.option("--id", "rule_id", required=True, help="Existing watch rule ID.")
def watch_remove(rule_id):
    from mcp_trendpulse.trend_watch import WatchStore

    try:
        deleted = WatchStore().delete(rule_id)
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps({"id": rule_id, "deleted": deleted}, sort_keys=True))


@watch.command("evaluate")
@click.option("--id", "rule_id", required=True, help="Existing watch rule ID.")
@click.option("--evidence", type=click.Path(exists=True, dir_okay=False, path_type=Path), required=True)
def watch_evaluate(rule_id, evidence):
    from mcp_trendpulse.trend_watch import MAX_EVIDENCE_BYTES, WatchStore

    try:
        if evidence.stat().st_size > MAX_EVIDENCE_BYTES:
            raise ValueError("Evidence file exceeds 256 KiB")
        result = WatchStore().evaluate_and_record(rule_id, evidence.read_bytes())
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(result.as_json())


@cli.command(help=get_news_by_keyword.__doc__)
@click.argument("keyword")
@click.option("--period", type=click.IntRange(min=1), default=7, help="Period in days to search for articles.")
@click.option(
    "--max-results",
    "max_results",
    type=click.IntRange(1, GOOGLE_NEWS_MAX_RESULTS),
    default=10,
    help="Maximum number of results to return.",
)
@click.option("--no-nlp", is_flag=True, default=False, help="Disable NLP processing for articles.")
@click.option("--headlines-only", is_flag=True, default=False, help="Return labeled RSS headline metadata, not full articles.")
@click.option("--save-json-dir", type=click.Path(exists=True, file_okay=False, path_type=Path), default=None,
              help="Save extracted article JSON in this existing directory without overwriting files.")
def keyword(keyword, period, max_results, no_nlp, headlines_only, save_json_dir):
    if headlines_only:
        if save_json_dir is not None:
            raise click.UsageError("--save-json-dir is not supported with --headlines-only.")
        items = asyncio.run(get_provider_set().news.get_rss_headlines_by_keyword(keyword=keyword, period=period, max_results=max_results))
        print_rss_headlines(items)
        click.echo(f"Found {len(items)} RSS headlines for keyword '{keyword}'.")
        return

    @BrowserManager()
    async def _keyword():
        articles = await get_news_by_keyword(keyword, period=period, max_results=max_results, nlp=not no_nlp)
        print_articles(articles, export_dir=save_json_dir)
        click.echo(f"Found {len(articles)} articles for keyword '{keyword}'.")

    asyncio.run(_keyword())


@cli.command(help=get_news_by_location.__doc__)
@click.argument("location")
@click.option("--period", type=click.IntRange(min=1), default=7, help="Period in days to search for articles.")
@click.option(
    "--max-results",
    "max_results",
    type=click.IntRange(1, GOOGLE_NEWS_MAX_RESULTS),
    default=10,
    help="Maximum number of results to return.",
)
@click.option("--no-nlp", is_flag=True, default=False, help="Disable NLP processing for articles.")
@click.option("--headlines-only", is_flag=True, default=False, help="Return labeled RSS headline metadata, not full articles.")
@click.option("--save-json-dir", type=click.Path(exists=True, file_okay=False, path_type=Path), default=None,
              help="Save extracted article JSON in this existing directory without overwriting files.")
def location(location, period, max_results, no_nlp, headlines_only, save_json_dir):
    if headlines_only:
        if save_json_dir is not None:
            raise click.UsageError("--save-json-dir is not supported with --headlines-only.")
        items = asyncio.run(get_provider_set().news.get_rss_headlines_by_location(location=location, period=period, max_results=max_results))
        print_rss_headlines(items)
        click.echo(f"Found {len(items)} RSS headlines for location '{location}'.")
        return

    @BrowserManager()
    async def _location():
        articles = await get_news_by_location(location, period=period, max_results=max_results, nlp=not no_nlp)
        print_articles(articles, export_dir=save_json_dir)
        click.echo(f"Found {len(articles)} articles for location '{location}'.")

    asyncio.run(_location())


@cli.command(help=get_news_by_topic.__doc__)
@click.argument("topic")
@click.option("--period", type=click.IntRange(min=1), default=7, help="Period in days to search for articles.")
@click.option(
    "--max-results",
    "max_results",
    type=click.IntRange(1, GOOGLE_NEWS_MAX_RESULTS),
    default=10,
    help="Maximum number of results to return.",
)
@click.option("--no-nlp", is_flag=True, default=False, help="Disable NLP processing for articles.")
@click.option("--headlines-only", is_flag=True, default=False, help="Return labeled RSS headline metadata, not full articles.")
@click.option("--save-json-dir", type=click.Path(exists=True, file_okay=False, path_type=Path), default=None,
              help="Save extracted article JSON in this existing directory without overwriting files.")
def topic(topic, period, max_results, no_nlp, headlines_only, save_json_dir):
    if headlines_only:
        if save_json_dir is not None:
            raise click.UsageError("--save-json-dir is not supported with --headlines-only.")
        items = asyncio.run(get_provider_set().news.get_rss_headlines_by_topic(topic=topic, period=period, max_results=max_results))
        print_rss_headlines(items)
        click.echo(f"Found {len(items)} RSS headlines for topic '{topic}'.")
        return

    @BrowserManager()
    async def _topic():
        articles = await get_news_by_topic(topic, period=period, max_results=max_results, nlp=not no_nlp)
        print_articles(articles, export_dir=save_json_dir)
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
            click.echo(
                "Traffic values are approximate Google Trends Trending Now buckets, "
                "not exact search volumes."
            )
            for term in trending_terms:
                if isinstance(term, dict):
                    click.echo(f"{term['keyword']:<40} - {term['volume']}")
                else:
                    click.echo(term)
        else:
            click.echo("No trending terms found.")

    asyncio.run(_trending())


@cli.command(help=get_top_news.__doc__)
@click.option("--period", type=click.IntRange(min=1), default=3, help="Period in days to search for top articles.")
@click.option(
    "--max-results",
    "max_results",
    type=click.IntRange(1, GOOGLE_NEWS_MAX_RESULTS),
    default=10,
    help="Maximum number of results to return.",
)
@click.option("--no-nlp", is_flag=True, default=False, help="Disable NLP processing for articles.")
@click.option("--headlines-only", is_flag=True, default=False, help="Return labeled RSS headline metadata, not full articles.")
@click.option("--save-json-dir", type=click.Path(exists=True, file_okay=False, path_type=Path), default=None,
              help="Save extracted article JSON in this existing directory without overwriting files.")
def top(period, max_results, no_nlp, headlines_only, save_json_dir):
    if headlines_only:
        if save_json_dir is not None:
            raise click.UsageError("--save-json-dir is not supported with --headlines-only.")
        items = asyncio.run(get_provider_set().news.get_rss_headlines_for_top_news(period=period, max_results=max_results))
        print_rss_headlines(items)
        click.echo(f"Found {len(items)} RSS headlines for top news.")
        return

    @BrowserManager()
    async def _top():
        articles = await get_top_news(max_results=max_results, period=period, nlp=not no_nlp)
        print_articles(articles, export_dir=save_json_dir)
        click.echo(f"Found {len(articles)} top articles.")

    asyncio.run(_top())


@cli.command(help=get_news_by_site.__doc__)
@click.argument("site")
@click.option("--period", type=click.IntRange(min=1), default=7, help="Period in days to search for articles.")
@click.option("--max-results", "max_results", type=click.IntRange(1, GOOGLE_NEWS_MAX_RESULTS), default=10, help="Maximum number of results.")
@click.option("--no-nlp", is_flag=True, default=False, help="Disable NLP processing for articles.")
@click.option("--headlines-only", is_flag=True, default=False, help="Return labeled RSS headline metadata, not full articles.")
@click.option("--save-json-dir", type=click.Path(exists=True, file_okay=False, path_type=Path), default=None,
              help="Save extracted article JSON in this existing directory without overwriting files.")
def site(site, period, max_results, no_nlp, headlines_only, save_json_dir):
    if headlines_only:
        if save_json_dir is not None:
            raise click.UsageError("--save-json-dir is not supported with --headlines-only.")
        items = asyncio.run(get_provider_set().news.get_rss_headlines_by_site(
            site=site, period=period, max_results=max_results,
        ))
        print_rss_headlines(items)
        click.echo(f"Found {len(items)} RSS headlines for site '{site}'.")
        return

    @BrowserManager()
    async def _site():
        articles = await get_news_by_site(site, period=period, max_results=max_results, nlp=not no_nlp)
        print_articles(articles, export_dir=save_json_dir)
        click.echo(f"Found {len(articles)} articles for site '{site}'.")

    asyncio.run(_site())


@cli.command("brief-pack", help="Build the core trend/growth evidence table for a TrendPulse Demand Brief.")
@click.option("--keyword", "keywords", multiple=True, required=True, help="Keyword or phrase; repeat up to five times.")
@click.option("--market", "markets", multiple=True, required=True, help="Country or subregion code such as US or US-CA; repeat up to twice.")
@click.option("--timeframe", type=str, default="today 12-m", show_default=True, help="Shared Google Trends timeframe.")
@click.option("--format", "output_format", type=click.Choice(["markdown", "json", "watch-json"]), default="markdown", show_default=True, help="Human-readable, structured brief, or manual Trend Watch evidence.")
@click.option("--watch-evidence-file", type=click.Path(dir_okay=False, path_type=Path), default=None, help="Write UTF-8 watch-json to a new file, never overwriting existing evidence.")
@click.option("--allow-partial", is_flag=True, help="Keep usable markets when a provider fails; incomplete output still exits nonzero.")
def brief_pack(keywords, markets, timeframe, output_format, watch_evidence_file, allow_partial):
    """Emit an attributed evidence pack for human Demand Brief fulfillment."""
    cleaned_keywords = [value.strip() for value in keywords if value.strip()]
    cleaned_markets = [value.strip().upper() for value in markets if value.strip()]
    if not 1 <= len(cleaned_keywords) <= 5 or len(cleaned_keywords) != len(keywords):
        raise click.UsageError("Provide between one and five non-empty --keyword values.")
    if len({keyword.casefold() for keyword in cleaned_keywords}) != len(cleaned_keywords):
        raise click.UsageError("Keywords must be unique.")
    if not 1 <= len(cleaned_markets) <= 2 or len(cleaned_markets) != len(markets):
        raise click.UsageError("Provide one or two non-empty --market values.")
    if any(not re.fullmatch(r"[A-Z]{2}(?:-[A-Z0-9]{1,6}){0,2}", market) for market in cleaned_markets):
        raise click.UsageError("Invalid --market: use a two-letter country code, optionally with region suffixes.")
    if len(set(cleaned_markets)) != len(cleaned_markets):
        raise click.UsageError("Markets must be unique.")
    if output_format == "watch-json" and allow_partial:
        raise click.UsageError("--allow-partial cannot be used with --format watch-json.")
    if output_format == "watch-json" and (len(cleaned_keywords) != 1 or len(cleaned_markets) != 1):
        raise click.UsageError("Watch evidence needs exactly one keyword and one market.")
    if watch_evidence_file is not None:
        if output_format != "watch-json":
            raise click.UsageError("--watch-evidence-file requires --format watch-json.")
        if watch_evidence_file.exists() or not watch_evidence_file.parent.is_dir():
            raise click.ClickException("Watch evidence destination must be a new file in an existing directory.")

    async def _build():
        providers = get_provider_set()
        display_timeframe = _brief_table_cell(" ".join(timeframe.split()))
        markets_output = []
        failed_markets = []
        if output_format == "markdown":
            click.echo("# TrendPulse Demand Brief evidence pack")
            click.echo()
            click.echo(f"Timeframe: **{display_timeframe}** | Google Trends property: **Google Search**")
            click.echo("Data source: **Google Trends** (https://trends.google.com/trends/)")
            click.echo()
            click.echo("> Google Trends values are normalized relative-interest indices, not absolute search volume. Compare terms within the same market request; do not compare index values directly across markets.")

        for index, market in enumerate(cleaned_markets):
            growth_failure = None
            try:
                raw_points = await providers.trends.get_trends(
                    keyword=cleaned_keywords,
                    source="google search",
                    geo=market,
                    timeframe=timeframe,
                )
                if output_format == "watch-json":
                    payload = _brief_watch_payload(raw_points, cleaned_keywords[0], market, timeframe)
                    if watch_evidence_file is None:
                        click.echo(payload, nl=False)
                    else:
                        try:
                            with watch_evidence_file.open("x", encoding="utf-8", newline="\n") as handle:
                                handle.write(payload)
                        except OSError as exc:
                            raise click.ClickException(f"Watch evidence file was not saved: {exc}") from exc
                        click.echo(f"Wrote Watch evidence to {watch_evidence_file}")
                    return
                invalid_points_container = not isinstance(raw_points, (list, tuple))
                points = [point for point in raw_points if isinstance(point, dict)] if not invalid_points_container else []
                malformed_points = len(raw_points) - len(points) if not invalid_points_container else 0
                dated_points = [
                    (point, _brief_observation_time(point.get("date"))) for point in points
                ]
                dated_points = [(point, when) for point, when in dated_points if when is not None]
                valid_interest_points = [
                    (point, when) for point, when in dated_points
                    if _brief_number(point.get("value"), interest=True) is not None
                ]
                if timeframe.strip().lower() == "today 12-m":
                    raw_growth_rows = _growth_from_trend_points(
                        [point for point, _ in valid_interest_points], cleaned_keywords, ["3M", "1Y"]
                    )
                else:
                    try:
                        raw_growth_rows = await providers.trends.get_growth(
                            keyword=cleaned_keywords,
                            source="google search",
                            percent_growth=["3M", "1Y"],
                            geo=market,
                        )
                    except ProviderError as exc:
                        if not allow_partial:
                            raise
                        growth_failure = exc
                        raw_growth_rows = []
            except ProviderError as exc:
                if not allow_partial:
                    raise
                public_error = json.loads(exc.public_message)
                failed_markets.append({
                    "market": market,
                    "code": public_error["code"],
                    "retryable": public_error["retryable"],
                    "message": public_error["message"],
                })
                if output_format == "markdown":
                    click.echo(f"\n## {market}\n\n> **UNAVAILABLE ({exc.code.value})**: {public_error['message']} No observations are reported for this market.")
                if exc.code == ProviderErrorCode.RATE_LIMITED:
                    # A rate limit is a stop signal, not permission to try another market.
                    for skipped in cleaned_markets[index + 1:]:
                        skipped_message = "Not queried after the provider rate limit; no observations are available."
                        failed_markets.append({
                            "market": skipped,
                            "code": "not_attempted_due_to_rate_limit",
                            "retryable": True,
                            "message": skipped_message,
                        })
                        if output_format == "markdown":
                            click.echo(f"\n## {skipped}\n\n> **NOT ATTEMPTED**: {skipped_message}")
                    break
                continue
            stop_after_market = bool(
                growth_failure and growth_failure.code == ProviderErrorCode.RATE_LIMITED
            )
            growth_warning = None
            if growth_failure is not None:
                public_error = json.loads(growth_failure.public_message)
                failed_markets.append({
                    "market": market,
                    "component": "growth",
                    "code": public_error["code"],
                    "retryable": public_error["retryable"],
                    "message": public_error["message"],
                })
                growth_warning = (
                    f"Growth unavailable ({public_error['code']}): {public_error['message']} "
                    "Available primary Trends observations were retained."
                )
                if stop_after_market:
                    for skipped in cleaned_markets[index + 1:]:
                        failed_markets.append({
                            "market": skipped,
                            "code": "not_attempted_due_to_rate_limit",
                            "retryable": True,
                            "message": "Not queried after the provider rate limit; no observations are available.",
                        })
            invalid_growth_container = not isinstance(raw_growth_rows, (list, tuple))
            growth_rows = (
                [
                    row for row in raw_growth_rows
                    if isinstance(row, dict)
                    and isinstance(row.get("keyword"), str)
                    and isinstance(row.get("growth"), dict)
                ]
                if not invalid_growth_container else []
            )
            malformed_growth_rows = (
                len(raw_growth_rows) - len(growth_rows) if not invalid_growth_container else 0
            )

            series = defaultdict(list)
            for point, when in valid_interest_points:
                series[str(point.get("keyword", ""))].append((when, point))
            growth = {
                str(row.get("keyword", "")): row.get("growth") or {}
                for row in growth_rows
            }
            validated_series = {
                keyword: [
                    entry for entry in series.get(keyword, [])
                    if _brief_number(entry[1].get("value"), interest=True) is not None
                ]
                for keyword in cleaned_keywords
            }
            latest_trends_point = max(
                (when for keyword in cleaned_keywords for when, _ in validated_series[keyword]),
                key=lambda when: when[0], default=None,
            )
            latest_trends_date = latest_trends_point[1] if latest_trends_point else None
            missing_primary_keywords = [
                keyword for keyword in cleaned_keywords if not validated_series[keyword]
            ]

            if output_format == "json":
                warnings = []
                if invalid_points_container:
                    warnings.append("Google Trends returned an invalid observation container; no series observations were usable.")
                elif malformed_points:
                    warnings.append(f"Excluded {malformed_points} malformed Trends rows.")
                skipped_dates = len(points) - len(dated_points)
                if skipped_dates:
                    warnings.append(f"Excluded {skipped_dates} Trends observations with invalid dates.")
                for keyword in missing_primary_keywords:
                    warnings.append(
                        f"{keyword}: no validated primary Google Trends interest observations in {market}; "
                        "separate growth values do not replace primary evidence."
                    )
                skipped_indices = len(dated_points) - len(valid_interest_points)
                if skipped_indices:
                    noun = "observation" if skipped_indices == 1 else "observations"
                    warnings.append(f"Excluded {skipped_indices} Trends {noun} with invalid relative-interest indices.")
                if timeframe.strip().lower() != "today 12-m":
                    warnings.append("3M and 1Y growth use separate Google Trends lookback requests, not the selected timeframe time series.")
                if invalid_growth_container:
                    warnings.append("Google Trends returned an invalid growth response; growth values are unavailable.")
                elif malformed_growth_rows:
                    warnings.append(f"Excluded {malformed_growth_rows} malformed growth entries.")
                if growth_warning:
                    warnings.append(growth_warning)
                keyword_evidence = []
                for keyword in cleaned_keywords:
                    latest_point = max(
                        validated_series[keyword] or series.get(keyword, []),
                        key=lambda entry: entry[0][0], default=None,
                    )
                    last_date = latest_point[0][1] if latest_point else None
                    if latest_point and latest_trends_point and latest_point[0][0] < latest_trends_point[0]:
                        warnings.append(f"{keyword}: latest observation {last_date} is older than market latest {latest_trends_date}.")
                    keyword_growth = growth.get(keyword, {})
                    keyword_evidence.append({
                        "keyword": keyword,
                        "latest_index": _brief_number(latest_point[1].get("value"), interest=True) if latest_point else None,
                        "latest_observation": last_date,
                        "growth_3m_pct": _brief_number(keyword_growth.get("3M")),
                        "growth_1y_pct": _brief_number(keyword_growth.get("1Y")),
                    })
                markets_output.append({
                    "market": market,
                    "latest_complete_trends_point": latest_trends_date,
                    "growth_basis": "selected_timeframe" if timeframe.strip().lower() == "today 12-m" else "separate_lookback_requests",
                    "keywords": keyword_evidence,
                    "warnings": warnings,
                })
                if stop_after_market:
                    break
                continue

            click.echo()
            click.echo(f"## {market}")
            if invalid_points_container:
                click.echo()
                click.echo("> Google Trends returned an invalid observation container; no series observations were usable.")
            elif malformed_points:
                click.echo()
                click.echo(f"> Excluded {malformed_points} malformed Trends rows from this evidence table.")
            skipped_dates = len(points) - len(dated_points)
            if skipped_dates:
                click.echo()
                noun = "observation" if skipped_dates == 1 else "observations"
                click.echo(f"> Excluded {skipped_dates} Trends {noun} with invalid dates from this evidence table.")
            for keyword in missing_primary_keywords:
                click.echo()
                click.echo(
                    f"> {_brief_table_cell(keyword)}: no validated primary Google Trends "
                    f"interest observations in {market}; separate growth values do not "
                    "replace primary evidence."
                )
            skipped_indices = len(dated_points) - len(valid_interest_points)
            if skipped_indices:
                click.echo()
                noun = "observation" if skipped_indices == 1 else "observations"
                click.echo(f"> Excluded {skipped_indices} Trends {noun} with invalid relative-interest indices from this evidence table.")
            if timeframe.strip().lower() != "today 12-m":
                click.echo()
                click.echo(
                    f"> 3M and 1Y growth use separate Google Trends lookback requests; "
                    f"they are not calculated from the selected {display_timeframe} time series."
                )
            if invalid_growth_container:
                click.echo()
                click.echo("> Google Trends returned an invalid growth response; growth values are unavailable.")
            elif malformed_growth_rows:
                click.echo()
                click.echo(f"> Excluded {malformed_growth_rows} malformed growth entries from this evidence table.")
            if growth_warning:
                click.echo()
                click.echo(f"> {growth_warning}")
            if latest_trends_date:
                click.echo()
                click.echo(f"Latest complete Trends point: **{latest_trends_date}**")
            click.echo()
            click.echo("| Keyword | Latest index | 3M growth | 1Y growth |")
            click.echo("| --- | ---: | ---: | ---: |")
            older_observations = []
            for keyword in cleaned_keywords:
                keyword_points = series.get(keyword, [])
                latest_point = max(
                    validated_series[keyword] or keyword_points,
                    key=lambda entry: entry[0][0], default=None,
                )
                latest = latest_point[1].get("value") if latest_point else None
                last_date = latest_point[0][1] if latest_point else ""
                if (
                    latest_point
                    and latest_trends_point
                    and latest_point[0][0] < latest_trends_point[0]
                ):
                    older_observations.append((keyword, last_date))
                keyword_growth = growth.get(keyword, {})
                click.echo(
                    f"| {_brief_table_cell(keyword)} | {_brief_value(latest)} | {_brief_percent(keyword_growth.get('3M'))} | {_brief_percent(keyword_growth.get('1Y'))} |"
                )
            if older_observations:
                click.echo()
                click.echo("> Some latest keyword indices are older than the newest market observation:")
                for keyword, last_date in older_observations:
                    click.echo(
                        f"> {_brief_table_cell(keyword)}: last observation **{last_date}** "
                        f"(market latest **{latest_trends_date}**)"
                    )
            if stop_after_market:
                for skipped in cleaned_markets[index + 1:]:
                    click.echo(
                        f"\n## {skipped}\n\n> **NOT ATTEMPTED**: "
                        "Not queried after the provider rate limit; no observations are available."
                    )
                break

        if output_format == "json":
            payload = {
                "schema_version": 1,
                "source": "Google Trends",
                "source_url": "https://trends.google.com/trends/",
                "property": "Google Search",
                "timeframe": " ".join(timeframe.split()),
                "comparability_note": "Google Trends indices are normalized relative interest, not absolute search volume. Compare terms only within each market request; do not compare indices directly across markets.",
                "markets": markets_output,
            }
            if failed_markets:
                payload["incomplete"] = True
                payload["failed_markets"] = failed_markets
            click.echo(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2))
        elif failed_markets:
            click.echo()
            click.echo(
                f"> **INCOMPLETE EVIDENCE:** {len(failed_markets)} failed or unattempted "
                f"market components across {len(cleaned_markets)} requested markets. "
                "Do not use as a complete Demand Brief."
            )
        if failed_markets:
            raise click.exceptions.Exit(1)

    try:
        asyncio.run(_build())
    except ProviderError as exc:
        # Preserve the provider's public retry guidance without a raw CLI traceback.
        public_error = json.loads(exc.public_message)
        raise click.ClickException(
            f"{public_error['code']}: {public_error['message']}"
        ) from exc


def _brief_observation_time(value):
    """Return UTC ordering time and a date- or timestamp-precision evidence label."""
    text = str(value or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[T ].+)?", text):
        return None
    try:
        if len(text) == 10:
            return datetime.fromisoformat(text).replace(tzinfo=timezone.utc), text
        instant = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if instant.tzinfo is None:
            # Google may emit naive intraday labels: retain their unspecified zone in output.
            return instant.replace(tzinfo=timezone.utc), instant.isoformat()
        utc_instant = instant.astimezone(timezone.utc)
        return utc_instant, utc_instant.isoformat().replace("+00:00", "Z")
    except ValueError:
        return None


def _brief_watch_payload(raw_points, keyword, market, timeframe):
    """Produce strict date-only, single-series evidence for offline manual Watch."""
    from mcp_trendpulse.trend_watch import MAX_EVIDENCE_BYTES, MAX_POINTS, parse_evidence

    if not isinstance(raw_points, (list, tuple)) or not 0 < len(raw_points) <= MAX_POINTS:
        raise click.ClickException("Watch evidence needs 1-520 date-only Trends observations.")
    points = []
    for point in raw_points:
        if not isinstance(point, dict) or point.get("keyword") != keyword:
            raise click.ClickException("Watch evidence contains an invalid or different keyword series.")
        when = point.get("date")
        if not isinstance(when, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", when) is None:
            raise click.ClickException("Watch evidence requires ISO calendar dates; hourly timestamps cannot be converted silently.")
        value = _brief_number(point.get("value"), interest=True)
        if value is None:
            raise click.ClickException("Watch evidence contains an invalid normalized interest score.")
        partial = point.get("isPartial", False)
        if not isinstance(partial, bool):
            raise click.ClickException("Watch evidence has an invalid isPartial marker.")
        record = {"date": when, "value": value}
        if partial:
            record["isPartial"] = True
        points.append(record)
    points.sort(key=lambda row: row["date"])
    payload = json.dumps({
        "keyword": keyword,
        "market": market,
        "source": "Google Trends",
        "source_url": "https://trends.google.com/trends/",
        "property": "Google Search",
        "timeframe": " ".join(timeframe.split()),
        "points": points,
    }, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    encoded = payload.encode("utf-8")
    if len(encoded) > MAX_EVIDENCE_BYTES:
        raise click.ClickException("Watch evidence exceeds the 256 KiB offline input limit.")
    try:
        parse_evidence(encoded, keyword=keyword, market=market)
    except ValueError as exc:
        raise click.ClickException(f"Watch evidence is not usable: {exc}") from exc
    return payload


def _brief_table_cell(value):
    """Render literal keyword text without changing Markdown table structure."""
    text = html.escape(str(value), quote=False).replace("\r", " ").replace("\n", " ")
    for marker in ("\\", "|", "*", "_", "`", "[", "]", "~"):
        text = text.replace(marker, "\\" + marker)
    return text


def _brief_number(value, *, interest=False):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(number) or (interest and not 0 <= number <= 100):
        return None
    return number


def _brief_value(value):
    number = _brief_number(value, interest=True)
    if number is None:
        return "n/a"
    return f"{number:g}"


def _brief_percent(value):
    number = _brief_number(value)
    if number is None:
        return "n/a"
    return f"{number:+.2f}%"


def print_rss_headlines(items):
    """Print genuine RSS metadata without treating headlines as full articles."""
    for item in items:
        meta = item.get("meta_data") or {}
        if meta.get("content_level") != "rss_headline_only" or meta.get("source") != "google_news_rss":
            raise click.ClickException("Unexpected RSS headline evidence level.")
        click.echo(f"Title: {item['title']}")
        click.echo(f"Google News URL: {item['url']}")
        click.echo(f"Publisher: {item.get('meta_site_name') or 'Unknown'}")
        click.echo(f"Publish Date: {item['publish_date']}")
        click.echo("Content level: rss_headline_only (metadata, not article text)\n")


def _article_export_filename(article):
    title = str(article.title or "article")
    safe_title = re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("._")[:48] or "article"
    identity = str(article.original_url or title)
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
    return f"{safe_title}-{digest}.json"


def print_articles(articles, *, export_dir=None):
    paths = []
    if export_dir is not None:
        paths = [Path(export_dir) / _article_export_filename(article) for article in articles]
        if len(paths) != len(set(paths)):
            raise click.ClickException("Duplicate article URLs in this result; no JSON files were written.")
        for path in paths:
            if path.exists():
                raise click.ClickException(f"Article JSON already exists; refusing to overwrite: {path}")

    for index, article in enumerate(articles):
        click.echo(f"Title: {article.title}")
        click.echo(f"URL: {article.original_url}")
        click.echo(f"Authors: {article.authors}")
        click.echo(f"Publish Date: {article.publish_date}")
        click.echo(f"Top Image: {article.top_image}")
        click.echo(f"Summary: {article.summary}\n")
        if export_dir is not None:
            path = paths[index]
            try:
                save_article_to_json(article, str(path), fail_if_exists=True, raise_on_error=True)
            except (OSError, TypeError) as exc:
                raise click.ClickException(f"Article JSON was not saved to {path}: {exc}") from exc



@cli.group(
    "intelligence",
    help="Opt-in free-only public intelligence. No paid providers or background polling.",
)
def intelligence():
    """Bounded public-source discovery and offline opportunity research."""


@intelligence.command("signal-schema")
@click.option("--format", "output_format",
              type=click.Choice(["text", "json"]), default="text",
              show_default=True)
def intelligence_signal_schema(output_format):
    """Show the no-network, site-independent M00 evidence schema."""
    from mcp_trendpulse.intelligence_signal import signal_contract_spec

    contract = signal_contract_spec()
    if output_format == "json":
        click.echo(json.dumps(contract, ensure_ascii=False, sort_keys=True))
        return
    click.echo("TrendPulse signal contract v1 (offline; no provider request)")
    click.echo("Site property required: no | New providers: no")
    click.echo("Country null means unknown source scope, NOT global coverage.")
    click.echo("Missing/unavailable or generated-keyword values stay null, NOT zero.")
    click.echo("Source metric types and units:")
    for metric, props in contract["metric_types"].items():
        click.echo(f"  {metric}: {props['unit']} [{props['evidence_class']}]")
    click.echo("Use --format json to inspect the versioned Pydantic JSON Schema.")


@intelligence.command("cluster-keywords")
@click.option("--input", "input_file", type=click.Path(
    exists=True, dir_okay=False, path_type=Path), required=True,
    help="Local JSON with signal list or M01 RSS result; strictly offline.")
@click.option("--threshold", type=click.FloatRange(90, 100),
              default=95.0, show_default=True)
@click.option("--format", "output_format", type=click.Choice(["text", "json"]),
              default="text", show_default=True)
def intelligence_cluster_keywords(input_file, threshold, output_format):
    """Lexically cluster up to 200 existing sourced keyword signals offline."""
    from mcp_trendpulse.intelligence_keywords import cluster_keyword_signals

    try:
        if input_file.stat().st_size > 128 * 1024:
            raise ValueError("Input JSON cannot exceed 128 KiB")
        payload = json.loads(input_file.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and payload.get("mode") == (
            "google_trending_now_public_rss_source_attributed"
        ):
            signals = [row["signal"] for row in payload["trends"]]
        elif isinstance(payload, list):
            signals = payload
        else:
            raise ValueError("Expected a list of TrendSignals or M01 RSS result")
        report = cluster_keyword_signals(signals, similarity_threshold=threshold)
    except (OSError, UnicodeError, ValueError, KeyError, TypeError,
            json.JSONDecodeError) as exc:
        # Never echo arbitrary JSON payloads or file contents in CLI errors.
        raise click.ClickException(
            "Keyword clustering input is invalid, unsupported or too large"
            if not isinstance(exc, ValueError) or "Expected a list" not in str(exc)
            else "Expected a list of TrendSignals or M01 RSS result"
        ) from None

    if output_format == "json":
        click.echo(json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True))
    else:
        click.echo(
            f"Offline lexical keyword clusters: {report['cluster_count']} "
            f"from {report['input_records']} sourced records"
        )
        click.echo("No network; no semantic-equivalence or search-volume aggregation.")
        for group in report["clusters"]:
            click.echo(
                f"- {group['representative']} "
                f"[{group['country'] or 'unknown'}/"
                f"{group['language'] or 'unknown language'}] "
                f"({len(group['members'])} source terms)"
            )


@intelligence.command("trending-now")
@click.option("--geo", type=str, default="US", show_default=True,
              help="Source-supported uppercase country code, e.g. US, GB, SI.")
@click.option("--execute", is_flag=True,
              help="Opt in to one capped live Google Trending Now RSS request, or cached result.")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]),
              default="text", show_default=True)
def intelligence_trending_now(geo, execute, output_format):
    """Country-scoped public Trending Now RSS using the existing TrendSpy provider."""
    from mcp_trendpulse.intelligence_rss import (
        discover_trending_rss, format_rss_report,
    )

    try:
        result = asyncio.run(discover_trending_rss(geo, execute=execute))
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    if output_format == "json":
        click.echo(json.dumps(result, ensure_ascii=False, allow_nan=False, sort_keys=True))
    else:
        click.echo(format_rss_report(result))


@intelligence.command("sources")
@click.option("--wave", type=click.IntRange(1, 3), default=None)
def intelligence_sources(wave):
    """List supported sources, access conditions and evidence limitations."""
    from mcp_trendpulse.intelligence_core import source_catalog

    sources = source_catalog()
    if wave is not None:
        sources = [item for item in sources if item["wave"] == wave]
    click.echo(json.dumps(sources, ensure_ascii=False, sort_keys=True))



@intelligence.command("discover")
@click.option("--lookback-days", type=click.IntRange(7, 90), default=30,
              show_default=True, help="Look at recent public-source publication dates.")
@click.option("--limit", type=click.IntRange(2, 20), default=12,
              show_default=True, help="Total TED cap; each other provider uses the same cap.")
@click.option("--ted-date-slices", type=click.Choice(["1", "3"]), default="1",
              show_default=True, help="Opt-in 3 separate TED date windows (5 source "
                                      "requests instead of 3; total TED cap unchanged).")
@click.option("--measure-trends", is_flag=True,
              help="Opt in to compare up to two auto-discovered OpenAlex topics "
                   "across three prior periods (up to 9 extra free requests).")
@click.option("--broad-topic-scan", is_flag=True,
              help="With --measure-trends, compare top 100 OpenAlex topic groups "
                   "across three periods and verify at most two history gaps "
                   "(up to 9 more bounded free requests).")
@click.option("--corroborate-issues", is_flag=True,
              help="Optional two-period public GitHub issue phrase-count checks "
                   "for up to two source-measured topics, including strictly "
                   "qualified inconclusive signals (max 4 free requests); "
                   "not validated customer problems or market growth.")
@click.option("--cross-source-hunt", is_flag=True,
              help="Opt in to existing CORDIS + USAspending context checks using up "
                   "to two source-measured research topics, including strictly "
                   "qualified inconclusive signals (max 4 extra free "
                   "requests); not verified market demand.")
@click.option("--workflow-briefs", is_flag=True,
              help="Offline source-attributed IT procurement and repeated consumer "
                   "problem investigations; exact lexical research links only, "
                   "no new API calls or invented commercial demand.")
@click.option("--ted-software-scan", is_flag=True,
              help="With --workflow-briefs, opt in to one CPV 48/72-filtered"
                   " official TED search (12-row cap); independent of the"
                   " unbiased baseline and not market prevalence.")
@click.option("--workflow-cross-check", is_flag=True,
              help="With --workflow-briefs, query existing free GitHub Issues and "
                   "USAspending for up to two phrases extracted from published "
                   "workflow clues (max 4 extra requests). No demand proof.")
@click.option("--ted-scope-details", is_flag=True,
              help="With --workflow-briefs, explicitly inspect published procedure "
                   "and lot text for at most two original TED notices (max 2 extra "
                   "free requests); no lot-to-budget inference.")
@click.option("--ted-related-notices", is_flag=True,
              help="With --ted-scope-details, find related TED notices using exact "
                   "source-published procedure UUIDs (max 2 more free searches); "
                   "newer notices trigger manual scope revalidation.")
@click.option("--idea-map", is_flag=True,
              help="With --workflow-briefs, synthesize source-backed product "
                   "hypotheses and keyword validation queues offline; no extra API "
                   "requests or invented search volumes.")
@click.option("--keyword-probe", is_flag=True,
              help="With --idea-map and --execute, opt in to at most two existing "
                   "unofficial Google Trends related-query provider operations per "
                   "local UTC day; rate limits and absence of volume caveats apply.")
@click.option("--keyword-evidence-file", type=click.Path(
              exists=True, dir_okay=False, path_type=Path), default=None,
              help="Optional local normalized Google Trends-style series JSON "
                   "for an exact keyword+country match in --idea-map; never fetched.")
@click.option("--execute", is_flag=True,
              help="Explicitly fetch fixed public free sources; otherwise plan only.")
@click.option("--record-history", is_flag=True,
              help="Store hashes of discovered candidates locally (requires --execute).")
@click.option("--record-idea-history", is_flag=True,
              help="With --execute and --idea-map, opt into a local 90-day source"
                   " sighting ledger (official URLs/labels only); prior-only"
                   " leads require revalidation, not active market claims.")
@click.option("--format", "output_format", type=click.Choice(["json", "text"]),
              default="json", show_default=True)
def intelligence_discover(lookback_days, limit, ted_date_slices, measure_trends,
                          broad_topic_scan, corroborate_issues,
                          cross_source_hunt, workflow_briefs, ted_software_scan,
                          workflow_cross_check, ted_scope_details, ted_related_notices,
                          idea_map, keyword_probe,
                          keyword_evidence_file, execute, record_history,
                          record_idea_history, output_format):
    """Discover current source themes without any predefined topic keywords."""
    from mcp_trendpulse.intelligence_discovery import (
        discover_current, format_discovery_report, record_discovery_history,
    )

    try:
        if record_history and not execute:
            raise ValueError("--record-history requires --execute")
        if record_idea_history and (not execute or not idea_map):
            raise ValueError("--record-idea-history requires --execute --idea-map")
        if keyword_evidence_file is not None and not idea_map:
            raise ValueError("--keyword-evidence-file requires --idea-map")
        parsed_keyword_evidence = None
        if keyword_evidence_file is not None:
            from mcp_trendpulse.intelligence_idea_map import MAX_EVIDENCE_BYTES

            if keyword_evidence_file.stat().st_size > MAX_EVIDENCE_BYTES:
                raise ValueError("Keyword evidence exceeds 64 KiB")
            parsed_keyword_evidence = json.loads(
                keyword_evidence_file.read_text(encoding="utf-8")
            )
        response = discover_current(
            lookback_days=lookback_days, limit=limit, execute=execute,
            ted_date_slices=int(ted_date_slices), measure_trends=measure_trends,
            broad_topic_scan=broad_topic_scan,
            corroborate_issues=corroborate_issues,
            cross_source_hunt=cross_source_hunt,
            workflow_briefs=workflow_briefs,
            ted_software_scan=ted_software_scan,
            workflow_cross_check=workflow_cross_check,
            ted_scope_details=ted_scope_details,
            ted_related_notices=ted_related_notices,
            idea_map=idea_map,
            keyword_probe=keyword_probe,
            keyword_evidence=parsed_keyword_evidence,
        )
        if record_history:
            response["history"] = record_discovery_history(response)
        if record_idea_history:
            from mcp_trendpulse.intelligence_idea_history import (
                record_idea_history as save_idea_history,
            )

            status_by_source = {
                row["source"]: (
                    "observed" if row.get("status") == "observed"
                    else "unavailable"
                )
                for row in response.get("source_coverage", [])
                if isinstance(row, dict)
                and row.get("source") in {"ted", "cfpb"}
            }
            # A successful focused TED page establishes source access even
            # when the separate sector-neutral TED windows were unavailable.
            focused = response.get("targeted_software_scan")
            if (isinstance(focused, dict)
                    and isinstance(focused.get("status"), str)
                    and focused["status"].startswith("source_observed_")):
                status_by_source["ted"] = "observed"
            response["idea_history"] = save_idea_history(
                response["idea_map"], source_status=status_by_source,
            )
    except (OSError, ValueError, TypeError) as exc:
        raise click.ClickException(str(exc)) from exc
    if output_format == "text" and execute:
        click.echo(format_discovery_report(response))
    else:
        click.echo(json.dumps(response, ensure_ascii=False, sort_keys=True))


@intelligence.command("hunt")
@click.option("--topic", "topics", multiple=True,
              help="Repeat up to four research seed topics; rotates defaults if omitted.")
@click.option("--source", "sources", multiple=True,
              help="Repeat up to five approved source IDs; keyless defaults if omitted.")
@click.option("--lookback-days", type=click.IntRange(7, 90), default=30,
              show_default=True)
@click.option("--execute", is_flag=True,
              help="Explicitly perform bounded, free, read-only source requests.")
@click.option("--record-history", is_flag=True,
              help="Opt in to local metadata-only SQLite history (requires --execute).")
@click.option("--format", "output_format", type=click.Choice(["json", "text"]),
              default="json", show_default=True)
def intelligence_hunt(topics, sources, lookback_days, execute, record_history,
                      output_format):
    """Rank fresh public-source observations without requiring a historical baseline."""
    from mcp_trendpulse.intelligence_hunter import (
        format_hunt_report, hunt_current, record_hunt_history,
    )

    try:
        if record_history and not execute:
            raise ValueError("--record-history requires --execute")
        result = hunt_current(
            list(topics) if topics else None,
            list(sources) if sources else None,
            lookback_days=lookback_days,
            execute=execute,
        )
        if record_history:
            result["history"] = record_hunt_history(result)
    except (OSError, ValueError, TypeError) as exc:
        raise click.ClickException(str(exc)) from exc
    if output_format == "text" and execute:
        click.echo(format_hunt_report(result))
    else:
        click.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))


@intelligence.command("observe")
@click.option("--input-json", "input_path", required=True,
              type=click.Path(exists=True, dir_okay=False, path_type=Path))
def intelligence_observe(input_path):
    """Audit prior collector snapshots; identify registered entities and dates."""
    from mcp_trendpulse.intelligence_observations import observe_source_snapshots

    try:
        if input_path.stat().st_size > 220_000:
            raise ValueError("Observation batch exceeds 220 KB")
        request = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(request, dict):
            raise ValueError("Observation input must be a JSON object")
        response = observe_source_snapshots(
            request["topic"], request["snapshots"], as_of=request.get("as_of")
        )
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(response, ensure_ascii=False, sort_keys=True))


@intelligence.group("opportunities")
def intelligence_opportunities_group():
    """Offline, source-attributed opportunity triage and dated backtesting."""


@intelligence_opportunities_group.command("lanes")
def intelligence_opportunities_lanes():
    """List valid source combinations without requesting remote data."""
    from mcp_trendpulse.intelligence_opportunities import lane_catalog

    click.echo(json.dumps(lane_catalog(), ensure_ascii=False, sort_keys=True))


@intelligence_opportunities_group.command("evaluate")
@click.option("--input-json", "input_path", required=True,
              type=click.Path(exists=True, dir_okay=False, path_type=Path))
def intelligence_opportunities_evaluate(input_path):
    """Rank investigation priorities from bounded, attributable JSON records."""
    from mcp_trendpulse.intelligence_opportunities import evaluate_opportunities

    try:
        if input_path.stat().st_size > 180_000:
            raise ValueError("Opportunity file exceeds 180 KB")
        request = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(request, dict):
            raise ValueError("Opportunity file must contain a JSON object")
        response = evaluate_opportunities(
            request["candidates"], request["evidence"],
            as_of=request.get("as_of"),
            source_health=request.get("source_health"),
            daily_trends=request.get("daily_trends"),
        )
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(response, ensure_ascii=False, sort_keys=True))


@intelligence_opportunities_group.command("backtest")
@click.option("--input-json", "input_path", required=True,
              type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--k", type=click.IntRange(1, 10), default=3, show_default=True)
def intelligence_opportunities_backtest(input_path, k):
    """Review dated past decisions against externally attested future outcomes."""
    from mcp_trendpulse.intelligence_backtest import walk_forward_evaluation

    try:
        if input_path.stat().st_size > 180_000:
            raise ValueError("Backtest file exceeds 180 KB")
        samples = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(samples, list):
            raise ValueError("Backtest requires a list of historical examples")
        result = walk_forward_evaluation(samples, k=k)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))



@intelligence.command("query")
@click.option("--source", required=True, help="Exact source ID from intelligence sources.")
@click.option("--keyword", default="", help="Public search phrase or TED expert query.")
@click.option("--company", default="", help="Known public hiring-board slug.")
@click.option("--dataset", default="", help="Eurostat dataset code.")
@click.option("--country", default="", help="ISO two-letter country code.")
@click.option("--identifier", default="", help="Source-specific public series/CIK/EIC/route ID.")
@click.option("--limit", type=click.IntRange(1, 20), default=10, show_default=True)
@click.option("--execute", is_flag=True, help="Explicitly perform one bounded read-only request.")
@click.option("--timeout", type=click.IntRange(2, 30), default=12, show_default=True,
              help="Per-request connection/read timeout in seconds; no retries.")
def intelligence_query(source, keyword, company, dataset, country, identifier,
                       limit, execute, timeout):
    """Print a safe query plan by default, or fetch once with --execute."""
    from mcp_trendpulse.intelligence_core import IntelligenceError, collect, plan_source

    try:
        plan = plan_source(
            source, keyword=keyword, company=company,
            dataset=dataset, country=country, identifier=identifier, limit=limit,
        )
        result = collect(plan, fetch=execute, timeout=timeout)
    except (IntelligenceError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))



@intelligence.group("settings")
def intelligence_settings():
    """Inspect optional provider settings and securely configure the local user."""


@intelligence_settings.command("status")
@click.argument("provider", required=False)
def intelligence_settings_status(provider):
    """Report which free credentials are present, without revealing values."""
    from mcp_trendpulse.intelligence_settings import provider_status

    try:
        result = provider_status(provider)
    except (ValueError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))


@intelligence_settings.command("guide")
@click.argument("provider")
def intelligence_settings_guide(provider):
    """Explain provider registration and local setup without collecting keys."""
    from mcp_trendpulse.intelligence_settings import setup_instructions

    try:
        result = setup_instructions(provider)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))


@intelligence_settings.command("set-key")
@click.argument("provider")
def intelligence_settings_set_key(provider):
    """Hidden terminal input into Windows Credential Manager; never into chat."""
    from mcp_trendpulse.intelligence_settings import (
        PROVIDERS, SecureStoreUnavailable, save_provider_credentials,
        _supports_native_store,
    )

    if provider not in PROVIDERS:
        raise click.ClickException("Unknown provider; run intelligence settings status")
    if not _supports_native_store():
        raise click.ClickException(
            "Native secure storage is Windows-only. Supply credentials via your MCP "
            "client's secure environment-variable settings on this platform."
        )
    click.echo("Only this local terminal accepts your credentials, not the LLM.")
    values = {}
    for field in PROVIDERS[provider]["fields"]:
        values[field] = click.prompt(field, hide_input=True, confirmation_prompt=False)
    try:
        save_provider_credentials(provider, values)
    except (ValueError, OSError, SecureStoreUnavailable) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"{provider}: stored in Windows Credential Manager (values hidden).")
    click.echo("Restart the optional intelligence MCP to load updated settings.")


@intelligence_settings.command("remove-key")
@click.argument("provider")
def intelligence_settings_remove_key(provider):
    """Delete the local provider credentials after explicit confirmation."""
    from mcp_trendpulse.intelligence_settings import (
        PROVIDERS, SecureStoreUnavailable, clear_provider_credentials,
    )

    if provider not in PROVIDERS:
        raise click.ClickException("Unknown provider")
    if not click.confirm(f"Remove {provider} credentials from your local store?", default=False):
        raise click.ClickException("No change made")
    try:
        clear_provider_credentials(provider)
    except (ValueError, OSError, SecureStoreUnavailable) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"{provider}: local credentials removed.")


@intelligence.command("jobs-analyze")
@click.option("--source", type=click.Choice(
    ["greenhouse", "lever", "ashby", "smartrecruiters"]), required=True)
@click.option("--company", required=True, help="Public employer/board slug.")
@click.option("--input-json", "input_path", type=click.Path(
    exists=True, dir_okay=False, path_type=Path), required=True)
def intelligence_jobs_analyze(source, company, input_path):
    """Extract sourced pain hypotheses from a local public job-board JSON export."""
    from mcp_trendpulse.intelligence_jobs import extract_job_pains, normalize_jobs

    try:
        if input_path.stat().st_size > 512 * 1024:
            raise ValueError("Input exceeds 512 KiB; split into bounded batches")
        response = json.loads(input_path.read_text(encoding="utf-8"))
        jobs = normalize_jobs(source, company, response)
        result = extract_job_pains(jobs)
    except (UnicodeError, json.JSONDecodeError, OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(result, ensure_ascii=False, sort_keys=True))

if __name__ == "__main__":
    cli()
