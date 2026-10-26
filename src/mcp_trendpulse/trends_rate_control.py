"""Best-effort process-local pressure control for unofficial Google Trends traffic.

This is not a Google quota and does not coordinate multiple server processes or
replicas. It intentionally leaves the inbound MCP middleware unchanged.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from math import isfinite
from random import random
from threading import Event, Lock
from time import monotonic, sleep
from typing import Any

from mcp_trendpulse.config import get_google_trends_delay
from mcp_trendpulse.errors import ProviderRateLimitError, ProviderTimeoutError


class TrendsCooldownError(RuntimeError):
    """Signal local upstream cooldown without sending another Google request."""


class TrendsRequestPacer:
    """Share spacing and 429 cooldown between all TrendSpy sessions in a process."""

    def __init__(
        self,
        *,
        delay_provider: Callable[[], float] = get_google_trends_delay,
        clock: Callable[[], float] = monotonic,
        sleeper: Callable[[float], None] = sleep,
        jitter: Callable[[], float] = random,
    ):
        self._delay_provider = delay_provider
        self._clock = clock
        self._sleep = sleeper
        self._jitter = jitter
        self._lock = Lock()
        self._next_request_at = 0.0
        self._cooldown_until = 0.0
        self._consecutive_limits = 0

    def _minimum_delay(self) -> float:
        delay = float(self._delay_provider())
        return max(0.0, delay) if isfinite(delay) else 2.0

    @staticmethod
    def _retry_after_seconds(headers: Mapping[str, Any] | None) -> float | None:
        if not headers:
            return None
        raw_value = headers.get("Retry-After") or headers.get("retry-after")
        if raw_value is None:
            return None
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            try:
                target = parsedate_to_datetime(str(raw_value))
            except (TypeError, ValueError, IndexError):
                return None
            if target.tzinfo is None:
                target = target.replace(tzinfo=timezone.utc)
            value = (target - datetime.now(timezone.utc)).total_seconds()
        return min(86400.0, max(0.0, value)) if isfinite(value) else None

    def _record_limit_locked(self, headers: Mapping[str, Any] | None = None) -> None:
        self._consecutive_limits = min(6, self._consecutive_limits + 1)
        exponential = min(300.0, 30.0 * (2 ** (self._consecutive_limits - 1)))
        hinted = self._retry_after_seconds(headers) or 0.0
        cooldown = max(exponential + self._jitter(), hinted)
        self._cooldown_until = max(self._cooldown_until, self._clock() + cooldown)

    def ensure_available(self, operation: str) -> None:
        with self._lock:
            if self._clock() < self._cooldown_until:
                raise ProviderRateLimitError("google_trends", operation)

    def note_rate_limit(self, exc: BaseException) -> None:
        """Handle a 200 response with an embedded quota error, or an unwrapped 429."""
        response = getattr(exc, "response", None)
        with self._lock:
            if self._clock() < self._cooldown_until:
                return  # Already registered by the HTTP wrapper; do not double-count.
            self._record_limit_locked(getattr(response, "headers", None))

    def send(self, send_request: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Pace all TrendSpy session HTTP requests, including its batch POST path."""
        with self._lock:
            if self._clock() < self._cooldown_until:
                raise TrendsCooldownError("Google Trends rate limit cooldown is active")
            wait = self._next_request_at - self._clock()
            if wait > 0:
                self._sleep(wait)
            # A stalled unofficial endpoint must not indefinitely monopolize the gate.
            kwargs.setdefault("timeout", 20.0)
            try:
                response = send_request(*args, **kwargs)
            finally:
                self._next_request_at = self._clock() + self._minimum_delay()

            status = getattr(response, "status_code", None)
            if status == 429:
                self._record_limit_locked(getattr(response, "headers", None))
            elif status == 200:
                self._consecutive_limits = 0
            return response


def install_trends_session_pacing(client: Any, pacer: TrendsRequestPacer) -> bool:
    """Wrap only this TrendSpy client's requests.Session; preserve cookies/proxies."""
    session = getattr(client, "session", None)
    if session is None or not callable(getattr(session, "request", None)):
        return False
    if getattr(session, "_trendpulse_paced", False):
        return True

    original_request = session.request

    def paced_request(method: str, url: str, **kwargs: Any) -> Any:
        return pacer.send(original_request, method, url, **kwargs)

    session.request = paced_request
    session._trendpulse_paced = True
    return True


class InterestResultCache:
    """Small, per-process TTL cache with single-flight for identical time-series."""

    def __init__(
        self,
        *,
        ttl_seconds: float = 90.0,
        max_entries: int = 128,
        clock: Callable[[], float] = monotonic,
    ):
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._lock = Lock()
        self._entries: OrderedDict[tuple[Any, ...], tuple[float, Any]] = OrderedDict()
        self._inflight: dict[tuple[Any, ...], Event] = {}

    @staticmethod
    def _key(name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> tuple[Any, ...] | None:
        if name != "interest_over_time" or len(args) != 1:
            return None
        keywords = args[0]
        if isinstance(keywords, str):
            terms = (keywords,)
        elif isinstance(keywords, (list, tuple)) and all(isinstance(word, str) for word in keywords):
            terms = tuple(keywords)
        else:
            return None

        # Only scalar provider inputs are safe to key without lossy coercion.
        if not terms or any(not term for term in terms):
            return None
        if any(not isinstance(value, (str, int, float, bool, type(None))) for value in kwargs.values()):
            return None
        return (terms, tuple(sorted(kwargs.items())))

    def get_or_load(
        self,
        name: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        loader: Callable[[], Any],
    ) -> Any:
        key = self._key(name, args, kwargs)
        if key is None:
            return loader()

        while True:
            with self._lock:
                entry = self._entries.get(key)
                if entry is not None and entry[0] > self._clock():
                    self._entries.move_to_end(key)
                    return deepcopy(entry[1])
                if entry is not None:
                    del self._entries[key]
                event = self._inflight.get(key)
                leader = event is None
                if leader:
                    event = Event()
                    self._inflight[key] = event

            if not leader:
                if not event.wait(timeout=45):
                    raise ProviderTimeoutError("google_trends", name)
                continue

            try:
                result = loader()
                if getattr(result, "empty", False):
                    return result  # Do not persist transient empty provider results.
                try:
                    cached_copy = deepcopy(result)
                except (TypeError, ValueError):
                    return result
                with self._lock:
                    self._entries[key] = (self._clock() + self._ttl, cached_copy)
                    self._entries.move_to_end(key)
                    while len(self._entries) > self._max_entries:
                        self._entries.popitem(last=False)
                return result
            finally:
                with self._lock:
                    self._inflight.pop(key, None)
                    event.set()


trends_request_pacer = TrendsRequestPacer()
trends_interest_cache = InterestResultCache()
