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



def test_rsshub_rejects_html_like_error_xml_and_accepts_feed():
    with pytest.raises(UnexpectedSourceShape, match="RSS/Atom"):
        evidence_projection("rsshub_local", {
            "root": "error",
            "observations": [{"element": "title", "text": "Route failed"}],
        })
    assert evidence_projection("rsshub_local", {
        "root": "rss",
        "observations": [
            {"element": "title", "text": "Test 1"},
            {"element": "title", "text": "Title1"},
        ],
    })["record_count"] == 2


@pytest.mark.parametrize("payload", [
    {"root": "Acknowledgement_MarketDocument", "observations": [
        {"element": "Reason", "text": "No matching data"}]},
    {"root": "Error", "observations": [{"element": "message", "text": "Invalid token"}]},
    {"root": "GL_MarketDocument", "observations": [
        {"element": "mRID", "text": "Only document identity; no load measurements"}]},
    {"root": "GL_MarketDocument", "observations": []},
])
def test_entsoe_does_not_treat_acknowledgements_as_actual_load(payload):
    with pytest.raises(UnexpectedSourceShape):
        evidence_projection("entsoe", payload)


def test_entsoe_requires_generation_load_document_with_quantity_measurement():
    report = evidence_projection("entsoe", {
        "root": "GL_MarketDocument",
        "observations": [
            {"element": "mRID", "text": "TEST-DOCUMENT"},
            {"element": "position", "text": "1"},
            {"element": "quantity", "text": "1100.25"},
        ],
    })
    assert report["record_count"] == 3
    assert "electricity load" in report["unit"]



def test_openalex_and_ted_projections_honor_public_twenty_record_limit():
    from mcp_trendpulse.intelligence_evidence import evidence_projection

    openalex_rows = [{
        "id": f"https://openalex.org/W{1000000000 + i}",
        "display_name": f"Research work {i}",
        "publication_date": "2026-11-18",
    } for i in range(20)]
    ted_rows = [{
        "publication-number": f"{100000+i}-2026",
        "publication-date": "2026-11-19",
        "notice-title": {"eng": [f"Public procurement {i}"]},
    } for i in range(20)]
    oa = evidence_projection("openalex", {"results": openalex_rows})
    notices = evidence_projection("ted", {"notices": ted_rows})
    assert oa["record_count"] == 20
    assert len(oa["sample"]) == 20
    assert notices["record_count"] == 20
    assert len(notices["sample"]) == 20
    assert notices["sample"][0]["notice-title"]["eng"] == ["Public procurement 0"]
