"""Offline tests for Wave 2; no real ATS, financial or research API calls."""

import pytest
from mcp_trendpulse.intelligence_core import IntelligenceError, plan_source
from mcp_trendpulse.intelligence_jobs import normalize_jobs, extract_job_pains


def test_public_board_plans_fixed_hosts():
    for name in ("greenhouse", "lever", "ashby", "smartrecruiters"):
        plan = plan_source(name, company="example-board", limit=5)
        assert plan.method == "GET"
        assert "example-board" in plan.url
        assert plan.budget_per_day <= 20


def test_free_but_not_unbounded_sources():
    plan = plan_source("openalex", keyword="care coordination", limit=5)
    assert plan.budget_per_day == 5
    assert "api.openalex.org" in plan.url
    with pytest.raises(IntelligenceError):
        plan_source("companies_house", keyword="example", env={})
    with pytest.raises(IntelligenceError):
        plan_source("sec_companyfacts", identifier="1", env={})


def test_sec_identity_and_header_redaction():
    p = plan_source(
        "sec_companyfacts", identifier="320193",
        env={"TRENDPULSE_INTEL_SEC_USER_AGENT": "Researcher Contact research@example.org"}
    )
    assert "CIK0000320193.json" in p.url
    assert p.public()["headers"]["User-Agent"] == "<configured>"


def test_job_normalization_and_pain_evidence():
    board = {"jobs": [
        {"id": "a", "title": "Operations Specialist", "content":
         "<p>Maintain manual spreadsheets, reconcile data and support compliance audits.</p>",
         "absolute_url": "https://job-boards.greenhouse.io/example/jobs/a"},
        {"id": "a", "title": "Duplicate", "content": "Manual work"},
    ]}
    jobs = normalize_jobs("greenhouse", "testco", board)
    assert len(jobs) == 1
    result = extract_job_pains(jobs)
    assert result["descriptions_examined"] == 1
    categories = {x["category"] for x in result["pain_hypotheses"]}
    assert {"manual_work", "compliance"}.issubset(categories)
    assert result["pain_hypotheses"][0]["examples"][0]["company"] == "testco"
    assert "not proof" in result["pain_hypotheses"][0]["interpretation"]


def test_no_fabricated_posting_pains():
    jobs = normalize_jobs("lever", "example", [{"id": "123", "text": "Engineer", "hostedUrl": "https://jobs.lever.co/test/123"}])
    report = extract_job_pains(jobs)
    assert report["descriptions_examined"] == 0
    assert report["pain_hypotheses"] == []
    assert report["postings_received"] == 1


def test_changed_cfpb_contract_is_fail_closed():
    with pytest.raises(IntelligenceError, match="not fetch-enabled"):
        plan_source("cfpb", keyword="credit")


def test_live_usaspending_request_is_bounded_and_contract_shaped():
    p = plan_source("usaspending", keyword="battery manufacturing", limit=4)
    assert p.method == "POST"
    assert p.url == "https://api.usaspending.gov/api/v2/search/spending_by_award/"
    assert p.body["filters"]["keywords"] == ["battery manufacturing"]
    assert p.body["filters"]["award_type_codes"] == ["A", "B", "C", "D"]
    assert p.body["limit"] == 4
    assert p.body["sort"] in p.body["fields"]


def test_sec_companyconcept_is_scoped():
    env = {"TRENDPULSE_INTEL_SEC_USER_AGENT": "Research Contact research@example.org"}
    p = plan_source("sec_companyconcept", identifier="320193", keyword="Assets", env=env)
    assert p.url.endswith("/CIK0000320193/us-gaap/Assets.json")
    with pytest.raises(IntelligenceError):
        plan_source("sec_companyconcept", identifier="320193", keyword="../../bad", env=env)
