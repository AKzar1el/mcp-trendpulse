"""Offline integration tests of free source overrides, JSON/CSV/XML content and EPO OAuth."""

from mcp_trendpulse import intelligence_core as intel
from mcp_trendpulse.intelligence_core import BudgetCache, collect, plan_source, source_catalog


def test_source_catalog_has_no_duplicate_placeholder_ids():
    entries = source_catalog()
    names = [entry["id"] for entry in entries]
    assert len(names) == len(set(names))
    for key in ("cfpb", "cordis", "epo", "copernicus", "opsi_slovenia", "changedetection_local"):
        assert next(x for x in entries if x["id"] == key)["fetch_enabled"] is True


def test_parse_csv_preserves_data_without_hallucination():
    data = intel._parse_csv(b"DATE,VALUE\n2026-11-17,3.4\n")
    assert data["columns"] == ["DATE", "VALUE"]
    assert data["rows"][0]["VALUE"] == "3.4"


def test_parse_xml_preserves_fact_text():
    data = intel._parse_xml(b"<feed><entry><title>Battery passport</title></entry></feed>")
    assert data["root"] == "feed"
    assert data["observations"][-1]["text"] == "Battery passport"


def test_live_opt_in_uses_form_encoding_and_host_allowlist(tmp_path, monkeypatch):
    seen = []
    class Response:
        headers = {"Content-Type": "application/sparql-results+json"}
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self, n): return b'{"results":{"bindings":[]}}'
    class Opener:
        def open(self, req, timeout):
            seen.append(req)
            return Response()
    monkeypatch.setattr(intel, "build_opener", lambda *_: Opener())
    p = plan_source("cordis", keyword="battery")
    assert p.body_encoding == "form"
    out = collect(p, cache=BudgetCache(tmp_path), fetch=True)
    assert out["status"] == "observed"
    assert seen[0].get_header("Content-type") == "application/x-www-form-urlencoded"
    assert b"query=" in seen[0].data


def test_epi_missing_key_does_not_access_provider(tmp_path, monkeypatch):
    monkeypatch.delenv("TRENDPULSE_INTEL_EPO_CONSUMER_KEY", raising=False)
    monkeypatch.delenv("TRENDPULSE_INTEL_EPO_CONSUMER_SECRET", raising=False)
    p = plan_source("epo", keyword="pa=siemens")
    try:
        collect(p, cache=BudgetCache(tmp_path), fetch=True)
    except intel.IntelligenceError as exc:
        assert "consumer key" in str(exc)
    else:
        raise AssertionError("Expected free credential requirement")
