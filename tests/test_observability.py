import logging

import pytest
from fastmcp.exceptions import ToolError

from mcp_trendpulse.errors import ProviderTimeoutError
from mcp_trendpulse.middleware import ProviderErrorMiddleware
from mcp_trendpulse.observability import reset_request_id, set_request_id


@pytest.mark.asyncio
async def test_provider_failure_log_contains_only_operational_fields(caplog):
    middleware = ProviderErrorMiddleware()
    request_id = "a" * 32
    secret = "sensitive-keyword-that-must-not-be-logged"

    async def fail(_context):
        raise ProviderTimeoutError("google_trends", "interest_over_time")

    token = set_request_id(request_id)
    try:
        with caplog.at_level(logging.WARNING, logger="mcp_trendpulse.middleware"):
            with pytest.raises(ToolError):
                await middleware.on_call_tool(secret, fail)
    finally:
        reset_request_id(token)

    records = [
        record.getMessage()
        for record in caplog.records
        if "provider_failure" in record.getMessage()
    ]
    assert records == [
        "provider_failure "
        f"request_id={request_id} "
        "provider=google_trends "
        "operation=interest_over_time "
        "code=provider_timeout "
        "retryable=True"
    ]
    assert secret not in records[0]
