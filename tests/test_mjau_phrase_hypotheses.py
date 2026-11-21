"""M12: offline multilingual, provenance-preserving phrase extraction."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest
from click.testing import CliRunner

from mcp_trendpulse.cli import cli
from mcp_trendpulse.intelligence_phrases import (
    MAX_INPUT_RECORDS, MAX_OUTPUT_TERMS, _intent, _title_phrases,
    extract_phrase_hypotheses,
)
from mcp_trendpulse.intelligence_signal import (
    SignalPeriod, SignalProvenance, TrendSignal,
)

OBSERVED = datetime(2026, 11, 21, 0, 0, tzinfo=timezone.utc)


def title(
    text="Python API timeout when running agents",
    *, lang="en", country=None,
    sid="hacker_news_algolia", url="https://news.ycombinator.com/item?id=123",
    rid="123",
):
    return {
        "kind": "public_title",
        "source_id": sid,
        "source_url": url,
        "source_record_id": rid,
        "observed_at": OBSERVED.isoformat(),
        "language": lang, "country": country, "title": text,
    }


def note(text="API reliability timeout problems", lang="en", country=None):
    return {"kind": "manual_note", "text": text, "language": lang, "country": country}


def signal(
    term="agent reliability tools", *, lang="en", country=None,
    is_query=True, method="community_provider",
    metric="google_trends_normalized_interest",
    status="observed", value=63.0,
):
    if status in ("no_data", "unavailable"):
        value = None
    unit = {
        "google_trends_normalized_interest": "relative_index_0_100",
        "google_bigquery_rank": "rank",
        "hacker_news_story_mentions": "stories",
        "generated_keyword_candidate": "none",
        "bing_keyword_impressions": "impressions",
    }[metric]
    if metric == "generated_keyword_candidate":
        is_query = False
        method = "derived"
        status = "not_measured"
        value = None
    obj = TrendSignal(
        source_id="google_trends_idea_related_queries",
        source_url="https://trends.google.com/trends/explore?geo=SI",
        observed_at=OBSERVED,
        country=country, language=lang,
        raw_term=term, normalized_term=term.casefold(),
        metric_type=metric, metric_unit=unit,
        period=SignalPeriod(
            start_date=date(2026, 11, 20),
            end_date=date(2026, 11, 20),
            granularity="daily",
        ),
        value=value,
        sampling_scope="Source API observation, manual fixture metadata",
        coverage_status=status,
        provenance=SignalProvenance(
            method=method, sampling_basis="official related source list",
            source_record_id="si-agent-tools",
            is_observed_search_query=is_query,
        ),
    ).model_dump(mode="json")
    return {"kind": "signal", "signal": obj}


def classes(out):
    return (
        out["observed_query_terms"],
        out["source_topics_not_queries"],
        out["generated_phrase_hypotheses"],
    )


def test_public_title_never_becomes_observed_keyword_and_no_metrics():
    report = extract_phrase_hypotheses({"evidence": [title()]})
    query, topics, generated = classes(report)
    assert not query and not topics
    assert generated
    assert report["network_performed"] is False
    assert report["paid_services_used"] is False
    assert report["models_or_corpora_downloaded"] is False
    assert report["source_metrics_aggregated"] is False
    assert report["observed_query_note"].startswith("Source-attested")
    assert any("api timeout" in c["normalized"] for c in generated)
    assert all(c["evidence_class"] == "generated_hypothesis" for c in generated)
    assert all(c["source_observations"][0]["is_source_attested_search_query"] is False
               for c in generated)
    assert all(c["source_observations"][0]["observation_kind"]
               == "user_supplied_public_title" for c in generated)
    assert all(c["search_volume_verified"] is False for c in generated)
    assert all(c["independent_customers_verified"] is False for c in generated)
    assert all(c["seo_competition_verified"] is False for c in generated)
    assert all(c["source_observations"][0]["source_url"]
               == "https://news.ycombinator.com/item?id=123" for c in generated)


def test_valid_typed_source_attested_query_retained_separately():
    report = extract_phrase_hypotheses([signal()])
    query, topics, generated = classes(report)
    assert len(query) == 1
    assert topics == [] and generated == []
    item = query[0]
    assert item["phrase"] == "agent reliability tools"
    assert item["normalized"] == "agent reliability tools"
    assert item["evidence_class"] == "observed_query"
    assert item["source_observations"][0]["coverage_status"] == "observed"
    assert item["source_observations"][0]["is_source_attested_search_query"]
    assert item["source_observations"][0]["metric_type"] == (
        "google_trends_normalized_interest"
    )
    assert "value" not in item["source_observations"][0]
    assert "value" not in item
    assert item["search_volume_verified"] is False


@pytest.mark.parametrize("method", ["operator_supplied", "derived"])
def test_forged_operator_query_flag_never_elevates_to_observed(method):
    report = extract_phrase_hypotheses([signal(method=method)])
    assert not report["observed_query_terms"]
    topics = report["source_topics_not_queries"]
    assert len(topics) == 1
    assert topics[0]["source_observations"][0]["is_source_attested_search_query"] is False


def test_community_mentions_are_not_search_query_even_with_attested_flag():
    report = extract_phrase_hypotheses([
        signal(metric="hacker_news_story_mentions", is_query=True, value=3),
    ])
    assert not report["observed_query_terms"]
    assert len(report["source_topics_not_queries"]) == 1


@pytest.mark.parametrize("status", ["unavailable", "no_data"])
def test_missing_source_signal_never_creates_candidate_or_measured_zero(status):
    report = extract_phrase_hypotheses([signal(status=status)])
    assert not any(classes(report))
    assert report["unavailable_or_no_data_signals_skipped"] == 1
    assert report["output_candidates"] == 0


def test_generated_source_signal_stays_hypothesis_unmeasured():
    report = extract_phrase_hypotheses([
        signal(term="serverless API reliability", metric="generated_keyword_candidate"),
    ])
    assert not report["observed_query_terms"]
    assert not report["source_topics_not_queries"]
    assert len(report["generated_phrase_hypotheses"]) == 1
    c = report["generated_phrase_hypotheses"][0]
    assert c["source_observations"][0]["metric_type"] == "generated_keyword_candidate"
    assert c["source_observations"][0]["coverage_status"] == "not_measured"


@pytest.mark.parametrize(("lang", "phrase", "cue"), [
    ("en", "Python API timeout errors", "timeout"),
    ("de", "Fehler bei Python Anmeldung", "fehler"),
    ("es", "Error de autenticación API", "error"),
    ("fr", "Erreur connexion Python", "erreur"),
    ("sl", "Kako odpraviti napako pri prijavi API", "napako"),
    ("hr", "Kako popraviti grešku pri prijavi API", "grešku"),
])
def test_six_multilingual_title_fixtures_preserve_language_and_problem_cues(
    lang, phrase, cue,
):
    result = extract_phrase_hypotheses([title(phrase, lang=lang)])
    generated = result["generated_phrase_hypotheses"]
    assert generated, (lang, result)
    assert not result["observed_query_terms"]
    assert all(c["language"] == lang for c in generated)
    assert all(c["source_observations"][0]["language"] == lang for c in generated)
    assert any(
        c["intent"]["label"] == "problem"
        and any(m["cue"] == cue for m in c["intent"]["matched_cues"])
        for c in generated
    ), (lang, generated)
    assert all(c["intent"]["method"].startswith("transparent_multilingual")
               for c in generated)
    assert all(c["ranking_explanation"][-1]
               == "no_source_metrics_or_keyword_volumes_aggregated"
               for c in generated)


@pytest.mark.parametrize(("lang", "text", "cue"), [
    ("en", "API service pricing", "pricing"),
    ("de", "Preis für API Agenten", "preis"),
    ("es", "Precio para API herramientas", "precio"),
    ("fr", "Prix des outils API", "prix"),
    ("sl", "Cena API storitve", "cena"),
    ("hr", "Cijena API usluge", "cijena"),
])
def test_six_languages_commercial_cues_are_explained(lang, text, cue):
    report = extract_phrase_hypotheses([title(text, lang=lang)])
    assert any(
        c["intent"]["label"] == "commercial"
        and any(t["cue"] == cue for t in c["intent"]["matched_cues"])
        for c in report["generated_phrase_hypotheses"]
    )


@pytest.mark.parametrize(("lang", "text", "cue"), [
    ("en", "tutorial API setup", "tutorial"),
    ("de", "Anleitung Python API", "anleitung"),
    ("es", "Tutorial para API", "tutorial"),
    ("fr", "Guide API Python", "guide"),
    ("sl", "Navodila za API", "navodila"),
    ("hr", "Upute za API", "upute"),
])
def test_informational_intent_heuristic_has_literal_trigger(lang, text, cue):
    r = extract_phrase_hypotheses([title(text, lang=lang)])
    assert any(
        c["intent"]["label"] == "informational"
        and any(x["cue"] == cue for x in c["intent"]["matched_cues"])
        for c in r["generated_phrase_hypotheses"]
    )


def test_mixed_and_unknown_intent_abstain_from_single_label():
    assert _intent("free API timeout", "en")["label"] == "mixed"
    assert _intent("distributed agent topology", "en")["label"] == "unknown"
    assert _intent("timeout", "ja")["label"] == "unknown"
    assert "abstaining" in _intent("timeout", "ja")["explanation"]


def test_unknown_language_title_skips_extraction_no_inferred_english():
    out = extract_phrase_hypotheses([title("agent timeout question", lang="ja")])
    assert out["unsupported_language_title_records_skipped"] == 1
    assert out["output_candidates"] == 0
    assert not any(classes(out))


def test_unknown_language_typed_source_query_kept_without_fake_intent():
    r = extract_phrase_hypotheses([signal("機械 学習", lang="ja")])
    assert len(r["observed_query_terms"]) == 1
    assert r["observed_query_terms"][0]["language"] == "ja"
    assert r["observed_query_terms"][0]["intent"]["label"] == "unknown"


def test_missing_language_public_title_abstains_without_en_heuristic():
    r = extract_phrase_hypotheses([title("Python timeout retry", lang=None)])
    assert r["unsupported_language_title_records_skipped"] == 1
    assert r["output_candidates"] == 0


def test_unaccented_and_accented_terms_are_not_silently_joined():
    result = extract_phrase_hypotheses([
        note("café reliability checks", lang="fr"),
        note("cafe reliability checks", lang="fr"),
    ])
    generated = result["generated_phrase_hypotheses"]
    a = {x["normalized"] for x in generated}
    assert "café reliability checks" in a
    assert "cafe reliability checks" in a
    matching = [
        f for f in result["lexical_keyword_families"]
        if "café reliability checks" in f["member_normalized"]
        or "cafe reliability checks" in f["member_normalized"]
    ]
    assert len(matching) == 2


def test_csharp_cpp_preserved_and_not_equated():
    result = extract_phrase_hypotheses([
        note("C++ reliability timeout", lang="en"),
        note("C# reliability timeout", lang="en"),
    ])
    generated = result["generated_phrase_hypotheses"]
    strings = {x["normalized"] for x in generated}
    assert "c++ reliability timeout" in strings
    assert "c# reliability timeout" in strings
    matching = [
        f for f in result["lexical_keyword_families"]
        if "c++ reliability timeout" in f["member_normalized"]
        or "c# reliability timeout" in f["member_normalized"]
    ]
    assert len(matching) == 2


def test_free_vs_paid_and_not_vs_with_never_fuzzy_merge():
    r = extract_phrase_hypotheses([
        note("free agent monitoring tools"), note("paid agent monitoring tools"),
        note("not working agent monitoring"), note("working agent monitoring"),
    ])
    for a, b in (
        ("free agent monitoring", "paid agent monitoring"),
        ("not working agent", "working agent"),
    ):
        families = [
            f for f in r["lexical_keyword_families"]
            if a in f["member_normalized"] or b in f["member_normalized"]
        ]
        assert len(families) >= 2


def test_same_phrase_two_sources_exact_dedup_provenance_and_relevance():
    a = title(
        "Python API timeout", sid="hacker_news_algolia",
        url="https://news.ycombinator.com/item?id=123", rid="123",
    )
    b = title(
        "Python API timeout", sid="stackexchange_question_mentions",
        url="https://stackoverflow.com/questions/123", rid="123",
    )
    one = extract_phrase_hypotheses([a])
    both = extract_phrase_hypotheses([b, a, a])
    p = "python api timeout"
    baseline = next(x for x in one["generated_phrase_hypotheses"] if x["normalized"] == p)
    merged = next(x for x in both["generated_phrase_hypotheses"] if x["normalized"] == p)
    assert len(merged["source_observations"]) == 2
    assert {x["source_id"] for x in merged["source_observations"]} == {
        "hacker_news_algolia", "stackexchange_question_mentions",
    }
    assert merged["lexical_relevance_score"] > baseline["lexical_relevance_score"]
    assert merged["independent_customers_verified"] is False
    assert merged["country"] is None


def test_country_and_language_scope_boundaries_not_merged():
    r = extract_phrase_hypotheses([
        title("Python API timeout", lang="en", country="US"),
        title("Python API timeout", lang="en", country="SI"),
        title("Python API timeout", lang="de", country="SI"),
    ])
    c = [x for x in r["generated_phrase_hypotheses"]
         if x["normalized"] == "python api timeout"]
    assert {(x["language"], x["country"]) for x in c} == {
        ("en", "US"), ("en", "SI"), ("de", "SI"),
    }
    assert len({id(x) for x in c}) == 3
    assert r["no_cross_language_or_country_merges"] is True


def test_reversing_input_order_has_same_deterministic_output():
    items = [
        title("Python API timeout", rid="123"),
        title("Python API timeout", rid="124",
              url="https://news.ycombinator.com/item?id=124"),
        note("Fix agent reliability timeout"),
        signal("agent reliability search", is_query=True),
    ]
    a = extract_phrase_hypotheses(items)
    b = extract_phrase_hypotheses(list(reversed(items)))
    assert a == b


def test_conservative_m02_near_duplicate_family_keeps_distinct_candidates():
    result = extract_phrase_hypotheses([
        note("agent reliability tools for developers"),
        note("agent reliabilty tools for developers"),
    ])
    terms = {c["normalized"] for c in result["generated_phrase_hypotheses"]}
    assert "agent reliability tools" in terms
    assert "agent reliabilty tools" in terms
    family = [
        f for f in result["lexical_keyword_families"]
        if {
            "agent reliability tools", "agent reliabilty tools"
        } <= set(f["member_normalized"])
    ]
    assert len(family) == 1
    assert family[0]["semantic_equivalence_verified"] is False
    assert family[0]["lexical_grouping"] == "conservative_rapidfuzz_complete_link"


def test_source_metric_values_never_change_ranking_or_appear_in_output():
    a = signal("agent timeout tools", is_query=True, value=90)
    b = signal("agent timeout tools", is_query=True, value=5)
    first = extract_phrase_hypotheses([a])
    second = extract_phrase_hypotheses([b])
    assert first == second
    assert "value" not in str(first)
    assert first["source_metrics_aggregated"] is False


@pytest.mark.parametrize("attack", [
    title("contact SECRET_NAME@example.org for reliability details"),
    title("API key sk-projabcdef12345678901234567890 leaked"),
    title("API key ghp_abcdefgh12345678901234567890 leaked"),
    title("API reliability\nSECRET_TOKEN"),
    {**title(), "private_access_token": "VERY_SECRET"},
    {**title(), "source_url": "http://localhost/private"},
    {**title(), "source_url": "https://example.com/path?api_key=TOP_SECRET"},
    {**title(), "source_record_id": "../SECRET"},
    {**title(), "country": "Sl"},
    {**title(), "language": "EN"},
    {**title(), "observed_at": "2026-11-20T00:00:00"},
])
def test_invalid_or_sensitive_public_evidence_rejected_without_echo(attack):
    with pytest.raises(ValueError) as info:
        extract_phrase_hypotheses([attack])
    assert "SECRET" not in str(info.value)
    assert "TOP_SECRET" not in str(info.value)
    assert "PRIVATE" not in str(info.value)


def test_invalid_typed_signal_rejected_and_error_redacted():
    malformed = signal()
    malformed["signal"]["access_token"] = "PRIVATE_SECRET"
    with pytest.raises(ValueError) as info:
        extract_phrase_hypotheses([malformed])
    assert "PRIVATE_SECRET" not in str(info.value)


@pytest.mark.parametrize("raw", [
    {},
    {"anything": []},
    {"evidence": []},
    {"evidence": [title()], "raw_secret": "PRIVATE"},
    "",
    123,
    [title()] * (MAX_INPUT_RECORDS+1),
    [{"kind": "unsupported", "text": "hello"}],
])
def test_invalid_envelopes_and_bounds_fail_closed(raw):
    with pytest.raises(ValueError):
        extract_phrase_hypotheses(raw)


def test_max_input_output_and_family_caps_are_bounded():
    rows = [
        note(
            f"agent reliability topic {i:03d} with timeout and documentation"
        )
        for i in range(MAX_INPUT_RECORDS)
    ]
    out = extract_phrase_hypotheses(rows)
    assert out["input_records"] == MAX_INPUT_RECORDS
    assert out["output_candidates"] <= MAX_OUTPUT_TERMS
    assert out["output_truncated"] is True
    assert len(out["lexical_keyword_families"]) <= MAX_OUTPUT_TERMS
    assert out["network_performed"] is False


def test_observed_source_query_survives_hypothesis_output_truncation():
    rows = [
        note(f"agent reliability topic {i:03d} with timeout and documentation")
        for i in range(MAX_INPUT_RECORDS-1)
    ]
    rows.append(signal("observed source query keeps priority"))
    report = extract_phrase_hypotheses(rows)
    assert report["output_truncated"] is True
    assert report["candidates_dropped_by_output_cap"] > 0
    assert len(report["observed_query_terms"]) == 1
    assert report["observed_query_terms"][0]["phrase"] == (
        "observed source query keeps priority"
    )


def test_offline_cli_json_and_text_modes(tmp_path):
    path = tmp_path/"evidence.json"
    path.write_text(
        json.dumps({"evidence": [
            title("Python API timeout"),
            signal("agent reliability tools"),
        ]}, ensure_ascii=False), encoding="utf-8",
    )
    runner = CliRunner()
    raw = runner.invoke(cli, [
        "intelligence", "phrase-hypotheses",
        "--input", str(path), "--format", "json",
    ])
    assert raw.exit_code == 0, raw.output
    out = json.loads(raw.output)
    assert out["mode"] == "offline_multilingual_source_preserving_phrase_hypotheses"
    assert len(out["observed_query_terms"]) == 1
    assert out["generated_phrase_hypotheses"]
    text = runner.invoke(cli, [
        "intelligence", "phrase-hypotheses",
        "--input", str(path), "--format", "text",
    ])
    assert text.exit_code == 0
    assert "OFFLINE MULTILINGUAL" in text.output
    assert "Generated phrase hypotheses" in text.output


def test_offline_cli_oversized_and_sensitive_invalid_input_redacted(tmp_path):
    path = tmp_path/"evidence.json"
    path.write_text("X"*(128*1024+1), encoding="utf-8")
    bad = CliRunner().invoke(cli, [
        "intelligence", "phrase-hypotheses",
        "--input", str(path), "--format", "json",
    ])
    assert bad.exit_code != 0
    assert "oversized" in bad.output
    path.write_text('{"evidence":[{"kind":"unknown","secret":"PRIVATE_SECRET"}]}',
                    encoding="utf-8")
    invalid = CliRunner().invoke(cli, [
        "intelligence", "phrase-hypotheses",
        "--input", str(path), "--format", "json",
    ])
    assert invalid.exit_code != 0
    assert "PRIVATE_SECRET" not in invalid.output
    assert "Invalid, unsafe" in invalid.output


def test_title_phrase_generation_is_repeatable_and_bounded():
    first = _title_phrases(
        "Python API timeout during browser automation and deployment", "en",
    )
    second = _title_phrases(
        "Python API timeout during browser automation and deployment", "en",
    )
    assert first == second
    assert 0 < len(first) <= 16
    assert all(len(term) <= 90 for term in first)
