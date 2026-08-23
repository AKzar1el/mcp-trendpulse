"""TrendPulse-specific FastMCP middleware."""

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware

from mcp_trendpulse.errors import ProviderError


class ProviderErrorMiddleware(Middleware):
    """Convert known provider failures into stable client-visible MCP tool errors."""

    async def on_call_tool(self, context, call_next):
        try:
            return await call_next(context)
        except ProviderError as exc:
            raise ToolError(exc.public_message) from exc
