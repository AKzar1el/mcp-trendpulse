"""Offline tests for Wave 3; no electricity service, data portal, or RSSHub calls."""

import pytest
from mcp_trendpulse.intelligence_core import IntelligenceError, plan_source, source_catalog


def test_catalog_covers_three_waves():
    sources = source_catalog()
    assert {s["wave"] for s in sources} == {1, 2, 3}
    assert len(sources) >= 20
    assert {s["id"] for s in sources} >= {"ted", "openalex", "gleif", "ecb", "entsoe", "rsshub_local"}


def test_gleif_public_no_key():
    p = plan_source("gleif", keyword="Example Holdings")
    assert p.method == "GET"
    assert "api.gleif.org" in p.url
    assert "Example+Holdings" in p.url


def test_ecb_only_specific_series_and_recent_points():
    p = plan_source("ecb", identifier="EXR/D.USD.EUR.SP00.A")
    assert p.content_type == "csv"
    assert "lastNObservations=10" in p.url
    with pytest.raises(IntelligenceError):
        plan_source("ecb", identifier="EXR")


def test_entsoe_free_token_not_in_url():
    with pytest.raises(IntelligenceError):
        plan_source("entsoe", identifier="10Y1001A1001A83F", env={})
    p = plan_source(
        "entsoe", identifier="10Y1001A1001A83F",
        env={"TRENDPULSE_INTEL_ENTSOE_TOKEN": "FAKE_OFFLINE_TOKEN"},
    )
    assert p.content_type == "xml"
    assert "FAKE_OFFLINE_TOKEN" not in p.url
    assert p.public()["headers"]["SECURITY_TOKEN"] == "<configured>"


def test_local_rsshub_only_known_local_origin():
    p = plan_source("rsshub_local", identifier="github/trending/daily")
    assert p.url == "http://127.0.0.1:1200/github/trending/daily"
    with pytest.raises(IntelligenceError):
        plan_source("rsshub_local", identifier="../../private")
    with pytest.raises(IntelligenceError):
        plan_source("rsshub_local", identifier="http://evil.example/x")


def test_extended_sources_are_planned_without_credentials_for_public_ones():
    assert plan_source("copernicus").method == "GET"
    assert plan_source("epo", keyword="pa=siemens").method == "GET"
    assert plan_source("opsi_slovenia", keyword="energy").method == "GET"
    with pytest.raises(IntelligenceError, match="API key"):
        plan_source("changedetection_local", env={})
