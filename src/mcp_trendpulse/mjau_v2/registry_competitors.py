"""A01 proof: one-page, free, source-attributed official MCP Registry name search.

The official Registry searches *server names*, not descriptions or capabilities.
A match is a possible alternative to inspect, never proof of competition,
actual users, commercial traction, market share or product-market fit.
This module deliberately does not register an MCP tool or alter the core CLI.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import quote, urlencode

SOURCE_ID = "official_mcp_registry_v01"
BASE = "https://registry.modelcontextprotocol.io"
URL = BASE + "/v0.1/servers"
BUDGET_PER_DAY = 4
CACHE_TTL_SECONDS = 6 * 3600
MAX_RESPONSE_BYTES = 128 * 1024
MAX_SERVERS = 15
_META = "io.modelcontextprotocol.registry/official"
_NAME = re.compile(r"^[a-z0-9][a-z0-9_.-]{1,125}/[a-zA-Z0-9][a-zA-Z0-9_.-]{0,125}$")


class OversizedRegistryResponse(ValueError):
    """Reject rather than silently truncate oversized provider responses."""


def _query(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Registry search must be a string")
    value = value.strip()
    if not 3 <= len(value) <= 80 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError("Registry search requires 3–80 printable characters")
    return value


def _text(value: Any, maximum: int) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        return None
    return value.strip()[:maximum]


def _parse(payload: Any, limit: int) -> dict[str, Any]:
    """Fail closed on invalid envelopes; never turn malformed data into no_data."""
    if not isinstance(payload, dict):
        return {"status": "invalid_source_shape", "records": [], "source_rows_received": None}
    raw = payload.get("servers")
    meta = payload.get("metadata")
    if (not isinstance(raw, list) or len(raw) > limit or not isinstance(meta, dict)
            or type(meta.get("count")) is not int or meta["count"] != len(raw)):
        return {"status": "invalid_source_shape", "records": [], "source_rows_received": None}
    cursor = meta.get("nextCursor")
    if cursor is not None and (not isinstance(cursor, str) or len(cursor) > 512
                               or any(ord(ch) < 32 for ch in cursor)):
        return {"status": "invalid_source_shape", "records": [], "source_rows_received": None}
    if not raw and cursor:
        return {"status": "invalid_source_shape", "records": [], "source_rows_received": 0}
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    rejected = 0
    for item in raw:
        if not isinstance(item, dict):
            rejected += 1
            continue
        server = item.get("server")
        official = item.get("_meta", {}).get(_META) if isinstance(item.get("_meta"), dict) else None
        if not isinstance(server, dict) or not isinstance(official, dict):
            rejected += 1
            continue
        name, version = server.get("name"), server.get("version")
        if (not isinstance(name, str) or not _NAME.fullmatch(name)
                or not isinstance(version, str) or not 1 <= len(version) <= 64
                or any(ord(ch) < 33 or ord(ch) == 127 for ch in version)
                or official.get("isLatest") is not True
                or official.get("status") != "active" or name in seen):
            rejected += 1
            continue
        title = _text(server.get("title"), 120)
        description = _text(server.get("description"), 240)
        repository = server.get("repository")
        repo_url = None
        if isinstance(repository, dict) and repository.get("source") in {"github", "gitlab"}:
            candidate = repository.get("url")
            prefix = "https://github.com/" if repository["source"] == "github" else "https://gitlab.com/"
            if (isinstance(candidate, str) and candidate.startswith(prefix)
                    and len(candidate) <= 250 and not any(ch in candidate for ch in "?#@ \\")):
                repo_url = candidate
        records.append({
            "server_name": name, "version": version, "title": title,
            "description": description, "repository_url": repo_url,
            "source_detail_url": f"{URL}/{quote(name, safe='')}/versions/latest",
            "source_status": "active_latest_registry_entry",
        })
        seen.add(name)
    if raw and not records:
        return {"status": "invalid_source_shape", "records": [], "source_rows_received": len(raw),
                "source_rows_rejected": rejected}
    return {
        "status": ("no_data" if not raw else "observed_partial" if rejected or cursor else "observed"),
        "records": records, "source_rows_received": len(raw),
        "source_rows_rejected": rejected, "has_more_results": bool(cursor),
    }


def _fetch(url: str, params: dict[str, str]) -> tuple[int, Any]:
    """Exactly one fixed-host GET; no redirects, environment proxy or retry."""
    import requests

    if url != URL or set(params) != {"search", "version", "limit"} or params["version"] != "latest":
        raise ValueError("Unexpected registry request")
    session = requests.Session()
    session.trust_env = False
    try:
        with session.get(
            url, params=params, timeout=(4, 10), stream=True,
            allow_redirects=False, headers={
                "Accept": "application/json",
                "User-Agent": "mcp-trendpulse/0.2 (public metadata research; read only)",
            },
        ) as response:
            code = response.status_code
            if code != 200 or "json" not in response.headers.get("Content-Type", "").lower():
                return code, None
            raw = response.raw.read(MAX_RESPONSE_BYTES + 1, decode_content=True)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise OversizedRegistryResponse("Registry response over safety ceiling")
            try:
                return code, json.loads(raw)
            except (ValueError, UnicodeError):
                return code, None
    finally:
        session.close()


def _cache_key(query: str, limit: int) -> str:
    return "v2_registry_" + hashlib.sha256(json.dumps(
        [SOURCE_ID, query, limit, "latest", "first_page"], ensure_ascii=False,
    ).encode()).hexdigest()


def search_registry_competitors(
    *, query: str, limit: int = 8, execute: bool = False,
    cache: Any = None,
    fetcher: Callable[[str, dict[str, str]], tuple[int, Any]] | None = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Plan-only by default; optionally search one official latest-version page.

    A caller-supplied query is a hypothesis, not an independently observed
    customer phrase. Returned entries are registry catalog matches, not
    proven functionally comparable products. Follow-up review is mandatory.
    """
    query = _query(query)
    if type(limit) is not int or not 1 <= limit <= MAX_SERVERS:
        raise ValueError("Limit must be 1..15")
    if type(execute) is not bool:
        raise ValueError("Execute must be boolean")
    now = observed_at or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("Observed time must include timezone")
    now = now.astimezone(timezone.utc)
    params = {"search": query, "version": "latest", "limit": str(limit)}
    result: dict[str, Any] = {
        "source": SOURCE_ID, "source_url": URL, "query": query,
        "query_basis": "manual_server_name_substring_not_semantic_search",
        "market": "registry_catalog_global_not_country_sample",
        "status": "planned", "records": [], "limit": limit,
        "request_url": URL + "?" + urlencode(params),
        "observed_at": now.isoformat(), "requests_attempted": 0,
        "network_performed": False, "cache_hit": False,
        "source_rows_received": 0, "source_rows_rejected": 0,
        "has_more_results": None, "local_daily_cap": BUDGET_PER_DAY,
        "competition_verified": False, "customer_demand_verified": False,
        "semantically_relevant_to_user_problem_verified": False,
        "search_is_name_substring_only": True, "free_provider": True,
    }
    if not execute:
        return result
    try:
        if cache is None:
            from mcp_trendpulse.intelligence_core import BudgetCache
            cache = BudgetCache()
        key = _cache_key(query, limit)
        saved = cache.cached(key)
        if (isinstance(saved, dict) and saved.get("query") == query
                and saved.get("limit") == limit and saved.get("source") == SOURCE_ID
                and isinstance(saved.get("observed_at"), str)):
            try:
                old_when = datetime.fromisoformat(saved["observed_at"])
                if (old_when.utcoffset() is not None
                        and now - timedelta(hours=6) <= old_when.astimezone(timezone.utc) <= now):
                    old_payload = saved.get("provider_result")
                    normalized = _parse(old_payload, limit)
                    if normalized["status"] in {"observed", "observed_partial", "no_data"}:
                        result.update(normalized)
                        result["observed_at"] = old_when.astimezone(timezone.utc).isoformat()
                        result["cache_hit"] = True
                        return result
            except (TypeError, ValueError):
                pass
        if cache.blocked(SOURCE_ID):
            result.update(status="unavailable", reason="provider_cooldown")
            return result
        cache.reserve(SOURCE_ID, BUDGET_PER_DAY, guard_cooldown=True)
        result["requests_attempted"] = 1
        code, payload = (fetcher or _fetch)(URL, params)
        result["network_performed"] = True
        if code in (429, 503):
            cache.cool_down(SOURCE_ID, seconds=120)
            result.update(status="unavailable", reason=f"http_{code}")
            return result
        if code != 200:
            result.update(status="unavailable", reason="provider_response_error")
            return result
        normalized = _parse(payload, limit)
        result.update(normalized)
        if (normalized["status"] in {"observed", "observed_partial", "no_data"}
                and normalized["source_rows_rejected"] == 0):
            # Persist only validated fields; never hide discarded source rows on replay.
            sanitized = [{"server": {
                "name": r["server_name"], "version": r["version"],
                "title": r["title"], "description": r["description"],
                "repository": ({"source": "github" if r["repository_url"].startswith("https://github.com/") else "gitlab", "url": r["repository_url"]} if r["repository_url"] else None),
            }, "_meta": {_META: {"isLatest": True, "status": "active"}}} for r in normalized["records"]]
            cache.save(key, {
                "query": query, "limit": limit, "source": SOURCE_ID,
                "observed_at": now.isoformat(),
                "provider_result": {"servers": sanitized, "metadata": {
                    "count": len(sanitized), "nextCursor": "opaque" if normalized["has_more_results"] else None,
                }},
            }, ttl=CACHE_TTL_SECONDS)
        return result
    except Exception as exc:
        # Never serialize provider/transport/SQLite exception text (may contain
        # URLs or credentials); preserve quota/cooldown without false evidence.
        if isinstance(exc, OversizedRegistryResponse):
            result.update(status="invalid_source_shape", reason="response_oversized")
        elif type(exc).__name__ == "DailyBudgetExceeded":
            result.update(status="unavailable", reason="local_daily_budget_exceeded")
        elif type(exc).__name__ == "SourceCoolingDown":
            result.update(status="unavailable", reason="provider_cooldown")
        else:
            result.update(status="unavailable", reason="storage_or_network_unavailable")
        return result
