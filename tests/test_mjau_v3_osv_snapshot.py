"""A10 replay of actual OSV metadata without redistributing upstream advisory bodies.

The fixture is a deliberately minimized, source-derived projection of two
official OSV API responses observed on 2026-11-21, not a verbatim API body.
Original response SHA-256 values are retained for audit and source traceability.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from mcp_trendpulse.intelligence_core import IntelligenceError, plan_source
from mcp_trendpulse.mjau_v3.osv import parse_advisory_lookup, parse_package_query


FIXTURE = Path(__file__).parent / "fixtures" / "mjau_v3" / "osv_jinja2_and_osv_2020_744_20261121.json"
EMPTY_SOURCE = Path(__file__).parent / "fixtures" / "mjau_v3" / "osv_six_1_16_0_empty_20261121.json"
EMPTY_SOURCE_SHA256 = "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"


def original_source_projection():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_minimal_source_derived_fixture_excludes_advisory_bodies():
    snapshot = original_source_projection()
    assert snapshot["metadata"]["original_raw_not_copied"] is True
    assert snapshot["metadata"]["license_review_required_per_original_feed"] is True
    records = snapshot["minimal_package_envelope"]["vulns"]
    assert len(records) == 10
    assert all(set(record) == {"id", "published", "modified", "withdrawn"} for record in records)
    assert all(re.fullmatch(r"[a-f0-9]{64}", snapshot["metadata"][key]) for key in
               ("source_package_sha256", "source_advisory_sha256"))
    assert not any("details" in item or "summary" in item for item in records)


def test_original_source_derived_package_version_yields_ten_distinct_advisories():
    snapshot = original_source_projection()
    response = parse_package_query(
        snapshot["minimal_package_envelope"],
        ecosystem="PyPI",
        package="Jinja2",
        version="2.10.1",
    )
    assert response["advisory_count_in_this_response"] == 10
    assert response["status"] == "source_advisories_returned"
    assert response["source_population_complete"] is True
    ids = [record["advisory_id"] for record in response["records"]]
    assert len(ids) == len(set(ids))
    assert response["no_auto_remediation"] is True
    assert response["no_advisory_not_equivalent_to_safe_package"] is True
    assert all(record["is_not_commercial_demand_evidence"] for record in response["records"])
    # The original observed GHSA and PYSEC ID families have separate CC BY
    # upstream sources; these are hints, not permission to redistribute bodies.
    assert all(record["source_license_hint"] == "CC-BY-4.0" for record in response["records"])
    assert all(record["source_specific_license_review_required"] for record in response["records"])
    assert all(not record["raw_advisory_redistribution_authorized"] for record in response["records"])
    assert {record["upstream_database_hint"] for record in response["records"]} == {
        "GitHub Advisory Database", "PyPI Advisory Database",
    }


def test_real_source_derived_advisory_identity_and_dates():
    snapshot = original_source_projection()
    result = parse_advisory_lookup(snapshot["minimal_advisory"], "OSV-2020-744")
    record = result["record"]
    assert record["advisory_id"] == "OSV-2020-744"
    assert record["published_at"] == "2020-07-04T00:00:01.948828Z"
    assert record["modified_at"] == "2022-04-13T03:04:39.780694Z"
    assert record["is_not_exploitation_evidence"] is True


def test_missing_advisory_list_only_means_no_indexed_match_in_that_response():
    # Synthetic negative test only; the saved Jinja2/idna observations are positive.
    result = parse_package_query(
        {"vulns": []}, ecosystem="PyPI", package="Jinja2", version="2.10.1"
    )
    assert result["status"] == "no_returned_advisories"
    assert result["no_advisory_not_equivalent_to_safe_package"] is True


def test_actual_osv_empty_object_response_is_no_indexed_match_not_safe():
    # Official POST /v1/query for real PyPI six==1.16.0 on 2026-11-21
    # returned HTTP 200, JSON {}. This is original two-byte source evidence.
    raw = EMPTY_SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EMPTY_SOURCE_SHA256
    result = parse_package_query(
        json.loads(raw), ecosystem="PyPI", package="six", version="1.16.0"
    )
    assert result["status"] == "no_returned_advisories"
    assert result["source_population_complete"] is True
    assert result["advisory_count_in_this_response"] == 0
    assert result["no_advisory_not_equivalent_to_safe_package"] is True


def test_source_projection_replay_is_network_free(monkeypatch):
    def network_not_allowed(*_args, **_kwargs):
        raise AssertionError("Saved source metadata replay must never make an API request")

    monkeypatch.setattr("socket.socket", network_not_allowed)
    snapshot = original_source_projection()
    result = parse_advisory_lookup(snapshot["minimal_advisory"], "OSV-2020-744")
    assert result["record"]["status"] == "dated_advisory"


def test_v1_has_no_osv_package_version_evidence_source():
    with pytest.raises(IntelligenceError, match="Unknown source ID"):
        plan_source("osv_public_api")
