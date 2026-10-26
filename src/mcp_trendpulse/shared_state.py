"""Opt-in, same-host Google Trends request coordination and private numeric cache.

This uses only the Python standard library and pandas, already a TrendPulse
dependency. It does not coordinate machines without a shared filesystem and
is not an authorization mechanism or a way around Google quotas.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import math
import os
import secrets
import sqlite3
import time
from contextlib import closing, contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import pandas


logger = logging.getLogger(__name__)
MAX_ROWS = 5_000
MAX_PAYLOAD_BYTES = 512 * 1024
MAX_CACHE_ENTRIES = 256
MAX_QUEUE_SECONDS = 12.0


class SharedCooldownError(RuntimeError):
    """Another worker has registered a Google Trends quota cooldown."""


class SharedQueueFullError(RuntimeError):
    """The bounded shared request queue is already saturated."""


class SharedTrendsState:
    """SQLite-backed pacing slots and bounded series cache on one trusted host."""

    def __init__(
        self,
        directory: str | Path,
        *,
        clock: Callable[[], float] = time.time,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        root = Path(directory).expanduser()
        if not root.is_absolute() or root.is_symlink():
            raise ValueError("Shared state directory must be absolute and not a symlink")
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._db_path = root / "state.sqlite3"
        self._clock = clock
        self._sleep = sleeper
        self._secret = self._load_secret(root / "key.bin")
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS pacing ("
                "id INTEGER PRIMARY KEY CHECK(id=1), next_at REAL NOT NULL, cooldown_until REAL NOT NULL)"
            )
            connection.execute(
                "INSERT OR IGNORE INTO pacing (id, next_at, cooldown_until) VALUES (1, 0, 0)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS series ("
                "key TEXT PRIMARY KEY, expires_at REAL NOT NULL, touched_at REAL NOT NULL, payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS inflight ("
                "key TEXT PRIMARY KEY, owner TEXT NOT NULL, expires_at REAL NOT NULL)"
            )
        if os.name != "nt":
            self._db_path.chmod(0o600)

    @staticmethod
    def _load_secret(path: Path) -> bytes:
        if path.is_symlink():
            raise ValueError("Shared state secret must not be a symlink")
        try:
            fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "wb") as stream:
                stream.write(secrets.token_bytes(32))
        # The winning process may still be writing after another sees EEXIST.
        secret = b""
        for _ in range(10):
            secret = path.read_bytes()
            if len(secret) == 32:
                break
            time.sleep(0.02)
        if len(secret) != 32:
            raise ValueError("Shared state key has an invalid size")
        if os.name != "nt":
            path.chmod(0o600)
        return secret

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self._db_path), timeout=3, isolation_level=None)
        connection.execute("PRAGMA busy_timeout=3000")
        return connection

    @contextmanager
    def _connection(self):
        with closing(self._connect()) as connection:
            try:
                yield connection
            except BaseException:
                connection.rollback()
                raise

    def reserve(self, *, delay_seconds: float, max_wait_seconds: float = MAX_QUEUE_SECONDS) -> None:
        """Atomically reserve a future slot before sending an upstream request."""
        delay = max(0.0, float(delay_seconds))
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            next_at, cooldown_until = connection.execute(
                "SELECT next_at, cooldown_until FROM pacing WHERE id=1"
            ).fetchone()
            now = self._clock()
            if cooldown_until > now:
                connection.rollback()
                raise SharedCooldownError("Google Trends shared rate limit cooldown")
            scheduled = max(now, next_at)
            wait = scheduled - now
            if wait > max_wait_seconds:
                connection.rollback()
                raise SharedQueueFullError("Google Trends shared rate limit queue full")
            connection.execute(
                "UPDATE pacing SET next_at=? WHERE id=1",
                (scheduled + delay,),
            )
            connection.commit()

        if wait > 0:
            self._sleep(wait)
        # A sibling process may have received a 429 after our slot was reserved.
        with self._connection() as connection:
            cooldown_until = connection.execute(
                "SELECT cooldown_until FROM pacing WHERE id=1"
            ).fetchone()[0]
        if cooldown_until > self._clock():
            raise SharedCooldownError("Google Trends shared rate limit cooldown")

    def extend_cooldown(self, seconds: float) -> None:
        """Extend, never shorten, the shared cooldown after an upstream quota signal."""
        until = self._clock() + max(0.0, min(float(seconds), 86_400.0))
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE pacing SET cooldown_until=MAX(cooldown_until, ?) WHERE id=1",
                (until,),
            )
            connection.commit()

    def _digest(self, key: tuple[Any, ...]) -> str:
        encoded = json.dumps(key, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return hmac.new(self._secret, encoded, hashlib.sha256).hexdigest()

    @staticmethod
    def _lifetime(key: tuple[Any, ...]) -> int:
        """Use conservative freshness windows by Trends data granularity."""
        options = dict(key[1])
        window = str(options.get("timeframe", "")).lower()
        if window.startswith("now ") or window.startswith("today 1-d"):
            return 120
        if window in {"all", "today 5-y"}:
            return 7200
        if window == "today 12-m":
            return 5400
        return 1800

    @staticmethod
    def _serialize(frame: pandas.DataFrame, terms: tuple[str, ...]) -> str | None:
        if (
            not isinstance(frame, pandas.DataFrame)
            or frame.empty
            or len(frame) > MAX_ROWS
            or not isinstance(frame.index, pandas.DatetimeIndex)
            or frame.index.name not in {None, "time [UTC]"}
            or set(frame.columns) - set(terms) - {"isPartial"}
            or not all(term in frame.columns for term in terms)
        ):
            return None
        try:
            values: list[list[float | None]] = []
            for row in frame[list(terms)].itertuples(index=False, name=None):
                values.append([
                    value if math.isfinite(value := float(cell)) else None
                    for cell in row
                ])
            record = {
                "v": 1,
                "dates": [date.isoformat() for date in frame.index],
                "values": values,
                "index_utc_name": frame.index.name == "time [UTC]",
                "freq": frame.index.freqstr,
                "partial": [bool(value) for value in frame["isPartial"]] if "isPartial" in frame else None,
            }
            encoded = json.dumps(record, separators=(",", ":"), allow_nan=False)
            return encoded if len(encoded.encode("utf-8")) <= MAX_PAYLOAD_BYTES else None
        except (TypeError, ValueError, OverflowError):
            return None

    @staticmethod
    def _deserialize(payload: str, terms: tuple[str, ...]) -> pandas.DataFrame | None:
        try:
            item = json.loads(payload)
            if item["v"] != 1:
                return None
            dates, values = item["dates"], item["values"]
            if not isinstance(dates, list) or not isinstance(values, list) or len(dates) != len(values):
                return None
            if not 1 <= len(dates) <= MAX_ROWS or any(len(row) != len(terms) for row in values):
                return None
            index = pandas.DatetimeIndex(pandas.to_datetime(dates))
            if item.get("freq"):
                index = pandas.DatetimeIndex(index, freq=item["freq"])
            index.name = "time [UTC]" if item["index_utc_name"] else None
            frame = pandas.DataFrame(values, columns=list(terms), index=index, dtype="float64")
            partial = item["partial"]
            if partial is not None:
                if len(partial) != len(frame):
                    return None
                frame["isPartial"] = [bool(value) for value in partial]
            return frame
        except (KeyError, TypeError, ValueError, OverflowError):
            return None

    def get_series(self, key: tuple[Any, ...]) -> pandas.DataFrame | None:
        digest = self._digest(key)
        with self._connection() as connection:
            result = connection.execute(
                "SELECT payload, expires_at FROM series WHERE key=?",
                (digest,),
            ).fetchone()
        if result is None or result[1] <= self._clock():
            return None
        return self._deserialize(result[0], tuple(key[0]))

    def claim_series_fill(self, key: tuple[Any, ...]) -> str | None:
        """Claim a bounded per-query lease; allow recovery after a crashed worker."""
        digest = self._digest(key)
        token = secrets.token_hex(16)
        now = self._clock()
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM inflight WHERE expires_at <= ?", (now,))
            inserted = connection.execute(
                "INSERT OR IGNORE INTO inflight (key, owner, expires_at) VALUES (?, ?, ?)",
                (digest, token, now + 90),
            ).rowcount
            connection.commit()
        return token if inserted else None

    def release_series_fill(self, key: tuple[Any, ...], owner: str) -> None:
        """Release only our own lease, never a replacement created after expiry."""
        with self._connection() as connection:
            connection.execute(
                "DELETE FROM inflight WHERE key=? AND owner=?",
                (self._digest(key), owner),
            )

    def put_series(self, key: tuple[Any, ...], frame: pandas.DataFrame) -> bool:
        encoded = self._serialize(frame, tuple(key[0]))
        if encoded is None:
            return False
        now = self._clock()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT OR REPLACE INTO series (key, expires_at, touched_at, payload) VALUES (?, ?, ?, ?)",
                (self._digest(key), now + self._lifetime(key), now, encoded),
            )
            connection.execute("DELETE FROM series WHERE expires_at <= ?", (now,))
            connection.execute(
                "DELETE FROM series WHERE key NOT IN "
                "(SELECT key FROM series ORDER BY touched_at DESC LIMIT ?)",
                (MAX_CACHE_ENTRIES,),
            )
            connection.commit()
        return True


@lru_cache(maxsize=4)
def _configured_state(raw_directory: str) -> SharedTrendsState | None:
    try:
        return SharedTrendsState(raw_directory)
    except (OSError, ValueError, sqlite3.DatabaseError):
        logger.warning("Shared Trends state unavailable; using process-local safeguards")
        return None


def get_shared_state() -> SharedTrendsState | None:
    """Load an opt-in state directory without persisting or logging its value."""
    directory = os.environ.get("TRENDPULSE_SHARED_STATE_DIR", "").strip()
    return _configured_state(directory) if directory else None
