"""M07 Hacker News Algolia: one-page, source-grounded, zero-network tests."""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from io import BytesIO

import pytest
from click.testing import CliRunner

from mcp_trendpulse import intelligence_hn_algolia as hn
from mcp_trendpulse.cli import cli
from mcp_trendpulse.intelligence_core import BudgetCache

NOW = datetime(2026, 11, 20, 22, 25, tzinfo=timezone.utc)
QUERY = "agent reliability"
STAMP = datetime(2026, 11, 18, 15, tzinfo=timezone.utc)
SOURCE = "hacker_news_algolia"


def story(number=12345678, when=STAMP, *, title="Agent reliability in production", tags=None):
    return {
        "objectID": str(number), "title": title, "url": "https://example.com/thing",
        "created_at": when.isoformat().replace("+00:00", "Z"),
        "created_at_i": int(when.timestamp()),
        "points": 42, "num_comments": 12,
        "_tags": tags if tags is not None else ["story"],
        "story_text": "untrusted_SECRET_BODY",
        "author": "untrusted_secret_author",
    }


def comment(number=22345678, thread=12345678, when=STAMP):
    return {
        "objectID": str(number), "story_id": thread,
        "parent_id": 111,
        "story_title": "Agent reliability in production",
        "comment_text": "sensitive_comment_BODY",
        "created_at": when.isoformat().replace("+00:00", "Z"),
        "created_at_i": int(when.timestamp()),
        "author": "do_not_store_this_user",
        "_tags": ["comment", f"story_{thread}"],
    }


def payload(*hits, total=None, pages=1, cap=10):
    return {
        "hits": list(hits),
        "nbHits": len(hits) if total is None else total,
        "nbPages": pages if hits else 0,
        "hitsPerPage": cap, "page": 0,
        "processingTimeMS": 1,
        "query": QUERY,
    }


class Fetcher:
    def __init__(self, data=None, *, status=200, error=None):
        self.data = data if data is not None else payload(story())
        self.status = status
        self.error = error
        self.calls = []

    def __call__(self, url, params):
        self.calls.append((url, dict(params)))
        if self.error is not None:
            raise self.error
        return self.status, self.data


def run(tmp_path, client, *, query=QUERY, tag="story", days=14, limit=10):
    return hn.discover_hn_discussions(
        query=query, tag=tag, days=days, limit=limit, execute=True,
        cache=BudgetCache(tmp_path), fetcher=client, observed_at=NOW,
    )


def test_plan_only_never_opens_sqlite_or_fetches(monkeypatch):
    monkeypatch.setattr(hn, "BudgetCache", lambda *_a, **_kw: (
        (_ for _ in ()).throw(AssertionError("Offline plan must never open SQLite"))
    ))
    monkeypatch.setattr(hn, "_fetch", lambda *_a: (
        (_ for _ in ()).throw(AssertionError("Offline plan must never fetch"))
    ))
    out = hn.discover_hn_discussions(query=QUERY, observed_at=NOW)
    assert out["status"] == "planned"
    assert out["source_url"] == hn.URL
    assert out["requests_attempted"] == 0
    assert out["network_performed"] is False
    assert out["signals"] == []
    assert out["source_total_matches_reported"] is None
    assert out["window"]["end_epoch_exclusive"] == int(
        datetime(2026, 11, 20, 22, tzinfo=timezone.utc).timestamp()
    )
    assert out["query_provenance"] == "manual_research_phrase"
    assert out["country"] is None and out["language"] is None


@pytest.mark.parametrize("options", [
    {"query": "agent reliability\nSECRET"},
    {"query": "https://example.com"},
    {"query": "@someone"},
    {"query": "xy"},
    {"query": "a" * 91},
    {"query": " agent reliability"},
    {"query": 8},
    {"tag": "user"},
    {"tag": "(story,comment)"},
    {"days": 0},
    {"days": 31},
    {"days": True},
    {"limit": 0},
    {"limit": 21},
    {"limit": True},
    {"execute": "true"},
])
def test_invalid_inputs_rejected_before_network(options):
    kw = dict(query=QUERY, observed_at=NOW)
    kw.update(options)
    with pytest.raises(ValueError):
        hn.discover_hn_discussions(**kw)


def test_story_source_ids_and_date_sample_not_total_market(tmp_path):
    client = Fetcher(data=payload(
        story(12345678, STAMP),
        story(12345679, STAMP + timedelta(minutes=1), title="How to test AI agents"),
        story(12345680, STAMP + timedelta(days=1), title="Show HN: agent checks"),
        total=137, pages=14,
    ))
    out = run(tmp_path, client)
    assert out["status"] == "observed_partial"
    assert out["source_rows_received"] == 3
    assert out["source_rows_rejected"] == 0
    assert out["source_total_matches_reported"] == 137
    assert out["matching_hits_not_fetched_reported"] == 134
    assert out["source_other_pages_present"] is True
    assert out["summary"]["unit"] == "distinct_story_items"
    assert out["summary"]["observed_items_on_returned_page"] == 3
    assert out["summary"]["distinct_discussion_threads_on_returned_page"] == 3
    assert out["summary"]["distinct_utc_days_on_returned_page"] == 2
    assert out["summary"]["daily_sample_counts"] == [
        {"date": "2026-11-18", "count": 2},
        {"date": "2026-11-19", "count": 1},
    ]
    assert out["summary"]["not_all_hacker_news_items_counted"] is True
    assert out["customer_demand_verified"] is False
    assert len(out["signals"]) == 2
    assert [s["value"] for s in out["signals"]] == [2, 1]
    assert all(s["metric_type"] == "hacker_news_story_mentions" for s in out["signals"])
    assert all(s["metric_unit"] == "stories" for s in out["signals"])
    assert all(s["coverage_status"] == "partial" for s in out["signals"])
    assert all(s["country"] is None and s["language"] is None for s in out["signals"])
    assert all(s["provenance"]["method"] == "public_api" for s in out["signals"])
    assert all(not s["provenance"]["is_observed_search_query"] for s in out["signals"])
    assert all(s["period"]["granularity"] == "daily" for s in out["signals"])
    assert out["requests_attempted"] == 1 and out["network_performed"]
    endpoint, params = client.calls[0]
    assert endpoint == hn.URL
    assert params["query"] == QUERY and params["tags"] == "story"
    assert params["page"] == "0" and params["hitsPerPage"] == "10"
    start, end = out["window"]["start_epoch_inclusive"], out["window"]["end_epoch_exclusive"]
    assert params["numericFilters"] == f"created_at_i>={start},created_at_i<{end}"
    assert not any(k in params for k in ("apikey", "auth", "token"))
    assert "untrusted_SECRET_BODY" not in json.dumps(out)
    assert "untrusted_secret_author" not in json.dumps(out)
    assert len({r["item_id"] for r in out["records"]}) == 3
    assert all(r["hn_url"].startswith("https://news.ycombinator.com/item?id=")
               for r in out["records"])

    hit = run(tmp_path, client)
    assert hit["cache_hit"] is True and hit["requests_attempted"] == 0
    assert hit["network_performed"] is False
    assert hit["summary"] == out["summary"]
    assert hit["signals"] == out["signals"]
    assert len(client.calls) == 1


def test_comment_matches_are_not_story_or_customer_counts(tmp_path):
    comments = payload(
        comment(22345678, 12345678),
        comment(22345679, 12345678, when=STAMP + timedelta(minutes=5)),
        comment(22345680, 12345690, when=STAMP + timedelta(minutes=8)),
    )
    out = run(tmp_path, Fetcher(data=comments), tag="comment")
    assert out["status"] == "observed"
    assert out["kind"] == "comment"
    assert out["summary"]["unit"] == "comment_matches"
    assert out["summary"]["observed_items_on_returned_page"] == 3
    assert out["summary"]["distinct_discussion_threads_on_returned_page"] == 2
    assert out["summary"]["distinct_utc_days_on_returned_page"] == 1
    assert out["signals"] == []  # Do not mislabel comment matches as story counts.
    assert "sensitive_comment_BODY" not in json.dumps(out)
    assert "do_not_store_this_user" not in json.dumps(out)
    repeat = run(tmp_path, Fetcher(error=RuntimeError("NO_NETWORK")), tag="comment")
    assert repeat["status"] == "observed" and repeat["cache_hit"]
    assert repeat["requests_attempted"] == 0


@pytest.mark.parametrize("tag", ["show_hn", "ask_hn"])
def test_launch_and_question_tags_stay_distinct(tmp_path, tag):
    out = run(
        tmp_path,
        Fetcher(data=payload(story(tags=["story", tag]))),
        tag=tag,
    )
    assert out["status"] == "observed"
    assert out["summary"]["unit"] == "distinct_story_items"
    assert len(out["signals"]) == 1
    mismatch = run(
        tmp_path / "mismatch",
        Fetcher(data=payload(story(tags=["story"]))),
        tag=tag,
    )
    assert mismatch["status"] == "invalid_source_shape"
    assert mismatch["signals"] == []


def test_duplicates_are_dropped_and_disclosed(tmp_path):
    out = run(tmp_path, Fetcher(data=payload(story(), story())))
    assert out["status"] == "observed_partial"
    assert out["source_rows_received"] == 2
    assert out["source_rows_rejected"] == 1
    assert out["summary"]["observed_items_on_returned_page"] == 1
    assert out["summary"]["distinct_utc_days_on_returned_page"] == 1
    assert len(out["signals"]) == 1


def test_missing_engagement_counters_are_not_zero(tmp_path):
    record = story()
    record["points"] = None
    record.pop("num_comments")
    out = run(tmp_path, Fetcher(data=payload(record)))
    assert out["status"] == "observed"
    assert out["records"][0]["points"] is None
    assert out["records"][0]["num_comments"] is None


def test_missing_and_out_of_scope_rows_do_not_invent_activity(tmp_path):
    old = story(33333333, NOW - timedelta(days=50))
    wrong = story(44444444)
    wrong["_tags"] = ["comment"]
    bad_timestamp = story(55555555)
    bad_timestamp["created_at"] = "2026-11-20T22:25:00Z"
    data = payload(story(), old, wrong, bad_timestamp)
    out = run(tmp_path, Fetcher(data=data))
    assert out["status"] == "observed_partial"
    assert out["source_rows_received"] == 4
    assert out["source_rows_rejected"] == 3
    assert len(out["records"]) == 1
    assert len(out["signals"]) == 1


def test_invalid_source_scope_or_envelope_not_treated_as_no_data(tmp_path):
    shapes = [
        {"hits": "PRIVATE", "nbHits": 1, "nbPages": 1, "page": 0, "hitsPerPage": 10},
        {"hits": [], "nbHits": 5, "nbPages": 2, "page": 0, "hitsPerPage": 10},
        {"hits": [story()], "nbHits": 1, "nbPages": 1, "page": 1, "hitsPerPage": 10},
        {"hits": [story()], "nbHits": 1, "nbPages": 1, "page": 0, "hitsPerPage": 99},
        {"hits": [story()], "nbHits": "1", "nbPages": 1, "page": 0, "hitsPerPage": 10},
        {"hits": [story()] * 11, "nbHits": 11, "nbPages": 2, "page": 0, "hitsPerPage": 10},
        {"error": {"message": "PRIVATE_API_ERROR"}},
    ]
    for i, data in enumerate(shapes):
        out = run(tmp_path / str(i), Fetcher(data=data))
        assert out["status"] == "invalid_source_shape"
        assert out["records"] == [] and out["signals"] == []
        assert "PRIVATE" not in repr(out)


def test_empty_page_is_unknown_coverage_not_zero_demand(tmp_path):
    out = run(tmp_path, Fetcher(data=payload()))
    assert out["status"] == "no_data"
    assert out["summary"]["observed_items_on_returned_page"] == 0
    assert out["signals"] == []
    assert out["customer_demand_verified"] is False
    assert out["source_total_matches_reported"] == 0
    assert out["search_volume_verified"] is False


@pytest.mark.parametrize(("code", "expected"), [
    (401, "provider_unavailable"), (403, "provider_unavailable"),
    (429, "provider_rate_limited"), (503, "provider_rate_limited"),
    (500, "provider_unavailable"), (302, "provider_unavailable"),
])
def test_failure_cooldown_and_no_raw_error_leak(tmp_path, code, expected):
    client = Fetcher(status=code, data={"token": "PRIVATE_PROVIDER_DATA"})
    out = run(tmp_path, client)
    assert out["status"] == expected
    assert len(client.calls) == 1
    assert "PRIVATE_PROVIDER_DATA" not in json.dumps(out)
    if code in (429, 503):
        new_client = Fetcher()
        blocked = run(tmp_path, new_client, query="different test term")
        assert blocked["status"] == "provider_cooldown"
        assert blocked["requests_attempted"] == 0
        assert new_client.calls == []


def test_upstream_exception_does_not_leak_authenticated_urls(tmp_path):
    out = run(tmp_path, Fetcher(error=RuntimeError(
        "Unauthorized https://private.domain.example?token=SECRET"
    )))
    assert out["status"] == "provider_unavailable"
    assert out["requests_attempted"] == 1
    assert "SECRET" not in repr(out)
    assert "private.domain" not in repr(out)


def test_shared_daily_limit_with_one_request_per_uncached_query(tmp_path):
    client = Fetcher(data=payload())
    for i in range(hn.UTC_DAILY_REQUEST_CAP):
        out = run(tmp_path, client, query=f"agent reliability subject {i}")
        assert out["status"] == "no_data"
    assert len(client.calls) == hn.UTC_DAILY_REQUEST_CAP
    blocked = run(tmp_path, client, query="unseen new investigation")
    assert blocked["status"] == "local_daily_budget_exhausted"
    assert blocked["requests_attempted"] == 0
    assert len(client.calls) == hn.UTC_DAILY_REQUEST_CAP


def test_cache_metadata_redaction_and_tamper_fail_closed(tmp_path):
    client = Fetcher(data=payload(story()))
    first = run(tmp_path, client)
    assert first["status"] == "observed"
    window = hn._observed_scope(tag="story", days=14, limit=10, observed_at=NOW)
    key = hn._key(QUERY, "story", 10, window)
    db = BudgetCache(tmp_path)
    original = db.cached(key)
    assert isinstance(original, dict)
    db.save(key, {**original, "private_token": "SHOULD_NEVER_SHOW"},
            hn.CACHE_TTL_SECONDS)
    cached = run(tmp_path, client)
    assert cached["cache_hit"] and cached["requests_attempted"] == 0
    assert "SHOULD_NEVER_SHOW" not in repr(cached)

    db.save(key, {**original, "records": [
        {"item_id": "INVALID", "token": "DONT_EXPOSE"},
    ]}, hn.CACHE_TTL_SECONDS)
    for i in range(hn.UTC_DAILY_REQUEST_CAP - 1):
        db.reserve(SOURCE, hn.UTC_DAILY_REQUEST_CAP)
    other = Fetcher()
    blocked = run(tmp_path, other)
    assert blocked["status"] == "local_daily_budget_exhausted"
    assert blocked["requests_attempted"] == 0
    assert other.calls == []
    assert "DONT_EXPOSE" not in repr(blocked)


def test_cache_fail_closed_on_storage_unavailable():
    class Broken:
        def cached(self, *_args):
            raise OSError("SECRET path")
    client = Fetcher()
    result = hn.discover_hn_discussions(
        query=QUERY, execute=True, observed_at=NOW,
        cache=Broken(), fetcher=client,
    )
    assert result["status"] == "local_budget_unavailable"
    assert result["requests_attempted"] == 0
    assert client.calls == []
    assert "SECRET" not in repr(result)


def test_transport_single_fixed_host_no_proxy_no_redirect_and_bounded_body(monkeypatch):
    import requests

    class Stream:
        def __init__(self, body):
            self.stream = BytesIO(body)
        def read(self, maximum, decode_content=False):
            assert maximum == hn.MAX_RESPONSE_BYTES + 1
            return self.stream.read(maximum)

    class Response:
        status_code = 200
        headers = {"Content-Type": "application/json"}
        raw = Stream(b'{"hits":[]}')
        def __enter__(self):
            return self
        def __exit__(self, *_a):
            return None

    sessions = []

    class Session:
        trust_env = True
        def __init__(self):
            sessions.append(self)
        def get(self, url, *, params, stream, allow_redirects, timeout, headers):
            assert url == hn.URL and self.trust_env is False
            assert params["page"] == "0"
            assert not allow_redirects and stream
            assert timeout == (5, 12)
            assert "github.com/AKzar1el/mcp-trendpulse" in headers["User-Agent"]
            return Response()
        def close(self):
            self.closed = True

    monkeypatch.setattr(requests, "Session", Session)
    http, data = hn._fetch(hn.URL, {"page": "0"})
    assert http == 200 and data == {"hits": []}
    assert sessions[-1].closed
    Response.raw = Stream(b"X" * (hn.MAX_RESPONSE_BYTES + 1))
    with pytest.raises(hn.ResponseTooLarge):
        hn._fetch(hn.URL, {"page": "0"})
    assert sessions[-1].closed
    with pytest.raises(ValueError):
        hn._fetch("https://hn.algolia.com.evil.tld/api/v1/search_by_date", {})


def test_cli_preview_never_fetches_and_invalid_tag_refused():
    runner = CliRunner()
    preview = runner.invoke(cli, [
        "intelligence", "hn-discussions", "--query", QUERY,
        "--tag", "story", "--days", "14", "--limit", "10", "--format", "json",
    ])
    assert preview.exit_code == 0, preview.output
    body = json.loads(preview.output)
    assert body["status"] == "planned"
    assert body["network_performed"] is False
    assert body["requests_attempted"] == 0
    bad = runner.invoke(cli, [
        "intelligence", "hn-discussions", "--query", QUERY,
        "--tag", "author_foo", "--format", "json",
    ])
    assert bad.exit_code != 0
    assert "invalid" in bad.output.lower()
