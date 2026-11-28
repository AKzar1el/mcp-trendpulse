"""Synthetic coverage, concentration, and provenance regressions."""
import pytest

from mcp_trendpulse.news_intelligence_collect import collect_news
from mcp_trendpulse.news_intelligence_coverage import summarize_gdelt_coverage, summarize_news_snapshot
from mcp_trendpulse.news_intelligence_schema import (
    GDELT_ATTRIBUTION, NewsArticle, NewsBatch, TimeEvidence,
)

CUT = "2026-11-28T12:00:00+00:00"
HEAD = "Researchers announce a new renewable energy project for regional communities"


def row(key, label="Publisher A", *, title=HEAD, host="example.org"):
    return NewsArticle(
        discovery_provider="gdelt_doc", link_type="publisher_candidate",
        reported_url=f"https://{host}/story/{key}", title=title,
        publisher_label=label, capture_mode="legacy_import", captured_at=CUT,
        provider_seen_at=TimeEvidence(value="2026-11-28T11:00:00Z", precision="second", basis="provider_seen"),
    )


def batch(*rows, status=None, capped=False):
    return NewsBatch(
        provider="gdelt_doc", attribution=GDELT_ATTRIBUTION, captured_at=CUT,
        status=status or ("observed" if rows else "empty"), source_count=len(rows),
        invalid_count=0, duplicate_count=0, truncated_count=0, possibly_capped=capped,
        articles=tuple(rows),
    )


def missing():
    return NewsBatch(provider="gdelt_doc", attribution=GDELT_ATTRIBUTION,
                     captured_at=None, status="unavailable", reason="provider_unavailable")


def test_snapshot_preserves_revisions_and_does_not_sum_overlapping_batches():
    a = row("a")
    revised = row("a", title="Researchers announce an updated project for regional communities")
    b = row("b", "Publisher B", host="other.org")
    result = summarize_news_snapshot([batch(a, b), batch(a, revised)], as_of=CUT)
    assert result["supplied_accepted_observations"] == 4
    assert result["distinct_observations"] == 3 and result["exact_replays_removed"] == 1
    assert result["provider_scoped_article_keys"] == 2
    assert result["distinct_reported_url_strings"] == 2
    assert result["event_candidate_count"] == 2
    assert result["verified_event_count"] is None
    assert result["independent_reporting_source_count"] is None
    assert result["normalized_coverage_pct"] is None
    assert result["monitored_universe_count"] is None
    assert result["publisher_label_concentration"]["hhi_known_labels_0_to_10000"] == 5000
    assert result["reported_publisher_host_concentration"]["distinct_known_labels"] == 2


def test_concentration_only_known_nonconflicting_labels():
    a, b, c, d = row("a"), row("b"), row("c", "Publisher B"), row("d", None)
    conflict = row("e")
    conflict_revision = row("e", "Publisher C")
    result = summarize_news_snapshot([batch(a, b, c, d, conflict, conflict_revision)], as_of=CUT)
    dist = result["publisher_label_concentration"]
    assert dist["article_key_count"] == 5
    assert (dist["known_label_article_count"], dist["unknown_label_article_count"],
            dist["conflicting_label_article_count"]) == (3, 1, 1)
    assert dist["known_label_coverage_pct"] == 60
    assert dist["largest_known_label_share_pct"] == pytest.approx(200/3)
    assert dist["hhi_known_labels_0_to_10000"] == pytest.approx(10000*5/9)
    assert dist["top_three_known_label_share_pct"] == 100


def test_same_reported_url_across_providers_is_not_unique_article_identity():
    a = row("a", host="www.nasa.gov", label="NASA")
    nasa = NewsArticle(discovery_provider="nasa_rss", link_type="publisher_candidate",
                       reported_url=a.reported_url, title=HEAD, publisher_label="NASA",
                       capture_mode="legacy_import", captured_at=CUT)
    n = NewsBatch(provider="nasa_rss", attribution="NASA (https://www.nasa.gov/)",
                  status="observed", captured_at=CUT, source_count=1, invalid_count=0,
                  duplicate_count=0, truncated_count=0, articles=(nasa,))
    out = summarize_news_snapshot([batch(a), n], as_of=CUT)
    assert out["distinct_reported_url_strings"] == 1
    assert out["provider_scoped_article_keys"] == 2
    assert out["distinct_discovery_providers"] == 2


def test_google_rss_host_is_not_a_publisher():
    a = NewsArticle(discovery_provider="google_news_rss", link_type="google_news_rss",
                    reported_url="https://news.google.com/rss/articles/abc", title=HEAD,
                    capture_mode="legacy_import", captured_at=CUT)
    b = NewsBatch(provider="google_news_rss", attribution="Google News RSS (https://news.google.com/)",
                  captured_at=CUT, status="observed", source_count=1, invalid_count=0,
                  duplicate_count=0, truncated_count=0, articles=(a,))
    result = summarize_news_snapshot([b], as_of=CUT)
    for key in ("publisher_label_concentration", "reported_publisher_host_concentration"):
        assert result[key]["known_label_article_count"] == 0
        assert result[key]["hhi_known_labels_0_to_10000"] is None
    assert result["unknown_time_counts"]["publication_unknown"] == 1


def test_unavailable_empty_partial_and_capped_are_distinct():
    for batches in ([], [missing()]):
        out = summarize_news_snapshot(batches, as_of=CUT)
        assert out["status"] == "unavailable" and out["distinct_observations"] is None
    out = summarize_news_snapshot([batch()], as_of=CUT)
    assert out["status"] == "empty" and out["distinct_observations"] == 0
    assert out["publisher_label_concentration"]["hhi_known_labels_0_to_10000"] is None
    out = summarize_news_snapshot([batch(), missing()], as_of=CUT)
    assert out["status"] == "partial" and out["distinct_observations"] == 0
    out = summarize_news_snapshot([batch(row("a"), capped=True)], as_of=CUT)
    assert out["status"] == "partial"


def test_snapshot_order_and_bounds():
    a, b = batch(row("a")), batch(row("b"))
    assert summarize_news_snapshot([a, b], as_of=CUT) == summarize_news_snapshot([b, a], as_of=CUT)
    with pytest.raises(ValueError, match="batch sequence"):
        summarize_news_snapshot([a] * 17, as_of=CUT)
    with pytest.raises(ValueError, match="after cutoff"):
        summarize_news_snapshot([a], as_of="2026-11-27T12:00:00Z")
    with pytest.raises(ValueError, match="Invalid news batch"):
        summarize_news_snapshot([a.model_copy(update={"source_count": 100})], as_of=CUT)


def timeline(*points, status="observed"):
    r = collect_news("gdelt_timeline", phrase="renewable energy", as_of=CUT, days=1)
    r.update(status=status, captured_at=CUT if status in ("observed", "empty") else None,
             evidence={
                 "schema_version": 1, "provider": "gdelt_doc", "attribution": GDELT_ATTRIBUTION,
                 "metric": "matched_and_monitored_articles", "status": status,
                 "points": [{"interval_at": at, "matched": m, "monitored": n} for at, m, n in points],
             } if status in ("observed", "empty") else None)
    return r


def test_weighted_share_not_mean_of_percentages():
    report = timeline(("2026-11-27T12:00:00Z", 1, 2), ("2026-11-27T13:00:00Z", 9, 90))
    result = summarize_gdelt_coverage(report, expected_interval_seconds=3600)
    assert [p["coverage_pct"] for p in result["points"]] == [50, 10]
    assert result["weighted_coverage_pct"] == pytest.approx(100*10/92)
    assert result["matched_articles_in_returned_intervals"] == 10
    assert result["monitored_articles_in_returned_intervals"] == 92
    grid = result["declared_grid_diagnostics"]
    assert (grid["expected_bins_on_declared_grid"], grid["observed_aligned_bins"],
            grid["missing_bins_on_declared_grid"]) == (24, 2, 22)
    assert not result["full_window_coverage_verified"]


def test_zero_denominators_and_missing_not_zero():
    r = summarize_gdelt_coverage(timeline(("2026-11-28T10:00:00Z", 0, 0)))
    assert r["weighted_coverage_pct"] is None and r["zero_denominator_intervals"] == 1
    assert r["points"][0]["coverage_pct"] is None
    r = summarize_gdelt_coverage(timeline(("2026-11-28T10:00:00Z", 0, 50)))
    assert r["weighted_coverage_pct"] == 0
    for state in ("planned", "unavailable", "invalid", "empty"):
        r = summarize_gdelt_coverage(timeline(status=state), expected_interval_seconds=3600)
        assert r["matched_articles_in_returned_intervals"] is None
        assert r["weighted_coverage_pct"] is None
        assert r["declared_grid_diagnostics"]["missing_bins_on_declared_grid"] is None
        assert r["returned_interval_count"] == (0 if state == "empty" else None)


def test_end_boundary_and_off_grid_are_explicit():
    r = summarize_gdelt_coverage(timeline(
        ("2026-11-27T12:00:00Z", 1, 10),
        ("2026-11-27T12:15:00Z", 1, 10),
        ("2026-11-28T12:00:00Z", 1, 10)), expected_interval_seconds=3600)
    assert r["declared_grid_diagnostics"]["off_grid_or_end_boundary_points"] == 2
    assert r["declared_grid_diagnostics"]["observed_aligned_bins"] == 1


@pytest.mark.parametrize("mutation", ["smoothed", "scope", "wrong_source", "status", "bad_count",
                                     "out_of_window", "capture", "unknown_measurement", "duplicated"])
def test_invalid_receipts_fail_closed(mutation):
    r = timeline(("2026-11-28T10:00:00Z", 1, 20))
    if mutation == "smoothed":
        r["url"] = r["url"].replace("timelinesmooth=1", "timelinesmooth=5")
    elif mutation == "scope":
        r["scope"]["country_filter"] = "SI"
    elif mutation == "wrong_source":
        r["provider"] = "nasa_rss"
    elif mutation == "status":
        r["evidence"]["status"] = "empty"
    elif mutation == "bad_count":
        r["evidence"]["points"][0]["matched"] = 21
    elif mutation == "out_of_window":
        r["evidence"]["points"][0]["interval_at"] = "2026-11-26T10:00:00Z"
    elif mutation == "capture":
        r["captured_at"] = "2026-11-27T10:00:00Z"
    elif mutation == "unknown_measurement":
        r["status"] = "unavailable"
    else:
        r["evidence"]["points"].append(r["evidence"]["points"][0].copy())
    with pytest.raises(ValueError):
        summarize_gdelt_coverage(r)


@pytest.mark.parametrize("cadence", [True, 0, 100, 1.5])
def test_invalid_cadence_rejected(cadence):
    with pytest.raises(ValueError, match="cadence"):
        summarize_gdelt_coverage(timeline(status="empty"), expected_interval_seconds=cadence)
