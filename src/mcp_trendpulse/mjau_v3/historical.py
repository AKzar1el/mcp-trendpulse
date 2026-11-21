"""A05: conservative, offline historical quality evaluation; no forecasting claim.

The input is a pre-reviewed replay manifest. No collector calls, retraining,
implicit labels, or historical data fetching take place here.
"""

from __future__ import annotations

import ipaddress
import json
from collections import defaultdict
from datetime import date, timedelta
from typing import Any
from urllib.parse import parse_qsl, urlsplit

MAX_CASES = 40
MAX_INPUT_BYTES = 160_000
MIN_REVIEWED = 20


def _date(value: Any, field: str) -> date:
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError(f"{field} requires an ISO date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} requires a valid ISO date") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{field} requires an ISO date")
    return parsed


def _public_url(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 700:
        raise ValueError("A bounded public HTTPS reference is required")
    url = urlsplit(value)
    if (url.scheme != "https" or not url.hostname or url.username
            or url.password or url.fragment or url.port not in (None, 443)):
        raise ValueError("A public HTTPS reference is required")
    hostname = url.hostname.lower()
    if hostname == "localhost" or hostname.endswith((".local", ".internal")):
        raise ValueError("Private reference is prohibited")
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        if "." not in hostname:
            raise ValueError("Invalid reference hostname") from None
    else:
        if not ip.is_global:
            raise ValueError("Private reference is prohibited")
    for name, _ in parse_qsl(url.query, keep_blank_values=True):
        if any(x in name.lower() for x in ("token", "secret", "apikey", "password", "auth")):
            raise ValueError("Credential-looking reference is prohibited")
    return value


def _rank(value: Any, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 40:
        raise ValueError(f"{field} must be 1-40 or null (abstain)")
    return value


def evaluate_historical_replay(
    cases: list[dict[str, Any]], *, replay_date: str, k: int = 3,
) -> dict[str, Any]:
    """Compare precomputed v1/v3 ranks on audited, as-of-safe historical cases.

    ``verification=independent`` means external human review is *attested by the
    caller*, never independently verified by this function. Synthetic labels
    exercise correctness but cannot establish empirical predictive utility.
    """
    if not isinstance(cases, list) or len(cases) > MAX_CASES:
        raise ValueError("At most 40 replay cases are allowed")
    if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= 10:
        raise ValueError("k must be an integer from 1 to 10")
    try:
        size = len(json.dumps(cases, ensure_ascii=False, allow_nan=False).encode())
    except (TypeError, ValueError) as exc:
        raise ValueError("Replay input must be JSON") from exc
    if size > MAX_INPUT_BYTES:
        raise ValueError("Replay input exceeds 160 KiB")
    reviewed_on = _date(replay_date, "replay_date")
    if reviewed_on > date.today():
        raise ValueError("Cannot score cases from the future")
    seen: set[tuple[str, str]] = set()
    folds: dict[str, list[dict[str, Any]]] = defaultdict(list)
    excluded_unknown = 0
    excluded_unreviewed = 0
    for entry in cases:
        if not isinstance(entry, dict):
            raise ValueError("Each replay case must be an object")
        ident = entry.get("case_id")
        if not isinstance(ident, str) or not 2 <= len(ident) <= 100 or not ident.isascii():
            raise ValueError("case_id must be a bounded ASCII identifier")
        as_of = _date(entry.get("as_of"), "as_of")
        if as_of >= reviewed_on:
            raise ValueError("Historical cutoff must precede replay date")
        key = (as_of.isoformat(), ident)
        if key in seen:
            raise ValueError("Duplicate case within historical cutoff")
        seen.add(key)
        evidence = entry.get("evidence")
        if not isinstance(evidence, list) or not 1 <= len(evidence) <= 20:
            raise ValueError("A replay case needs 1-20 sourced observations")
        for obs in evidence:
            if not isinstance(obs, dict):
                raise ValueError("Sourced observation must be an object")
            # These fields are projections of the existing v1 TrendSignal contract.
            if not isinstance(obs.get("source_id"), str) or not obs["source_id"]:
                raise ValueError("Missing source identity")
            _public_url(obs.get("source_url"))
            observed = _date(obs.get("source_observed_at"), "source_observed_at")
            published = obs.get("source_published_at")
            if published is not None:
                source_published = _date(published, "source_published_at")
                if source_published > observed:
                    raise ValueError("Source publication cannot follow observation")
            if observed > as_of or (published is not None and source_published > as_of):
                raise ValueError("Future evidence leakage relative to historical cutoff")
        label = entry.get("label")
        if label not in {"positive", "negative", "unknown"}:
            raise ValueError("Label must be positive, negative, or unknown")
        original = _rank(entry.get("v1_rank"), "v1_rank")
        candidate = _rank(entry.get("v3_rank"), "v3_rank")
        if label == "unknown":
            excluded_unknown += 1
            continue
        if entry.get("verification") != "independent":
            excluded_unreviewed += 1
            continue
        known_after = _date(entry.get("known_after"), "known_after")
        verified = _date(entry.get("verified_at"), "verified_at")
        if not as_of < known_after <= verified <= reviewed_on:
            raise ValueError("Invalid outcome chronology or label leakage")
        # Demand/outcome labels must follow a real 30-day forward window.
        if entry.get("label_kind") == "commercial_outcome" and (
            known_after < as_of + timedelta(days=30)
        ):
            raise ValueError("Commercial outcome must follow 30 days")
        if entry.get("label_kind") not in {"commercial_outcome", "evidence_quality"}:
            raise ValueError("A known label_kind is required")
        _public_url(entry.get("ground_truth_url"))
        v1_citation = entry.get("v1_citations_correct")
        v3_citation = entry.get("v3_citations_correct")
        if not isinstance(v1_citation, bool) or not isinstance(v3_citation, bool):
            raise ValueError("Independent reviewer must check both citation sets")
        folds[as_of.isoformat()].append({
            "case_id": ident, "positive": label == "positive",
            "v1_rank": original, "v3_rank": candidate,
            "v1_citations_correct": v1_citation,
            "v3_citations_correct": v3_citation,
            "label_kind": entry["label_kind"],
        })
    for cutoff, group in folds.items():
        for model in ("v1", "v3"):
            ranks = [row[f"{model}_rank"] for row in group
                     if row[f"{model}_rank"] is not None]
            if len(ranks) != len(set(ranks)):
                raise ValueError(f"Duplicate {model} ranks at historical cutoff {cutoff}")
    scored = [v for values in folds.values() for v in values]
    positives = sum(v["positive"] for v in scored)
    negatives = len(scored) - positives
    kind_set = {v["label_kind"] for v in scored}
    basis = {
        "replay_date": reviewed_on.isoformat(), "total_cases": len(cases),
        "independently_attested_cases": len(scored),
        "unknown_cases": excluded_unknown, "unreviewed_cases": excluded_unreviewed,
        "cutoff_count": len(folds), "positive_cases": positives,
        "negative_cases": negatives, "rank_limit": k,
        "caller_attested_ground_truth": True,
        "zero_network_calls": True, "not_success_probability": True,
        "no_calibration_claim": True,
    }
    if (len(scored) < MIN_REVIEWED or len(folds) < 2
            or any(len(group) < 3 for group in folds.values())
            or positives < 5 or negatives < 5 or len(kind_set) != 1):
        return {**basis, "status": "BLOCKED_INSUFFICIENT_COMPARABLE_LABELS",
                "metrics": None}
    metrics: dict[str, Any] = {}
    for name in ("v1", "v3"):
        ranked = [v for v in scored if v[f"{name}_rank"] is not None
                  and v[f"{name}_rank"] <= k]
        true_pos = sum(v["positive"] for v in ranked)
        false_pos = len(ranked) - true_pos
        metrics[name] = {
            "selected": len(ranked), "precision_at_k": (
                round(true_pos / len(ranked), 4) if ranked else None
            ),
            "false_positive_count": false_pos,
            "false_positive_rate_among_negatives": round(false_pos / negatives, 4),
            "abstained": sum(v[f"{name}_rank"] is None for v in scored),
            "citation_correct_fraction": round(
                sum(v[f"{name}_citations_correct"] for v in scored) / len(scored), 4
            ),
        }
    return {**basis, "status": "DESCRIPTIVE_ONLY", "label_kind": next(iter(kind_set)),
            "metrics": metrics, "not_proof_of_predictive_utility": True}
