"""A05 deterministic guardrails. These tests use synthetic labels, not proof."""
import pytest
from mcp_trendpulse.mjau_v3.historical import evaluate_historical_replay


def sample(i, *, kind="evidence_quality"):
    as_of = "2026-01-15" if i < 12 else "2026-02-15"
    after = "2026-03-20"
    return {
        "case_id": f"case-{i}", "as_of": as_of,
        "evidence": [{"source_id": "github_issues", "source_url":
                      f"https://github.com/example/repo/issues/{i+1}",
                      "source_observed_at": as_of, "source_published_at": as_of}],
        "label": "positive" if i % 2 else "negative",
        "label_kind": kind, "verification": "independent",
        "known_after": after, "verified_at": "2026-04-10",
        "ground_truth_url": f"https://github.com/example/repo/issues/{i+1}",
        "v1_rank": (1 + (i % 12) // 2) if i % 2 else (7 + (i % 12) // 2),
        "v3_rank": i % 12 + 1,
        "v1_citations_correct": True, "v3_citations_correct": i % 3 != 0,
    }


def test_empty_is_blocked_not_zero_accuracy():
    got = evaluate_historical_replay([], replay_date="2026-11-21")
    assert got["status"].startswith("BLOCKED")
    assert got["metrics"] is None


def test_unverified_unknown_is_not_a_negative_label():
    row = sample(0)
    row["label"] = "unknown"
    row["verification"] = "unreviewed"
    got = evaluate_historical_replay([row], replay_date="2026-11-21")
    assert got["negative_cases"] == 0
    assert got["unknown_cases"] == 1


def test_independent_comparable_cases_produce_descriptive_metrics():
    got = evaluate_historical_replay(
        [sample(i) for i in range(24)], replay_date="2026-11-21")
    assert got["status"] == "DESCRIPTIVE_ONLY"
    assert got["metrics"]["v1"]["precision_at_k"] == 1.0
    assert got["metrics"]["v3"]["false_positive_count"] > 0
    assert got["not_success_probability"]


def test_future_source_evidence_rejected():
    row = sample(1)
    row["evidence"][0]["source_observed_at"] = "2026-12-01"
    with pytest.raises(ValueError, match="Future evidence"):
        evaluate_historical_replay([row], replay_date="2026-11-21")


def test_duplicate_cutoff_case_rejected():
    row = sample(1)
    with pytest.raises(ValueError, match="Duplicate"):
        evaluate_historical_replay([row, row], replay_date="2026-11-21")


def test_label_known_at_cutoff_rejected():
    row = sample(1)
    row["known_after"] = row["as_of"]
    with pytest.raises(ValueError, match="chronology"):
        evaluate_historical_replay([row], replay_date="2026-11-21")


def test_secret_query_rejected_without_leakage():
    row = sample(1)
    row["evidence"][0]["source_url"] += "?token=abc"
    with pytest.raises(ValueError, match="Credential-looking") as exc:
        evaluate_historical_replay([row], replay_date="2026-11-21")
    assert "abc" not in str(exc.value)


def test_unsupported_rank_fails_closed():
    row = sample(0)
    row["v1_rank"] = True
    with pytest.raises(ValueError, match="v1_rank"):
        evaluate_historical_replay([row], replay_date="2026-11-21")


def test_unreviewed_labels_do_not_score():
    row = sample(0)
    row["verification"] = "unreviewed"
    got = evaluate_historical_replay([row], replay_date="2026-11-21")
    assert got["independently_attested_cases"] == 0
    assert got["unreviewed_cases"] == 1


def test_commercial_outcome_requires_forward_window():
    row = sample(0, kind="commercial_outcome")
    row["known_after"] = "2026-01-25"
    with pytest.raises(ValueError, match="30 days"):
        evaluate_historical_replay([row], replay_date="2026-11-21")


def test_mixed_labels_are_not_commensurable():
    rows = [sample(i) for i in range(24)]
    rows[0]["label_kind"] = "commercial_outcome"
    got = evaluate_historical_replay(rows, replay_date="2026-11-21")
    assert got["metrics"] is None


def test_bounded_request():
    with pytest.raises(ValueError, match="At most"):
        evaluate_historical_replay([sample(i) for i in range(41)],
                                  replay_date="2026-11-21")


def test_duplicate_ranks_at_one_cutoff_rejected():
    rows = [sample(i) for i in range(24)]
    rows[1]["v1_rank"] = rows[3]["v1_rank"]
    with pytest.raises(ValueError, match="Duplicate v1 ranks"):
        evaluate_historical_replay(rows, replay_date="2026-11-21")


def test_source_publication_after_observation_is_rejected():
    row = sample(1)
    row["evidence"][0]["source_published_at"] = "2026-01-16"
    with pytest.raises(ValueError, match="Source publication"):
        evaluate_historical_replay([row], replay_date="2026-11-21")


def test_per_model_citation_accuracy_is_reported_independently():
    rows = [sample(i) for i in range(24)]
    result = evaluate_historical_replay(rows, replay_date="2026-11-21")
    assert result["metrics"]["v1"]["citation_correct_fraction"] == 1.0
    assert result["metrics"]["v3"]["citation_correct_fraction"] < 1.0
