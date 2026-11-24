"""M06 Wikimedia daily article views: source-scoped, quota-safe offline tests."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest
from click.testing import CliRunner

from mcp_trendpulse import intelligence_wikimedia as wiki
from mcp_trendpulse.cli import cli
from mcp_trendpulse.intelligence_core import BudgetCache, DailyBudgetExceeded

NOW = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
TITLE = "Python (programming language)"
PROJECT = "en.wikipedia.org"
END = "2026-11-17"


def metadata(*, title=TITLE, missing=False, redirect=False, disambiguation=False):
    item = {
        "pageid": 23862, "ns": 0, "title": title,
        "pageprops": {"disambiguation": ""} if disambiguation else {},
    }
    if missing:
        item = {"ns": 0, "title": title, "missing": True}
    output = {"batchcomplete": True, "query": {"pages": [item]}}
    if redirect:
        output["query"]["redirects"] = [{
            "from": title, "to": "Python",
        }]
    return output


def item(day, views, *, project="en.wikipedia", article="Python_(programming_language)"):
    return {
        "project": project, "article": article, "granularity": "daily",
        "access": "all-access", "agent": "user",
        "timestamp": day.strftime("%Y%m%d") + "00",
        "views": views,
    }


def series(start=datetime(2026, 11, 4), count=14):
    return {"items": [item(start + timedelta(days=i), 100 + i) for i in range(count)]}


class Fetcher:
    def __init__(self, *, meta=None, view=None, first_http=200, second_http=200,
                 error=None):
        self.meta = metadata() if meta is None else meta
        self.view = series() if view is None else view
        self.first_http = first_http
        self.second_http = second_http
        self.error = error
        self.calls = []

    def __call__(self, url, params):
        self.calls.append((url, params))
        if self.error is not None:
            raise self.error
        if url.endswith("/w/api.php"):
            return self.first_http, self.meta
        return self.second_http, self.view


def run(tmp_path, fetcher, **kw):
    return wiki.discover_pageviews(
        article_title=TITLE, project=PROJECT, days=7, end_date=END,
        observed_at=NOW, execute=True, cache=BudgetCache(tmp_path),
        fetcher=fetcher, **kw,
    )


def test_pure_preview_never_opens_sqlite_or_contact_transport(monkeypatch):
    monkeypatch.setattr(wiki, "BudgetCache", lambda: (
        (_ for _ in ()).throw(AssertionError("Preview cannot open SQLite"))
    ))
    monkeypatch.setattr(wiki, "_http_get", lambda *_a: (
        (_ for _ in ()).throw(AssertionError("Preview cannot fetch"))
    ))
    report = wiki.discover_pageviews(
        article_title=TITLE, project=PROJECT,
        days=7, end_date=END, execute=False, observed_at=NOW,
    )
    assert report["status"] == "planned"
    assert report["requests_attempted"] == 0
    assert report["network_performed"] is False
    assert report["article_verification"] == "not_checked"
    assert report["window"] == {
        "days_each": 7,
        "previous_start_date": "2026-11-04",
        "previous_end_date": "2026-11-10",
        "start_date": "2026-11-11", "end_date": "2026-11-17",
    }
    assert report["comparison"]["current_window"]["views_sum"] is None
    assert report["country"] is None and report["language"] == "en"


@pytest.mark.parametrize("options", [
    {"article_title": "Python", "project": "evil.test"},
    {"article_title": "Python", "project": "en.wikipedia.org.evil.test"},
    {"article_title": "Python", "project": "EN.wikipedia.org"},
    {"article_title": "https://en.wikipedia.org/wiki/Python", "project": PROJECT},
    {"article_title": "Python\nSECRET", "project": PROJECT},
    {"article_title": "../Python", "project": PROJECT},
    {"article_title": "Python:abc", "project": PROJECT},
    {"article_title": "Python?x", "project": PROJECT},
    {"article_title": "en.wikipedia.org", "project": PROJECT, "days": 0},
    {"article_title": "Python", "project": PROJECT, "days": 31},
    {"article_title": "Python", "project": PROJECT, "days": True},
    {"article_title": "Python", "project": PROJECT, "end_date": "2026-11-19"},
    {"article_title": "Python", "project": PROJECT, "end_date": "0001-01-01", "days": 1},
    {"article_title": "Python", "project": PROJECT, "end_date": "0001-01-01", "days": 7},
    {"article_title": "Python", "project": PROJECT, "end_date": "2015-07-02", "days": 7},
])
def test_invalid_project_title_and_dates_refused_before_network(options):
    kwargs = {"article_title": TITLE, "project": PROJECT, "observed_at": NOW}
    kwargs.update(options)
    with pytest.raises(ValueError):
        wiki.discover_pageviews(**kwargs)


def test_earliest_complete_two_period_window_is_accepted():
    assert wiki._window(7, "2015-07-14", NOW) == {
        "days_each": 7,
        "previous_start_date": "2015-07-01",
        "previous_end_date": "2015-07-07",
        "start_date": "2015-07-08",
        "end_date": "2015-07-14",
    }
    with pytest.raises(ValueError, match="two complete, historical equal-length windows"):
        wiki._window(7, "2015-07-13", NOW)


def test_title_encoding_and_language_project_are_exact_not_inferred():
    project, language = wiki._project_name("sl.wikipedia.org")
    assert project == "sl.wikipedia.org" and language == "sl"
    title = wiki._title("Gospodarska_rast")
    assert title == "Gospodarska rast"
    meta, api = wiki._urls(
        project, title, wiki._window(7, END, NOW),
    )
    assert meta == "https://sl.wikipedia.org/w/api.php"
    assert api.startswith("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/sl.wikipedia.org")
    assert "/Gospodarska_rast/daily/20261104/20261117" in api


def test_known_canonical_article_two_equal_periods_and_provenance(tmp_path):
    fetcher = Fetcher()
    result = run(tmp_path, fetcher)
    assert result["status"] == "observed"
    assert result["article_verification"] == "verified_canonical_article"
    assert result["requests_attempted"] == 2
    assert result["network_performed"] is True
    assert result["source_rows_received"] == 14
    assert result["source_rows_rejected"] == 0
    assert result["missing_dates"] == []
    assert len(result["rows"]) == 14 and len(result["signals"]) == 14
    assert result["comparison"]["previous_window"] == {
        "start_date": "2026-11-04", "end_date": "2026-11-10",
        "days_expected": 7, "days_observed": 7, "views_sum": 721,
    }
    assert result["comparison"]["current_window"] == {
        "start_date": "2026-11-11", "end_date": "2026-11-17",
        "days_expected": 7, "days_observed": 7, "views_sum": 770,
    }
    assert result["comparison"]["change_percent_only_if_both_complete_and_prior_positive"] == 6.8
    assert all(s["source_id"] == "wikimedia_pageviews" for s in result["signals"])
    assert all(s["metric_type"] == "wikimedia_pageviews" for s in result["signals"])
    assert all(s["metric_unit"] == "pageviews" for s in result["signals"])
    assert all(s["period"]["granularity"] == "daily" for s in result["signals"])
    assert all(s["country"] is None and s["language"] == "en" for s in result["signals"])
    assert all(s["provenance"]["method"] == "official_api" for s in result["signals"])
    assert all(not s["provenance"]["is_observed_search_query"] for s in result["signals"])
    assert result["country_of_readers_unknown"] is True
    assert result["search_volume_verified"] is False
    assert result["unique_visitors_verified"] is False
    assert result["paid_services_used"] is False
    metadata_url, params = fetcher.calls[0]
    assert metadata_url == "https://en.wikipedia.org/w/api.php"
    assert params == {
        "action": "query", "format": "json", "formatversion": "2",
        "redirects": "1", "prop": "pageprops",
        "titles": TITLE, "maxlag": "5",
    }
    pv_url, pv_params = fetcher.calls[1]
    assert pv_params is None and pv_url.endswith(
        "/all-access/user/Python_%28programming_language%29/daily/20261104/20261117"
    )

    cached = run(tmp_path, fetcher)
    assert cached["status"] == "observed"
    assert cached["cache_hit"] is True
    assert cached["requests_attempted"] == 0
    assert cached["network_performed"] is False
    assert len(fetcher.calls) == 2
    assert cached["comparison"] == result["comparison"]


@pytest.mark.parametrize(("meta", "expected"), [
    (metadata(redirect=True), "redirect_requires_canonical_title"),
    (metadata(disambiguation=True), "disambiguation_requires_article"),
    (metadata(missing=True), "article_not_found"),
    (metadata(title="Python"), "canonical_title_mismatch"),
    ({"query": {"pages": [{"ns": 1, "pageid": 1, "title": TITLE}]}},
     "invalid_article_metadata"),
    ({"query": {"pages": []}}, "invalid_article_metadata"),
    ({"error": "upstream SECRET"}, "invalid_article_metadata"),
])
def test_redirect_disambiguation_missing_canonical_and_bad_metadata_fail_closed(
    tmp_path, meta, expected,
):
    client = Fetcher(meta=meta)
    result = run(tmp_path, client)
    assert result["status"] == expected
    assert result["article_verification"] == expected
    assert result["requests_attempted"] == 1
    assert len(client.calls) == 1
    assert result["signals"] == []
    assert "SECRET" not in json.dumps(result)


def test_daily_gaps_are_unknown_not_zero_and_growth_is_withheld(tmp_path):
    start = datetime(2026, 11, 4)
    client = Fetcher(view={
        "items": [
            item(start + timedelta(days=i), 0 if i == 4 else 100 + i)
            for i in range(14) if i not in (8, 13)
        ]
    })
    report = run(tmp_path, client)
    assert report["status"] == "observed_partial"
    assert report["missing_dates"] == ["2026-11-12", "2026-11-17"]
    assert report["comparison"]["previous_window"]["views_sum"] == 617
    assert report["comparison"]["current_window"]["views_sum"] is None
    assert report["comparison"]["change_percent_only_if_both_complete_and_prior_positive"] is None
    assert any(item["views"] == 0 for item in report["rows"])
    assert len(report["signals"]) == 12


def test_404_is_unknown_zero_or_not_loaded_not_zero(tmp_path):
    fetcher = Fetcher(second_http=404)
    out = run(tmp_path, fetcher)
    assert out["status"] == "zero_or_not_loaded_unknown"
    assert out["comparison"]["current_window"]["views_sum"] is None
    assert len(out["signals"]) == 0


def test_successful_empty_series_is_no_data_not_verified_zero(tmp_path):
    client = Fetcher(view={"items": []})
    first = run(tmp_path, client)
    assert first["status"] == "no_data"
    assert first["comparison"]["previous_window"]["views_sum"] is None
    assert first["comparison"]["current_window"]["views_sum"] is None
    repeated = run(tmp_path, client)
    assert repeated["cache_hit"] and repeated["requests_attempted"] == 0
    assert repeated["status"] == "no_data"


@pytest.mark.parametrize("malformed", [
    {"not_items": []},
    {"items": "private"},
    {"items": [item(datetime(2026, 11, 4), 1, project="it.wikipedia")]},
    {"items": [item(datetime(2026, 11, 4), 1, article="Other")]},
    {"items": [item(datetime(2026, 11, 4), 1)] * 100},
])
def test_invalid_source_payload_and_cross_wiki_contamination_refused(tmp_path, malformed):
    client = Fetcher(view=malformed)
    report = run(tmp_path, client)
    assert report["status"] in {"invalid_source_shape", "invalid_source_scope"}
    assert report["signals"] == []
    assert report["rows"] == []


def test_partial_source_rejections_and_duplicates_not_full_coverage(tmp_path):
    start = datetime(2026, 11, 4)
    items = [
        item(start + timedelta(days=i), 200 + i)
        for i in range(14)
    ]
    items[3]["views"] = 2**53 + 1
    items[4]["timestamp"] = "unexpected"
    items[5] = items[6].copy()
    client = Fetcher(view={"items": items})
    out = run(tmp_path, client)
    assert out["status"] in {"invalid_source_scope", "observed_partial"}
    assert out["comparison"]["change_percent_only_if_both_complete_and_prior_positive"] is None


@pytest.mark.parametrize(("first", "second", "expected"), [
    (429, 200, "provider_rate_limited"),
    (503, 200, "provider_rate_limited"),
    (401, 200, "metadata_unavailable"),
    (200, 404, "zero_or_not_loaded_unknown"),
    (200, 429, "provider_rate_limited"),
    (200, 500, "source_unavailable"),
])
def test_http_failures_and_durable_cooldown(tmp_path, first, second, expected):
    client = Fetcher(first_http=first, second_http=second)
    result = run(tmp_path, client)
    assert result["status"] == expected
    if first in (429, 503) or second == 429:
        fresh = run(tmp_path, Fetcher())
        assert fresh["status"] == "provider_cooldown"
        assert fresh["requests_attempted"] == 0
        assert fresh["network_performed"] is False


def test_exceptions_with_sensitive_data_never_echo(tmp_path):
    client = Fetcher(error=RuntimeError("Bearer PRIVATE_SECRET https://host/key=PRIVATE"))
    report = run(tmp_path, client)
    assert report["status"] == "source_unavailable"
    assert "PRIVATE" not in repr(report)
    assert report["requests_attempted"] == 1


def test_atomic_daily_budget_two_requests_and_no_partial_reservation(tmp_path):
    store = BudgetCache(tmp_path)
    store.reserve_many(wiki.BUDGET_ID, wiki.UTC_DAILY_SOURCE_CAP, 2)
    client = Fetcher()
    out = run(tmp_path, client)
    assert out["requests_attempted"] == 2
    other = Fetcher()
    blocked = wiki.discover_pageviews(
        article_title="Other real article", project=PROJECT,
        days=7, end_date=END, execute=True, observed_at=NOW,
        cache=BudgetCache(tmp_path), fetcher=other,
    )
    assert blocked["status"] == "local_daily_budget_exhausted"
    assert blocked["requests_attempted"] == 0 and other.calls == []
    with pytest.raises(DailyBudgetExceeded):
        store.reserve_many(wiki.BUDGET_ID, wiki.UTC_DAILY_SOURCE_CAP, 1)


def test_one_leftover_allowance_never_launches_first_request(tmp_path):
    store = BudgetCache(tmp_path)
    store.reserve_many(wiki.BUDGET_ID, wiki.UTC_DAILY_SOURCE_CAP, 3)
    client = Fetcher()
    result = run(tmp_path, client)
    assert result["status"] == "local_daily_budget_exhausted"
    assert client.calls == []
    from datetime import datetime as d, timezone as tz
    today = d.now(tz.utc).date().isoformat()
    with store._connect() as conn:
        assert conn.execute(
            "SELECT used FROM budget WHERE source=? and day=?",
            (wiki.BUDGET_ID, today),
        ).fetchone()[0] == 3


def test_bad_local_sqlite_fails_closed(tmp_path):
    class FailCache:
        def cached(self, _key):
            raise OSError("AUTHORIZATION_SECRET_PATH")
    client = Fetcher()
    report = wiki.discover_pageviews(
        article_title=TITLE, project=PROJECT, days=7,
        end_date=END, execute=True, cache=FailCache(),
        observed_at=NOW, fetcher=client,
    )
    assert report["status"] == "local_budget_unavailable"
    assert report["requests_attempted"] == 0
    assert client.calls == []
    assert "SECRET" not in repr(report)


def test_corrupted_cache_records_are_not_echoed_and_cannot_bypass_quota(tmp_path):
    client = Fetcher()
    first = run(tmp_path, client)
    assert first["status"] == "observed"
    store = BudgetCache(tmp_path)
    window = wiki._window(7, END, NOW)
    key = wiki._cache_key(project=PROJECT, title=TITLE, window=window)
    prior = store.cached(key)
    assert isinstance(prior, dict)
    store.save(
        key, {**prior, "private_token": "SECRET_CANNOT_ESCAPE"},
        wiki.CACHE_TTL_SECONDS,
    )
    cached = run(tmp_path, client)
    assert cached["cache_hit"]
    assert "SECRET_CANNOT_ESCAPE" not in json.dumps(cached)
    store.save(
        key, {"article_title": "other", "rows": [{
            "date": "2026-11-11", "views": 900, "secret": "DONT_ECHO",
        }]},
        wiki.CACHE_TTL_SECONDS,
    )
    store.reserve_many(wiki.BUDGET_ID, wiki.UTC_DAILY_SOURCE_CAP, 2)
    blocked = run(tmp_path, Fetcher())
    assert blocked["status"] == "local_daily_budget_exhausted"
    assert blocked["requests_attempted"] == 0
    assert "DONT_ECHO" not in repr(blocked)


def test_cached_partial_rows_must_account_for_every_source_row(tmp_path):
    client = Fetcher(view=series(count=13))
    first = run(tmp_path, client)
    assert first["status"] == "observed_partial"
    assert first["source_rows_received"] == 13
    assert run(tmp_path, client)["cache_hit"] is True

    store = BudgetCache(tmp_path)
    window = wiki._window(7, END, NOW)
    key = wiki._cache_key(project=PROJECT, title=TITLE, window=window)
    prior = store.cached(key)
    assert isinstance(prior, dict)
    store.save(key, {**prior, "source_rows_received": 14}, wiki.CACHE_TTL_SECONDS)

    result = run(tmp_path, client)
    assert result["cache_hit"] is False
    assert result["status"] == "observed_partial"
    assert result["source_rows_received"] == 13
    assert len(client.calls) == 4


def test_http_client_identifying_header_fixed_hosts_no_redirects_no_proxies(monkeypatch):
    import requests

    class FakeStream:
        def __init__(self, body):
            self.raw = BytesIO(body)
        def read(self, size, decode_content=False):
            assert size == wiki.MAX_RESPONSE_BYTES + 1
            return self.raw.read(size)

    class FakeResponse:
        status_code = 200
        headers = {"Content-Type": "application/json"}
        raw = FakeStream(b'{"items":[]}')
        def __enter__(self):
            return self
        def __exit__(self, *_a):
            return None

    instances = []

    class FakeSession:
        trust_env = True
        def __init__(self):
            instances.append(self)
        def get(self, url, *, params, timeout, stream, allow_redirects, headers):
            assert self.trust_env is False
            assert url == (
                "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
                "en.wikipedia.org/all-access/user/Python_%28programming_language%29"
                "/daily/20261104/20261117"
            )
            assert params is None and timeout == (5, 12)
            assert stream and not allow_redirects
            assert "https://github.com/AKzar1el/mcp-trendpulse" in headers["User-Agent"]
            return FakeResponse()
        def close(self):
            self.closed = True

    monkeypatch.setattr(requests, "Session", FakeSession)
    endpoint = wiki._urls(PROJECT, TITLE, wiki._window(7, END, NOW))[1]
    status, payload = wiki._http_get(endpoint, None)
    assert status == 200 and payload == {"items": []}
    assert instances[-1].closed is True
    FakeResponse.raw = FakeStream(b"z" * (wiki.MAX_RESPONSE_BYTES + 1))
    with pytest.raises(wiki.ResponseTooLarge):
        wiki._http_get(endpoint, None)
    assert instances[-1].closed is True
    with pytest.raises(ValueError):
        wiki._http_get("https://wikimedia.org.evil.test/api/rest_v1/x", None)


def test_cli_preview_is_offline_and_invalid_title_is_an_error():
    runner = CliRunner()
    first = runner.invoke(cli, [
        "intelligence", "wikimedia-pageviews",
        "--article", TITLE, "--project", PROJECT, "--days", "7",
        "--end-date", END, "--format", "json",
    ])
    assert first.exit_code == 0, first.output
    parsed = json.loads(first.output)
    assert parsed["status"] == "planned"
    assert parsed["requests_attempted"] == 0
    bad = runner.invoke(cli, [
        "intelligence", "wikimedia-pageviews",
        "--article", "https://en.wikipedia.org/wiki/Python",
        "--format", "json",
    ])
    assert bad.exit_code != 0
    assert "invalid" in bad.output.lower()
