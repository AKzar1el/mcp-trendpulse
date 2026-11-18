"""Exhaustive offline reliability checks for the 18 opt-in source recipes.

All scenarios are invented fixtures: they are NOT market evidence.
"""
from __future__ import annotations

import pytest

from mcp_trendpulse.intelligence_opportunities import (
    LANES, evaluate_opportunities,
)


def sample(lane):
    candidate = {
        "id": "example-workflow", "title": "Illustrative research hypothesis",
        "lane": lane, "geography": "US", "workflow": "costly_process",
        "buyer": "", "buyer_entity": "",
    }
    evidence = [
        {
            "id": f"evidence-{index}", "candidate": "example-workflow",
            "source": source, "origin_id": f"origin-{index}",
            "publisher": f"publisher-{index}",
            "geography": "US", "workflow": "costly_process",
            "url": f"https://example.org/observations/{index}",
            "published_at": "2026-11-05", "observed_at": "2026-11-06",
            "polarity": "support", "claim": "Synthetic provider fixture",
        }
        for index, source in enumerate(LANES[lane]["sources"], start=1)
    ]
    return candidate, evidence


def evaluate(candidate, evidence, health=None):
    return evaluate_opportunities(
        [candidate], evidence, source_health=health, as_of="2026-11-18",
    )["results"][0]


@pytest.mark.parametrize("lane", sorted(LANES))
def test_every_recipe_requires_real_buyer_proof_before_commercial_priority(lane):
    candidate, evidence = sample(lane)
    healthy = {source: "ok" for source in LANES[lane]["sources"]}
    baseline = evaluate(candidate, evidence, healthy)
    assert baseline["priority_order"] <= 2
    assert baseline["buying_intent_confirmed"] is False
    assert baseline["success_probability"] is None
    assert baseline["provider_health_reported_ok"] is True
    assert not baseline["trend"]["status"].startswith("rising")

    # Each lane must abstain under provider failure without manufacturing a
    # positive signal from cached/empty observations.
    broken = dict(healthy)
    broken[LANES[lane]["sources"][0]] = "invalid_source_shape"
    degraded = evaluate(candidate, evidence, broken)
    assert degraded["priority_order"] <= 1
    assert degraded["provider_health_reported_ok"] is False
    assert degraded["ignored_reasons"].get("unhealthy_provider") == 1

    contradictory = {
        **evidence[0], "id": "contradiction", "origin_id": "contradiction",
        "publisher": "independent-countervoice",
        "url": "https://example.org/observations/counter",
        "polarity": "against",
    }
    disputed = evaluate(candidate, evidence + [contradictory], healthy)
    assert disputed["status"] in {"contested", "conflict_review"}
    assert disputed["priority_order"] == 0

    future = {
        **evidence[0], "id": "future-observation", "origin_id": "future-origin",
        "publisher": "future-publisher",
        "url": "https://example.org/observations/future",
        "published_at": "2027-01-01", "observed_at": "2027-01-02",
    }
    retrospective = evaluate(candidate, evidence + [future], healthy)
    assert retrospective["priority_order"] == baseline["priority_order"]
    assert retrospective["ignored_reasons"].get("future_or_unobserved") == 1
