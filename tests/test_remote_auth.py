import json

import pytest
from fastmcp.server.auth import RemoteAuthProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier, RSAKeyPair
from mcp.types import LATEST_PROTOCOL_VERSION
from pydantic import AnyHttpUrl
from starlette.testclient import TestClient

import mcp_trendpulse.asgi as asgi_module
from mcp_trendpulse.asgi import create_app
from mcp_trendpulse.auth import build_remote_auth_provider
from mcp_trendpulse.config import (
    CLERK_OAUTH_SCOPES,
    RemoteAuthSettings,
    RemoteHttpSettings,
    get_remote_auth_settings,
)


ISSUER = "https://issuer.example.test"
PUBLIC_BASE_URL = "https://allowed.test"
AUDIENCE = "trendpulse-client"


def remote_http_settings() -> RemoteHttpSettings:
    return RemoteHttpSettings(
        path="/mcp",
        allowed_hosts=("allowed.test",),
        allowed_origins=("https://allowed.test",),
    )


def clerk_settings() -> RemoteAuthSettings:
    return RemoteAuthSettings(
        mode="clerk",
        issuer=ISSUER,
        jwks_uri=f"{ISSUER}/.well-known/jwks.json",
        audience=(AUDIENCE,),
        public_base_url=PUBLIC_BASE_URL,
    )


def initialize_payload() -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": LATEST_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "oauth-test", "version": "1.0"},
        },
    }


def decode_initialize_response(response) -> dict:
    content_type = response.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        return response.json()
    assert content_type.startswith("text/event-stream")
    data_lines = [
        line.removeprefix("data: ")
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert data_lines
    return json.loads(data_lines[-1])


def static_remote_auth(key_pair: RSAKeyPair) -> RemoteAuthProvider:
    verifier = JWTVerifier(
        public_key=key_pair.public_key,
        issuer=ISSUER,
        audience=AUDIENCE,
        algorithm="RS256",
        required_scopes=["openid"],
        base_url=PUBLIC_BASE_URL,
    )
    return RemoteAuthProvider(
        token_verifier=verifier,
        authorization_servers=[AnyHttpUrl(ISSUER)],
        base_url=PUBLIC_BASE_URL,
        scopes_supported=list(CLERK_OAUTH_SCOPES),
        resource_name="TrendPulse by DigestSEO",
    )


def test_remote_auth_settings_default_disabled_for_local_development():
    assert get_remote_auth_settings({}) == RemoteAuthSettings(mode="disabled")


def test_remote_auth_settings_require_complete_https_clerk_configuration():
    complete = get_remote_auth_settings(
        {
            "TRENDPULSE_AUTH_MODE": "clerk",
            "TRENDPULSE_CLERK_ISSUER": "https://clerk.example.test/",
            "TRENDPULSE_PUBLIC_BASE_URL": "https://trendpulse.example.test/",
            "TRENDPULSE_CLERK_AUDIENCE": "client-a, client-b",
        }
    )
    assert complete.mode == "clerk"
    assert complete.issuer == "https://clerk.example.test"
    assert complete.jwks_uri == "https://clerk.example.test/.well-known/jwks.json"
    assert complete.public_base_url == "https://trendpulse.example.test"
    assert complete.audience == ("client-a", "client-b")

    with pytest.raises(ValueError, match="AUTH_MODE"):
        get_remote_auth_settings({"TRENDPULSE_AUTH_MODE": "maybe"})
    with pytest.raises(ValueError, match="CLERK_ISSUER"):
        get_remote_auth_settings(
            {
                "TRENDPULSE_AUTH_MODE": "clerk",
                "TRENDPULSE_PUBLIC_BASE_URL": "https://trendpulse.example.test",
                "TRENDPULSE_CLERK_AUDIENCE": "client-a",
            }
        )
    with pytest.raises(ValueError, match="PUBLIC_BASE_URL"):
        get_remote_auth_settings(
            {
                "TRENDPULSE_AUTH_MODE": "clerk",
                "TRENDPULSE_CLERK_ISSUER": "https://clerk.example.test",
                "TRENDPULSE_CLERK_AUDIENCE": "client-a",
            }
        )
    with pytest.raises(ValueError, match="absolute HTTPS"):
        get_remote_auth_settings(
            {
                "TRENDPULSE_AUTH_MODE": "clerk",
                "TRENDPULSE_CLERK_ISSUER": "http://clerk.example.test",
                "TRENDPULSE_PUBLIC_BASE_URL": "https://trendpulse.example.test",
                "TRENDPULSE_CLERK_AUDIENCE": "client-a",
            }
        )
    with pytest.raises(ValueError, match="without a path"):
        get_remote_auth_settings(
            {
                "TRENDPULSE_AUTH_MODE": "clerk",
                "TRENDPULSE_CLERK_ISSUER": "https://clerk.example.test",
                "TRENDPULSE_PUBLIC_BASE_URL": "https://trendpulse.example.test/mcp",
                "TRENDPULSE_CLERK_AUDIENCE": "client-a",
            }
        )
    with pytest.raises(ValueError, match="AUDIENCE"):
        get_remote_auth_settings(
            {
                "TRENDPULSE_AUTH_MODE": "clerk",
                "TRENDPULSE_CLERK_ISSUER": "https://clerk.example.test",
                "TRENDPULSE_PUBLIC_BASE_URL": "https://trendpulse.example.test",
            }
        )


def test_build_remote_auth_provider_uses_clerk_jwt_contract():
    provider = build_remote_auth_provider(clerk_settings())
    assert isinstance(provider, RemoteAuthProvider)
    assert [str(url).rstrip("/") for url in provider.authorization_servers] == [ISSUER]
    assert provider.required_scopes == ["openid"]
    verifier = provider.token_verifier
    assert isinstance(verifier, JWTVerifier)
    assert verifier.issuer == ISSUER
    assert verifier.audience == [AUDIENCE]
    assert verifier.jwks_uri == f"{ISSUER}/.well-known/jwks.json"
    assert verifier.algorithm == "RS256"


def test_clerk_mode_publishes_protected_resource_metadata_and_requires_bearer(monkeypatch):
    key_pair = RSAKeyPair.generate()
    provider = static_remote_auth(key_pair)
    monkeypatch.setattr(asgi_module, "build_remote_auth_provider", lambda _: provider)
    app = create_app(remote_http_settings(), clerk_settings())

    with TestClient(app, base_url=PUBLIC_BASE_URL) as client:
        metadata = client.get("/.well-known/oauth-protected-resource/mcp")
        unauthenticated = client.post(
            "/mcp",
            json=initialize_payload(),
            headers={"accept": "application/json, text/event-stream"},
        )

    assert metadata.status_code == 200
    payload = metadata.json()
    assert payload["resource"] == f"{PUBLIC_BASE_URL}/mcp"
    assert payload["authorization_servers"] == [f"{ISSUER}/"]
    assert set(CLERK_OAUTH_SCOPES).issubset(set(payload["scopes_supported"]))

    assert unauthenticated.status_code == 401
    challenge = unauthenticated.headers.get("www-authenticate", "")
    assert challenge.startswith("Bearer")
    assert "resource_metadata=" in challenge


def test_clerk_mode_accepts_correct_signed_audienced_scoped_token(monkeypatch):
    key_pair = RSAKeyPair.generate()
    provider = static_remote_auth(key_pair)
    monkeypatch.setattr(asgi_module, "build_remote_auth_provider", lambda _: provider)
    app = create_app(remote_http_settings(), clerk_settings())
    token = key_pair.create_token(
        subject="user_test",
        issuer=ISSUER,
        audience=AUDIENCE,
        scopes=["openid", "profile"],
        additional_claims={"client_id": AUDIENCE},
    )

    with TestClient(app, base_url=PUBLIC_BASE_URL) as client:
        response = client.post(
            "/mcp",
            json=initialize_payload(),
            headers={
                "accept": "application/json, text/event-stream",
                "authorization": f"Bearer {token}",
            },
        )

    assert response.status_code == 200
    payload = decode_initialize_response(response)
    assert payload["id"] == 1
    assert payload["result"]["serverInfo"]["name"] == "trendpulse-by-digestseo"


def test_clerk_mode_rejects_wrong_audience_and_missing_scope(monkeypatch):
    key_pair = RSAKeyPair.generate()
    provider = static_remote_auth(key_pair)
    monkeypatch.setattr(asgi_module, "build_remote_auth_provider", lambda _: provider)
    app = create_app(remote_http_settings(), clerk_settings())

    wrong_audience = key_pair.create_token(
        subject="user_test",
        issuer=ISSUER,
        audience="other-client",
        scopes=["openid"],
        additional_claims={"client_id": "other-client"},
    )
    missing_scope = key_pair.create_token(
        subject="user_test",
        issuer=ISSUER,
        audience=AUDIENCE,
        scopes=["profile"],
        additional_claims={"client_id": AUDIENCE},
    )

    with TestClient(app, base_url=PUBLIC_BASE_URL) as client:
        audience_response = client.post(
            "/mcp",
            json=initialize_payload(),
            headers={
                "accept": "application/json, text/event-stream",
                "authorization": f"Bearer {wrong_audience}",
            },
        )
        scope_response = client.post(
            "/mcp",
            json=initialize_payload(),
            headers={
                "accept": "application/json, text/event-stream",
                "authorization": f"Bearer {missing_scope}",
            },
        )

    assert audience_response.status_code == 401
    assert scope_response.status_code == 401
