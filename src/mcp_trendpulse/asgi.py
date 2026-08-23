"""Dedicated remote ASGI entry point for TrendPulse Streamable HTTP."""

from __future__ import annotations

import logging
from time import perf_counter

from mcp.server.transport_security import (
    TransportSecurityMiddleware,
    TransportSecuritySettings,
)
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from mcp_trendpulse.auth import build_remote_auth_provider
from mcp_trendpulse.config import (
    RemoteAuthSettings,
    RemoteHttpSettings,
    get_remote_auth_settings,
    get_remote_http_settings,
    load_environment,
)
from mcp_trendpulse.hosted import hosted_mcp
from mcp_trendpulse.observability import (
    new_request_id,
    reset_request_id,
    set_request_id,
)


logger = logging.getLogger(__name__)
REMOTE_SERVICE_NAME = "trendpulse-by-digestseo"


class TrendPulseRemoteASGI:
    """Add health endpoints, request telemetry, and DNS-rebinding protection."""

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
        request_id = new_request_id()
        request_token = set_request_id(request_id)
        started = perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = list(message.get("headers", []))
                if not any(name.lower() == b"x-request-id" for name, _ in headers):
                    headers.append((b"x-request-id", request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            if path == "/health":
                response = JSONResponse({"status": "ok", "service": REMOTE_SERVICE_NAME})
                await response(scope, receive, send_with_request_id)
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
                await response(scope, receive, send_with_request_id)
                return

            if self._is_mcp_path(path):
                request = Request(scope, receive=receive)
                validation_error = await self.security.validate_request(
                    request,
                    is_post=scope.get("method") == "POST",
                )
                if validation_error is not None:
                    await validation_error(scope, receive, send_with_request_id)
                    return

            await self.inner_app(scope, receive, send_with_request_id)
        finally:
            if self._is_mcp_path(path):
                logger.info(
                    "mcp_http_request request_id=%s method=%s status=%s duration_ms=%.1f auth=%s",
                    request_id,
                    scope.get("method", ""),
                    status_code,
                    (perf_counter() - started) * 1000,
                    self.auth_settings.mode,
                )
            reset_request_id(request_token)


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
