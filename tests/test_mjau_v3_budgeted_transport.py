"""Outbound HTTP threat-model tests for the optional budgeted A04/A10 source gate.

Never opens a network connection. All provider responses are fabricated locally.
"""

from __future__ import annotations

import json

import pytest

from mcp_trendpulse.intelligence_core import IntelligenceError
from mcp_trendpulse.mjau_v3 import budgeted_sources as budgeted
from mcp_trendpulse.mjau_v3.wikidata import plan_qid_lookup


class Response:
    def __init__(self, data: bytes, *, status: int = 200, mime: str = "application/json"):
        self.data = data
        self.status = status
        self.headers = {"Content-Type": mime}

    def read(self, size: int):
        return self.data[:size]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class Opener:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def open(self, req, *, timeout):
        self.requests.append((req, timeout))
        return self.response


def _fake(monkeypatch, raw: bytes, **kwargs):
    opener = Opener(Response(raw, **kwargs))
    monkeypatch.setattr(budgeted, "build_opener", lambda *_args: opener)
    return opener


@pytest.mark.parametrize("url, method, body", [
    ("http://api.osv.dev/v1/querybatch", "POST", {"queries": []}),
    ("https://evil.invalid/v1/querybatch", "POST", {"queries": []}),
    ("https://api.osv.dev.evil.invalid/v1/querybatch", "POST", {"queries": []}),
    ("https://api.osv.dev:8080/v1/querybatch", "POST", {"queries": []}),
    ("https://user:pass@api.osv.dev/v1/querybatch", "POST", {"queries": []}),
    ("https://api.osv.dev/v1/query", "POST", {"queries": []}),
    ("https://api.osv.dev/v1/querybatch#fragment", "POST", {"queries": []}),
    ("https://www.wikidata.org.evil.invalid/w/api.php", "GET", None),
    ("https://www.wikidata.org/w/index.php", "GET", None),
    ("https://www.wikidata.org/w/api.php", "POST", {"x": 1}),
])
def test_fixed_origin_and_path_reject_untrusted_destinations(
    monkeypatch, url, method, body,
):
    opener = _fake(monkeypatch, b"{}")
    with pytest.raises(IntelligenceError, match="Unapproved"):
        budgeted._request_json(url=url, method=method, body=body)
    assert not opener.requests


def test_wikimedia_contact_header_and_single_no_redirect_opener(monkeypatch):
    opener = _fake(monkeypatch, b'{"success":1,"entities":{}}')
    source = budgeted._request_json(
        url=plan_qid_lookup(["Q64"], ["en"])["url"],
        method="GET", body=None,
    )
    assert source["success"] == 1
    assert len(opener.requests) == 1
    request, timeout = opener.requests[0]
    assert timeout == 8
    assert request.get_method() == "GET"
    assert "github.com/AKzar1el/mcp-trendpulse/issues" in request.get_header("User-agent")
    assert "json" in request.get_header("Accept").lower()


def test_osv_has_single_post_with_no_secret_headers(monkeypatch):
    opener = _fake(monkeypatch, b'{"results":[{}]}')
    body = {
        "queries": [{"package": {"ecosystem": "PyPI", "name": "Django"},
                     "version": "2.2.0"}]
    }
    assert budgeted._request_json(
        url="https://api.osv.dev/v1/querybatch", method="POST", body=body,
    ) == {"results": [{}]}
    assert len(opener.requests) == 1
    request, timeout = opener.requests[0]
    assert timeout == 8
    assert request.get_method() == "POST"
    assert json.loads(request.data) == body
    assert "Authorization" not in request.headers
    assert "Cookie" not in request.headers


def test_osv_two_query_batch_must_be_denied_at_http_boundary(monkeypatch):
    opener = _fake(monkeypatch, b'{"results":[{},{}]}')
    package = {"ecosystem": "PyPI", "name": "Django"}
    body = {
        "queries": [
            {"package": package, "version": "2.2.0"},
            {"package": package, "version": "2.2.1"},
        ],
    }
    with pytest.raises(IntelligenceError, match="Unapproved"):
        budgeted._request_json(
            url="https://api.osv.dev/v1/querybatch", method="POST", body=body,
        )
    assert opener.requests == []


def test_wikidata_arbitrary_action_must_be_denied_at_http_boundary(monkeypatch):
    opener = _fake(monkeypatch, b'{"query":{}}')
    with pytest.raises(IntelligenceError, match="Unapproved"):
        budgeted._request_json(
            url="https://www.wikidata.org/w/api.php?action=query&meta=siteinfo",
            method="GET", body=None,
        )
    assert opener.requests == []


@pytest.mark.parametrize("payload,mime,exc", [
    (b"<html>bad gateway</html>", "text/html", IntelligenceError),
    (b"{" + b" " * 192_000 + b"}", "application/json", IntelligenceError),
    (b'{"results":[],"results":[]}', "application/json", ValueError),
    (b'{"results":[NaN]}', "application/json", ValueError),
    (b"\xff", "application/json", UnicodeDecodeError),
], ids=["html", "oversized-192kb", "duplicate-json-key", "nonfinite-json", "invalid-utf8"])
def test_invalid_mime_oversized_duplicate_json_or_encoding_fails_closed(
    monkeypatch, payload, mime, exc,
):
    _fake(monkeypatch, payload, mime=mime)
    with pytest.raises(exc):
        budgeted._request_json(
            url="https://api.osv.dev/v1/querybatch", method="POST",
            body={
                "queries": [{"package": {"ecosystem": "PyPI", "name": "Django"},
                             "version": "2.2.0"}],
            },
        )


def test_no_automatic_redirects_are_possible():
    handler = budgeted._NoRedirect()
    assert handler.redirect_request(None, None, 302, "Moved", {}, "https://evil.invalid") is None
