"""Offline adversarial issue-quality classification with no AI or provider calls."""
from __future__ import annotations

import pytest

from mcp_trendpulse.intelligence_issue_quality import (
    EXCLUDED_FROM_CURRENT_HUNT, classify_github_issue,
)
from mcp_trendpulse.intelligence_evidence import evidence_projection


@pytest.mark.parametrize(("title", "body", "url", "expected"), [
    (
        "Automotive Battery Recycling Market to Reach USD 29.78 Billion by 2034",
        "Projected compound annual growth rate of 35 percent.",
        "https://github.com/user/market/issues/90",
        "promotional_market_claim",
    ),
    (
        "Battery Recycling Market Forecast 2027",
        "Projections and CAGRs",
        "https://github.com/user/market/issues/11",
        "promotional_market_claim",
    ),
    (
        "Zion Metric dimensional yield definitions for battery recycling research",
        "A hypothetical research consortium proposes an architecture.",
        "https://github.com/zion-support/zion-support.github.io/issues/72103",
        "hypothetical_or_unverified_design",
    ),
    (
        "Extract Agent Reliability Lab into a dedicated repository",
        "Draft PR plus implementation steps.",
        "https://github.com/artemoffM8/artemoffM8/issues/3",
        "profile_repository_work_item",
    ),
    (
        "Implement scheduled battery recovery dashboards",
        "No current error report.",
        "https://github.com/example/project/issues/333",
        "internal_implementation_work_item",
    ),
    (
        "Crash when opening billing reports",
        "Steps to reproduce: open the page. Actual behavior: crash.",
        "https://github.com/example/project/issues/1",
        "reported_operational_problem",
    ),
    (
        "Audit AI Agent Batch Transaction Reliability and Recovery",
        "A proposal to make batch operations safer.",
        "https://github.com/bownyu/fin-dash/issues/1",
        "unverified_public_issue",
    ),
])
def test_conservative_quality_screen(title, body, url, expected):
    assert classify_github_issue(title, body, url) == expected


def test_quality_exclusions_do_not_include_actual_reproduced_issue():
    assert "reported_operational_problem" not in EXCLUDED_FROM_CURRENT_HUNT
    assert "unverified_public_issue" not in EXCLUDED_FROM_CURRENT_HUNT
    assert "promotional_market_claim" in EXCLUDED_FROM_CURRENT_HUNT
    assert "hypothetical_or_unverified_design" in EXCLUDED_FROM_CURRENT_HUNT


def test_upstream_narrative_and_author_identity_never_leak_through_projection():
    payload = {
        "items": [{
            "id": 8,
            "title": "Battery recycling market to reach 29 billion by 2034",
            "body": "private-test-value@example.net\\nA hypothetical sales pitch.",
            "user": {"login": "hidden-person", "email": "private@example.net"},
            "labels": [{"name": "hidden-tag"}],
            "html_url": "https://github.com/owner/project/issues/8",
            "created_at": "2026-11-19T10:00:00Z",
        }],
    }
    x = evidence_projection("github_issues", payload)
    assert x["record_count"] == 1
    assert x["sample"][0]["issue_evidence_type"] == "promotional_market_claim"
    text = repr(x)
    assert "hidden-person" not in text
    assert "private@example.net" not in text
    assert "private-test-value" not in text
    assert "hidden-tag" not in text


def test_untrusted_urls_and_titles_are_not_approved_as_positive_buyer_proof():
    assert classify_github_issue("Battery recycling", None, "https://example.com/?token=X") == (
        "unverified_public_issue"
    )
    assert classify_github_issue(None, None, None) == "unverified_public_issue"
