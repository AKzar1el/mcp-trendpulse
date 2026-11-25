import json
from urllib.parse import parse_qs, urlsplit

import pytest

from mcp_trendpulse import intelligence_core as core
from mcp_trendpulse.intelligence_identity import canonical_doi

DOI = "10.1002/adma.201404892"


def _response(monkeypatch, items):
    calls = []

    class Response:
        headers = {"Content-Type": "application/json"}
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def read(self, n):
            return json.dumps({"status": "ok", "message": {
                "total-results": len(items), "items": items,
            }}).encode()

    class Opener:
        def open(self, req, timeout):
            calls.append(req.full_url)
            return Response()

    monkeypatch.setattr(core, "build_opener", lambda *_: Opener())
    return calls


def test_exact_bounded_plan_and_doi_validation():
    assert canonical_doi("HTTPS://DOI.ORG/10.1002/ADMA.201404892") == DOI
    p = core.plan_source("crossref", identifier=DOI, env={})
    parsed = urlsplit(p.url)
    assert parsed.hostname == "api.crossref.org"
    q = parse_qs(parsed.query)
    assert q["filter"] == ["doi:" + DOI]
    assert q["rows"] == ["1"]
    assert "author" not in q["select"][0] and "abstract" not in q["select"][0]
    for bad in ("https://evil.example/10.1002/a", "10.1002/a,doi:10.1002/b", "10.1002/a?x=1", ""):
        with pytest.raises(core.IntelligenceError):
            core.plan_source("crossref", identifier=bad, env={})


def test_exact_match_metadata_only_cache_and_conservative_pacing(tmp_path, monkeypatch):
    calls = _response(monkeypatch, [{
        "DOI": DOI.upper(), "title": ["Bibliographic title"],
        "published": {"date-parts": [[2015, 2]]}, "type": "journal-article",
        "author": [{"name": "FORBIDDEN_RAW_AUTHOR"}], "abstract": "FORBIDDEN_RAW_ABSTRACT",
    }])
    cache = core.BudgetCache(tmp_path)
    plan = core.plan_source("crossref", identifier=DOI, env={})
    result = core.collect(plan, fetch=True, cache=cache)
    assert result["doi_match_status"] == "exact_metadata_match"
    assert result["retraction_status_verified"] is False
    assert result["observations"]["sample"][0]["published"] == "2015-02"
    assert core.collect(plan, fetch=True, cache=cache)["cache_hit"]
    other = core.plan_source("crossref", identifier="10.1002/other", env={})
    blocked = core.collect(other, fetch=True, cache=cache)
    assert blocked["status"] == "unavailable" and blocked["reason"] == "provider_cooldown"
    assert len(calls) == 1
    assert "FORBIDDEN_RAW" not in repr(result)
    assert b"FORBIDDEN_RAW" not in cache.db.read_bytes()


def test_missing_and_mismatched_doi_not_equivalent(tmp_path, monkeypatch):
    p = core.plan_source("crossref", identifier=DOI, env={})
    _response(monkeypatch, [])
    result = core.collect(p, fetch=True, cache=core.BudgetCache(tmp_path / "empty"))
    assert result["doi_match_status"] == "not_observed_in_crossref"
    _response(monkeypatch, [{"DOI": "10.1002/wrong", "title": ["Similar title"]}])
    result = core.collect(p, fetch=True, cache=core.BudgetCache(tmp_path / "mismatch"))
    assert result["status"] == "invalid_source_shape"
    assert "doi_match_status" not in result
