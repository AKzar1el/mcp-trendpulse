"""Bounded, privacy-safe per-process provider telemetry.

Only a fixed set of event names and latency buckets is recorded. Query terms,
URLs, user IDs, request bodies and provider payloads never enter these metrics.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from threading import Lock
from typing import Final


logger = logging.getLogger(__name__)

EVENTS: Final[frozenset[str]] = frozenset(
    {
        "trends_http_request",
        "trends_http_429",
        "trends_http_error",
        "trends_cooldown_open",
        "trends_cooldown_block",
        "trends_cache_hit",
        "trends_cache_miss",
        "trends_cache_wait",
        "trends_cache_eviction",
        "news_feed_request",
        "news_feed_error",
        "news_feed_429",
        "news_feed_timeout",
    }
)
LATENCY_SOURCES: Final[frozenset[str]] = frozenset({"trends_http", "news_feed"})
LATENCY_BUCKETS_MS: Final[tuple[int, ...]] = (250, 1_000, 5_000, 20_000)


class ProviderMetrics:
    """Constant-cardinality counters, emitted periodically as aggregate logs."""

    def __init__(self, *, log_every: int = 128) -> None:
        if log_every < 1:
            raise ValueError("log_every must be positive")
        self._lock = Lock()
        self._counts: Counter[str] = Counter()
        self._buckets: Counter[str] = Counter()
        self._events_since_log = 0
        self._log_every = log_every

    def count(self, event: str) -> None:
        if event not in EVENTS:
            raise ValueError("Unknown provider metric event")
        snapshot: dict[str, dict[str, int]] | None = None
        with self._lock:
            self._counts[event] += 1
            self._events_since_log += 1
            if self._events_since_log >= self._log_every:
                self._events_since_log = 0
                snapshot = self._snapshot_locked()
        if snapshot is not None:
            logger.info("provider_metrics %s", json.dumps(snapshot, separators=(",", ":"), sort_keys=True))

    def observe_ms(self, source: str, elapsed_ms: float) -> None:
        if source not in LATENCY_SOURCES:
            raise ValueError("Unknown provider latency source")
        bucket = next(
            (f"le_{boundary}" for boundary in LATENCY_BUCKETS_MS if elapsed_ms <= boundary),
            "gt_20000",
        )
        with self._lock:
            self._buckets[f"{source}_{bucket}"] += 1

    def _snapshot_locked(self) -> dict[str, dict[str, int]]:
        return {
            "counters": dict(sorted(self._counts.items())),
            "latency_buckets_ms": dict(sorted(self._buckets.items())),
        }

    def snapshot(self) -> dict[str, dict[str, int]]:
        """Copy aggregate counters for operator-only inspection and tests."""
        with self._lock:
            return self._snapshot_locked()


provider_metrics = ProviderMetrics()
