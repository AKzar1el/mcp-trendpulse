"""Real-world Hugging Face Hub multi-token search regression (2026-11-22).

The public API returned valid IDs with query terms in different positions.
No HTTP calls, provider credentials or persistent SQLite budgets in this test.
"""
from datetime import datetime, timezone

from mcp_trendpulse.mjau_v2 import hf_catalog as hf

NOW = datetime(2026, 11, 22, 4, 30, tzinfo=timezone.utc)


def _record(ident):
    return {
        "id": ident, "modelId": ident, "private": False, "gated": None,
        "trendingScore": 2, "downloads": 350, "likes": 7,
        "createdAt": "2026-11-01T00:00:00Z", "lastModified": None,
        "cardData": {"summary": "Must never leave source boundary"},
    }


def test_live_provider_multitoken_search_accepts_valid_nonadjacent_terms():
    payload = [
        _record("jinaai/jina-embeddings-v5-text-nano"),
        _record("litert-community/embeddinggemma-2-text-270m-litert-lm"),
        _record("DiffSynth-Studio/MiniMax-H3-Text-Embeddings"),
    ]
    parsed = hf._parse(payload, kind="models", limit=5,
                       search="text embedding", observed=NOW)
    assert parsed["status"] == "observed_partial"
    assert parsed["received_rows"] == 3
    assert parsed["rejected_rows"] == 0
    assert [row["repository_id"] for row in parsed["records"]] == [
        item["id"] for item in payload
    ]
    assert all("cardData" not in row for row in parsed["records"])


def test_multitoken_search_still_rejects_unrelated_and_private_rows():
    payload = [
        _record("example/text-to-image-only"),
        _record("example/audio-embedding-only"),
        dict(_record("example/text-embedding-v1"), private=True),
        _record("example/text-embedding-v2"),
    ]
    parsed = hf._parse(payload, kind="models", limit=5,
                       search="text embedding", observed=NOW)
    assert parsed["status"] == "observed_partial"
    assert parsed["received_rows"] == 4
    assert parsed["rejected_rows"] == 3
    assert [row["repository_id"] for row in parsed["records"]] == [
        "example/text-embedding-v2"
    ]
