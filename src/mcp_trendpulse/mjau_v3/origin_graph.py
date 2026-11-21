"""B09: bounded offline event-origin and syndication audit.

No text similarity, inferred business identity, scraping or automatic trust of
publisher labels. Linked records require explicit, source-backed human review.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, timedelta
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from .historical import _date, _public_url

MAX_RECORDS = 120
MAX_BYTES = 180_000
RELATIONS = frozenset({"original", "syndicated", "same_event", "unknown"})
TRACKERS = {"fbclid", "gclid", "igshid", "mc_cid", "mc_eid", "ref"}


def _canonical(url: str) -> tuple[str, str, tuple[tuple[str, str], ...]]:
    parts = urlsplit(url)
    params = tuple(sorted(
        (name, value) for name, value in parse_qsl(parts.query, keep_blank_values=True)
        if name.lower() not in TRACKERS and not name.lower().startswith("utm_")
    ))
    return (parts.hostname.lower(), parts.path.rstrip("/") or "/", params)


def _label(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a bounded ASCII identifier")
    if name in {"source_id", "publisher"}:
        if re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,79}", value) is None:
            raise ValueError(f"{name} must be a lowercase stable identifier")
    elif (not value.isascii() or not 2 <= len(value) <= 120
          or any(ord(char) < 33 or ord(char) > 126 for char in value)):
        raise ValueError(f"{name} must be a bounded printable ASCII identifier")
    return value


def audit_origin_evidence(
    records: list[dict[str, Any]], *, as_of: str,
) -> dict[str, Any]:
    """Count *anchored* original event chains, abstaining on uncertain origins.

    ``reviewed_origin`` is a reviewer assertion; this function cannot confirm
    that a third-party web page truly cites the specified original. Only
    manually source-audited inputs may be used for factual comparison.
    """
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        raise ValueError("At most 120 evidence records may be audited")
    try:
        size = len(json.dumps(records, ensure_ascii=False, allow_nan=False).encode())
    except (ValueError, TypeError) as exc:
        raise ValueError("Evidence must be JSON") from exc
    if size > MAX_BYTES:
        raise ValueError("Evidence exceeds 180 KiB")
    cutoff = _date(as_of, "as_of")
    if cutoff > date.today():
        raise ValueError("Future as_of cutoff is prohibited")
    kept: list[dict[str, Any]] = []
    ignored: dict[str, int] = defaultdict(int)
    seen_ids: dict[tuple[str, str], str] = {}
    for raw in records:
        if not isinstance(raw, dict):
            raise ValueError("Evidence record must be an object")
        source = _label(raw.get("source_id"), "source_id")
        rid = _label(raw.get("source_record_id"), "source_record_id")
        key = (source, rid)
        fingerprint = json.dumps(raw, ensure_ascii=False, sort_keys=True)
        if key in seen_ids:
            if seen_ids[key] != fingerprint:
                raise ValueError("Conflicting duplicate source identity")
            ignored["duplicate_source_record"] += 1
            continue
        seen_ids[key] = fingerprint
        publisher = _label(raw.get("publisher"), "publisher")
        url = _public_url(raw.get("source_url"))
        observed = _date(raw.get("observed_at"), "observed_at")
        published = _date(raw.get("published_at"), "published_at")
        if published > observed:
            raise ValueError("Publication cannot follow observation")
        if observed > cutoff or published > cutoff:
            ignored["future_or_unobserved"] += 1
            continue
        if published < cutoff - timedelta(days=365):
            ignored["older_than_365_days"] += 1
            continue
        relation = raw.get("origin_relation", "unknown")
        if relation not in RELATIONS:
            raise ValueError("Unsupported origin relation")
        reviewed = raw.get("reviewed_origin") is True
        root_key = None
        if relation != "unknown":
            root_url = _public_url(raw.get("origin_url"))
            root_key = _canonical(root_url)
            if relation == "original" and _canonical(url) != root_key:
                raise ValueError("An original source must resolve to its own URL")
            if relation in {"syndicated", "same_event"}:
                if _canonical(url) == root_key:
                    raise ValueError("A derived source must have a distinct URL")
                # An explicit reference allows a reviewer to inspect the linkage.
                _public_url(raw.get("lineage_reference_url"))
            if not reviewed:
                root_key = None
                ignored["unreviewed_origin_claim"] += 1
        kept.append({
            "id": f"{source}:{rid}", "publisher": publisher,
            "url": url, "relation": relation, "root": root_key,
            "original": relation == "original" and reviewed,
        })
    by_root: dict[tuple[str, str, tuple[tuple[str, str], ...]], list[dict[str, Any]]] = (
        defaultdict(list)
    )
    unresolved: list[dict[str, Any]] = []
    for rec in kept:
        if rec["root"] is None:
            unresolved.append(rec)
        else:
            by_root[rec["root"]].append(rec)
    origin_groups = []
    anchored_publishers = set()
    dependent_records = 0
    conflicts = 0
    for root, members in sorted(by_root.items(), key=lambda x: repr(x[0])):
        originals = [item for item in members if item["original"]]
        publishers = {item["publisher"] for item in originals}
        if len(publishers) != 1:
            unresolved.extend(members)
            ignored["unanchored_or_conflicting_root"] += len(members)
            if len(publishers) > 1:
                conflicts += 1
            continue
        anchor = next(iter(publishers))
        anchored_publishers.add(anchor)
        dependent_records += len(members) - 1
        origin_groups.append({
            "origin_url_key": {"host": root[0], "path": root[1],
                               "query": list(root[2])},
            "original_publisher": anchor,
            "record_ids": sorted(x["id"] for x in members),
            "original_count": len(originals),
            "derived_count": len(members) - len(originals),
        })
    return {
        "status": "AUDIT_ONLY" if origin_groups else "INSUFFICIENT_VERIFIED_ORIGINS",
        "as_of": cutoff.isoformat(), "records_submitted": len(records),
        "records_in_window": len(kept),
        "verified_original_event_count": len(origin_groups),
        "verified_independent_original_publishers": len(anchored_publishers),
        "dependent_or_same_event_records": dependent_records,
        "unresolved_origin_records": len(unresolved),
        "contradictory_original_claims": conflicts,
        "v1_independent_publisher_proxy_before_lineage": len({
            item["publisher"] for item in kept
        }),
        "v1_proxy_is_not_full_v1_evaluation": True,
        "ignored": dict(sorted(ignored.items())),
        "origins": origin_groups[:40],
        "unresolved_record_ids": sorted(x["id"] for x in unresolved)[:60],
        "caller_attested_lineage_not_automatically_proved": True,
        "no_market_demand_inference": True,
        "zero_network_calls": True,
    }
