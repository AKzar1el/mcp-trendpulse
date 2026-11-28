"""Offline transport and durable quota/cache tests for V4.02."""
from datetime import datetime, timezone
from email.message import Message
import json
from urllib.error import HTTPError, URLError

import pytest
from filelock import FileLock

from mcp_trendpulse import news_intelligence_collect as collect
from mcp_trendpulse.intelligence_core import BudgetCache

NOW = datetime(2026, 11, 28, 12, tzinfo=timezone.utc)
AS_OF = NOW.isoformat()


class Response:
    status = 200

    def __init__(self, payload, mime="application/json"):
        self.payload = payload
        self.headers = Message()
        self.headers["Content-Type"] = mime

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self.payload[:limit]


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(collect, "_now", lambda: NOW)
    store = BudgetCache(tmp_path)
    calls = []

    def install(response):
        class Opener:
            def open(self, request, timeout):
                calls.append((request, timeout))
                if isinstance(response, Exception):
                    raise response
                return response

        monkeypatch.setattr(collect, "build_opener", lambda *args: Opener())

    return store, calls, install


def gdelt_payload():
    return json.dumps({"articles": [{
        "url": "https://example.org/story", "title": "Energy research",
        "seendate": "20261128T110000Z", "domain": "example.org",
        "body": "NEVER_STORE_THIS_BODY", "language": "English",
    }, {"url": "http://example.org/unsupported", "title": "Unsafe"}]}).encode()


def run_articles(store, **kwargs):
    return collect.collect_news("gdelt_articles", phrase="energy research",
                                as_of=AS_OF, cache=store, execute=True, **kwargs)


def test_plan_never_constructs_cache_or_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("Must stay offline")
    monkeypatch.setattr(collect, "BudgetCache", denied)
    monkeypatch.setattr(collect, "build_opener", denied)
    report = collect.collect_news("gdelt_articles", phrase="energy research", as_of=AS_OF)
    assert report["status"] == "planned" and not report["network_performed"]
    assert report["provider_requests"] == 0 and report["evidence"] is None


def test_live_projection_and_cache_replay(setup):
    store, calls, install = setup
    install(Response(gdelt_payload()))
    first = run_articles(store)
    assert first["status"] == "partial" and first["http_status"] == 200
    assert first["provider_requests"] == 1 and first["evidence"]["invalid_count"] == 1
    assert first["evidence"]["rejected_row_reasons"] == ["unsafe_or_unsupported_url"]
    article = first["evidence"]["articles"][0]
    assert article["capture_mode"] == "live" and article["published_at"] is None
    assert "NEVER_STORE_THIS_BODY" not in str(first)
    assert "NEVER_STORE_THIS_BODY" not in store.db.read_bytes().decode("utf-8", errors="ignore")
    request, timeout = calls[0]
    assert request.full_url.startswith("https://api.gdeltproject.org/api/v2/doc/doc?")
    assert request.method == "GET" and timeout == 12
    assert request.get_header("Authorization") is None
    again = run_articles(store)
    assert again["cache_hit"] and not again["network_performed"]
    assert again["evidence"] == first["evidence"] and again["captured_at"] == first["captured_at"]
    assert len(calls) == 1
    blocked = collect.collect_news("gdelt_timeline", phrase="energy research",
                                   as_of=AS_OF, execute=True, cache=store)
    assert blocked["reason"] == "provider_cooldown" and len(calls) == 1


def test_timeline_uses_same_budget_and_preserves_denominator(setup):
    store, calls, install = setup
    install(Response(b'{"timeline":[{"series":"Article Count","data":'
                     b'[{"date":"20261128T110000Z","value":3,"norm":40}]}]}'))
    result = collect.collect_news("gdelt_timeline", phrase="energy research",
                                  as_of=AS_OF, execute=True, cache=store)
    assert result["status"] == "observed"
    assert result["evidence"]["points"][0]["matched"] == 3
    assert result["evidence"]["points"][0]["monitored"] == 40
    assert "timelinesmooth=1" in calls[0][0].full_url


def test_nasa_independent_source(setup):
    store, calls, install = setup
    install(Response(b'<rss version="2.0"><channel><title>NASA</title>'
                     b'<link>https://www.nasa.gov/</link><item><title>Space</title>'
                     b'<link>https://www.nasa.gov/story</link>'
                     b'<pubDate>Fri, 27 Nov 2026 12:00:00 +0000</pubDate>'
                     b'<description>PRIVATE_BODY</description></item></channel></rss>',
                     "application/rss+xml"))
    result = collect.collect_news("nasa_rss", execute=True, cache=store)
    assert result["status"] == "observed" and len(calls) == 1
    assert result["evidence"]["articles"][0]["published_at"]["basis"] == "feed"
    assert result["scope"]["query"] is None and "PRIVATE_BODY" not in str(result)


@pytest.mark.parametrize("response", [
    Response(b"<html>error</html>", "text/html"),
    Response(b'{"articles":[],"error":"provider error"}'),
    Response(b" " * (collect.MAX_BYTES + 1)),
    URLError("secret transport detail"),
], ids=["content-type", "false-empty", "size-cap", "transport"])
def test_failures_are_not_measurements(setup, response):
    store, calls, install = setup
    install(response)
    result = run_articles(store)
    assert result["status"] in ("invalid", "unavailable")
    assert result["provider_requests"] == 1 and len(calls) == 1
    assert result["evidence"] is None or result["evidence"]["source_count"] is None
    assert "secret transport detail" not in str(result)


def test_rate_limit_and_retry_after_are_persisted(setup):
    store, calls, install = setup
    headers = Message()
    headers["Retry-After"] = "3600"
    install(HTTPError("https://api.gdeltproject.org/", 429, "limited", headers, None))
    result = run_articles(store)
    assert result["reason"] == "provider_rate_limited" and result["http_status"] == 429
    assert not result["retry_automatically"]
    assert store.blocked("gdelt_doc")
    with store._connect() as conn:
        remaining = conn.execute("SELECT until FROM cooldown WHERE source='gdelt_doc'").fetchone()[0]
    import time
    assert remaining - time.time() > 3500
    assert run_articles(store)["reason"] == "provider_cooldown" and len(calls) == 1


def test_budget_and_lock_refuse_without_io(setup):
    store, calls, install = setup
    install(Response(gdelt_payload()))
    root = store.db.parent / ".request_locks"
    root.mkdir()
    with FileLock(str(root / "news-v4-gdelt_doc.lock")):
        assert run_articles(store)["reason"] == "provider_local_concurrency_limit"
    for _ in range(6):
        store.reserve("gdelt_doc", 6)
    assert run_articles(store)["reason"] == "local_daily_budget_exhausted"
    assert not calls


def test_corrupt_cache_fails_closed(setup, monkeypatch):
    store, calls, install = setup
    install(Response(gdelt_payload()))
    monkeypatch.setattr(store, "cached", lambda key: {"untrusted": "SECRET"})
    result = run_articles(store)
    assert result["reason"] == "local_cache_or_budget_invalid" and not calls
    assert "SECRET" not in str(result)


@pytest.mark.parametrize("kwargs", [
    {"phrase": "a&mode=other"}, {"as_of": "2026-11-29T12:00:00Z"},
    {"limit": True}, {"execute": "yes"}, {"timeout": 999},
])
def test_bad_inputs_rejected(setup, kwargs):
    store, calls, _ = setup
    options = {"phrase": "energy", "as_of": AS_OF, "cache": store, **kwargs}
    with pytest.raises(ValueError):
        collect.collect_news("gdelt_articles", **options)
    assert not calls
