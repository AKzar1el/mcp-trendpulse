"""MJAU M08 GitHub Issues: reusable source adapter, exact IDs and honest bias.

All fixtures go through the EXISTING intelligence_core.collect transport
with an injected opener; no second GitHub HTTP client is added.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest
from click.testing import CliRunner

from mcp_trendpulse import intelligence_core as core
from mcp_trendpulse import intelligence_github_issues as gh
from mcp_trendpulse.cli import cli

NOW = datetime.now(timezone.utc).replace(microsecond=0)
DAY = NOW - timedelta(days=1)
SECRET = "NEVER_PERSIST_PRIVATE_ISSUE_BODY_123"


def issue(
    iid=80001234, number=1402, owner="microsoft", repo="playwright",
    *, title="Timeout on browser navigation", created=DAY, state="open",
    pull=False,
):
    url = f"https://github.com/{owner}/{repo}/issues/{number}"
    row = {
        "id": iid, "number": number, "title": title, "state": state,
        "created_at": created.isoformat().replace("+00:00", "Z"),
        "updated_at": (created + timedelta(minutes=1)).isoformat().replace(
            "+00:00", "Z"
        ),
        "html_url": url,
        "repository_url": f"https://api.github.com/repos/{owner}/{repo}",
        "body": f"{SECRET} Steps to reproduce: browser timeout error on navigation",
        "user": {"login": "DONT_PERSIST_AUTHOR"},
        "assignees": [{"email": "DONT_PERSIST_EMAIL@example.com"}],
        "labels": [{"name": "private_customer_notes"}],
    }
    if pull:
        row["pull_request"] = {
            "url": f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}"
        }
    return row


class FakeOpener:
    def __init__(self, payload, status=None):
        self.payload = payload
        self.status = status
        self.calls = []

    def open(self, request, *, timeout):
        self.calls.append(request.full_url)
        if self.status is not None:
            from urllib.error import HTTPError
            raise HTTPError(request.full_url, self.status, "error SECRET", {}, None)
        blob = json.dumps(self.payload).encode("utf-8")

        class Response:
            headers = {"Content-Type": "application/json"}
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                return None
            def read(self, *_args):
                return blob
        return Response()


def source(monkeypatch, *, items=None, total=None, incomplete=False, status=None):
    if items is None:
        items = [issue()]
    payload = {
        "items": items, "total_count": len(items) if total is None else total,
        "incomplete_results": incomplete,
        "token": "DONT_PERSIST_SOURCE_METADATA",
    }
    client = FakeOpener(payload, status=status)
    monkeypatch.setattr(core, "build_opener", lambda *_args: client)
    return client


def run(tmp_path, **kw):
    return gh.discover_github_problems(
        query="timeout", repository="microsoft/playwright",
        lookback_days=30, limit=10, execute=True,
        cache=core.BudgetCache(tmp_path), observed_at=NOW, **kw,
    )


def test_preview_never_opens_db_or_fetches(monkeypatch):
    monkeypatch.setattr(gh, "BudgetCache", lambda *_a, **_kw: (
        (_ for _ in ()).throw(AssertionError("Preview opened a database"))
    ))
    monkeypatch.setattr(gh, "collect", lambda *_a, **_kw: (
        (_ for _ in ()).throw(AssertionError("Preview attempted a request"))
    ))
    report = gh.discover_github_problems(query="timeout")
    assert report["status"] == "planned"
    assert report["requests_attempted"] == 0
    assert report["network_performed"] is False
    assert report["issues"] == [] and report["signals"] == []
    assert report["source_url"].startswith("https://api.github.com/search/issues?")
    assert report["method"] == "existing_intelligence_foundation_github_issues"
    assert report["duplicate_github_api_client_created"] is False
    assert report["paid_services_used"] is False


@pytest.mark.parametrize("inputs", [
    {"query": 'timeout" OR repo:anything'},
    {"query": "https://github.com/private"},
    {"query": "@username"},
    {"query": "a"},
    {"query": "agent\nreliability"},
    {"query": "timeout:search"},
    {"query": " timeout"},
    {"query": "x" * 81},
    {"repository": "../private"},
    {"repository": "foo/bar/baz"},
    {"repository": "foo.github.com/x"},
    {"lookback_days": 6},
    {"lookback_days": 91},
    {"lookback_days": True},
    {"limit": 0},
    {"limit": 11},
    {"limit": True},
    {"execute": "yes"},
])
def test_user_search_injection_and_invalid_params_fail_before_provider(inputs):
    options = {"query": "timeout", "observed_at": NOW, **inputs}
    with pytest.raises(ValueError):
        gh.discover_github_problems(**options)


def test_verified_issue_id_repo_state_utc_provenance_and_no_sensitive_cache(tmp_path, monkeypatch):
    client = source(monkeypatch, items=[issue()], total=1)
    result = run(tmp_path)
    assert result["status"] == "observed"
    assert result["source"] == "github_issues"
    assert result["network_performed"] is True
    assert result["requests_attempted"] == 1
    assert len(client.calls) == 1
    query = parse_qs(urlsplit(client.calls[0]).query)
    assert '"timeout" is:issue is:open' in query["q"][0]
    assert "repo:microsoft/playwright" in query["q"][0]
    assert "per_page" in query and query["per_page"] == ["10"]
    assert result["source_rows_received"] == 1
    assert result["provider_total_matches_reported"] == 1
    assert len(result["issues"]) == 1
    item = result["issues"][0]
    assert item["issue_id"] == 80001234
    assert item["number"] == 1402
    assert item["repository"] == "microsoft/playwright"
    assert item["state"] == "open"
    assert item["utc_day"] == DAY.date().isoformat()
    assert item["issue_evidence_type"] == "reported_operational_problem"
    assert item["title_contains_exact_phrase"] is True
    assert item["source_url"] == "https://github.com/microsoft/playwright/issues/1402"
    assert result["summary"]["distinct_repositories_in_sample"] == 1
    assert result["summary"]["distinct_repository_owners_in_sample"] == 1
    assert result["summary"]["largest_owner_share_of_sample"] == 1
    assert result["summary"]["repository_owner_bias"] == "explicit_repository_filter"
    assert result["summary"]["distinct_humans_verified"] is False
    assert result["summary"]["independent_buyers_verified"] is False
    assert len(result["signals"]) == 1
    sig = result["signals"][0]
    assert sig["source_id"] == "github_issues"
    assert sig["metric_type"] == "github_issue_mentions"
    assert sig["value"] == 1
    assert sig["coverage_status"] == "partial"
    assert sig["provenance"]["method"] == "public_api"
    assert sig["provenance"]["is_observed_search_query"] is False
    assert sig["period"]["granularity"] == "daily"
    assert sig["country"] is None and sig["language"] is None

    # Verify the real durable cache does NOT contain raw issue bodies,
    # authors, e-mail addresses, arbitrary URLs, or the upstream error blob.
    with core.BudgetCache(tmp_path)._connect() as db:
        stored = "\n".join(str(x[0]) for x in db.execute("select body from cache"))
    assert SECRET not in stored
    assert "DONT_PERSIST_AUTHOR" not in stored
    assert "DONT_PERSIST_EMAIL" not in stored
    assert "DONT_PERSIST_SOURCE_METADATA" not in stored
    assert "private_customer_notes" not in stored
    repeated = run(tmp_path)
    assert repeated["cache_hit"] is True
    assert repeated["network_performed"] is False
    assert repeated["requests_attempted"] == 0
    assert repeated["issues"] == result["issues"]
    assert len(client.calls) == 1


def test_global_sample_owners_repo_bias_and_duplicate_global_id(tmp_path, monkeypatch):
    rows = [
        issue(80000001, 41, owner="alpha", repo="a"),
        issue(80000002, 42, owner="alpha", repo="a"),
        issue(80000003, 12, owner="beta", repo="b"),
        issue(80000001, 41, owner="alpha", repo="a"),
        issue(80000004, 44, owner="other", repo="c", pull=True),
    ]
    source(monkeypatch, items=rows, total=150)
    out = gh.discover_github_problems(
        query="timeout", repository="", lookback_days=30, limit=10,
        execute=True, cache=core.BudgetCache(tmp_path), observed_at=NOW,
    )
    assert out["status"] == "observed_partial"
    assert out["source_rows_received"] == 5
    assert out["source_rows_rejected_or_duplicated"] == 2
    assert out["provider_total_matches_reported"] == 150
    assert out["provider_matches_not_fetched"] == 145
    assert out["summary"]["unique_open_issue_ids_in_sample"] == 3
    assert out["summary"]["distinct_repository_owners_in_sample"] == 2
    assert out["summary"]["distinct_repositories_in_sample"] == 2
    assert out["summary"]["largest_owner_share_of_sample"] == pytest.approx(2/3, abs=0.001)
    assert out["summary"]["repository_owner_bias"].startswith("GitHub search")
    assert len(out["signals"]) == 1
    assert out["signals"][0]["value"] == 3
    assert out["summary"]["independent_buyers_verified"] is False


def test_missing_empty_source_not_zero_market_demand(tmp_path, monkeypatch):
    source(monkeypatch, items=[], total=0, incomplete=False)
    out = run(tmp_path)
    assert out["status"] == "no_data"
    assert out["signals"] == []
    assert out["provider_total_matches_reported"] == 0
    assert out["summary"]["product_demand_verified"] is False
    assert out["summary"]["unique_open_issue_ids_in_sample"] == 0


@pytest.mark.parametrize("malformed", [
    {"items": [], "total_count": "SECRET", "incomplete_results": False},
    {"items": [], "total_count": 5, "incomplete_results": "false"},
    {"items": [], "incomplete_results": False},
    {"items": "raw_username", "total_count": 1, "incomplete_results": False},
])
def test_invalid_search_envelope_not_accepted(tmp_path, monkeypatch, malformed):
    client = FakeOpener(malformed)
    monkeypatch.setattr(core, "build_opener", lambda *_a: client)
    out = run(tmp_path)
    assert out["status"] == "invalid_source_shape"
    assert out["issues"] == []


@pytest.mark.parametrize("mutator", [
    lambda x: x.update(state="closed"),
    lambda x: x.update(id=True),
    lambda x: x.update(number="1402"),
    lambda x: x.update(html_url="https://evil.test/a/b/issues/1402"),
    lambda x: x.update(html_url="https://github.com:INVALID/microsoft/playwright/issues/1402"),
    lambda x: x.update(repository_url="https://api.github.com/repos/evil/a"),
    lambda x: x.update(html_url="https://github.com/microsoft/playwright/pull/1402"),
    lambda x: x.update(created_at="1900-01-01T00:00:00Z"),
    lambda x: x.update(updated_at="2025-01-01T00:00:00Z"),
    lambda x: x.update(title="bad\nSECRET"),
    lambda x: x.update(pull_request={"url": "https://api.github.com/pull/1"}),
])
def test_wrong_state_pr_url_metadata_and_out_of_window_fail_closed(
    tmp_path, monkeypatch, mutator,
):
    row = issue()
    mutator(row)
    source(monkeypatch, items=[row], total=1)
    out = run(tmp_path)
    assert out["status"] == "invalid_source_shape"
    assert out["issues"] == [] and out["signals"] == []
    assert "SECRET" not in repr(out)


def test_incomplete_provider_flag_prevents_full_coverage_claim(tmp_path, monkeypatch):
    source(monkeypatch, items=[issue()], total=1, incomplete=True)
    out = run(tmp_path)
    assert out["status"] == "observed_partial"
    assert out["provider_incomplete_results"] is True
    assert out["summary"]["source_report_is_partial"] is True


def test_rate_limit_and_no_hidden_retry(tmp_path, monkeypatch):
    client = source(monkeypatch, status=403)
    out = run(tmp_path)
    assert out["status"] == "provider_unavailable"
    assert out["requests_attempted"] == 1
    assert len(client.calls) == 1
    assert "SECRET" not in json.dumps(out)


def test_shared_daily_quota_without_new_client_or_budget(tmp_path, monkeypatch):
    client = source(monkeypatch, items=[])
    store = core.BudgetCache(tmp_path)
    for _ in range(12):
        store.reserve("github_issues", 12)
    out = run(tmp_path)
    assert out["status"] == "local_daily_budget_exhausted"
    assert out["requests_attempted"] == 0
    assert client.calls == []


def test_cli_preview_is_network_free_and_invalid_repo_rejected():
    runner = CliRunner()
    preview = runner.invoke(cli, [
        "intelligence", "github-problems", "--query", "timeout",
        "--days", "30", "--limit", "10", "--format", "json",
    ])
    assert preview.exit_code == 0, preview.output
    out = json.loads(preview.output)
    assert out["status"] == "planned"
    assert out["network_performed"] is False
    assert out["method"] == "existing_intelligence_foundation_github_issues"
    assert out["daily_original_source_budget"] == 12
    invalid = runner.invoke(cli, [
        "intelligence", "github-problems",
        "--query", "timeout", "--repository", "../private",
        "--format", "json",
    ])
    assert invalid.exit_code != 0
    assert "invalid" in invalid.output.lower()
