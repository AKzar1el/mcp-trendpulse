"""A04 offline falsification: synthetic fixtures are not live data proof."""
import copy
import pytest
from mcp_trendpulse.mjau_v3.wikidata import (
    candidates_for_name, parse_qid_lookup, plan_qid_lookup,
)

LANGS = ["en", "de", "fr", "es", "sl", "it"]
WORDS = {"en": "Apple", "de": "Apfel", "fr": "pomme", "es": "manzana", "sl": "jabolko", "it": "mela"}


def source_entity(qid, words):
    return {"id": qid, "type": "item", "labels": {
        lang: {"language": lang, "value": word} for lang, word in words.items()
    }, "aliases": {}, "descriptions": {}}


def payload():
    return {"success": 1, "entities": {
        "Q89": source_entity("Q89", WORDS),
        "Q312": source_entity("Q312", {"en": "Apple", "de": "Apple", "fr": "Apple", "es": "Apple", "sl": "Apple", "it": "Apple"}),
    }}


_UNSET = object()

def parse(data=_UNSET):
    return parse_qid_lookup(payload() if data is _UNSET else data, ["Q89", "Q312"], LANGS)


def test_plan_is_fixed_origin_explicit_qid_and_zero_network(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("Network not authorized")
    monkeypatch.setattr("socket.socket", deny)
    plan = plan_qid_lookup(["Q89", "Q312"], LANGS)
    assert plan["url"].startswith("https://www.wikidata.org/w/api.php?")
    assert "wbgetentities" in plan["url"] and plan["request_count_if_approved"] == 1
    assert plan["zero_network_calls"] and plan["execution"] == "PLAN_ONLY"


@pytest.mark.parametrize("qid", ["apple", "q89", "Q0", "Q-1", "Q89%7CQ312", "Q99999999999", " Q89"])
def test_invalid_qid_rejected(qid):
    with pytest.raises(ValueError, match="explicit Wikidata QIDs"):
        plan_qid_lookup([qid], ["en"])


def test_duplicate_qids_rejected():
    with pytest.raises(ValueError, match="unique"):
        plan_qid_lookup(["Q89", "Q89"], ["en"])


@pytest.mark.parametrize("language", ["ru", "zh", "EN", "en-us", "en|fr"])
def test_unsupported_languages_rejected(language):
    with pytest.raises(ValueError, match="language"):
        plan_qid_lookup(["Q89"], [language])


def test_six_language_exact_names_remain_source_scoped():
    parsed = parse()
    assert len(parsed["results"][0]["names"]) == 6
    for lang, word in WORDS.items():
        selected = candidates_for_name(parsed, word, lang)
        assert "Q89" in selected["candidate_qids"]
        assert not selected["identity_confirmed"]


def test_ambiguous_english_apple_not_auto_merged():
    query = candidates_for_name(parse(), "Apple", "en")
    assert query["status"] == "ambiguous"
    assert query["candidate_qids"] == ["Q312", "Q89"]


def test_unique_name_still_requires_human_confirmation():
    query = candidates_for_name(parse(), "jabolko", "sl")
    assert query["status"] == "candidate_requires_confirmation"
    assert query["candidate_qids"] == ["Q89"] and not query["identity_confirmed"]


def test_accent_not_erased_and_unicode_preserved():
    data = payload()
    data["entities"]["Q89"]["labels"]["sl"]["value"] = "čéšnje"
    parsed = parse(data)
    assert candidates_for_name(parsed, "čéšnje", "sl")["candidate_qids"] == ["Q89"]
    assert candidates_for_name(parsed, "cesnje", "sl")["status"] == "unknown_no_match"


def test_missing_entity_not_negative_zero():
    data = {"success": 1, "entities": {"Q89": {"id": "Q89", "missing": ""}}}
    parsed = parse_qid_lookup(data, ["Q89", "Q312"], ["en"])
    assert parsed["results"][0]["status"] == "unknown_missing_entity"
    assert parsed["results"][1]["status"] == "unknown_partial_response"
    assert not parsed["source_coverage_complete"]


def test_empty_source_map_is_unknown():
    p = parse_qid_lookup({"success": 1, "entities": {}}, ["Q89"], ["en"])
    assert p["results"][0]["status"] == "unknown_partial_response"


@pytest.mark.parametrize("data", [None, {}, [], {"success": 0}, {"error": {"code": "ratelimited"}}, {"success": 1, "entities": []}])
def test_malformed_or_failed_api_response_never_becomes_zero(data):
    with pytest.raises(ValueError):
        parse(data)


def test_unrequested_entity_rejected():
    data = payload()
    data["entities"]["Q900"] = source_entity("Q900", {"en": "Other"})
    with pytest.raises(ValueError, match="result map|Unrequested"):
        parse(data)


def test_wrong_qid_in_value_rejected():
    data = payload()
    data["entities"]["Q89"]["id"] = "Q312"
    with pytest.raises(ValueError, match="Mismatched"):
        parse(data)


def test_language_mismatch_rejected():
    data = payload()
    data["entities"]["Q89"]["labels"]["en"]["language"] = "fr"
    with pytest.raises(ValueError, match="Language-inconsistent"):
        parse(data)


def test_unrequested_language_rejected():
    data = payload()
    data["entities"]["Q89"]["labels"]["ja"] = {"language": "ja", "value": "apple"}
    with pytest.raises(ValueError, match="Unrequested language"):
        parse(data)


def test_unverified_redirect_fails_closed():
    data = payload()
    data["redirects"] = [{"from": "Q123", "to": "Q89"}]
    with pytest.raises(ValueError, match="redirect"):
        parse(data)


def test_control_character_rejected():
    data = payload()
    data["entities"]["Q89"]["labels"]["en"]["value"] = "Apple\nInjected"
    with pytest.raises(ValueError, match="Control"):
        parse(data)


def test_oversized_payload_rejected():
    data = payload()
    data["entities"]["Q89"]["extra"] = "X" * 193_000
    with pytest.raises(ValueError, match="too large"):
        parse(data)


def test_alias_limit_and_duplicate_alias_dedup():
    data = payload()
    data["entities"]["Q89"]["aliases"]["en"] = [
        {"language": "en", "value": "apple fruit"},
        {"language": "en", "value": "apple fruit"},
    ]
    parsed = parse(data)
    assert parsed["results"][0]["names"]["en"]["aliases"] == ["apple fruit"]
    assert candidates_for_name(parsed, "apple fruit", "en")["candidate_qids"] == ["Q89"]
    too_many = copy.deepcopy(data)
    too_many["entities"]["Q89"]["aliases"]["en"] *= 5
    projected = parse(too_many)
    record = projected["results"][0]["names"]["en"]
    assert record["source_alias_count"] == 10
    assert record["aliases_truncated"] is True
    assert record["aliases"] == ["apple fruit"]
    missing = candidates_for_name(projected, "unlisted alias", "en")
    assert missing["status"] == "unknown_incomplete_aliases"
    assert missing["identity_confirmed"] is False
    assert missing["searched_aliases_incomplete"] is True
    # A bounded projected match still requires human confirmation.
    assert candidates_for_name(projected, "apple fruit", "en")["status"] == (
        "candidate_requires_confirmation"
    )


def test_no_text_similarity_does_not_infer_jurisdiction_or_market():
    parsed = parse()
    assert candidates_for_name(parsed, "Apples", "en")["status"] == "unknown_no_match"
    assert "country" not in parsed["results"][0]


def test_not_a_live_source_claim():
    parsed = parse()
    assert parsed["status"] == "OFFLINE_PARSED_UPSTREAM_PAYLOAD"
    assert parsed["raw_payload_reused_not_fetched"] and parsed["no_auto_entity_merging"]


def test_two_real_wikidata_page_labels_are_distinct_review_candidates():
    """Manually reviewed 2026-11-21 official Q89 and Q312 page *labels*.

    This is NOT an Action API transport acceptance; only the labels are
    independently source-backed, other API fields are constructed test data.
    """
    data = {"success": 1, "entities": {
        "Q89": source_entity("Q89", {"en": "apple"}),
        "Q312": source_entity("Q312", {"en": "Apple Inc."}),
    }}
    parsed = parse_qid_lookup(data, ["Q89", "Q312"], ["en"])
    assert candidates_for_name(parsed, "apple", "en")["candidate_qids"] == ["Q89"]
    assert candidates_for_name(parsed, "Apple Inc.", "en")["candidate_qids"] == ["Q312"]
    assert candidates_for_name(parsed, "APPLE", "en")["identity_confirmed"] is False


@pytest.mark.parametrize("http_code,reason", [
    (401, "permission_denied"), (403, "permission_denied"),
    (429, "rate_limited"), (503, "upstream_unavailable"),
    (504, "upstream_unavailable"), (302, "redirect_disallowed"),
])
def test_http_failure_is_unavailable_without_retry_or_false_zero(http_code, reason):
    from mcp_trendpulse.mjau_v3.wikidata import parse_transport_result
    out = parse_transport_result(http_code, {"error": {"secret": "dont_echo"}}, ["Q89"], ["en"])
    assert out["results"] is None and out["reason"] == reason
    assert not out["automatic_retry"] and out["zero_not_inferred_from_absence"]
    assert "dont_echo" not in str(out)


def test_http_200_bad_envelope_does_not_silently_succeed():
    from mcp_trendpulse.mjau_v3.wikidata import parse_transport_result
    with pytest.raises(ValueError, match="envelope"):
        parse_transport_result(200, {"error": {"code": "bad"}}, ["Q89"], ["en"])


def test_http_200_valid_envelope_matches_parser():
    from mcp_trendpulse.mjau_v3.wikidata import parse_transport_result
    assert parse_transport_result(200, payload(), ["Q89", "Q312"], LANGS) == parse()
