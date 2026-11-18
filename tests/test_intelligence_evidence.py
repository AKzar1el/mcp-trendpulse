"""Offline provider envelope validation and noisy upstream error detection."""

import pytest

from mcp_trendpulse.intelligence_evidence import evidence_projection, UnexpectedSourceShape


@pytest.mark.parametrize(("source", "payload", "count"), [
    ("cfpb", {"hits": {"hits": [{"_source": {"issue": "Unexpected fees",
        "complaint_what_happened": "private content"}}]}}, 1),
    ("cordis", {"results": {"bindings": [{"title": {"value": "battery"}}]}}, 1),
    ("copernicus", {"id": "sentinel-2-l2a", "type": "Collection", "title": "Sentinel 2"}, 1),
    ("worldbank", [{"page": 1}, [{"date": "2025", "value": 2.0}]], 1),
    ("gdelt_latest", {"lines": [
        "1234 aabbccddeeff00112233445566778899 https://data.gdeltproject.org/gdeltv2/20261118120000.export.CSV.zip"
    ]}, 1),
    ("openalex", {"results": [{"id": "W123"}]}, 1),
    ("eurostat", {"id": ["geo", "time"], "value": {"0": 12}, "size": [1, 1]}, 1),
])
def test_valid_shapes(source, payload, count):
    result = evidence_projection(source, payload)
    assert result["record_count"] == count
    assert isinstance(result["sample"], list)


def test_cfpb_never_exports_private_narrative():
    payload = {"hits": {"hits": [{"_source": {
        "issue": "Billing", "complaint_what_happened": "PRIVATE PERSON",
        "company": "Example", "zip_code": "12345",
    }}]}}
    fields = evidence_projection("cfpb", payload)["sample"][0]
    assert fields == {"issue": "Billing", "company": "Example"}
    assert "PRIVATE PERSON" not in repr(fields)


@pytest.mark.parametrize(("source", "payload"), [
    ("cfpb", {"error": "forbidden"}),
    ("cordis", {"result": {"bindings": []}}),
    ("copernicus", {"errors": ["bad parameter"]}),
    ("openalex", {"error": "invalid_key"}),
    ("worldbank", {"message": [{"id": "not-found"}]}),
    ("eurostat", {"error": "DATASET_NOT_FOUND"}),
])
def test_provider_errors_are_not_mistaken_for_zero_results(source, payload):
    with pytest.raises(UnexpectedSourceShape):
        evidence_projection(source, payload)


def test_gdelt_manifest_preserves_file_size_and_name_only():
    result = evidence_projection("gdelt_latest", {"lines": [
        "12345 0123456789abcdef0123456789abcdef http://data.gdeltproject.org/gdeltv2/20261118120000.export.CSV.zip"
    ]})
    assert result["record_count"] == 1
    assert result["sample"][0]["compressed_bytes"] == 12345
