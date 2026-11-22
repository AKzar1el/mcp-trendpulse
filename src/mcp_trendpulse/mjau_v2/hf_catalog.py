"""A07: bounded Hugging Face Hub AI model/dataset discovery metadata.

TrendingScore, likes and downloads are provider-defined current snapshots,
NOT a time series, model quality, adoption/population or commercial demand.
Read-only source; no models, weights, dataset files, profile data or tokens.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

from mcp_trendpulse.mjau_v2.singleflight import singleflight_request

BASE = "https://huggingface.co"
SOURCE = "hf_public_hub_catalog_v2"
KINDS = frozenset({"models", "datasets"})
MAX_ROWS = 8
MAX_BYTES = 96 * 1024
CAP_PER_DAY = 4
TTL_SECONDS = 6 * 3600
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
_TERM = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{1,63}$")


class ResponseTooLarge(ValueError):
    pass


def _inputs(kind: Any, limit: Any, search: Any) -> tuple[str, int, str]:
    if not isinstance(kind, str) or kind not in KINDS:
        raise ValueError("Hub catalog kind must be models or datasets")
    if type(limit) is not int or not 1 <= limit <= MAX_ROWS:
        raise ValueError("Hub page limit must be 1..8")
    if not isinstance(search, str) or search and not _TERM.fullmatch(search):
        raise ValueError("Optional Hub search must be a bounded printable phrase")
    return kind, limit, search


def _params(limit: int, search: str) -> dict[str, str]:
    out = {"sort": "trendingScore", "direction": "-1", "limit": str(limit)}
    if search:
        out["search"] = search
    return out


def _url(kind: str) -> str:
    return BASE + "/api/" + kind


def _key(kind: str, limit: int, search: str) -> str:
    return "mjau_v2_hf_" + hashlib.sha256(json.dumps(
        [SOURCE, kind, limit, search],
        ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()


def _utc(raw: Any, *, now: datetime) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str) or not 10 <= len(raw) <= 50:
        raise ValueError("Invalid source timestamp")
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.utcoffset() is None or dt > now + timedelta(days=1):
            raise ValueError("Invalid timestamp timezone or future date")
        return dt.astimezone(timezone.utc).isoformat()
    except (ValueError, OverflowError) as exc:
        raise ValueError("Invalid source timestamp") from exc


def _count(raw: Any) -> int | None:
    if raw is None:
        return None
    if type(raw) is not int or not 0 <= raw <= 1_000_000_000_000:
        raise ValueError("Invalid metric count")
    return raw


def _score(raw: Any) -> float | None:
    if raw is None:
        return None
    if type(raw) not in (int, float) or not math.isfinite(raw) or raw < 0 or raw > 1e12:
        raise ValueError("Invalid provider trending score")
    return float(raw)


def _parse(payload: Any, *, kind: str, limit: int,
           search: str, observed: datetime) -> dict[str, Any]:
    invalid = {"status": "invalid_source_shape", "records": [],
               "received_rows": None, "rejected_rows": None}
    if not isinstance(payload, list) or len(payload) > limit:
        return invalid
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    rejected = 0
    # The Hub may match each query token in different parts of an ID.
    # Preserve a local scope check without requiring an exact phrase.
    search_tokens = search.casefold().split()
    for i, obj in enumerate(payload):
        if not isinstance(obj, dict):
            rejected += 1
            continue
        rid = obj.get("id")
        if (not isinstance(rid, str) or not _ID.fullmatch(rid)
                or rid in seen or obj.get("private") is not False
                or (kind == "models" and obj.get("modelId", rid) != rid)
                or (search_tokens and not all(
                    part in rid.casefold() for part in search_tokens))):
            rejected += 1
            continue
        gated = obj.get("gated")
        if not (gated is None or type(gated) is bool
                or (isinstance(gated, str) and gated in {"auto", "manual"})):
            rejected += 1
            continue
        try:
            score = _score(obj.get("trendingScore"))
            likes = _count(obj.get("likes"))
            downloads = _count(obj.get("downloads"))
            created = _utc(obj.get("createdAt"), now=observed)
            updated = _utc(obj.get("lastModified"), now=observed)
        except ValueError:
            rejected += 1
            continue
        item = {
            "repository_id": rid, "kind": kind,
            "source_detail_url": f"{BASE}/{'datasets/' if kind == 'datasets' else ''}{rid}",
            "provider_first_page_position": i + 1,
            "provider_trending_score": score,
            "provider_downloads": downloads,
            "provider_likes": likes,
            "created_at": created, "last_modified_at": updated,
            "gated": gated if gated is not None else "not_reported",
            "private": False,
            "provider_download_window": "not_verified_by_this_adapter",
        }
        rows.append(item)
        seen.add(rid)
    if payload and not rows:
        return {**invalid, "received_rows": len(payload),
                "rejected_rows": rejected}
    return {
        "status": "no_data" if not payload else
                  "observed_partial" if rejected else "observed_partial",
        "records": rows, "received_rows": len(payload),
        "rejected_rows": rejected,
        "source_sort": "trendingScore_desc",
        "scope": "one_bounded_page_from_public_hub_catalog_not_population",
        "comparative_time_series_provided": False,
        "metric_counts_are_provider_defined_snapshots": True,
        "model_quality_verified": False,
        "buyer_demand_verified": False,
        "global_market_adoption_verified": False,
    }


def _fetch(url: str, params: dict[str, str]) -> tuple[int, Any]:
    """One bounded fixed-host GET; no auth, proxy, redirect or retry."""
    import requests

    if (url not in {_url("models"), _url("datasets")}
            or set(params) not in ({"sort", "direction", "limit"},
                                   {"sort", "direction", "limit", "search"})
            or params.get("sort") != "trendingScore"
            or params.get("direction") != "-1"):
        raise ValueError("Unexpected Hub request")
    try:
        limit = int(params["limit"])
    except (TypeError, ValueError, KeyError) as exc:
        raise ValueError("Invalid Hub request limit") from exc
    if not 1 <= limit <= MAX_ROWS:
        raise ValueError("Invalid Hub request limit")
    if "search" in params and not _TERM.fullmatch(params["search"]):
        raise ValueError("Invalid Hub request search")

    session = requests.Session()
    session.trust_env = False
    try:
        with session.get(
            url, params=params, timeout=(4, 12), allow_redirects=False,
            stream=True, headers={
                "Accept": "application/json",
                "User-Agent": "mcp-trendpulse/0.2 (public Hub metadata research only)",
            },
        ) as response:
            code = response.status_code
            if code != 200 or "json" not in response.headers.get("Content-Type", "").lower():
                return code, None
            raw = response.raw.read(MAX_BYTES + 1, decode_content=True)
            if len(raw) > MAX_BYTES:
                raise ResponseTooLarge("Hub metadata exceeds local cap")
            try:
                return code, json.loads(raw)
            except (UnicodeError, ValueError):
                return code, None
    finally:
        session.close()


@singleflight_request(
    lambda args: _key(args["kind"], args["limit"], args["search"])
)
def discover_hf_catalog(
    *, kind: str, limit: int = 5, search: str = "",
    execute: bool = False, cache: Any = None,
    fetcher: Callable[[str, dict[str, str]], tuple[int, Any]] | None = None,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    kind, limit, search = _inputs(kind, limit, search)
    if type(execute) is not bool:
        raise ValueError("execute must be boolean")
    now = observed_at or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    now = now.astimezone(timezone.utc)
    params = _params(limit, search)
    url = _url(kind)
    result: dict[str, Any] = {
        "source": SOURCE, "source_url": url,
        "request_url": url + "?" + urlencode(params),
        "kind": kind, "search": search, "limit": limit,
        "status": "planned", "observed_at": now.isoformat(),
        "requests_attempted": 0, "network_performed": False,
        "cache_hit": False, "records": [],
        "provider_query_is_catalog_not_semantic_validation": True,
        "local_daily_cap": CAP_PER_DAY,
        "paid_services_used": False,
        "model_weights_or_dataset_files_downloaded": False,
        "customer_demand_verified": False,
    }
    if not execute:
        return result
    try:
        if cache is None:
            from mcp_trendpulse.intelligence_core import BudgetCache
            cache = BudgetCache(root=Path.home() / ".mcp-trendpulse" / "mjau-v2-intelligence")
        key = _key(kind, limit, search)
        saved = cache.cached(key)
        if (isinstance(saved, dict)
                and saved.get("source") == SOURCE
                and saved.get("kind") == kind
                and saved.get("limit") == limit
                and saved.get("search") == search
                and isinstance(saved.get("observed_at"), str)):
            try:
                old = datetime.fromisoformat(saved["observed_at"])
                if old.utcoffset() is not None and 0 <= (
                    now - old.astimezone(timezone.utc)
                ).total_seconds() <= TTL_SECONDS:
                    parsed = _parse(saved.get("payload"), kind=kind, limit=limit,
                                    search=search, observed=now)
                    if parsed["status"] in {"observed_partial", "no_data"} and parsed["rejected_rows"] == 0:
                        result.update(parsed)
                        result["cache_hit"] = True
                        result["observed_at"] = old.astimezone(timezone.utc).isoformat()
                        return result
            except (ValueError, TypeError):
                pass
        if cache.blocked(SOURCE):
            result.update(status="unavailable", reason="provider_cooldown")
            return result
        cache.reserve(SOURCE, CAP_PER_DAY, guard_cooldown=True)
        result["requests_attempted"] = 1
        status, payload = (fetcher or _fetch)(url, params)
        result["network_performed"] = True
        if status in (429, 503):
            cache.cool_down(SOURCE, seconds=120)
            result.update(status="unavailable", reason=f"http_{status}")
            return result
        if status != 200:
            result.update(status="unavailable", reason="provider_response_error")
            return result
        parsed = _parse(payload, kind=kind, limit=limit, search=search, observed=now)
        result.update(parsed)
        if parsed["status"] in {"observed_partial", "no_data"} and parsed["rejected_rows"] == 0:
            clean = [{
                "id": row["repository_id"], "private": False,
                "trendingScore": row["provider_trending_score"],
                "likes": row["provider_likes"],
                "downloads": row["provider_downloads"],
                "createdAt": row["created_at"],
                "lastModified": row["last_modified_at"],
                "gated": None if row["gated"] == "not_reported" else row["gated"],
                **({"modelId": row["repository_id"]} if kind == "models" else {}),
            } for row in parsed["records"]]
            cache.save(key, {
                "source": SOURCE, "kind": kind, "limit": limit,
                "search": search, "observed_at": now.isoformat(),
                "payload": clean,
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
