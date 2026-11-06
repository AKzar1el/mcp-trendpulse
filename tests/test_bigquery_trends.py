"""Offline-only BigQuery SQL construction: never uses Google credentials or jobs."""

import re
import sqlite3
from datetime import date, timedelta

import pytest
from click.testing import CliRunner

from mcp_trendpulse.bigquery_trends import build_discovery_sql
from mcp_trendpulse.cli import cli


def test_bigquery_usa_top_uses_pinned_table_and_partition_filter():
    sql = build_discovery_sql(country="US", kind="top", limit=5)
    assert "`bigquery-public-data.google_trends.top_terms`" in sql
    assert "refresh_date = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)" in sql
    assert "ORDER BY best_rank, term" in sql
    assert sql.endswith("LIMIT 5;")
    assert "SQL PREVIEW ONLY" in sql
    assert "maximum bytes billed" in sql


def test_international_rising_is_country_and_region_filtered():
    sql = build_discovery_sql(country="GB", kind="rising", region_code="GB-ENG")
    assert "`bigquery-public-data.google_trends.international_top_rising_terms`" in sql
    assert "country_code = 'GB'" in sql
    assert "region_code = 'GB-ENG'" in sql


def test_bigquery_usa_rising_dma_selects_correct_dataset():
    sql = build_discovery_sql(country="US", kind="rising", dma_id="501")
    assert "`bigquery-public-data.google_trends.top_rising_terms`" in sql
    assert "dma_id = 501" in sql
    assert "country_code" not in sql


def test_explicit_partition_literal():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    sql = build_discovery_sql(country="SI", snapshot_date=yesterday)
    assert f"refresh_date = DATE '{yesterday}'" in sql


@pytest.mark.parametrize(
    "options",
    [
        {"country": "US", "kind": "top"},
        {"country": "US", "kind": "rising", "dma_id": "501"},
        {"country": "GB", "kind": "top"},
        {"country": "GB", "kind": "rising", "region_code": "GB-ENG"},
    ],
)
def test_latest_week_is_selected_after_snapshot_and_geo_filters(options):
    """A refreshed snapshot can contain older-week rows and other geographies."""
    snapshot = (date.today() - timedelta(days=1)).isoformat()
    previous_snapshot = (date.today() - timedelta(days=2)).isoformat()
    sql = build_discovery_sql(snapshot_date=snapshot, limit=5, **options)
    # SQLite executes the SELECT logic offline; BigQuery table/date syntax is adapted only.
    executable_sql = re.sub(r"FROM `[^`]+`", "FROM trends", sql)
    executable_sql = executable_sql.replace(f"DATE '{snapshot}'", f"'{snapshot}'")

    country = options["country"]
    region = options.get("region_code")
    dma = int(options["dma_id"]) if "dma_id" in options else None
    rows = [
        ("expired", 1, "2026-10-12", snapshot, country, region, dma),
        ("fresh", 4, "2026-10-19", snapshot, country, region, dma),
        ("second", 2, "2026-10-19", snapshot, country, region, dma),
        ("wrong-partition", 1, "2026-10-26", previous_snapshot, country, region, dma),
    ]
    if country != "US":
        rows.append(("wrong-country", 1, "2026-10-26", snapshot, "FR", region, dma))
    if region is not None:
        rows.append(("wrong-region", 1, "2026-10-26", snapshot, country, "GB-SCT", dma))
    if dma is not None:
        rows.append(("wrong-dma", 1, "2026-10-26", snapshot, country, region, 999))

    with sqlite3.connect(":memory:") as db:
        db.execute(
            "CREATE TABLE trends (term TEXT, rank INTEGER, week TEXT, "
            "refresh_date TEXT, country_code TEXT, region_code TEXT, dma_id INTEGER)"
        )
        db.executemany("INSERT INTO trends VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
        result = db.execute(executable_sql).fetchall()
    assert result == [("second", 2), ("fresh", 4)]


@pytest.mark.parametrize(
    "options",
    [
        {"country": "si'; DROP TABLE x; --"},
        {"country": "GB", "region_code": "GB-ENG'; DELETE FROM x; --"},
        {"country": "US", "region_code": "US-CA"},
        {"country": "CA", "region_code": "US-CA"},
        {"country": "US", "dma_id": "50; DELETE"},
        {"country": "SI", "dma_id": "501"},
        {"country": "US", "limit": 0},
        {"country": "US", "limit": 26},
        {"country": "US", "limit": True},
        {"country": "US", "kind": "arbitrary"},
        {"country": "US", "snapshot_date": "2030-01-01"},
        {"country": "US", "snapshot_date": "2026-02-30"},
    ],
)
def test_rejects_invalid_or_injectable_inputs(options):
    with pytest.raises(ValueError):
        build_discovery_sql(**options)


def test_cli_is_preview_only_and_does_not_import_news_provider(monkeypatch):
    runner = CliRunner()
    result = runner.invoke(cli, ["bigquery-sql", "--country", "gb", "--kind", "rising", "--limit", "10"])
    assert result.exit_code == 0, result.output
    assert "international_top_rising_terms" in result.output
    assert "country_code = 'GB'" in result.output
    assert re.search(r"LIMIT 10;\s*$", result.output)
    assert "Google Trends public dataset" in result.output


def test_cli_rejects_injection_without_echoing_sql():
    result = CliRunner().invoke(cli, ["bigquery-sql", "--country", "GB';DROP TABLE"])
    assert result.exit_code != 0
    assert "FROM" not in result.output
