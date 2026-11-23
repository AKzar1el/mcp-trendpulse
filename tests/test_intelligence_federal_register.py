"""Federal Register fixed-origin planning, cautious evidence, and discovery integration."""
from __future__ import annotations

from datetime import date
import random
import string
from urllib.parse import parse_qs, urlsplit

import pytest

from mcp_trendpulse.intelligence_core import (
    IntelligenceError, collect, plan_source, source_catalog,
)
from mcp_trendpulse.intelligence_evidence import (
    UnexpectedSourceShape, evidence_projection,
)
from mcp_trendpulse import intelligence_discovery as discovery
from mcp_trendpulse import intelligence_regulatory as regulatory


def _doc(number="2026-12345", title="Artificial Intelligence Safety Rules"):
    return {
        "document_number": number,
        "title": title,
        "publication_date": date.today().isoformat(),
        "type": "Proposed Rule",
        "html_url": (
            "https://www.federalregister.gov/documents/"
            "2026/11/23/2026-12345/artificial-intelligence-safety-rules"
        ),
        "abstract": "Do not retain whole document bodies.",
        "email": "should-not-appear@example.com",
    }


def test_catalog_registers_legal_context_and_not_an_extra_tool():
    sources = {s["id"]: s for s in source_catalog()}
    assert sources["federal_register"]["access"] == "public/no-key"
    assert sources["federal_register"]["wave"] == 1
    from mcp_trendpulse.intelligence_opportunities import SOURCE_KIND
    assert SOURCE_KIND["federal_register"] == "legal_metadata"


def test_federal_register_plan_is_keyless_fixed_origin_and_bounded():
    plan = plan_source(
        "federal_register", keyword="artificial intelligence",
        limit=8, lookback_days=30, env={},
    )
    parsed = urlsplit(plan.url)
    q = parse_qs(parsed.query)
    assert parsed.scheme == "https" and parsed.hostname == "www.federalregister.gov"
    assert parsed.path == "/api/v1/documents.json"
    assert q["conditions[term]"] == ["artificial intelligence"]
    assert q["per_page"] == ["8"]
    assert q["order"] == ["newest"]
    assert "publication_date" in " ".join(q["fields[]"])
    assert plan.body is None and plan.method == "GET"
    assert not plan.headers and plan.budget_per_day == 20
    assert collect(plan, fetch=False)["network_performed"] is False


@pytest.mark.parametrize("bad", [
    "", " ", "topic\nInjected", "topic&per_page=1000",
    "topic?order=oldest", "topic#frag", "💣", "a" * 81,
])
def test_federal_register_unsafe_topic_rejected_before_network(bad):
    with pytest.raises(IntelligenceError):
        plan_source("federal_register", keyword=bad, env={})


@pytest.mark.parametrize("lookback", [0, 6, 91, True, "14"])
def test_federal_register_rejects_bad_lookback(lookback):
    with pytest.raises(IntelligenceError):
        plan_source("federal_register", keyword="machine learning",
                    lookback_days=lookback, env={})


def test_valid_official_proposal_is_not_an_enacted_regulation():
    observations = evidence_projection(
        "federal_register", {"results": [_doc(), _doc()], "count": 2},
    )
    assert observations["record_count"] == 1
    row = observations["sample"][0]
    assert row["proposed_rule_not_effective_rule"] is True
    assert row["legal_effect_verified"] is False
    assert "abstract" not in row and "email" not in row
    assert row["html_url"].startswith("https://www.federalregister.gov/documents/")


def test_correction_doc_prefix_is_valid_original_official_identity():
    row = _doc(number="C1-2026-15326")
    row["html_url"] = (
        "https://www.federalregister.gov/documents/2026/08/19/"
        "C1-2026-15326/agency-information-collection-activities"
    )
    result = evidence_projection("federal_register", {"results": [row], "count": 1})
    assert result["record_count"] == 1
    assert result["sample"][0]["document_number"] == "C1-2026-15326"
    assert result["sample"][0]["legal_effect_verified"] is False


def test_zero_count_without_results_is_valid_empty_response_not_source_failure():
    result = evidence_projection("federal_register", {"count": 0})
    assert result["record_count"] == 0
    assert result["sample"] == []


def test_invalid_zero_count_envelope_does_not_silently_pass():
    with pytest.raises(UnexpectedSourceShape):
        evidence_projection("federal_register", {"count": 5})


def test_empty_collection_is_bounded_observation_not_a_no_regulation_claim():
    result = evidence_projection("federal_register", {"results": [], "count": 0})
    assert result["record_count"] == 0
    assert result["sample"] == []
    assert "not current legal obligations" in result["unit"]


@pytest.mark.parametrize("payload", [
    {}, {"results": "not-array"}, {"status": "error", "results": []},
    {"results": [{"title": "No document identity"}]},
    {"results": [{**_doc(), "html_url": "https://evil.example/documents/abc"}]},
    {"results": [{**_doc(), "publication_date": "not-a-date"}]},
    {"results": [{**_doc(), "html_url": "https://www.federalregister.gov.evil.example/documents/abc"}]},
    {"results": [{**_doc(), "html_url": "https://[::1/documents/bad"}]},
])
def test_malformed_and_untrusted_records_are_not_valid_evidence(payload):
    with pytest.raises(UnexpectedSourceShape):
        evidence_projection("federal_register", payload)


def test_seeded_offline_input_fuzz_never_escapes_fixed_host():
    rng = random.Random(20261123)
    alphabet = string.ascii_letters + string.digits + " &?=/#<>\\n\\t%'()"
    safe = 0
    for _ in range(300):
        term = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 100)))
        try:
            plan = plan_source("federal_register", keyword=term, env={})
        except IntelligenceError:
            continue
        parsed = urlsplit(plan.url)
        params = parse_qs(parsed.query)
        assert parsed.scheme == "https" and parsed.netloc == "www.federalregister.gov"
        assert parsed.path == "/api/v1/documents.json"
        assert params["conditions[term]"] == [" ".join(term.split())]
        assert params["order"] == ["newest"]
        safe += 1
    assert safe > 0


def test_optional_context_without_sourced_topic_never_calls_external_source(monkeypatch):
    monkeypatch.setattr(
        regulatory, "collect",
        lambda *args, **kwargs: pytest.fail("No source topic must never fetch"),
    )
    result = regulatory.enrich_regulatory_context(
        {"candidates": [], "research_observations": []}, env={},
    )
    assert result["status"] == "no_supported_topic"
    assert result["source_requests_budgeted"] == 0
    assert result["documents"] == []


def test_topic_derived_from_source_candidate_uses_at_most_one_new_request(monkeypatch):
    calls = []
    def fake_collect(plan, **kwargs):
        calls.append((plan, kwargs))
        return {
            "status": "observed", "cache_hit": False,
            "observations": evidence_projection("federal_register", {"results": [_doc()]}),
        }
    monkeypatch.setattr(regulatory, "collect", fake_collect)
    result = regulatory.enrich_regulatory_context(
        {"candidates": [{"label": "Artificial Intelligence Safety"}],
         "research_observations": []},
        lookback_days=14, limit=8, env={},
    )
    assert result["status"] == "observed"
    assert result["topic_origin"] == "source_derived_candidate"
    assert result["source_requests_budgeted"] == 1
    assert len(calls) == 1 and calls[0][0].source == "federal_register"
    assert calls[0][1]["fetch"] is True
    assert result["sampled_documents"] == 1
    assert result["buyer_demand_verified"] is False
    assert result["legal_effect_verified"] is False


def test_provider_429_is_reported_without_retry_or_false_zero(monkeypatch):
    calls = []
    def unavailable(plan, **kwargs):
        calls.append(plan.url)
        return {"status": "unavailable", "reason": "HTTPError",
                "http_status": 429, "retry_automatically": False}
    monkeypatch.setattr(regulatory, "collect", unavailable)
    result = regulatory.enrich_regulatory_context(
        {"candidates": [], "research_observations": []},
        regulatory_term="data privacy", env={},
    )
    assert result["status"] == "unavailable"
    assert result["reason_code"] == "HTTPError"
    assert result["http_status"] == 429
    assert result["documents"] == []
    assert result["source_requests_budgeted"] == 1
    assert len(calls) == 1


def test_discovery_baseline_unchanged_without_opt_in():
    plan = discovery.discover_current(execute=False, env={})
    assert plan["request_count"] == 3
    assert "regulatory_context" not in plan
    assert all(p["source"] != "federal_register" for p in plan["plans"])


def test_explicit_discovery_plan_remains_offline_and_counts_extra_request():
    plan = discovery.discover_current(
        execute=False, regulatory_context=True,
        regulatory_term="Artificial Intelligence", env={},
    )
    assert plan["status"] == "planned"
    assert plan["network_performed"] is False
    assert plan["request_count"] == 3
    assert plan["max_requests_with_regulatory_context"] == 4
    assert plan["regulatory_context"]["request_plan"]["source"] == "federal_register"


def test_regulatory_term_rejected_without_opt_in():
    with pytest.raises(ValueError, match="requires regulatory_context"):
        discovery.discover_current(execute=False, regulatory_term="privacy")


def test_discovery_attach_context_does_not_change_core_candidates(monkeypatch):
    observed = []
    monkeypatch.setattr(
        discovery, "collect",
        lambda plan, **kwargs: {
            "source": plan.source, "status": "observed",
            "observations": {"sample": []}, "cache_hit": False,
        },
    )
    def fake_summarize(*args, **kwargs):
        return {
            "mode": "seedless_public_source_discovery_not_market_growth",
            "candidates": [{"label": "Artificial Intelligence Safety"}],
            "research_observations": [], "limits": "Original three-source uncertainty.",
            "source_coverage": [], "paid_buyers_verified": False,
        }
    monkeypatch.setattr(discovery, "summarize_discovery", fake_summarize)
    def fake_reg_collect(plan, **kwargs):
        observed.append(plan.source)
        return {"status": "observed", "cache_hit": False,
                "observations": evidence_projection("federal_register", {"results": [_doc()]})}
    monkeypatch.setattr(regulatory, "collect", fake_reg_collect)
    result = discovery.discover_current(execute=True, regulatory_context=True, env={})
    assert result["candidates"] == [{"label": "Artificial Intelligence Safety"}]
    assert result["queries_budgeted"] == 4
    assert observed == ["federal_register"]
    assert result["regulatory_context"]["status"] == "observed"
    assert result["paid_buyers_verified"] is False
