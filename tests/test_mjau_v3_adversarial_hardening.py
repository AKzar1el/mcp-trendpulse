"""Falsification of the two retained MJAU v3 adapters on untrusted data.

These are regression/property checks against the actual parsing contracts,
not fabricated real-world usefulness metrics or tests of live providers.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from mcp_trendpulse.mjau_v3.osv import (
    _safe_ref,
    parse_compact_package_query,
    parse_package_query,
    plan_compact_package_query,
    plan_package_query,
)
from mcp_trendpulse.mjau_v3.wikidata import (
    candidates_for_name,
    parse_qid_lookup,
)

BASE = Path(__file__).parent / "fixtures" / "mjau_v3"


def _apple_entity():
    return {
        "id": "Q89", "type": "item",
        "labels": {"en": {"language": "en", "value": "apple"}},
        "aliases": {}, "descriptions": {},
    }


@pytest.mark.parametrize("source", [
    {"success": 1, "entities": {"Q89": _apple_entity()}},
    {"success": 1, "entities": {
        "Q89": _apple_entity(), "Q312": {"id": "Q312", "missing": ""},
    }},
])
def test_unobserved_qid_name_is_unknown_not_a_negative(source):
    parsed = parse_qid_lookup(source, ["Q89", "Q312"], ["en"])
    result = candidates_for_name(parsed, "Some unobserved company", "en")
    assert result["status"] == "unknown_incomplete_source"
    assert result["candidate_qids"] == []
    assert result["source_items_incomplete"] is True
    assert result["searched_name_coverage_complete"] is False
    assert result["identity_confirmed"] is False


def test_missing_language_name_must_not_be_a_false_negative():
    source = {"success": 1, "entities": {
        "Q89": {"id": "Q89", "type": "item",
                "labels": {}, "aliases": {}, "descriptions": {}},
    }}
    parsed = parse_qid_lookup(source, ["Q89"], ["en"])
    result = candidates_for_name(parsed, "apple", "en")
    assert result["status"] == "unknown_incomplete_source"
    assert result["source_items_incomplete"] is True
    assert result["searched_name_coverage_complete"] is False
    assert result["identity_confirmed"] is False


def test_observed_positive_stays_unconfirmed_if_other_source_qid_missing():
    source = {"success": 1, "entities": {"Q89": _apple_entity()}}
    parsed = parse_qid_lookup(source, ["Q89", "Q312"], ["en"])
    result = candidates_for_name(parsed, "apple", "en")
    assert result["candidate_qids"] == ["Q89"]
    assert result["status"] == "candidate_requires_confirmation"
    assert result["source_items_incomplete"] is True
    assert result["searched_name_coverage_complete"] is False
    assert result["identity_confirmed"] is False


def test_complete_negative_still_no_match_if_all_qids_have_full_names():
    source = {"success": 1, "entities": {"Q89": _apple_entity()}}
    parsed = parse_qid_lookup(source, ["Q89"], ["en"])
    result = candidates_for_name(parsed, "nonexistent source name", "en")
    assert result["status"] == "unknown_no_match"
    assert result["source_items_incomplete"] is False
    assert result["searched_name_coverage_complete"] is True


@pytest.mark.parametrize("link", [
    "https://security.example.org/advisory?api_key=private-demo-secret",
    "https://security.example.org/advisory?access_key=private-demo-secret",
    "https://security.example.org/advisory?session_id=private-demo-secret",
    "https://security.example.org/advisory?jwt=private-demo-secret",
    "https://security.example.org/advisory?signature=private-demo-secret",
    "https://security.example.org/advisory?api%5Fkey=private-demo-secret",
    "https://security.example.org/advisory\nnewline",
    "https://security.example.org/advisory\rreturn",
    "https://security.example.org/unsafe\\backslash",
    "https://security.example.org/\x00control",
    "https://security.example.org/path%0Ainjected",
    "https://security.example.org/path%0dcarriage",
    "https://security.example.org/path%00nul",
    " https://security.example.org/advisory",
])
def test_unsafe_external_reference_never_echoed(link):
    assert _safe_ref(link) is None
    payload = {"vulns": [{
        "id": "GHSA-cpwx-vrp4-4pq7",
        "published": "2026-11-21T10:00:00Z",
        "modified": "2026-11-21T12:00:00Z",
        "references": [
            {"url": "https://github.com/example/repo/issues/123"},
            {"url": link},
        ],
    }]}
    projected = parse_package_query(
        payload, ecosystem="PyPI", package="Jinja2", version="2.10.1"
    )
    safe = projected["records"][0]["advisory_links"]
    assert safe == ["https://github.com/example/repo/issues/123"]
    assert "private-demo-secret" not in json.dumps(projected)


@pytest.mark.parametrize("ecosy", [[], {}, ["npm"], {"name": "npm"}, set(), 14, True])
def test_unhashable_and_non_string_ecosystem_is_controlled_validation_error(ecosy):
    for fn in (plan_package_query, plan_compact_package_query):
        with pytest.raises(ValueError, match="ecosystem|scoped"):
            fn(ecosy, "lodash", "4.17.11")


def test_seeded_compact_result_shape_fuzz_never_throws_non_contract_exception():
    rng = random.Random(20261121)
    types = [None, True, False, 0, -1, "bad", [], {}, 3.5]
    for _ in range(550):
        choice = rng.randrange(6)
        if choice == 0:
            payload = rng.choice(types)
        elif choice == 1:
            payload = {"results": rng.choice(types)}
        elif choice == 2:
            payload = {"results": [rng.choice(types)]}
        elif choice == 3:
            payload = {"results": [{"vulns": rng.choice(types)}]}
        elif choice == 4:
            payload = {"results": [{"vulns": [{
                "id": rng.choice(types),
                "modified": rng.choice(types),
            }]}]}
        else:
            payload = {"results": [{"vulns": [], "next_page_token": rng.choice(types)}]}
        try:
            result = parse_compact_package_query(
                payload, ecosystem="npm", package="lodash", version="4.17.11"
            )
        except ValueError:
            continue
        assert result["source"] == "osv_public_api"
        assert result["no_advisory_not_equivalent_to_safe_package"]
        assert result["advisory_count_projected"] <= 100
        assert result["zero_network_calls"] is True


def test_source_derived_real_wikidata_unknown_or_positive_never_auto_confirms():
    raw = json.loads(
        (BASE / "wikidata_q42_q64_q30_20261121.json").read_text("utf-8")
    )
    parsed = parse_qid_lookup(raw, ["Q42", "Q64", "Q30"],
                              ["en", "de", "fr", "es", "sl", "it"])
    for language in ("en", "de", "fr", "es", "sl", "it"):
        for name in ("Berlin", "United States", "unknown provenance", "apple"):
            result = candidates_for_name(parsed, name, language)
            assert result["identity_confirmed"] is False
            assert result["searched_name_coverage_complete"] is False or (
                result["searched_name_coverage_complete"] is True
                and result["source_items_incomplete"] is False
            )


def test_null_alias_record_is_rejected_instead_of_projecting_null():
    entity = _apple_entity()
    entity["aliases"] = {"en": [None]}
    source = {"success": 1, "entities": {"Q89": entity}}
    with pytest.raises(ValueError, match="alias"):
        parse_qid_lookup(source, ["Q89"], ["en"])


def test_excessively_nested_source_objects_fail_closed_with_public_value_error():
    nested = []
    for _ in range(6000):
        nested = [nested]
    with pytest.raises(ValueError, match="Invalid Wikidata JSON"):
        parse_qid_lookup(nested, ["Q89"], ["en"])
    with pytest.raises(ValueError, match="Invalid OSV JSON"):
        parse_compact_package_query(
            nested, ecosystem="PyPI", package="Jinja2", version="2.10.1",
        )
