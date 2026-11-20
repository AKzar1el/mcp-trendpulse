"""Source-window failure categories remain actionable without raw exceptions.

Every source window is still one planned request. No retries, no count
imputation from a separate CPV-filtered procurement population.
"""
from __future__ import annotations

import re
from datetime import date

import pytest

from mcp_trendpulse import intelligence_discovery as discovery
from mcp_trendpulse.intelligence_core import DailyBudgetExceeded


def _observed(source, rows):
    return {
        "source": source, "status": "observed",
        "observations": {"sample": rows, "record_count": len(rows)},
    }


def _notice_for_window(plan, number: str):
    match = re.search(r"PD = \((\d{8}) <> (\d{8})\)", plan.body["query"])
    assert match
    end = match.group(2)
    return {
        "publication-number": number,
        "publication-date": f"{end[:4]}-{end[4:6]}-{end[6:]}",
        "notice-title": {"eng": ["Source-published software procurement"]},
        "notice-type": "cn-standard",
        "buyer-name": {"eng": ["Public buyer"]},
        "buyer-country": "DEU",
    }


def _run(monkeypatch, third):
    used = []
    def fake_collect(plan, **kwargs):
        used.append(plan.source)
        if plan.source != "ted":
            return _observed(plan.source, [])
        nth = used.count("ted")
        if nth == 3:
            return third()
        return _observed(
            "ted", [_notice_for_window(plan, f"{800000+nth}-2026")]
        )
    monkeypatch.setattr(discovery, "collect", fake_collect)
    report = discovery.discover_current(
        execute=True, limit=12, lookback_days=30,
        ted_date_slices=3, env={},
    )
    assert used == ["openalex", "cfpb", "ted", "ted", "ted"]
    assert report["queries_budgeted"] == 5
    assert report["ted_sampling_audit"]["observed_date_windows"] == 2
    assert report["source_health_degraded"] is True
    assert report["ted_sampling_audit"]["observed_notice_count"] == 2
    assert report["growth_rate_verified"] is False
    return report


def test_typed_daily_ted_quota_includes_consumed_limit_and_utc_no_retry(monkeypatch):
    def fail():
        raise DailyBudgetExceeded("ted", "2026-11-20", 20, 20)
    report = _run(monkeypatch, fail)
    row = report["ted_sampling_audit"]["date_window_results"][-1]
    assert row["status"] == "unavailable"
    assert row["failure_reason_code"] == "daily_source_budget_exhausted"
    assert (row["local_quota_used"], row["local_quota_limit"]) == (20, 20)
    assert row["local_quota_utc_day"] == "2026-11-20"
    text = discovery.format_discovery_report(report)
    assert "UTC 2026-11-20 local TED quota 20/20 exhausted; no bypass" in text
    assert "PARTIAL COVERAGE" in text


@pytest.mark.parametrize(("raw_response", "reason", "http"), [
    (
        {"status": "unavailable", "source": "ted",
         "reason": "HTTPError", "http_status": 429,
         "full_error": "PRIVATE_TOKEN=abc"},
        "HTTPError", 429,
    ),
    (
        {"status": "unavailable", "source": "ted",
         "reason": "provider_cooldown"},
        "provider_cooldown", None,
    ),
    (
        {"status": "unavailable", "source": "ted",
         "reason": "password: PRIVATE_TOKEN=abc", "http_status": 503},
        "source_failure_unclassified", 503,
    ),
    (
        {"status": "invalid_source_shape", "source": "ted",
         "reason": {"private": "PRIVATE_TOKEN=abc"}},
        "source_failure_unclassified", None,
    ),
])
def test_window_http_cooldown_and_untrusted_reason_do_not_leak(
    monkeypatch, raw_response, reason, http,
):
    report = _run(monkeypatch, lambda: raw_response)
    row = report["ted_sampling_audit"]["date_window_results"][-1]
    assert row["failure_reason_code"] == reason
    assert row.get("http_status") == http
    text = discovery.format_discovery_report(report)
    assert "PRIVATE_TOKEN" not in repr(report)
    assert "PRIVATE_TOKEN" not in text
    assert reason in text


def test_local_sqlite_failure_cannot_be_mislabeled_as_exhausted_quota(monkeypatch):
    import sqlite3

    def fail():
        raise sqlite3.OperationalError("PRIVATE_TOKEN=abc")
    report = _run(monkeypatch, fail)
    row = report["ted_sampling_audit"]["date_window_results"][-1]
    assert row["failure_reason_code"] == "local_cache_storage_error"
    assert "local_quota_used" not in row
    assert "PRIVATE_TOKEN" not in repr(report)


def test_provider_failure_no_retry_or_focused_sample_fallback(monkeypatch):
    report = _run(monkeypatch, lambda: {
        "source": "ted", "status": "rate_limited",
    })
    row = report["ted_sampling_audit"]["date_window_results"][-1]
    assert row["failure_reason_code"] == "provider_rate_limited"
    assert row["sampled_rows"] == 0
    assert "2026" in discovery.format_discovery_report(report)
    # Bounded newest-first neutral sample remains separate from optional
    # CPV-filtered source population.
    assert report["ted_sampling_audit"]["observed_notice_count"] == 2
