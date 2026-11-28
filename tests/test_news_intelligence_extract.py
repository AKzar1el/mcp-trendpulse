"""V4.03 offline evidence and transport provenance regressions."""
from datetime import datetime, timezone
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from mcp_trendpulse import news
from mcp_trendpulse import news_intelligence_extract as extraction
from mcp_trendpulse.news_intelligence_schema import NewsArticle, TimeEvidence

NOW = datetime(2026, 11, 28, 12, tzinfo=timezone.utc)
ORIGINAL = "https://news.google.com/rss/articles/abc"
RESOLVED = "https://example.org/news/story?ref=feed"
BODY = "A substantial example article. This body is not persisted in the extraction report."


def observation():
    return NewsArticle(
        discovery_provider="google_news_rss", link_type="google_news_rss", reported_url=ORIGINAL,
        title="Original feed title", publisher_label="Feed publisher",
        published_at=TimeEvidence(value="2026-11-27T10:00:00Z", precision="second", basis="legacy_normalized"),
        capture_mode="legacy_import", captured_at="2026-11-28T10:00:00Z",
        warnings=("legacy_date_provenance",),
    )


def article(**changes):
    values = {
        "_trendpulse_transport_receipt": (200, RESOLVED),
        "original_url": "https://wrong.example.org/not-transport",
        "canonical_link": "https://example.org/news/story",
        "text": BODY, "title": "Publisher title", "meta_site_name": "Publisher",
        "meta_lang": "en", "publish_date": datetime(2026, 11, 27, 11, tzinfo=timezone.utc),
        "summary": "UNTRUSTED_SUMMARY", "authors": ["UNNEEDED_AUTHOR"],
    }
    return SimpleNamespace(**{**values, **changes})


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    monkeypatch.setattr(extraction, "_now", lambda: NOW)


@pytest.mark.asyncio
async def test_plan_is_offline(monkeypatch):
    downloader = AsyncMock(side_effect=AssertionError("Unexpected network operation"))
    monkeypatch.setattr(news, "download_article", downloader)
    report = await extraction.extract_article(observation())
    assert report.status == "planned" and report.started_at is None
    assert report.discovery == observation()
    downloader.assert_not_awaited()


@pytest.mark.asyncio
async def test_success_preserves_discovery_and_canonical_as_candidate(monkeypatch):
    downloader = AsyncMock(return_value=article())
    monkeypatch.setattr(news, "download_article", downloader)
    report = await extraction.extract_article(observation(), execute=True)
    assert report.status == "extracted" and report.content_level == "extracted_text"
    assert report.http_status == 200
    assert report.discovery == observation()
    assert report.resolved_url == RESOLVED
    assert report.canonical_url_candidate == "https://example.org/news/story"
    assert report.extractor_date.basis == "extractor_reported"
    assert report.extractor_date.source_precision == "unknown"
    assert report.date_relation == "different_reported_values"
    assert report.body_sha256 is None and report.claim_verification == "not_performed"
    wire = report.model_dump_json()
    assert all(x not in wire for x in (BODY, "UNTRUSTED_SUMMARY", "UNNEEDED_AUTHOR", "wrong.example.org"))
    assert extraction.ArticleExtraction.model_validate_json(wire) == report
    downloader.assert_awaited_once_with(ORIGINAL)


@pytest.mark.asyncio
async def test_digest_only_when_explicitly_permitted(monkeypatch):
    monkeypatch.setattr(news, "download_article", AsyncMock(return_value=article()))
    result = await extraction.extract_article(observation(), execute=True, permit_body_digest=True)
    assert result.body_sha256 == sha256(BODY.encode()).hexdigest()
    assert result.body_digest_policy == "operator_permitted"
    assert BODY not in result.model_dump_json()


@pytest.mark.asyncio
@pytest.mark.parametrize("value,expected", [
    (None, "download_unavailable"),
    (ValueError("SECRET_UNSAFE_TARGET"), "download_rejected"),
    (TimeoutError("SECRET_TIMEOUT"), "download_timeout"),
    (RuntimeError("SECRET_TRANSPORT"), "download_failed"),
], ids=["unavailable", "rejected", "timeout", "failure"])
async def test_failed_extraction_preserves_headline_without_exception_leak(monkeypatch, value, expected):
    downloader = AsyncMock(side_effect=value) if isinstance(value, Exception) else AsyncMock(return_value=value)
    monkeypatch.setattr(news, "download_article", downloader)
    report = await extraction.extract_article(observation(), execute=True)
    assert report.reason == expected and report.discovery == observation()
    assert report.content_level == "headline_only" and report.resolved_url is None
    assert report.extractor_date is None and "SECRET_" not in report.model_dump_json()


@pytest.mark.asyncio
@pytest.mark.parametrize("receipt,reason", [
    (None, "missing_transport_receipt"),
    ((206, RESOLVED), "unexpected_http_status"),
    ((200, "http://example.org/story"), "unsafe_resolved_url"),
    ((200, "https://127.0.0.1/"), "unsafe_resolved_url"),
    ((200, "https://news.google.com/rss/articles/abc"), "unsafe_resolved_url"),
    ((200, "https://NEWS.GOOGLE.COM:443/rss/articles/abc"), "unsafe_resolved_url"),
    ((200, "https://example.org/?token=SECRET"), "unsafe_resolved_url"),
])
async def test_missing_or_unsafe_receipt_not_replaced_by_extractor_url(monkeypatch, receipt, reason):
    monkeypatch.setattr(news, "download_article", AsyncMock(return_value=article(_trendpulse_transport_receipt=receipt)))
    report = await extraction.extract_article(observation(), execute=True)
    assert report.status == "rejected" and report.reason == reason and report.resolved_url is None
    assert "SECRET" not in report.model_dump_json()


@pytest.mark.asyncio
@pytest.mark.parametrize("canonical,warning", [
    ("https://other.example.org/story", "cross_host_canonical_candidate"),
    ("https://127.0.0.1/hidden", "invalid_canonical_candidate"),
    ("https://example.org/?token=SECRET", "invalid_canonical_candidate"),
    ("/relative", "invalid_canonical_candidate"),
])
async def test_canonical_never_followed(monkeypatch, canonical, warning):
    downloader = AsyncMock(return_value=article(canonical_link=canonical))
    monkeypatch.setattr(news, "download_article", downloader)
    report = await extraction.extract_article(observation(), execute=True)
    assert report.status == "extracted" and warning in report.warnings
    assert report.resolved_url == RESOLVED
    assert "SECRET" not in report.model_dump_json()
    downloader.assert_awaited_once_with(ORIGINAL)


@pytest.mark.asyncio
@pytest.mark.parametrize("date_value,relation,warning", [
    (datetime(2026, 11, 27, 10), "not_comparable", "invalid_extractor_date"),
    ("2026-11-27", "not_comparable", None),
    ("2026-11-27T11:00:00+01:00", "same_reported_value", None),
    ("2026-11-29T12:00:00Z", "not_comparable", "future_extractor_date"),
])
async def test_date_precision_and_confidence(monkeypatch, date_value, relation, warning):
    monkeypatch.setattr(news, "download_article", AsyncMock(return_value=article(publish_date=date_value)))
    result = await extraction.extract_article(observation(), execute=True)
    assert result.date_relation == relation
    assert result.discovery.published_at.value == "2026-11-27T10:00:00Z"
    if warning:
        assert warning in result.warnings and result.extractor_date is None


@pytest.mark.asyncio
async def test_empty_text_never_promoted(monkeypatch):
    monkeypatch.setattr(news, "download_article", AsyncMock(return_value=article(text=" ")))
    result = await extraction.extract_article(observation(), execute=True)
    assert result.reason == "invalid_extracted_text" and result.content_level == "headline_only"


@pytest.mark.asyncio
async def test_forged_discovery_instance_fails_before_network(monkeypatch):
    downloader = AsyncMock()
    monkeypatch.setattr(news, "download_article", downloader)
    forged = observation().model_copy(update={"reported_url": "https://127.0.0.1/"})
    with pytest.raises(ValidationError):
        await extraction.extract_article(forged, execute=True)
    downloader.assert_not_awaited()


@pytest.mark.asyncio
async def test_forged_receipt_rejected(monkeypatch):
    monkeypatch.setattr(news, "download_article", AsyncMock(return_value=article()))
    result = await extraction.extract_article(observation(), execute=True)
    data = result.model_dump()
    with pytest.raises(ValidationError):
        extraction.ArticleExtraction.model_validate({**data, "date_relation": "same_reported_value"})
    with pytest.raises(ValidationError):
        extraction.ArticleExtraction.model_validate({**data, "body_sha256": "0" * 64})


def test_actual_transport_captures_response_url_not_parser_guess():
    # Test the real legacy scraper with an isolated mock transport. No DNS or HTTP.
    validator = MagicMock()
    validator.validate_url.side_effect = lambda value: value
    response = MagicMock(status_code=200, url=RESOLVED)
    response.headers = {"Content-Type": "text/html"}
    response.encoding = "utf-8"
    response.iter_content.return_value = [b"<html>publisher page</html>"]
    scraper = MagicMock()
    scraper.get.return_value = response
    parsed = article(_trendpulse_transport_receipt=None)
    with (patch.object(news, "get_scraper", return_value=scraper),
          patch.object(news.newspaper, "article", return_value=parsed)):
        assert news.download_article_with_scraper("https://example.org/original", validator) is parsed
    assert parsed._trendpulse_transport_receipt == (200, RESOLVED)
    response.close.assert_called_once()

def direct_observation():
    return NewsArticle(
        discovery_provider="gdelt_doc", link_type="publisher_candidate",
        reported_url="https://example.org/story", title="Source headline",
        capture_mode="legacy_import", captured_at="2026-11-28T10:00:00Z",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("status,reason", [
    (401, "http_access_denied"), (402, "http_payment_required"),
    (403, "http_access_denied"), (429, "http_rate_limited"), (503, "http_error"),
])
async def test_real_downloader_preserves_explicit_http_failure(monkeypatch, status, reason):
    # Actual async worker/legacy scraper path, but no DNS, network or paid services.
    validator = MagicMock()
    validator.validate_url.side_effect = lambda value: value
    monkeypatch.setattr(news, "ArticleTargetValidator", lambda: validator)
    response = MagicMock(status_code=status, url=RESOLVED)
    response.headers = {"Content-Type": "text/html"}
    scraper = MagicMock()
    scraper.get.return_value = response
    monkeypatch.setattr(news, "get_scraper", lambda: scraper)
    report = await extraction.extract_article(direct_observation(), execute=True)
    assert report.status == "unavailable" and report.reason == reason
    assert report.http_status == status and report.content_level == "headline_only"
    assert report.discovery == direct_observation()
    assert scraper.get.call_count == 1
    assert news._article_download_trace.get() is None


@pytest.mark.asyncio
async def test_non_html_is_not_an_empty_article(monkeypatch):
    validator = MagicMock()
    validator.validate_url.side_effect = lambda value: value
    monkeypatch.setattr(news, "ArticleTargetValidator", lambda: validator)
    response = MagicMock(status_code=200, url=RESOLVED)
    response.headers = {"Content-Type": "application/pdf"}
    scraper = MagicMock()
    scraper.get.return_value = response
    monkeypatch.setattr(news, "get_scraper", lambda: scraper)
    report = await extraction.extract_article(direct_observation(), execute=True)
    assert report.status == "rejected" and report.reason == "unsupported_content_type"
    assert report.http_status == 200
    response.iter_content.assert_not_called()


def test_trace_is_closed_against_late_worker_result():
    trace = news._ArticleDownloadTrace()
    trace.record("download_timeout")
    assert trace.close() == ("download_timeout", None)
    trace.record("http_access_denied", 403, replace=True)
    assert trace.close() == ("download_timeout", None)


@pytest.mark.asyncio
async def test_cancelled_attempt_releases_context(monkeypatch):
    import asyncio
    monkeypatch.setattr(news, "download_article", AsyncMock(side_effect=asyncio.CancelledError()))
    with pytest.raises(asyncio.CancelledError):
        await extraction.extract_article(observation(), execute=True)
    assert news._article_download_trace.get() is None
