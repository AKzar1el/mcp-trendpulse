"""Offline shared-state tests; no Google requests, credentials or paid services."""

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pandas
import pytest

from mcp_trendpulse import trends_rate_control
from mcp_trendpulse.errors import ProviderTimeoutError
from mcp_trendpulse.provider_metrics import ProviderMetrics
from mcp_trendpulse.shared_state import (
    SharedCooldownError,
    SharedQueueFullError,
    SharedTrendsState,
    get_shared_state,
)
from mcp_trendpulse.trends_rate_control import InterestResultCache, TrendsRequestPacer


def test_shared_request_slots_are_coordinated_between_independent_instances(tmp_path):
    now = [1000.0]
    waits = []

    def sleep(seconds):
        waits.append(seconds)
        now[0] += seconds

    first = SharedTrendsState(tmp_path, clock=lambda: now[0], sleeper=sleep)
    second = SharedTrendsState(tmp_path, clock=lambda: now[0], sleeper=sleep)
    first.reserve(delay_seconds=2)
    second.reserve(delay_seconds=2)
    assert waits == [2.0]
    assert now[0] == 1002.0

    first.extend_cooldown(30)
    with pytest.raises(SharedCooldownError):
        second.reserve(delay_seconds=2)
    now[0] += 30
    second.reserve(delay_seconds=2)


def test_shared_queue_is_bounded_to_prevent_long_provider_waits(tmp_path):
    state = SharedTrendsState(tmp_path, clock=lambda: 1000.0, sleeper=lambda _seconds: None)
    for _ in range(7):
        state.reserve(delay_seconds=2)
    with pytest.raises(SharedQueueFullError):
        state.reserve(delay_seconds=2)


def test_shared_cache_roundtrip_omits_raw_keywords_and_obeys_ttl(tmp_path):
    now = [1000.0]
    state1 = SharedTrendsState(tmp_path, clock=lambda: now[0])
    state2 = SharedTrendsState(tmp_path, clock=lambda: now[0])
    terms = ("confidential-rare-business-term", "another-private-query")
    key = (terms, (("cat", 0), ("geo", "SI"), ("timeframe", "today 12-m")))
    original = pandas.DataFrame(
        {
            terms[0]: [10.0, 20.0],
            terms[1]: [70.0, 80.0],
            "isPartial": [False, True],
        },
        index=pandas.date_range("2026-10-01", periods=2, tz="UTC", name="time [UTC]"),
    )
    assert state1.put_series(key, original)
    restored = state2.get_series(key)
    pandas.testing.assert_frame_equal(restored, original)

    with sqlite3.connect(str(tmp_path / "state.sqlite3")) as db:
        contents = db.execute("SELECT key, payload FROM series").fetchall()
    assert len(contents) == 1
    assert all(term not in repr(contents) for term in terms)

    # 12-month trend data is cached for 90 minutes, not indefinitely.
    now[0] += 5_401
    assert state2.get_series(key) is None


def test_shared_cache_does_not_store_unexpected_non_numeric_data(tmp_path):
    state = SharedTrendsState(tmp_path)
    key = (("a",), (("geo", "US"), ("timeframe", "today 12-m")))
    text_frame = pandas.DataFrame(
        {"a": ["private raw payload"]},
        index=pandas.date_range("2026-01-01", periods=1),
    )
    assert not state.put_series(key, text_frame)
    assert state.get_series(key) is None


def test_cross_process_cache_reuse_without_duplicate_provider_fetch(tmp_path):
    first_state = SharedTrendsState(tmp_path)
    second_state = SharedTrendsState(tmp_path)
    first = InterestResultCache(shared_provider=lambda: first_state)
    second = InterestResultCache(shared_provider=lambda: second_state)
    calls = []
    key_args = (["alpha"],)
    key_kwargs = {"geo": "US", "timeframe": "today 12-m"}

    def load():
        calls.append(True)
        return pandas.DataFrame(
            {"alpha": [25.0, 80.0]},
            index=pandas.date_range("2026-01-01", periods=2, name="time [UTC]"),
        )

    original = first.get_or_load("interest_over_time", key_args, key_kwargs, load)
    restored = second.get_or_load("interest_over_time", key_args, key_kwargs, load)
    pandas.testing.assert_frame_equal(original, restored)
    assert len(calls) == 1


def test_independent_cache_instances_coalesce_concurrent_misses(tmp_path):
    state_a = SharedTrendsState(tmp_path)
    state_b = SharedTrendsState(tmp_path)
    cache_a = InterestResultCache(shared_provider=lambda: state_a)
    cache_b = InterestResultCache(shared_provider=lambda: state_b)
    entered = threading.Event()
    release = threading.Event()
    provider_calls = []
    args = (["alpha"],)
    kwargs = {"geo": "US", "timeframe": "today 12-m"}

    def fetch_from_provider():
        provider_calls.append(1)
        entered.set()
        assert release.wait(timeout=5)
        return pandas.DataFrame(
            {"alpha": [15.0]},
            index=pandas.date_range("2026-01-01", periods=1, name="time [UTC]"),
        )

    def load_first():
        return cache_a.get_or_load("interest_over_time", args, kwargs, fetch_from_provider)

    def load_second():
        return cache_b.get_or_load("interest_over_time", args, kwargs, fetch_from_provider)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(load_first)
        assert entered.wait(timeout=5)
        second = pool.submit(load_second)
        release.set()
        pandas.testing.assert_frame_equal(first.result(timeout=5), second.result(timeout=5))
    assert len(provider_calls) == 1


def test_slow_cross_process_fill_times_out_without_duplicate_provider_request(tmp_path, monkeypatch):
    now = [1000.0]

    def clock():
        return now[0]

    monkeypatch.setattr(trends_rate_control, "monotonic", clock)
    monkeypatch.setattr(trends_rate_control, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))

    owner_state = SharedTrendsState(tmp_path, clock=clock)
    waiter_state = SharedTrendsState(tmp_path, clock=clock)
    waiter_cache = InterestResultCache(shared_provider=lambda: waiter_state)
    args, kwargs = (["alpha"],), {"geo": "US", "timeframe": "today 12-m"}
    key = waiter_cache._key("interest_over_time", args, kwargs)
    owner = owner_state.claim_series_fill(key)
    assert owner is not None
    provider_calls = []

    def load():
        provider_calls.append(1)
        return pandas.DataFrame(
            {"alpha": [25.0]},
            index=pandas.date_range("2026-10-01", periods=1),
        )

    # The other process still owns its 90-second lease when our 10-second
    # wait expires. The caller must time out, not issue a second Google call.
    with pytest.raises(ProviderTimeoutError):
        waiter_cache.get_or_load("interest_over_time", args, kwargs, load)
    assert now[0] >= 1010.0
    assert provider_calls == []

    # The original process can still publish its result, and the waiting
    # process can recover on the next call using the shared cache.
    owner_state.put_series(key, load())
    owner_state.release_series_fill(key, owner)
    restored = waiter_cache.get_or_load("interest_over_time", args, kwargs, load)
    assert restored["alpha"].tolist() == [25.0]
    assert len(provider_calls) == 1


def test_slow_cross_process_fill_completes_before_wait_deadline(tmp_path, monkeypatch):
    now = [1000.0]

    def clock():
        return now[0]

    owner_state = SharedTrendsState(tmp_path, clock=clock)
    waiter_state = SharedTrendsState(tmp_path, clock=clock)
    cache = InterestResultCache(shared_provider=lambda: waiter_state)
    args, kwargs = (["alpha"],), {"geo": "US", "timeframe": "today 12-m"}
    key = cache._key("interest_over_time", args, kwargs)
    owner = owner_state.claim_series_fill(key)
    assert owner is not None
    original = pandas.DataFrame(
        {"alpha": [75.0]},
        index=pandas.date_range("2026-10-01", periods=1),
    )
    finished = [False]

    def advance(seconds):
        now[0] += seconds
        if now[0] >= 1008.0 and not finished[0]:
            assert owner_state.put_series(key, original)
            owner_state.release_series_fill(key, owner)
            finished[0] = True

    monkeypatch.setattr(trends_rate_control, "monotonic", clock)
    monkeypatch.setattr(trends_rate_control, "sleep", advance)

    def unexpected_provider_call():
        pytest.fail("A waiting process must reuse the first process's result")

    restored = cache.get_or_load("interest_over_time", args, kwargs, unexpected_provider_call)
    assert finished[0]
    assert restored["alpha"].tolist() == [75.0]


def test_expired_lease_cannot_be_deleted_by_old_owner(tmp_path):
    now = [1_000.0]
    first = SharedTrendsState(tmp_path, clock=lambda: now[0])
    second = SharedTrendsState(tmp_path, clock=lambda: now[0])
    key = (("alpha",), (("geo", "US"),))
    original_owner = first.claim_series_fill(key)
    assert original_owner
    assert second.claim_series_fill(key) is None
    now[0] += 91
    new_owner = second.claim_series_fill(key)
    assert new_owner
    first.release_series_fill(key, original_owner)
    assert first.claim_series_fill(key) is None
    second.release_series_fill(key, new_owner)
    assert first.claim_series_fill(key)


def test_pacer_uses_shared_state_and_preserves_local_fallback(tmp_path, monkeypatch):
    metrics = ProviderMetrics(log_every=1000)
    monkeypatch.setattr(trends_rate_control, "provider_metrics", metrics)
    now = [1000.0]
    calls = []
    shared = SharedTrendsState(tmp_path, clock=lambda: now[0], sleeper=lambda t: now.__setitem__(0, now[0] + t))
    pacer = TrendsRequestPacer(
        delay_provider=lambda: 0,
        clock=lambda: now[0],
        sleeper=lambda seconds: now.__setitem__(0, now[0] + seconds),
        shared_provider=lambda: shared,
    )

    def send(*args, **kwargs):
        calls.append(True)
        return type("Response", (), {"status_code": 200})()

    pacer.send(send, "GET", "https://trends.google.com")
    assert len(calls) == 1

    def broken_shared():
        raise sqlite3.OperationalError("database busy")

    fallback = TrendsRequestPacer(delay_provider=lambda: 0, shared_provider=broken_shared)
    assert fallback.send(send, "GET", "https://trends.google.com").status_code == 200
    assert metrics.snapshot()["counters"]["trends_shared_state_fallback"] == 1


def test_shared_state_is_explicit_opt_in(monkeypatch, tmp_path):
    monkeypatch.delenv("TRENDPULSE_SHARED_STATE_DIR", raising=False)
    assert get_shared_state() is None
    monkeypatch.setenv("TRENDPULSE_SHARED_STATE_DIR", str(tmp_path))
    assert get_shared_state() is not None
    assert (tmp_path / "state.sqlite3").exists()
