"""A11 preregistered optional MCP tool-discovery experiment.

The real benchmark runs only via the explicit --benchmark entry point.
Ordinary pytest verifies the frozen prompt contract without changing any
global server, connecting to providers, or adding an MCP tool registration.
"""
from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "mjau_v3"
    / "a11_preregistered_tool_tasks_20261121.json"
)
KNOWN = {
    "intelligence_source_catalog",
    "intelligence_plan",
    "intelligence_collect",
    "intelligence_analyze_job_postings",
    "intelligence_provider_settings",
    "intelligence_provider_setup",
    "intelligence_observe_source_snapshots",
    "intelligence_discover_current",
    "intelligence_hunt_current",
    "intelligence_opportunity_lanes",
    "intelligence_evaluate_opportunities",
    "intelligence_walk_forward_backtest",
}


def _cases() -> list[dict[str, Any]]:
    artifact = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert artifact["benchmark"] == "MJAU-v3-A11"
    return artifact["cases"]


def test_preregistered_task_contract() -> None:
    cases = _cases()
    assert len(cases) == 28
    assert len({row["id"] for row in cases}) == 28
    assert len({row["query"] for row in cases}) == 28
    positive = [row for row in cases if row["expected_tool"] is not None]
    negative = [row for row in cases if row["expected_tool"] is None]
    assert len(positive) == 24 and len(negative) == 4
    assert {row["expected_tool"] for row in positive} == KNOWN
    assert all(sum(row["expected_tool"] == name for row in positive) == 2 for name in KNOWN)
    assert all(20 <= len(row["query"]) <= 200 for row in cases)


def _bytes(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


async def _run() -> dict[str, Any]:
    # Confine global FastMCP modification to this short-lived test process only.
    from fastmcp import Client
    from fastmcp.server.transforms.search import BM25SearchTransform
    from mcp_trendpulse.intelligence_mcp import intel_mcp

    cases = _cases()
    async with Client(intel_mcp) as baseline:
        original = await baseline.list_tools()
        original_names = {item.name for item in original}
        assert original_names == KNOWN
        full_bytes = _bytes([item.model_dump(mode="json") for item in original])
        direct_ms = []
        for _ in range(5):
            start = time.perf_counter()
            response = await baseline.call_tool("intelligence_source_catalog", {})
            direct_ms.append((time.perf_counter() - start) * 1000)
            assert not response.is_error

    intel_mcp.add_transform(BM25SearchTransform(max_results=5))
    async with Client(intel_mcp) as transformed:
        exposed = await transformed.list_tools()
        exposed_names = {item.name for item in exposed}
        assert exposed_names == {"search_tools", "call_tool"}
        proxy_bytes = _bytes([item.model_dump(mode="json") for item in exposed])

        records = []
        for task in cases:
            start = time.perf_counter()
            response = await transformed.call_tool("search_tools", {"query": task["query"]})
            milliseconds = (time.perf_counter() - start) * 1000
            assert not response.is_error
            rows = response.data
            if not isinstance(rows, list):
                raise AssertionError("Expected structured search-tool list")
            names = [item["name"] for item in rows]
            if len(names) != len(set(names)) or not set(names).issubset(KNOWN):
                raise AssertionError("Search result contained an unknown or duplicate tool")
            expected = task["expected_tool"]
            records.append({
                "id": task["id"],
                "expected": expected,
                "first": names[0] if names else None,
                "top5": expected in names if expected is not None else None,
                "ms": round(milliseconds, 3),
                "search_bytes": _bytes(rows),
            })

        proxy_ms = []
        safe_proxy_ok = True
        for _ in range(5):
            start = time.perf_counter()
            try:
                result = await transformed.call_tool(
                    "call_tool", {"name": "intelligence_source_catalog", "arguments": {}}
                )
                safe_proxy_ok = safe_proxy_ok and not result.is_error
            except Exception:
                safe_proxy_ok = False
            proxy_ms.append((time.perf_counter() - start) * 1000)

        async def rejected(name: str, arguments: dict[str, Any]) -> bool:
            try:
                result = await transformed.call_tool(
                    "call_tool", {"name": name, "arguments": arguments}
                )
                return bool(result.is_error)
            except Exception:
                return True

        rejects_unknown = await rejected("delete_everything", {})
        rejects_bad_plan = await rejected("intelligence_plan", {"source": "unapproved-source"})

    positive = [row for row in records if row["expected"] is not None]
    negatives = [row for row in records if row["expected"] is None]
    positive_hit1 = sum(row["first"] == row["expected"] for row in positive)
    positive_top5 = sum(row["top5"] is True for row in positive)
    negative_abstain = sum(row["first"] is None for row in negatives)
    times = [row["ms"] for row in records]
    median_search_bytes = int(statistics.median(row["search_bytes"] for row in positive))
    estimate_two_search_bytes = proxy_bytes + 2 * median_search_bytes
    thresholds = {
        "positive_first_at_least_22_of_24": positive_hit1 >= 22,
        "negative_abstain_at_least_3_of_4": negative_abstain >= 3,
        "two_search_context_smaller_than_direct_catalog": estimate_two_search_bytes < full_bytes,
        "search_p95_under_125_ms": _percentile(times, 0.95) < 125,
        "proxy_guards_and_safe_call": safe_proxy_ok and rejects_unknown and rejects_bad_plan,
    }
    return {
        "benchmark": "A11 FastMCP 3.4.11 in-memory lexical pilot",
        "not_a_model_agent_study": True,
        "pinned_v1_commit": "b88b0a974b5dcdb480e4fd8c4da5f7bbca68e98e",
        "queries": len(records),
        "positive_hit1": positive_hit1,
        "positive_hit5": positive_top5,
        "positive_total": len(positive),
        "negative_no_tool": negative_abstain,
        "negative_total": len(negatives),
        "baseline_tool_count": len(original),
        "transformed_tool_count": len(exposed),
        "baseline_catalog_bytes": full_bytes,
        "transformed_catalog_bytes": proxy_bytes,
        "median_search_result_bytes": median_search_bytes,
        "two_search_total_bytes_estimate": estimate_two_search_bytes,
        "search_p50_ms": round(_percentile(times, 0.5), 3),
        "search_p95_ms": round(_percentile(times, 0.95), 3),
        "direct_source_catalog_p50_ms": round(_percentile(direct_ms, 0.5), 3),
        "via_proxy_source_catalog_p50_ms": round(_percentile(proxy_ms, 0.5), 3),
        "safe_proxy_succeeded": safe_proxy_ok,
        "proxy_rejected_unknown_tool": rejects_unknown,
        "proxy_rejected_bad_source": rejects_bad_plan,
        "thresholds": thresholds,
        "thresholds_all_passed": all(thresholds.values()),
        "misranked_positive": [
            {"id": r["id"], "expected": r["expected"], "first": r["first"]}
            for r in positive if r["expected"] != r["first"]
        ],
        "false_positive_negatives": [
            {"id": r["id"], "first": r["first"]}
            for r in negatives if r["first"] is not None
        ],
        "call_count_note": "BM25 adds one search request before normal tool invocation",
    }


if __name__ == "__main__":
    if sys.argv[1:] != ["--benchmark"]:
        raise SystemExit("Use --benchmark for the explicit read-only in-memory trial")
    report = asyncio.run(_run())
    print("A11_BENCHMARK_JSON=" + json.dumps(report, sort_keys=True), flush=True)
