"""Authenticated client for optional DigestSEO project/Search Console context."""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from fastmcp.server.dependencies import get_http_headers


DEFAULT_DIGESTSEO_CONTEXT_URL = "https://digestseo.com/api/trendpulse/context"
MAX_CONTEXT_RESPONSE_BYTES = 256_000
MAX_ERROR_RESPONSE_BYTES = 32_000
CONTEXT_TIMEOUT_SECONDS = 12


@dataclass(frozen=True)
class DigestSeoContextError(RuntimeError):
    """Safe error raised when optional DigestSEO project context cannot be resolved."""

    message: str
    code: str = "digestseo_context_error"
    status: int | None = None

    def __str__(self) -> str:
        return self.message


class _NoRedirectHandler(HTTPRedirectHandler):
    """Do not follow redirects while carrying an end-user bearer token."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201
        return None


def get_digestseo_context_url(env: Mapping[str, str] | None = None) -> str:
    """Return the fixed HTTPS control-plane endpoint used for project enrichment."""
    source = os.environ if env is None else env
    value = source.get("TRENDPULSE_DIGESTSEO_CONTEXT_URL", DEFAULT_DIGESTSEO_CONTEXT_URL).strip()
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("TRENDPULSE_DIGESTSEO_CONTEXT_URL must be an absolute HTTPS URL.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError(
            "TRENDPULSE_DIGESTSEO_CONTEXT_URL must not include credentials, a query, or a fragment."
        )
    return value


def _current_bearer_header() -> str:
    headers = get_http_headers(include={"authorization"})
    authorization = headers.get("authorization", "").strip()
    if not authorization.lower().startswith("bearer ") or len(authorization) <= 7:
        raise DigestSeoContextError(
            "DigestSEO project context requires an authenticated hosted MCP request.",
            code="digestseo_auth_required",
            status=401,
        )
    return authorization


def _read_bounded(response, max_bytes: int) -> bytes:  # noqa: ANN001
    declared = response.headers.get("content-length")
    if declared:
        try:
            if int(declared) > max_bytes:
                raise DigestSeoContextError(
                    "DigestSEO returned a response larger than the allowed limit.",
                    code="digestseo_response_too_large",
                    status=502,
                )
        except ValueError:
            pass
    body = response.read(max_bytes + 1)
    if len(body) > max_bytes:
        raise DigestSeoContextError(
            "DigestSEO returned a response larger than the allowed limit.",
            code="digestseo_response_too_large",
            status=502,
        )
    return body


def _decode_json(body: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DigestSeoContextError(
            "DigestSEO returned an invalid context response.",
            code="digestseo_invalid_response",
            status=502,
        ) from exc
    if not isinstance(payload, dict):
        raise DigestSeoContextError(
            "DigestSEO returned an invalid context response.",
            code="digestseo_invalid_response",
            status=502,
        )
    return payload


def _open_no_redirects(request: Request, timeout: int):
    return build_opener(_NoRedirectHandler()).open(request, timeout=timeout)


def _http_error(error: HTTPError) -> DigestSeoContextError:
    try:
        body = error.read(MAX_ERROR_RESPONSE_BYTES + 1)
        payload = _decode_json(body[:MAX_ERROR_RESPONSE_BYTES]) if body else {}
    except DigestSeoContextError:
        payload = {}
    code = str(payload.get("error") or "digestseo_http_error")
    message = str(payload.get("message") or "DigestSEO could not resolve project context.")
    if error.code == 401:
        message = "DigestSEO did not accept the OAuth session. Reconnect the hosted integration."
    elif error.code == 403:
        message = "DigestSEO denied access to the requested project context."
    elif error.code == 404:
        message = "The requested DigestSEO project was not found for this account."
    elif 300 <= error.code < 400:
        message = "DigestSEO context redirects are not allowed while forwarding an OAuth bearer token."
        code = "digestseo_redirect_blocked"
    elif error.code >= 500:
        message = "DigestSEO project context is temporarily unavailable."
    return DigestSeoContextError(message, code=code, status=error.code)


def _post_context_sync(
    *,
    url: str,
    authorization: str,
    project_id: str,
    keywords: Sequence[str],
    days: int,
) -> dict[str, Any]:
    body = json.dumps(
        {
            "projectId": project_id,
            "keywords": list(keywords),
            "days": days,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    request = Request(
        url,
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Authorization": authorization,
            "Content-Type": "application/json",
            "User-Agent": "TrendPulse-DigestSEO-Context/1.0",
        },
    )
    try:
        with _open_no_redirects(request, CONTEXT_TIMEOUT_SECONDS) as response:
            return _decode_json(_read_bounded(response, MAX_CONTEXT_RESPONSE_BYTES))
    except HTTPError as exc:
        raise _http_error(exc) from exc
    except URLError as exc:
        raise DigestSeoContextError(
            "DigestSEO project context could not be reached.",
            code="digestseo_unavailable",
            status=503,
        ) from exc
    except TimeoutError as exc:
        raise DigestSeoContextError(
            "DigestSEO project context timed out.",
            code="digestseo_timeout",
            status=504,
        ) from exc


async def fetch_digestseo_project_context(
    *,
    project_id: str,
    keywords: Sequence[str],
    days: int = 28,
    authorization_header: str | None = None,
    context_url: str | None = None,
) -> dict[str, Any]:
    """Fetch bounded project/GSC context using the caller's existing Clerk bearer."""
    normalized_project_id = project_id.strip()
    if not normalized_project_id:
        raise ValueError("project_id must not be empty.")
    bounded_keywords = [str(keyword).strip() for keyword in keywords if str(keyword).strip()][:5]
    authorization = authorization_header or _current_bearer_header()
    url = context_url or get_digestseo_context_url()
    bounded_days = max(7, min(90, int(days)))
    return await asyncio.to_thread(
        _post_context_sync,
        url=url,
        authorization=authorization,
        project_id=normalized_project_id,
        keywords=bounded_keywords,
        days=bounded_days,
    )
