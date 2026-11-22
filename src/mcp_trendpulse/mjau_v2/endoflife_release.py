"""B02: bounded community-curated product release support-window evidence.

endoflife.date publishes release-cycle status, not official vendor promises,
confirmed migration budgets, or business demand. In particular, active support,
extended support and end-of-life are distinct dates and boolean states.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from mcp_trendpulse.mjau_v2.singleflight import singleflight_request

BASE = "https://endoflife.date"
SOURCE = "endoflife_date_v1_release_cycle"
CAP_PER_DAY = 4
TTL_SECONDS = 24 * 3600
MAX_BYTES = 64 * 1024
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")
_RELEASE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,79}$")


class ResponseTooLarge(ValueError):
    pass


def _identifiers(product: Any, release: Any) -> tuple[str, str]:
    if not isinstance(product, str) or not _SLUG.fullmatch(product):
        raise ValueError("Product requires exact bounded endoflife.date slug")
    if (not isinstance(release, str) or not _RELEASE.fullmatch(release)
            or release in {".", ".."} or ".." in release):
        raise ValueError("Release cycle requires exact bounded name")
    return product, release


def _url(product: str, release: str) -> str:
    return f"{BASE}/api/v1/products/{product}/releases/{release}"


def _key(product: str, release: str) -> str:
    return "mjau_v2_eol_" + hashlib.sha256(
        json.dumps([SOURCE, product, release], separators=(",", ":")).encode(),
    ).hexdigest()


def _source_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not 10 <= len(value) <= 50:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def _source_date(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Invalid date-only source field")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError("Invalid date-only source field") from exc


def _parse(payload: Any, *, release: str, observed: datetime) -> dict[str, Any]:
    invalid = {"status": "invalid_source_shape", "release": None}
    if not isinstance(payload, dict) or not isinstance(payload.get("result"), dict):
        return invalid
    result = payload["result"]
    created = _source_datetime(payload.get("generated_at"))
    if (created is None or created > observed
            or not isinstance(payload.get("schema_version"), str)
            or not 1 <= len(payload["schema_version"]) <= 20
            or result.get("name") != release
            or type(result.get("isEol")) is not bool
            or type(result.get("isMaintained")) is not bool):
        return invalid
    parsed: dict[str, Any] = {}
    try:
        for field in ("releaseDate", "ltsFrom", "eoasFrom", "eolFrom", "eoesFrom"):
            parsed[field] = _source_date(result.get(field))
    except ValueError:
        return invalid
    for field in ("isEoas", "isLts", "isEoes"):
        value = result.get(field)
        if value is not None and type(value) is not bool:
            return invalid
        parsed[field] = value
    age_days = max(0, (observed.date() - created.date()).days)
    end_date = parsed["eolFrom"]
    days_until = (date.fromisoformat(end_date) - observed.date()).days if end_date else None
    # The source's isMaintained is broad: it may include commercial/extended
    # support even after the upstream software project's EOL. This is not
    # inherently contradictory (Node.js 20 is an observed real-world example).
    # Never convert availability into a contractual entitlement or vendor
    # commitment. Keep unrelated date/phase contradictions explicit.
    conflicts: list[str] = []
    caveats: list[str] = []
    post_eol_maintenance = result["isEol"] and result["isMaintained"]
    if post_eol_maintenance:
        if parsed["isEoes"] is False:
            caveats.append("post_eol_extended_or_commercial_support_possible")
        else:
            caveats.append("post_eol_maintenance_scope_unverified")
            if parsed["isEoes"] is True:
                conflicts.append("maintenance_claim_after_recorded_extended_support_end")
    # Ignore the EOL boundary day because providers can disagree on inclusivity.
    if days_until is not None:
        if days_until < -1 and not result["isEol"]:
            conflicts.append("past_eol_date_but_eol_false")
        elif days_until > 1 and result["isEol"]:
            conflicts.append("future_eol_date_but_eol_true")
    return {
        # Staleness takes precedence over caveats: never cache an aged
        # partial record as if it were a current provider observation.
        "status": ("observed_stale" if age_days > 30 else
                   "observed_partial" if conflicts or caveats else "observed"),
        "provider_phase_conflicts": conflicts,
        "provider_phase_consistent": not conflicts,
        "support_scope_caveats": caveats,
        "post_eol_maintenance_may_be_commercial": post_eol_maintenance,
        "support_entitlement_verified": False,
        "official_vendor_support_verified_by_api": False,
        "unconditional_support_or_migration_advice_allowed": False,
        "release": release,
        "source_schema_version": payload["schema_version"],
        "source_generated_at": created.isoformat(),
        "source_age_days": age_days,
        "release_date": parsed["releaseDate"],
        "lts": parsed["isLts"],
        "lts_from": parsed["ltsFrom"],
        "is_eoas": parsed["isEoas"],
        "eoas_from": parsed["eoasFrom"],
        "is_eol": result["isEol"],
        "eol_from": end_date,
        "is_eoes": parsed["isEoes"],
        "eoes_from": parsed["eoesFrom"],
        "is_maintained": result["isMaintained"],
        "calendar_days_until_reported_eol": days_until,
        "unknown_date_is_not_zero_or_no_support": True,
        "is_maintained_may_include_extended_support": True,
        "community_curated_not_vendor_certified": True,
        "commercial_migration_budget_verified": False,
    }


def _sanitized(payload: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": parsed["source_schema_version"],
        "generated_at": parsed["source_generated_at"],
        "result": {
            "name": parsed["release"], "isEol": parsed["is_eol"],
            "isMaintained": parsed["is_maintained"],
            "isEoas": parsed["is_eoas"],
            "isLts": parsed["lts"], "isEoes": parsed["is_eoes"],
            "releaseDate": parsed["release_date"], "ltsFrom": parsed["lts_from"],
            "eoasFrom": parsed["eoas_from"], "eolFrom": parsed["eol_from"],
            "eoesFrom": parsed["eoes_from"],
        },
    }


def _fetch(url: str) -> tuple[int, Any]:
    import requests

    if not re.fullmatch(
        r"https://endoflife\.date/api/v1/products/[a-z0-9][a-z0-9-]{0,79}/releases/[A-Za-z0-9][A-Za-z0-9._+-]{0,79}",
        url,
    ):
        raise ValueError("Unapproved lifecycle source URL")
    session = requests.Session()
    session.trust_env = False
    try:
        with session.get(
            url, allow_redirects=False, stream=True, timeout=(4, 12),
            headers={"Accept": "application/json",
                     "User-Agent": "mcp-trendpulse/0.2 (read-only lifecycle evidence)"},
        ) as response:
            if (response.status_code != 200
                    or "json" not in response.headers.get("Content-Type", "").lower()):
                return response.status_code, None
            body = response.raw.read(MAX_BYTES + 1, decode_content=True)
            if len(body) > MAX_BYTES:
                raise ResponseTooLarge("Oversized product lifecycle response")
            try:
                return 200, json.loads(body)
            except (UnicodeError, ValueError):
                return 200, None
    finally:
        session.close()


@singleflight_request(lambda args: _key(args["product"], args["release"]))
def observe_release_support(
    *, product: str, release: str, execute: bool = False,
    cache: Any = None, fetcher: Callable[[str], tuple[int, Any]] | None = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    product, release = _identifiers(product, release)
    if type(execute) is not bool:
        raise ValueError("Explicit execute boolean required")
    observed = observed_at or datetime.now(timezone.utc)
    if not isinstance(observed, datetime) or observed.utcoffset() is None:
        raise ValueError("Observation requires timezone")
    observed = observed.astimezone(timezone.utc)
    url = _url(product, release)
    vendor_reference = {
        "nodejs": "https://github.com/nodejs/Release/blob/main/schedule.json",
        "python": "https://devguide.python.org/versions/",
    }.get(product)
    result: dict[str, Any] = {
        "status": "planned", "source": SOURCE, "source_url": url,
        "primary_vendor_schedule_reference": vendor_reference,
        "vendor_schedule_checked_by_this_call": False,
        "product": product, "release": release,
        "observed_at": observed.isoformat(),
        "requests_attempted": 0, "network_performed": False,
        "cache_hit": False, "local_daily_cap": CAP_PER_DAY,
        "is_eol": None, "is_maintained": None,
        "calendar_days_until_reported_eol": None,
        "vendor_guarantee": False, "commercial_migration_budget_verified": False,
    }
    if not execute:
        return result
    try:
        if cache is None:
            from mcp_trendpulse.intelligence_core import BudgetCache
            cache = BudgetCache(root=Path.home() / ".mcp-trendpulse" / "mjau-v2-intelligence")
        key = _key(product, release)
        saved = cache.cached(key)
        if (isinstance(saved, dict) and saved.get("source") == SOURCE
                and saved.get("product") == product and saved.get("release") == release
                and isinstance(saved.get("observed_at"), str)):
            try:
                before = datetime.fromisoformat(saved["observed_at"])
                if before.utcoffset() is not None and 0 <= (
                    observed - before.astimezone(timezone.utc)
                ).total_seconds() <= TTL_SECONDS:
                    parsed = _parse(saved.get("payload"), release=release, observed=observed)
                    if (parsed["status"] in {"observed", "observed_partial"}
                            and not parsed["provider_phase_conflicts"]):
                        result.update(parsed)
                        result["cache_hit"] = True
                        result["observed_at"] = before.astimezone(timezone.utc).isoformat()
                        return result
            except (ValueError, TypeError):
                pass
        if cache.blocked(SOURCE):
            result.update(status="unavailable", reason="provider_cooldown")
            return result
        cache.reserve(SOURCE, CAP_PER_DAY, guard_cooldown=True)
        result["requests_attempted"] = 1
        code, payload = (fetcher or _fetch)(url)
        result["network_performed"] = True
        if code in (429, 503):
            cache.cool_down(SOURCE, seconds=120)
            result.update(status="unavailable", reason=f"http_{code}")
            return result
        if code == 404:
            result.update(status="not_found", reason="unknown_product_or_release")
            return result
        if code in (301, 302, 307, 308):
            result.update(status="unavailable", reason="rename_redirect_not_followed")
            return result
        if code != 200:
            result.update(status="unavailable", reason="provider_response_error")
            return result
        parsed = _parse(payload, release=release, observed=observed)
        result.update(parsed)
        if (parsed["status"] in {"observed", "observed_partial"}
                and not parsed["provider_phase_conflicts"]):
            cache.save(key, {
                "source": SOURCE, "product": product, "release": release,
                "observed_at": observed.isoformat(),
                "payload": _sanitized(payload, parsed),
            }, ttl=TTL_SECONDS)
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
