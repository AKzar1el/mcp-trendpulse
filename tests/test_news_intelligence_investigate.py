"""Offline end-to-end workflow regressions; no upstream requests."""
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from mcp_trendpulse import news_intelligence_investigate as inv
from mcp_trendpulse import news_intelligence_collect as collector
from mcp_trendpulse.intelligence_core import BudgetCache
from mcp_trendpulse.news_intelligence_schema import parse_news_capture, parse_nasa_rss_capture

NOW = datetime(2026, 11, 28, 12, tzinfo=timezone.utc)
CUT = NOW.isoformat()
HEAD = "Researchers announce a new renewable energy project for regional communities"


def rss_rows():
    return [{
        "title": HEAD, "url": "https://news.google.com/rss/articles/abc",
        "publish_date": "2026-11-28T10:00:00Z", "meta_site_name": "Example publisher",
        "meta_data": {"content_level": "rss_headline_only", "source": "google_news_rss"},
    }]


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    monkeypatch.setattr(inv, "_now", lambda: NOW)
    monkeypatch.setattr(collector, "_now", lambda: NOW)
    monkeypatch.setattr(inv, "get_google_news_country", lambda: "US")
    monkeypatch.setattr(inv, "get_google_news_language", lambda: "en")


@pytest.mark.asyncio
async def test_plan_never_executes_or_constructs_budget(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected execution")
    monkeypatch.setattr(inv, "BudgetCache", forbidden)
    monkeypatch.setattr(inv, "_google_collect", forbidden)
    monkeypatch.setattr(inv, "extract_article", forbidden)
    report = await inv.investigate_news("renewable energy", sources=inv.SOURCES)
    assert report["status"] == "planned"
    assert report["budget"]["provider_operations_attempted"] == 0
    assert report["budget"]["selected_source_operations"] == 4
    assert all(x["status"] == "planned" for x in report["source_receipts"])
    assert report["topical_sample"] is None and report["claim_verification"] == "not_performed"
    assert report["network_performed"] is False


@pytest.mark.asyncio
async def test_offline_import_reuses_dedup_events_and_coverage():
    rows = rss_rows()
    rows.append({**rows[0], "url": "https://news.google.com/rss/articles/def"})
    batch = parse_news_capture(json.dumps(rows).encode(), provider="google_news_rss", captured_at=CUT)
    report = await inv.investigate_news("renewable energy", sources=(), imported_batches=[batch])
    assert report["status"] == "offline_replay"
    assert report["topical_sample"] is None
    assert report["all_sample_and_context"]["event_candidate_count"] == 1
    assert report["all_sample_and_context"]["provider_scoped_article_keys"] == 2
    assert report["duplicate_evidence"]["comparisons"] == 1
    assert all(x["scope"] == ["imported_unscoped"] for x in report["citations"])
    assert report["budget"]["provider_operations_attempted"] == 0
    assert "not verified" in inv.format_investigation_markdown(report)


def fake_provider(monkeypatch, response):
    from mcp_trendpulse import providers
    from types import SimpleNamespace
    call = AsyncMock(side_effect=response) if isinstance(response, Exception) else AsyncMock(return_value=response)
    monkeypatch.setattr(providers, "get_provider_set", lambda: SimpleNamespace(
        news=SimpleNamespace(get_rss_headlines_by_keyword=call)))
    return call


@pytest.mark.asyncio
async def test_existing_google_provider_budget_and_metadata_cache(monkeypatch, tmp_path):
    call = fake_provider(monkeypatch, rss_rows())
    store = BudgetCache(tmp_path)
    first = await inv.investigate_news("renewable energy", sources=("google_news_rss",), execute=True, cache=store)
    assert first["status"] == "observed"
    assert first["topical_sample"]["distinct_observations"] == 1
    assert first["budget"]["provider_operations_attempted"] == 1
    assert first["citations"][0]["scope"] == ["query_scoped_sample"]
    markdown = inv.format_investigation_markdown(first)
    assert "event candidates (unverified)" in markdown
    assert "(N1)" in markdown and "Duplicate evidence" in markdown
    assert first["run_id"] == inv._digest({k: v for k, v in first.items() if k != "run_id"})
    second = await inv.investigate_news("renewable energy", sources=("google_news_rss",), execute=True, cache=store)
    assert second["source_receipts"][0]["cache_hit"]
    assert second["budget"]["provider_operations_attempted"] == 0
    assert second["network_performed"] is False
    assert first["citations"] == second["citations"]
    call.assert_awaited_once_with(keyword="renewable energy", period=3, max_results=10)
    blocked = await inv.investigate_news("different phrase", sources=("google_news_rss",), execute=True, cache=store)
    assert blocked["source_receipts"][0]["reason"] == "provider_cooldown"
    assert call.await_count == 1


@pytest.mark.asyncio
async def test_legacy_empty_is_not_zero(monkeypatch, tmp_path):
    fake_provider(monkeypatch, [])
    report = await inv.investigate_news("renewable energy", sources=("google_news_rss",),
                                        execute=True, cache=BudgetCache(tmp_path))
    assert report["status"] == "unavailable"
    assert report["source_receipts"][0]["reason"] == "legacy_empty_or_unavailable"
    assert report["topical_sample"]["provider_scoped_article_keys"] is None


@pytest.mark.asyncio
async def test_multi_source_partial_keeps_nasa_out_of_topical_sample(monkeypatch, tmp_path):
    fake_provider(monkeypatch, rss_rows())
    original = collector.collect_news
    calls = []

    def fake(source, *, execute=False, cache=None, **kwargs):
        plan = original(source, **kwargs)
        if not execute:
            return plan
        calls.append(source)
        if source == "nasa_rss":
            raw = (b'<rss version="2.0"><channel><title>NASA</title><link>https://www.nasa.gov/</link>'
                   b'<item><title>Unrelated space news</title><link>https://www.nasa.gov/story</link>'
                   b'</item></channel></rss>')
            b = parse_nasa_rss_capture(raw, captured_at=CUT)
            return {**plan, "status": b.status, "captured_at": CUT, "evidence": b.model_dump(mode="json"),
                    "provider_requests": 1, "network_performed": True, "http_status": 200}
        return {**plan, "status": "unavailable", "reason": "provider_rate_limited",
                "provider_requests": 1, "network_performed": True, "http_status": 429}

    monkeypatch.setattr(inv, "collect_news", fake)
    result = await inv.investigate_news("renewable energy", sources=("google_news_rss", "gdelt_timeline", "nasa_rss"),
                                        execute=True, cache=BudgetCache(tmp_path))
    assert result["status"] == "partial" and calls == ["gdelt_timeline", "nasa_rss"]
    assert result["coverage_timeline"]["weighted_coverage_pct"] is None
    assert result["topical_sample"]["distinct_observations"] == 1
    assert result["all_sample_and_context"]["distinct_observations"] == 2
    assert {tuple(c["scope"]) for c in result["citations"]} == {("query_scoped_sample",), ("recent_context",)}
    assert result["budget"]["provider_operations_attempted"] == 3


@pytest.mark.asyncio
async def test_invalid_selection_and_budget_before_io(monkeypatch):
    monkeypatch.setattr(inv, "_google_collect", AsyncMock(side_effect=AssertionError("Unexpected I/O")))
    for kwargs in ({"sources": ("nasa_rss", "nasa_rss")}, {"limit": True},
                   {"execute": "yes"}, {"extract_limit": 1}, {"days": 31},
                   {"sources": (), "execute": True},
                   {"sources": ("nasa_rss",), "timeline_as_of": CUT}):
        with pytest.raises(ValueError):
            await inv.investigate_news("renewable energy", **kwargs)
    rows = [{**rss_rows()[0], "url": f"https://news.google.com/rss/articles/test{i}"} for i in range(20)]
    b = parse_news_capture(json.dumps(rows).encode(), provider="google_news_rss", captured_at=CUT)
    with pytest.raises(ValueError, match="observation budget"):
        await inv.investigate_news("renewable energy", sources=inv.SOURCES, limit=20, imported_batches=[b,b])


@pytest.mark.asyncio
async def test_no_implicit_extraction_and_explicit_bounded_attempt(monkeypatch, tmp_path):
    from mcp_trendpulse.news_intelligence_extract import ArticleExtraction
    rows = rss_rows()
    rows.append({**rows[0], "url": "https://news.google.com/rss/articles/def"})
    fake_provider(monkeypatch, rows)

    async def failed(article, *, execute=False):
        assert execute
        return ArticleExtraction(discovery=article, status="unavailable", reason="http_rate_limited",
                                 http_status=429, started_at=CUT, completed_at=CUT)

    call = AsyncMock(side_effect=failed)
    monkeypatch.setattr(inv, "extract_article", call)
    store = BudgetCache(tmp_path)
    first = await inv.investigate_news("renewable energy", sources=("google_news_rss",), execute=True, cache=store)
    assert first["extraction_receipts"] == []
    call.assert_not_awaited()
    result = await inv.investigate_news("renewable energy", sources=("google_news_rss",), execute=True,
                                        extract_limit=2, cache=store)
    assert len(result["extraction_receipts"]) == 1
    assert result["status"] == "partial"
    assert result["budget"]["extraction_http_request_count"] is None
    call.assert_awaited_once()


@pytest.mark.asyncio
async def test_untrusted_headline_is_escaped_in_markdown():
    rows = rss_rows()
    rows[0]["title"] = "<img src=x> ![click](https://bad.example/) **execute**"
    batch = parse_news_capture(json.dumps(rows).encode(), provider="google_news_rss", captured_at=CUT)
    report = await inv.investigate_news("test", sources=(), imported_batches=[batch])
    md = inv.format_investigation_markdown(report)
    assert "<img" not in md and "![click]" not in md and "**execute**" not in md
    assert "&lt;img" in md


@pytest.mark.asyncio
async def test_forged_batch_rejected():
    batch = parse_news_capture(json.dumps(rss_rows()).encode(), provider="google_news_rss", captured_at=CUT)
    with pytest.raises(ValueError, match="Invalid saved"):
        await inv.investigate_news("test", sources=(), imported_batches=[batch.model_copy(update={"source_count": 50})])


@pytest.mark.asyncio
async def test_timeline_fingerprint_changes_with_evidence(monkeypatch):
    original = collector.collect_news
    counts = iter((1, 2))

    def fake(source, *, execute=False, cache=None, **kwargs):
        plan = original(source, **kwargs)
        if not execute:
            return plan
        return {**plan, "status": "observed", "captured_at": CUT, "http_status": 200,
                "network_performed": True, "provider_requests": 1,
                "evidence": {"schema_version": 1, "provider": "gdelt_doc",
                             "attribution": "The GDELT Project (https://www.gdeltproject.org/)",
                             "metric": "matched_and_monitored_articles", "status": "observed",
                             "points": [{"interval_at": "2026-11-28T10:00:00Z",
                                         "matched": next(counts), "monitored": 100}]}}

    monkeypatch.setattr(inv, "collect_news", fake)
    opts = {"sources": ("gdelt_timeline",), "execute": True}
    a = await inv.investigate_news("test", **opts)
    b = await inv.investigate_news("test", **opts)
    assert a["coverage_timeline"]["weighted_coverage_pct"] == 1
    assert b["coverage_timeline"]["weighted_coverage_pct"] == 2
    assert a["run_id"] != b["run_id"]
