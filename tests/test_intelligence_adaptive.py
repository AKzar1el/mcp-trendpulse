from datetime import date
import sqlite3

import pytest
from fastmcp import Client

from mcp_trendpulse import intelligence_adaptive as adaptive
from mcp_trendpulse.intelligence_mcp import intel_mcp


def _report(sources, number=1, title="Battery recycling", *, failed=()):
    return {"topics": [{
        "evidence": [{"source": s, "id": str(number), "title": title,
                      "event_date": date.today().isoformat(), "reference": "https://openalex.org/W12345"}
                     for s in sources if s not in failed],
        "source_coverage": [{"source": s, "status": "unavailable" if s in failed else "observed",
                             "recent_eligible_matches": 0 if s in failed else 1}
                            for s in sources],
    }]}


def test_plan_only_does_not_create_history_or_fetch(monkeypatch, tmp_path):
    calls = []

    def plan(topics, sources, **kwargs):
        calls.append(kwargs["execute"])
        return {"status": "planned"}

    monkeypatch.setattr(adaptive, "hunt_current", plan)
    db = tmp_path / "history.sqlite"
    result = adaptive.adaptive_hunt("battery recycling", ["openalex"], session_id="test",
                                   history_path=db, max_passes=3)
    assert result["network_performed"] is False
    assert not db.exists()
    assert calls == [False]


def test_only_healthy_weak_sources_and_no_duplicate_strategy(monkeypatch):
    calls = []

    def fake(topics, sources, **kwargs):
        calls.append((topics, sources, kwargs["sample_limit"], kwargs["relevance_first"]))
        return _report(sources, failed=("cordis",))

    monkeypatch.setattr(adaptive, "hunt_current", fake)
    result = adaptive.adaptive_hunt("battery recycling", ["openalex", "cordis"],
                                   execute=True, max_passes=3)
    assert len(calls) == 2
    assert calls[1][1:] == (["openalex"], 10, True)
    assert result["request_slots_used"] == 3
    assert result["stop_reason"] == "no_new_preview_evidence"
    assert result["distinct_preview_revisions_seen"] == 1
    assert result["passes"][1]["duplicate_preview_records"] == 1


def test_explicit_variants_exclusions_and_conflict_preserved(monkeypatch):
    calls = []

    def fake(topics, sources, **kwargs):
        calls.extend(topics)
        return _report(sources, title="Battery recycling" if len(calls) == 1 else "Battery recovery")

    monkeypatch.setattr(adaptive, "hunt_current", fake)
    result = adaptive.adaptive_hunt("battery recycling", ["openalex"], execute=True,
                                   alternate_queries=["battery recovery"], max_passes=2)
    assert calls == ["battery recycling", "battery recovery"]
    assert result["passes"][1]["conflicting_preview_records"] == 1
    assert len(result["new_evidence_preview"]) == 2
    excluded = adaptive.adaptive_hunt("battery recycling", ["openalex"], execute=True,
                                     exclude_terms=["battery"], max_passes=1)
    assert excluded["passes"][0]["excluded_preview_records"] == 1
    assert not excluded["new_evidence_preview"]


def test_same_doi_different_provider_record_id_is_duplicate(monkeypatch):
    calls = []

    def fake(topics, sources, **kwargs):
        calls.append(1)
        result = _report(sources, number=len(calls))
        result["topics"][0]["evidence"][0]["doi"] = "10.1002/adma.201404892"
        return result

    monkeypatch.setattr(adaptive, "hunt_current", fake)
    result = adaptive.adaptive_hunt("battery recycling", ["openalex"], execute=True, max_passes=2)
    assert result["distinct_preview_revisions_seen"] == 1
    assert result["passes"][1]["duplicate_preview_records"] == 1


def test_resume_completed_pass_and_rotate_versions(monkeypatch, tmp_path):
    calls = []
    db = tmp_path / "history.sqlite"

    def interrupted(topics, sources, **kwargs):
        calls.append(topics)
        if len(calls) == 2:
            raise RuntimeError("simulated interrupted pass")
        return _report(sources)

    monkeypatch.setattr(adaptive, "hunt_current", interrupted)
    opts = dict(sources=["openalex"], execute=True, max_passes=2, session_id="test", history_path=db)
    with pytest.raises(RuntimeError):
        adaptive.adaptive_hunt("battery recycling", **opts)
    result = adaptive.adaptive_hunt("battery recycling", resume=True, **opts)
    assert result["completed_passes_before_resume"] == 1
    assert result["stop_reason"] == "interrupted_pass_unknown"
    assert result["unconfirmed_attempts"] == 1
    assert len(calls) == 2
    before = len(calls)
    again = adaptive.adaptive_hunt("battery recycling", resume=True, **opts)
    assert len(calls) == before
    assert again["request_slots_used"] == 2
    for _ in range(11):
        adaptive.adaptive_hunt("battery recycling", **{**opts, "max_passes": 1})
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM adaptive_hunter_sessions").fetchone()[0] == 10
    assert b"Battery recycling" not in db.read_bytes()
    assert b"https://openalex.org" not in db.read_bytes()


def test_budget_and_config_validation(monkeypatch):
    monkeypatch.setattr(adaptive, "hunt_current", lambda *a, **kw: pytest.fail("No plan or request expected"))
    for opts in [{"request_budget": 0}, {"max_passes": 4}, {"resume": True},
                 {"alternate_queries": ["battery recycling"]}, {"exclude_terms": ["bad/term"]}]:
        with pytest.raises(ValueError):
            adaptive.adaptive_hunt("battery recycling", ["openalex"], **opts)


async def test_adaptive_mcp_plan_only():
    async with Client(intel_mcp) as client:
        result = await client.call_tool("intelligence_hunt_current", {
            "topics": ["battery recycling"], "sources": ["openalex"],
            "adaptive_passes": 2, "request_budget": 2,
        })
    assert result.structured_content["network_performed"] is False
    assert result.structured_content["maximum_request_slots"] == 2
