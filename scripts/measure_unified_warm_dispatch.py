"""Local no-provider A/B: does mounting V3 regress existing V1/V2 dispatch?

Both arms use exactly the same original V1 and V2 server objects.
Baseline mounts 34 tools; comparison is actual source-only 36-tool unified.
No network, no worker mutation; timings are warm process RPC time only.
"""
from __future__ import annotations

import asyncio
import json
import statistics
from time import perf_counter

from fastmcp import Client, FastMCP
from mcp_trendpulse.server import mcp as v1, lifespan as v1_lifespan
from mcp_trendpulse.intelligence_mcp import intel_mcp
from mcp_trendpulse.mjau_v3.unified_mcp import unified_mcp


baseline = FastMCP(name="test-only-v1-v2-34", lifespan=v1_lifespan)
baseline.mount(v1)
baseline.mount(intel_mcp)


async def exercise(server):
    times = []
    async with Client(server) as client:
        tools = await client.list_tools()
        n = len(tools)
        out = []
        for i in range(14):
            started = perf_counter()
            response = await client.call_tool(
                "intelligence_source_catalog", {"wave": 1},
            )
            times.append(round(1000*(perf_counter()-started), 3))
            assert not response.is_error
            out.append(response.structured_content)
        for i in range(7):
            err = await client.call_tool(
                "get_news_by_keyword", {"unexpected_field": "no"},
                raise_on_error=False,
            )
            assert err.is_error
        for i in range(14):
            tools2 = await client.list_tools()
            assert len(tools2) == n
        if n == 36:
            for i in range(5):
                r = await client.call_tool(
                    "mjau_v3_osv_advisory_ids", {
                        "ecosystem": "npm", "package": "minimist",
                        "version": "0.0.8", "execute": False,
                    },
                )
                assert not r.is_error
                assert r.structured_content["network_performed"] is False
        return {
            "tools": n,
            "catalog_fingerprint": json.dumps(
                out[0], sort_keys=True, ensure_ascii=True,
            ),
            "catalog_consistent": all(x == out[0] for x in out),
            "elapsed_ms": times,
            "median_warm_catalog_call_ms": statistics.median(times),
        }


async def main():
    trials = []
    for i in range(5):
        order = (
            (("baseline34", baseline), ("unified36", unified_mcp))
            if i % 2 == 0 else
            (("unified36", unified_mcp), ("baseline34", baseline))
        )
        for label, server in order:
            row = await exercise(server)
            assert row["tools"] == (34 if label == "baseline34" else 36)
            assert row["catalog_consistent"]
            trials.append((i+1, label, row))
            print("WARM_CALL_TRIAL=" + json.dumps({
                "round": i+1,
                "mode": label,
                "tool_count": row["tools"],
                "median_catalog_ms": round(row["median_warm_catalog_call_ms"], 3),
            }, sort_keys=True), flush=True)

    baselines = [r for _, label, r in trials if label == "baseline34"]
    unified = [r for _, label, r in trials if label == "unified36"]
    assert all(
        x["catalog_fingerprint"] == baselines[0]["catalog_fingerprint"]
        for x in baselines + unified
    ), "Existing V2 catalog results changed in unified app"
    a = statistics.median(r["median_warm_catalog_call_ms"] for r in baselines)
    b = statistics.median(r["median_warm_catalog_call_ms"] for r in unified)
    print("WARM_CALL_SUMMARY=" + json.dumps({
        "trials": 5,
        "baseline_tool_count": 34,
        "unified_tool_count": 36,
        "unchanged_source_catalog": True,
        "baseline_median_ms": round(a, 3),
        "unified_median_ms": round(b, 3),
        "difference_ms": round(b-a, 3),
        "provider_requests": 0,
        "human_research_productivity_proven": False,
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
