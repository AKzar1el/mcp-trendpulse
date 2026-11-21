"""A10: offline-only OSV advisory projection, never an automated security verdict.

All HTTP is handled by an externally approved budgeted TrendPulse collector.
This module defines fixed public request plans and parses bounded payloads.
Vulnerability existence is NOT user demand, exploitation, or affectedness proof
outside the provider's package/version query contract.
"""

from __future__ import annotations

import ipaddress
import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlsplit

ORIGIN = "https://api.osv.dev"
ECOSYSTEMS = {"PyPI", "npm"}
PACKAGE = re.compile(r"(?:@[-a-z0-9._]+/)?[-a-zA-Z0-9._]+\Z")
VERSION = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._+\-]{0,63}\Z")
ADVISORY = re.compile(r"(?:OSV-\d{4}-\d+|GHSA-[a-z0-9-]{10,40}|CVE-\d{4}-\d{4,}|PYSEC-\d{4}-\d+)\Z")
MAX_BYTES = 192_000
MAX_ADVISORIES = 12
MAX_LINKS = 4
OSV_LICENSE_SOURCES = "https://google.github.io/osv.dev/data/"
CC_BY_4_LICENSE = "https://creativecommons.org/licenses/by/4.0/"


def _attribution_hint(advisory_id: str) -> dict[str, Any]:
    """Return a non-authoritative attribution hint, never a license grant.

    OSV aggregates feeds with different rights, so an advisory's ID prefix
    alone cannot establish that all downstream uses are permitted.
    """
    database = (
        "GitHub Advisory Database" if advisory_id.startswith("GHSA-")
        else "PyPI Advisory Database" if advisory_id.startswith("PYSEC-")
        else None
    )
    return {
        "upstream_database_hint": database,
        "source_license_hint": "CC-BY-4.0" if database else None,
        "source_license_reference": OSV_LICENSE_SOURCES,
        "license_text_reference": CC_BY_4_LICENSE if database else None,
        "suggested_attribution": f"{database} via OSV.dev" if database else None,
        "source_specific_license_review_required": True,
        "raw_advisory_redistribution_authorized": False,
    }


def _query_inputs(ecosystem: str, package: str, version: str) -> None:
    if ecosystem not in ECOSYSTEMS:
        raise ValueError("Only scoped PyPI/npm ecosystem lookups are supported")
    if (not isinstance(package, str) or not 1 <= len(package) <= 120
            or PACKAGE.fullmatch(package) is None or ".." in package
            or package.startswith((".", "-"))):
        raise ValueError("Invalid bounded package name")
    if ecosystem == "PyPI" and ("/" in package or "@" in package):
        raise ValueError("PyPI package must be an exact registry name")
    if not isinstance(version, str) or VERSION.fullmatch(version) is None:
        raise ValueError("Exact bounded package version required")


def plan_package_query(ecosystem: str, package: str, version: str) -> dict[str, Any]:
    """One POST, plan-only; no automatic querybatch or follow-up paging."""
    _query_inputs(ecosystem, package, version)
    return {
        "source": "osv_public_api", "method": "POST", "url": f"{ORIGIN}/v1/query",
        "json_body": {"package": {"name": package, "ecosystem": ecosystem}, "version": version},
        "execution": "PLAN_ONLY", "max_requests_if_approved": 1,
        "max_response_bytes": MAX_BYTES, "timeout_seconds_if_approved": 8,
        "requires_existing_trendpulse_budget_and_cache": True,
        "zero_network_calls": True,
    }


def plan_advisory_lookup(advisory_id: str) -> dict[str, Any]:
    if not isinstance(advisory_id, str) or ADVISORY.fullmatch(advisory_id) is None:
        raise ValueError("Valid OSV/GHSA/CVE/PYSEC advisory ID required")
    return {
        "source": "osv_public_api", "method": "GET",
        "url": f"{ORIGIN}/v1/vulns/{advisory_id}", "execution": "PLAN_ONLY",
        "max_requests_if_approved": 1, "max_response_bytes": MAX_BYTES,
        "requires_existing_trendpulse_budget_and_cache": True, "zero_network_calls": True,
    }


def _date(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not 10 <= len(value) <= 40:
        raise ValueError(f"Invalid {field} timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid {field} timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"Timezone missing for {field}")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_ref(link: Any) -> str | None:
    if not isinstance(link, str) or len(link) > 500:
        return None
    try:
        url = urlsplit(link)
    except ValueError:
        return None
    if (url.scheme != "https" or not url.hostname or url.username or url.password
            or url.fragment or url.port not in (None, 443)):
        return None
    host = url.hostname.lower()
    if "." not in host or host.endswith((".local", ".internal")) or host == "localhost":
        return None
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not ip.is_global:
            return None
    if any(any(x in name.lower() for x in ("token", "secret", "auth", "apikey", "password"))
           for name, _ in parse_qsl(url.query, keep_blank_values=True)):
        return None
    return link


def _size(payload: Any) -> None:
    try:
        size = len(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid OSV JSON") from exc
    if size > MAX_BYTES:
        raise ValueError("OSV response exceeds local safety cap")


def _advisory(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError("Invalid OSV advisory object")
    ident = item.get("id")
    if not isinstance(ident, str) or ADVISORY.fullmatch(ident) is None:
        raise ValueError("Invalid OSV advisory identity")
    published = _date(item.get("published"), "published")
    modified = _date(item.get("modified"), "modified")
    withdrawn = _date(item.get("withdrawn"), "withdrawn")
    if published is not None and modified is not None and published > modified:
        raise ValueError("Advisory modified before publication")
    refs = item.get("references", [])
    if not isinstance(refs, list) or len(refs) > 30:
        raise ValueError("Invalid OSV reference list")
    links = []
    for row in refs:
        if not isinstance(row, dict):
            raise ValueError("Invalid OSV reference")
        url = _safe_ref(row.get("url"))
        if url and url not in links:
            links.append(url)
    return {
        "advisory_id": ident, "source_url": f"https://osv.dev/vulnerability/{ident}",
        "published_at": published, "modified_at": modified,
        "withdrawn_at": withdrawn,
        "status": "withdrawn" if withdrawn else (
            "dated_advisory" if published is not None and modified is not None
            else "incomplete_advisory_dates"
        ),
        "advisory_links": links[:MAX_LINKS],
        **_attribution_hint(ident),
        "copyright_review_required_per_original_feed": True,
        "is_not_exploitation_evidence": True,
        "is_not_commercial_demand_evidence": True,
    }


def parse_package_query(payload: Any, *, ecosystem: str, package: str, version: str) -> dict[str, Any]:
    """Project one official response, marking pagination and missingness."""
    _query_inputs(ecosystem, package, version)
    _size(payload)
    if not isinstance(payload, dict) or "error" in payload:
        raise ValueError("OSV provider error or malformed envelope")
    more = payload.get("next_page_token")
    if more is not None and (not isinstance(more, str) or not 1 <= len(more) <= 2048):
        raise ValueError("Invalid pagination token")
    # The real OSV POST /v1/query endpoint returns HTTP 200 with {} when no
    # advisories are indexed (observed for PyPI six==1.16.0). This is a valid
    # empty result, NOT a declaration that the package is secure. Reject other
    # missing-vulns envelopes rather than silently treating them as empty.
    items = [] if not payload else payload.get("vulns")
    if items is None and more is not None:
        items = []
    if not isinstance(items, list) or len(items) > MAX_ADVISORIES:
        raise ValueError("Unexpected or oversized advisory sample")
    records = [_advisory(row) for row in items]
    if len({r["advisory_id"] for r in records}) != len(records):
        raise ValueError("Duplicate advisory IDs in response")
    return {
        "source": "osv_public_api", "package": package, "ecosystem": ecosystem,
        "version": version, "status": "incomplete_paged_response" if more is not None else (
            "no_returned_advisories" if not records else "source_advisories_returned"
        ),
        "query_is_source_match_not_local_version_range_recomputation": True,
        "source_population_complete": more is None,
        "advisory_count_in_this_response": len(records), "records": records,
        "no_advisory_not_equivalent_to_safe_package": True,
        "no_auto_remediation": True, "zero_network_calls": True,
    }


def parse_advisory_lookup(payload: Any, advisory_id: str) -> dict[str, Any]:
    if not isinstance(advisory_id, str) or ADVISORY.fullmatch(advisory_id) is None:
        raise ValueError("Invalid advisory ID")
    _size(payload)
    record = _advisory(payload)
    if record["advisory_id"] != advisory_id:
        raise ValueError("Wrong advisory returned for requested identity")
    return {"source": "osv_public_api", "lookup_id": advisory_id,
            "record": record, "zero_network_calls": True}


def parse_http_result(status: int, payload: Any, *, ecosystem: str, package: str, version: str) -> dict[str, Any]:
    """Already-received transport result: never fetches/retries/copies errors."""
    _query_inputs(ecosystem, package, version)
    if isinstance(status, bool) or not isinstance(status, int):
        raise ValueError("Invalid HTTP status")
    if status != 200:
        return {"source": "osv_public_api", "status": "source_unavailable",
                "http_status": status, "observations": None, "retry": False,
                "cause": "rate_limited" if status == 429 else (
                    "permission_denied" if status in (401, 403) else "transport_failed"
                ), "not_a_zero_result": True}
    return parse_package_query(payload, ecosystem=ecosystem, package=package, version=version)
