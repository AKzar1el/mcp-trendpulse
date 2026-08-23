from __future__ import annotations

from fastmcp.server.auth import AuthProvider, RemoteAuthProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier
from pydantic import AnyHttpUrl

from mcp_trendpulse.config import CLERK_OAUTH_SCOPES, RemoteAuthSettings


def build_remote_auth_provider(settings: RemoteAuthSettings) -> AuthProvider | None:
    """Build the hosted MCP auth provider from explicit deployment settings."""
    if settings.mode == "disabled":
        return None
    if settings.mode != "clerk":
        raise ValueError(f"Unsupported remote auth mode: {settings.mode!r}")
    if not settings.issuer or not settings.jwks_uri or not settings.public_base_url:
        raise ValueError("Clerk auth settings are incomplete.")
    if not settings.audience:
        raise ValueError("Clerk OAuth audience is required.")

    verifier = JWTVerifier(
        jwks_uri=settings.jwks_uri,
        issuer=settings.issuer,
        audience=list(settings.audience),
        algorithm="RS256",
        required_scopes=["openid"],
        base_url=settings.public_base_url,
    )
    return RemoteAuthProvider(
        token_verifier=verifier,
        authorization_servers=[AnyHttpUrl(settings.issuer)],
        base_url=settings.public_base_url,
        scopes_supported=list(CLERK_OAUTH_SCOPES),
        resource_name="TrendPulse by DigestSEO",
    )
