"""Two simultaneous identical V2 requests must not consume duplicate free quota.

Uses the real SQLite BudgetCache, independent worker threads and injected
fixture fetches (no HTTP). Covers all five optional V2 source adapters.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from multiprocessing import get_all_start_methods, get_context
from pathlib import Path

import pytest

from mcp_trendpulse.intelligence_core import BudgetCache
from mcp_trendpulse.mjau_v2.depsdev_graph import inspect_package_dependencies
from mcp_trendpulse.mjau_v2.endoflife_release import observe_release_support
from mcp_trendpulse.mjau_v2.github_stars import github_star_history
from mcp_trendpulse.mjau_v2.hf_catalog import discover_hf_catalog
from mcp_trendpulse.mjau_v2.openssf_scorecard import inspect_openssf_scorecard


@pytest.mark.parametrize("source", ["stars", "dependencies", "scorecard", "lifecycle", "hub"])
def test_concurrent_identical_source_misses_use_only_one_quota(source, tmp_path):
    cache = BudgetCache(tmp_path / source)
    now = datetime.now(timezone.utc)
    source_calls = []
    source_lock = threading.Lock()
    launch = threading.Barrier(3, timeout=8)

    star_epoch = int(now.timestamp()) - 14 * 86400
    payloads = {
        "stars": [{
            "week": star_epoch,
            "total": 2,
            "days": [0, 1, 1, 0, 0, 0, 0],
        }],
        "dependencies": {
            "nodes": [
                {"versionKey": {"system": "NPM", "name": "is-odd", "version": "3.0.1"},
                 "relation": "SELF", "bundled": False, "errors": []},
                {"versionKey": {"system": "NPM", "name": "is-number", "version": "6.0.0"},
                 "relation": "DIRECT", "bundled": False, "errors": []},
            ],
            "edges": [{"fromNode": 0, "toNode": 1}],
            "error": "",
        },
        "scorecard": {
            "date": now.date().isoformat(),
            "repo": {"name": "github.com/pallets/flask", "commit": "a" * 40},
            "scorecard": {"version": "v5.1.0"},
            "score": 7.0,
            "checks": [{"name": "Maintained", "score": 10}],
        },
        "lifecycle": {
            "schema_version": "1.2.1",
            "generated_at": (now - timedelta(seconds=5)).isoformat(),
            "result": {"name": "20", "isEol": True, "isMaintained": True,
                       "isEoes": False, "eolFrom": "2026-04-30"},
        },
        "hub": [{
            "id": "example/public-model",
            "modelId": "example/public-model",
            "private": False, "gated": False,
            "trendingScore": 23.0, "downloads": 200, "likes": 18,
            "createdAt": (now - timedelta(hours=1)).isoformat(),
        }],
    }

    def fetcher(*_args):
        with source_lock:
            source_calls.append(source)
        time.sleep(0.28)
        return 200, payloads[source]

    def invoke():
        launch.wait()
        if source == "stars":
            return github_star_history(
                owner="AKzar1el", repo="mcp-trendpulse", limit=10,
                execute=True, cache=cache, fetcher=fetcher, observed_at=now,
            )
        if source == "dependencies":
            return inspect_package_dependencies(
                ecosystem="npm", package="is-odd", version="3.0.1",
                execute=True, cache=cache, fetcher=fetcher, observed_at=now,
            )
        if source == "scorecard":
            return inspect_openssf_scorecard(
                owner="pallets", repo="flask",
                execute=True, cache=cache, fetcher=fetcher, observed_at=now,
            )
        if source == "lifecycle":
            return observe_release_support(
                product="nodejs", release="20",
                execute=True, cache=cache, fetcher=fetcher, observed_at=now,
            )
        return discover_hf_catalog(
            kind="models", limit=2,
            execute=True, cache=cache, fetcher=fetcher, observed_at=now,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(invoke)
        second = pool.submit(invoke)
        launch.wait()
        answers = [first.result(timeout=12), second.result(timeout=12)]

    assert all(x["status"] in {"observed", "observed_partial"} for x in answers)
    assert len(source_calls) == 1, "Duplicate provider GET spent unnecessary free quota"
    assert sum(x["requests_attempted"] for x in answers) == 1
    assert sorted(x["cache_hit"] for x in answers) == [False, True]


def _multi_process_hub_probe(root, ready, start, results, fetch_count):
    cache = BudgetCache(Path(root))
    ready.put(True)
    if not start.wait(timeout=15):
        results.put(("timeout", False, -1))
        return

    def fetch(_url, _params):
        with fetch_count.get_lock():
            fetch_count.value += 1
        time.sleep(0.25)
        return 200, [{
            "id": "example/public-model", "modelId": "example/public-model",
            "private": False, "gated": False, "trendingScore": 7,
            "downloads": 10, "likes": 2,
        }]

    answer = discover_hf_catalog(
        kind="models", limit=2, execute=True, cache=cache, fetcher=fetch,
    )
    results.put((answer["status"], answer["cache_hit"], answer["requests_attempted"]))


def test_singleflight_works_between_separate_processes(tmp_path):
    # Pytest's Linux import mode can name this module tests.* without making
    # that package importable to a spawned child. Fork validates independent
    # POSIX process locking; Windows still verifies real spawn semantics.
    context = get_context("fork" if "fork" in get_all_start_methods() else "spawn")
    ready, responses = context.Queue(), context.Queue()
    go = context.Event()
    attempts = context.Value("i", 0)
    workers = [
        context.Process(
            target=_multi_process_hub_probe,
            args=(str(tmp_path / "shared"), ready, go, responses, attempts),
        )
        for _ in range(2)
    ]
    try:
        for worker in workers:
            worker.start()
        for _ in workers:
            assert ready.get(timeout=20) is True
        go.set()
        outputs = [responses.get(timeout=20) for _ in workers]
        for worker in workers:
            worker.join(timeout=12)
            assert worker.exitcode == 0
        assert attempts.value == 1
        assert sorted(item[1] for item in outputs) == [False, True]
        assert all(item[0] == "observed_partial" for item in outputs)
        assert sum(item[2] for item in outputs) == 1
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
            worker.join(timeout=3)


def test_distinct_hub_queries_can_fetch_concurrently(tmp_path):
    cache = BudgetCache(tmp_path / "distinct")
    entered = threading.Barrier(2, timeout=5)

    def fetch(url, _params):
        entered.wait()
        if url.endswith("/models"):
            return 200, [{"id": "example/model", "modelId": "example/model",
                          "private": False, "gated": False, "trendingScore": 2}]
        return 200, [{"id": "example/dataset", "private": False,
                      "gated": False, "trendingScore": 3}]

    def run(kind):
        return discover_hf_catalog(
            kind=kind, limit=2, execute=True, cache=cache, fetcher=fetch,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, ["models", "datasets"]))
    assert all(r["status"] == "observed_partial" for r in results)
    assert all(r["requests_attempted"] == 1 for r in results)


def test_rate_limited_identical_requests_do_not_retry_source(tmp_path):
    cache = BudgetCache(tmp_path / "rate-limit")
    call_count = []

    def blocked_fetch(*_args):
        call_count.append(1)
        return 429, None

    first = discover_hf_catalog(
        kind="datasets", limit=2, execute=True, cache=cache, fetcher=blocked_fetch
    )
    second = discover_hf_catalog(
        kind="datasets", limit=2, execute=True, cache=cache, fetcher=blocked_fetch
    )
    assert first["status"] == second["status"] == "unavailable"
    assert first["reason"] == "http_429"
    assert second["reason"] == "provider_cooldown"
    assert second["requests_attempted"] == 0
    assert len(call_count) == 1


def test_request_lock_failure_fails_closed_without_reserving(monkeypatch, tmp_path):
    from mcp_trendpulse.mjau_v2 import singleflight

    cache = BudgetCache(tmp_path / "lock-error")
    def broken_lock(*_args):
        raise OSError("synthetic lock failure")

    monkeypatch.setattr(singleflight, "_source_lock", broken_lock)
    called = []
    result = discover_hf_catalog(
        kind="models", execute=True, cache=cache,
        fetcher=lambda *_args: called.append(True),
    )
    assert result["status"] == "unavailable"
    assert result["reason"] == "local_request_lock_unavailable"
    assert result["requests_attempted"] == 0
    assert result["network_performed"] is False
    assert not called
