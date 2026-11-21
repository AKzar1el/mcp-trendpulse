"""M05 Bing Webmaster REST/JSON global keyword research — fully offline tests.

Live acceptance uses the user's existing account key, but these tests inject
an in-memory transport. They do not contact Bing or read user credentials.
"""
from __future__ import annotations

import json
from io import BytesIO
from datetime import datetime, timezone

import pytest
from click.testing import CliRunner

from mcp_trendpulse import intelligence_bing_keywords as bing
from mcp_trendpulse.cli import cli
from mcp_trendpulse.intelligence_core import BudgetCache

NOW = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)
KEY = "TEST_NON_SECRET_API_KEY_DO_NOT_LOG"
SOURCE = "bing_webmaster_keyword_research"


def ticks(year=2026, month=11, day=13, *, offset=""):
    epoch = int(datetime(year, month, day, tzinfo=timezone.utc).timestamp() * 1000)
    return f"/Date({epoch}{offset})/"


def stat(query="crochet patterns", day=13, exact=100, broad=220):
    return {"__type": "KeywordStats:#Microsoft.Bing.Webmaster.Api",
            "Query": query, "Date": ticks(day=day),
            "Impressions": exact, "BroadImpressions": broad}


def related(query="crochet pattern for beginners", exact=45, broad=88):
    return {"Query": query, "Impressions": exact, "BroadImpressions": broad,
            "__type": "Keyword:#Microsoft.Bing.Webmaster.Api"}


class Fetcher:
    def __init__(self, status=200, data=None, error=None):
        self.status = status
        self.data = data if data is not None else {"d": [stat()]}
        self.error = error
        self.calls: list[tuple[str, dict[str, str]]] = []

    def __call__(self, endpoint, params):
        self.calls.append((endpoint, dict(params)))
        if self.error is not None:
            raise self.error
        return self.status, self.data


def run(cache_dir, fetcher, *, kind="stats", execute=True, **options):
    return bing.discover_bing_keyword(
        query="crochet patterns", country="US", language="en-US",
        kind=kind, execute=execute,
        cache=BudgetCache(cache_dir), api_key=KEY, fetcher=fetcher,
        observed_at=NOW, **options,
    )


def test_preview_never_opens_budget_reads_key_or_uses_network(monkeypatch):
    monkeypatch.setattr(bing, "BudgetCache", lambda *_a, **_k: (
        (_ for _ in ()).throw(AssertionError("Preview must not open sqlite"))
    ))
    monkeypatch.setattr(bing, "_fetch_json", lambda *_a, **_k: (
        (_ for _ in ()).throw(AssertionError("Preview must not contact Bing"))
    ))
    monkeypatch.setattr(bing, "resolved_environment", lambda *_a, **_k: (
        (_ for _ in ()).throw(AssertionError("Preview must not read secrets"))
    ))
    out = bing.discover_bing_keyword(
        query="crochet patterns", country="US", language="en-US",
        kind="stats", execute=False,
    )
    assert out["status"] == "planned"
    assert out["requests_attempted"] == 0
    assert out["network_performed"] is False
    assert out["site_property_required_for_keyword_query"] is False
    assert out["site_url_parameter_sent"] is False
    assert out["signals"] == [] and out["records"] == []
    assert out["source_url"].endswith("/GetKeywordStats")
    assert "apikey" not in out["source_url"].lower()


@pytest.mark.parametrize("kwargs", [
    {"query": "https://sample.test/?secret=123", "country": "US", "language": "en-US"},
    {"query": "ai\nagents", "country": "US", "language": "en-US"},
    {"query": "a", "country": "US", "language": "en-US"},
    {"query": "something", "country": "USA", "language": "en-US"},
    {"query": "something", "country": "US", "language": "../../SI"},
    {"query": "something", "country": "US", "language": "en-US", "kind": "unknown"},
    {"query": "something", "country": "US", "language": "en-US", "kind": "stats",
     "start_date": "2026-10-20"},
    {"query": "something", "country": "US", "language": "en-US", "kind": "related",
     "start_date": "2026-11-22", "end_date": "2026-11-24"},
    {"query": "something", "country": "US", "language": "en-US", "kind": "related",
     "start_date": "2026-04-01", "end_date": "2026-11-20"},
    {"query": "something", "country": "US", "language": "en-US", "limit": 0},
    {"query": "something", "country": "US", "language": "en-US", "limit": 21},
])
def test_invalid_scope_and_unbounded_inputs_refused_before_network(kwargs):
    with pytest.raises(ValueError):
        bing.discover_bing_keyword(**kwargs, execute=False)


def test_missing_credentials_never_consumes_quota(tmp_path, monkeypatch):
    monkeypatch.setattr(bing, "resolved_environment", lambda *_a, **_k: {})
    client = Fetcher()
    report = bing.discover_bing_keyword(
        query="crochet patterns", country="US", language="en-US",
        execute=True, cache=BudgetCache(tmp_path), fetcher=client,
    )
    assert report["status"] == "no_bing_credentials"
    assert report["requests_attempted"] == 0
    assert client.calls == []
    assert report["records"] == []


def test_key_rest_json_scope_weekly_source_signals_and_cache(tmp_path):
    client = Fetcher(data={"d": [
        stat(day=7, exact=77, broad=150),
        stat(day=14, exact=0, broad=10),
    ]})
    result = run(tmp_path, client, limit=20)
    assert result["status"] == "observed"
    assert result["source"] == SOURCE
    assert result["kind"] == "stats"
    assert result["country"] == "US" and result["language"] == "en-US"
    assert result["market_scope"] == "bing_search_keyword_research_not_site_performance"
    assert result["requests_attempted"] == 1
    assert result["source_rows_received"] == 2
    assert result["source_rows_omitted"] == 0
    assert result["records"][0]["exact_impressions"] == 77
    assert result["records"][1]["exact_impressions"] == 0
    assert result["records"][1]["broad_impressions"] == 10
    assert result["records"][1]["date"] == "2026-11-14"
    assert len(result["signals"]) == 4
    assert {s["provenance"]["sampling_basis"] for s in result["signals"]} == {
        "bing_weekly_exact_query_impressions",
        "bing_weekly_broad_query_impressions",
    }
    assert all(s["source_id"] == SOURCE for s in result["signals"])
    assert all(s["metric_type"] == "bing_keyword_impressions" for s in result["signals"])
    assert all(s["period"]["granularity"] == "weekly" for s in result["signals"])
    assert all(s["language"] == "en-US" and s["country"] == "US"
               for s in result["signals"])
    assert all(s["provenance"]["method"] == "official_api" for s in result["signals"])
    assert all(not s["provenance"]["is_observed_search_query"] for s in result["signals"])
    assert all("apikey" not in s["source_url"].lower() for s in result["signals"])
    assert result["google_search_volume_verified"] is False
    assert result["paid_services_used"] is False
    assert result["website_impressions_included"] is False

    assert len(client.calls) == 1
    endpoint, params = client.calls[0]
    assert endpoint == "https://ssl.bing.com/webmaster/api.svc/json/GetKeywordStats"
    assert params == {"apikey": KEY, "q": "crochet patterns",
                      "country": "us", "language": "en-US"}
    assert "siteUrl" not in params and "siteUrl" not in endpoint
    assert KEY not in json.dumps(result)
    cached = run(tmp_path, client, limit=20)
    assert cached["status"] == "observed"
    assert cached["cache_hit"] is True
    assert cached["requests_attempted"] == 0
    assert cached["network_performed"] is False
    assert len(client.calls) == 1
    assert cached["records"] == result["records"]


def test_related_window_country_language_no_site_url_and_empty_is_unknown(tmp_path):
    client = Fetcher(data={"d": [related(), related("crochet blanket", 0, 4)]})
    result = run(tmp_path, client, kind="related",
                 start_date="2026-10-25", end_date="2026-11-18")
    assert result["status"] == "observed"
    assert result["period"] == {"start_date": "2026-10-25",
                                "end_date": "2026-11-18",
                                "granularity": "selected_period_aggregate"}
    assert len(result["records"]) == 2
    assert result["records"][0]["query"] == "crochet pattern for beginners"
    assert result["records"][1]["exact_impressions"] == 0
    assert result["signals"] == []  # Aggregates lack a documented weekly bucket.
    endpoint, params = client.calls[0]
    assert endpoint.endswith("/GetRelatedKeywords")
    assert params == {"apikey": KEY, "q": "crochet patterns", "country": "us",
                      "language": "en-US", "startDate": "2026-10-25",
                      "endDate": "2026-11-18"}
    empty = run(tmp_path / "empty", Fetcher(data={"d": []}), kind="related",
                start_date="2026-10-25", end_date="2026-11-18")
    assert empty["status"] == "no_data"
    assert empty["records"] == []
    assert empty["source_rows_received"] == 0


def test_stats_are_weekly_with_ms_timezone_not_host_timezone(tmp_path):
    stamp = int(datetime(2026, 11, 13, 23, 30, tzinfo=timezone.utc).timestamp() * 1000)
    client = Fetcher(data={"d": [{
        "Query": "crochet patterns",
        "Date": f"/Date({stamp}+0200)/",
        "Impressions": 3,
        "BroadImpressions": 4,
    }]})
    result = run(tmp_path, client)
    assert result["records"][0]["date"] == "2026-11-14"
    assert result["signals"][0]["period"]["start_date"] == "2026-11-14"


def test_partial_provenance_and_rows_limit_not_false_clean_observation(tmp_path):
    client = Fetcher(data={"d": [
        stat(day=3, exact=7),
        stat(day=8, exact=8),
        stat(day=11, exact=10),
        stat(day=11, exact=12),
        stat(day=17, exact=-1),
        {"Query": "crochet patterns", "Impressions": 4},
    ]})
    result = run(tmp_path, client, limit=2)
    assert result["status"] == "observed_partial"
    assert result["source_rows_received"] == 6
    assert result["source_rows_omitted"] == 4
    assert result["rows_truncated"] is True
    assert len(result["records"]) == 2
    assert [r["date"] for r in result["records"]] == ["2026-11-08", "2026-11-11"]


@pytest.mark.parametrize("payload", [
    {"d": {"Error": "super_secret"}},
    {"d": [{"Query": "crochet patterns", "Date": "INVALID", "Impressions": 1,
             "BroadImpressions": 1}]},
    {"d": [{"Query": "OTHER", "Date": ticks(), "Impressions": 50,
             "BroadImpressions": 100}]},
    {"d": ["untrusted_secret_response"]},
    {"not_d": [stat()]},
])
def test_invalid_source_is_not_accepted_or_echoed(tmp_path, payload):
    result = run(tmp_path, Fetcher(data=payload))
    assert result["status"] == "invalid_source_shape"
    assert result["records"] == []
    assert result["signals"] == []
    assert "super_secret" not in json.dumps(result)
    assert "untrusted_secret_response" not in json.dumps(result)


def test_overprecise_impression_count_is_not_rounded_into_fake_exact_measurement(tmp_path):
    client = Fetcher(data={"d": [stat(exact=(1 << 53) + 1, broad=200)]})
    result = run(tmp_path, client)
    assert result["status"] == "invalid_source_shape"
    assert result["signals"] == [] and result["records"] == []


@pytest.mark.parametrize("http,expected", [
    (401, "authentication_required"),
    (403, "authentication_required"),
    (404, "provider_unavailable"),
    (429, "provider_rate_limited"),
    (503, "provider_rate_limited"),
    (500, "provider_unavailable"),
    (302, "provider_unavailable"),
])
def test_http_statuses_are_safe_and_provider_rate_limit_cooldown(tmp_path, http, expected):
    client = Fetcher(status=http, data={"error": "TOKEN_DO_NOT_LOG"})
    result = run(tmp_path, client)
    assert result["status"] == expected
    assert len(client.calls) == 1
    assert "TOKEN_DO_NOT_LOG" not in json.dumps(result)
    if http in {429, 503}:
        repeated = run(tmp_path, client, kind="related")
        assert repeated["status"] == "provider_cooldown"
        assert repeated["requests_attempted"] == 0
        assert len(client.calls) == 1


def test_secret_bearing_exception_is_never_printed_or_cached(tmp_path):
    client = Fetcher(error=RuntimeError("Authorization: TOP_SECRET https://bing.invalid/key=SECRET"))
    result = run(tmp_path, client)
    assert result["status"] == "provider_unavailable"
    assert result["requests_attempted"] == 1
    assert "SECRET" not in json.dumps(result)
    assert "Authorization" not in json.dumps(result)


def test_real_transport_refuses_redirects_proxies_and_oversized_response(monkeypatch):
    import requests

    sessions = []

    class BoundedStream:
        def __init__(self, body):
            self.payload = BytesIO(body)
        def read(self, size, *, decode_content=False):
            assert size == bing.MAX_RESPONSE_BYTES + 1
            return self.payload.read(size)

    class Response:
        status_code = 200
        headers = {"Content-Type": "application/json; charset=utf-8"}
        raw = BoundedStream(b'{"d":[]}')
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return None

    class Session:
        trust_env = True
        def __init__(self):
            sessions.append(self)
        def get(self, endpoint, *, params, timeout, stream, allow_redirects, headers):
            assert self.trust_env is False
            assert endpoint == bing.ENDPOINTS["stats"]
            assert params == {"apikey": KEY, "q": "crochet patterns",
                              "country": "us", "language": "en-US"}
            assert timeout == (5, 12) and stream and not allow_redirects
            assert headers["Accept"] == "application/json"
            return Response()
        def close(self):
            self.closed = True

    monkeypatch.setattr(requests, "Session", Session)
    status, payload = bing._fetch_json(
        bing.ENDPOINTS["stats"],
        {"apikey": KEY, "q": "crochet patterns",
         "country": "us", "language": "en-US"},
    )
    assert status == 200
    assert payload == {"d": []}
    assert len(sessions) == 1 and sessions[0].closed is True

    Response.raw = BoundedStream(b"X" * (bing.MAX_RESPONSE_BYTES + 1))
    with pytest.raises(bing.ResponseTooLarge):
        bing._fetch_json(
            bing.ENDPOINTS["stats"],
            {"apikey": KEY, "q": "crochet patterns",
             "country": "us", "language": "en-US"},
        )
    assert sessions[-1].closed is True


def test_one_shared_daily_cap_for_stats_and_related_without_any_bypass(tmp_path):
    client = Fetcher(data={"d": []})
    for term in ("crochet patterns", "knitting basics", "yarn charts"):
        response = bing.discover_bing_keyword(
            query=term, country="US", language="en-US", kind="stats",
            execute=True, api_key=KEY, cache=BudgetCache(tmp_path),
            observed_at=NOW, fetcher=client,
        )
        assert response["status"] == "no_data"
    exhausted = run(tmp_path, client, kind="related")
    assert exhausted["status"] == "local_daily_budget_exhausted"
    assert exhausted["requests_attempted"] == 0
    assert len(client.calls) == bing.UTC_DAILY_BING_CAP == 3


def test_cache_is_bound_to_credentials_and_unknown_metadata_never_leaks(tmp_path):
    client = Fetcher(data={"d": [stat()]})
    result = run(tmp_path, client)
    assert result["status"] == "observed"
    store = BudgetCache(tmp_path)
    key = bing._cache_key(
        kind="stats", query="crochet patterns", country="US", language="en-US",
        start_date=None, end_date=None, limit=20, api_key=KEY,
    )
    prior = store.cached(key)
    assert isinstance(prior, dict)
    assert KEY not in json.dumps(prior)
    store.save(key, {**prior, "private_password": "TOKEN_CANNOT_ESCAPE"}, bing.CACHE_TTL_SECONDS)
    cached = run(tmp_path, client)
    assert cached["cache_hit"] is True
    assert "TOKEN_CANNOT_ESCAPE" not in json.dumps(cached)
    different_key = bing.discover_bing_keyword(
        query="crochet patterns", country="US", language="en-US",
        kind="stats", execute=True, api_key="ANOTHER_TEST_KEY",
        cache=BudgetCache(tmp_path), observed_at=NOW,
        fetcher=Fetcher(data={"d": []}),
    )
    assert different_key["cache_hit"] is False
    assert different_key["status"] == "no_data"


def test_invalid_cached_structure_fails_closed_and_respects_existing_budget(tmp_path):
    client = Fetcher(data={"d": [stat()]})
    first = run(tmp_path, client)
    assert first["status"] == "observed"
    store = BudgetCache(tmp_path)
    key = bing._cache_key(
        kind="stats", query="crochet patterns", country="US", language="en-US",
        start_date=None, end_date=None, limit=20, api_key=KEY,
    )
    store.save(key, {"query": "OTHER", "records": [{"token": "PRIVATE_CACHED_MATERIAL"}]},
               bing.CACHE_TTL_SECONDS)
    store.reserve(bing.BING_BUDGET_ID, bing.UTC_DAILY_BING_CAP)
    store.reserve(bing.BING_BUDGET_ID, bing.UTC_DAILY_BING_CAP)
    result = run(tmp_path, client)
    assert result["status"] == "local_daily_budget_exhausted"
    assert result["requests_attempted"] == 0
    assert "PRIVATE_CACHED_MATERIAL" not in json.dumps(result)
    assert len(client.calls) == 1


def test_store_failure_fails_closed(tmp_path):
    class BrokenStore:
        def cached(self, *_args):
            raise OSError("SECRET path")
    client = Fetcher()
    out = bing.discover_bing_keyword(
        query="crochet patterns", country="US", language="en-US",
        execute=True, api_key=KEY, cache=BrokenStore(),
        observed_at=NOW, fetcher=client,
    )
    assert out["status"] == "local_budget_unavailable"
    assert out["requests_attempted"] == 0
    assert client.calls == []
    assert "SECRET" not in json.dumps(out)


def test_cli_preview_offline_and_rejects_invalid_scope(monkeypatch):
    monkeypatch.setattr(bing, "resolved_environment", lambda *_a, **_k: (
        (_ for _ in ()).throw(AssertionError("Preview should never load credentials"))
    ))
    response = CliRunner().invoke(cli, [
        "intelligence", "bing-keywords", "--term", "crochet patterns",
        "--country", "US", "--language", "en-US", "--kind", "stats",
        "--format", "json",
    ])
    assert response.exit_code == 0, response.output
    out = json.loads(response.output)
    assert out["status"] == "planned"
    assert out["requests_attempted"] == 0
    assert out["source_url"].endswith("GetKeywordStats")
    assert "apikey" not in response.output.lower()
    bad = CliRunner().invoke(cli, [
        "intelligence", "bing-keywords", "--term", "crochet patterns",
        "--country", "usa", "--language", "en-US", "--format", "json",
    ])
    assert bad.exit_code != 0
    assert "invalid" in bad.output.lower()
