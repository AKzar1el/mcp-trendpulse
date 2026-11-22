"""Preregistered new original-source evidence and post-failure corrections.

Provider observations are reviewable facts, not market, buyer or security verdicts.
The original OSV full response bodies were never saved to these fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcp_trendpulse.mjau_v3.osv import (
    parse_compact_package_query,
    parse_package_query,
)
from mcp_trendpulse.mjau_v3.wikidata import (
    candidates_for_name,
    parse_qid_lookup,
)

BASE = Path(__file__).parent / "fixtures" / "mjau_v3"
LANGS = ["en", "de", "fr", "es", "sl", "it"]


def fixture(name):
    return json.loads((BASE / name).read_text(encoding="utf-8"))


def test_real_wikidata_multi_qid_missing_label_remains_unknown():
    payload = fixture("wikidata_q42_q64_q30_20261121.json")
    assert set(payload["entities"]) == {"Q42", "Q64", "Q30"}
    parsed = parse_qid_lookup(payload, ["Q42", "Q64", "Q30"], LANGS)
    assert parsed["source_coverage_complete"] is True
    by_id = {x["qid"]: x for x in parsed["results"]}
    assert by_id["Q42"]["names"]["en"]["label"] is None
    assert by_id["Q64"]["names"]["en"]["label"] == "Berlin"
    assert all(by_id["Q64"]["names"][lang]["label"] for lang in LANGS)
    assert by_id["Q30"]["names"]["en"]["source_alias_count"] == 20
    assert by_id["Q30"]["names"]["en"]["aliases_truncated"] is True
    assert by_id["Q64"]["names"]["de"]["aliases_truncated"] is True
    assert candidates_for_name(parsed, "Berlin", "en")["status"] == (
        "candidate_requires_confirmation"
    )
    missing = candidates_for_name(parsed, "some unknown name not in any alias", "en")
    assert not missing["candidate_qids"] and not missing["identity_confirmed"]
    assert missing["status"] == "unknown_incomplete_aliases"


def test_preregistered_nine_source_queries_preserve_missingness_and_licenses():
    results = fixture("acceptance_source_metadata_20261121.json")
    assert results["total_http_calls"] == 9
    assert results["no_retries"] is True
    assert results["sources_no_paid"] is True
    assert len(results["osv"]) == 8
    assert results["wikidata"]["http_status"] == 200
    assert results["wikidata"]["status"] == "source_parsed"
    assertions = {
        ("PyPI", "Jinja2", "2.10.1"): (10, "source_advisories_returned"),
        ("PyPI", "six", "1.16.0"): (0, "no_returned_advisories"),
        ("PyPI", "requests", "2.19.1"): (10, "source_advisories_returned"),
        ("PyPI", "PyYAML", "5.1"): (6, "source_advisories_returned"),
        ("npm", "minimist", "0.0.8"): (2, "source_advisories_returned"),
        ("npm", "react", "18.2.0"): (0, "no_returned_advisories"),
    }
    for case in results["osv"]:
        key = case["ecosystem"], case["package"], case["version"]
        assert case["http_status"] == 200
        if key in assertions:
            count, status = assertions[key]
            assert case["adapter_count"] == count
            assert case["adapter_status"] == status
            assert case["raw_advisory_reuse_auth"] is False
        elif case["package"] == "Django":
            assert case["unavailable"] == "response_exceeded_192000_bytes"
            assert "adapter_count" not in case
        elif case["package"] == "lodash":
            # Frozen original result before the source-backed 93-reference fix.
            assert case["adapter_status"] == "parse_rejected"
        else:
            raise AssertionError(f"Unexpected unregistered query: {key}")


def test_real_django_75_ids_now_complete_under_safe_size_cap():
    source = fixture("osv_django_compact_20261121.json")
    assert source["metadata"]["http_status"] == 200
    assert source["metadata"]["raw_body_stored"] is False
    assert source["query"] == {
        "ecosystem": "PyPI", "package": "Django", "version": "2.2.0",
    }
    raw = source["one_query_envelope"]
    assert len(raw["results"][0]["vulns"]) == 75
    assert all(set(x) == {"id", "modified"} for x in raw["results"][0]["vulns"])
    projected = parse_compact_package_query(
        raw, ecosystem="PyPI", package="Django", version="2.2.0"
    )
    assert projected["provider_ids_in_this_page"] == 75
    assert projected["advisory_count_projected"] == 75
    assert projected["status"] == "source_advisories_returned"
    assert projected["source_population_complete"] is True
    assert projected["no_advisory_not_equivalent_to_safe_package"]
    assert all(r["raw_advisory_redistribution_authorized"] is False
               for r in projected["records"])


def test_real_lodash_large_reference_list_does_not_hide_source_advisory():
    source = fixture("osv_lodash_ref_counts_20261121.json")
    assert source["metadata"]["full_advisory_body_retained"] is False
    observations = source["per_advisory_reference_counts"]
    assert len(observations) == 6
    assert max(x["references_count"] for x in observations) == 93
    assert sum(x["references_count"] > 30 for x in observations) == 1
    records = [
        {
            "id": x["id"],
            "published": "2025-09-01T12:00:00Z",
            "modified": "2025-09-03T12:00:00Z",
            # Safe constructed URLs; original advisory bodies were not saved.
            "references": [
                {"url": f"https://example.org/safe/{index}"}
                for index in range(x["references_count"])
            ],
        }
        for x in observations
    ]
    result = parse_package_query(
        {"vulns": records}, ecosystem="npm",
        package="lodash", version="4.17.11",
    )
    assert result["advisory_count_in_this_response"] == 6
    assert result["status"] == "source_advisories_returned"
    assert sum(1 for row in result["records"] if row["references_truncated"]) == 1
    assert all(len(row["advisory_links"]) <= 4 for row in result["records"])
    assert all(not row["raw_advisory_redistribution_authorized"]
               for row in result["records"])
