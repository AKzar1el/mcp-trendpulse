"""Measured old/new standard TrendPulse MCP offline A/B baseline.

Compares the original preserved installed MCP runtime against the currently
merged repository's standard 16 tools. Same source-free Finance category
query and direct MCP SDK transport; this measures latency and answer
consistency only, not online trend reliability or user-time savings.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent
OLD_PYTHON = (
    Path.home() / "AppData" / "Roaming" / "TrendPulseDogfood" /
    "main-runtime-0.2.31" / ".venv" / "Scripts" / "python.exe"
)


def _latency_stats(values):
    ordered = sorted(values)
    return {"n": len(ordered),
            "p50_ms": round(statistics.median(ordered), 2),
            "p95_ms": round(ordered[min(len(ordered) - 1, int(0.95 * (len(ordered) - 1)))], 2),
            "min_ms": round(ordered[0], 2), "max_ms": round(ordered[-1], 2)}


async def _measure(label, python, pythonpath, n):
    params = StdioServerParameters(
        command=str(python),
        args=["-m", "mcp_trendpulse"],
        env={"PYTHONPATH": str(pythonpath)},
        cwd=str(ROOT) if label == "latest" else str(OLD_PYTHON.parents[2]),
    )
    started = time.perf_counter()
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(
            reader, writer, read_timeout_seconds=timedelta(seconds=150)
        ) as session:
            handshake = await session.initialize()
            tools = (await session.list_tools()).tools
            assert len(tools) == 16, f"{label}: {len(tools)} standard tools"
            cold_ms = round((time.perf_counter() - started) * 1000, 2)
            results = []
            latencies = []
            for _ in range(n):
                before = time.perf_counter()
                call = await session.call_tool(
                    "get_categories", {"query": "finance", "limit": 3},
                    read_timeout_seconds=timedelta(seconds=25),
                )
                assert not call.isError
                body = call.structuredContent
                if body is None:
                    body = json.loads(next(c.text for c in call.content if c.type == "text"))
                if isinstance(body, dict) and set(body) == {"result"}:
                    body = body["result"]
                assert isinstance(body, list), type(body).__name__
                assert any(str(x.get("name", "")).lower() == "finance" and x.get("id") == 7 for x in body)
                results.append(sorted((str(x["name"]), int(x["id"])) for x in body))
                latencies.append((time.perf_counter() - before) * 1000)
            assert all(r == results[0] for r in results)
            return {"label": label, "server": handshake.serverInfo.name,
                    "tools": len(tools), "cold_initialize_and_discover_ms": cold_ms,
                    "category_ids": results[0], "successes": n,
                    "latency": _latency_stats(latencies)}


async def main_task(repeats):
    if not OLD_PYTHON.is_file():
        raise FileNotFoundError("Original 0.2.31 saved runtime unavailable")
    old = await _measure("preserved_old", OLD_PYTHON, "", repeats)
    latest = await _measure("latest", Path(sys.executable), ROOT / "src", repeats)
    return {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "transport": "independent_child_process_mcp_sdk",
            "free_provider_requests": 0,
            "repeats_per_runtime": repeats,
            "same_answer": old["category_ids"] == latest["category_ids"],
            "answers": [old, latest],
            "limitations": (
                "Same source-free category lookup, not an online search coverage "
                "or human productivity comparison. Cold startup varies with CPU/IO."
            )}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--repeats", type=int, default=6)
    args = parser.parse_args()
    if not 2 <= args.repeats <= 20:
        raise SystemExit("repeats must be between 2 and 20")
    try:
        report = asyncio.run(main_task(args.repeats))
    except Exception as exc:
        print(json.dumps({"status": "failed", "type": type(exc).__name__,
                          "reason": str(exc)[:180]}), file=sys.stderr)
        return 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"status": "passed", "same_answer": report["same_answer"],
                      "old": report["answers"][0]["latency"],
                      "latest": report["answers"][1]["latency"],
                      "provider_requests": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
