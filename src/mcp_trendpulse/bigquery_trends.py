"""SQL preview and explicitly opted-in no-billing BigQuery Trends sandbox reads.

The public dataset is a curated Top 25 / Top 25 Rising source. It does not
answer arbitrary Google Trends keyword requests. The existing SQL builder
never creates a job; an independent opt-in path verifies a billing-free
project, dry-runs first, then applies a hard byte cap and local query budget.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

from mcp_trendpulse.intelligence_signal import SignalPeriod, SignalProvenance, TrendSignal

TrendKind = Literal["top", "rising"]

_TABLES = {
    ("US", "top"): "bigquery-public-data.google_trends.top_terms",
    ("US", "rising"): "bigquery-public-data.google_trends.top_rising_terms",
    ("international", "top"): "bigquery-public-data.google_trends.international_top_terms",
    ("international", "rising"): "bigquery-public-data.google_trends.international_top_rising_terms",
}

MAX_BYTES_PER_QUERY = 100 * 1024 * 1024
MAX_EXECUTIONS_PER_DAY = 3
_RESULT_CACHE_SECONDS = 15 * 60
_PROJECT_ID = re.compile(r"[a-z][a-z0-9-]{4,28}[a-z0-9]\Z")
_BILLING_API = "https://cloudbilling.googleapis.com/v1/projects/{}/billingInfo"
_SOURCE_REFERENCE = "https://cloud.google.com/blog/products/data-analytics/international-google-trends-datasets-in-bigquery"


class SandboxUnavailable(RuntimeError):
    """A stable, non-secret reason why a BigQuery sandbox operation is refused."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


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
        "-- Use only the latest observation week within the selected snapshot and geography.\n"
        "SELECT term, MIN(rank) AS best_rank\n"
        "FROM (\n"
        "  SELECT term, rank, week, MAX(week) OVER () AS latest_week\n"
        f"  FROM `{table}`\n"
        f"  WHERE {' AND '.join(filters)}\n"
        ") AS scoped_terms\n"
        "WHERE week = latest_week\n"
        "GROUP BY term\n"
        "ORDER BY best_rank, term\n"
        f"LIMIT {limit};"
    )


def _google_client(project_id: str) -> tuple[Any, Any, Any]:
    """Load optional dependencies and the operator's existing ADC, not a key."""
    try:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession
        from google.cloud import bigquery
    except ImportError as exc:
        raise SandboxUnavailable("bigquery_extra_missing") from exc
    try:
        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        client = bigquery.Client(project=project_id, credentials=credentials)
        return client, bigquery, AuthorizedSession(credentials)
    except Exception as exc:
        # The original error can contain credential paths or account details.
        raise SandboxUnavailable("no_sandbox_credentials") from exc


def _verify_sandbox_billing(session: Any, project_id: str) -> None:
    """Fail closed unless the official billing API proves no account is attached."""
    try:
        response = session.get(_BILLING_API.format(project_id), timeout=10, allow_redirects=False)
        if response.status_code != 200:
            raise SandboxUnavailable("sandbox_billing_unverified")
        info = response.json()
        if not isinstance(info, dict):
            raise SandboxUnavailable("sandbox_billing_unverified")
        if (info.get("name") != f"projects/{project_id}/billingInfo"
                or info.get("projectId") != project_id):
            raise SandboxUnavailable("sandbox_billing_unverified")
        if info.get("billingAccountName") or info.get("billingEnabled") is True:
            raise SandboxUnavailable("billing_account_attached")
        if info.get("billingEnabled") is not False:
            raise SandboxUnavailable("sandbox_billing_unverified")
    except SandboxUnavailable:
        raise
    except Exception as exc:
        raise SandboxUnavailable("sandbox_billing_unverified") from exc


def _normalize_rows(
    rows: Any, *, country: str, kind: TrendKind, snapshot: date, limit: int,
) -> tuple[list[dict[str, Any]], int, int]:
    """Accept only bounded public leaderboard ranks, never search volumes."""
    observed = datetime.now(timezone.utc)
    signals: list[dict[str, Any]] = []
    seen: set[str] = set()
    rejected = 0
    received = 0
    for row in rows:
        if received >= limit:
            break
        received += 1
        try:
            term = row["term"]
            rank = row["best_rank"]
        except (KeyError, IndexError, TypeError):
            rejected += 1
            continue
        if (not isinstance(term, str) or not 1 <= len(term) <= 180
                or term.strip() != term or any(ord(c) < 32 or ord(c) == 127 for c in term)
                or type(rank) is not int or not 1 <= rank <= 25):
            rejected += 1
            continue
        normalized = term.casefold()
        if normalized in seen:
            rejected += 1
            continue
        seen.add(normalized)
        signal = TrendSignal(
            source_id="google_trends_bigquery",
            source_url=_SOURCE_REFERENCE,
            observed_at=observed,
            published_at=None,
            country=country,
            language=None,
            raw_term=term,
            normalized_term=normalized,
            metric_type="google_bigquery_rank",
            metric_unit="rank",
            period=SignalPeriod(start_date=snapshot, end_date=snapshot, granularity="daily"),
            value=rank,
            sampling_scope=(
                f"Google Trends BigQuery curated {kind} 25 snapshot {snapshot.isoformat()} "
                f"for {country}; best rank in latest historical week"
            ),
            coverage_status="observed",
            provenance=SignalProvenance(
                method="public_dataset",
                sampling_basis="daily_curated_25_latest_week_best_rank",
                is_observed_search_query=False,
            ),
        )
        signals.append(signal.model_dump(mode="json"))
    return signals, rejected, received


def discover_sandbox_trends(
    *,
    country: str,
    project_id: str | None = None,
    kind: TrendKind = "top",
    limit: int = 25,
    snapshot_date: str | None = None,
    region_code: str | None = None,
    dma_id: str | None = None,
    execute: bool = False,
    cache: Any = None,
) -> dict[str, Any]:
    """Only --execute on a verified unbilled project can issue BigQuery jobs.

    Every live invocation uses a fresh billing-account check, one dry run, a
    100 MiB maximum_bytes_billed bound and a persistent three-per-UTC-day cap.
    Cache hits avoid all cloud calls. No credentials or raw provider failures
    are ever serialized into the report.
    """
    country = country.strip().upper() if isinstance(country, str) else country
    selected = snapshot_date or (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    sql = build_discovery_sql(
        country=country, kind=kind, limit=limit,
        snapshot_date=selected, region_code=region_code, dma_id=dma_id,
    )
    snapshot = date.fromisoformat(selected)
    if snapshot < datetime.now(timezone.utc).date() - timedelta(days=29):
        raise ValueError("Snapshot must be within the 30-day public dataset publication window")
    if project_id is not None and (
        not isinstance(project_id, str) or _PROJECT_ID.fullmatch(project_id) is None
    ):
        raise ValueError("Sandbox project ID must be a valid Google Cloud project ID")
    report: dict[str, Any] = {
        "source": "google_trends_bigquery_public",
        "status": "planned",
        "country": country,
        "kind": kind,
        "snapshot_date": selected,
        "limit": limit,
        "max_bytes_billed": MAX_BYTES_PER_QUERY,
        "market_coverage": "unknown",
        "metric_note": "Curated Top 25 daily dataset rank, not an absolute or arbitrary-keyword count",
        "sql": sql,
        "signals": [],
        "records_rejected": 0,
        "dry_run_estimated_bytes": None,
        "query_jobs_started": 0,
        "network_performed": False,
        "cache_hit": False,
    }
    if not execute:
        return report
    if project_id is None:
        return {**report, "status": "unavailable", "reason": "no_sandbox_project"}

    cache_key = "mjau_bq:" + hashlib.sha256(
        json.dumps([project_id, country, kind, limit, selected, region_code, dma_id]).encode("utf-8")
    ).hexdigest()

    def unavailable(reason: str) -> dict[str, Any]:
        return {**report, "status": "unavailable", "reason": reason}

    from mcp_trendpulse.intelligence_core import BudgetCache, DailyBudgetExceeded

    try:
        client, sdk, session = _google_client(project_id)
    except SandboxUnavailable as exc:
        return unavailable(exc.reason)

    try:
        store = cache if cache is not None else BudgetCache()
        cached = store.cached(cache_key)
        if cached is not None:
            return {**cached, "network_performed": False, "query_jobs_started": 0, "cache_hit": True}
    except (OSError, ValueError, TypeError):
        return unavailable("local_budget_unavailable")

    try:
        report["network_performed"] = True
        _verify_sandbox_billing(session, project_id)
    except SandboxUnavailable as exc:
        return unavailable(exc.reason)

    try:
        store.reserve("google_bigquery_sandbox", MAX_EXECUTIONS_PER_DAY)
    except DailyBudgetExceeded:
        return unavailable("local_daily_budget_exhausted")
    except (OSError, ValueError):
        return unavailable("local_budget_unavailable")

    # The SQL preview's warning comments are removed from the executed SQL.
    query = "\n".join(line for line in sql.splitlines() if not line.startswith("-- "))
    try:
        dry = sdk.QueryJobConfig(
            dry_run=True, use_query_cache=False,
            maximum_bytes_billed=MAX_BYTES_PER_QUERY, job_timeout_ms=15_000,
        )
        estimated_job = client.query(
            query, job_config=dry, project=project_id, location="US",
            retry=None, job_retry=None, timeout=15,
        )
        report["query_jobs_started"] = 1
        estimate = estimated_job.total_bytes_processed
        if type(estimate) is not int or estimate < 0:
            return unavailable("dry_run_estimate_unavailable")
        report["dry_run_estimated_bytes"] = estimate
        if estimate > MAX_BYTES_PER_QUERY:
            return unavailable("estimated_bytes_exceeds_limit")
        live = sdk.QueryJobConfig(
            dry_run=False, use_query_cache=False,
            maximum_bytes_billed=MAX_BYTES_PER_QUERY, job_timeout_ms=15_000,
        )
        query_job = client.query(
            query, job_config=live, project=project_id, location="US",
            retry=None, job_retry=None, timeout=15,
        )
        report["query_jobs_started"] = 2
        rows = query_job.result(
            timeout=20, max_results=limit, page_size=limit,
            retry=None, job_retry=None,
        )
        signals, rejected, received = _normalize_rows(
            rows, country=country, kind=kind, snapshot=snapshot, limit=limit,
        )
    except Exception:
        # No automatic retry: an ambiguous or interrupted job may exist.
        return unavailable("bigquery_source_unavailable")

    report["signals"] = signals
    report["records_rejected"] = rejected
    report["records_observed"] = len(signals)
    report["market_coverage"] = "observed" if signals else "unknown"
    report["status"] = (
        "observed_partial" if signals and rejected else
        "observed" if signals else
        "invalid_source_shape" if received else "no_data"
    )
    try:
        store.save(cache_key, report, _RESULT_CACHE_SECONDS)
    except (OSError, ValueError):
        pass  # Local caching failure must not falsify the completed source result.
    return report
