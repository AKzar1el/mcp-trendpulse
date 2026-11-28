"""No-internet chaos tests for the free-only source collector.

Proves short-lived failed-request caching, cross-query throttling, credential
isolation, malformed upstream responses, database corruption fail-closed and
recovery without exponential retries or billable fallbacks.
"""

from __future__ import annotations

import io
import sqlite3
from urllib.error import HTTPError

import pytest

from mcp_trendpulse import intelligence_core as core


class FakeResponse:
    headers = {"Content-Type": "application/json"}

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self, n): return self.payload


def _opener(monkeypatch, callback):
    class Opener:
        def open(self, req, timeout):
            return callback(req, timeout)
    monkeypatch.setattr(core, "build_opener", lambda *_: Opener())


def test_429_short_cached_failure_and_provider_cooldown_across_queries(tmp_path, monkeypatch):
    calls = []

    def responder(req, timeout):
        calls.append(req.full_url)
        raise HTTPError(req.full_url, 429, "Too Many Requests",
                        {"Retry-After": "80"}, io.BytesIO(b""))

    _opener(monkeypatch, responder)
    cache = core.BudgetCache(tmp_path)
    a = core.plan_source("worldbank", identifier="NY.GDP.MKTP.CD", country="US", env={})
    b = core.plan_source("worldbank", identifier="NY.GDP.MKTP.CD", country="DE", env={})
    first = core.collect(a, cache=cache, fetch=True)
    repeated = core.collect(a, cache=cache, fetch=True)
    sibling = core.collect(b, cache=cache, fetch=True)
    assert first["status"] == "unavailable"
    assert first["http_status"] == 429
    assert repeated["cache_hit"] is True
    assert repeated["status"] != "observed"
    assert sibling["reason"] == "provider_cooldown"
    assert len(calls) == 1


def test_failed_response_cache_expires_without_retry_loop(tmp_path, monkeypatch):
    calls = []
    from time import time

    def responder(req, timeout):
        calls.append(1)
        if len(calls) == 1:
            raise HTTPError(req.full_url, 503, "Service Unavailable", {}, io.BytesIO(b""))
        return FakeResponse(b'[{"page":1}, [{"value":19}]]')
    _opener(monkeypatch, responder)
    cache = core.BudgetCache(tmp_path)
    plan = core.plan_source("worldbank", identifier="NY.GDP.MKTP.CD", country="US", env={})
    a = core.collect(plan, cache=cache, fetch=True)
    assert a["http_status"] == 503
    assert core.collect(plan, cache=cache, fetch=True)["cache_hit"]
    with sqlite3.connect(cache.db) as conn:
        conn.execute("UPDATE cache SET until=?", (time() - 1,))
        conn.execute("UPDATE cooldown SET until=?", (time() - 1,))
    b = core.collect(plan, cache=cache, fetch=True)
    assert b["status"] == "observed"
    assert len(calls) == 2


def test_malformed_upstream_envelope_is_cached_not_demand(tmp_path, monkeypatch):
    calls = []
    def bad(req, timeout):
        calls.append(1)
        return FakeResponse(b'{"error":"outage"}')
    _opener(monkeypatch, bad)
    cache = core.BudgetCache(tmp_path)
    plan = core.plan_source("worldbank", identifier="NY.GDP.MKTP.CD", country="US", env={})
    a = core.collect(plan, cache=cache, fetch=True)
    b = core.collect(plan, cache=cache, fetch=True)
    assert a["status"] == "invalid_source_shape"
    assert b["cache_hit"] is True
    assert b["status"] != "observed"
    assert len(calls) == 1


def test_provider_token_rotation_does_not_replay_another_token_cache(tmp_path, monkeypatch):
    called = []
    def ok(req, timeout):
        called.append(req.get_header("Authorization"))
        return FakeResponse(b'{"items":[{"company_name":"Example"}]}')
    _opener(monkeypatch, ok)
    cache = core.BudgetCache(tmp_path)
    p1 = core.plan_source("companies_house", keyword="test", env={
        "TRENDPULSE_INTEL_COMPANIES_HOUSE_KEY": "SYNTHETIC_A_NOT_REAL",
    })
    p2 = core.plan_source("companies_house", keyword="test", env={
        "TRENDPULSE_INTEL_COMPANIES_HOUSE_KEY": "SYNTHETIC_B_NOT_REAL",
    })
    a = core.collect(p1, cache=cache, fetch=True)
    b = core.collect(p2, cache=cache, fetch=True)
    again = core.collect(p1, cache=cache, fetch=True)
    assert a["status"] == "observed"
    assert b["status"] == "observed"
    assert again["cache_hit"] is True
    assert len(called) == 2
    assert "SYNTHETIC" not in repr([a, b, again])


def test_database_corruption_does_not_fabricate_empty_demand(tmp_path):
    cache = core.BudgetCache(tmp_path)
    with sqlite3.connect(cache.db) as conn:
        conn.execute("DROP TABLE cache")
    p = core.plan_source("worldbank", identifier="NY.GDP.MKTP.CD", country="US", env={})
    with pytest.raises(sqlite3.OperationalError):
        core.collect(p, cache=cache, fetch=True)


def test_failed_provider_does_not_poison_other_provider(tmp_path, monkeypatch):
    calls = []
    def mixed(req, timeout):
        calls.append(req.full_url)
        if "api.worldbank.org" in req.full_url:
            raise HTTPError(req.full_url, 429, "Limit", {}, io.BytesIO(b""))
        return FakeResponse(b'{"data":[{"id":"GLEIF-ENTITY"}]}')
    _opener(monkeypatch, mixed)
    cache = core.BudgetCache(tmp_path)
    worldbank = core.plan_source("worldbank", identifier="NY.GDP.MKTP.CD", country="US", env={})
    gleif = core.plan_source("gleif", keyword="test", env={})
    assert core.collect(worldbank, cache=cache, fetch=True)["status"] == "unavailable"
    success = core.collect(gleif, cache=cache, fetch=True)
    assert success["status"] == "observed"
    assert len(calls) == 2


def test_long_retry_after_preserved_and_classified(tmp_path, monkeypatch):
    import time

    def limited(req, timeout):
        raise HTTPError(req.full_url, 429, "Limit", {"Retry-After": "900"}, io.BytesIO(b""))

    _opener(monkeypatch, limited)
    cache = core.BudgetCache(tmp_path)
    plan = core.plan_source("cellar", keyword="battery", env={})
    result = core.collect(plan, cache=cache, fetch=True)
    assert result["status"] == "unavailable"
    assert result["failure_class"] == "provider_rate_limited"
    assert result["retry_after_seconds"] == 900
    with sqlite3.connect(cache.db) as conn:
        until = conn.execute("SELECT until FROM cooldown WHERE source='cellar'").fetchone()[0]
    assert until - time.time() > 895


def test_retry_after_http_date():
    from datetime import datetime, timezone, timedelta
    from email.utils import format_datetime

    now = datetime(2026, 11, 25, tzinfo=timezone.utc)
    assert core._retry_after_seconds(format_datetime(now + timedelta(minutes=20), usegmt=True), now) == 1200
    assert core._retry_after_seconds("invalid", now) == 90


def test_redirect_is_unavailable_without_location_or_following(tmp_path, monkeypatch):
    calls = []

    def redirect(req, timeout):
        calls.append(req.full_url)
        raise HTTPError(req.full_url, 302, "Redirect",
                        {"Location": "https://example.com/private?secret=value"}, io.BytesIO(b""))

    _opener(monkeypatch, redirect)
    result = core.collect(core.plan_source("cordis", keyword="battery", env={}),
                          cache=core.BudgetCache(tmp_path), fetch=True)
    assert result["failure_class"] == "provider_redirect"
    assert result["http_status"] == 302
    assert result["status"] == "unavailable"
    assert "secret=value" not in repr(result)
    assert len(calls) == 1


@pytest.mark.parametrize("payload,classification", [
    (b"x" * (core.MAX_RESPONSE_BYTES + 1), "response_too_large"),
    (b"{invalid", "malformed_response"),
], ids=["oversized", "invalid-json"])
def test_bad_response_is_structured_and_cached(tmp_path, monkeypatch, payload, classification):
    calls = []

    def responder(req, timeout):
        calls.append(1)
        return FakeResponse(payload)

    _opener(monkeypatch, responder)
    cache = core.BudgetCache(tmp_path)
    plan = core.plan_source("cellar", keyword="battery", env={})
    first = core.collect(plan, cache=cache, fetch=True)
    assert first["status"] == "invalid_source_shape"
    assert first["failure_class"] == classification
    assert core.collect(plan, cache=cache, fetch=True)["cache_hit"] is True
    assert len(calls) == 1
