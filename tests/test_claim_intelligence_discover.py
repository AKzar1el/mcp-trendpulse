"""Offline provider projections, fact-check import, and claim-scoped integration."""
import json
from datetime import datetime, timezone

import pytest

from mcp_trendpulse import claim_intelligence_discover as discovery
from mcp_trendpulse.claim_intelligence_extract import extract_observation_claims
from mcp_trendpulse.claim_intelligence_graph import ClaimEvidenceGraph
from mcp_trendpulse.claim_intelligence_reviews import parse_review_capture
from mcp_trendpulse.news_intelligence_schema import NewsArticle, _digest

CUT = "2026-11-28T12:00:00Z"
NOW = datetime(2026, 11, 28, 12, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    monkeypatch.setattr(discovery, "_now", lambda: NOW)


def graph():
    row = NewsArticle(discovery_provider="gdelt_doc", link_type="publisher_candidate",
                      reported_url="https://example.org/story", title="Acme produced 100 units",
                      capture_mode="legacy_import", captured_at=CUT)
    result = extract_observation_claims([row], as_of=CUT)
    g = ClaimEvidenceGraph.model_validate_json(json.dumps(result["graph"]))
    return g, g.claims[0].claim_id


def raw(payload):
    return json.dumps(payload).encode()


def google():
    return {"claims": [{"text": "Acme produced 100 units", "claimant": "Acme",
                        "claimDate": "2026-11-27T10:00:00.123456789Z", "claimReview": [
                            {"publisher": {"name": "Review outlet", "site": "example.org"},
                             "url": "https://example.org/review", "title": "Checking the claim",
                             "reviewDate": CUT, "textualRating": "Mostly false", "languageCode": "en"}]}]}


def parse(payload, format="google_claim_search"):
    return parse_review_capture(raw(payload), format=format, captured_at=CUT, permit_metadata=True)


def test_google_original_attribution_dates_and_partial_page():
    p = google()
    p["nextPageToken"] = "DO_NOT_RETAIN"
    r = parse(p)
    assert r["status"] == "partial" and r["more_results_reported"]
    item = r["reviews"][0]
    assert item["claimant"] == "Acme" and item["review_publisher"] == "Review outlet"
    assert item["original_rating"]["text"] == "Mostly false"
    assert item["claim_date_reported"].endswith(".123456789Z")
    assert item["target_claim_match"] == "not_assessed"
    assert "DO_NOT_RETAIN" not in json.dumps(r)
    assert r["claim_verification"] == "not_performed"


def test_claimreview_preserves_rating_scale_without_remote_expansion():
    value = {"@context": "https://schema.org", "@type": "ClaimReview",
             "claimReviewed": "Acme produced 100 units", "url": "https://example.org/check",
             "author": {"name": "Different reviewer"}, "datePublished": "2026-11-27",
             "reviewRating": {"ratingValue": "2", "worstRating": 1, "bestRating": 7, "alternateName": "Needs context"},
             "itemReviewed": {"author": {"name": "Acme"}, "datePublished": "2026-11-26"}}
    r = parse({"@graph": [value]}, "claimreview_jsonld")
    assert r["reviews"][0]["original_rating"] == {"text":"Needs context","value":"2","worst":1,"best":7}
    assert r["reviews"][0]["review_date_reported"] == "2026-11-27"
    assert not r["network_performed"]


@pytest.mark.parametrize("change", ["url", "future", "rating", "publisher"])
def test_bad_review_metadata_rejected_without_inventing_verdict(change):
    p = google()
    review = p["claims"][0]["claimReview"][0]
    if change == "url":
        review["url"] = "https://127.0.0.1/"
    elif change == "future":
        review["reviewDate"] = "2026-11-29"
    elif change == "rating":
        review.pop("textualRating")
    else:
        review.pop("publisher")
    result = parse(p)
    assert result["status"] == "invalid" and result["rejected_rows"] == 1
    assert not result["reviews"]


def test_empty_missing_duplicate_rights_and_error_envelope():
    assert parse({"claims":[]})["status"] == "empty"
    assert parse({})["status"] == "unavailable"
    with pytest.raises(ValueError, match="permission"):
        parse_review_capture(raw(google()), format="google_claim_search", captured_at=CUT)
    with pytest.raises(ValueError, match="error envelope"):
        parse({"claims":[], "error":{"code":429}})
    p = google()
    p["claims"] *= 2
    assert parse(p)["exact_replays_removed"] == 1


def wb_row():
    return {"indicator":{"id":"SP.POP.TOTL","value":"Population, total"},
            "country":{"id":"SI","value":"Slovenia"},"date":"2025","value":0,"unit":""}


def provider_receipt(plan, rows, **kwargs):
    return {"source":plan.source, "source_url":plan.url, "status":"observed",
            "retrieved_at":CUT, "cache_hit":False,
            "observations":{"record_count":len(rows),"sample":rows}, **kwargs}


@pytest.mark.asyncio
async def test_plan_first_and_no_credential_resolution(monkeypatch):
    g, cid = graph()
    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected fetch")
    monkeypatch.setattr(discovery, "collect", forbidden)
    result = await discovery.discover_claim_evidence(g,claim_id=cid,queries=[
        discovery.RecordQuery(source="worldbank",country="SI",identifier="SP.POP.TOTL"),
        discovery.RecordQuery(source="cellar",keyword="energy"),
        discovery.RecordQuery(source="gleif",keyword="Acme"),
    ],review_captures=[(raw(google()),"google_claim_search",CUT)],permit_review_metadata=True)
    assert all(x["status"] == "planned" for x in result["official_record_receipts"])
    assert result["imported_review_receipts"][0]["review_count"] == 1
    assert result["google_fact_check_search"]["status"] == "disabled_unverified_free_access"
    assert result["automatic_relations_created"] == 0
    assert result["report_id"] == _digest({k:v for k,v in result.items() if k!="report_id"})


@pytest.mark.asyncio
async def test_all_official_routes_use_existing_collector(monkeypatch):
    g,cid = graph()
    calls = []
    lei = "54930012345678901234"
    def fake(plan, *, cache, fetch, env):
        assert fetch and env == {}
        calls.append(plan.source)
        if plan.source == "worldbank":
            rows = [wb_row(), {**wb_row(),"value":None,"date":"2024"}]
        elif plan.source == "gleif":
            rows = [{"id":lei,"attributes":{"lei":lei,"entity":{"legalName":{"name":"Acme"},"status":"ACTIVE"},
                                            "registration":{"status":"ISSUED"}}}]
        else:
            rows = [{"work":"http://publications.europa.eu/resource/cellar/abc","title":"Energy act"}]
        return provider_receipt(plan, rows)
    monkeypatch.setattr(discovery,"collect",fake)
    r = await discovery.discover_claim_evidence(g,claim_id=cid,execute=True,queries=[
        discovery.RecordQuery(source="worldbank",country="SI",identifier="SP.POP.TOTL"),
        discovery.RecordQuery(source="gleif",keyword="Acme"),
        discovery.RecordQuery(source="cellar",keyword="energy")])
    assert calls == ["worldbank","gleif","cellar"]
    a,b,c = r["official_record_receipts"]
    assert [x["value_reported"] for x in a["records"]] == [0,None]
    assert b["records"][0]["lei"] == lei
    assert c["records"][0]["work_uri_reported"].startswith("http://")
    assert all(x["status"] == "observed" for x in (a,b,c))
    assert r["source_independence"] == "unknown" and r["automatic_relations_created"] == 0


@pytest.mark.asyncio
async def test_partial_provider_failure_scope_and_no_raw_error_leak(monkeypatch):
    g,cid = graph()
    def fake(plan, **kwargs):
        if plan.source == "worldbank":
            return provider_receipt(plan,[wb_row(),{**wb_row(),"country":{"id":"AT","value":"Austria"}}])
        return {"source":plan.source,"status":"unavailable","http_status":429,"reason":"SECRET_ERROR"}
    monkeypatch.setattr(discovery,"collect",fake)
    r = await discovery.discover_claim_evidence(g,claim_id=cid,execute=True,queries=[
        discovery.RecordQuery(source="worldbank",country="SI",identifier="SP.POP.TOTL"),
        discovery.RecordQuery(source="cellar",keyword="energy")])
    a,b = r["official_record_receipts"]
    assert a["status"] == "partial" and a["rejected_rows"] == 1
    assert b["status"] == "unavailable" and b["http_status"] == 429
    assert "SECRET_ERROR" not in json.dumps(r)


@pytest.mark.asyncio
async def test_preflight_rejects_invalid_claim_duplicate_queries_and_review_rights(monkeypatch):
    g,cid = graph()
    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected fetch")
    monkeypatch.setattr(discovery,"collect",forbidden)
    q = discovery.RecordQuery(source="gleif",keyword="Acme")
    for opts in ({"queries":[q,q]}, {"queries":[q],"review_captures":[(raw(google()),"google_claim_search",CUT)]},
                 {"queries":[]}, {"queries":[q],"claim_id":"0"*64}):
        args = {"claim_id":cid,"execute":True,**opts}
        with pytest.raises(ValueError):
            await discovery.discover_claim_evidence(g,**args)


@pytest.mark.asyncio
async def test_news_search_uses_existing_plan_first_and_does_not_promote_independence(monkeypatch):
    g,cid = graph()
    calls = []
    async def fake(phrase, *, sources, limit, execute=False, cache=None):
        calls.append((phrase,sources,execute))
        return {"query":phrase,"status":"observed" if execute else "planned",
                "source_receipts":[],"citations":[{"title":"Reported headline"}] if execute else []}
    monkeypatch.setattr(discovery,"investigate_news",fake)
    r = await discovery.discover_claim_evidence(g,claim_id=cid,news_phrase="renewable energy",execute=True)
    assert calls == [("renewable energy",("google_news_rss",),False),
                     ("renewable energy",("google_news_rss",),True)]
    assert r["reporting_candidates"]["independence"] == "unknown"
    assert r["automatic_relations_created"] == 0
