"""Optional Hypothesis fuzz tests for Federal Register parsing and source isolation.

Run with: uv run --with hypothesis --no-sync python -m pytest -q
          tests/test_intelligence_federal_register_properties.py
The base installation intentionally does not add a production dependency.
"""
from __future__ import annotations

from datetime import date
from urllib.parse import parse_qs, urlsplit

import pytest

pytest.importorskip("hypothesis")
from hypothesis import given, settings, strategies as st

from mcp_trendpulse.intelligence_core import IntelligenceError, plan_source
from mcp_trendpulse.intelligence_evidence import (
    UnexpectedSourceShape, evidence_projection,
)
from mcp_trendpulse.intelligence_regulatory import choose_topic


@settings(max_examples=160, deadline=None)
@given(st.text(max_size=200), st.integers(min_value=1, max_value=20))
def test_untrusted_topic_never_changes_fixed_origin_or_request_shape(topic, limit):
    try:
        plan = plan_source(
            "federal_register", keyword=topic, limit=limit,
            lookback_days=30, env={},
        )
    except IntelligenceError:
        return
    parsed = urlsplit(plan.url)
    q = parse_qs(parsed.query)
    assert parsed.hostname == "www.federalregister.gov"
    assert parsed.scheme == "https"
    assert parsed.path == "/api/v1/documents.json"
    assert q["per_page"] == [str(limit)]
    assert q["order"] == ["newest"]
    assert q["conditions[term]"] == [" ".join(topic.split())]
    assert sorted(q) == [
        "conditions[publication_date][gte]", "conditions[term]",
        "fields[]", "order", "per_page",
    ]
    assert plan.budget_per_day == 20
    assert not plan.headers and plan.body is None


@settings(max_examples=120, deadline=None)
@given(st.text(max_size=180))
def test_untrusted_document_title_is_bounded_or_fails_closed(title):
    payload = {"results": [{
        "document_number": "2026-12345",
        "publication_date": date.today().isoformat(),
        "title": title,
        "type": "Proposed Rule",
        "html_url": "https://www.federalregister.gov/documents/2026/11/23/2026-12345/example",
        "body": "never-copy-full-text",
        "abstract": "never-copy-abstract",
    }]}
    try:
        result = evidence_projection("federal_register", payload)
    except UnexpectedSourceShape:
        return
    assert len(result["sample"]) == 1
    row = result["sample"][0]
    assert len(row["title"]) <= 240
    assert "abstract" not in row and "body" not in row
    assert row["legal_effect_verified"] is False


@settings(max_examples=120, deadline=None)
@given(st.text(max_size=120))
def test_untrusted_source_label_cannot_be_promoted_as_a_fake_regulation(label):
    result = choose_topic(
        {"candidates": [{"label": label}], "research_observations": []}
    )
    assert result[1] in ("source_derived_candidate", "no_supported_source_derived_topic")
    if result[0]:
        plan = plan_source("federal_register", keyword=result[0], env={})
        assert urlsplit(plan.url).hostname == "www.federalregister.gov"
