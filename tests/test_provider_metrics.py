"""Aggregates only fixed-cardinality, non-sensitive provider telemetry."""

import logging
from types import SimpleNamespace

import pandas
import pytest

from mcp_trendpulse import news, trends_rate_control
from mcp_trendpulse.errors import ProviderRateLimitError
from mcp_trendpulse.provider_metrics import ProviderMetrics
from mcp_trendpulse.trends_rate_control import InterestResultCache, TrendsRequestPacer


def test_metrics_are_bounded_and_periodic_logs_contain_no_query_text(caplog):
    registry = ProviderMetrics(log_every=2)
    query = "private-secret-search-term"
    with caplog.at_level(logging.INFO, logger="mcp_trendpulse.provider_metrics"):
        registry.count("trends_http_request")
        registry.count("trends_cache_hit")
    registry.observe_ms("trends_http", 19)
    assert registry.snapshot() == {
        "counters": {"trends_cache_hit": 1, "trends_http_request": 1},
        "latency_buckets_ms": {"trends_http_le_250": 1},
    }
    assert "provider_metrics" in caplog.text
    assert query not in caplog.text
    with pytest.raises(ValueError, match="Unknown provider metric event"):
        registry.count(query)
    with pytest.raises(ValueError, match="Unknown provider latency source"):
        registry.observe_ms(query, 2.0)


def test_cache_records_hits_misses_and_evictions(monkeypatch):
    metrics = ProviderMetrics(log_every=1000)
    monkeypatch.setattr(trends_rate_control, "provider_metrics", metrics)
    cache = InterestResultCache(max_entries=1, ttl_seconds=90)
    def load():
        return pandas.DataFrame({"a": [10]})
    cache.get_or_load("interest_over_time", (["a"],), {"geo": "US"}, load)
    cache.get_or_load("interest_over_time", (["a"],), {"geo": "US"}, load)
    cache.get_or_load("interest_over_time", (["a"],), {"geo": "GB"}, load)
    counts = metrics.snapshot()["counters"]
    assert counts["trends_cache_miss"] == 2
    assert counts["trends_cache_hit"] == 1
    assert counts["trends_cache_eviction"] == 1


def test_pacer_records_429_cooldown_and_network_latency(monkeypatch):
    metrics = ProviderMetrics(log_every=1000)
    monkeypatch.setattr(trends_rate_control, "provider_metrics", metrics)
    now = [10.0]
    pacer = TrendsRequestPacer(
        delay_provider=lambda: 0,
        clock=lambda: now[0],
        sleeper=lambda seconds: now.__setitem__(0, now[0] + seconds),
        jitter=lambda: 0,
    )

    def send(*args, **kwargs):
        now[0] += 0.3
        return SimpleNamespace(status_code=429, headers={"Retry-After": "45"})

    pacer.send(send, "GET", "https://trends.google.com")
    with pytest.raises(ProviderRateLimitError):
        pacer.ensure_available("interest_over_time")
    snapshot = metrics.snapshot()
    assert snapshot["counters"] == {
        "trends_cooldown_block": 1,
        "trends_cooldown_open": 1,
        "trends_http_429": 1,
        "trends_http_request": 1,
    }
    assert snapshot["latency_buckets_ms"] == {"trends_http_le_1000": 1}


def test_news_lookup_counters_do_not_log_provider_arguments(monkeypatch, caplog):
    metrics = ProviderMetrics(log_every=2)
    monkeypatch.setattr(news, "provider_metrics", metrics)

    class FailingNews:
        def get_news(self, keyword):
            exc = RuntimeError("429 Too Many Requests: private search")
            exc.response = SimpleNamespace(status_code=429)
            raise exc

    with caplog.at_level(logging.INFO, logger="mcp_trendpulse.provider_metrics"):
        with pytest.raises(ProviderRateLimitError):
            news._call_google_news(FailingNews(), "get_news", "private search")
    counts = metrics.snapshot()["counters"]
    assert counts == {"news_feed_429": 1, "news_feed_error": 1, "news_feed_request": 1}
    assert "private search" not in caplog.text
    assert "news_feed_le_" in str(metrics.snapshot()["latency_buckets_ms"])
