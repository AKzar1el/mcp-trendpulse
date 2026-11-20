"""Scope descriptions must stay TED-attributed without inventing lot joins."""
from __future__ import annotations

from dataclasses import replace

import pytest

from mcp_trendpulse import intelligence_discovery as discovery
from mcp_trendpulse import intelligence_ted_scope as scope

NOTICE_1 = "804742-2026"
NOTICE_2 = "781080-2026"


def brief(ident=NOTICE_1, *, valid=True):
    return {
        "brief_id": "abc123abc123ab", "kind": "published_software_it_procurement_to_investigate",
        "published_lot_date_on_or_after_analysis": valid,
        "source_published_workflow_clue": "Digital portal",
        "evidence": [{
            "source": "ted",
            "reference": "https://ted.europa.eu/en/notice/-/detail/" + ident,
        }],
    }


def observed(tender_id, **fields):
    return {
        "status": "observed", "source": "ted",
        "observations": {"record_count": 1, "sample": [
            {"publication-number": tender_id, **fields}
        ]},
        "cache_hit": False,
    }


def test_two_official_exact_notice_queries_and_unmapped_multilot_source_excerpts(monkeypatch):
    sources = {"briefs": [brief(), {**brief(NOTICE_2), "brief_id": "bcd234bcd234bc"}]}
    calls = []
    def fake_collect(plan, **options):
        calls.append((plan, options))
        assert plan.source == "ted" and plan.body["limit"] == 1
        assert plan.body["page"] == 1
        assert all(x in plan.body["fields"] for x in scope.SCOPE_FIELDS)
        assert options["fetch"] is True and options["timeout"] == 20
        if NOTICE_1 in plan.body["query"]:
            return observed(NOTICE_1, **{
                "official-language": ["ELL"],
                "description-proc": {"ell": ["Digital portal and public employment support \n with contact user@example.org"]},
                "title-lot": {"ell": ["Digital employment portal", "Publicity and outreach"]},
                "description-lot": {"ell": ["Software operations", "Advertising campaign"]},
                "unused": "SECRET_MUST_NOT_COPY",
            })
        return observed(NOTICE_2, **{
            "official-language": ["DEU"],
            "description-proc": {"deu": ["Integrierte Finanz- und Haushaltssoftware einschließlich Gebäudemanagement (CAFM)"]},
            "title-lot": {"deu": ["Finanzsoftware"]},
        })
    monkeypatch.setattr(scope, "collect", fake_collect)
    result = scope.inspect_ted_scopes(sources, env={})
    assert len(calls) == 2
    assert calls[0][0].body["query"] == f"publication-number = {NOTICE_1}"
    assert calls[1][0].body["query"] == f"publication-number = {NOTICE_2}"
    assert result["source_requests_budgeted"] == 2
    assert result["status"] == "published_scope_context_observed"
    first = sources["briefs"][0]["published_scope_context"]
    assert first["procedure_description"][0]["language"] == "ell"
    assert first["lot_title_excerpts_without_lot_identity"][1]["excerpt"] == "Publicity and outreach"
    assert first["lot_budget_deadline_alignment_verified"] is False
    second = sources["briefs"][1]["published_scope_context"]
    assert "CAFM" in second["procedure_description"][0]["excerpt"]
    assert "user@example.org" not in repr(sources)
    assert "SECRET_MUST_NOT_COPY" not in repr(sources)
    report = "\n".join(scope.format_ted_scopes(result, sources))
    assert "unassigned" in report
    assert "not zero demand" not in report.lower()


def test_unverified_identity_rejected_and_untrusted_details_not_echoed(monkeypatch):
    monkeypatch.setattr(scope, "collect", lambda *_a, **_kw: observed(
        "999999-2026", **{
            "description-proc": {"eng": ["SENSITIVE_SUPPLIER_CONTACT"]},
        }
    ))
    sources = {"briefs": [brief()]}
    result = scope.inspect_ted_scopes(sources, env={})
    assert result["source_status"][0]["status"] == "invalid_source_shape"
    assert "published_scope_context" not in sources["briefs"][0]
    assert "SENSITIVE_SUPPLIER_CONTACT" not in repr(result)


def test_past_and_invalid_source_reference_never_make_network_calls(monkeypatch):
    def deny(*_a, **_kw):
        raise AssertionError("No network for past lots / bad IDs")
    monkeypatch.setattr(scope, "collect", deny)
    docs = {"briefs": [brief(valid=False), brief("../secret")]}
    result = scope.inspect_ted_scopes(docs, env={})
    assert result["source_requests_budgeted"] == 0
    assert result["status"] == "no_eligible_published_tenders"


def test_http_failure_only_exposes_allowlisted_reason_not_provider_body(monkeypatch):
    def fail(*_a, **_kw):
        return {
            "source": "ted", "status": "rate_limited",
            "http_status": 429, "error": "BEARER_PRIVATE_KEY_DO_NOT_COPY",
        }
    monkeypatch.setattr(scope, "collect", fail)
    result = scope.inspect_ted_scopes({"briefs": [brief()]}, env={})
    assert result["source_status"][0]["http_status"] == 429
    assert "BEARER_PRIVATE_KEY" not in repr(result)
    assert "BEARER_PRIVATE_KEY" not in "\n".join(scope.format_ted_scopes(
        result, {"briefs": [brief()]},
    ))


def test_public_excerpt_redacts_urls_emails_and_limits_all_strings():
    lines = scope._published_excerpts({
        "eng": [
            "See https://example.org/private?token=SECRET and email staff@example.org for details",
            "Building finance operations",
            "Noise that must be excluded",
        ],
        "deu": ["Andere Sprache"],
    }, official=["DEU"])
    assert len(lines) == 2 and lines[0]["language"] == "eng"
    assert "example.org" not in repr(lines)
    assert "SECRET" not in repr(lines)
    assert "Andere" not in repr(lines)
    assert all(len(x["excerpt"]) <= scope.MAX_EXCERPT_CHARS for x in lines)
    assert scope._published_excerpts([{"junk": "SECRET"}]) == []


def test_scope_plan_and_source_budget_no_mutation_or_network(monkeypatch):
    monkeypatch.setattr(discovery, "collect", lambda *_a, **_kw: (
        (_ for _ in ()).throw(AssertionError("Plan-only must not request network"))
    ))
    plan = discovery.discover_current(
        execute=False, workflow_briefs=True,
        ted_scope_details=True, ted_date_slices=3, limit=20, env={},
    )
    assert plan["request_count"] == 5
    assert plan["max_requests_with_ted_scope_details"] == 7
    assert plan["workflow_briefs"]["ted_scope_details"]["max_additional_source_requests"] == 2
    assert plan["workflow_briefs"]["ted_scope_details"]["source_requests_performed"] == 0
    with pytest.raises(ValueError, match="ted-scope-details"):
        discovery.discover_current(execute=False, ted_scope_details=True, env={})
    with pytest.raises(ValueError, match="ted_scope_details"):
        discovery.discover_current(
            execute=False, ted_scope_details="yes", workflow_briefs=True, env={},
        )


def test_seedless_live_pipeline_uses_only_one_explicit_source_scope_extra(monkeypatch):
    today = __import__("datetime").date.today().isoformat()
    urls = []
    def fake_collect(plan, **kw):
        urls.append(plan.body["query"] if plan.source == "ted" else plan.source)
        if plan.source == "openalex":
            return {"source": "openalex", "status": "observed",
                    "observations": {"sample": [], "record_count": 0}}
        if plan.source == "cfpb":
            return {"source": "cfpb", "status": "observed",
                    "observations": {"sample": [], "record_count": 0}}
        if "publication-number =" in plan.body["query"]:
            return observed(NOTICE_1, **{
                "description-proc": {"eng": ["New digital employment platform"]},
            })
        return {"source": "ted", "status": "observed",
                "observations": {"sample": [{
                    "publication-number": NOTICE_1,
                    "publication-date": today,
                    "notice-title": {"eng": ["Digital portal and software operations"]},
                    "buyer-name": {"eng": ["Public authority"]},
                    "notice-type": "cn-standard",
                    "main-classification-proc": "72000000",
                    "deadline-receipt-tender-date-lot": "2026-12-21",
                }], "record_count": 1}}
    monkeypatch.setattr(discovery, "collect", fake_collect)
    monkeypatch.setattr(scope, "collect", fake_collect)
    result = discovery.discover_current(
        execute=True, workflow_briefs=True,
        ted_scope_details=True, env={},
    )
    assert len(urls) == 4
    assert urls[-1] == f"publication-number = {NOTICE_1}"
    assert result["queries_budgeted"] == 4
    assert result["workflow_briefs"]["ted_scope_details"]["source_requests_budgeted"] == 1
    assert "New digital employment platform" in discovery.format_discovery_report(result)
    assert result["growth_rate_verified"] is False
