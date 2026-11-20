"""M00 global signal schema: no source calls, cross-market leakage or fake demand."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from mcp_trendpulse.cli import cli
from mcp_trendpulse.intelligence_signal import (
    SignalPeriod, SignalProvenance, TrendSignal, signal_contract_spec,
)

OBSERVED = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)


def build(**changes):
    row = {
        "source_id": "google_trends",
        "source_url": "https://trends.google.com/trends/",
        "observed_at": OBSERVED,
        "country": "SI",
        "language": "sl",
        "raw_term": "Umetna inteligenca",
        "normalized_term": "umetna inteligenca",
        "metric_type": "google_trends_normalized_interest",
        "metric_unit": "relative_index_0_100",
        "period": SignalPeriod(
            start_date=date(2026, 11, 13),
            end_date=date(2026, 11, 20),
            granularity="daily",
        ),
        "value": 72,
        "sampling_scope": "Google Trends Explore query: SI, selected week",
        "coverage_status": "observed",
        "provenance": SignalProvenance(
            method="community_provider", sampling_basis="normalized_google_trends_series",
            is_observed_search_query=True,
        ),
    }
    row.update(changes)
    return TrendSignal(**row)


def test_normalized_interest_retains_observation_and_market_provenance():
    signal = build()
    assert signal.country == "SI" and signal.language == "sl"
    assert signal.raw_term == "Umetna inteligenca"
    assert signal.metric_unit == "relative_index_0_100"
    assert signal.value == 72.0
    assert signal.model_dump(mode="json")["observed_at"] == "2026-11-20T12:00:00Z"
    assert signal.provenance.is_observed_search_query
    assert TrendSignal.model_validate_json(signal.model_dump_json()) == signal
    with pytest.raises(ValidationError):
        signal.country = "US"


def test_arbitrary_keyword_bing_impressions_not_site_property_metrics():
    signal = build(
        source_id="bing_keyword_research",
        source_url="https://ssl.bing.com/webmaster/api.svc/json/GetKeywordStats",
        country="DE", language="de",
        raw_term="welche software kaufen", normalized_term="welche software kaufen",
        metric_type="bing_keyword_impressions", metric_unit="impressions",
        value=420, sampling_scope="Bing keyword research: country DE, language de",
        provenance=SignalProvenance(
            method="official_api", sampling_basis="independent_search_keyword",
            is_observed_search_query=True,
        ),
    )
    assert signal.country == "DE"
    assert signal.value == 420
    assert "site_url" not in signal.model_dump()


def test_approximate_google_traffic_bucket_never_converts_to_absolute_volume():
    signal = build(metric_type="google_trending_traffic_bucket",
                   metric_unit="approximate_search_bucket", value=None,
                   value_label="10K+", coverage_status="observed",
                   provenance=SignalProvenance(
                       method="public_rss", sampling_basis="trending_now_feed",
                       is_observed_search_query=True,
                   ))
    assert signal.value is None
    assert signal.value_label == "10K+"
    with pytest.raises(ValidationError):
        build(metric_type="google_trending_traffic_bucket",
              metric_unit="approximate_search_bucket",
              value=10000, value_label="10K+")


def test_source_unavailable_partial_observation_and_zero_are_distinct():
    missing = build(value=None, coverage_status="unavailable")
    assert missing.value is None
    assert missing.coverage_status == "unavailable"
    with pytest.raises(ValidationError):
        build(value=0, coverage_status="unavailable")
    partial = build(value=20, coverage_status="partial")
    assert partial.value == 20
    observed_zero = build(value=0, coverage_status="observed")
    assert observed_zero.value == 0


def test_generated_keywords_are_not_labeled_observed_google_searches():
    conjecture = build(
        source_id="keyword_research",
        source_url="https://trends.google.com/trends/",
        metric_type="generated_keyword_candidate", metric_unit="none",
        value=None, coverage_status="not_measured",
        provenance=SignalProvenance(
            method="derived", sampling_basis="source_title_phrase_expansion",
            is_observed_search_query=False,
        ),
    )
    assert conjecture.value is None
    assert not conjecture.provenance.is_observed_search_query
    with pytest.raises(ValidationError):
        build(
            metric_type="generated_keyword_candidate", metric_unit="none",
            value=None, coverage_status="not_measured",
            provenance=SignalProvenance(
                method="derived", sampling_basis="generated_phrase",
                is_observed_search_query=True,
            ),
        )


@pytest.mark.parametrize("updates", [
    {"metric_type": "bing_keyword_impressions", "metric_unit": "relative_index_0_100"},
    {"metric_type": "google_trends_normalized_interest", "value": 101},
    {"value": -1},
    {"value": float("nan")},
    {"value": float("inf")},
    {"value": True},
    {"value": "20"},
    {"metric_type": "github_issue_mentions", "metric_unit": "issues", "value": 1.3},
    {"metric_type": "google_bigquery_rank", "metric_unit": "rank", "value": 0},
    {"metric_type": "npm_package_downloads", "metric_unit": "downloads", "value": 1.5},
])
def test_reject_incompatible_metric_units_fabricated_values(updates):
    with pytest.raises(ValidationError):
        build(**updates)


@pytest.mark.parametrize("url", [
    "http://trends.google.com/trends/",
    "https://user:password@example.com/a",
    "https://example.com/a?api_key=TOP_SECRET",
    "https://example.com/a?token=TOP_SECRET",
    "https://example.com/a#secret",
    "javascript:alert(1)",
])
def test_public_reference_rejects_transport_and_secret_urls(url):
    with pytest.raises(ValidationError):
        build(source_url=url)


def test_market_unspecified_never_means_all_countries():
    unspecified = build(country=None, language=None)
    assert unspecified.country is None and unspecified.language is None
    with pytest.raises(ValidationError):
        build(country="WORLD")
    with pytest.raises(ValidationError):
        build(country="si")
    with pytest.raises(ValidationError):
        build(language="bad_locale_999")
    local = build(language="sl-SI")
    assert local.language == "sl-SI"


def test_timestamp_order_and_date_range_are_explicit():
    with pytest.raises(ValidationError):
        build(observed_at=datetime(2026, 11, 20, 12, 0))
    with pytest.raises(ValidationError):
        build(published_at=OBSERVED + timedelta(seconds=1))
    with pytest.raises(ValidationError):
        SignalPeriod(start_date=date(2026, 11, 21),
                     end_date=date(2026, 11, 20), granularity="daily")
    zoned = build(observed_at=OBSERVED.astimezone(timezone(timedelta(hours=1))))
    assert zoned.observed_at == OBSERVED


def test_input_schema_rejects_unknown_provider_payload_properties():
    with pytest.raises(ValidationError):
        build(secret="DO_NOT_PERSIST", raw_payload={"api_key": "A"})
    data = signal_contract_spec()
    assert data["schema_version"] == 1
    assert data["network_performed"] is False
    assert data["new_provider_added"] is False
    assert data["site_property_required"] is False
    assert data["metric_types"]["bing_keyword_impressions"]["unit"] == "impressions"
    assert data["schema"]["additionalProperties"] is False


def test_offline_cli_intelligence_signal_schema_json_and_text(monkeypatch):
    from mcp_trendpulse import intelligence_core

    monkeypatch.setattr(
        intelligence_core, "collect",
        lambda *_a, **_kw: (_ for _ in ()).throw(
            AssertionError("M00 schema must be network-free")),
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["intelligence", "signal-schema", "--format", "json"])
    assert result.exit_code == 0, result.output
    schema = json.loads(result.output)
    assert schema["network_performed"] is False
    assert "google_trending_traffic_bucket" in schema["metric_types"]
    assert "generated_keyword_candidate" in schema["metric_types"]
    assert "raw_term" in schema["schema"]["properties"]
    text = runner.invoke(cli, ["intelligence", "signal-schema", "--format", "text"])
    assert text.exit_code == 0, text.output
    assert "offline" in text.output.lower()
    assert "unavailable" in text.output.lower()
    assert "property" in text.output.lower()
