"""MJAU M03: no-billing BigQuery sandbox, fail-closed jobs and source evidence."""
from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from click.testing import CliRunner

from mcp_trendpulse import bigquery_trends as bq
from mcp_trendpulse.cli import cli
from mcp_trendpulse.intelligence_core import BudgetCache


class FakeResponse:
    status_code = 200

    def __init__(self, project="free-sandbox-123", *, enabled=False, account=""):
        self.info = {
            "name": f"projects/{project}/billingInfo", "projectId": project,
            "billingEnabled": enabled, "billingAccountName": account,
        }

    def json(self):
        return self.info


class FakeSession:
    def __init__(self, response=None):
        self.response = response or FakeResponse()
        self.calls = []

    def get(self, url, *, timeout, allow_redirects):
        self.calls.append((url, timeout, allow_redirects))
        return self.response


class FakeConfig:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeSDK:
    QueryJobConfig = FakeConfig


class FakeJob:
    def __init__(self, *, dry=False, estimate=10_485_760, rows=None):
        self.total_bytes_processed = estimate
        self.dry = dry
        self.rows = rows if rows is not None else [{"term": "Razvoj programske opreme", "best_rank": 4}]
        self.result_kwargs = None

    def result(self, **kwargs):
        self.result_kwargs = kwargs
        return iter(self.rows)


class FakeClient:
    def __init__(self, *, estimate=10_485_760, rows=None):
        self.estimate = estimate
        self.rows = rows
        self.jobs = []
        self.execution_job = None

    def query(self, sql, **kwargs):
        self.jobs.append((sql, kwargs))
        config = kwargs["job_config"]
        if config.dry_run:
            return FakeJob(dry=True, estimate=self.estimate)
        self.execution_job = FakeJob(rows=self.rows)
        return self.execution_job


def fixture_backend(monkeypatch, *, billing=None, estimate=10_485_760, rows=None):
    session = FakeSession(billing)
    client = FakeClient(estimate=estimate, rows=rows)
    monkeypatch.setattr(bq, "_google_client", lambda project: (client, FakeSDK, session))
    return client, session


def query_options(**changes):
    options = {"country": "GB", "kind": "rising", "limit": 5,
               "snapshot_date": (date.today() - timedelta(days=1)).isoformat(),
               "project_id": "free-sandbox-123", "execute": True}
    options.update(changes)
    return options


def test_plan_never_loads_client_or_uses_query_budget(monkeypatch):
    monkeypatch.setattr(bq, "_google_client", lambda _: pytest.fail("preview must not load cloud auth"))
    report = bq.discover_sandbox_trends(country="GB", kind="rising")
    assert report["status"] == "planned" and not report["network_performed"]
    assert "international_top_rising_terms" in report["sql"]
    assert report["query_jobs_started"] == 0


@pytest.mark.parametrize("changes", [
    {"project_id": "not valid; DROP TABLE"},
    {"project_id": "upper-CASE-123"},
    {"snapshot_date": "1900-01-01"},
    {"limit": 100},
    {"country": "US;DROP"},
])
def test_unbounded_or_injectable_arguments_refused_before_auth(monkeypatch, changes):
    monkeypatch.setattr(bq, "_google_client", lambda _: pytest.fail("invalid query reached auth"))
    with pytest.raises(ValueError):
        bq.discover_sandbox_trends(**query_options(**changes))


def test_missing_sandbox_project_and_credentials_fail_gracefully(monkeypatch):
    missing_project = bq.discover_sandbox_trends(country="GB", execute=True)
    assert missing_project["status"] == "unavailable"
    assert missing_project["reason"] == "no_sandbox_project"
    monkeypatch.setattr(bq, "_google_client", lambda _: (_ for _ in ()).throw(
        bq.SandboxUnavailable("no_sandbox_credentials")))
    report = bq.discover_sandbox_trends(**query_options())
    assert report["reason"] == "no_sandbox_credentials"
    assert report["query_jobs_started"] == 0


@pytest.mark.parametrize("response", [
    FakeResponse(enabled=True, account="billingAccounts/private"),
    FakeResponse(enabled=False, account="billingAccounts/inactive"),
    FakeResponse(project="another-project", enabled=False),
])
def test_billing_guard_rejects_attached_or_other_project(monkeypatch, response, tmp_path):
    client, session = fixture_backend(monkeypatch, billing=response)
    result = bq.discover_sandbox_trends(**query_options(), cache=BudgetCache(tmp_path))
    assert result["status"] == "unavailable"
    assert result["reason"] in {"billing_account_attached", "sandbox_billing_unverified"}
    assert not client.jobs
    assert len(session.calls) == 1 and session.calls[0][2] is False


def test_dry_run_before_live_job_with_limits_and_typed_rank(monkeypatch, tmp_path):
    client, session = fixture_backend(monkeypatch)
    report = bq.discover_sandbox_trends(**query_options(), cache=BudgetCache(tmp_path))
    assert report["status"] == "observed" and report["dry_run_estimated_bytes"] == 10_485_760
    assert report["query_jobs_started"] == 2
    assert [kw["job_config"].dry_run for _, kw in client.jobs] == [True, False]
    for sql, kwargs in client.jobs:
        assert "refresh_date = DATE" in sql and "country_code = 'GB'" in sql
        assert kwargs["job_config"].maximum_bytes_billed == bq.MAX_BYTES_PER_QUERY
        assert kwargs["location"] == "US"
        assert kwargs["retry"] is None and kwargs["job_retry"] is None
    assert client.execution_job.result_kwargs["max_results"] <= 25
    signal = report["signals"][0]
    assert signal["raw_term"] == "Razvoj programske opreme"
    assert signal["metric_type"] == "google_bigquery_rank" and signal["metric_unit"] == "rank"
    assert signal["value"] == 4 and signal["country"] == "GB" and signal["language"] is None
    assert signal["provenance"]["method"] == "public_dataset"
    assert not signal["provenance"]["is_observed_search_query"]
    assert "volume" not in json.dumps(report).lower()
    assert len(session.calls) == 1


def test_dry_run_over_cap_never_executes_real_job(monkeypatch, tmp_path):
    client, _ = fixture_backend(monkeypatch, estimate=bq.MAX_BYTES_PER_QUERY + 1)
    report = bq.discover_sandbox_trends(**query_options(), cache=BudgetCache(tmp_path))
    assert report["status"] == "unavailable" and report["reason"] == "estimated_bytes_exceeds_limit"
    assert report["query_jobs_started"] == 1
    assert len(client.jobs) == 1


def test_empty_market_does_not_fabricate_zero_or_retry(monkeypatch, tmp_path):
    client, _ = fixture_backend(monkeypatch, rows=[])
    report = bq.discover_sandbox_trends(**query_options(), cache=BudgetCache(tmp_path))
    assert report["status"] == "no_data"
    assert report["signals"] == [] and report["market_coverage"] == "unknown"
    assert len(client.jobs) == 2


def test_bad_rows_are_rejected_without_synthesizing_metrics(monkeypatch, tmp_path):
    bad = [
        {"term": "good", "best_rank": 2},
        {"term": " GOOD ", "best_rank": 3},
        {"term": "injected\nvalue", "best_rank": 1},
        {"term": "other", "best_rank": 0},
        {"term": "NaN", "best_rank": float("nan")},
    ]
    fixture_backend(monkeypatch, rows=bad)
    report = bq.discover_sandbox_trends(**query_options(), cache=BudgetCache(tmp_path))
    assert report["status"] == "observed_partial"
    assert report["records_rejected"] >= 3
    assert len(report["signals"]) == 1 and report["signals"][0]["raw_term"] == "good"


def test_cached_repeat_avoids_second_billing_check_and_jobs(monkeypatch, tmp_path):
    client, session = fixture_backend(monkeypatch)
    cache = BudgetCache(tmp_path)
    first = bq.discover_sandbox_trends(**query_options(), cache=cache)
    second = bq.discover_sandbox_trends(**query_options(), cache=cache)
    assert first["status"] == "observed" and second["cache_hit"]
    assert len(client.jobs) == 2 and len(session.calls) == 1


def test_local_budget_refuses_further_remote_calls(monkeypatch, tmp_path):
    client, session = fixture_backend(monkeypatch)
    cache = BudgetCache(tmp_path)
    for _ in range(bq.MAX_EXECUTIONS_PER_DAY):
        cache.reserve("google_bigquery_sandbox", bq.MAX_EXECUTIONS_PER_DAY)
    report = bq.discover_sandbox_trends(**query_options(), cache=cache)
    assert report["reason"] == "local_daily_budget_exhausted"
    assert not client.jobs
    assert len(session.calls) == 1


def test_cli_preview_without_sandbox_or_credentials():
    result = CliRunner().invoke(cli, ["bigquery-discover", "--country", "GB"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["status"] == "planned" and not report["network_performed"]
    assert "international_top_terms" in report["sql"]
