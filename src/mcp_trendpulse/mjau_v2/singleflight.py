"""Singleflight guard for optional V2 source adapters using the existing SQLite root.

Identical simultaneous cacheable misses share one provider reservation across
threads/processes; noncacheable failures may be queried again after the lock.
Disjoint source queries are independent. Plan-only does not touch SQLite or
the filesystem. Native BudgetCache still owns all quotas and source validation.
"""
from __future__ import annotations

from contextlib import nullcontext
from functools import wraps
from inspect import signature
from pathlib import Path
import re
from typing import Any, Callable

from filelock import FileLock, Timeout as FileLockTimeout

from mcp_trendpulse import intelligence_core
from mcp_trendpulse.intelligence_core import IntelligenceError


def _source_lock(cache: Any, key: str):
    db = getattr(cache, "db", None)
    if db is None:
        # Injected test doubles need not expose any on-disk lock metadata.
        return nullcontext()
    db = Path(db)
    if not db.is_absolute() or db.is_symlink():
        raise IntelligenceError("Untrusted V2 cache database for request lock")
    folder = db.parent / ".request_locks"
    if folder.is_symlink():
        raise IntelligenceError("V2 request lock directory cannot be symlink")
    folder.mkdir(mode=0o700, exist_ok=True)
    lock_path = folder / (key + ".lock")
    if lock_path.is_symlink():
        raise IntelligenceError("V2 request lock file cannot be symlink")
    # The longest HTTP request allows up to 4s connect + 12s read.
    return FileLock(str(lock_path), timeout=24)


def singleflight_request(key_for: Callable[[dict[str, Any]], str]):
    """Decorate a keyword-only V2 adapter without changing its public API."""

    def decorator(function):
        call_signature = signature(function)

        @wraps(function)
        def wrapped(*args, **kwargs):
            bound = call_signature.bind(*args, **kwargs)
            bound.apply_defaults()
            if bound.arguments["execute"] is not True:
                return function(*args, **kwargs)

            # Validate identifiers, execute flags and timestamp before any IO.
            # Every V2 adapter has a strictly IO-free plan path.
            planned_args = dict(bound.arguments)
            planned_args["execute"] = False
            plan = function(**planned_args)
            try:
                cache = bound.arguments["cache"]
                if cache is None:
                    cache = intelligence_core.BudgetCache(
                        root=Path.home() / ".mcp-trendpulse" / "mjau-v2-intelligence"
                    )
                key = key_for(bound.arguments)
                if (not isinstance(key, str) or len(key) > 160
                        or not re.fullmatch(r"[A-Za-z0-9_-]+", key)):
                    raise IntelligenceError("Invalid V2 request lock key")
                with _source_lock(cache, key):
                    # Cache lookup is deliberately repeated under the lock:
                    # the first request has now populated it, if cacheable.
                    return function(**{**bound.arguments, "cache": cache})
            except (FileLockTimeout, IntelligenceError, OSError) as exc:
                # No source request when the lock is unavailable. Never
                # misreport an uncompleted query as no_data or zero demand.
                return {
                    **plan,
                    "status": "unavailable",
                    "reason": ("identical_request_still_running"
                               if isinstance(exc, FileLockTimeout)
                               else "local_request_lock_unavailable"),
                    "requests_attempted": 0,
                    "network_performed": False,
                    "cache_hit": False,
                }
        return wrapped
    return decorator
