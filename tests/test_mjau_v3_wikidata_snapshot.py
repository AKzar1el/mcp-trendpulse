"""A04 deterministic replay of a real, CC0 Wikidata Action API observation.

Retrieved 2026-11-21 with the exact one-request Q89/Q312 six-language plan.
Only source data is stored; no OAuth token, session, personal record, or artwork.
The original raw bytes are retained to detect accidental edits to this snapshot.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from mcp_trendpulse.intelligence_core import IntelligenceError, plan_source
from mcp_trendpulse.mjau_v3.wikidata import candidates_for_name, parse_qid_lookup


FIXTURE = Path(__file__).parent / "fixtures" / "mjau_v3" / "wikidata_q89_q312_20261121.json"
EXPECTED_SHA256 = "7e2c2bf65104d1029330d0a752be5a54aa69085b10b13332eeef132d4202ac10"
QIDS = ["Q89", "Q312"]
LANGUAGES = ["en", "de", "fr", "es", "sl", "it"]


def original_payload():
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_SHA256
    assert len(raw) <= 192_000
    return json.loads(raw)


def test_exact_original_source_fixture_and_language_scopes():
    parsed = parse_qid_lookup(original_payload(), QIDS, LANGUAGES)
    assert [item["qid"] for item in parsed["results"]] == QIDS
    fruit, company = parsed["results"]
    assert fruit["status"] == "source_item_observed"
    assert company["status"] == "source_item_observed"
    assert fruit["names"]["en"]["label"] == "apple"
    assert company["names"]["en"]["label"] == "Apple Inc."
    assert sum(bool(v["label"]) for v in fruit["names"].values()) == 6
    assert sum(bool(v["label"]) for v in company["names"].values()) == 4
    assert parsed["no_auto_entity_merging"] is True


def test_real_source_does_not_automatically_confirm_apple_identity():
    parsed = parse_qid_lookup(original_payload(), QIDS, LANGUAGES)
    fruit = candidates_for_name(parsed, "apple", "en")
    company = candidates_for_name(parsed, "Apple Inc.", "en")
    assert fruit["candidate_qids"] == ["Q89"]
    assert company["candidate_qids"] == ["Q312"]
    assert fruit["status"] == company["status"] == "candidate_requires_confirmation"
    assert not fruit["identity_confirmed"] and not company["identity_confirmed"]
    assert candidates_for_name(parsed, "Unrelated", "en")["status"] == "unknown_no_match"


def test_original_source_identity_tampering_fails_closed():
    payload = copy.deepcopy(original_payload())
    payload["entities"]["Q312"]["id"] = "Q89"
    with pytest.raises(ValueError, match="Mismatched Wikidata identity"):
        parse_qid_lookup(payload, QIDS, LANGUAGES)


def test_original_source_can_be_replayed_with_network_unavailable(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Original-source regression must never fetch an API")

    monkeypatch.setattr("socket.socket", forbidden)
    observed = parse_qid_lookup(original_payload(), QIDS, LANGUAGES)
    assert observed["source_coverage_complete"] is True
    assert observed["raw_payload_reused_not_fetched"] is True


def test_v1_does_not_already_offer_this_exact_source_lookup():
    with pytest.raises(IntelligenceError, match="Unknown source ID"):
        plan_source("wikidata_action_api")
