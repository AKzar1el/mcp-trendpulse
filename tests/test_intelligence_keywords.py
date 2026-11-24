"""M02: conservative, source- and market-preserving RapidFuzz grouping."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest
from click.testing import CliRunner
from mcp_trendpulse.cli import cli
from mcp_trendpulse.intelligence_keywords import (
    MAX_KEYWORD_SIGNALS, benchmark_clustering, cluster_keyword_signals,
    normalize_keyword,
)
from mcp_trendpulse.intelligence_signal import (
    SignalPeriod, SignalProvenance, TrendSignal,
)

DAY = datetime(2026, 11, 20, 13, 0, tzinfo=timezone.utc)


def signal(term, *, country="GB", language=None, source="google_trending_now_rss",
           bucket="100+", metric="google_trending_traffic_bucket"):
    return TrendSignal(
        source_id=source, source_url="https://trends.google.com/trending/rss?geo=GB",
        observed_at=DAY, country=country, language=language,
        raw_term=term, normalized_term=term.casefold(),
        metric_type=metric,
        metric_unit="approximate_search_bucket"
        if metric == "google_trending_traffic_bucket" else "relative_index_0_100",
        value=None if metric == "google_trending_traffic_bucket" else 50,
        value_label=bucket if metric == "google_trending_traffic_bucket" else None,
        period=SignalPeriod(start_date=date(2026, 11, 20),
                            end_date=date(2026, 11, 20),
                            granularity="point_in_time"),
        sampling_scope="Google public RSS sample", coverage_status="observed",
        provenance=SignalProvenance(method="public_rss",
            sampling_basis="google_trending_now_grouped_search_label"),
    )


def test_unicode_nfc_casefold_whitespace_separators_and_meaningful_symbols():
    assert normalize_keyword("  AI—Agent    RELIABILITY! ") == "ai agent reliability"
    assert normalize_keyword("C++") == "c++"
    assert normalize_keyword("C#") == "c#"
    assert normalize_keyword("Živjo") == "živjo"
    assert normalize_keyword("Živjo") == "živjo"
    assert normalize_keyword("Österreich") == "österreich"
    assert normalize_keyword("Slovénija") != normalize_keyword("Slovenija")


def test_zero_width_space_does_not_fuse_distinct_keyword_tokens():
    assert normalize_keyword("AI\u200btools") == "ai tools"
    assert normalize_keyword("AI\u200btools") != normalize_keyword("AItools")


@pytest.mark.parametrize("separator", ["\v", "\f", "\u0085"])
def test_unicode_whitespace_does_not_fuse_distinct_keyword_tokens(separator):
    assert normalize_keyword(f"AI{separator}tools") == "ai tools"
    assert normalize_keyword(f"AI{separator}tools") != normalize_keyword("AItools")


@pytest.mark.parametrize("broken", ["", "   ", "...", "\u200d"])
def test_bad_keywords_cannot_silently_enter_an_unnamed_cluster(broken):
    with pytest.raises(ValueError):
        normalize_keyword(broken)


def test_same_market_exact_dedup_preserves_every_source_and_raw_term():
    records = [signal("AI—Agent reliability"),
               signal("ai agent reliability"),
               signal("AI agent reliability!"),
               signal("different topic")]
    report = cluster_keyword_signals(records)
    assert report["cluster_count"] == 2
    assert report["exact_duplicate_records"] == 2
    group = next(c for c in report["clusters"]
                 if c["representative_normalized"] == "ai agent reliability")
    assert len(group["members"]) == 3
    assert len({m["input_index"] for m in group["members"]}) == 3
    assert report["metrics_aggregated"] is False
    assert all(x["value"] is None for x in group["members"])


def test_typo_near_duplicate_groups_but_intent_changing_terms_do_not():
    report = cluster_keyword_signals([
        signal("agent reliability checker"),
        signal("agent reliabilty checker"),
        signal("agent unreliability checker"),
        signal("agent reliability not checker"),
        signal("agent reliability without checker"),
        signal("agent reliability free checker"),
    ])
    groups = [set(m["raw_term"] for m in group["members"])
              for group in report["clusters"]]
    assert {"agent reliability checker", "agent reliabilty checker"} in groups
    assert {"agent unreliability checker"} in groups
    assert {"agent reliability not checker"} in groups
    assert {"agent reliability without checker"} in groups
    assert {"agent reliability free checker"} in groups


def test_market_language_and_unknown_scope_never_cross_merge():
    signals = [
        signal("agent reliability checker", country="GB", language="en"),
        signal("agent reliability checker", country="US", language="en"),
        signal("agent reliability checker", country="GB", language=None),
        signal("agent reliability checker", country=None, language="en"),
        signal("agent reliability checker", country="GB", language="sl"),
    ]
    report = cluster_keyword_signals(signals)
    assert report["cluster_count"] == 5
    assert {x["country"] for x in report["clusters"]} == {"US", "GB", None}


def test_brand_suffixes_and_negated_terms_must_never_fuzzy_merge():
    candidates = [
        ("OpenAI Codex", "OpenAI Code"),
        ("Google Ads", "Google Ad"),
        ("agent reliability checker", "agent unreliability checker"),
    ]
    for left, right in candidates:
        result = cluster_keyword_signals([signal(left), signal(right)])
        assert result["cluster_count"] == 2, (left, right)


def test_diacritic_only_variants_and_distinct_programming_languages_preserved():
    result = cluster_keyword_signals([
        signal("slovenski šolski sistem", language="sl"),
        signal("slovenski solski sistem", language="sl"),
        signal("how to code in C++", language="en"),
        signal("how to code in C#", language="en"),
        signal("how to code in C", language="en"),
        signal("cheap shoes online", language="en"),
        signal("sheep shoes online", language="en"),
    ])
    assert result["cluster_count"] == 7


def test_no_transitive_chaining_into_dissimilar_cluster():
    # A highly similar intermediate label must not attach an unrelated third.
    report = cluster_keyword_signals([
        signal("agent reliability validator"),
        signal("agent reliabilty validator"),
        signal("agent reliabilty validations"),
    ])
    for group in report["clusters"]:
        keys = [m["normalized_term"] for m in group["members"]]
        if len(keys) == 3:
            assert False, "Single-link fuzzy chaining must not absorb third label"


def test_idempotent_output_except_input_indices_and_zero_network():
    a = signal("Agent reliability checker")
    b = signal("agent reliabilty checker")
    c = signal("Different topic")
    first = cluster_keyword_signals([a, b, c])
    second = cluster_keyword_signals([c, a, b])
    assert first["network_performed"] is second["network_performed"] is False
    assert first["cluster_count"] == second["cluster_count"]
    assert [x["representative_normalized"] for x in first["clusters"]] == [
        x["representative_normalized"] for x in second["clusters"]]


def test_source_measurements_not_combined_or_modified():
    result = cluster_keyword_signals([
        signal("agent reliability checker", bucket="1K+"),
        signal("agent reliabilty checker", bucket="500+"),
    ])
    members = result["clusters"][0]["members"]
    assert {x["value_label"] for x in members} == {"1K+", "500+"}
    assert result["metrics_aggregated"] is False
    assert not any(x in result for x in ("total_volume", "average_searches", "score"))


@pytest.mark.parametrize("bad_threshold", [89, 101, True, "95", float("nan")])
def test_invalid_threshold_rejected(bad_threshold):
    with pytest.raises(ValueError):
        cluster_keyword_signals([], similarity_threshold=bad_threshold)


def test_input_bound_rejects_unlimited_quadratic_work():
    with pytest.raises(ValueError):
        cluster_keyword_signals([signal("test topic")] * (MAX_KEYWORD_SIGNALS + 1))
    stats = benchmark_clustering(count=200)
    assert stats["records"] == 200
    assert stats["elapsed_seconds"] >= 0


def test_offline_cli_can_cluster_existing_m01_json_without_refetch(tmp_path, monkeypatch):
    from mcp_trendpulse import intelligence_rss, providers
    monkeypatch.setattr(providers, "get_provider_set",
                        lambda: (_ for _ in ()).throw(AssertionError("network")))
    feed = intelligence_rss._normalize_feed([
        {"keyword": "agent reliability checker", "volume": "1K+"},
        {"keyword": "agent reliabilty checker", "volume": "500+"},
    ], "GB", DAY)
    incoming = tmp_path / "rss.json"
    incoming.write_text(json.dumps(feed), encoding="utf-8")
    res = CliRunner().invoke(cli, [
        "intelligence", "cluster-keywords", "--input", str(incoming), "--format", "json",
    ])
    assert res.exit_code == 0, res.output
    response = json.loads(res.output)
    assert response["cluster_count"] == 1
    assert response["input_records"] == 2
    assert response["network_performed"] is False


def test_cli_rejects_unknown_json_shape_and_oversized_document(tmp_path):
    path = tmp_path / "signals.json"
    path.write_text('{"foo":"bar"}', encoding="utf-8")
    err = CliRunner().invoke(cli, ["intelligence", "cluster-keywords",
                                   "--input", str(path)])
    assert err.exit_code != 0
    assert "expected a list" in err.output.lower()
    path.write_text(" " * (128 * 1024 + 1), encoding="utf-8")
    oversized = CliRunner().invoke(cli, [
        "intelligence", "cluster-keywords", "--input", str(path),
    ])
    assert oversized.exit_code != 0


def test_does_not_silently_strip_source_provenance():
    source = signal("agent reliability checker")
    report = cluster_keyword_signals([source])
    item = report["clusters"][0]["members"][0]
    assert item["source_id"] == source.source_id
    assert item["source_url"] == source.source_url
    assert item["coverage_status"] == "observed"
