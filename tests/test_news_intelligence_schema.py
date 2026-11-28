"""Synthetic, no-network tests for the additive V4.02 foundation."""
import json
from urllib.parse import parse_qs, urlsplit

import pytest
from pydantic import ValidationError

from mcp_trendpulse.news_intelligence_schema import (
    GDELT_ATTRIBUTION,
    MAX_BYTES,
    NASA_ATTRIBUTION,
    NewsArticle,
    NewsBatch,
    TimeEvidence,
    gdelt_doc_request,
    nasa_rss_request,
    parse_gdelt_raw_timeline,
    parse_nasa_rss_capture,
    parse_news_capture,
)

CAPTURE = "2026-11-28T13:00:00Z"


def _json(data):
    return json.dumps(data, ensure_ascii=False).encode()


def _row(**changes):
    return {"title": "New research in Črnomelj", "url": "https://example.org/news?a=1",
            "domain": "example.org", "seendate": "20261128T120000Z", "language": "Slovenian",
            "sourcecountry": "Slovenia", **changes}


def _gdelt(*rows, **kwargs):
    return parse_news_capture(_json({"articles": rows}), provider="gdelt_doc", captured_at=CAPTURE, **kwargs)


def test_gdelt_provenance_and_roundtrip():
    result = _gdelt(_row(socialimage="https://example.org/image.jpg", body="ignored"))
    assert result.status == "observed" and result.source_count == 1
    assert result.attribution == GDELT_ATTRIBUTION
    article = result.articles[0]
    assert article.published_at is None and article.provider_seen_at.basis == "provider_seen"
    assert article.reported_source_country == "Slovenia" and article.reported_language == "Slovenian"
    assert article.capture_mode == "legacy_import" and article.content_level == "headline_only"
    assert "socialimage" not in result.model_dump_json() and "ignored" not in result.model_dump_json()
    assert NewsBatch.model_validate_json(result.model_dump_json()) == result


def test_ids_are_stable_but_revisions_distinct():
    one = _gdelt(_row()).articles[0]
    two = _gdelt(_row(title="Updated headline")).articles[0]
    assert one == _gdelt(_row()).articles[0]
    assert one.article_id == two.article_id and one.observation_id != two.observation_id
    bad = one.model_dump()
    bad["observation_id"] = "0" * 64
    with pytest.raises(ValidationError):
        NewsArticle.model_validate(bad)


def test_explicit_counts_duplicates_and_truncation():
    result = _gdelt(_row(), _row(), _row(url="http://example.org/legacy"), _row(title="Other"), limit=3)
    assert result.status == "partial" and result.possibly_capped
    assert (result.source_count, result.invalid_count, result.duplicate_count, result.truncated_count) == (4, 1, 1, 1)
    assert len(result.articles) == 1


@pytest.mark.parametrize("url", ["https://127.0.0.1/a", "https://2130706433/a", "https://example.org/?token=secret",
                                "https://user:pass@example.org/a", "https://example.org/%0a", "https://example.org\\evil",
                                "https://example.org/#fragment", "https://news.google.com/rss/articles/abc", "http://example.org/a"])
def test_unsafe_or_misclassified_links(url):
    result = _gdelt(_row(url=url))
    assert result.status == "invalid" and result.invalid_count == 1 and not result.articles


@pytest.mark.parametrize("raw", [b"{}", b"<html>provider error</html>", b'{"articles":[],"articles":[]}',
                                b'{"articles":[],"x":NaN}', b'{"articles":[],"x":1e999}', pytest.param(b" " * (MAX_BYTES + 1), id="oversized-payload")])
def test_invalid_payload_is_not_empty(raw):
    result = parse_news_capture(raw, provider="gdelt_doc", captured_at=CAPTURE)
    assert result.status == "invalid" and result.source_count is None


def test_explicit_empty_and_legacy_capture_unknown():
    empty = _gdelt()
    assert empty.status == "empty" and empty.source_count == 0
    result = parse_news_capture(_json({"articles": [_row()]}), provider="gdelt_doc", captured_at=None)
    assert result.articles[0].captured_at is None


def test_gdelt_date_errors_never_become_publication():
    for seen in (None, "not a date", "2026-11-28T12:00:00"):
        result = _gdelt(_row(seendate=seen))
        assert result.articles[0].provider_seen_at is None and result.articles[0].warnings
    assert _gdelt(_row(seendate="20261128T140000Z")).status == "invalid"


def test_legacy_rss_requires_evidence_marker_and_preserves_date_precision():
    row = {"title": "Headlines only", "url": "https://news.google.com/rss/articles/abc", "publish_date": "2026-11-27",
           "meta_site_name": "Example", "meta_data": {"source": "google_news_rss", "content_level": "rss_headline_only"},
           "text": "not publisher evidence"}
    result = parse_news_capture(_json([row]), provider="google_news_rss", captured_at=CAPTURE)
    article = result.articles[0]
    assert article.published_at.precision == "day" and article.published_at.value == "2026-11-27"
    assert article.warnings == ("legacy_date_provenance",) and article.provider_seen_at is None
    assert "not publisher evidence" not in result.model_dump_json()
    row.pop("meta_data")
    assert parse_news_capture(_json([row]), provider="google_news_rss", captured_at=CAPTURE).status == "invalid"


@pytest.mark.parametrize("value", ["2026-11-28T12:00:00", "2026-11-28T12:00:00Z ", "2026-02-30T12:00:00Z"])
def test_time_requires_real_offset(value):
    with pytest.raises(ValidationError):
        TimeEvidence(value=value, precision="second", basis="provider_seen")


def test_rejects_forged_batch_status_and_attribution():
    data = _gdelt(_row()).model_dump()
    for changes in ({"status": "empty"}, {"attribution": "Other"}, {"schema_version": True}, {"source_count": 2}):
        with pytest.raises(ValidationError):
            NewsBatch.model_validate({**data, **changes})


def test_request_is_fixed_origin_and_no_io():
    plan = gdelt_doc_request("renewable energy", as_of=CAPTURE, days=3, limit=3)
    url = urlsplit(plan["url"])
    args = parse_qs(url.query)
    assert url.netloc == "api.gdeltproject.org" and args["query"] == ['"renewable energy"']
    assert args["startdatetime"] == ["20261125130000"] and args["maxrecords"] == ["3"]
    assert plan["status"] == "planned" and plan["network_performed"] is False
    timeline = gdelt_doc_request("energy", as_of=CAPTURE, mode="timelinevolraw")
    timeline_args = parse_qs(urlsplit(timeline["url"]).query)
    assert "maxrecords" not in timeline_args
    assert timeline_args["timelinesmooth"] == ["1"]


@pytest.mark.parametrize("phrase", ['news" OR "x', "sourcecountry:US", "a\nheader", "1", "a&format=html"])
def test_request_rejects_query_operators(phrase):
    with pytest.raises(ValueError):
        gdelt_doc_request(phrase, as_of=CAPTURE)


def _timeline(*rows):
    return parse_gdelt_raw_timeline(_json({"timeline": [{"series": "Article Count", "data": rows}]}))


def test_timeline_keeps_counts_and_denominators_separate():
    result = _timeline({"date": "20261128T120000Z", "value": 3, "norm": 20}, {"date": "20261128T110000Z", "value": 0, "norm": 0})
    assert result.status == "observed" and result.attribution == GDELT_ATTRIBUTION
    assert [(p.matched, p.monitored) for p in result.points] == [(0, 0), (3, 20)]
    assert _timeline().status == "empty"
    assert parse_gdelt_raw_timeline(b'{"timeline":[]}').status == "empty"


@pytest.mark.parametrize("row", [{"value": 3}, {"value": 4, "norm": 3}, {"value": 1.2, "norm": 3},
                                 {"value": True, "norm": 3}, {"value": -1, "norm": 3}])
def test_invalid_timeline_counts_rejected(row):
    with pytest.raises(ValueError):
        _timeline({"date": "20261128T120000Z", **row})


def test_duplicate_interval_and_missing_series_rejected():
    row = {"date": "20261128T120000Z", "value": 3, "norm": 20}
    with pytest.raises(ValueError):
        _timeline(row, row)
    with pytest.raises(ValueError):
        parse_gdelt_raw_timeline(b"{}")


@pytest.mark.parametrize("error", [
    {"status": "error"},
    {"status": " FAILED "},
    {"error": "temporarily unavailable"},
    {"errors": ["provider failure"]},
    {"fault": {"code": "upstream_error"}},
])
def test_source_error_never_becomes_empty_evidence(error):
    batch = parse_news_capture(
        _json({"articles": [], **error}), provider="gdelt_doc", captured_at=CAPTURE,
    )
    assert batch.status == "invalid" and batch.source_count is None
    with pytest.raises(ValueError, match="error envelope"):
        parse_gdelt_raw_timeline(_json({"timeline": [], **error}))

def _nasa_xml(*items):
    return (
        '<rss version="2.0"><channel><title>NASA</title>'
        '<link>https://www.nasa.gov/</link><description>News</description>'
        + "".join(items) + "</channel></rss>"
    ).encode()


def _nasa_item(link="https://www.nasa.gov/example", date="Fri, 27 Nov 2026 12:00:00 +0000"):
    return (
        "<item><title>Research update</title><link>" + link + "</link>"
        "<pubDate>" + date + "</pubDate>"
        "<description>Full body must never be persisted</description></item>"
    )


def test_nasa_feed_is_fixed_and_metadata_only():
    plan = nasa_rss_request()
    assert plan["url"] == "https://www.nasa.gov/feed/"
    assert plan["network_performed"] is False
    batch = parse_nasa_rss_capture(_nasa_xml(_nasa_item()), captured_at=CAPTURE)
    assert batch.status == "observed" and batch.attribution == NASA_ATTRIBUTION
    article = batch.articles[0]
    assert article.publisher_label == "NASA" and article.published_at.basis == "feed"
    assert article.content_level == "headline_only" and article.provider_seen_at is None
    assert article.reported_language is None and article.reported_source_country is None
    assert "Full body" not in batch.model_dump_json()
    assert NewsBatch.model_validate_json(batch.model_dump_json()) == batch


def test_nasa_feed_counts_and_publisher_scope():
    batch = parse_nasa_rss_capture(
        _nasa_xml(_nasa_item(), _nasa_item(), _nasa_item("https://example.org/"),
                  _nasa_item("https://science.nasa.gov/example"), _nasa_item()),
        captured_at=CAPTURE, limit=4,
    )
    assert batch.status == "partial"
    assert (batch.source_count, batch.invalid_count, batch.duplicate_count, batch.truncated_count) == (5, 1, 1, 1)
    assert len(batch.articles) == 2
    assert batch.articles[1].reported_url == "https://science.nasa.gov/example"


@pytest.mark.parametrize("date", ["Fri, 27 Nov 2026 12:00:00 -0000", "malformed"])
def test_nasa_feed_unknown_dates_are_not_inferred(date):
    batch = parse_nasa_rss_capture(_nasa_xml(_nasa_item(date=date)), captured_at=CAPTURE)
    assert batch.articles[0].published_at is None
    assert batch.articles[0].warnings == ("invalid_source_date",)


def test_nasa_feed_future_and_ambiguous_items_rejected():
    future = _nasa_item(date="Sun, 29 Nov 2026 12:00:00 +0000")
    ambiguous = _nasa_item().replace("</item>", "<link>https://www.nasa.gov/other</link></item>")
    batch = parse_nasa_rss_capture(_nasa_xml(future, ambiguous), captured_at=CAPTURE)
    assert batch.status == "invalid" and batch.invalid_count == 2


@pytest.mark.parametrize("raw", [
    b"<rss/>",
    b"<html>not a feed</html>",
    b'<!DOCTYPE rss [<!ENTITY x SYSTEM "file:///etc/passwd">]><rss/>',
    pytest.param(b" " * (MAX_BYTES + 1), id="oversized-payload"),
    b"\xff\xfe<rss/>",
    _nasa_xml().replace(b"https://www.nasa.gov/", b"https://example.org/"),
])
def test_nasa_invalid_capture_is_not_zero(raw):
    batch = parse_nasa_rss_capture(raw, captured_at=CAPTURE)
    assert batch.status == "invalid" and batch.source_count is None


def test_nasa_explicit_empty_and_legacy_capture():
    assert parse_nasa_rss_capture(_nasa_xml(), captured_at=CAPTURE).status == "empty"
    batch = parse_nasa_rss_capture(_nasa_xml(_nasa_item()), captured_at=None)
    assert batch.articles[0].captured_at is None
    assert batch.articles[0].capture_mode == "legacy_import"

@pytest.mark.parametrize("url", [
    "https://224.0.0.1/a", "https://[ff02::1]/a", "https://[fec0::1]/a",
])
def test_non_unicast_literal_addresses_are_not_citations(url):
    batch = _gdelt(_row(url=url))
    assert batch.status == "invalid" and batch.invalid_count == 1
