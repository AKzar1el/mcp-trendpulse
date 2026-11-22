"""Classify known transient upstream errors in explicitly live smoke tests.

A skipped live smoke is *not* a passed provider test. Do not classify unrelated
validation bugs, unsafe inputs, or MCP protocol failures as provider downtime.
"""
from __future__ import annotations

from contextlib import contextmanager
import json

from fastmcp.exceptions import ToolError
import pytest

from mcp_trendpulse.errors import ProviderError

_UPSTREAM_ERRORS = frozenset({
    "provider_timeout", "provider_rate_limited", "provider_unavailable",
})


def _classified_external_failure(exc: BaseException, provider: str) -> str | None:
    if isinstance(exc, ProviderError):
        if exc.provider == provider and exc.retryable:
            return exc.code.value
        return None
    if isinstance(exc, ToolError):
        raw = str(exc)
        marker = raw.find('{"code":')
        if marker == -1:
            return None
        try:
            receipt, _ = json.JSONDecoder().raw_decode(raw[marker:])
        except (ValueError, TypeError):
            return None
        if (isinstance(receipt, dict) and receipt.get("provider") == provider
                and receipt.get("code") in _UPSTREAM_ERRORS
                and receipt.get("retryable") is True):
            return receipt["code"]
    return None


@pytest.fixture
def external_source_available():
    @contextmanager
    def verified_source(provider: str):
        try:
            yield
        except (ProviderError, ToolError) as exc:
            category = _classified_external_failure(exc, provider)
            if category:
                pytest.skip(
                    f"Live upstream {provider} {category}; availability not proven"
                )
            raise
    return verified_source
