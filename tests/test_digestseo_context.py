import json
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from mcp_trendpulse import digestseo


class FakeResponse:
    def __init__(self, payload, *, headers=None):
        self.body = json.dumps(payload).encode("utf-8")
        self.headers = headers or {"content-length": str(len(self.body))}

    def read(self, size=-1):
        return self.body if size < 0 else self.body[:size]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_digestseo_context_url_requires_https_and_rejects_credential_like_parts():
    assert digestseo.get_digestseo_context_url({}) == digestseo.DEFAULT_DIGESTSEO_CONTEXT_URL
    assert (
        digestseo.get_digestseo_context_url(
            {"TRENDPULSE_DIGESTSEO_CONTEXT_URL": "https://staging.example.test/context"}
        )
        == "https://staging.example.test/context"
    )

    with pytest.raises(ValueError, match="absolute HTTPS"):
        digestseo.get_digestseo_context_url(
            {"TRENDPULSE_DIGESTSEO_CONTEXT_URL": "http://digestseo.com/api/trendpulse/context"}
        )
    with pytest.raises(ValueError, match="must not include"):
        digestseo.get_digestseo_context_url(
            {"TRENDPULSE_DIGESTSEO_CONTEXT_URL": "https://user@digestseo.com/api/trendpulse/context"}
        )
    with pytest.raises(ValueError, match="must not include"):
        digestseo.get_digestseo_context_url(
            {"TRENDPULSE_DIGESTSEO_CONTEXT_URL": "https://digestseo.com/api/trendpulse/context?next=x"}
        )


def test_current_bearer_header_requires_authenticated_http_context(monkeypatch):
    monkeypatch.setattr(digestseo, "get_http_headers", lambda **_: {})
    with pytest.raises(digestseo.DigestSeoContextError, match="authenticated hosted MCP") as exc:
        digestseo._current_bearer_header()
    assert exc.value.code == "digestseo_auth_required"
    assert exc.value.status == 401

    monkeypatch.setattr(
        digestseo,
        "get_http_headers",
        lambda **_: {"authorization": "Bearer clerk-oauth-token"},
    )
    assert digestseo._current_bearer_header() == "Bearer clerk-oauth-token"


@pytest.mark.asyncio
async def test_context_client_forwards_bearer_only_as_header_and_bounds_payload(monkeypatch):
    captured = {}
    payload = {
        "project": {"id": "project_1", "name": "Example", "origin": "https://example.com"},
        "gsc": {"available": True, "metrics": []},
    }

    def fake_open(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        captured["content_type"] = request.get_header("Content-type")
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse(payload)

    monkeypatch.setattr(digestseo, "_open_no_redirects", fake_open)
    result = await digestseo.fetch_digestseo_project_context(
        project_id="project_1",
        keywords=[f"keyword {index}" for index in range(8)],
        days=200,
        authorization_header="Bearer secret-clerk-token",
        context_url="https://digestseo.example.test/api/trendpulse/context",
    )

    assert result == payload
    assert captured["url"] == "https://digestseo.example.test/api/trendpulse/context"
    assert captured["authorization"] == "Bearer secret-clerk-token"
    assert captured["content_type"] == "application/json"
    assert captured["body"] == {
        "projectId": "project_1",
        "keywords": [f"keyword {index}" for index in range(5)],
        "days": 90,
    }
    assert "secret-clerk-token" not in json.dumps(captured["body"])
    assert captured["timeout"] == digestseo.CONTEXT_TIMEOUT_SECONDS


def test_context_client_blocks_redirects_instead_of_forwarding_bearer(monkeypatch):
    error_body = json.dumps({"error": "redirect", "message": "Moved"}).encode("utf-8")

    def fake_open(request, timeout):
        raise HTTPError(
            request.full_url,
            302,
            "Found",
            {"location": "https://evil.example.test/context"},
            SimpleNamespace(read=lambda size=-1: error_body),
        )

    monkeypatch.setattr(digestseo, "_open_no_redirects", fake_open)
    with pytest.raises(digestseo.DigestSeoContextError, match="redirects are not allowed") as exc:
        digestseo._post_context_sync(
            url="https://digestseo.example.test/api/trendpulse/context",
            authorization="Bearer secret",
            project_id="project_1",
            keywords=["seo"],
            days=28,
        )
    assert exc.value.code == "digestseo_redirect_blocked"
    assert exc.value.status == 302


def test_context_client_bounds_response_size(monkeypatch):
    oversized = b"x" * (digestseo.MAX_CONTEXT_RESPONSE_BYTES + 1)

    class OversizedResponse:
        headers = {}

        def read(self, size=-1):
            return oversized if size < 0 else oversized[:size]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(digestseo, "_open_no_redirects", lambda request, timeout: OversizedResponse())
    with pytest.raises(digestseo.DigestSeoContextError, match="larger than the allowed limit") as exc:
        digestseo._post_context_sync(
            url="https://digestseo.example.test/api/trendpulse/context",
            authorization="Bearer secret",
            project_id="project_1",
            keywords=["seo"],
            days=28,
        )
    assert exc.value.code == "digestseo_response_too_large"


def test_context_client_maps_project_not_found_without_echoing_remote_details(monkeypatch):
    body = json.dumps({"error": "project_not_found", "message": "internal project detail"}).encode("utf-8")

    def fake_open(request, timeout):
        raise HTTPError(
            request.full_url,
            404,
            "Not Found",
            {},
            SimpleNamespace(read=lambda size=-1: body),
        )

    monkeypatch.setattr(digestseo, "_open_no_redirects", fake_open)
    with pytest.raises(digestseo.DigestSeoContextError, match="not found for this account") as exc:
        digestseo._post_context_sync(
            url="https://digestseo.example.test/api/trendpulse/context",
            authorization="Bearer secret",
            project_id="project_1",
            keywords=["seo"],
            days=28,
        )
    assert exc.value.code == "project_not_found"
    assert exc.value.status == 404
    assert "internal project detail" not in str(exc.value)
