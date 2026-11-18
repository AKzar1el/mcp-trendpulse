"""Ten-agent duplicate-request coalescing and distinct-source concurrency.

All tests mock the provider HTTP layer: no external network or vendor keys.
The integration remains opt-in, single-user scoped, with the existing cache.
"""

from __future__ import annotations

import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock

from mcp_trendpulse import intelligence_core as intel


class Response:
    headers = {"Content-Type": "application/json"}

    def __init__(self, on_close):
        self.on_close = on_close

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.on_close()
        return False

    def read(self, n):
        time.sleep(0.08)  # Long enough to expose concurrent cache misses.
        return json.dumps([
            {"page": 1, "pages": 1},
            [{"date": "2025", "value": 100.0, "indicator": {"id": "NY.GDP.MKTP.CD"}}],
        ]).encode("utf-8")


def _fake_provider(monkeypatch):
    stats = {"requests": 0, "active": 0, "peak": 0}
    gate = Lock()

    def open_request(req, timeout):
        with gate:
            stats["requests"] += 1
            stats["active"] += 1
            stats["peak"] = max(stats["active"], stats["peak"])

        def closed():
            with gate:
                stats["active"] -= 1

        return Response(closed)

    class Opener:
        def open(self, req, timeout):
            return open_request(req, timeout)

    monkeypatch.setattr(intel, "build_opener", lambda *_: Opener())
    return stats


def test_ten_simultaneous_identical_calls_cost_only_one_provider_request(
    tmp_path, monkeypatch,
):
    stats = _fake_provider(monkeypatch)
    cache = intel.BudgetCache(tmp_path)
    plan = intel.plan_source(
        "worldbank", country="US", identifier="NY.GDP.MKTP.CD", limit=1,
        env={},
    )
    started = Barrier(10)

    def worker(_):
        started.wait(timeout=5)
        return intel.collect(plan, cache=cache, fetch=True, timeout=5, env={})

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(worker, range(10)))

    assert all(x["status"] == "observed" for x in results)
    assert stats["requests"] == 1  # Without single-flight: up to ten.
    assert sum(bool(x["cache_hit"]) for x in results) == 9
    assert len({x["retrieved_at"] for x in results}) == 1
    with sqlite3.connect(cache.db) as db:
        used = db.execute(
            "SELECT used FROM budget WHERE source = ?", ("worldbank",)
        ).fetchone()[0]
    assert used == 1


def test_different_queries_still_fetch_in_parallel(tmp_path, monkeypatch):
    stats = _fake_provider(monkeypatch)
    cache = intel.BudgetCache(tmp_path)
    plan_us = intel.plan_source(
        "worldbank", country="US", identifier="NY.GDP.MKTP.CD", limit=1, env={}
    )
    plan_de = intel.plan_source(
        "worldbank", country="DE", identifier="NY.GDP.MKTP.CD", limit=1, env={}
    )
    started = Barrier(2)

    def worker(plan):
        started.wait(timeout=5)
        return intel.collect(plan, cache=cache, fetch=True, timeout=5, env={})

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, [plan_us, plan_de]))
    assert all(x["status"] == "observed" for x in results)
    assert stats["requests"] == 2
    assert stats["peak"] == 2
    with sqlite3.connect(cache.db) as db:
        assert db.execute(
            "SELECT used FROM budget WHERE source = ?", ("worldbank",)
        ).fetchone()[0] == 2
