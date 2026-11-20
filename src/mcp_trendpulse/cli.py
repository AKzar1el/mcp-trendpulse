import asyncio
import csv
import hashlib
import html
import io
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


@cli.command("doctor", help="Inspect local settings offline without network calls or revealing secrets.")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text",
              show_default=True, help="Human-readable or structured redacted diagnostic report.")
@click.option("--strict", is_flag=True, help="Exit 2 if any static configuration issue is detected.")
def doctor(output_format, strict):
    """Inspect local Community and hosted settings; do not test provider reachability."""
    from mcp_trendpulse.diagnostics import format_doctor_text, inspect_local_configuration

    report = inspect_local_configuration()
    if output_format == "json":
        click.echo(json.dumps(report, indent=2, ensure_ascii=True))
    else:
        click.echo(format_doctor_text(report))
    if strict and report["issues"]:
        raise click.exceptions.Exit(2)


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
@click.option("--dry-run", is_flag=True, help="Preview the decision without recording an alert or consuming cooldown.")
def watch_evaluate(rule_id, evidence, dry_run):
    from mcp_trendpulse.trend_watch import MAX_EVIDENCE_BYTES, WatchStore

    try:
        if evidence.stat().st_size > MAX_EVIDENCE_BYTES:
            raise ValueError("Evidence file exceeds 256 KiB")
        store = WatchStore()
        payload = evidence.read_bytes()
        result = store.preview(rule_id, payload) if dry_run else store.evaluate_and_record(rule_id, payload)
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    if dry_run:
        click.echo(json.dumps({**asdict(result), "dry_run": True}, sort_keys=True))
    else:
        click.echo(result.as_json())


@watch.command("preview-all")
@click.option("--evidence", "evidence_files", type=click.Path(exists=True, dir_okay=False, path_type=Path),
              multiple=True, required=True, help="Repeat for up to 12 saved keyword/market series JSON files.")
@click.option("--format", "output_format", type=click.Choice(["json", "csv", "markdown"]), default="json",
              show_default=True, help="Offline multi-rule preview; never records alerts or cooldowns.")
@click.option("--output-file", type=click.Path(dir_okay=False, path_type=Path), default=None,
              help="Save a new UTF-8 preview file without overwriting an existing report.")
def watch_preview_all(evidence_files, output_format, output_file):
    """Preview all saved watches against supplied matching series without network calls."""
    from mcp_trendpulse.trend_watch import MAX_EVIDENCE_BYTES, WatchStore, evaluate_watch, parse_evidence

    try:
        if output_file is not None and (output_file.exists() or not output_file.parent.is_dir()):
            raise ValueError("Preview destination must be a new file in an existing directory")
        if len(evidence_files) > 12:
            raise ValueError("At most 12 evidence files may be reviewed at once")
        rules = WatchStore().list_rules()
        if not rules:
            raise ValueError("No saved watch rules to preview")
        if len(rules) > 100:
            raise ValueError("At most 100 saved watch rules may be previewed at once")
        known = {(rule.keyword, rule.market) for rule in rules}
        series = {}
        for path in evidence_files:
            if path.stat().st_size > MAX_EVIDENCE_BYTES:
                raise ValueError("Evidence file exceeds 256 KiB")
            payload = path.read_bytes()
            if len(payload) > MAX_EVIDENCE_BYTES:
                raise ValueError("Evidence file exceeds 256 KiB")
            try:
                envelope = json.loads(payload.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise ValueError("Evidence must be valid UTF-8 JSON") from exc
            if not isinstance(envelope, dict):
                raise ValueError("Evidence must include keyword, market and points")
            key = (envelope.get("keyword"), envelope.get("market"))
            if not all(isinstance(part, str) for part in key):
                raise ValueError("Evidence must declare a string keyword and market")
            if key in series:
                raise ValueError("Duplicate evidence keyword/market series")
            if key not in known:
                raise ValueError("Evidence has no matching saved watch rule")
            series[key] = parse_evidence(payload, keyword=key[0], market=key[1])
        results = []
        status_counts = {}
        for rule in rules:
            rows = series.get((rule.keyword, rule.market))
            if rows is None:
                decision = {"rule_id": rule.id, "status": "missing_evidence", "evidence_date": None,
                            "baseline_interest": None, "current_interest": None, "growth_pct": None,
                            "note": "No matching saved series supplied; not evaluated."}
            else:
                decision = asdict(evaluate_watch(rule, rows))
            status_counts[decision["status"]] = status_counts.get(decision["status"], 0) + 1
            results.append({**decision, "keyword": rule.keyword, "market": rule.market,
                            "evidence_present": rows is not None})
    except (OSError, ValueError, TypeError) as exc:
        raise click.ClickException(str(exc)) from exc

    note = ("User-supplied normalized Trends-style series are not independently verified. "
            "This dry-run does not record alerts, consume cooldowns, or fetch providers.")
    if output_format == "json":
        report = json.dumps({"dry_run": True, "source_verified": False, "note": note,
                             "status_counts": status_counts, "rules": results}, sort_keys=True)
    elif output_format == "markdown":
        from mcp_trendpulse.brief_review import _markdown_safe

        def render_group(title, items):
            lines.extend(["", f"## {title}", ""])
            if not items:
                lines.append("None in the supplied evidence.")
                return
            lines.extend([
                "| Rule | Keyword | Market | Decision | Evidence date | Current index | Growth |",
                "| --- | --- | --- | --- | --- | ---: | ---: |",
            ])
            for item in items:
                date_text = item["evidence_date"] or "not available"
                interest = item["current_interest"]
                growth = item["growth_pct"]
                lines.append(
                    f"| {_markdown_safe(item['rule_id'])} | {_markdown_safe(item['keyword'])} | "
                    f"{_markdown_safe(item['market'])} | {_markdown_safe(item['status'])} | "
                    f"{_markdown_safe(date_text)} | "
                    f"{interest if interest is not None else 'not available'} | "
                    f"{str(growth) + '%' if growth is not None else 'not available'} |"
                )

        lines = [
            "# Trend Watch batch preview (offline)",
            "",
            f"**Rules:** {len(results)}; **{status_counts.get('triggered', 0)} triggered**; "
            f"**{status_counts.get('missing_evidence', 0)} missing evidence**",
            "",
            "This is a dry run using user-supplied normalized Trends-style series that are "
            "not independently verified. It does not record alerts, consume cooldowns, "
            "fetch providers, or establish actual market demand.",
        ]
        render_group("Manual follow-up candidates", [
            item for item in results if item["status"] == "triggered"
        ])
        lines.extend(["", "Review these apparent threshold matches against independently "
                      "obtained source evidence and actual user needs before choosing a product."])
        render_group("Evidence gaps", [
            item for item in results if item["status"] == "missing_evidence"
        ])
        lines.extend(["", "Supply a matching saved keyword/market series before drawing conclusions; "
                      "missing evidence is not zero interest."])
        render_group("Other evaluated rules", [
            item for item in results if item["status"] not in ("triggered", "missing_evidence")
        ])
        lines.extend(["", "Below-threshold, stale, irregular, insufficient, duplicate, or cooldown "
                      "outcomes are not negative market forecasts. Do not compare normalized "
                      "indices across separately collected series."])
        report = "\n".join(lines)
    else:
        fields = ("rule_id", "keyword", "market", "status", "evidence_present", "evidence_date",
                  "baseline_interest", "current_interest", "growth_pct", "dry_run", "source_verified", "note")
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for item in results:
            row = {**item, "dry_run": True, "source_verified": False, "note": item["note"] + " " + note}
            writer.writerow({field: _brief_csv_cell(row.get(field)) for field in fields})
        report = output.getvalue()

    if output_file is None:
        click.echo(report, nl=output_format != "csv")
    else:
        saved_report = report if output_format == "csv" else report + "\n"
        _save_new_brief_report(output_file, saved_report, kind="preview", label="Trend Watch")


@watch.command("backtest")
@click.option("--id", "rule_id", required=True, help="Existing watch rule ID.")
@click.option("--evidence", type=click.Path(exists=True, dir_okay=False, path_type=Path), required=True)
@click.option("--growth-pct", type=click.FloatRange(1, 1000), default=None, help="Hypothetical growth threshold.")
@click.option("--minimum-interest", type=click.FloatRange(0, 100), default=None, help="Hypothetical minimum interest.")
@click.option("--window", type=click.IntRange(2, 12), default=None, help="Hypothetical comparison window.")
@click.option("--cooldown-days", type=click.IntRange(1, 90), default=None, help="Hypothetical alert cooldown.")
@click.option("--compare-baseline", is_flag=True, help="Show saved-policy and scenario alert-date differences.")
@click.option("--format", "output_format", type=click.Choice(["json", "csv"]), default="json",
              show_default=True, help="Structured JSON or spreadsheet-ready simulated alert dates.")
@click.option("--output-file", type=click.Path(dir_okay=False, path_type=Path), default=None,
              help="Save a new UTF-8 report file; existing files are never overwritten.")
def watch_backtest(rule_id, evidence, growth_pct, minimum_interest, window, cooldown_days,
                   compare_baseline, output_format, output_file):
    """Simulate historic threshold decisions offline without updating cooldown."""
    from mcp_trendpulse.trend_watch import MAX_EVIDENCE_BYTES, WatchStore

    try:
        if evidence.stat().st_size > MAX_EVIDENCE_BYTES:
            raise ValueError("Evidence file exceeds 256 KiB")
        result = WatchStore().backtest(
            rule_id, evidence.read_bytes(), growth_pct=growth_pct,
            minimum_interest=minimum_interest, window=window, cooldown_days=cooldown_days,
            compare_baseline=compare_baseline,
        )
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    report = _watch_backtest_csv(result) if output_format == "csv" else json.dumps(result, sort_keys=True)
    if output_file is None:
        click.echo(report, nl=output_format != "csv")
    else:
        _save_new_brief_report(output_file, report, kind="backtest", label="Trend Watch")


def _watch_backtest_csv(report):
    """Export one summary and a date-union of hypothetical alerts, never real alerts."""
    fields = (
        "row_type", "rule_id", "keyword", "market", "alert_date", "baseline_alert",
        "scenario_alert", "change", "baseline_evaluated_windows", "scenario_evaluated_windows",
        "baseline_alert_count", "scenario_alert_count", "delta_alert_count", "simulated", "note",
    )
    comparison = report.get("comparison")
    baseline = comparison["baseline"] if comparison is not None else None
    baseline_dates = set(baseline["simulated_alert_dates"]) if baseline is not None else set()
    scenario_dates = {alert["evidence_date"] for alert in report["simulated_alerts"]}
    common = {"rule_id": report["rule_id"], "keyword": report["keyword"], "market": report["market"]}
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
    writer.writeheader()

    def write(row):
        writer.writerow({field: _brief_csv_cell(row.get(field)) for field in fields})

    write({
        **common, "row_type": "summary",
        "baseline_evaluated_windows": baseline["evaluated_windows"] if baseline else "",
        "scenario_evaluated_windows": report["evaluated_windows"],
        "baseline_alert_count": len(baseline_dates) if baseline else "",
        "scenario_alert_count": len(scenario_dates),
        "delta_alert_count": comparison["alert_count_delta"] if comparison else "",
        "simulated": "true",
        "note": report["note"] + (" " + comparison["note"] if comparison else ""),
    })
    for alert_date in sorted(baseline_dates | scenario_dates):
        in_baseline = alert_date in baseline_dates
        in_scenario = alert_date in scenario_dates
        change = ""
        if comparison:
            change = "shared" if in_baseline and in_scenario else ("added" if in_scenario else "removed")
        write({
            **common, "row_type": "alert", "alert_date": alert_date,
            "baseline_alert": int(in_baseline) if baseline else "",
            "scenario_alert": int(in_scenario), "change": change,
            "simulated": "true",
        })
    return out.getvalue()


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
@click.option("--format", "headline_format", type=click.Choice(["text", "json", "csv"]), default="text",
              show_default=True, help="RSS headline output format; JSON/CSV require --headlines-only.")
@click.option("--output-file", type=click.Path(dir_okay=False, path_type=Path), default=None,
              help="Save structured RSS headlines to a new UTF-8 file; never overwrite.")
@click.option("--save-json-dir", type=click.Path(exists=True, file_okay=False, path_type=Path), default=None,
              help="Save extracted article JSON in this existing directory without overwriting files.")
def keyword(keyword, period, max_results, no_nlp, headlines_only, headline_format, output_file, save_json_dir):
    _require_rss_headline_mode(headline_format, headlines_only, output_file)
    if headlines_only:
        if save_json_dir is not None:
            raise click.UsageError("--save-json-dir is not supported with --headlines-only.")
        items = asyncio.run(get_provider_set().news.get_rss_headlines_by_keyword(keyword=keyword, period=period, max_results=max_results))
        print_rss_headlines(items, output_format=headline_format, output_file=output_file)
        if headline_format == "text":
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
@click.option("--format", "headline_format", type=click.Choice(["text", "json", "csv"]), default="text",
              show_default=True, help="RSS headline output format; JSON/CSV require --headlines-only.")
@click.option("--output-file", type=click.Path(dir_okay=False, path_type=Path), default=None,
              help="Save structured RSS headlines to a new UTF-8 file; never overwrite.")
@click.option("--save-json-dir", type=click.Path(exists=True, file_okay=False, path_type=Path), default=None,
              help="Save extracted article JSON in this existing directory without overwriting files.")
def location(location, period, max_results, no_nlp, headlines_only, headline_format, output_file, save_json_dir):
    _require_rss_headline_mode(headline_format, headlines_only, output_file)
    if headlines_only:
        if save_json_dir is not None:
            raise click.UsageError("--save-json-dir is not supported with --headlines-only.")
        items = asyncio.run(get_provider_set().news.get_rss_headlines_by_location(location=location, period=period, max_results=max_results))
        print_rss_headlines(items, output_format=headline_format, output_file=output_file)
        if headline_format == "text":
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
@click.option("--format", "headline_format", type=click.Choice(["text", "json", "csv"]), default="text",
              show_default=True, help="RSS headline output format; JSON/CSV require --headlines-only.")
@click.option("--output-file", type=click.Path(dir_okay=False, path_type=Path), default=None,
              help="Save structured RSS headlines to a new UTF-8 file; never overwrite.")
@click.option("--save-json-dir", type=click.Path(exists=True, file_okay=False, path_type=Path), default=None,
              help="Save extracted article JSON in this existing directory without overwriting files.")
def topic(topic, period, max_results, no_nlp, headlines_only, headline_format, output_file, save_json_dir):
    _require_rss_headline_mode(headline_format, headlines_only, output_file)
    if headlines_only:
        if save_json_dir is not None:
            raise click.UsageError("--save-json-dir is not supported with --headlines-only.")
        items = asyncio.run(get_provider_set().news.get_rss_headlines_by_topic(topic=topic, period=period, max_results=max_results))
        print_rss_headlines(items, output_format=headline_format, output_file=output_file)
        if headline_format == "text":
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
@click.option("--format", "headline_format", type=click.Choice(["text", "json", "csv"]), default="text",
              show_default=True, help="RSS headline output format; JSON/CSV require --headlines-only.")
@click.option("--output-file", type=click.Path(dir_okay=False, path_type=Path), default=None,
              help="Save structured RSS headlines to a new UTF-8 file; never overwrite.")
@click.option("--save-json-dir", type=click.Path(exists=True, file_okay=False, path_type=Path), default=None,
              help="Save extracted article JSON in this existing directory without overwriting files.")
def top(period, max_results, no_nlp, headlines_only, headline_format, output_file, save_json_dir):
    _require_rss_headline_mode(headline_format, headlines_only, output_file)
    if headlines_only:
        if save_json_dir is not None:
            raise click.UsageError("--save-json-dir is not supported with --headlines-only.")
        items = asyncio.run(get_provider_set().news.get_rss_headlines_for_top_news(period=period, max_results=max_results))
        print_rss_headlines(items, output_format=headline_format, output_file=output_file)
        if headline_format == "text":
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
@click.option("--format", "headline_format", type=click.Choice(["text", "json", "csv"]), default="text",
              show_default=True, help="RSS headline output format; JSON/CSV require --headlines-only.")
@click.option("--output-file", type=click.Path(dir_okay=False, path_type=Path), default=None,
              help="Save structured RSS headlines to a new UTF-8 file; never overwrite.")
@click.option("--save-json-dir", type=click.Path(exists=True, file_okay=False, path_type=Path), default=None,
              help="Save extracted article JSON in this existing directory without overwriting files.")
def site(site, period, max_results, no_nlp, headlines_only, headline_format, output_file, save_json_dir):
    _require_rss_headline_mode(headline_format, headlines_only, output_file)
    if headlines_only:
        if save_json_dir is not None:
            raise click.UsageError("--save-json-dir is not supported with --headlines-only.")
        items = asyncio.run(get_provider_set().news.get_rss_headlines_by_site(
            site=site, period=period, max_results=max_results,
        ))
        print_rss_headlines(items, output_format=headline_format, output_file=output_file)
        if headline_format == "text":
            click.echo(f"Found {len(items)} RSS headlines for site '{site}'.")
        return

    @BrowserManager()
    async def _site():
        articles = await get_news_by_site(site, period=period, max_results=max_results, nlp=not no_nlp)
        print_articles(articles, export_dir=save_json_dir)
        click.echo(f"Found {len(articles)} articles for site '{site}'.")

    asyncio.run(_site())


def _save_new_brief_report(destination, report, *, kind, label="Demand Brief"):
    """Write an already-validated offline report without overwriting existing files."""
    if destination.exists() or not destination.parent.is_dir():
        raise click.ClickException(f"{kind.capitalize()} destination must be a new file in an existing directory.")
    created = False
    try:
        with destination.open("x", encoding="utf-8", newline="\n") as handle:
            created = True
            handle.write(report)
    except OSError as exc:
        if created:
            try:
                destination.unlink()
            except OSError:
                raise click.ClickException(
                    f"{kind.capitalize()} write failed; partial file may remain at {destination}: {exc}"
                ) from exc
        raise click.ClickException(f"{kind.capitalize()} file was not saved: {exc}") from exc
    click.echo(f"Wrote {label} {kind} to {destination}", err=True)


@cli.command("brief-review", help="Review saved Demand Brief JSON offline without provider calls.")
@click.option("--evidence", type=click.Path(exists=True, dir_okay=False, path_type=Path), required=True)
@click.option("--format", "review_format", type=click.Choice(["text", "json", "csv", "markdown", "checklist"]), default="text",
              show_default=True, help="Text, JSON, CSV, Markdown, or an offline evidence-gap checklist.")
@click.option("--output-file", type=click.Path(dir_okay=False, path_type=Path), default=None,
              help="Save the review to a new UTF-8 file; never overwrite existing files.")
@click.option("--as-of", default=None, help="Explicit YYYY-MM-DD date for reproducible offline freshness review.")
@click.option("--max-age-days", type=click.IntRange(0, 3650), default=None,
              help="Maximum age of each primary observation; requires --as-of.")
def brief_review(evidence, review_format, output_file, as_of, max_age_days):
    """Review primary evidence coverage and incomplete markets from a saved JSON file."""
    from mcp_trendpulse.brief_review import MAX_EVIDENCE_BYTES, review_saved_brief

    try:
        with evidence.open("rb") as handle:
            raw = handle.read(MAX_EVIDENCE_BYTES + 1)
        report, needs_attention = review_saved_brief(
            raw, output_format=review_format, as_of=as_of, max_age_days=max_age_days
        )
    except (OSError, ValueError) as exc:
        raise click.ClickException(f"Demand Brief review failed: {exc}") from exc
    if output_file is None:
        click.echo(report, nl=False)
    else:
        _save_new_brief_report(output_file, report, kind="review")
    if needs_attention:
        raise click.exceptions.Exit(2)


@cli.command("brief-compare", help="Compare saved Demand Brief evidence coverage offline.")
@click.option("--before", "before_path", type=click.Path(exists=True, dir_okay=False, path_type=Path), required=True)
@click.option("--after", "after_path", type=click.Path(exists=True, dir_okay=False, path_type=Path), required=True)
@click.option("--format", "compare_format", type=click.Choice(["text", "json", "csv", "keyword-csv", "markdown", "checklist"]), default="text", show_default=True)
@click.option("--output-file", type=click.Path(dir_okay=False, path_type=Path), default=None,
              help="Save the comparison to a new UTF-8 file; never overwrite existing files.")
@click.option("--as-of", default=None, help="Explicit YYYY-MM-DD reference for checking after-file primary observation dates.")
@click.option("--max-age-days", type=click.IntRange(0, 3650), default=None,
              help="Maximum age of after-file primary observations; requires --as-of.")
def brief_compare(before_path, after_path, compare_format, output_file, as_of, max_age_days):
    """Compare two compatible saved evidence files without querying providers."""
    from mcp_trendpulse.brief_review import MAX_EVIDENCE_BYTES, compare_saved_briefs

    if output_file is not None and (output_file.exists() or not output_file.parent.is_dir()):
        raise click.ClickException("Comparison destination must be a new file in an existing directory.")
    try:
        with before_path.open("rb") as handle:
            before_raw = handle.read(MAX_EVIDENCE_BYTES + 1)
        with after_path.open("rb") as handle:
            after_raw = handle.read(MAX_EVIDENCE_BYTES + 1)
        report, needs_attention = compare_saved_briefs(
            before_raw, after_raw, output_format=compare_format,
            as_of=as_of, max_age_days=max_age_days,
        )
    except (OSError, ValueError) as exc:
        raise click.ClickException(f"Demand Brief comparison failed: {exc}") from exc
    if output_file is None:
        click.echo(report, nl=False)
    else:
        _save_new_brief_report(output_file, report, kind="comparison")
    if needs_attention:
        raise click.exceptions.Exit(2)


@cli.command("brief-audit", help="Audit up to twelve saved Demand Brief files together, offline.")
@click.option("--evidence", "evidence_paths", multiple=True, required=True,
              type=click.Path(exists=True, dir_okay=False, path_type=Path),
              help="Saved schema-v1 evidence file; repeat up to twelve times.")
@click.option("--format", "audit_format", type=click.Choice(["markdown", "json", "csv"]),
              default="markdown", show_default=True)
@click.option("--output-file", type=click.Path(dir_okay=False, path_type=Path), default=None,
              help="Save the batch audit as a new UTF-8 file without overwriting.")
@click.option("--as-of", default=None, help="Explicit YYYY-MM-DD offline freshness reference date.")
@click.option("--max-age-days", type=click.IntRange(0, 3650), default=None,
              help="Maximum age of primary observations; requires --as-of.")
def brief_audit(evidence_paths, audit_format, output_file, as_of, max_age_days):
    """Summarize independently saved evidence quality without comparing interest indices."""
    from mcp_trendpulse.brief_audit import audit_saved_briefs

    if output_file is not None and (output_file.exists() or not output_file.parent.is_dir()):
        raise click.ClickException("Audit destination must be a new file in an existing directory.")
    try:
        report, needs_attention = audit_saved_briefs(
            evidence_paths, output_format=audit_format, as_of=as_of, max_age_days=max_age_days,
        )
    except (OSError, ValueError) as exc:
        raise click.ClickException(f"Demand Brief batch audit failed: {exc}") from exc
    if output_file is None:
        click.echo(report, nl=False)
    else:
        _save_new_brief_report(output_file, report, kind="audit")
    if needs_attention:
        raise click.exceptions.Exit(2)


@cli.command("rss-review", help="Audit saved headline-only Google News RSS JSON without provider calls.")
@click.option("--evidence", type=click.Path(exists=True, dir_okay=False, path_type=Path), required=True,
              help="Explicit JSON file saved with --headlines-only --format json.")
@click.option("--format", "review_format", type=click.Choice(["markdown", "json", "csv"]),
              default="markdown", show_default=True)
@click.option("--output-file", type=click.Path(dir_okay=False, path_type=Path), default=None,
              help="Save the report to a new UTF-8 file without overwriting.")
@click.option("--contains", default=None, help="Filter saved headlines by a case-insensitive literal title substring.")
@click.option("--publisher-breakdown", is_flag=True,
              help="Show unverified publisher-label counts on unique saved headlines in scope.")
def rss_review(evidence, review_format, output_file, contains, publisher_breakdown):
    """Review exact-URL duplicates, missing metadata and evidence limitations offline."""
    from mcp_trendpulse.rss_review import MAX_RSS_EVIDENCE_BYTES, review_saved_rss_headlines

    if output_file is not None and (output_file.exists() or not output_file.parent.is_dir()):
        raise click.ClickException("RSS review destination must be a new file in an existing directory.")
    try:
        if evidence.is_symlink():
            raise ValueError("Symbolic-link RSS evidence is not supported")
        with evidence.open("rb") as handle:
            raw = handle.read(MAX_RSS_EVIDENCE_BYTES + 1)
        report, needs_attention = review_saved_rss_headlines(
            raw, output_format=review_format, contains=contains,
            publisher_breakdown=publisher_breakdown)
    except (OSError, ValueError) as exc:
        raise click.ClickException(f"RSS headline review failed: {exc}") from exc
    if output_file is None:
        click.echo(report, nl=False)
    else:
        _save_new_brief_report(output_file, report, kind="review", label="RSS headlines")
    if needs_attention:
        raise click.exceptions.Exit(2)


@cli.command("rss-compare", help="Compare two saved headline-only Google News RSS captures offline.")
@click.option("--older", type=click.Path(exists=True, dir_okay=False, path_type=Path), required=True,
              help="User-designated earlier schema-v1 RSS headline JSON file.")
@click.option("--newer", type=click.Path(exists=True, dir_okay=False, path_type=Path), required=True,
              help="User-designated later schema-v1 RSS headline JSON file.")
@click.option("--format", "comparison_format", type=click.Choice(["markdown", "json", "csv"]),
              default="markdown", show_default=True)
@click.option("--output-file", type=click.Path(dir_okay=False, path_type=Path), default=None,
              help="Save report as a new UTF-8 file without overwriting.")
def rss_compare(older, newer, comparison_format, output_file):
    """Compare exact saved Google News URLs without a network or provider request."""
    from mcp_trendpulse.rss_compare import compare_saved_rss_headlines
    from mcp_trendpulse.rss_review import MAX_RSS_EVIDENCE_BYTES

    if older == newer or older.resolve() == newer.resolve():
        raise click.ClickException("RSS comparison requires two distinct captures.")
    if output_file is not None and (output_file.exists() or not output_file.parent.is_dir()):
        raise click.ClickException("RSS comparison destination must be a new file in an existing directory.")
    try:
        if older.is_symlink() or newer.is_symlink():
            raise ValueError("Symbolic-link RSS evidence is not supported")
        with older.open("rb") as handle:
            older_raw = handle.read(MAX_RSS_EVIDENCE_BYTES + 1)
        with newer.open("rb") as handle:
            newer_raw = handle.read(MAX_RSS_EVIDENCE_BYTES + 1)
        report, needs_attention = compare_saved_rss_headlines(
            older_raw, newer_raw, output_format=comparison_format)
    except (OSError, ValueError) as exc:
        raise click.ClickException(f"RSS headline comparison failed: {exc}") from exc
    if output_file is None:
        click.echo(report, nl=False)
    else:
        _save_new_brief_report(output_file, report, kind="comparison", label="RSS headlines")
    if needs_attention:
        raise click.exceptions.Exit(2)


@cli.command("brief-pack", help="Build the core trend/growth evidence table for a TrendPulse Demand Brief.")
@click.option("--keyword", "keywords", multiple=True, required=True, help="Keyword or phrase; repeat up to five times.")
@click.option("--market", "markets", multiple=True, required=True, help="Country or subregion code such as US or US-CA; repeat up to twice.")
@click.option("--timeframe", type=str, default="today 12-m", show_default=True, help="Shared Google Trends timeframe.")
@click.option("--format", "output_format", type=click.Choice(["markdown", "json", "csv", "watch-json"]), default="markdown", show_default=True, help="Human-readable brief, structured JSON, spreadsheet CSV, or manual Trend Watch evidence.")
@click.option("--output-file", type=click.Path(dir_okay=False, path_type=Path), default=None, help="Write JSON, CSV or Markdown as a new UTF-8 evidence file without overwriting existing files.")
@click.option("--watch-evidence-file", type=click.Path(dir_okay=False, path_type=Path), default=None, help="Write UTF-8 watch-json to a new file, never overwriting existing evidence.")
@click.option("--allow-partial", is_flag=True, help="Keep usable markets when a provider fails; incomplete output still exits nonzero.")
def brief_pack(keywords, markets, timeframe, output_format, output_file, watch_evidence_file, allow_partial):
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
    if output_file is not None:
        if output_format not in ("json", "csv", "markdown"):
            raise click.UsageError("--output-file requires --format json, csv or markdown; use --watch-evidence-file for watch-json.")
        if output_file.exists() or not output_file.parent.is_dir():
            raise click.ClickException("Evidence destination must be a new file in an existing directory.")
    if output_format == "watch-json" and allow_partial:
        raise click.UsageError("--allow-partial cannot be used with --format watch-json.")
    if output_format == "watch-json" and (len(cleaned_keywords) != 1 or len(cleaned_markets) != 1):
        raise click.UsageError("Watch evidence needs exactly one keyword and one market.")
    if watch_evidence_file is not None:
        if output_format != "watch-json":
            raise click.UsageError("--watch-evidence-file requires --format watch-json.")
        if watch_evidence_file.exists() or not watch_evidence_file.parent.is_dir():
            raise click.ClickException("Watch evidence destination must be a new file in an existing directory.")

    def emit_document(document, incomplete):
        if output_file is None:
            click.echo(document, nl=False)
            return
        created = False
        try:
            with output_file.open("x", encoding="utf-8", newline="\n") as handle:
                created = True
                handle.write(document)
        except OSError as exc:
            if created:
                try:
                    output_file.unlink()
                except OSError:
                    pass
            raise click.ClickException(f"Demand Brief evidence file was not saved: {exc}") from exc
        label = "incomplete Demand Brief evidence" if incomplete else "Demand Brief evidence"
        click.echo(f"Wrote {label} to {output_file}", err=True)

    # Keep Markdown buffering local to this invocation; never redirect process stdout.
    markdown_buffer = io.StringIO() if output_file is not None and output_format == "markdown" else None

    def echo_markdown(message=None):
        click.echo(message, file=markdown_buffer)

    async def _build():
        providers = get_provider_set()
        display_timeframe = _brief_table_cell(" ".join(timeframe.split()))
        markets_output = []
        failed_markets = []
        markdown_coverage = {}
        if output_format == "markdown":
            echo_markdown("# TrendPulse Demand Brief evidence pack")
            echo_markdown()
            echo_markdown(f"Timeframe: **{display_timeframe}** | Google Trends property: **Google Search**")
            echo_markdown("Data source: **Google Trends** (https://trends.google.com/trends/)")
            echo_markdown()
            echo_markdown("> Google Trends values are normalized relative-interest indices, not absolute search volume. Compare terms within the same market request; do not compare index values directly across markets.")

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
                        created = False
                        try:
                            with watch_evidence_file.open("x", encoding="utf-8", newline="\n") as handle:
                                created = True
                                handle.write(payload)
                        except OSError as exc:
                            if created:
                                try:
                                    watch_evidence_file.unlink()
                                except OSError:
                                    pass
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
                    echo_markdown(f"\n## {market}\n\n> **UNAVAILABLE ({exc.code.value})**: {public_error['message']} No observations are reported for this market.")
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
                            echo_markdown(f"\n## {skipped}\n\n> **NOT ATTEMPTED**: {skipped_message}")
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
            if output_format == "markdown":
                validated_count = len(cleaned_keywords) - len(missing_primary_keywords)
                if not validated_count:
                    coverage_status = "no primary evidence"
                    if growth_failure:
                        coverage_status += "; growth unavailable"
                else:
                    coverage_status = "growth unavailable" if growth_failure else "observed"
                markdown_coverage[market] = (
                    validated_count,
                    latest_trends_date or "n/a",
                    coverage_status,
                )

            if output_format in ("json", "csv"):
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

            echo_markdown()
            echo_markdown(f"## {market}")
            if invalid_points_container:
                echo_markdown()
                echo_markdown("> Google Trends returned an invalid observation container; no series observations were usable.")
            elif malformed_points:
                echo_markdown()
                echo_markdown(f"> Excluded {malformed_points} malformed Trends rows from this evidence table.")
            skipped_dates = len(points) - len(dated_points)
            if skipped_dates:
                echo_markdown()
                noun = "observation" if skipped_dates == 1 else "observations"
                echo_markdown(f"> Excluded {skipped_dates} Trends {noun} with invalid dates from this evidence table.")
            for keyword in missing_primary_keywords:
                echo_markdown()
                echo_markdown(
                    f"> {_brief_table_cell(keyword)}: no validated primary Google Trends "
                    f"interest observations in {market}; separate growth values do not "
                    "replace primary evidence."
                )
            skipped_indices = len(dated_points) - len(valid_interest_points)
            if skipped_indices:
                echo_markdown()
                noun = "observation" if skipped_indices == 1 else "observations"
                echo_markdown(f"> Excluded {skipped_indices} Trends {noun} with invalid relative-interest indices from this evidence table.")
            if timeframe.strip().lower() != "today 12-m":
                echo_markdown()
                echo_markdown(
                    f"> 3M and 1Y growth use separate Google Trends lookback requests; "
                    f"they are not calculated from the selected {display_timeframe} time series."
                )
            if invalid_growth_container:
                echo_markdown()
                echo_markdown("> Google Trends returned an invalid growth response; growth values are unavailable.")
            elif malformed_growth_rows:
                echo_markdown()
                echo_markdown(f"> Excluded {malformed_growth_rows} malformed growth entries from this evidence table.")
            if growth_warning:
                echo_markdown()
                echo_markdown(f"> {growth_warning}")
            if latest_trends_date:
                echo_markdown()
                echo_markdown(f"Latest complete Trends point: **{latest_trends_date}**")
            echo_markdown()
            echo_markdown("| Keyword | Latest index | 3M growth | 1Y growth |")
            echo_markdown("| --- | ---: | ---: | ---: |")
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
                echo_markdown(
                    f"| {_brief_table_cell(keyword)} | {_brief_value(latest)} | {_brief_percent(keyword_growth.get('3M'))} | {_brief_percent(keyword_growth.get('1Y'))} |"
                )
            if older_observations:
                echo_markdown()
                echo_markdown("> Some latest keyword indices are older than the newest market observation:")
                for keyword, last_date in older_observations:
                    echo_markdown(
                        f"> {_brief_table_cell(keyword)}: last observation **{last_date}** "
                        f"(market latest **{latest_trends_date}**)"
                    )
            if stop_after_market:
                for skipped in cleaned_markets[index + 1:]:
                    echo_markdown(
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
            emit_document(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2) + "\n", bool(failed_markets))
        elif output_format == "csv":
            stream = io.StringIO(newline="")
            columns = (
                "source", "source_url", "property", "timeframe", "comparability_note",
                "market", "keyword", "latest_market_observation", "latest_observation",
                "observation_alignment", "latest_index", "growth_3m_pct", "growth_1y_pct", "growth_basis",
                "status", "incomplete", "error_component", "error_code", "retryable",
                "error_message", "warnings",
            )
            writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            evidence_by_market = {item["market"]: item for item in markets_output}
            failure_by_market = {item["market"]: item for item in failed_markets}
            for market in cleaned_markets:
                evidence = evidence_by_market.get(market, {})
                failure = failure_by_market.get(market, {})
                by_keyword = {item["keyword"]: item for item in evidence.get("keywords", [])}
                for keyword in cleaned_keywords:
                    item = by_keyword.get(keyword, {})
                    if failure.get("code") == "not_attempted_due_to_rate_limit":
                        status = "not_attempted"
                    elif not evidence:
                        status = "unavailable"
                    elif item.get("latest_index") is None:
                        status = "no_valid_observation"
                    else:
                        status = "observed"
                    alignment = ""
                    if status == "observed":
                        observed_at = _brief_observation_time(item.get("latest_observation"))
                        market_at = _brief_observation_time(evidence.get("latest_complete_trends_point"))
                        if observed_at and market_at:
                            alignment = (
                                "older_than_market_latest" if observed_at[0] < market_at[0]
                                else "market_latest"
                            )
                    values = {
                        "source": "Google Trends",
                        "source_url": "https://trends.google.com/trends/",
                        "property": "Google Search",
                        "timeframe": " ".join(timeframe.split()),
                        "comparability_note": "Relative-interest index, not absolute search volume; compare only within a market request.",
                        "market": market,
                        "keyword": keyword,
                        "latest_market_observation": evidence.get("latest_complete_trends_point"),
                        "latest_observation": item.get("latest_observation"),
                        "observation_alignment": alignment,
                        "latest_index": item.get("latest_index"),
                        "growth_3m_pct": item.get("growth_3m_pct"),
                        "growth_1y_pct": item.get("growth_1y_pct"),
                        "growth_basis": evidence.get("growth_basis"),
                        "status": status,
                        "incomplete": str(bool(failed_markets)).lower(),
                        "error_component": failure.get("component"),
                        "error_code": failure.get("code"),
                        "retryable": str(failure["retryable"]).lower() if failure else "",
                        "error_message": failure.get("message"),
                        "warnings": "; ".join(evidence.get("warnings", [])),
                    }
                    writer.writerow({column: _brief_csv_cell(values[column]) for column in columns})
            emit_document(stream.getvalue(), bool(failed_markets))
        else:
            if len(cleaned_markets) > 1:
                failures = {item["market"]: item for item in failed_markets}
                echo_markdown()
                echo_markdown("## Cross-market evidence coverage (not a ranking)")
                echo_markdown()
                echo_markdown("| Market | Validated primary keywords | Latest validated point | Status |")
                echo_markdown("| --- | ---: | --- | --- |")
                for market in cleaned_markets:
                    if market in markdown_coverage:
                        count, latest, status = markdown_coverage[market]
                    else:
                        count, latest = 0, "n/a"
                        failure = failures.get(market, {})
                        status = (
                            "not attempted" if failure.get("code") == "not_attempted_due_to_rate_limit"
                            else "unavailable"
                        )
                    echo_markdown(f"| {market} | {count}/{len(cleaned_keywords)} | {latest} | {status} |")
                echo_markdown()
                echo_markdown(
                    "> This compares evidence coverage and freshness only, not a ranking. "
                    "Google Trends relative-interest indices from separate market requests "
                    "are not directly comparable."
                )
            if failed_markets:
                echo_markdown()
                echo_markdown(
                    f"> **INCOMPLETE EVIDENCE:** {len(failed_markets)} failed or unattempted "
                    f"market components across {len(cleaned_markets)} requested markets. "
                    "Do not use as a complete Demand Brief."
                )
        if markdown_buffer is not None:
            emit_document(markdown_buffer.getvalue(), bool(failed_markets))
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


def _brief_csv_cell(value):
    """Keep untrusted text inert in spreadsheet applications, even when CSV-quoted."""
    if value is None:
        return ""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


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


def _require_rss_headline_mode(output_format, headlines_only, output_file=None):
    if output_format != "text" and not headlines_only:
        raise click.UsageError(f"--format {output_format} requires --headlines-only.")
    if output_file is not None:
        if not headlines_only or output_format not in ("json", "csv"):
            raise click.UsageError("--output-file requires --format json or csv and --headlines-only.")
        if output_file.exists() or not output_file.parent.is_dir():
            raise click.ClickException("RSS headline destination must be a new file in an existing directory.")


def print_rss_headlines(items, *, output_format="text", output_file=None):
    """Emit genuine RSS metadata without treating headlines as full articles."""
    headlines = []
    for item in items:
        meta = item.get("meta_data") or {}
        if (not isinstance(meta, dict)
                or meta.get("content_level") != "rss_headline_only"
                or meta.get("source") != "google_news_rss"):
            raise click.ClickException("Unexpected RSS headline evidence level.")
        try:
            headlines.append({
                "title": item["title"], "url": item["url"],
                "publisher": item.get("meta_site_name"),
                "publish_date": item["publish_date"],
            })
        except KeyError as exc:
            raise click.ClickException("RSS headline missing required metadata.") from exc
    if output_format == "json":
        document = json.dumps({
            "schema_version": 1, "source": "google_news_rss",
            "content_level": "rss_headline_only", "count": len(headlines),
            "headlines": headlines,
        }, ensure_ascii=False, indent=2) + "\n"
        if output_file is None:
            click.echo(document, nl=False)
        else:
            _save_new_brief_report(output_file, document, kind="JSON", label="RSS headlines")
        return
    if output_format == "csv":
        out = io.StringIO(newline="")
        fields = ("source", "content_level", "title", "url", "publisher", "publish_date")
        writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for headline in headlines:
            writer.writerow({
                "source": "google_news_rss", "content_level": "rss_headline_only",
                **{key: _brief_csv_cell(headline[key]) for key in fields[2:]},
            })
        if output_file is None:
            click.echo(out.getvalue(), nl=False)
        else:
            _save_new_brief_report(output_file, out.getvalue(), kind="CSV", label="RSS headlines")
        return
    for headline in headlines:
        click.echo(f"Title: {headline['title']}")
        click.echo(f"Google News URL: {headline['url']}")
        click.echo(f"Publisher: {headline['publisher'] or 'Unknown'}")
        click.echo(f"Publish Date: {headline['publish_date']}")
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
