"""Dedicated remote ASGI entry point for TrendPulse Streamable HTTP."""

from __future__ import annotations

from mcp.server.transport_security import (
    TransportSecurityMiddleware,
    TransportSecuritySettings,
)
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from mcp_trendpulse.auth import build_remote_auth_provider
from mcp_trendpulse.config import (
    RemoteAuthSettings,
    RemoteHttpSettings,
    get_remote_auth_settings,
    get_remote_http_settings,
    load_environment,
)
from mcp_trendpulse.hosted import hosted_mcp


REMOTE_SERVICE_NAME = "trendpulse-by-digestseo"


class TrendPulseRemoteASGI:
    """Add health endpoints and DNS-rebinding protection around FastMCP HTTP."""

    def __init__(
        self,
        inner_app: ASGIApp,
        settings: RemoteHttpSettings,
        auth_settings: RemoteAuthSettings,
    ):
        self.inner_app = inner_app
        self.settings = settings
        self.auth_settings = auth_settings
        self.security = TransportSecurityMiddleware(
            TransportSecuritySettings(
                enable_dns_rebinding_protection=True,
                allowed_hosts=list(settings.allowed_hosts),
                allowed_origins=list(settings.allowed_origins),
            )
        )

    def _is_mcp_path(self, path: str) -> bool:
        if self.settings.path == "/":
            return path == "/"
        return path.rstrip("/") == self.settings.path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.inner_app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path == "/health":
            response = JSONResponse({"status": "ok", "service": REMOTE_SERVICE_NAME})
            await response(scope, receive, send)
            return

        if path == "/ready":
            response = JSONResponse(
                {
                    "status": "ready",
                    "service": REMOTE_SERVICE_NAME,
                    "transport": "streamable-http",
                    "stateless": True,
                    "auth": self.auth_settings.mode,
                }
            )
            await response(scope, receive, send)
            return

        if self._is_mcp_path(path):
            request = Request(scope, receive=receive)
            validation_error = await self.security.validate_request(
                request,
                is_post=scope.get("method") == "POST",
            )
            if validation_error is not None:
                await validation_error(scope, receive, send)
                return

        await self.inner_app(scope, receive, send)


def create_app(
    settings: RemoteHttpSettings | None = None,
    auth_settings: RemoteAuthSettings | None = None,
) -> TrendPulseRemoteASGI:
    """Create the stateless hosted MCP application without changing local stdio."""
    if settings is None or auth_settings is None:
        load_environment()
    if settings is None:
        settings = get_remote_http_settings()
    if auth_settings is None:
        auth_settings = get_remote_auth_settings()

    auth_provider = build_remote_auth_provider(auth_settings)
    previous_auth = hosted_mcp.auth
    hosted_mcp.auth = auth_provider
    try:
        mcp_app = hosted_mcp.http_app(
            path=settings.path,
            transport="streamable-http",
            stateless_http=True,
        )
    finally:
        hosted_mcp.auth = previous_auth

    mcp_app.state.trendpulse_sampling_enabled = False
    mcp_app.state.trendpulse_remote_settings = settings
    mcp_app.state.trendpulse_auth_settings = auth_settings
    return TrendPulseRemoteASGI(mcp_app, settings, auth_settings)


app = create_app()
