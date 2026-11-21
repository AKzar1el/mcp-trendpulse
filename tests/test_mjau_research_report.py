"""M14: bounded, inspectable public-source synthesis without demand fiction."""
from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner

from mcp_trendpulse.cli import cli
from mcp_trendpulse.intelligence_research import (
    MAX_INPUT_BYTES, MAX_INPUT_SIGNALS, format_public_research,
    synthesize_public_research,
)
from mcp_trendpulse.intelligence_signal import TrendSignal

NOW = datetime(2026, 11, 21, 1, tzinfo=timezone.utc)
START = date(2026, 11, 1)
FIXTURE = (
    Path(__file__).resolve().parent.parent
    / "docs" / "examples" / "mjau-m14-real-multisource-signals.json"
)
SOURCE = {
    "bing_keyword_impressions": (
        "bing_webmaster_keyword_research",
        "https://ssl.bing.com/webmaster/api.svc/json/GetKeywordStats",
        "impressions",
    ),
    "google_trends_normalized_interest": (
        "google_trends_idea_related_queries",
        "https://trends.google.com/trends/explore",
        "relative_index_0_100",
    ),
    "wikimedia_pageviews": (
        "wikimedia_pageviews",
        "https://wikimedia.org/api/rest_v1/metrics/pageviews",
        "pageviews",
    ),
    "news_mention_count": (
        "news_mention_count",
        "https://news.google.com/rss",
        "mentions",
    ),
    "github_issue_mentions": (
        "github_issue_mentions",
        "https://api.github.com/search/issues",
        "issues",
    ),
    "hacker_news_story_mentions": (
        "hacker_news_story_mentions",
        "https://hn.algolia.com/api/v1/search_by_date",
        "stories",
    ),
    "stackexchange_question_mentions": (
        "stackexchange_question_mentions",
        "https://stackoverflow.com/questions/80015847",
        "questions",
    ),
    "npm_package_downloads": (
        "npm_package_downloads",
        "https://api.npmjs.org/downloads/range/last-week/zod",
        "downloads",
    ),
    "pypi_package_downloads": (
        "pypi_package_downloads",
        "https://pypistats.org/api/packages/pydantic/overall?mirrors=false",
        "downloads",
    ),
    "google_bigquery_rank": (
        "google_trends_bigquery_public",
        "https://cloud.google.com/blog/products/data-analytics/international-google-trends-datasets-in-bigquery",
        "rank",
    ),
    "generated_keyword_candidate": (
        "local_derived_candidate",
        "https://github.com/AKzar1el/mcp-trendpulse",
        "none",
    ),
}


def record(
    *, metric="wikimedia_pageviews", term="Python",
    day=START, value=10, status="observed",
    country=None, language=None, scope="one bounded provider source sample",
    record_id="s:1", observed_at=NOW, source_id=None, source_url=None,
    method=None, query=False, granularity="daily",
):
    sid, url, unit = SOURCE[metric]
    if metric == "generated_keyword_candidate":
        status = "not_measured"
        value = None
        method = "derived"
        query = False
    if status in ("unavailable", "no_data"):
        value = None
    model = TrendSignal(
        source_id=source_id or sid,
        source_url=source_url or url,
        observed_at=observed_at,
        country=country, language=language,
        raw_term=term, normalized_term=term.casefold(),
        metric_type=metric, metric_unit=unit,
        period={
            "start_date": day, "end_date": day,
            "granularity": granularity,
        },
        value=value,
        coverage_status=status,
        sampling_scope=scope,
        provenance={
            "method": method or "official_api",
            "source_record_id": record_id,
            "sampling_basis": "bounded_exact_source_record",
            "is_observed_search_query": query,
        },
    )
    return model.model_dump(mode="json")


def query_history(
    previous=10, current=30, *, metric="google_trends_normalized_interest",
    observed_at=NOW, country="US", language="en", term="AI agents",
):
    return [
        record(
            metric=metric, term=term, value=(previous if day < 7 else current),
            day=START + timedelta(days=day),
            country=country, language=language,
            record_id=f"day-{day}", observed_at=observed_at, query=True,
            scope="one source normalization batch" if metric.startswith("google")
            else "one weekly exact source sample",
        )
        for day in range(14)
    ]


def test_genuine_seven_source_family_cached_fixture_has_no_fake_demand():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(data["signals"]) == 42
    report = synthesize_public_research(data)
    assert report["mode"] == "offline_source_attributed_cross_source_research"
    assert report["input_signal_records"] == 42
    assert report["deduplicated_source_records"] == 42
    assert report["network_performed"] is False
    assert report["sqlite_or_quotas_modified"] is False
    assert report["source_provider_operations"] == 0
    assert report["paid_services_used"] is False
    assert report["new_background_automation_created"] is False
    assert report["site_property_required"] is False
    assert report["source_metric_values_aggregated"] is False
    assert report["market_demand_score"] is None
    assert report["search_volume_estimate"] is None
    assert report["rising_queries"] == []
    assert report["observed_query_candidates"] == []
    assert report["product_hypotheses"] == []
    assert len(report["source_inventory"]) == 7
    assert len(report["country_language_interest"]) >= 2
    assert len(report["independent_attention"]) >= 1
    assert len(report["developer_problem_evidence"]) >= 2
    assert len(report["package_adoption_evidence"]) == 2
    assert report["next_validation_action"]["priority"] == (
        "source_attested_search_queries"
    )
    assert any(x["kind"] == "observed_query_missing" for x in report["data_gaps"])
    assert any(x["kind"] == "developer_need_not_verified" for x in report["data_gaps"])
    assert any(x["kind"] == "download_events_not_people" for x in report["data_gaps"])
    assert any(x["kind"] == "market_geography_unspecified" for x in report["data_gaps"])
    assert any(item["source_url"].startswith("https://") for item in
               report["developer_problem_evidence"])
    assert all(item["source_metric_values_summed"] is False for item in
               report["package_adoption_evidence"])
    assert all(item["country"] is None for item in
               report["package_adoption_evidence"])
    assert all(item["semantic_equivalence_verified"] is False for item in
               report["keyword_families"])
    assert "causality" in report["methodology_note"]
    assert "re-fetched" in report["offline_evidence_caution"]


def test_genuine_fixture_separate_npm_pypi_totals_not_merged():
    out = synthesize_public_research(json.loads(FIXTURE.read_text("utf-8")))
    packages = {item["source_id"]: item
                for item in out["package_adoption_evidence"]}
    assert set(packages) == {"npm_package_downloads", "pypi_package_downloads"}
    assert packages["npm_package_downloads"]["source_records_in_supplied_sample"] == 7
    assert packages["pypi_package_downloads"]["source_records_in_supplied_sample"] == 7
    assert packages["npm_package_downloads"]["metric_unit"] == "downloads"
    assert packages["pypi_package_downloads"]["metric_unit"] == "downloads"
    assert packages["npm_package_downloads"]["source_url"].startswith("https://api.npmjs.org/")
    assert packages["pypi_package_downloads"]["source_url"].startswith("https://pypistats.org/")
    assert all(s["source_metric_values_summed"] is False for s in packages.values())


def test_genuine_public_provider_metadata_is_direct_and_measured_missingness():
    out = synthesize_public_research(json.loads(FIXTURE.read_text("utf-8")))
    developer = out["developer_problem_evidence"]
    assert any("stackoverflow.com/questions/80015847" in item["source_url"]
               for item in developer)
    assert any("news.ycombinator.com/item" in item["source_url"]
               for item in developer)
    assert all(item["family"] == "developer_discussion_unverified_problem"
               for item in developer)
    assert all(item["source_records_are_not_people_or_customers"] for item in developer)
    assert all(item["observations"][0]["source_recontacted_for_this_report"] is False
               for item in developer)


def test_query_attestation_required_even_for_bing_api_keyword_stats():
    rows = [
        record(metric="bing_keyword_impressions", value=10, query=False,
               country="US", language="en")
    ]
    out = synthesize_public_research(rows)
    assert out["observed_query_candidates"] == []
    item = out["country_language_interest"][0]["observations"][0]
    assert item["evidence_level"] == "keyword_research_impressions_not_search_logs"
    assert item["observed_query_flag"] is False


def test_two_fully_observed_normalized_query_windows_may_be_called_rising():
    out = synthesize_public_research(query_history())
    assert len(out["observed_query_candidates"]) == 14
    assert len(out["rising_queries"]) == 1
    rise = out["rising_queries"][0]
    assert rise["term"] == "ai agents"
    assert rise["country"] == "US"
    assert rise["language"] == "en"
    assert rise["previous_window_mean_in_original_unit"] == 10
    assert rise["recent_window_mean_in_original_unit"] == 30
    assert rise["source_specific_change_pct"] == 200
    assert rise["source_units_not_comparable_across_providers"] is True
    assert rise["search_volume_verified"] is False
    assert rise["acceleration_verified"] is False
    assert rise["future_growth_forecast"] is False
    assert len(rise["source_reference_ids"]) == 14


def test_query_increase_is_not_proof_of_acceleration():
    out = synthesize_public_research(query_history(previous=10, current=13))
    assert len(out["rising_queries"]) == 1
    assert out["rising_queries"][0]["acceleration_verified"] is False
    assert "two_complete" in out["rising_queries"][0]["comparison_type"]


def test_less_than_25pct_query_increase_not_rising():
    out = synthesize_public_research(query_history(previous=10, current=12))
    assert out["rising_queries"] == []
    assert len(out["observed_query_candidates"]) == 14


def test_actual_source_measured_zero_not_missing_or_rising():
    out = synthesize_public_research(query_history(previous=0, current=20))
    assert out["rising_queries"] == []
    assert all(item["measured_value"] == 0 for item in
               out["observed_query_candidates"] if
               item["period"]["start_date"] <= "2026-11-07")
    assert any(x["kind"] == "rising_query_evidence_missing" for x in out["data_gaps"])


def test_missing_day_or_only_7_days_prevents_false_growth():
    rows = query_history()
    assert synthesize_public_research(rows[:7])["rising_queries"] == []
    del rows[8]
    assert synthesize_public_research(rows)["rising_queries"] == []


@pytest.mark.parametrize("status", ["partial", "unavailable", "no_data"])
def test_partial_or_missing_source_query_does_not_count_as_rising(status):
    rows = query_history()
    row = record(
        metric="google_trends_normalized_interest", term="AI agents",
        day=START + timedelta(days=10),
        value=None if status != "partial" else 30,
        status=status, country="US", language="en",
        scope="one source normalization batch",
        query=True, record_id="day-10",
    )
    rows[10] = row
    out = synthesize_public_research(rows)
    assert out["rising_queries"] == []
    assert any(x["kind"] == "source_coverage" for x in out["data_gaps"])
    if status in ("unavailable", "no_data"):
        assert all(item["measured_value"] is None for g in
                   out["country_language_interest"] for item in g["observations"]
                   if item["coverage_status"] == status)


def test_different_google_normalization_batches_never_compared():
    rows = query_history()
    bad = dict(rows[9])
    bad["observed_at"] = (NOW + timedelta(minutes=4)).isoformat()
    rows[9] = bad
    out = synthesize_public_research(rows)
    assert out["rising_queries"] == []
    assert out["search_volume_estimate"] is None


def test_single_explosive_last_day_is_one_off_not_rising_query():
    rows = query_history(
        previous=10, current=10, metric="bing_keyword_impressions",
    )
    rows[-1] = dict(rows[-1])
    rows[-1]["value"] = 700
    out = synthesize_public_research(rows)
    assert out["rising_queries"] == []


def test_operator_supplied_query_flag_does_not_become_observed_logs():
    rows = query_history()
    for row in rows:
        row["provenance"]["method"] = "operator_supplied"
    out = synthesize_public_research(rows)
    assert out["observed_query_candidates"] == []
    assert out["rising_queries"] == []
    assert out["country_language_interest"][0]["observations"][0][
        "evidence_level"
    ] == "operator_or_derived_source_claim"


def test_unrelated_rank_or_trending_bucket_never_becomes_source_rising():
    rank = record(metric="google_bigquery_rank", value=1, query=True)
    out = synthesize_public_research([rank])
    assert out["rising_queries"] == []
    assert out["observed_query_candidates"] == []
    assert out["country_language_interest"][0]["observations"][0][
        "evidence_level"
    ] == "relative_source_rank"


def test_data_gaps_dont_turn_no_data_into_zero_or_hypothesis():
    rows = [
        record(metric="wikimedia_pageviews", value=None, status="no_data"),
        record(metric="npm_package_downloads", value=None, status="unavailable"),
    ]
    out = synthesize_public_research(rows)
    assert out["independent_attention"] == []
    assert out["package_adoption_evidence"] == []
    assert out["rising_queries"] == []
    assert out["market_demand_score"] is None
    assert sum(g["kind"] == "source_coverage" for g in out["data_gaps"]) == 2
    assert out["product_hypotheses"] == []


def test_generated_term_only_creates_unverified_product_hypothesis():
    generated = record(
        metric="generated_keyword_candidate",
        term="agent reliability monitoring",
        method="derived", value=None, status="not_measured",
    )
    out = synthesize_public_research([generated])
    assert out["observed_query_candidates"] == []
    assert out["rising_queries"] == []
    assert out["independent_attention"] == []
    assert len(out["product_hypotheses"]) == 1
    hypothesis = out["product_hypotheses"][0]
    assert hypothesis["evidence_level"] == "hypothetical_business_opportunity"
    assert hypothesis["demand_verified"] is False
    assert hypothesis["buyer_intent_verified"] is False
    assert hypothesis["product_recommendation"] is False
    assert "willingness" in hypothesis["validation_question"]


def test_generated_and_observed_same_term_never_fused_into_one_evidence_level():
    generated = record(
        metric="generated_keyword_candidate", term="AI agents",
        method="derived",
    )
    query = query_history()[0]
    report = synthesize_public_research([generated, query])
    families = [
        f for f in report["keyword_families"]
        if f["representative"].casefold() == "ai agents"
    ]
    assert len(families) == 2
    assert {f["evidence_level"] for f in families} == {
        "generated_keyword_hypothesis", "source_attested_query",
    }
    assert all(f["source_metric_values_aggregated"] is False for f in families)


def test_source_reference_duplicates_collapsed_and_order_deterministic():
    rows = [
        record(metric="wikimedia_pageviews", term="Python", record_id="wiki-one"),
        record(metric="news_mention_count", term="Python", record_id="news-two"),
    ]
    first = synthesize_public_research(rows + rows[:1])
    reversed_report = synthesize_public_research(list(reversed(rows)) + rows[:1])
    assert first == reversed_report
    assert first["input_signal_records"] == 3
    assert first["deduplicated_source_records"] == 2
    assert first["exact_input_duplicates_collapsed"] == 1
    overlaps = first["source_diversity_exact_term_only"]
    assert len(overlaps) == 1
    assert overlaps[0]["source_count"] == 2
    assert overlaps[0]["semantic_or_customer_independence_verified"] is False


def test_country_language_boundaries_and_null_country_never_global():
    rows = [
        record(metric="wikimedia_pageviews", country="SI", language="sl", record_id="1"),
        record(metric="wikimedia_pageviews", country="DE", language="de", record_id="2"),
        record(metric="wikimedia_pageviews", country=None, language="en", record_id="3"),
    ]
    report = synthesize_public_research(rows)
    countries = {
        (group["country"], group["language"]) for group in report["independent_attention"]
    }
    assert countries == {("SI", "sl"), ("DE", "de"), (None, "en")}
    assert report["source_diversity_exact_term_only"] == []
    assert any(x["kind"] == "market_geography_unspecified" for x in report["data_gaps"])


@pytest.mark.parametrize("term_pair", [
    ("c++ agent failure", "c# agent failure"),
    ("agent reliability free", "agent reliability paid"),
    ("not working agent", "working agent"),
    ("café monitoring", "cafe monitoring"),
])
def test_m02_lexical_guard_does_not_claim_semantic_equivalence(term_pair):
    left, right = term_pair
    rows = [
        record(metric="wikimedia_pageviews", term=left, record_id="x1"),
        record(metric="wikimedia_pageviews", term=right, record_id="x2"),
    ]
    output = synthesize_public_research(rows)
    assert len(output["keyword_families"]) == 2
    assert all(f["semantic_equivalence_verified"] is False
               for f in output["keyword_families"])


def test_same_term_many_source_dates_one_lexical_family_with_bounded_references():
    rows = [
        record(
            metric="wikimedia_pageviews",
            term="Python", day=START + timedelta(days=i),
            record_id=f"day-{i}",
        )
        for i in range(14)
    ]
    out = synthesize_public_research(rows)
    assert len(out["keyword_families"]) == 1
    family = out["keyword_families"][0]
    assert family["source_reference_count"] == 14
    assert len(family["evidence_refs"]) == 12
    assert family["references_truncated"] is True
    assert out["independent_attention"][0]["source_records_in_supplied_sample"] == 14
    assert out["independent_attention"][0]["observations_truncated"] is True


def test_source_level_specific_metric_units_not_combined_in_attention():
    rows = [
        record(metric="wikimedia_pageviews", term="AI agents",
               country=None, language=None, record_id="wiki"),
        record(metric="news_mention_count", term="AI agents",
               country=None, language=None, record_id="news"),
    ]
    out = synthesize_public_research(rows)
    assert len(out["independent_attention"]) == 2
    assert {g["metric_unit"] for g in out["independent_attention"]} == {
        "pageviews", "mentions",
    }
    assert all(g["source_metric_values_summed"] is False for g in
               out["independent_attention"])
    assert out["source_diversity_exact_term_only"][0]["source_count"] == 2


def test_packaging_downloads_cannot_be_search_volume_or_unique_users():
    rows = [
        record(metric="npm_package_downloads", term="zod", value=10000),
        record(metric="pypi_package_downloads", term="pydantic", value=1000000),
    ]
    out = synthesize_public_research(rows)
    assert out["country_language_interest"] == []
    assert out["observed_query_candidates"] == []
    assert out["search_volume_estimate"] is None
    assert out["market_demand_score"] is None
    assert all(group["source_records_are_not_people_or_customers"]
               for group in out["package_adoption_evidence"])
    assert out["next_validation_action"]["priority"] == (
        "source_attested_search_queries"
    )


@pytest.mark.parametrize("bad_url", [
    "https://127.0.0.1/internal",
    "https://localhost/private",
    "https://host.local/private",
    "https://10.0.0.5/secret",
    "https://[::1]/",
    "https://example.org:8443/private",
    "http://example.org/plain",
    "https://example.org/path?api_key=PRIVATE",
    "https://u:pass@example.org/path",
])
def test_unsafe_or_credential_source_url_refused_without_leak(bad_url):
    row = record()
    row["source_url"] = bad_url
    with pytest.raises(ValueError) as info:
        synthesize_public_research([row])
    assert "PRIVATE" not in str(info.value)
    assert "pass" not in str(info.value)


@pytest.mark.parametrize("term", [
    "reach user@example.com for troubleshooting",
    "sk-abcdefghijklmnopqrstuv0123456789",
    "ghp_abcdefgh1234567890abcdefghijkl",
])
def test_secret_bearing_source_terms_rejected_without_echo(term):
    row = record()
    row["raw_term"] = term
    row["normalized_term"] = term.casefold()
    with pytest.raises(ValueError) as info:
        synthesize_public_research([row])
    assert term not in str(info.value)


@pytest.mark.parametrize("payload", [
    [],
    {},
    {"signals": []},
    {"signals": [record()], "private": "SECRET"},
    123,
    "untrusted",
    [{"not_a_typed_signal": "SECRET"}],
    [record()] * (MAX_INPUT_SIGNALS + 1),
])
def test_invalid_root_and_large_record_count_fail_closed(payload):
    with pytest.raises(ValueError) as info:
        synthesize_public_research(payload)
    assert "SECRET" not in str(info.value)


def test_json_input_exceeds_128k_refused():
    rows = [
        record(
            metric="wikimedia_pageviews", term="P"*150,
            scope=f"sample observation {i} " + "x"*145,
            record_id=str(i),
            source_url="https://data.example.org/" + "a"*530,
        )
        for i in range(MAX_INPUT_SIGNALS)
    ]
    with pytest.raises(ValueError, match="exceeds"):
        synthesize_public_research(rows)


def test_output_limit_on_keyword_families_does_not_drop_source_inventory():
    import hashlib

    # Distinct opaque identifiers are intentionally NOT near-duplicates;
    # "unique term number 001/002" actually is near-duplicate by M02.
    rows = [
        record(
            metric="wikimedia_pageviews",
            term="niche " + hashlib.sha256(str(i).encode()).hexdigest()[:24],
            record_id=str(i),
        )
        for i in range(120)
    ]
    report = synthesize_public_research(rows)
    assert len(report["keyword_families"]) == 80
    assert report["keyword_families_truncated"] is True
    assert report["deduplicated_source_records"] == 120
    assert report["source_inventory"][0]["source_observations_in_input"] == 120
    assert report["source_group_totals"]["independent_attention"] == 120
    assert report["source_group_previews_truncated"]["independent_attention"] is True
    assert len(report["independent_attention"]) == 24
    assert all(group["source_metric_values_summed"] is False
               for group in report["independent_attention"])


def test_provenance_source_record_id_and_period_preserved():
    report = synthesize_public_research([
        record(metric="stackexchange_question_mentions",
               term="Asyncio Unhandled Exception in atexit", value=1,
               record_id="stack:80015847", status="partial"),
    ])
    item = report["developer_problem_evidence"][0]["observations"][0]
    assert item["source_record_id"] == "stack:80015847"
    assert item["source_url"] == "https://stackoverflow.com/questions/80015847"
    assert item["period"]["granularity"] == "daily"
    assert item["source_value_label"] is None
    assert item["partial_source_value"] == 1
    assert item["measured_value"] is None
    assert item["source_claim_reverified_online"] is False


def test_mcp_read_only_prompt_direct_invocation_does_not_contact_providers(monkeypatch):
    import sqlite3
    import requests
    from mcp_trendpulse.hosted import source_evidence_research_report

    def forbid(*_args, **_kwargs):
        raise AssertionError("M14 MUST NOT connect, even when MCP prompt called")

    monkeypatch.setattr(sqlite3, "connect", forbid)
    monkeypatch.setattr(requests.Session, "get", forbid)
    source = json.dumps([record(metric="wikimedia_pageviews")])
    result = json.loads(source_evidence_research_report(source, "json"))
    assert result["network_performed"] is False
    assert result["source_provider_operations"] == 0
    assert len(result["independent_attention"]) == 1


def test_mcp_prompt_registered_without_changing_six_hosted_tools():
    from mcp_trendpulse.hosted import hosted_mcp

    prompts = asyncio.run(hosted_mcp.list_prompts())
    assert "source_evidence_research_report" in {p.name for p in prompts}
    assert len(asyncio.run(hosted_mcp.list_tools())) == 6


def test_real_fixture_cli_text_and_json_are_readable_and_sourced():
    runner = CliRunner()
    json_out = runner.invoke(cli, [
        "intelligence", "research-report",
        "--input", str(FIXTURE), "--format", "json",
    ])
    assert json_out.exit_code == 0, json_out.output
    report = json.loads(json_out.output)
    assert report["input_signal_records"] == 42
    assert report["network_performed"] is False
    human = runner.invoke(cli, [
        "intelligence", "research-report",
        "--input", str(FIXTURE), "--format", "text",
    ])
    assert human.exit_code == 0, human.output
    assert "M14 OFFLINE SOURCE-ATTRIBUTED" in human.output
    assert "https://wikimedia.org/" in human.output
    assert "https://pypistats.org/" in human.output
    assert "Next validation:" in human.output
    assert "No network." in human.output


def test_cli_error_does_not_echo_sensitive_payload_or_oversized_file(tmp_path):
    path = tmp_path/"report.json"
    path.write_text("x"*(MAX_INPUT_BYTES+1), encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(cli, [
        "intelligence", "research-report",
        "--input", str(path), "--format", "json",
    ])
    assert result.exit_code != 0
    assert "oversized" in result.output.lower()
    path.write_text('{"signals":[{"token":"SUPER_PRIVATE_SECRET"}]}', encoding="utf-8")
    invalid = runner.invoke(cli, [
        "intelligence", "research-report",
        "--input", str(path), "--format", "json",
    ])
    assert invalid.exit_code != 0
    assert "SUPER_PRIVATE_SECRET" not in invalid.output


def test_qualification_of_relative_interest_does_not_leak_absolute_volume():
    out = synthesize_public_research([record(
        metric="google_trends_normalized_interest",
        value=85, country="SI", language="sl",
    )])
    item = out["country_language_interest"][0]["observations"][0]
    assert item["evidence_level"] == "relative_search_interest_not_volume"
    assert item["measured_value"] == 85
    assert item["metric_unit"] == "relative_index_0_100"
    assert out["search_volume_estimate"] is None
    assert out["rising_queries"] == []


def test_data_gap_density_does_not_hide_observed_query_missing():
    rows = [
        record(
            metric="hacker_news_story_mentions",
            value=1, status="partial",
            source_url=f"https://news.ycombinator.com/item?id={100000+i}",
            record_id=f"story-{i}",
        )
        for i in range(30)
    ]
    out = synthesize_public_research(rows)
    kinds = {gap["kind"] for gap in out["data_gaps"]}
    assert "observed_query_missing" in kinds
    assert "rising_query_evidence_missing" in kinds
    assert "developer_need_not_verified" in kinds
    assert out["source_metric_values_aggregated"] is False


def test_text_formatter_does_not_invent_source_metrics():
    report = synthesize_public_research([
        record(metric="wikimedia_pageviews", term="Python", value=1234),
    ])
    text = format_public_research(report)
    assert "source" in text.lower()
    assert "1234 searches" not in text
    assert "product" in text.lower()
    assert "No network" in text

def test_many_attested_queries_have_total_counts_and_safe_preview_cap():
    rows = [
        record(
            metric="bing_keyword_impressions", term=f"source query {i:03d}",
            country="US", language="en", query=True, record_id=f"q:{i}",
        )
        for i in range(30)
    ]
    report = synthesize_public_research(rows)
    assert report["observed_query_candidates_total"] == 30
    assert len(report["observed_query_candidates"]) == 24
    assert report["observed_query_candidates_truncated"] is True
    assert report["source_group_totals"]["country_language_interest"] == 30
    assert len(report["country_language_interest"]) == 24
    assert report["source_group_previews_truncated"]["country_language_interest"]
    assert report["rising_queries"] == []
    assert report["search_volume_estimate"] is None


def test_generated_hypothesis_preview_is_bounded_but_count_exact():
    rows = [
        record(
            metric="generated_keyword_candidate",
            term=f"unvalidated hypothesis {i:03d}", record_id=f"h:{i}",
        )
        for i in range(25)
    ]
    report = synthesize_public_research(rows)
    assert report["product_hypotheses_total"] == 25
    assert len(report["product_hypotheses"]) == 24
    assert report["product_hypotheses_truncated"] is True
    assert all(not row["buyer_intent_verified"] for row in report["product_hypotheses"])
    assert report["observed_query_candidates_total"] == 0
    assert report["market_demand_score"] is None
