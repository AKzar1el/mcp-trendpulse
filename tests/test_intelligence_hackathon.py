"""Devpost evidence-gap research: bounded, offline and skeptical of inputs."""
from __future__ import annotations

import copy

import pytest

from mcp_trendpulse.intelligence_hackathon import review_devpost_candidates

DATE = "2026-11-23"


def candidate(**overrides):
    row = {
        "id": "shadow-mcp",
        "name": "ShadowMCP",
        "devpost_url": "https://devpost.com/software/shadowmcp",
        "repo_url": "https://github.com/XaiverTLN/ShadowMCP",
        "problem": "AI tool calls require risk-based permissions",
        "product_type": "github_repo",
        "geography": "US",
        "buyer_hypothesis": "Platform security teams",
        "search_terms": ["MCP security", "agent permissions"],
    }
    row.update(overrides)
    return row


def evidence(kind="project_award", **overrides):
    row = {
        "id": f"example-{kind}",
        "candidate": "shadow-mcp",
        "kind": kind,
        "status": "observed",
        "source_url": "https://devpost.com/software/shadowmcp",
        "observed_at": DATE,
        "published_at": "2026-11-08",
        "note": "Caller reports a named hackathon award",
    }
    row.update(overrides)
    return row


def review(candidates=None, records=None):
    return review_devpost_candidates(
        [candidate()] if candidates is None else candidates,
        [] if records is None else records,
        as_of=DATE,
    )


def test_no_evidence_returns_unknown_gaps_not_an_automatic_build_decision():
    row = review()["results"][0]
    assert row["evidence_status"]["prize_details"] == "not_supplied"
    assert "buyer_discovery" in row["open_evidence_gaps"]
    assert row["success_probability"] is None
    assert row["decision"] == "research_and_independent_validation_required"
    assert not row["buyer_spending_independently_verified"]
    assert not row["project_works_independently_verified"]


def test_award_and_news_do_not_count_as_paid_buyer_or_reproducible_software():
    r = review(records=[
        evidence(),
        evidence("news_headline", id="headline",
                 source_url="https://news.google.com/rss/articles/example",
                 note="A publisher discussed agent safety"),
    ])["results"][0]
    assert r["evidence_status"]["prize_details"] == "source_supplied_not_independently_verified"
    assert r["evidence_status"]["search_or_news_attention"] == "source_supplied_not_independently_verified"
    assert r["evidence_status"]["buyer_discovery"] == "not_supplied"
    assert r["evidence_status"]["independent_functional_test"] == "not_supplied"


def test_unavailable_provider_does_not_turn_into_zero_demand():
    r = review(records=[
        evidence("search_interest", id="throttled", status="unavailable",
                 source_url="", published_at=DATE, note="Google Trends rate limited")
    ])["results"][0]
    assert r["evidence_status"]["search_or_news_attention"] == "source_unavailable_unknown"
    assert r["unavailable_records"] == 1
    assert "search_or_news_attention" in r["open_evidence_gaps"]


def test_missing_publication_date_remains_unknown_instead_of_being_fabricated():
    record = evidence()
    del record["published_at"]
    assert review(records=[record])["results"][0]["provided_evidence_count"] == 1


def test_duplicate_citation_not_double_counted():
    a = evidence()
    b = copy.deepcopy(a)
    b["id"] = "duplicate-second-id"
    result = review(records=[a, b])
    assert result["evidence_count"] == 1
    assert result["duplicate_evidence_ignored"] == 1


def test_buyer_and_paid_pilot_remain_caller_asserted_even_when_links_exist():
    r = review(records=[
        evidence("buyer_interview", id="buyer", source_url="https://example.org/notes/1"),
        evidence("paid_pilot", id="pilot", source_url="https://example.org/receipt/1"),
    ])["results"][0]
    assert r["evidence_status"]["buyer_discovery"] == "source_supplied_not_independently_verified"
    assert r["evidence_status"]["purchase_experiment"] == "source_supplied_not_independently_verified"
    assert r["buyer_spending_independently_verified"] is False
    assert r["success_probability"] is None


def test_contradictory_evidence_suppresses_a_clean_check():
    r = review(records=[
        evidence("independent_test", id="test-a", source_url="https://example.org/test/1"),
        evidence("independent_test", id="test-b", status="contradicted",
                 source_url="https://example.org/test/2"),
    ])["results"][0]
    assert r["evidence_status"]["independent_functional_test"] == "contested_caller_evidence"
    assert r["contradicted_records"] == 1


def test_old_observation_does_not_satisfy_freshness_gate():
    r = review(records=[
        evidence("project_demo", id="demo", observed_at="2023-01-01",
                 published_at="2022-12-01", source_url="https://example.org/old")
    ])["results"][0]
    assert r["stale_records"] == 1
    assert r["evidence_status"]["functioning_demo"] == "not_supplied"


@pytest.mark.parametrize("url", [
    "http://devpost.com/software/shadowmcp",
    "https://devpost.com/users/someone",
    "https://localhost/software/shadowmcp",
    "https://127.0.0.1/software/shadowmcp",
    "https://devpost.com/software/shadowmcp?access_token=abc",
    "https://evil.com/software/shadowmcp",
    "https://devpost.com/software/shadowmcp#something",
])
def test_untrusted_project_urls_rejected(url):
    with pytest.raises(ValueError):
        review(candidates=[candidate(devpost_url=url)])


@pytest.mark.parametrize("url", [
    "https://127.0.0.1/private",
    "https://private.internal/private",
    "http://google.com/no-ssl",
    "https://example.com/?apikey=private",
    "https://example.com/path#fragment",
])
def test_untrusted_evidence_urls_rejected(url):
    with pytest.raises(ValueError):
        review(records=[evidence(source_url=url)])


def test_duplicates_across_devpost_marketing_variants_rejected():
    second = candidate(id="other-case", devpost_url="https://devpost.com/software/shadowmcp/?utm_source=email")
    with pytest.raises(ValueError, match="Duplicate Devpost"):
        review(candidates=[candidate(), second])


def test_duplicate_search_terms_and_non_root_repo_urls_rejected():
    with pytest.raises(ValueError, match="Duplicate candidate search term"):
        review(candidates=[candidate(search_terms=["MCP security", "mcp security"])])
    with pytest.raises(ValueError, match="GitHub repository root"):
        review(candidates=[candidate(repo_url="https://github.com/owner/repo/blob/main/LICENSE")])


@pytest.mark.parametrize("bad_record", [
    {"id": ""},
    {"candidate": "unknown-id"},
    {"kind": "nonexistent"},
    {"status": "verified_purchase"},
    {"published_at": "2026-11-24"},
    {"observed_at": "2026-11-24"},
    {"published_at": "bad-date"},
])
def test_invalid_evidence_fails_closed(bad_record):
    record = evidence(**bad_record)
    with pytest.raises(ValueError):
        review(records=[record])


def test_bounded_input_rejects_many_candidates_and_records():
    candidates = [
        candidate(id=f"case-{i:02d}", devpost_url=f"https://devpost.com/software/example-{i:02d}")
        for i in range(21)
    ]
    with pytest.raises(ValueError, match="1-20"):
        review(candidates=candidates)
    with pytest.raises(ValueError, match="200"):
        review(records=[evidence(id=f"example-{i}") for i in range(201)])


def test_sensitive_notes_rejected_without_echoing_secret():
    secret = "sk-" + "X" * 21
    with pytest.raises(ValueError) as error:
        review(records=[evidence(note=secret)])
    assert secret not in str(error.value)


def test_two_distinct_projects_can_be_compared_without_a_ranking():
    first = candidate()
    second = candidate(
        id="permit-pike", name="PermitPike",
        devpost_url="https://devpost.com/software/permitpike",
        problem="Contractors struggle with municipal permits",
        product_type="saas", buyer_hypothesis="Electrical contractors",
    )
    report = review(candidates=[first, second], records=[])
    assert report["candidate_count"] == 2
    assert report["ranked_business_predictions"] is False
    assert report["network_performed"] is False
    assert all(x["success_probability"] is None for x in report["results"])
