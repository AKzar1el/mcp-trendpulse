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
from mcp_trendpulse.errors import ProviderError
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
@click.option("--format", "output_format", type=click.Choice(["markdown", "json"]), default="markdown", show_default=True, help="Human-readable evidence or structured evidence for local report workflows.")
def brief_pack(keywords, markets, timeframe, output_format):
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

    async def _build():
        providers = get_provider_set()
        display_timeframe = _brief_table_cell(" ".join(timeframe.split()))
        markets_output = []
        if output_format == "markdown":
            click.echo("# TrendPulse Demand Brief evidence pack")
            click.echo()
            click.echo(f"Timeframe: **{display_timeframe}** | Google Trends property: **Google Search**")
            click.echo("Data source: **Google Trends** (https://trends.google.com/trends/)")
            click.echo()
            click.echo("> Google Trends values are normalized relative-interest indices, not absolute search volume. Compare terms within the same market request; do not compare index values directly across markets.")

        for market in cleaned_markets:
            raw_points = await providers.trends.get_trends(
                keyword=cleaned_keywords,
                source="google search",
                geo=market,
                timeframe=timeframe,
            )
            invalid_points_container = not isinstance(raw_points, (list, tuple))
            points = [point for point in raw_points if isinstance(point, dict)] if not invalid_points_container else []
            malformed_points = len(raw_points) - len(points) if not invalid_points_container else 0
            dated_points = [
                (point, _brief_observation_time(point.get("date"))) for point in points
            ]
            dated_points = [(point, when) for point, when in dated_points if when is not None]
            if timeframe.strip().lower() == "today 12-m":
                raw_growth_rows = _growth_from_trend_points(
                    [point for point, _ in dated_points], cleaned_keywords, ["3M", "1Y"]
                )
            else:
                raw_growth_rows = await providers.trends.get_growth(
                    keyword=cleaned_keywords,
                    source="google search",
                    percent_growth=["3M", "1Y"],
                    geo=market,
                )
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
            for point, when in dated_points:
                series[str(point.get("keyword", ""))].append((when, point))
            latest_trends_point = max(
                (when for _, when in dated_points), key=lambda when: when[0], default=None
            )
            latest_trends_date = latest_trends_point[1] if latest_trends_point else None
            growth = {
                str(row.get("keyword", "")): row.get("growth") or {}
                for row in growth_rows
            }

            if output_format == "json":
                warnings = []
                if invalid_points_container:
                    warnings.append("Google Trends returned an invalid observation container; no series observations were usable.")
                elif malformed_points:
                    warnings.append(f"Excluded {malformed_points} malformed Trends rows.")
                skipped_dates = len(points) - len(dated_points)
                if skipped_dates:
                    warnings.append(f"Excluded {skipped_dates} Trends observations with invalid dates.")
                if timeframe.strip().lower() != "today 12-m":
                    warnings.append("3M and 1Y growth use separate Google Trends lookback requests, not the selected timeframe time series.")
                if invalid_growth_container:
                    warnings.append("Google Trends returned an invalid growth response; growth values are unavailable.")
                elif malformed_growth_rows:
                    warnings.append(f"Excluded {malformed_growth_rows} malformed growth entries.")
                keyword_evidence = []
                for keyword in cleaned_keywords:
                    latest_point = max(series.get(keyword, []), key=lambda entry: entry[0][0], default=None)
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
            if latest_trends_date:
                click.echo()
                click.echo(f"Latest complete Trends point: **{latest_trends_date}**")
            click.echo()
            click.echo("| Keyword | Latest index | 3M growth | 1Y growth |")
            click.echo("| --- | ---: | ---: | ---: |")
            older_observations = []
            for keyword in cleaned_keywords:
                keyword_points = series.get(keyword, [])
                latest_point = max(keyword_points, key=lambda entry: entry[0][0], default=None)
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

        if output_format == "json":
            click.echo(json.dumps({
                "schema_version": 1,
                "source": "Google Trends",
                "source_url": "https://trends.google.com/trends/",
                "property": "Google Search",
                "timeframe": " ".join(timeframe.split()),
                "comparability_note": "Google Trends indices are normalized relative interest, not absolute search volume. Compare terms only within each market request; do not compare indices directly across markets.",
                "markets": markets_output,
            }, ensure_ascii=False, allow_nan=False, indent=2))

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


if __name__ == "__main__":
    cli()
