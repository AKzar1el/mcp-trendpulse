"""B09 real-source-derived release lineage, with no copied release-note bodies.

The fixture retains IDs, dates, canonical URLs and hashes from four official
GitHub Releases/PyPI API responses on 2026-11-21. A reviewer manually attested
the release-version linkage; the algorithm does not infer publisher identity.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from mcp_trendpulse.intelligence_opportunities import SOURCE_KIND, evaluate_opportunities
from mcp_trendpulse.mjau_v3.origin_graph import audit_origin_evidence


FIXTURE = Path(__file__).parent / "fixtures" / "mjau_v3" / "mcp_release_pypi_two_events_20261121.json"


def case():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_four_source_metadata_observations_are_limited_and_traceable():
    fixture = case()
    source_records = fixture["original_sources"]
    assert len(source_records) == 4
    assert {item["version"] for item in source_records} == {"2.2.0", "2.3.0"}
    assert all(re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) for item in source_records)
    assert all(item["endpoint"].startswith(("https://api.github.com/", "https://pypi.org/pypi/"))
               for item in source_records)
    assert "NOT independent customer demand" in fixture["reviewed_relation_basis"]
    assert "no GitHub release notes" in fixture["$schema_note"]


def test_two_original_events_remain_distinct_and_pypi_mirrors_not_independent():
    fixture = case()
    output = audit_origin_evidence(fixture["evidence_records"], as_of=fixture["observed_at"])
    assert output["status"] == "AUDIT_ONLY"
    assert output["records_submitted"] == 4
    assert output["verified_original_event_count"] == 2
    assert output["dependent_or_same_event_records"] == 2
    assert output["unresolved_origin_records"] == 0
    assert output["verified_independent_original_publishers"] == 1
    assert output["v1_independent_publisher_proxy_before_lineage"] == 2
    assert output["v1_proxy_is_not_full_v1_evaluation"] is True
    assert output["no_market_demand_inference"] is True
    assert all(group["original_count"] == 1 and group["derived_count"] == 1
               for group in output["origins"])
    paths = {group["origin_url_key"]["path"] for group in output["origins"]}
    assert paths == {
        "/modelcontextprotocol/python-sdk/releases/tag/v2.2.0",
        "/modelcontextprotocol/python-sdk/releases/tag/v2.3.0",
    }


def test_unreviewed_pypi_relation_abstains_even_if_dates_versions_match():
    fixture = case()
    rows = copy.deepcopy(fixture["evidence_records"])
    for row in rows:
        if row["source_id"] == "pypi_catalog" and row["source_record_id"] == "mcp:2.3.0":
            row["reviewed_origin"] = False
    output = audit_origin_evidence(rows, as_of=fixture["observed_at"])
    assert output["verified_original_event_count"] == 2
    assert output["dependent_or_same_event_records"] == 1
    assert output["unresolved_origin_records"] == 1
    assert output["ignored"]["unreviewed_origin_claim"] == 1


def test_false_original_url_claim_cannot_steal_another_release_root():
    fixture = case()
    rows = copy.deepcopy(fixture["evidence_records"])
    rows[0]["origin_url"] = "https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.2.0"
    with pytest.raises(ValueError, match="own URL"):
        audit_origin_evidence(rows, as_of=fixture["observed_at"])


def test_original_source_case_replays_without_network(monkeypatch):
    def deny_network(*_args, **_kwargs):
        raise AssertionError("B09 recorded evidence is strictly offline")

    monkeypatch.setattr("socket.socket", deny_network)
    fixture = case()
    output = audit_origin_evidence(fixture["evidence_records"], as_of=fixture["observed_at"])
    assert output["zero_network_calls"] is True


def test_real_v1_evaluator_rejects_release_metadata_not_supported_by_its_source_contract():
    """Exact source-derived records cannot create a fictitious v1 uplift.

    GitHub Releases and PyPI distributions are real sources, but neither is a
    supported v1 opportunity-evaluation evidence class. The old label-count
    proxy cannot stand in for an actual baseline measurement.
    """
    fixture = case()
    assert "github_releases" not in SOURCE_KIND
    assert "pypi_catalog" not in SOURCE_KIND
    candidate = {
        "id": "mcp-sdk-releases", "title": "MCP SDK release metadata",
        "lane": "research_to_product", "geography": "US",
        "workflow": "sdk-release-research", "buyer": "",
    }
    evidence = [
        {
            "id": f"release-record-{index}",
            "candidate": candidate["id"],
            "source": row["source_id"],
            "published_at": row["published_at"],
            "observed_at": row["observed_at"],
            "origin_id": f"release-origin-{index}",
            "publisher": row["publisher"],
            "geography": candidate["geography"],
            "workflow": candidate["workflow"],
            "url": row["source_url"],
            "claim": "Source-observed SDK release metadata only",
        }
        for index, row in enumerate(fixture["evidence_records"], start=1)
    ]
    baseline = evaluate_opportunities(
        [candidate], evidence, as_of=fixture["observed_at"]
    )
    assert baseline["rejected_count"] == 4
    assert all(
        "Unknown or non-free source" in row["reason"]
        for row in baseline["rejected_records"]
    )
    assert baseline["results"][0]["status"] == "insufficient"
    assert baseline["results"][0]["independent_publishers"] == 0
    assert baseline["results"][0]["buying_intent_confirmed"] is False
    v3 = audit_origin_evidence(
        fixture["evidence_records"], as_of=fixture["observed_at"]
    )
    assert v3["verified_original_event_count"] == 2
    assert v3["dependent_or_same_event_records"] == 2
    assert v3["v1_proxy_is_not_full_v1_evaluation"] is True
