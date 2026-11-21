"""Original source UUIDv4 join and amendment-aware investigation guardrails."""
from __future__ import annotations

from datetime import date

import pytest

from mcp_trendpulse import intelligence_discovery as discovery
from mcp_trendpulse import intelligence_ted_lineage as lineage
from mcp_trendpulse import intelligence_ted_scope as scope

ASOF = date(2026, 11, 20)
UUID_1 = "123e4567-e89b-42d3-a456-426614174000"
UUID_2 = "abcdef12-1234-4bcd-aaaa-abcdef123456"


def brief(ident="781080-2026", uuid=UUID_1):
    return {
        "brief_id": "abc123abc123ab",
        "kind": "published_software_it_procurement_to_investigate",
        "published_lot_date_on_or_after_analysis": True,
        "evidence": [{
            "source": "ted", "date": "2026-11-10",
            "reference": "https://ted.europa.eu/en/notice/-/detail/" + ident,
        }],
        "published_scope_context": {
            "status": "observed_scope_excerpts",
            "published_procedure_identifier": uuid,
        },
    }


def observed(rows):
    return {"source": "ted", "status": "observed",
            "observations": {"sample": rows, "record_count": len(rows)}}


def notice(ident, published, uuid=UUID_1, kind="cn-standard"):
    return {"publication-number": ident, "publication-date": published,
            "procedure-identifier": [uuid], "notice-type": kind}


def test_source_uuid_rejects_multi_value_other_versions_and_untrusted_values():
    assert lineage._source_uuid(UUID_1) == UUID_1
    assert lineage._source_uuid([UUID_1]) == UUID_1
    for item in ([], [UUID_1, UUID_2], UUID_1.upper() + " extra",
                 "00000000-0000-1000-8000-000000000000",
                 "https://evil.example/SECRET"):
        assert lineage._source_uuid(item) == ""


def test_exact_related_procedure_notices_with_newer_publication_require_review(monkeypatch):
    calls = []
    def collect(plan, **kw):
        calls.append((plan, kw))
        assert plan.source == "ted"
        assert plan.body["query"] == "procedure-identifier = " + UUID_1
        assert plan.body["limit"] == 10
        return observed([
            notice("781080-2026", "2026-11-10"),
            notice("785157-2026", "2026-11-11"),
            notice("999998-2026", "2026-11-15", uuid=UUID_2),
            notice("999999-2026", "2026-12-02"),
        ])
    monkeypatch.setattr(lineage, "collect", collect)
    briefs = {"briefs": [brief()]}
    result = lineage.inspect_related_ted_notices(briefs, as_of=ASOF, env={})
    assert len(calls) == 1
    assert result["source_requests_budgeted"] == 1
    assert result["status"] == "source_joined_related_notices_observed"
    item = result["related_notice_results"][0]
    assert item["related_notice_count_in_bounded_sample"] == 2
    assert item["provider_sample_rows"] == 4
    assert item["rows_excluded_for_unmatched_procedure_identifier"] == 1
    assert item["rows_excluded_for_invalid_or_future_publication"] == 1
    assert item["newest_related_notice"]["publication_number"] == "785157-2026"
    assert item["newer_same_procedure_publication_present"] is True
    assert briefs["briefs"][0]["related_notice_context"][
        "newer_source_publication_requires_scope_revalidation"] is True
    assert not item["actual_current_lot_or_bid_status_verified"]
    shown = "\n".join(lineage.format_related_ted_notices(result))
    assert "NEWER SAME-PROCEDURE PUBLICATION" in shown
    assert "999998-2026" not in repr(result)


def test_ted_timezone_suffixed_publication_dates_survive_procedure_join(monkeypatch):
    assert lineage._date("2026-11-11+01:00", as_of=ASOF) == "2026-11-11"
    assert lineage._date("2026-11-11T10:30:00+01:00", as_of=ASOF) == "2026-11-11"
    assert lineage._date("2026-11-11T10:30:00.123Z", as_of=ASOF) == "2026-11-11"
    assert lineage._date("2026-11-21+01:00", as_of=ASOF) == ""
    assert lineage._date("2026-11-11 garbage", as_of=ASOF) == ""
    assert lineage._date("2026-02-30+01:00", as_of=ASOF) == ""
    monkeypatch.setattr(lineage, "collect", lambda *a, **kw: observed([
        notice("781080-2026", "2026-11-10+01:00"),
        notice("785157-2026", "2026-11-11T00:00:00+01:00"),
    ]))
    briefs = {"briefs": [brief()]}
    result = lineage.inspect_related_ted_notices(briefs, as_of=ASOF, env={})
    item = result["related_notice_results"][0]
    assert item["status"] == "observed_related_notice_sample"
    assert item["newest_related_notice"]["publication_number"] == "785157-2026"
    assert item["newer_same_procedure_publication_present"] is True
    assert item["rows_excluded_for_invalid_or_future_publication"] == 0


def test_no_ted_related_notice_rows_remain_inconclusive(monkeypatch):
    monkeypatch.setattr(lineage, "collect", lambda *a, **kw: observed([]))
    result = lineage.inspect_related_ted_notices(
        {"briefs": [brief()]}, as_of=ASOF, env={},
    )
    item = result["related_notice_results"][0]
    assert item["related_notice_count_in_bounded_sample"] == 0
    assert item["provider_sample_rows"] == 0
    assert item["actual_current_lot_or_bid_status_verified"] is False
    assert "not proof that no amendments exist" in "\n".join(
        lineage.format_related_ted_notices(result)
    )


def test_ambiguous_uuid_rejects_queries_and_does_not_infer_title_matches(monkeypatch):
    monkeypatch.setattr(lineage, "collect", lambda *_a, **_kw: (
        (_ for _ in ()).throw(AssertionError("Not queryable"))
    ))
    result = lineage.inspect_related_ted_notices(
        {"briefs": [brief(uuid="NO_UUID")]}, as_of=ASOF, env={},
    )
    assert result["source_requests_budgeted"] == 0
    assert result["status"] == "no_source_published_procedure_uuid"


def test_source_scope_preserves_single_original_validated_public_uuid(monkeypatch):
    from mcp_trendpulse.intelligence_ted_scope import inspect_ted_scopes

    def fake(plan, **_kw):
        return observed([{
            "publication-number": "781080-2026",
            "procedure-identifier": [UUID_1],
            "description-proc": {"deu": ["Finanzsoftware und CAFM"]},
        }])
    monkeypatch.setattr(scope, "collect", fake)
    b = {
        "brief_id": "abc123abc123ab",
        "kind": "published_software_it_procurement_to_investigate",
        "published_lot_date_on_or_after_analysis": True,
        "evidence": [{"source": "ted",
                      "reference": "https://ted.europa.eu/en/notice/-/detail/781080-2026"}],
    }
    records = {"briefs": [b]}
    report = inspect_ted_scopes(records, env={})
    assert report["status"] == "published_scope_context_observed"
    assert b["published_scope_context"]["published_procedure_identifier"] == UUID_1


def test_related_ted_provider_failure_is_not_zero_market_evidence(monkeypatch):
    monkeypatch.setattr(lineage, "collect", lambda *_a, **_kw: {
        "status": "unavailable", "reason": "HTTPError",
        "http_status": 429, "error": "SENSITIVE_ACCESS_KEY",
    })
    result = lineage.inspect_related_ted_notices(
        {"briefs": [brief()]}, as_of=ASOF, env={},
    )
    assert result["status"] == "partial_or_unavailable_related_notices"
    assert result["related_notice_results"][0]["http_status"] == 429
    assert "SENSITIVE_ACCESS_KEY" not in repr(result)


def test_lineage_requires_scope_and_plan_only_budget_with_no_network(monkeypatch):
    monkeypatch.setattr(discovery, "collect", lambda *_a, **_kw: (
        (_ for _ in ()).throw(AssertionError("Plan only"))
    ))
    with pytest.raises(ValueError, match="ted-related-notices"):
        discovery.discover_current(execute=False, ted_related_notices=True, env={})
    planned = discovery.discover_current(
        execute=False, workflow_briefs=True, ted_scope_details=True,
        ted_related_notices=True, idea_map=True, env={},
    )
    assert planned["request_count"] == 3
    assert planned["max_requests_with_ted_related_notices"] == 7
    assert planned["workflow_briefs"]["ted_related_notices"][
        "source_requests_performed"
    ] == 0
