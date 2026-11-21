"""A04+A10 narrowly useful, source-backed workflows on the merged v1 baseline.

This is a real-source replay, not an agent productivity study, live provider
fetch, exploitation assessment, market forecast or a merged MCP registration.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcp_trendpulse.intelligence_core import IntelligenceError, plan_source
from mcp_trendpulse.mjau_v3.osv import parse_package_query, plan_package_query
from mcp_trendpulse.mjau_v3.wikidata import (
    candidates_for_name,
    parse_qid_lookup,
    plan_qid_lookup,
)
import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "mjau_v3"
LANGS = ["en", "de", "fr", "es", "sl", "it"]


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_separate_apple_entities_from_original_wikidata_response():
    source = _fixture("wikidata_q89_q312_20261121.json")
    parsed = parse_qid_lookup(source, ["Q89", "Q312"], LANGS)
    fruit = candidates_for_name(parsed, "apple", "en")
    company = candidates_for_name(parsed, "Apple Inc.", "en")
    assert fruit["candidate_qids"] == ["Q89"]
    assert company["candidate_qids"] == ["Q312"]
    assert fruit["identity_confirmed"] is company["identity_confirmed"] is False


def test_real_six_language_mercury_ambiguity_never_auto_merges():
    source = _fixture("wikidata_mercury_planet_god_six_languages_20261121.json")
    parsed = parse_qid_lookup(source, ["Q308", "Q1150"], LANGS)
    expected = {"en": "Mercury", "de": "Merkur", "fr": "Mercure",
                "es": "Mercurio", "sl": "Merkur", "it": "Mercurio"}
    for lang, text in expected.items():
        found = candidates_for_name(parsed, text, lang)
        assert found["status"] == "ambiguous", lang
        assert found["candidate_qids"] == ["Q1150", "Q308"], lang
        assert found["identity_confirmed"] is False


def test_real_q30_overflow_is_bounded_and_safe_on_unknown():
    source = _fixture("wikidata_q30_aliases_20261121.json")
    parsed = parse_qid_lookup(source, ["Q30"], LANGS)
    record = parsed["results"][0]["names"]["en"]
    assert record["source_alias_count"] == 20
    assert record["aliases_truncated"] is True
    assert len(record["aliases"]) <= 8
    negative = candidates_for_name(parsed, "not in the bounded alias set", "en")
    assert negative["status"] == "unknown_incomplete_aliases"
    assert negative["identity_confirmed"] is False


def test_osv_source_backed_positive_and_negative_are_not_safety_verdicts():
    stored = _fixture("osv_jinja2_and_osv_2020_744_20261121.json")
    positive = parse_package_query(
        stored["minimal_package_envelope"], ecosystem="PyPI",
        package="Jinja2", version="2.10.1",
    )
    assert positive["advisory_count_in_this_response"] == 10
    assert positive["status"] == "source_advisories_returned"
    assert all(r["source_specific_license_review_required"] for r in positive["records"])
    assert all(not r["raw_advisory_redistribution_authorized"] for r in positive["records"])
    negative = parse_package_query(
        _fixture("osv_six_1_16_0_empty_20261121.json"),
        ecosystem="PyPI", package="six", version="1.16.0",
    )
    assert negative["status"] == "no_returned_advisories"
    assert negative["advisory_count_in_this_response"] == 0
    assert negative["no_advisory_not_equivalent_to_safe_package"] is True


def test_both_plans_are_opt_in_and_not_in_v1_source_catalog():
    wikidata = plan_qid_lookup(["Q308", "Q1150"], LANGS)
    osv = plan_package_query("PyPI", "Jinja2", "2.10.1")
    assert wikidata["execution"] == osv["execution"] == "PLAN_ONLY"
    assert wikidata["zero_network_calls"] and osv["zero_network_calls"]
    assert wikidata["requires_existing_trendpulse_budget_and_cache"]
    assert osv["requires_existing_trendpulse_budget_and_cache"]
    for name in ("wikidata_action_api", "osv_public_api"):
        with pytest.raises(IntelligenceError, match="Unknown source ID"):
            plan_source(name)
