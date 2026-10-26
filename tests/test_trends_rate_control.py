"""Offline regression tests for cooperative Google Trends request protection."""

import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pandas
import pytest

from mcp_trendpulse import news
from mcp_trendpulse.errors import ProviderRateLimitError
from mcp_trendpulse.trends_rate_control import (
    InterestResultCache,
    TrendsRequestPacer,
    install_trends_session_pacing,
)


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def make_pacer(clock, delay=2.0):
    return TrendsRequestPacer(
        delay_provider=lambda: delay,
        clock=clock.monotonic,
        sleeper=clock.sleep,
        jitter=lambda: 0.0,
    )


def response(status=200, headers=None):
    return SimpleNamespace(status_code=status, headers=headers or {})


def test_outbound_pacer_spaces_requests_across_sessions_and_methods():
    clock = FakeClock()
    pacer = make_pacer(clock)
    sent_at = []

    def send(method, url, **kwargs):
        sent_at.append((clock.now, method, kwargs["timeout"]))
        return response()

    pacer.send(send, "GET", "https://trends.google.com/one")
    pacer.send(send, "POST", "https://trends.google.com/two")
    pacer.send(send, "GET", "https://trends.google.com/three", timeout=8)

    assert sent_at == [(0.0, "GET", 20.0), (2.0, "POST", 20.0), (4.0, "GET", 8)]


def test_google_429_enforces_retry_after_and_avoids_additional_requests():
    clock = FakeClock()
    pacer = make_pacer(clock, delay=0)
    sent = []

    def send(*args, **kwargs):
        sent.append(1)
        return response(429, {"Retry-After": "75"})

    assert pacer.send(send, "GET", "https://trends.google.com") .status_code == 429

    with pytest.raises(ProviderRateLimitError):
        pacer.ensure_available("interest_over_time")
    with pytest.raises(RuntimeError, match="cooldown"):
        pacer.send(send, "POST", "https://trends.google.com")
    assert len(sent) == 1

    clock.sleep(75)
    pacer.ensure_available("interest_over_time")


def test_embedded_quota_failure_opens_bounded_cooldown():
    clock = FakeClock()
    pacer = make_pacer(clock, delay=0)
    pacer.note_rate_limit(RuntimeError("API quota exceeded"))
    with pytest.raises(ProviderRateLimitError):
        pacer.ensure_available("related_queries")
    clock.sleep(30)
    pacer.ensure_available("related_queries")


def test_successful_http_response_resets_exponential_strikes():
    clock = FakeClock()
    pacer = make_pacer(clock, delay=0)
    pacer.send(lambda *_a, **_k: response(429), "GET", "https://trends.google.com")
    clock.sleep(30)
    pacer.send(lambda *_a, **_k: response(200), "GET", "https://trends.google.com")
    pacer.send(lambda *_a, **_k: response(429), "GET", "https://trends.google.com")
    clock.sleep(30)
    pacer.ensure_available("interest_over_time")


def test_session_wrapper_paces_get_and_batch_post_without_replacing_session():
    clock = FakeClock()
    pacer = make_pacer(clock)

    class FakeSession:
        def __init__(self):
            self.calls = []
            self.proxies = {"https": "http://example.invalid:8888"}

        def request(self, method, url, **kwargs):
            self.calls.append((clock.now, method, url, kwargs.get("timeout")))
            return response()

        def get(self, url, **kwargs):
            return self.request("GET", url, **kwargs)

        def post(self, url, **kwargs):
            return self.request("POST", url, **kwargs)

    session = FakeSession()
    client = SimpleNamespace(session=session)
    assert install_trends_session_pacing(client, pacer)
    assert install_trends_session_pacing(client, pacer)  # Must not wrap twice.

    session.get("https://trends.google.com/one")
    session.post("https://trends.google.com/batch", data="payload")
    assert session.calls == [
        (0.0, "GET", "https://trends.google.com/one", 20.0),
        (2.0, "POST", "https://trends.google.com/batch", 20.0),
    ]
    assert session.proxies == {"https": "http://example.invalid:8888"}


def test_identical_interest_series_are_cached_and_return_isolation_holds():
    clock = FakeClock()
    cache = InterestResultCache(ttl_seconds=90, max_entries=2, clock=clock.monotonic)
    requests = []

    def load():
        requests.append(1)
        return pandas.DataFrame({"alpha": [10, 20]})

    args = (["alpha"],)
    kwargs = {"timeframe": "today 12-m", "geo": "US", "cat": 0, "gprop": ""}
    first = cache.get_or_load("interest_over_time", args, kwargs, load)
    first.loc[0, "alpha"] = 999
    second = cache.get_or_load("interest_over_time", args, kwargs, load)

    assert second["alpha"].tolist() == [10, 20]
    assert len(requests) == 1

    clock.sleep(91)
    cache.get_or_load("interest_over_time", args, kwargs, load)
    assert len(requests) == 2


def test_cache_does_not_mix_different_geographies_or_methods():
    cache = InterestResultCache()
    requested = []

    def load():
        requested.append(1)
        return pandas.DataFrame({"alpha": [1]})

    cache.get_or_load("interest_over_time", (["alpha"],), {"geo": "US"}, load)
    cache.get_or_load("interest_over_time", (["alpha"],), {"geo": "GB"}, load)
    cache.get_or_load("related_queries", (["alpha"],), {"geo": "US"}, load)
    assert len(requested) == 3


def test_interest_series_single_flight_deduplicates_concurrent_callers():
    cache = InterestResultCache()
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def load():
        calls.append(1)
        entered.set()
        assert release.wait(timeout=5)
        return pandas.DataFrame({"alpha": [42]})

    def fetch():
        return cache.get_or_load("interest_over_time", (["alpha"],), {"geo": "US"}, load)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(fetch)
        assert entered.wait(timeout=5)
        second = pool.submit(fetch)
        release.set()
        assert first.result(timeout=5)["alpha"].tolist() == [42]
        assert second.result(timeout=5)["alpha"].tolist() == [42]
    assert len(calls) == 1


def test_trendspy_proxy_uses_cache_for_identical_normalized_interest_requests(monkeypatch):
    fake_clock = FakeClock()
    fake_pacer = make_pacer(fake_clock, delay=0)
    fake_cache = InterestResultCache(clock=fake_clock.monotonic)
    calls = []

    class FakeSession:
        def request(self, method, url, **kwargs):
            return response()

    class FakeTrends:
        def __init__(self, request_delay):
            self.session = FakeSession()

        def interest_over_time(self, keywords, **kwargs):
            calls.append((keywords, kwargs))
            return pandas.DataFrame({"alpha": [13]})

    monkeypatch.setattr(news, "Trends", FakeTrends)
    monkeypatch.setattr(news, "_trends_local", threading.local())
    monkeypatch.setattr(news, "trends_request_pacer", fake_pacer)
    monkeypatch.setattr(news, "trends_interest_cache", fake_cache)

    args = (["alpha"],)
    kwargs = {"timeframe": "today 12-m", "geo": "US", "cat": 0, "gprop": ""}
    first = news.tr.interest_over_time(*args, **kwargs)
    second = news.tr.interest_over_time(*args, **kwargs)
    assert first.equals(second)
    assert len(calls) == 1
