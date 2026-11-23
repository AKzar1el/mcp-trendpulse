"""Regression: V3 cache inspection closes its SQLite read connection on Windows."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_trendpulse.intelligence_core import BudgetCache
from mcp_trendpulse.mjau_v3 import budgeted_sources as api

FIXTURE = Path(__file__).parent / "fixtures" / "mjau_v3" / "wikidata_q42_q64_q30_20261121.json"


@pytest.mark.parametrize("corrupt_cache", [False, True])
def test_v3_cache_lookup_closes_read_connection(tmp_path, monkeypatch, corrupt_cache):
    cache = BudgetCache(tmp_path)
    original_payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    with patch.object(api, "_request_json", return_value=original_payload):
        initial = api.wikidata_identity(
            ["Q42", "Q64", "Q30"], ["en", "de", "fr", "es", "sl", "it"],
            execute=True, cache=cache,
        )
    assert initial["status"] == "source_entities_observed"
    assert initial["network_performed"] is True

    if corrupt_cache:
        with closing(cache._connect()) as conn, conn:
            conn.execute("UPDATE cache SET body=? WHERE id IN (SELECT id FROM cache LIMIT 1)",
                         ('{"status":"tampered","source":"wikidata_action_api"}',))

    seen: list[sqlite3.Connection] = []
    original_connect = cache._connect

    def tracked_connect():
        conn = original_connect()
        seen.append(conn)
        return conn

    monkeypatch.setattr(cache, "_connect", tracked_connect)
    try:
        result = api.wikidata_identity(
            ["Q42", "Q64", "Q30"], ["en", "de", "fr", "es", "sl", "it"],
            execute=True, cache=cache,
        )
        assert seen, "V3 cache read must open one SQLite connection"
        assert result["status"] == (
            "source_unavailable" if corrupt_cache else "source_entities_observed"
        )
        if corrupt_cache:
            assert result["reason"] == "local_cache_integrity_failure"
            assert result["network_performed"] is False
        else:
            assert result["cache_hit"] is True
            assert result["network_performed"] is False
        for conn in seen:
            with pytest.raises(sqlite3.ProgrammingError, match="closed"):
                conn.execute("SELECT 1")
    finally:
        # Avoid test-created leaked handles after a red-stage failure.
        for conn in seen:
            try:
                conn.close()
            except sqlite3.ProgrammingError:
                pass
