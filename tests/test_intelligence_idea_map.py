"""Seedless product hypotheses and source-to-keyword provenance guardrails."""
from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from click.testing import CliRunner

from mcp_trendpulse import intelligence_discovery as discovery
from mcp_trendpulse import intelligence_idea_map as ideas
from mcp_trendpulse.cli import cli

DAY = date.today()
NOW = DAY.isoformat()


def tender():
    return {
        "kind": "published_software_it_procurement_to_investigate",
        "brief_id": "00112233445566", "source_published_workflow_clue": "Germany – Finanzsoftware",
        "buyer_country_code": "DEU", "published_buyer_label": "Landkreis Example",
        "published_lot_date_on_or_after_analysis": True,
        "sampled_original_record_count": 1,
        "evidence": [{"reference": "https://ted.europa.eu/en/notice/-/detail/781080-2026",
                      "date": NOW, "source": "ted"}],
        "published_scope_context": {
            "status": "observed_scope_excerpts",
            "procedure_description": [
                {"language": "deu", "excerpt":
                 "Einführung einer neuen integrierten Finanz- und Haushaltssoftware einschließlich Liegenschafts- und Gebäudemanagement (CAFM)"}
            ],
            "lot_title_excerpts_without_lot_identity": [
                {"language": "deu", "excerpt": "Finanzsoftware"}
            ],
        },
    }


def complaint():
    return {
        "kind": "recurring_public_consumer_issue_to_investigate",
        "brief_id": "fedcba98765432",
        "source_published_workflow_clue":
            "Credit reporting — Incorrect information on your report",
        "consumer_issue_source_category":
            "Credit reporting — Incorrect information on your report",
        "sampled_original_record_count": 7,
        "evidence": [{"reference": ideas.CFPB_REF, "date": NOW, "source": "cfpb"}],
    }


def source(briefs=None):
    return {
        "as_of": NOW,
        "workflow_briefs": {
            "mode": "source_grounded_workflow_briefs_not_validated_market_demand",
            "briefs": [tender(), complaint()] if briefs is None else briefs,
        },
    }


def test_idea_dossiers_honor_source_geography_lexical_and_unknown_market_metrics():
    result = ideas.build_idea_map(source())
    assert result["idea_count"] == 2
    assert result["source_requests_added"] == 0
    assert result["no_predefined_industry_seed_list"] is True
    de, us = result["ideas"]
    assert de["geography"]["country_code"] == "DE"
    assert de["scope_excerpt_present"] is True
    assert de["source_reference"].endswith("781080-2026")
    assert de["buyer_willingness_to_pay_verified"] is False
    assert any("finanzsoftware" in kw["keyword"] for kw in de["keyword_hypotheses"])
    assert any(kw["basis"] == "contiguous_published_ted_scope_phrase" for kw in de["keyword_hypotheses"])
    assert us["geography"]["country_code"] == "US"
    assert us["sampled_source_records"] == 7
    assert us["keyword_hypotheses"][0]["keyword"] == "incorrect information on your report"
    assert all(kw["search_volume"] is None and not kw["observed_as_actual_search_query"]
               for row in result["ideas"] for kw in row["keyword_hypotheses"])
    assert all(not x["market_growth_verified"] for x in result["ideas"])
    assert "keyword hypothesis" in "\n".join(ideas.format_idea_map(result)).lower()


@pytest.mark.parametrize(("source_iso3", "expected_iso2"), [
    ("CHE", "CH"), ("EST", "EE"), ("HUN", "HU"), ("LTU", "LT"),
    ("DEU", "DE"), ("GRC", "GR"), ("SVN", "SI"), ("ZZZ", ""),
])
def test_ted_buyer_country_mapping_is_explicit_not_search_demand(
    source_iso3, expected_iso2,
):
    proof = tender()
    proof["buyer_country_code"] = source_iso3
    result = ideas.build_idea_map(source([proof]))
    geography = result["ideas"][0]["geography"]
    assert geography["country_code"] == expected_iso2
    assert geography["source_buyer_country_iso3"] == source_iso3
    assert geography["source_market_geo_mapping"] == (
        "known_iso3_to_iso2" if expected_iso2
        else "unknown_source_country_not_guessed"
    )
    assert result["ideas"][0]["keyword_search_volume_verified"] is False


def test_no_buyer_invention_no_secret_raw_source_reuse_or_stale_tender():
    stale = tender()
    stale["published_lot_date_on_or_after_analysis"] = False
    stale["source_published_workflow_clue"] = "PRIVATE_SECRET"
    bad = complaint()
    bad["evidence"] = [{"reference": "https://other.invalid/hidden=SECRET", "date": NOW}]
    result = ideas.build_idea_map(source([stale, bad]))
    assert result["idea_count"] == 0
    assert "PRIVATE_SECRET" not in repr(result)
    assert "other.invalid" not in repr(result)


def test_normalized_trend_series_only_attaches_exact_term_and_target_country():
    observed = ideas.build_idea_map(source())
    term = observed["ideas"][1]["keyword_hypotheses"][0]["keyword"]
    points = [
        {"date": (DAY - timedelta(days=9-i)).isoformat(), "value": 10+i*4}
        for i in range(10)
    ]
    report = ideas.build_idea_map(
        source(), keyword_evidence={"keyword": term, "market": "US", "points": points},
    )
    entry = report["ideas"][1]["keyword_hypotheses"][0]
    assert entry["normalized_series_observation_count"] == 10
    assert entry["growth_percent_in_user_series"] is not None
    assert entry["search_volume"] is None
    assert entry["market_search_evidence_verified"] is False
    assert entry["series_provenance"] == "operator_supplied_unverified_source"
    assert report["keyword_evidence"]["attached_idea_count"] == 1
    mismatch = ideas.build_idea_map(
        source(), keyword_evidence={"keyword": term, "market": "DE", "points": points},
    )
    assert mismatch["keyword_evidence"]["attached_idea_count"] == 0


def test_bad_keyword_series_invalid_finite_and_oversize_rejected():
    term = "incorrect information on your report"
    with pytest.raises(ValueError):
        ideas.build_idea_map(source(), keyword_evidence={
            "keyword": term, "market": "US",
            "points": [{"date": NOW, "value": float("nan")}],
        })
    with pytest.raises(ValueError):
        ideas.build_idea_map(source(), keyword_evidence={
            "keyword": term, "market": "US", "points": [],
            "access_token": "PRIVATE_KEY",
        })
    with pytest.raises(ValueError):
        ideas.build_idea_map(source(), keyword_evidence={
            "keyword": term, "market": "US",
            "points": [{"date": NOW, "value": 1}] * 530,
        })


def test_opt_in_plan_and_no_network_default(monkeypatch):
    monkeypatch.setattr(discovery, "collect", lambda *_a, **_kw: (
        (_ for _ in ()).throw(AssertionError("plan must remain offline"))
    ))
    plain = discovery.discover_current(execute=False, env={})
    assert "idea_map" not in plain
    with pytest.raises(ValueError, match="idea-map"):
        discovery.discover_current(execute=False, idea_map=True, env={})
    plan = discovery.discover_current(execute=False, workflow_briefs=True,
                                      idea_map=True, env={})
    assert plan["request_count"] == 3
    assert plan["idea_map"]["source_requests_added"] == 0


def test_live_discovery_with_idea_map_only_reuses_baseline(monkeypatch):
    def fake_collect(plan, **_kw):
        data = []
        if plan.source == "cfpb":
            data = [
                {"public_complaint_id": str(101+i), "product": "Credit reporting",
                 "issue": "Incorrect information on your report", "date_received": NOW}
                for i in range(2)
            ]
        return {"source": plan.source, "status": "observed",
                "observations": {"sample": data, "record_count": len(data)}}
    seen = []
    def record(plan, **kw):
        seen.append(plan.source)
        return fake_collect(plan, **kw)
    monkeypatch.setattr(discovery, "collect", record)
    result = discovery.discover_current(execute=True, workflow_briefs=True,
                                        idea_map=True, env={})
    assert seen == ["openalex", "cfpb", "ted"]
    assert result["queries_budgeted"] == 3
    assert result["idea_map"]["idea_count"] == 1
    assert "PROJECT IDEA + KEYWORD" in discovery.format_discovery_report(result)


def test_cli_option_and_locally_supplied_keyword_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(discovery, "collect", lambda *_a, **_kw: (
        (_ for _ in ()).throw(AssertionError("plan-only CLI should not fetch"))
    ))
    runner = CliRunner()
    res = runner.invoke(cli, ["intelligence", "discover", "--workflow-briefs",
                              "--idea-map", "--format", "json"])
    assert res.exit_code == 0, res.output
    value = json.loads(res.output)
    assert value["idea_map"]["source_requests_added"] == 0
    wrong = runner.invoke(cli, ["intelligence", "discover", "--idea-map"])
    assert wrong.exit_code != 0
    path = tmp_path / "keyword.json"
    path.write_text(json.dumps({"keyword": "credit reporting",
                                "market": "US", "points": []}), encoding="utf-8")
    plan_only = runner.invoke(cli, ["intelligence", "discover", "--workflow-briefs",
                                    "--idea-map", "--keyword-evidence-file", str(path)])
    assert plan_only.exit_code == 0, plan_only.output
    oversize = tmp_path / "large.json"
    oversize.write_text("x" * (ideas.MAX_EVIDENCE_BYTES + 1), encoding="utf-8")
    bad = runner.invoke(cli, ["intelligence", "discover", "--workflow-briefs", "--idea-map",
                              "--keyword-evidence-file", str(oversize)])
    assert bad.exit_code != 0
