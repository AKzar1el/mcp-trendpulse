"""A04/A10 opt-in fixed-origin fetching using v1's durable UTC budgets.

This module deliberately does NOT call intelligence_core.collect(): its generic
market evidence projector could retain raw OSV advisory material and would
violate this minimal-rights contract. Reuse BudgetCache / FileLock but process
only source-validated metadata before storing anything.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from filelock import FileLock, Timeout as FileLockTimeout

from mcp_trendpulse.intelligence_core import (
    BudgetCache, DailyBudgetExceeded, IntelligenceError, SourceCoolingDown,
)
from mcp_trendpulse.mjau_v3.osv import (
    parse_compact_package_query, plan_compact_package_query,
    present_compact_query_for_mcp,
)
from mcp_trendpulse.mjau_v3.wikidata import (
    _clean_text, candidates_for_name, parse_qid_lookup, plan_qid_lookup,
)

MAX_BYTES = 192_000
TIMEOUT_SECONDS = 8
WIKIDATA_DAILY_CAP = 8
OSV_DAILY_CAP = 10
WIKIDATA_BUDGET_KEY = "mjau_v3_wikidata_action_api"
OSV_BUDGET_KEY = "mjau_v3_osv_querybatch"
CACHE_TTL_SECONDS = 3600
WIKIDATA_CONTACT_USER_AGENT = (
    "mcp-trendpulse-mjau-v3/0.1 "
    "(https://github.com/AKzar1el/mcp-trendpulse/issues)"
)
OSV_USER_AGENT = "mcp-trendpulse-mjau-v3/0.1 (read-only research)"
WIKIDATA_LICENSE = "https://www.wikidata.org/wiki/Wikidata:Licensing"


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def _canonical_wikidata_query(url: str) -> bool:
    """At the transport boundary, accept only our exact bounded QID request."""
    try:
        query = parse_qs(
            urlsplit(url).query, strict_parsing=True, keep_blank_values=True,
        )
        if (set(query) != {
                "action", "ids", "languages", "props", "format", "formatversion",
        } or any(len(values) != 1 for values in query.values())):
            return False
        qids = query["ids"][0].split("|")
        languages = query["languages"][0].split("|")
        return plan_qid_lookup(qids, languages)["url"] == url
    except (KeyError, ValueError):
        return False


def _canonical_osv_batch(body: Any) -> bool:
    """Do not let a future caller expand a single-version OSV query into N."""
    if (not isinstance(body, dict) or set(body) != {"queries"}
            or not isinstance(body["queries"], list)
            or len(body["queries"]) != 1):
        return False
    query = body["queries"][0]
    if not isinstance(query, dict) or set(query) != {"package", "version"}:
        return False
    package = query["package"]
    if not isinstance(package, dict) or set(package) != {"ecosystem", "name"}:
        return False
    try:
        canonical = plan_compact_package_query(
            package["ecosystem"], package["name"], query["version"],
        )
    except ValueError:
        return False
    return canonical["json_body"] == body


def _request_json(
    *, url: str, method: str, body: dict[str, Any] | None,
    timeout: int = TIMEOUT_SECONDS,
) -> Any:
    """One original-provider request; never retries, redirects or fetches URLs in results."""
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise IntelligenceError("Unapproved MJAU v3 source request") from None
    trusted_get = (
        method == "GET" and parsed.hostname == "www.wikidata.org"
        and parsed.path == "/w/api.php" and body is None
        and _canonical_wikidata_query(url)
    )
    trusted_post = (
        method == "POST" and parsed.hostname == "api.osv.dev"
        and parsed.path == "/v1/querybatch" and parsed.query == ""
        and _canonical_osv_batch(body)
    )
    if (parsed.scheme != "https" or port not in (None, 443)
            or parsed.username or parsed.password or parsed.fragment
            or not (trusted_get or trusted_post)):
        raise IntelligenceError("Unapproved MJAU v3 source request")
    if type(timeout) is not int or timeout != TIMEOUT_SECONDS:
        raise IntelligenceError("MJAU v3 request timeout is fixed")
    data = (
        json.dumps(body, separators=(",", ":"), allow_nan=False).encode("utf-8")
        if body is not None else None
    )
    headers = {
        "Accept": "application/json",
        "User-Agent": WIKIDATA_CONTACT_USER_AGENT if trusted_get else OSV_USER_AGENT,
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    request = Request(url, data=data, headers=headers, method=method)
    with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
        if response.status != 200:
            raise IntelligenceError("Provider returned non-200 response")
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().casefold()
        if not (content_type == "application/json" or (
                content_type.startswith("application/") and content_type.endswith("+json")
        )):
            raise IntelligenceError("Provider returned non-JSON content")
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise IntelligenceError("Public source response exceeds 192000 bytes")

    def reject_duplicate_keys(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate keys in upstream JSON")
            result[key] = value
        return result

    return json.loads(
        raw.decode("utf-8", "strict"), object_pairs_hook=reject_duplicate_keys,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")),
    )


def _safe_failure(source: str, reason: str, *, cache_hit: bool = False) -> dict[str, Any]:
    return {
        "source": source,
        "status": "source_unavailable",
        "reason": reason,
        "not_a_zero_result": True,
        "retry_automatically": False,
        "network_performed": False,
        "cache_hit": cache_hit,
    }


def _prepare_or_get(
    source: str, *, url: str, method: str, body: dict[str, Any] | None,
    projection: Any, execute: bool, cache: BudgetCache | None,
) -> dict[str, Any]:
    """Scoped, no-side-effect plan; execution spends one atomic daily reservation."""
    if type(execute) is not bool:
        raise ValueError("execute must be an explicit boolean")
    cap, budget_key = {
        "wikidata_action_api": (WIKIDATA_DAILY_CAP, WIKIDATA_BUDGET_KEY),
        "osv_public_api": (OSV_DAILY_CAP, OSV_BUDGET_KEY),
    }[source]
    plan = {
        "source": source, "status": "planned",
        "method": method, "url": url, "body": body,
        "max_response_bytes": MAX_BYTES,
        "timeout_seconds": TIMEOUT_SECONDS,
        "daily_request_cap": cap,
        "max_request_count": 1,
        "no_automatic_redirects_or_retries": True,
        "credentials_required": False,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "network_performed": False,
    }
    if not execute:
        return plan

    store = cache if cache is not None else BudgetCache()
    identity = hashlib.sha256(json.dumps([
        "mjau-v3-fixed-source-v1", source, method, url, body,
    ], sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()
    cached = store.cached(identity)
    if cached is not None:
        return {**cached, "cache_hit": True, "network_performed": False}

    root = store.db.parent / ".request_locks"
    if root.is_symlink():
        raise IntelligenceError("Request lock directory may not be a symlink")
    root.mkdir(mode=0o700, exist_ok=True)
    path = root / f"{identity}.lock"
    if path.is_symlink():
        raise IntelligenceError("Request lock file may not be a symlink")
    try:
        with FileLock(str(path), timeout=TIMEOUT_SECONDS + 5):
            cached = store.cached(identity)
            if cached is not None:
                return {**cached, "cache_hit": True, "network_performed": False}
            try:
                store.reserve(budget_key, cap, guard_cooldown=True)
            except DailyBudgetExceeded:
                return _safe_failure(source, "local_utc_daily_budget_exhausted")
            except SourceCoolingDown:
                return _safe_failure(source, "persisted_provider_cooldown")

            try:
                payload = _request_json(
                    url=url, method=method, body=body, timeout=TIMEOUT_SECONDS,
                )
                data = projection(payload)
            except HTTPError as exc:
                if exc.code == 429:
                    # Respect upstream rate limits conservatively for the
                    # rest of this UTC-day. The local daily cap and caching
                    # remain in force even if the client retries manually.
                    store.stop_after_rate_limit(budget_key)
                elif exc.code == 503:
                    delay = exc.headers.get("Retry-After", "") if exc.headers else ""
                    seconds = min(300, max(30, int(delay))) if (
                        delay.isdecimal() and len(delay) <= 4
                    ) else 90
                    if delay.isdecimal() and len(delay) <= 6 and int(delay) > 300:
                        store.stop_after_rate_limit(budget_key)
                    else:
                        store.cool_down(budget_key, seconds)
                result = _safe_failure(source, f"provider_http_{exc.code}")
                result["network_performed"] = True
                store.save(identity, result, 45)
                return result
            except (URLError, OSError, TimeoutError, UnicodeError,
                    json.JSONDecodeError, ValueError, IntelligenceError,
                    RecursionError) as exc:
                # Never save/report external source content or exceptional strings.
                reason = (
                    "invalid_or_oversized_source_shape"
                    if isinstance(exc, (ValueError, RecursionError, IntelligenceError))
                    else "source_transport_or_encoding_error"
                )
                result = _safe_failure(source, reason)
                result["network_performed"] = True
                store.save(identity, result, 45)
                return result
            output = {
                **data,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "network_performed": True,
                "cache_hit": False,
                "daily_request_cap": cap,
                "retry_automatically": False,
                "source_terms_review_required": source == "osv_public_api",
            }
            # Cache ONLY validated, projected source metadata, never full JSON.
            store.save(identity, output, CACHE_TTL_SECONDS)
            return output
    except FileLockTimeout:
        return _safe_failure(source, "identical_source_request_in_progress")


def wikidata_identity(
    qids: list[str], languages: list[str], *, name: str = "",
    match_language: str = "en", execute: bool = False,
    cache: BudgetCache | None = None,
) -> dict[str, Any]:
    """Bounded official CC0 names, explicit human identity confirmation only."""
    original = plan_qid_lookup(qids, languages)
    if not isinstance(name, str):
        raise ValueError("Name must be a string")
    if name:
        _clean_text(name)
        if match_language not in languages:
            raise ValueError("Match language must be in requested languages")
    def project(payload: Any) -> dict[str, Any]:
        parsed = parse_qid_lookup(payload, qids, languages)
        # The pure adapter validates data *offline*, but this wrapper actually
        # obtained the source via a budgeted HTTP call. Do not expose the
        # internal OFFLINE_PARSED_UPSTREAM_PAYLOAD status to an end user as
        # though the source was not contacted. Preserve a separate field
        # describing the parser's no-extra-network guarantee.
        parsed["status"] = (
            "source_entities_observed"
            if parsed["source_coverage_complete"]
            else "source_entities_partially_observed"
        )
        parsed["source_payload_validated_offline"] = True
        parsed["license"] = "CC0-1.0"
        parsed["license_url"] = WIKIDATA_LICENSE
        parsed["identity_verified"] = False
        return parsed

    result = _prepare_or_get(
        "wikidata_action_api", url=original["url"], method="GET", body=None,
        projection=project, execute=execute, cache=cache,
    )
    # Request identity is QIDs/languages only. Each caller's optional name
    # comparison must be derived AFTER cache lookup, never persisted under a
    # cache key that ignores the name and could return a stale false match.
    if name and result.get("status") in (
        "source_entities_observed", "source_entities_partially_observed",
    ):
        return {
            **result,
            "name_candidates": candidates_for_name(result, name, match_language),
        }
    return result


def osv_package_ids(
    ecosystem: str, package: str, version: str, *,
    execute: bool = False, cache: BudgetCache | None = None,
) -> dict[str, Any]:
    """One source-matched version lookup; only minimal ID/date/link metadata."""
    original = plan_compact_package_query(ecosystem, package, version)
    def project(payload: Any) -> dict[str, Any]:
        parsed = parse_compact_package_query(
            payload, ecosystem=ecosystem, package=package, version=version,
        )
        return {
            **present_compact_query_for_mcp(parsed),
            "source_rights_review_status": "pending_final_original_feed_review",
            "commercial_bulk_redistribution_approved": False,
            "cc_by_license_url": "https://creativecommons.org/licenses/by/4.0/",
            "source_attribution": {
                "aggregator": "OSV.dev",
                "aggregator_url": "https://osv.dev/",
                "upstream_license_index": "https://google.github.io/osv.dev/data/",
                "cc_by_4_license": "https://creativecommons.org/licenses/by/4.0/",
                "transformation_notice": (
                    "Filtered original OSV querybatch response to factual "
                    "advisory IDs, modified timestamps and OSV record links; "
                    "no original advisory prose or severity was reproduced."
                ),
                "original_per_record_feed_verified": False,
            },
            "third_party_request_notice": (
                "execute=True sends ecosystem, package and exact version to "
                "the OSV.dev API; no private package lists or secrets."
            ),
            "source_licensing_comment": (
                "GHSA/PYSEC prefix indicates attribution hint, not permission; "
                "check original OSV source; no raw advisories are redistributed."
            ),
        }

    return _prepare_or_get(
        "osv_public_api", url=original["url"], method="POST",
        body=original["json_body"], projection=project,
        execute=execute, cache=cache,
    )
