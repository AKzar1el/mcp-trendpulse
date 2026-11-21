"""Guarded, loopback-only transport for optional MJAU v3 HTTP diagnostics.

The usual stdio transport is unaffected. FastMCP 3.x intentionally leaves
HTTP Host/Origin protection opt-in; never expose a test server without it.
This helper does not register new tools or change the v1 server entrypoint.
"""

from __future__ import annotations

from typing import Any


def run_guarded_loopback_http(mcp: Any, *, port: int) -> None:
    """Run an existing MCP app with fixed local binding and strict headers.

    Authentication is still needed before any external/public HTTP deployment.
    This helper deliberately offers no host, origin or path override.
    """
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("Use a valid unprivileged localhost TCP port")
    mcp.run(
        transport="http",
        host="127.0.0.1",
        port=port,
        path="/mcp",
        show_banner=False,
        host_origin_protection=True,
        allowed_hosts=["127.0.0.1", "localhost"],
        allowed_origins=["http://127.0.0.1", "http://localhost"],
    )
