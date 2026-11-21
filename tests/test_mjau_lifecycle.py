"""MJAU M13: conservative lifecycle, provenance, and no fabricated momentum."""
from __future__ import annotations

import json
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone

import pytest
from click.testing import CliRunner

from mcp_trendpulse.cli import cli
from mcp_trendpulse.intelligence_lifecycle import (
    MAX_INPUT_BYTES, MAX_SIGNALS, _weekly_repetition, analyze_lifecycle,
)
from mcp_trendpulse.intelligence_signal import (
    SignalPeriod, SignalProvenance, TrendSignal,
)

OBSERVED = datetime(2026, 11, 21, 1, tzinfo=timezone.utc)
DAY0 = date(2026, 10, 1)
WEEK0 = date(2026, 7, 4)
MONTH0 = date(2025, 1, 1)
UNIT = {
    "npm_package_downloads": "downloads",
    "pypi_package_downloads": "downloads",
    "wikimedia_pageviews": "pageviews",
    "google_trends_normalized_interest": "relative_index_0_100",
    "google_bigquery_rank": "rank",
    "google_trending_traffic_bucket": "approximate_search_bucket",
    "generated_keyword_candidate": "none",
}
SOURCE = {
    "npm_package_downloads": ("npm_package_downloads",
                              "https://api.npmjs.org/downloads/range/last-month/zod"),
    "pypi_package_downloads": ("pypi_package_downloads",
                               "https://pypistats.org/api/packages/pydantic/overall?mirrors=false"),
    "wikimedia_pageviews": ("wikimedia_pageviews",
                             "https://wikimedia.org/api/rest_v1/metrics/pageviews"),
    "google_trends_normalized_interest": ("google_trends_idea_related_queries",
                                          "https://trends.google.com/trends/explore"),
    "google_bigquery_rank": ("google_trends_bigquery_public",
                              "https://console.cloud.google.com/bigquery"),
    "google_trending_traffic_bucket": ("google_trending_now_public_rss",
                                       "https://trends.google.com/trending/rss"),
    "generated_keyword_candidate": ("generated_keyword_candidate",
                                     "https://example.org/local"),
}


def _month(d: date, offset: int) -> date:
    idx = d.year * 12 + d.month - 1 + offset
    return date(idx // 12, idx % 12 + 1, 1)


def _anchor(idx: int, grain: str) -> date:
    if grain == "daily":
        return DAY0 + timedelta(days=idx)
    if grain == "weekly":
        return WEEK0 + timedelta(days=7 * idx)
    if grain == "monthly":
        return _month(MONTH0, idx)
    return DAY0 + timedelta(days=idx)


def point(
    value=10, idx=0, *, metric="npm_package_downloads",
    grain="daily", scope="official registry tarball requests",
    term="zod", country=None, language=None, status="observed",
    batch=OBSERVED, shape="label", record=None,
    source_id=None, source_url=None,
):
    sid, url = SOURCE[metric]
    d = _anchor(idx, grain)
    if grain == "weekly" and shape == "span":
        end = d + timedelta(days=6)
    elif grain == "monthly" and shape == "span":
        end = date(d.year, d.month, monthrange(d.year, d.month)[1])
    else:
        end = d
    if status in ("no_data", "unavailable"):
        value = None
    if metric == "generated_keyword_candidate":
        status = "not_measured"
        value = None
    data = TrendSignal(
        source_id=source_id or sid,
        source_url=source_url or url,
        observed_at=batch,
        country=country,
        language=language,
        raw_term=term,
        normalized_term=term.casefold(),
        metric_type=metric,
        metric_unit=UNIT[metric],
        period=SignalPeriod(start_date=d, end_date=end,
                            granularity=grain),
        value=value,
        value_label="100K+" if metric == "google_trending_traffic_bucket" else None,
        coverage_status=status,
        sampling_scope=scope,
        provenance=SignalProvenance(
            method="derived" if metric == "generated_keyword_candidate"
            else "official_api",
            source_record_id=record or f"sample-{grain}-{idx}",
            sampling_basis="same source-period observations",
            is_observed_search_query=False,
        ),
    )
    return data.model_dump(mode="json")


def history(values, *, metric="npm_package_downloads",
            grain="daily", scope="official registry tarball requests",
            term="zod", country=None, language=None, batch=OBSERVED,
            shape="label", source_id=None, source_url=None):
    return [
        point(value, i, metric=metric, grain=grain, scope=scope,
              term=term, country=country, language=language,
              batch=batch, shape=shape, source_id=source_id,
              source_url=source_url)
        for i, value in enumerate(values)
    ]


def single(series):
    assert series["source_series"] == 1
    return series["series"][0]


def test_no_network_no_provider_quota_and_observed_sustained_signal():
    result = analyze_lifecycle(history([10] * 7 + [11] * 7))
    g = single(result)
    assert g["status"] == "observed"
    assert g["lifecycle"] == "sustained"
    assert g["comparison"]["previous_window_mean"] == 10
    assert g["comparison"]["recent_window_mean"] == 11
    assert g["comparison"]["recent_vs_previous_pct"] == 10
    assert g["first_recorded_source_period"] == "2026-10-01"
    assert g["first_positive_observed_period"] == "2026-10-01"
    assert g["last_recorded_source_period"] == "2026-10-14"
    assert g["required_observed_periods"] == 14
    assert result["network_performed"] is False
    assert result["provider_operations"] == 0
    assert result["sqlite_or_quota_modified"] is False
    assert result["cross_source_metric_comparison_performed"] is False
    assert result["forecast_generated"] is False
    assert g["buyer_demand_verified"] is False
    assert g["annual_seasonality_verified"] is False


@pytest.mark.parametrize(("first", "recent", "expected"), [
    (10, 5, "declining"),
    (10, 8, "irregular_or_unclassified"),
    (10, 13, "rising_not_acceleration_verified"),
    (20, 20, "sustained"),
])
def test_complete_two_window_classification(first, recent, expected):
    g = single(analyze_lifecycle(history([first] * 7 + [recent] * 7)))
    assert g["lifecycle"] == expected
    if expected == "irregular_or_unclassified":
        assert g["status"] == "abstained"
    else:
        assert g["status"] == "observed"


def test_accelerating_requires_three_complete_growth_windows():
    values = [5] * 7 + [10] * 7 + [40] * 7
    g = single(analyze_lifecycle(history(values)))
    assert g["status"] == "observed"
    assert g["lifecycle"] == "accelerating"
    assert g["comparison"]["older_window_mean"] == 5
    assert g["comparison"]["prior_growth_ratio_minus_one"] == 1
    assert g["comparison"]["recent_growth_ratio_minus_one"] == 3
    assert "no causal" in g["reason"] or "forecast" in g["reason"]
    two = single(analyze_lifecycle(history([10] * 7 + [40] * 7)))
    assert two["lifecycle"] != "accelerating"
    assert two["lifecycle"] == "rising_not_acceleration_verified"


def test_sampled_recent_first_positive_is_not_ever_first_seen():
    g = single(analyze_lifecycle(history([0] * 7 + [0, 8, 9, 7, 8, 0, 10])))
    assert g["lifecycle"] == "new_in_observed_window"
    assert g["comparison"]["prior_positive_periods"] == 0
    assert g["first_positive_observed_period"] == "2026-10-09"
    assert g["new_source_or_user_growth_verified"] is False
    assert "NOT an established global first-seen" in g["reason"]


def test_reappearing_after_prior_positive_history_is_not_new():
    values = [12] * 7 + [0] * 7 + [8, 9, 8, 9, 10, 8, 8]
    g = single(analyze_lifecycle(history(values)))
    assert g["status"] == "observed"
    assert g["lifecycle"] == "resurfacing_in_observed_window"
    assert g["first_positive_observed_period"] == "2026-10-01"
    assert g["new_source_or_user_growth_verified"] is False
    assert "not" in g["reason"].lower()


def test_single_positive_after_observed_zeros_does_not_mean_new_trend():
    g = single(analyze_lifecycle(history([0] * 7 + [0] * 6 + [15])))
    assert g["status"] == "abstained"
    assert g["lifecycle"] == "unconfirmed_change"
    assert g["comparison"]["recent_vs_previous_pct"] is None
    assert g["comparison"]["recent_positive_periods"] == 1


def test_true_observed_zero_not_missing_data():
    g = single(analyze_lifecycle(history([10] * 7 + [0] * 7)))
    assert g["status"] == "observed"
    assert g["lifecycle"] == "declining"
    assert g["comparison"]["recent_window_mean"] == 0
    assert g["comparison"]["recent_vs_previous_pct"] == -100
    no_activity = single(analyze_lifecycle(history([0] * 14)))
    assert no_activity["lifecycle"] == "no_activity_observed"
    assert no_activity["status"] == "observed"


def test_single_outlier_is_not_accelerating_growth():
    values = [10] * 7 + [10, 10, 10, 150, 10, 10, 10]
    g = single(analyze_lifecycle(history(values)))
    assert g["status"] == "observed"
    assert g["lifecycle"] == "one_off_spike"
    assert g["comparison"]["recent_window_mean"] > 10
    assert g["forecast_generated"] is False


@pytest.mark.parametrize("status", ["partial", "unavailable", "no_data"])
def test_partial_or_unavailable_never_fakes_growth(status):
    rows = history([10] * 7 + [200] * 7)
    rows[10] = point(
        None if status in ("unavailable", "no_data") else 200, 10,
        status=status,
    )
    g = single(analyze_lifecycle(rows))
    assert g["status"] == "coverage_incomplete"
    assert g["source_coverage_incomplete"] is True
    assert g["lifecycle"] == "unknown"
    assert g["comparison"] is None


@pytest.mark.parametrize("cut", [4, 13])
def test_omitted_interior_day_never_inferred_zero_or_growth(cut):
    rows = history([10] * 8 + [40] * 8)
    del rows[cut]
    g = single(analyze_lifecycle(rows))
    assert g["status"] == "coverage_incomplete"
    assert g["missing_period_count"] == 1
    assert len(g["missing_period_dates_first_24"]) == 1
    assert g["comparison"] is None
    assert g["lifecycle"] == "unknown"


def test_missing_leading_day_cannot_be_detected_without_declared_source_window():
    original = history([10] * 8 + [40] * 8)
    omit_leading_day = original[1:]
    report = single(analyze_lifecycle(omit_leading_day))
    assert report["internal_observation_gaps_checked"] is True
    assert report["provider_declared_window_boundaries_verified"] is False
    assert report["missing_period_count"] == 0
    assert "leading" in report["boundary_coverage_caveat"]
    # This is a within-supplied-date-window heuristic, NOT a guarantee
    # that the provider's complete expected historical window was supplied.
    assert report["new_source_or_user_growth_verified"] is False


def test_incomplete_short_history_even_all_values_positive():
    g = single(analyze_lifecycle(history([5000] * 7)))
    assert g["status"] == "insufficient_history"
    assert g["required_observed_periods"] == 14
    assert g["periods_observed"] == 7
    assert g["comparison"] is None
    assert g["lifecycle"] == "unknown"


def test_volatile_alternating_bursts_not_mislabeled_sustained():
    v = [3, 80, 3, 80, 3, 80, 3] * 2
    g = single(analyze_lifecycle(history(v)))
    assert g["status"] == "abstained"
    assert g["lifecycle"] == "irregular_or_unclassified"
    assert g["comparison"]["recent_window_cv"] > .65


def test_realistic_repeatable_four_week_pattern_only_heuristic():
    repeated_week = [12, 13, 11, 14, 13, 12, 70]
    g = single(analyze_lifecycle(history(repeated_week * 4)))
    assert g["status"] == "observed"
    assert g["lifecycle"] == "seasonal_pattern"
    pattern = g["comparison"]["weekly_pattern"]
    assert pattern["detected"] is True
    assert pattern["complete_cycles"] == 4
    assert pattern["minimum_profile_correlation"] >= .85
    assert g["annual_seasonality_verified"] is False
    assert "not annual" in g["reason"] or "not annual" in (
        pattern["method"].replace("_", " ")
    )


def test_three_week_cycles_not_enough_to_verify_repeated_weekly_pattern():
    g = single(analyze_lifecycle(history([12, 11, 12, 10, 11, 9, 100] * 3)))
    assert g["lifecycle"] != "seasonal_pattern"
    assert g["comparison"]["weekly_pattern"]["detected"] is False


def test_weekly_pattern_excluded_when_week_totals_drift_strongly():
    values = (
        [10, 10, 10, 10, 10, 10, 70]
        + [20, 20, 20, 20, 20, 20, 140]
        + [40, 40, 40, 40, 40, 40, 280]
        + [100, 100, 100, 100, 100, 100, 700]
    )
    g = single(analyze_lifecycle(history(values)))
    assert g["comparison"]["weekly_pattern"]["detected"] is False
    assert g["lifecycle"] != "seasonal_pattern"


def test_weekly_source_label_periods_with_non_monday_anchor_are_valid():
    g = single(analyze_lifecycle(history([3] * 4 + [9] * 4, grain="weekly")))
    assert g["status"] == "observed"
    assert g["lifecycle"] == "rising_not_acceleration_verified"
    assert g["granularity"] == "weekly"
    assert g["min_points_per_window"] == 4
    assert g["required_observed_periods"] == 8


def test_weekly_full_7day_source_period_spans_are_valid():
    g = single(analyze_lifecycle(
        history([5] * 4 + [5] * 4, grain="weekly", shape="span")
    ))
    assert g["lifecycle"] == "sustained"
    assert g["periods_observed"] == 8


def test_shifted_weekly_source_label_alignment_fails_closed():
    rows = history([8] * 8, grain="weekly")
    row = rows[5].copy()
    original_date = date.fromisoformat(row["period"]["start_date"])
    shifted = original_date + timedelta(days=1)
    row["period"] = dict(row["period"])
    row["period"]["start_date"] = shifted.isoformat()
    row["period"]["end_date"] = shifted.isoformat()
    rows[5] = row
    g = single(analyze_lifecycle(rows))
    assert g["status"] == "unaligned_or_mixed_period_shapes"
    assert g["comparison"] is None


def test_mixed_weekly_span_and_source_label_is_not_aligned():
    rows = history([10] * 8, grain="weekly", shape="span")
    rows[5] = point(10, 5, grain="weekly", shape="label")
    g = single(analyze_lifecycle(rows))
    assert g["status"] == "unaligned_or_mixed_period_shapes"


def test_monthly_calendar_alignment_across_february():
    g = single(analyze_lifecycle(history(
        [10] * 3 + [7] * 3, grain="monthly", shape="span"
    )))
    assert g["status"] == "observed"
    assert g["lifecycle"] == "declining"
    assert g["required_observed_periods"] == 6
    assert g["compared_window_dates"]["previous_first"] == "2025-01-01"
    assert g["compared_window_dates"]["recent_last"] == "2025-06-01"


def test_monthly_source_labels_aligned():
    g = single(analyze_lifecycle(history(
        [5] * 3 + [5] * 3, grain="monthly", shape="label"
    )))
    assert g["lifecycle"] == "sustained"


def test_mixed_monthly_end_dates_rejected():
    rows = history([5] * 6, grain="monthly", shape="label")
    rows[3] = point(5, 3, grain="monthly", shape="span")
    g = single(analyze_lifecycle(rows))
    assert g["status"] == "unaligned_or_mixed_period_shapes"


def test_point_in_time_granularity_cannot_infer_lifecycle():
    rows = [point(10, idx, grain="point_in_time") for idx in range(14)]
    g = single(analyze_lifecycle(rows))
    assert g["status"] == "unsupported_granularity"
    assert g["comparison"] is None


@pytest.mark.parametrize("metric,value", [
    ("google_bigquery_rank", 12),
    ("google_trending_traffic_bucket", None),
    ("generated_keyword_candidate", None),
])
def test_rank_buckets_and_generated_keywords_do_not_make_trends(metric, value):
    rows = [
        point(value, idx, metric=metric)
        for idx in range(14)
    ]
    g = single(analyze_lifecycle(rows))
    assert g["status"] == "unsupported_metric"
    assert g["comparison"] is None
    assert g["lifecycle"] == "unknown"


def test_relative_index_within_one_source_normalization_batch_allowed():
    rows = history(
        [15] * 7 + [35] * 7,
        metric="google_trends_normalized_interest",
        scope="normalized single US three month batch",
        term="AI agents", country="US", language="en",
    )
    g = single(analyze_lifecycle(rows))
    assert g["status"] == "observed"
    assert g["lifecycle"] == "rising_not_acceleration_verified"
    assert g["metric_unit"] == "relative_index_0_100"
    assert g["search_volume_verified"] is False


def test_normalized_index_snapshots_differing_observed_at_abstain():
    rows = history(
        [15] * 7 + [35] * 7,
        metric="google_trends_normalized_interest",
    )
    later = (OBSERVED + timedelta(minutes=1)).isoformat()
    rows[9] = dict(rows[9])
    rows[9]["observed_at"] = later
    g = single(analyze_lifecycle(rows))
    assert g["status"] == "incomparable_normalized_batches"
    assert g["lifecycle"] == "unknown"
    assert g["comparison"] is None


def test_duplicate_same_period_and_same_value_deduplicated_deterministically():
    rows = history([10] * 7 + [20] * 7)
    later = dict(rows[4])
    later["observed_at"] = (OBSERVED + timedelta(minutes=1)).isoformat()
    extra = rows[4].copy()
    expected = single(analyze_lifecycle(rows))
    actual = single(analyze_lifecycle([later, *reversed(rows), extra]))
    assert actual["lifecycle"] == expected["lifecycle"]
    assert actual["periods_observed"] == 14
    assert actual["duplicate_observations_collapsed"] == 2
    assert actual["comparison"] == expected["comparison"]


def test_conflicting_repeated_period_values_do_not_cherrypick_newest():
    rows = history([10] * 14)
    conflict = dict(rows[-1])
    conflict["value"] = 10000
    g = single(analyze_lifecycle([*rows, conflict]))
    assert g["status"] == "conflicting_source_revisions"
    assert g["lifecycle"] == "unknown"
    assert g["comparison"] is None


def test_source_cannot_publish_measurements_from_future_period():
    rows = history([10] * 14)
    future = dict(rows[4])
    future["observed_at"] = datetime(
        2026, 1, 1, tzinfo=timezone.utc
    ).isoformat()
    rows[4] = future
    g = single(analyze_lifecycle(rows))
    assert g["status"] == "source_time_inconsistent"
    assert g["comparison"] is None


def test_unlike_sources_and_units_remain_separate():
    rows = history([10] * 7 + [50] * 7)
    pypi = history(
        [100] * 7 + [80] * 7,
        metric="pypi_package_downloads", term="pydantic",
    )
    result = analyze_lifecycle(rows + pypi)
    assert result["source_series"] == 2
    groups = {g["source_id"]: g for g in result["series"]}
    assert groups["npm_package_downloads"]["lifecycle"] == (
        "rising_not_acceleration_verified"
    )
    assert groups["pypi_package_downloads"]["lifecycle"] == (
        "irregular_or_unclassified"
    )
    assert all(g["cross_source_metrics_aggregated"] is False for g in groups.values())
    assert result["cross_source_metric_comparison_performed"] is False
    assert "sum" not in json.dumps(result).lower()


def test_different_language_country_and_sampling_scope_do_not_merge():
    a = history([10] * 14, country="SI", language="sl")
    b = history([20] * 14, country="US", language="en")
    c = history([25] * 14, country="SI", language="sl",
                scope="only source records with CI excluded")
    r = analyze_lifecycle(a + b + c)
    assert r["source_series"] == 3
    assert {(g["country"], g["language"]) for g in r["series"]} == {
        ("SI", "sl"), ("US", "en"),
    }
    assert all(g["cross_source_metrics_aggregated"] is False for g in r["series"])


def test_repeat_same_source_input_order_determinism():
    rows = history([10] * 7 + [20] * 7) + history(
        [25] * 14, metric="pypi_package_downloads", term="pydantic",
    )
    assert analyze_lifecycle(rows) == analyze_lifecycle(list(reversed(rows)))


def test_extreme_date_gap_is_bounded_and_no_fake_zeros():
    rows = history([5] * 14)
    row = dict(rows[-1])
    row["period"] = dict(row["period"])
    row["period"]["start_date"] = "9500-01-01"
    row["period"]["end_date"] = "9500-01-01"
    row["observed_at"] = "9500-01-02T00:00:00+00:00"
    rows[-1] = row
    g = single(analyze_lifecycle(rows))
    assert g["status"] == "coverage_incomplete"
    assert g["missing_period_count"] > 1_000_000
    assert len(g["missing_period_dates_first_24"]) == 24
    assert g["comparison"] is None


def test_count_beyond_exact_float_integer_range_is_refused():
    rows = history([1] * 14)
    rows[4] = dict(rows[4])
    rows[4]["value"] = float(2**53)
    g = single(analyze_lifecycle(rows))
    assert g["status"] == "unsafe_numeric_precision"
    assert g["comparison"] is None


@pytest.mark.parametrize("raw", [
    {},
    [],
    {"signals": []},
    {"observations": []},
    {"signals": [point(10)], "extra_secret": "PRIVATE"},
    [point(10)] * (MAX_SIGNALS + 1),
    [{"source_id": "SECRET_KEY"}],
    "some text",
    42,
])
def test_malformed_envelopes_and_bounds_do_not_echo_sensitive(raw):
    with pytest.raises(ValueError) as exc:
        analyze_lifecycle(raw)
    assert "PRIVATE" not in str(exc.value)
    assert "SECRET_KEY" not in str(exc.value)


def test_more_than_16_distinct_source_series_refused():
    rows = [
        point(10, 0, term=f"package-{idx}") for idx in range(17)
    ]
    with pytest.raises(ValueError, match="Too many source"):
        analyze_lifecycle(rows)


def test_no_network_or_sqlite_side_effect_from_analysis(monkeypatch):
    import requests
    import sqlite3

    monkeypatch.setattr(requests.Session, "get", lambda *_a, **_k: (
        (_ for _ in ()).throw(AssertionError("must not use network"))
    ))
    monkeypatch.setattr(sqlite3, "connect", lambda *_a, **_k: (
        (_ for _ in ()).throw(AssertionError("must not open quotas"))
    ))
    data = analyze_lifecycle(history([10] * 14))
    assert data["network_performed"] is False
    assert data["sqlite_or_quota_modified"] is False


def test_cli_offline_json_and_human_readable(tmp_path):
    path = tmp_path / "typed_history.json"
    path.write_text(
        json.dumps({"signals": history([10] * 7 + [20] * 7)}),
        encoding="utf-8",
    )
    runner = CliRunner()
    res = runner.invoke(cli, [
        "intelligence", "lifecycle", "--input", str(path), "--format", "json",
    ])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["source_series"] == 1
    assert payload["series"][0]["lifecycle"] == "rising_not_acceleration_verified"
    human = runner.invoke(cli, [
        "intelligence", "lifecycle", "--input", str(path), "--format", "text",
    ])
    assert human.exit_code == 0, human.output
    assert "OFFLINE M13 SOURCE-SCOPED" in human.output
    assert "no network" in human.output.lower() or "No network" in human.output


def test_cli_oversized_or_invalid_json_is_redacted(tmp_path):
    path = tmp_path / "input.json"
    path.write_text("X" * (MAX_INPUT_BYTES + 1), encoding="utf-8")
    bad = CliRunner().invoke(cli, [
        "intelligence", "lifecycle", "--input", str(path), "--format", "json",
    ])
    assert bad.exit_code != 0
    assert "oversized" in bad.output
    path.write_text('{"signals":[{"SECRET_PRIVATE":"value"}]}', encoding="utf-8")
    invalid = CliRunner().invoke(cli, [
        "intelligence", "lifecycle", "--input", str(path), "--format", "json",
    ])
    assert invalid.exit_code != 0
    assert "SECRET_PRIVATE" not in invalid.output


def test_report_is_source_provenance_only_without_full_raw_payload():
    rows = history([15] * 14)
    report = analyze_lifecycle(rows)
    g = single(report)
    assert g["source_url"] == SOURCE["npm_package_downloads"][1]
    assert g["metric_type"] == "npm_package_downloads"
    assert g["metric_unit"] == "downloads"
    assert g["source_record_ids_first_12"]
    assert len(g["source_record_ids_first_12"]) <= 12
    assert "raw" not in g
    assert "API_KEY" not in repr(report)


def test_earlier_verified_real_package_cache_fixture_abstains_without_growth():
    from pathlib import Path

    fixture = (
        Path(__file__).resolve().parent.parent
        / "docs" / "examples" / "mjau-m13-observed-package-downloads.json"
    )
    data = json.loads(fixture.read_text(encoding="utf-8"))
    assert len(data["signals"]) == 14
    result = analyze_lifecycle(data)
    assert result["network_performed"] is False
    assert result["provider_operations"] == 0
    assert result["sqlite_or_quota_modified"] is False
    assert result["source_series"] == 2
    group = {s["source_id"]: s for s in result["series"]}
    assert set(group) == {"npm_package_downloads", "pypi_package_downloads"}
    for value in group.values():
        assert value["status"] == "insufficient_history"
        assert value["periods_observed"] == 7
        assert value["required_observed_periods"] == 14
        assert value["comparison"] is None
        assert value["lifecycle"] == "unknown"
    source_counts = {}
    for item in data["signals"]:
        sid = item["source_id"]
        source_counts[sid] = source_counts.get(sid, 0) + item["value"]
    assert source_counts["npm_package_downloads"] == 475488459
    assert source_counts["pypi_package_downloads"] == 285184650
    assert result["cross_source_metric_comparison_performed"] is False


def test_weekly_pattern_helper_denies_less_than_four_cycles():
    assert _weekly_repetition([10] * 21)["detected"] is False
