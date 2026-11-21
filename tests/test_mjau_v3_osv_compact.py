"""A10 bounded compact ID-only OSV source contract and saved official results."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from mcp_trendpulse.mjau_v3.osv import (
    parse_compact_http_result,
    parse_compact_package_query,
    present_compact_query_for_mcp,
    plan_compact_package_query,
)

SOURCE = Path(__file__).parent / "fixtures" / "mjau_v3" / (
    "osv_querybatch_source_20261121.json"
)


def source_cases():
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def envelope(rows, token=None):
    page = {"vulns": rows}
    if token is not None:
        page["next_page_token"] = token
    return {"results": [page]}


def record(i):
    return {"id": f"GHSA-0000-0000-{i:04d}",
            "modified": "2026-11-21T12:00:00Z"}


def parse(payload):
    return parse_compact_package_query(
        payload, ecosystem="npm", package="lodash", version="4.17.11"
    )


def test_one_keyless_official_batch_request_is_plan_only_and_bounded():
    p = plan_compact_package_query("PyPI", "Django", "2.2.0")
    assert p["url"] == "https://api.osv.dev/v1/querybatch"
    assert p["method"] == "POST"
    assert p["json_body"] == {
        "queries": [{"package": {"name": "Django", "ecosystem": "PyPI"},
                     "version": "2.2.0"}]
    }
    assert p["max_requests_if_approved"] == 1
    assert p["max_response_bytes"] == 192_000
    assert p["execution"] == "PLAN_ONLY"
    assert p["zero_network_calls"]
    assert p["requires_existing_trendpulse_budget_and_cache"]
    assert p["returns_identifiers_and_modified_only"]


@pytest.mark.parametrize("ecosy,pkg,version", [
    ("unapproved", "lodash", "1.0"), ("npm", "../secret", "1.0"),
    ("PyPI", "Django", "version?"), ("npm", "lodash", ""),
])
def test_bad_source_id_or_input_never_generates_request(ecosy, pkg, version):
    with pytest.raises(ValueError):
        plan_compact_package_query(ecosy, pkg, version)


@pytest.mark.parametrize("source", ["PyPI", "npm"])
def test_original_compact_sample_has_only_id_and_modified(source):
    fixture = source_cases()
    assert fixture["metadata"]["original_full_advisory_bodies_retained"] is False
    cases = [x for x in fixture["samples"] if x["ecosystem"] == source]
    assert cases
    for case in cases:
        assert all(set(x) == {"id", "modified"} for x in case["advisory_stubs"])
        result = parse_compact_package_query(
            envelope(case["advisory_stubs"]),
            ecosystem=case["ecosystem"], package=case["package"],
            version=case["version"],
        )
        assert result["advisory_count_projected"] == len(case["advisory_stubs"])
        assert result["source_population_complete"]
        assert result["compact_id_only_no_full_advisory_bodies"] is True
        assert result["no_advisory_not_equivalent_to_safe_package"] is True
        assert result["no_auto_remediation"] is True
        assert all(r["published_at"] is None for r in result["records"])
        assert all(r["raw_advisory_redistribution_authorized"] is False
                   for r in result["records"])


def test_real_django_original_source_has_more_than_12_while_compact_is_small():
    fixture = source_cases()
    django = next(c for c in fixture["samples"] if c["package"] == "Django")
    assert fixture["metadata"]["original_http_status"] == 200
    assert fixture["metadata"]["original_raw_bytes"] < 192_000
    assert django["count"] == 75
    assert not django["paged"]
    assert len(django["advisory_stubs"]) == 40
    sample = parse_compact_package_query(
        envelope(django["advisory_stubs"]),
        ecosystem="PyPI", package="Django", version="2.2.0",
    )
    assert sample["advisory_count_projected"] == 40
    assert sample["no_advisory_not_equivalent_to_safe_package"]


def test_more_than_hundred_ids_never_disappears_or_becomes_complete():
    result = parse(envelope([record(i) for i in range(104)]))
    assert result["status"] == "incomplete_truncated_response"
    assert result["provider_ids_in_this_page"] == 104
    assert result["advisory_count_projected"] == 100
    assert not result["source_population_complete"]
    assert all("summary" not in r and "details" not in r for r in result["records"])


def test_empty_with_pagination_is_unknown_not_secure():
    output = parse(envelope([], token="opaque-source-token"))
    assert output["status"] == "incomplete_paged_response"
    assert output["provider_ids_in_this_page"] == 0
    assert output["source_population_complete"] is False
    assert output["no_advisory_not_equivalent_to_safe_package"]


def test_empty_compact_source_is_only_no_indexed_match():
    r = parse({"results": [{}]})
    assert r["status"] == "no_returned_advisories"
    assert r["advisory_count_projected"] == 0
    assert r["source_population_complete"]
    assert r["no_advisory_not_equivalent_to_safe_package"]


@pytest.mark.parametrize("payload", [
    {}, {"results": []}, {"results": [{}, {}]}, {"results": [None]},
    {"results": [{"vulns": None}]}, {"results": [{"vulns": {}}]},
    {"results": [{"vulns": [record(1), record(1)]}]},
    {"results": [{"vulns": [{**record(1), "details": "unsafe"}]}]},
    {"results": [{"next_page_token": ""}]},
])
def test_bad_compact_result_cannot_be_presented_as_complete(payload):
    with pytest.raises(ValueError):
        parse(payload)


def test_unrecognized_source_id_has_no_assumed_reuse_rights():
    sample = record(1)
    sample["id"] = "OSV-2020-744"
    output = parse(envelope([sample]))["records"][0]
    assert output["upstream_database_hint"] is None
    assert output["source_license_hint"] is None
    assert output["source_specific_license_review_required"]
    assert output["raw_advisory_redistribution_authorized"] is False


def test_http_errors_are_unknown_never_empty():
    for status in [401, 403, 429, 503]:
        output = parse_compact_http_result(
            status, {}, ecosystem="npm", package="lodash", version="4.17.11"
        )
        assert output["status"] == "source_unavailable"
        assert output["not_a_zero_result"] is True
        assert output["retry"] is False


def test_compact_source_input_is_never_mutated():
    source = envelope([record(4)])
    prior = copy.deepcopy(source)
    parse(source)
    assert source == prior


def test_mcp_presentation_is_substantially_smaller_with_all_75_real_ids():
    source = json.loads(
        (SOURCE.parent / "osv_django_compact_20261121.json").read_text("utf-8")
    )
    detail = parse_compact_package_query(
        source["one_query_envelope"],
        ecosystem="PyPI", package="Django", version="2.2.0",
    )
    before = copy.deepcopy(detail)
    compact = present_compact_query_for_mcp(detail)
    assert detail == before
    assert compact["advisory_count_projected"] == 75
    assert compact["provider_ids_in_this_page"] == 75
    assert compact["source_population_complete"] is True
    assert compact["source_licenses_are_heterogeneous"]
    assert compact["source_specific_license_review_required"]
    assert compact["raw_advisory_redistribution_authorized"] is False
    assert compact["no_advisory_not_equivalent_to_safe_package"]
    assert compact["no_auto_remediation"] is True
    assert [r["id"] for r in compact["advisories"]] == [
        r["advisory_id"] for r in detail["records"]
    ]
    for record in compact["advisories"]:
        assert set(record) == {
            "id", "modified_at", "source_url", "source_database_hint",
        }
    full_size = len(json.dumps(detail, ensure_ascii=False).encode("utf-8"))
    small_size = len(json.dumps(compact, ensure_ascii=False).encode("utf-8"))
    assert small_size < full_size * 0.4
    assert small_size < 20_000


def test_mcp_presentation_of_no_matches_does_not_claim_secure_package():
    detail = parse({"results": [{}]})
    compact = present_compact_query_for_mcp(detail)
    assert compact["advisories"] == []
    assert compact["status"] == "no_returned_advisories"
    assert compact["no_advisory_not_equivalent_to_safe_package"]
    assert compact["source_specific_license_review_required"]


def test_mcp_presentation_cannot_accept_unvalidated_upstream_input():
    with pytest.raises(ValueError):
        present_compact_query_for_mcp({"results": [{}]})
