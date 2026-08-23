"""TrendPulse-specific FastMCP middleware."""

import logging

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware

from mcp_trendpulse.errors import ProviderError
from mcp_trendpulse.observability import get_request_id


logger = logging.getLogger(__name__)


class ProviderErrorMiddleware(Middleware):
    """Convert known provider failures into stable client-visible MCP tool errors."""

    async def on_call_tool(self, context, call_next):
        try:
            return await call_next(context)
        except ProviderError as exc:
            logger.warning(
                "provider_failure request_id=%s provider=%s operation=%s code=%s retryable=%s",
                get_request_id() or "-",
                exc.provider,
                exc.operation,
                exc.code.value,
                exc.retryable,
            )
            raise ToolError(exc.public_message) from exc
