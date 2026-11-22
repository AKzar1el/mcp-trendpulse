"""Historical ranking tests only: all provided 'paid' labels are synthetic."""

from __future__ import annotations

import copy

import pytest

from mcp_trendpulse.intelligence_backtest import walk_forward_evaluation


def example(number: int, cutoff: str, paid: bool):
    # Documentation and tests never claim these synthetic data are customers.
    candidate_id = f"synthetic-{number}"
    return {
        "candidate": {
            "id": candidate_id,
            "title": "Incident automation",
            "lane": "developer_reliability", "workflow": "incident_triage",
            "geography": "US", "buyer": "Public agencies",
        },
        "as_of": cutoff,
        "evidence": [
            {
                "id": f"synthetic-e-{number}-{i}", "candidate": candidate_id,
                "source": src,
                "origin_id": f"synthetic-o-{number}-{i}",
                "publisher": f"synthetic-pub-{i}", "workflow": "incident_triage",
                "geography": "US", "published_at": "2026-02-01",
                "observed_at": "2026-02-02",
                "url": f"https://example.org/label/{number}/{i}",
                "claim": "Synthetic provider fixture", "polarity": "support",
            }
            for i, src in enumerate(("github_issues", "greenhouse_job", "usaspending"))
        ] if number % 2 == 0 else [
            {
                "id": f"synthetic-e-{number}-0", "candidate": candidate_id,
                "source": "github_issues",
                "origin_id": f"synthetic-o-{number}-0",
                "publisher": "synthetic-pub-x", "workflow": "incident_triage",
                "geography": "US", "published_at": "2026-02-01",
                "observed_at": "2026-02-02", "polarity": "support",
                "url": "https://example.org/label/other",
                "claim": "Illustrative weak evidence",
            }
        ],
        "outcome_at": "2026-08-15",
        "outcome": "paid_pilot" if paid else "no_purchase",
        "outcome_verified": True,
        "outcome_url": f"https://example.org/outcomes/{number}",
    }


def eight():
    return [
        example(i, "2026-03-01" if i < 4 else "2026-04-01", i in (0, 2, 4, 6))
        for i in range(8)
    ]


def test_time_split_evaluation_is_descriptive_not_calibrated():
    result = walk_forward_evaluation(eight(), k=2)
    assert result["status"] == "descriptive_backtest_only"
    assert result["n"] == 8
    assert result["cutoff_dates"] == 2
    assert len(result["folds"]) == 2
    assert result["labels_user_attested_not_independently_audited"]
    assert result["no_calibration_claim"]
    assert result["not_a_success_probability"]
    assert result["base_rate"] == 0.5


def test_future_evidence_never_boosts_past_snapshot():
    base = eight()
    original = walk_forward_evaluation(base)
    changed = copy.deepcopy(base)
    extra = copy.deepcopy(changed[1]["evidence"][0])
    extra.update({"id": "synthetic-future-1", "origin_id": "synthetic-future-o",
                  "publisher": "synthetic-future-p", "published_at": "2026-06-01",
                  "observed_at": "2026-06-03"})
    changed[1]["evidence"].append(extra)
    after = walk_forward_evaluation(changed)
    assert after["folds"] == original["folds"]
    assert after["precision_at_k"] == original["precision_at_k"]


def test_insufficient_real_labels_do_not_produce_marketing_accuracy():
    result = walk_forward_evaluation(eight()[:3])
    assert result["status"] == "insufficient_verified_outcomes"
    assert "precision_at_k" not in result


@pytest.mark.parametrize(("key", "value"), [
    ("outcome_verified", False), ("outcome_at", "2026-03-05"),
    ("outcome", "funded_unicorn"), ("outcome_url", "http://localhost/hidden"),
])
def test_invalid_labels_are_not_counted(key, value):
    rows = eight()
    rows[0][key] = value
    result = walk_forward_evaluation(rows)
    assert result["rejected_count"] == 1
    assert result["status"] == "invalid_historical_labels"


def test_omitted_polarity_blocks_historical_backtest_metrics():
    rows = eight()
    rows[0]["evidence"][2].pop("polarity")
    result = walk_forward_evaluation(rows)
    assert result["status"] == "invalid_historical_labels"
    assert result["rejected_count"] == 1
    assert "precision_at_k" not in result


def test_duplicate_candidate_at_cutoff_fails_closed():
    rows = eight()
    rows[1]["candidate"]["id"] = rows[0]["candidate"]["id"]
    # Alter evidence ownership to keep each snapshot internally consistent.
    for item in rows[1]["evidence"]:
        item["candidate"] = rows[0]["candidate"]["id"]
    with pytest.raises(ValueError, match="Duplicate candidate"):
        walk_forward_evaluation(rows)


def test_unsupported_k_and_oversize_are_rejected():
    with pytest.raises(ValueError):
        walk_forward_evaluation(eight(), k=0)
    with pytest.raises(ValueError):
        walk_forward_evaluation(eight(), k=True)
    with pytest.raises(ValueError):
        walk_forward_evaluation(eight() * 30)



def test_duplicate_historical_outcome_is_not_counted_twice():
    rows = eight()
    rows[1]["outcome_url"] = rows[0]["outcome_url"]
    result = walk_forward_evaluation(rows)
    assert result["rejected_count"] == 1
    assert result["status"] == "invalid_historical_labels"


def test_future_claimed_sales_label_is_rejected():
    rows = eight()
    rows[0]["outcome_at"] = "2030-01-01"
    result = walk_forward_evaluation(rows)
    assert result["rejected_count"] == 1
    assert result["status"] == "invalid_historical_labels"
