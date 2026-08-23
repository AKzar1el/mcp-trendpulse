"""Minimal privacy-safe observability helpers for the hosted runtime."""

from __future__ import annotations

from contextvars import ContextVar, Token
from uuid import uuid4


_request_id: ContextVar[str | None] = ContextVar("trendpulse_request_id", default=None)


def new_request_id() -> str:
    """Generate an opaque server-side correlation identifier."""
    return uuid4().hex


def set_request_id(request_id: str) -> Token[str | None]:
    """Bind a correlation identifier to the current async request context."""
    return _request_id.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    """Restore the previous request correlation context."""
    _request_id.reset(token)


def get_request_id() -> str | None:
    """Return the active request identifier, if any."""
    return _request_id.get()
