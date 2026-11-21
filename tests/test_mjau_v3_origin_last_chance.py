"""Final B09 usefulness check, preregistered before scoring.

All public issue facts are from the original GitHub issue metadata. This test
compares actual v1 opportunity scoring to B09 on identical provenance knowledge
and ensures the rejected prototype does not magically discover new lineage.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from mcp_trendpulse.intelligence_opportunities import evaluate_opportunities
from mcp_trendpulse.mjau_v3.origin_graph import audit_origin_evidence

FIXTURE = Path(__file__).parent / "fixtures" / "mjau_v3" / (
    "b09_public_python_sdk_duplicate_issues_20261121.json"
)


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _records() -> tuple[dict, list[dict], list[dict]]:
    source = _fixture()
    issues = {row["issue"]: row for row in source["public_originals"]}
    candidate = {
        "id": "sdk-stdin-worker", "title": "SDK reliability investigation",
        "lane": "developer_reliability", "geography": "GLOBAL",
        "workflow": "incident_triage", "buyer": "",
    }

    def evidence(number: int, origin: int) -> dict:
        row = issues[number]
        return {
            "id": f"issue-{number}", "candidate": candidate["id"],
            "source": "github_issues", "origin_id": f"python-sdk-issue-{origin}",
            "publisher": "modelcontextprotocol", "geography": "GLOBAL",
            "workflow": "incident_triage", "published_at": row["created_at"][:10],
            "observed_at": source["observed_at"], "url": row["url"],
            "polarity": "support",
            "claim": "Public issue report only; not independent buying demand",
        }

    v1 = [evidence(3551, 3551), evidence(3596, 3551), evidence(3100, 3100)]
    records = []
    for number, relation, origin in (
        (3551, "original", 3551),
        (3596, "same_event", 3551),
        (3100, "original", 3100),
    ):
        row = issues[number]
        record = {
            "source_id": "github_issues", "source_record_id": str(number),
            "publisher": "modelcontextprotocol", "source_url": row["url"],
            "published_at": row["created_at"][:10],
            "observed_at": source["observed_at"],
            "origin_relation": relation, "origin_url": issues[origin]["url"],
            "reviewed_origin": True,
        }
        if relation != "original":
            record["lineage_reference_url"] = row["url"]
        records.append(record)
    return candidate, v1, records


def test_real_public_issue_ids_dates_and_explicit_duplicate_link():
    fixture = _fixture()
    issues = {row["issue"]: row for row in fixture["public_originals"]}
    assert set(issues) == {3551, 3596, 3100}
    assert issues[3596]["original_issue"] == 3551
    assert "duplicate of #3551" in issues[3596]["linkage_evidence"]
    assert issues[3596]["created_at"] > issues[3551]["created_at"]
    assert issues[3100]["distinct_from"] == 3551
    assert all(
        row["url"] == f"https://github.com/modelcontextprotocol/python-sdk/issues/{number}"
        for number, row in issues.items()
    )


def test_one_decisive_paired_v1_and_b09_trial_without_extra_provenance(monkeypatch):
    """NO uplift: correct v1 origin_id already handles linked source identities."""
    def no_network(*_args, **_kwargs):
        raise AssertionError("B09 final source replay must not access network")

    monkeypatch.setattr("socket.socket", no_network)
    candidate, evidence, records = _records()
    baseline = evaluate_opportunities(
        [candidate], evidence, as_of=_fixture()["observed_at"]
    )
    assert baseline["rejected_count"] == 0
    original = baseline["results"][0]
    assert original["supporting_origins"] == 2
    assert original["independent_publishers"] == 1
    assert original["ignored_reasons"]["duplicate_origin"] == 1
    assert original["status"] == "monitor"
    assert original["buying_intent_confirmed"] is False

    lineage = audit_origin_evidence(records, as_of=_fixture()["observed_at"])
    assert lineage["status"] == "AUDIT_ONLY"
    assert lineage["verified_original_event_count"] == 2
    assert lineage["dependent_or_same_event_records"] == 1
    assert lineage["verified_independent_original_publishers"] == 1
    assert lineage["unresolved_origin_records"] == 0
    assert sorted(
        tuple(group["record_ids"]) for group in lineage["origins"]
    ) == [
        ("github_issues:3100",),
        ("github_issues:3551", "github_issues:3596"),
    ]
    assert lineage["no_market_demand_inference"] is True

    # B09 does not improve on either existing true origin or duplicate
    # detection; it merely re-expresses the same operator-supplied linkage.
    assert original["supporting_origins"] == lineage["verified_original_event_count"]
    assert original["ignored_reasons"]["duplicate_origin"] == (
        lineage["dependent_or_same_event_records"]
    )


def test_unreviewed_b09_link_abstains_while_v1_already_deduplicates():
    candidate, evidence, records = _records()
    unreviewed = copy.deepcopy(records)
    unreviewed[1]["reviewed_origin"] = False
    baseline = evaluate_opportunities(
        [candidate], evidence, as_of=_fixture()["observed_at"]
    )
    trial = audit_origin_evidence(unreviewed, as_of=_fixture()["observed_at"])
    assert baseline["results"][0]["supporting_origins"] == 2
    assert baseline["results"][0]["status"] == "monitor"
    assert trial["verified_original_event_count"] == 2
    assert trial["dependent_or_same_event_records"] == 0
    assert trial["unresolved_origin_records"] == 1
    assert trial["ignored"]["unreviewed_origin_claim"] == 1
    assert trial["caller_attested_lineage_not_automatically_proved"] is True


def test_b09_without_additional_human_review_does_not_correct_naive_ids():
    candidate, evidence, records = _records()
    naive = copy.deepcopy(evidence)
    naive[1]["origin_id"] = "python-sdk-issue-3596"
    baseline = evaluate_opportunities(
        [candidate], naive, as_of=_fixture()["observed_at"]
    )
    assert baseline["results"][0]["supporting_origins"] == 3
    assert baseline["results"][0]["status"] == "monitor"
    unreviewed = copy.deepcopy(records)
    unreviewed[1]["reviewed_origin"] = False
    trial = audit_origin_evidence(unreviewed, as_of=_fixture()["observed_at"])
    assert trial["dependent_or_same_event_records"] == 0
    assert trial["unresolved_origin_records"] == 1
    # Correcting the naive origin IDs still requires the same explicit source
    # relationship already available to the v1 caller.
    assert trial["verified_original_event_count"] == 2
