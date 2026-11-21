"""A03: opt-in, bounded deps.dev resolved package dependency evidence.

Source observations concern one package version and one generic Linux resolver
scenario, NOT installations, downloads, dependents, market share or users.
No shared CLI/MCP registration, scheduled jobs, paid keys, or implicit network.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import quote

BASE = "https://api.deps.dev"
SOURCE = "depsdev_v3_resolved_dependencies"
SYSTEMS = frozenset({"NPM", "PYPI", "CARGO", "MAVEN"})
DAILY_CAP = 4
TTL_SECONDS = 12 * 3600
MAX_BYTES = 128 * 1024
MAX_NODES = 512
MAX_EDGES = 2048
MAX_PREVIEW = 12

_NAME = re.compile(r"^[A-Za-z0-9@._:/+-]{1,160}$")
_VERSION = re.compile(r"^[A-Za-z0-9._+-]{1,100}$")
_KEY_NAME = re.compile(r"^[\x20-\x7e]{1,300}$")
_KEY_VERSION = re.compile(r"^[\x20-\x7e]{1,160}$")


class ResponseTooLarge(ValueError):
    """The API response cannot safely be interpreted under local limits."""


def _identifiers(system: Any, package: Any, version: Any) -> tuple[str, str, str]:
    if not isinstance(system, str) or system.upper() not in SYSTEMS:
        raise ValueError("Resolved graphs only available for npm, pypi, cargo and maven")
    if (not isinstance(package, str) or not _NAME.fullmatch(package)
            or package in {".", ".."} or "//" in package or "/../" in package):
        raise ValueError("Invalid scoped package identifier")
    if (not isinstance(version, str) or not _VERSION.fullmatch(version)
            or version in {".", ".."} or ".." in version):
        raise ValueError("Invalid concrete package version")
    return system.upper(), package, version


def _url(system: str, package: str, version: str) -> str:
    return (f"{BASE}/v3/systems/{system.lower()}/packages/"
            f"{quote(package, safe='')}/versions/{quote(version, safe='')}:dependencies")


def _key(system: str, package: str, version: str) -> str:
    return "mjau_v2_depsdev_v3_" + hashlib.sha256(json.dumps(
        [SOURCE, system, package, version, "resolved_graph_1"],
        separators=(",", ":")).encode()).hexdigest()


def _equivalent_name(a: str, b: str, system: str) -> bool:
    """Ecosystem-canonical names: PEP 503 in PyPI, case for npm/cargo."""
    if system == "PYPI":
        return re.sub(r"[-_.]+", "-", a).lower() == re.sub(r"[-_.]+", "-", b).lower()
    if system in {"NPM", "CARGO"}:
        return a.casefold() == b.casefold()
    return a == b


def _parse_graph(value: Any, *, system: str, package: str,
                 version: str, limit: int = MAX_PREVIEW) -> dict[str, Any]:
    """Fail closed; preserve graph errors, duplicates, and measurement semantics."""
    invalid = {"status": "invalid_source_shape", "root": None,
               "summary": None, "direct_preview": []}
    if not isinstance(value, dict):
        return invalid
    nodes, edges = value.get("nodes"), value.get("edges")
    err = value.get("error", "")
    if (not isinstance(nodes, list) or not isinstance(edges, list)
            or not 1 <= len(nodes) <= MAX_NODES or len(edges) > MAX_EDGES
            or not isinstance(err, str) or len(err) > 4096):
        return invalid
    safe_nodes: list[dict[str, Any]] = []
    has_errors = bool(err)
    try:
        for i, node in enumerate(nodes):
            if not isinstance(node, dict) or not isinstance(node.get("versionKey"), dict):
                raise ValueError("invalid node")
            k = node["versionKey"]
            if (not isinstance(k.get("system"), str) or k["system"] not in SYSTEMS
                    or not isinstance(k.get("name"), str) or not _KEY_NAME.fullmatch(k["name"])
                    or not isinstance(k.get("version"), str) or not _KEY_VERSION.fullmatch(k["version"])
                    or node.get("relation") not in {"SELF", "DIRECT", "INDIRECT"}
                    or (i == 0 and node["relation"] != "SELF")
                    or (i > 0 and node["relation"] == "SELF")
                    or type(node.get("bundled", False)) is not bool):
                raise ValueError("invalid node metadata")
            errors = node.get("errors", [])
            if not isinstance(errors, list) or len(errors) > 16 or any(
                not isinstance(e, str) or len(e) > 1024 for e in errors
            ):
                raise ValueError("invalid node errors")
            has_errors |= bool(errors)
            safe_nodes.append({
                "system": k["system"], "name": k["name"],
                "version": k["version"], "relation": node["relation"],
                "bundled": node.get("bundled", False),
                "has_resolution_error": bool(errors),
            })
        if (safe_nodes[0]["system"] != system
                or not _equivalent_name(package, safe_nodes[0]["name"], system)
                or safe_nodes[0]["version"] != version):
            raise ValueError("provider root package/version mismatch")
        safe_edges: list[tuple[int, int]] = []
        for edge in edges:
            if (not isinstance(edge, dict)
                    or type(edge.get("fromNode")) is not int
                    or type(edge.get("toNode")) is not int
                    or not 0 <= edge["fromNode"] < len(nodes)
                    or not 0 <= edge["toNode"] < len(nodes)):
                raise ValueError("bad graph edge")
            safe_edges.append((edge["fromNode"], edge["toNode"]))
    except (ValueError, TypeError):
        return invalid

    direct = [n for n in safe_nodes[1:] if n["relation"] == "DIRECT"]
    indirect = [n for n in safe_nodes[1:] if n["relation"] == "INDIRECT"]
    # Duplicate package versions can occur at different nodes; distinguish
    # node instances from distinct canonical version keys.
    distinct = {
        (n["system"], n["name"], n["version"])
        for n in safe_nodes[1:]
    }
    direct_keys = {(n["system"], n["name"], n["version"]) for n in direct}
    preview = []
    for key in sorted(direct_keys)[:limit]:
        preview.append({"ecosystem": key[0], "package": key[1], "version": key[2]})
    return {
        "status": "observed_partial" if has_errors else "observed",
        "root": {"ecosystem": safe_nodes[0]["system"],
                 "package": safe_nodes[0]["name"],
                 "version": safe_nodes[0]["version"]},
        "summary": {
            "resolved_dependency_node_instances": len(safe_nodes) - 1,
            "distinct_resolved_dependency_versions": len(distinct),
            "direct_dependency_node_instances": len(direct),
            "distinct_direct_dependency_versions": len(direct_keys),
            "indirect_dependency_node_instances": len(indirect),
            "graph_edge_count": len(safe_edges),
            "bundled_node_instances": sum(n["bundled"] for n in safe_nodes[1:]),
            "graph_has_resolution_errors": has_errors,
            "preview_truncated": len(direct_keys) > limit,
            "root_only_zero_dependencies_observed": len(safe_nodes) == 1 and not has_errors,
        },
        "direct_preview": preview,
        "graph_scope": "provider_resolved_generic_64bit_linux_single_version",
        "not_installs_or_dependents_or_customers": True,
        "missing_graph_is_not_zero_dependencies": True,
        "_cache_nodes": safe_nodes,
        "_cache_edges": safe_edges,
    }


def _sanitized_cache_payload(parsed: dict[str, Any]) -> dict[str, Any]:
    return {
        "nodes": [
            {"versionKey": {"system": n["system"], "name": n["name"],
                            "version": n["version"]},
             "relation": n["relation"], "bundled": n["bundled"], "errors": []}
            for n in parsed["_cache_nodes"]
        ],
        "edges": [{"fromNode": a, "toNode": b} for a, b in parsed["_cache_edges"]],
        "error": "",
    }


def _fetch(url: str) -> tuple[int, Any]:
    """One fixed-host HTTPS GET; no proxies, redirects, retries, or secrets."""
    import requests

    if not url.startswith(BASE + "/v3/systems/") or not url.endswith(":dependencies"):
        raise ValueError("Unapproved deps.dev request")
    if len(url) > 500 or "?" in url or "#" in url or "\\" in url:
        raise ValueError("Unsafe deps.dev request")
    session = requests.Session()
    session.trust_env = False
    try:
        with session.get(
            url, allow_redirects=False, timeout=(4, 12), stream=True,
            headers={"Accept": "application/json",
                     "User-Agent": "mcp-trendpulse/0.2 (read-only package research)"},
        ) as response:
            if response.status_code != 200 or "json" not in response.headers.get(
                "Content-Type", ""
            ).lower():
                return response.status_code, None
            raw = response.raw.read(MAX_BYTES + 1, decode_content=True)
            if len(raw) > MAX_BYTES:
                raise ResponseTooLarge("Source exceeded local 128KiB cap")
            try:
                return 200, json.loads(raw)
            except (UnicodeError, ValueError):
                return 200, None
    finally:
        session.close()


def inspect_package_dependencies(
    *, ecosystem: str, package: str, version: str,
    execute: bool = False, cache: Any = None,
    fetcher: Callable[[str], tuple[int, Any]] | None = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Plan-only by default. Only a fixed, concrete version is inspected."""
    system, package, version = _identifiers(ecosystem, package, version)
    if type(execute) is not bool:
        raise ValueError("execute must be explicitly boolean")
    now = observed_at or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("observed_at must include timezone")
    now = now.astimezone(timezone.utc)
    url = _url(system, package, version)
    result: dict[str, Any] = {
        "source": SOURCE, "source_url": url,
        "requested": {"ecosystem": system, "package": package, "version": version},
        "status": "planned", "root": None, "summary": None,
        "direct_preview": [], "observed_at": now.isoformat(),
        "requests_attempted": 0, "network_performed": False,
        "cache_hit": False, "free_source": True,
        "local_daily_cap": DAILY_CAP, "customer_demand_verified": False,
        "download_count_verified": False,
        "ecosystem_scope": "ecosystem_specific_not_cross_platform_population",
    }
    if not execute:
        return result
    try:
        if cache is None:
            from mcp_trendpulse.intelligence_core import BudgetCache
            cache = BudgetCache()
        key = _key(system, package, version)
        saved = cache.cached(key)
        if (isinstance(saved, dict)
                and saved.get("source") == SOURCE
                and saved.get("requested") == result["requested"]
                and isinstance(saved.get("observed_at"), str)):
            try:
                when = datetime.fromisoformat(saved["observed_at"])
                if when.utcoffset() is not None and 0 <= (
                    now - when.astimezone(timezone.utc)
                ).total_seconds() <= TTL_SECONDS:
                    parsed = _parse_graph(saved.get("payload"), system=system, package=package, version=version)
                    if parsed["status"] == "observed":
                        parsed.pop("_cache_nodes", None)
                        parsed.pop("_cache_edges", None)
                        result.update(parsed)
                        result["observed_at"] = when.astimezone(timezone.utc).isoformat()
                        result["cache_hit"] = True
                        return result
            except (TypeError, ValueError):
                pass
        if cache.blocked(SOURCE):
            result.update(status="unavailable", reason="provider_cooldown")
            return result
        cache.reserve(SOURCE, DAILY_CAP, guard_cooldown=True)
        result["requests_attempted"] = 1
        status, payload = (fetcher or _fetch)(url)
        result["network_performed"] = True
        if status in (429, 503):
            cache.cool_down(SOURCE, seconds=120)
            result.update(status="unavailable", reason=f"http_{status}")
            return result
        if status != 200:
            result.update(status="unavailable", reason="provider_response_error")
            return result
        parsed = _parse_graph(payload, system=system, package=package, version=version)
        if parsed["status"] == "observed":
            cache.save(key, {
                "source": SOURCE, "requested": result["requested"],
                "observed_at": now.isoformat(),
                "payload": _sanitized_cache_payload(parsed),
            }, ttl=TTL_SECONDS)
        parsed.pop("_cache_nodes", None)
        parsed.pop("_cache_edges", None)
        result.update(parsed)
        return result
    except Exception as exc:
        if isinstance(exc, ResponseTooLarge):
            result.update(status="invalid_source_shape", reason="response_oversized")
        elif type(exc).__name__ == "DailyBudgetExceeded":
            result.update(status="unavailable", reason="local_daily_budget_exceeded")
        elif type(exc).__name__ == "SourceCoolingDown":
            result.update(status="unavailable", reason="provider_cooldown")
        else:
            result.update(status="unavailable", reason="storage_or_network_unavailable")
        return result
