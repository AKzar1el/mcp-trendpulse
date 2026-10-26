"""No-network SQL builder for Google's official BigQuery Trends public tables.

The public dataset is a curated Top 25 / Top 25 Rising source. It does not
answer arbitrary Google Trends keyword requests. This module constructs SQL
only: it never creates BigQuery jobs, requests credentials or incurs spend.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

TrendKind = Literal["top", "rising"]

_TABLES = {
    ("US", "top"): "bigquery-public-data.google_trends.top_terms",
    ("US", "rising"): "bigquery-public-data.google_trends.top_rising_terms",
    ("international", "top"): "bigquery-public-data.google_trends.international_top_terms",
    ("international", "rising"): "bigquery-public-data.google_trends.international_top_rising_terms",
}


def build_discovery_sql(
    *,
    country: str,
    kind: TrendKind = "top",
    limit: int = 25,
    snapshot_date: str | None = None,
    region_code: str | None = None,
    dma_id: str | None = None,
) -> str:
    """Generate allowlisted, partition-filtered and non-executing discovery SQL."""
    if not isinstance(country, str) or re.fullmatch(r"[A-Z]{2}", country) is None:
        raise ValueError("Country must be an uppercase ISO 3166-1 alpha-2 code")
    if kind not in {"top", "rising"}:
        raise ValueError("Dataset must be 'top' or 'rising'")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 25:
        raise ValueError("Limit must be an integer between 1 and 25")
    if region_code is not None:
        if country == "US" or re.fullmatch(r"[A-Z]{2}-[A-Z0-9]{1,3}", region_code) is None:
            raise ValueError("Region must be an ISO 3166-2 code for an international market")
        if not region_code.startswith(country + "-"):
            raise ValueError("Region must belong to the specified country")
    if dma_id is not None:
        if country != "US" or re.fullmatch(r"[0-9]{3}", dma_id) is None:
            raise ValueError("DMA must be a three-digit US metro-area code")

    if snapshot_date is None:
        partition = "DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)"
    else:
        if not isinstance(snapshot_date, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", snapshot_date) is None:
            raise ValueError("Snapshot date must use YYYY-MM-DD")
        try:
            parsed = date.fromisoformat(snapshot_date)
        except ValueError as exc:
            raise ValueError("Snapshot date is not a calendar date") from exc
        if parsed > date.today():
            raise ValueError("Snapshot date must not be in the future")
        partition = f"DATE '{snapshot_date}'"

    scope = "US" if country == "US" else "international"
    table = _TABLES[scope, kind]
    filters = [f"refresh_date = {partition}"]
    if country != "US":
        filters.append(f"country_code = '{country}'")
    if region_code:
        filters.append(f"region_code = '{region_code}'")
    if dma_id:
        filters.append(f"dma_id = {int(dma_id)}")

    return (
        "-- SQL PREVIEW ONLY. No BigQuery job has been started.\n"
        "-- Google Trends public dataset: curated top 25, NOT arbitrary keywords.\n"
        "-- Before running, use a BigQuery dry run and configure maximum bytes billed.\n"
        "-- LIMIT does not cap bytes scanned or financial charges.\n"
        "SELECT term, MIN(rank) AS best_rank\n"
        f"FROM `{table}`\n"
        f"WHERE {' AND '.join(filters)}\n"
        "GROUP BY term\n"
        "ORDER BY best_rank, term\n"
        f"LIMIT {limit};"
    )
