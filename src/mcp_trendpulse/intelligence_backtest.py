"""Leakage-resistant *descriptive* walk-forward evaluation of opportunity triage.

Labels are externally provided and not independently verified. We do not fit
weights or publish calibrated probabilities. A synthetic smoke can test the
temporal protocol but never establish historical prediction quality.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import timedelta
from typing import Any

from mcp_trendpulse.intelligence_opportunities import (
    _day, _safe_url, evaluate_opportunities,
)


def walk_forward_evaluation(
    examples: list[dict[str, Any]], *, k: int = 3,
) -> dict[str, Any]:
    if not isinstance(examples, list) or not 1 <= len(examples) <= 200:
        raise ValueError("Provide 1-200 bounded historical evaluation examples")
    if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= 10:
        raise ValueError("k must be an integer from 1 to 10")
    try:
        if len(json.dumps(examples, ensure_ascii=False).encode("utf-8")) > 180_000:
            raise ValueError("Historical examples exceed 180 KB")
    except (ValueError, TypeError) as exc:
        raise ValueError("Historical examples must be bounded JSON") from exc
    by_cutoff: dict[str, list[dict[str, Any]]] = defaultdict(list)
    invalid = []
    for index, row in enumerate(examples):
        try:
            if not isinstance(row, dict):
                raise ValueError("Historical example must be an object")
            asof = _day(row.get("as_of"), "as_of")
            outcome_at = _day(row.get("outcome_at"), "outcome_at")
            if outcome_at <= asof + timedelta(days=29):
                raise ValueError("Outcome must follow a 30-day forward observation window")
            if row.get("outcome") not in {"paid_pilot", "no_purchase"}:
                raise ValueError("Outcome must be paid_pilot or no_purchase")
            if row.get("outcome_verified") is not True:
                raise ValueError("Outcome must be explicitly attested by data owner")
            _safe_url(row.get("outcome_url"))
            candidate = row.get("candidate")
            evidence = row.get("evidence")
            evaluated = evaluate_opportunities([candidate], evidence, as_of=asof.isoformat())
            decision = evaluated["results"][0]
            if evaluated["rejected_count"]:
                raise ValueError("Historical input contains invalid evidence")
            # Future evidence is discarded, never retrospectively considered.
            by_cutoff[asof.isoformat()].append({
                "id": decision["id"],
                "status": decision["status"],
                "priority": decision["priority_order"],
                "positive": row["outcome"] == "paid_pilot",
                "eligible_at": asof.isoformat(),
                "outcome_at": outcome_at.isoformat(),
            })
        except (ValueError, TypeError, KeyError) as exc:
            invalid.append({"index": index, "reason": str(exc)[:125]})
    if not by_cutoff:
        return {"status": "insufficient_verified_outcomes", "evaluated": 0,
                "rejected_count": len(invalid), "rejected": invalid[:30],
                "not_a_success_probability": True}
    counts = [len(rows) for rows in by_cutoff.values()]
    labels = [item["positive"] for rows in by_cutoff.values() for item in rows]
    if (len(labels) < 8 or len(by_cutoff) < 2 or
            min(sum(labels), len(labels) - sum(labels)) < 2
            or any(n < 3 for n in counts)):
        return {"status": "insufficient_verified_outcomes", "evaluated": len(labels),
                "cutoff_dates": len(by_cutoff), "rejected_count": len(invalid),
                "rejected": invalid[:30], "not_a_success_probability": True}
    folds = []
    for cutoff, entries in sorted(by_cutoff.items()):
        ordered = sorted(entries, key=lambda r: (-r["priority"], r["id"]))
        if len({x["id"] for x in ordered}) != len(ordered):
            raise ValueError("Duplicate candidate within historical cutoff")
        top = ordered[:min(k, len(ordered))]
        folds.append({
            "as_of": cutoff, "candidates": len(entries),
            "prioritized": sum(x["priority"] >= 2 for x in entries),
            "positive_outcomes": sum(x["positive"] for x in entries),
            "top_k": len(top),
            "true_positives_top_k": sum(x["positive"] for x in top),
            "baseline_prevalence": round(sum(x["positive"] for x in entries) / len(entries), 4),
            "precision_at_k": round(sum(x["positive"] for x in top) / len(top), 4),
        })
    positives = sum(x["positive_outcomes"] for x in folds)
    n = sum(x["candidates"] for x in folds)
    top_n = sum(x["top_k"] for x in folds)
    top_true = sum(x["true_positives_top_k"] for x in folds)
    return {
        "status": "descriptive_backtest_only",
        "method": "chronological_as_of_cutoffs_no_model_fitting",
        "n": n,
        "cutoff_dates": len(folds),
        "base_rate": round(positives / n, 4),
        "precision_at_k": round(top_true / top_n, 4),
        "top_k": k,
        "folds": folds,
        "rejected_count": len(invalid),
        "rejected": invalid[:30],
        "labels_user_attested_not_independently_audited": True,
        "selection_bias_possible": True,
        "not_a_success_probability": True,
        "no_calibration_claim": True,
        "next_step": "Audit outcomes and coverage, then compare against honest temporal baselines",
    }
