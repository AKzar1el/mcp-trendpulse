"""Stable provider-error contract shared by Community and hosted TrendPulse surfaces."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any


class ProviderErrorCode(str, Enum):
    """Machine-readable classes of upstream provider failure."""

    TIMEOUT = "provider_timeout"
    RATE_LIMITED = "provider_rate_limited"
    UNAVAILABLE = "provider_unavailable"


class ProviderError(RuntimeError):
    """Base error for a failed upstream provider operation."""

    code = ProviderErrorCode.UNAVAILABLE
    retryable = True

    def __init__(self, provider: str, operation: str):
        self.provider = provider
        self.operation = operation
        super().__init__(self.public_message)

    @property
    def public_message(self) -> str:
        messages = {
            ProviderErrorCode.TIMEOUT: "The upstream provider timed out. Try again.",
            ProviderErrorCode.RATE_LIMITED: "The upstream provider is rate limiting requests. Try again later.",
            ProviderErrorCode.UNAVAILABLE: "The upstream provider is temporarily unavailable. Try again later.",
        }
        payload: dict[str, Any] = {
            "code": self.code.value,
            "provider": self.provider,
            "operation": self.operation,
            "retryable": self.retryable,
            "message": messages[self.code],
        }
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


class ProviderTimeoutError(ProviderError):
    code = ProviderErrorCode.TIMEOUT


class ProviderRateLimitError(ProviderError):
    code = ProviderErrorCode.RATE_LIMITED


class ProviderUnavailableError(ProviderError):
    code = ProviderErrorCode.UNAVAILABLE


def _status_code(exc: BaseException) -> int | None:
    response = getattr(exc, "response", None)
    candidates = (
        getattr(response, "status_code", None),
        getattr(response, "status", None),
        getattr(exc, "status_code", None),
        getattr(exc, "status", None),
    )
    for candidate in candidates:
        if isinstance(candidate, int):
            return candidate
    return None


def classify_provider_exception(exc: BaseException, *, provider: str, operation: str) -> ProviderError:
    """Translate provider/library exceptions into the stable TrendPulse error contract."""
    status = _status_code(exc)
    type_name = type(exc).__name__.lower()
    message = str(exc).lower()

    if status == 429 or "too many requests" in message or "rate limit" in message or "ratelimit" in type_name:
        return ProviderRateLimitError(provider, operation)

    if (
        status in {408, 504}
        or isinstance(exc, TimeoutError)
        or "timeout" in type_name
        or "timed out" in message
    ):
        return ProviderTimeoutError(provider, operation)

    return ProviderUnavailableError(provider, operation)
