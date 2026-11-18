"""Test all six previously placeholder source integrations offline."""

import json
from urllib.parse import parse_qs, urlsplit

import pytest

from mcp_trendpulse.intelligence_core import IntelligenceError, plan_source, source_catalog
from mcp_trendpulse.intelligence_extended import epo_oauth_token


def test_all_reclassified_sources_have_real_plan():
    catalog = {x["id"]: x for x in source_catalog()}
    for name in ("cfpb", "cordis", "copernicus", "epo", "opsi_slovenia"):
        assert catalog[name]["fetch_enabled"] is True
    assert plan_source("cfpb", keyword="credit cards").method == "GET"
    assert plan_source("cordis", keyword="battery recycling").body_encoding == "form"
    assert plan_source("copernicus", keyword="sentinel").url.startswith("https://")
    assert plan_source("epo", keyword="pa=siemens").content_type == "xml"
    assert "package_search" in plan_source("opsi_slovenia", keyword="energija").url


def test_cfpb_not_export_mode_and_cordis_graph_scoped():
    cfpb = plan_source("cfpb", keyword="late fee", limit=2)
    opts = parse_qs(urlsplit(cfpb.url).query)
    assert opts["size"] == ["2"]
    assert "format" not in opts  # CSV export ignores pagination.
    cordis = plan_source("cordis", keyword="battery")
    assert "http://data.europa.eu/s66/graph/projects" in cordis.body["query"]


def test_changedetection_local_requires_opt_in():
    with pytest.raises(IntelligenceError):
        plan_source("changedetection_local", env={})
    p = plan_source("changedetection_local",
        env={"TRENDPULSE_INTEL_CHANGEDETECTION_KEY": "test-only-token"})
    assert p.url == "http://127.0.0.1:5000/api/v1/watch"
    assert p.allow_loopback
    assert p.public()["headers"] == {"x-api-key": "<configured>"}


def test_epo_oauth_without_credentials_fails_closed():
    with pytest.raises(IntelligenceError, match="consumer key"):
        epo_oauth_token({}, None)


def test_epo_oauth_parses_response_and_never_logs_secrets():
    class Response:
        headers = {"Content-Type": "application/json"}
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self, n): return json.dumps({"access_token": "fake123456789"}).encode()
    class Opener:
        def open(self, request, timeout):
            assert request.full_url == "https://ops.epo.org/3.2/auth/accesstoken"
            assert request.get_header("Authorization").startswith("Basic ")
            return Response()
    assert epo_oauth_token({
        "TRENDPULSE_INTEL_EPO_CONSUMER_KEY": "test-key",
        "TRENDPULSE_INTEL_EPO_CONSUMER_SECRET": "test-secret",
    }, Opener()) == "fake123456789"


def test_bad_epo_expressions_refused():
    with pytest.raises(IntelligenceError):
        plan_source("epo", keyword="search?q=ok&token=exposed")
