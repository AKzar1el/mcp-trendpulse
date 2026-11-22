"""Independent full-project MCP-surface acceptance (no paid or live source calls).

Tests actual separate subprocess JSON-RPC for the standard, opt-in intelligence,
hosted and unreleased V3 entrypoints. Output is deliberately small and safe.
Run from repo root: python scripts/full_project_surface_acceptance.py --report PATH
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import timedelta, timezone, datetime
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent
PROBES = (
    ("standard", ["-m", "mcp_trendpulse"], 16),
    ("intelligence_v2", ["-m", "mcp_trendpulse.intelligence_mcp"], 17),
    ("hosted", ["-c", "from mcp_trendpulse.hosted import hosted_mcp; hosted_mcp.run(transport='stdio')"], 6),
    ("v3_isolated_unreleased", ["-m", "mcp_trendpulse.mjau_v3.mcp"], 2),
)


def _body(result):
    if result.isError:
        raise AssertionError("MCP tool returned isError")
    body = result.structuredContent
    if body is None:
        text = next((c.text for c in result.content if getattr(c, "type", "") == "text"), None)
        if text is None:
            raise AssertionError("MCP tool did not return text or structured content")
        body = json.loads(text)
    if isinstance(body, dict) and set(body) == {"result"}:
        body = body["result"]
    return body


async def _call(session, name, args):
    start = time.perf_counter()
    result = _body(await session.call_tool(
        name, args, read_timeout_seconds=timedelta(seconds=32)
    ))
    return result, round((time.perf_counter() - start) * 1000, 2)


async def _one(label, args, expected):
    params = StdioServerParameters(
        command=sys.executable, args=args, env={"PYTHONPATH": str(ROOT / "src")}
    )
    start = time.perf_counter()
    async with stdio_client(params) as (reader, writer):
        # Windows cold-start with large optional FastMCP imports can exceed
        # 90 seconds under competing processes. Record the startup latency
        # separately; permit at most three minutes for an isolated smoke.
        async with ClientSession(
            reader, writer, read_timeout_seconds=timedelta(seconds=180)
        ) as session:
            handshake = await session.initialize()
            names = (await session.list_tools()).tools
            unique = {tool.name for tool in names}
            if len(names) != len(unique) or len(names) != expected:
                raise AssertionError(
                    f"{label}: tool count/uniqueness incorrect {len(names)}/{len(unique)} expected {expected}"
                )
            result = {
                "surface": label,
                "server": handshake.serverInfo.name,
                "tool_count": len(names),
                "tool_names": sorted(unique),
                "read_only_annotations_count": sum(
                    bool(tool.annotations and tool.annotations.readOnlyHint)
                    for tool in names
                ),
                "handshake_and_discovery_ms": round(
                    (time.perf_counter() - start) * 1000, 2
                ),
                "cases": [],
            }
            if label == "standard":
                if "get_categories" not in unique:
                    raise AssertionError("Standard Trends categories missing")
                data, dur = await _call(session, "get_categories", {"query": "finance", "limit": 5})
                if not isinstance(data, list) or not any(
                    "finance" in str(item.get("name", "")).lower() for item in data
                ):
                    raise AssertionError("Standard category lookup incorrect")
                result["cases"].append({"task": "offline_category_resolution", "ok": True, "ms": dur})
            if label == "intelligence_v2":
                for name, arguments in (
                    ("intelligence_hf_catalog", {"kind": "models", "limit": 2, "execute": False}),
                    ("intelligence_release_lifecycle", {"product": "nodejs", "release": "20", "execute": False}),
                    ("intelligence_dependency_graph", {"ecosystem": "npm", "package": "is-odd",
                                                      "version": "3.0.1", "execute": False}),
                ):
                    data, dur = await _call(session, name, arguments)
                    if not isinstance(data, dict) or data.get("status") != "planned":
                        raise AssertionError("V2 did not return a bounded plan")
                    if data.get("network_performed") is not False or data.get("requests_attempted") != 0:
                        raise AssertionError("V2 plan-only leaked a source call")
                    result["cases"].append({"task": name + "_zero_network", "ok": True, "ms": dur})
            if label == "v3_isolated_unreleased":
                for name, arguments in (
                    ("mjau_v3_wikidata_names", {"qids": ["Q42"], "languages": ["en"], "execute": False}),
                    ("mjau_v3_osv_advisory_ids", {"ecosystem": "PyPI", "package": "Jinja2",
                                                 "version": "2.10.1", "execute": False}),
                ):
                    data, dur = await _call(session, name, arguments)
                    if not isinstance(data, dict) or data.get("status") != "planned":
                        raise AssertionError("V3 did not return plan-only observation")
                    # V3's plan contract states the *maximum future* request
                    # count, not a V2-style requests_attempted counter.
                    if data.get("max_request_count") != 1 or data.get("network_performed") is not False:
                        raise AssertionError("V3 source call made without opt-in")
                    result["cases"].append({"task": name + "_zero_network", "ok": True, "ms": dur})
            if label == "hosted":
                prompts = await session.list_prompts()
                has_research_report = any(x.name == "source_evidence_research_report" for x in prompts.prompts)
                result["cases"].append({"task": "offline_evidence_prompt_registered",
                                        "ok": has_research_report})
                if not has_research_report:
                    raise AssertionError("Hosted offline source evidence prompt missing")
            return result


async def run(selected: str = "all"):
    results = []
    for label, args, expected in PROBES:
        if selected != "all" and label != selected:
            continue
        results.append(await _one(label, args, expected))
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "run_mode": "independent_stdios_not_production",
        "sources_attempted": 0,
        "paid_services_used": False,
        "total_tools_across_separate_surfaces": sum(x["tool_count"] for x in results),
        "total_cases": sum(len(x["cases"]) for x in results),
        "all_passed": all(y["ok"] for x in results for y in x["cases"]),
        "results": results,
        "v3_deployed_or_registered": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--surface", choices=["all"] + [label for label, _, _ in PROBES],
        default="all",
    )
    args = parser.parse_args()
    try:
        report = asyncio.run(run(args.surface))
    except Exception as e:
        def cause_types(error):
            nested = getattr(error, "exceptions", ())
            return [leaf for x in nested for leaf in cause_types(x)] if nested else [
                {"type": type(error).__name__, "detail": str(error)[:180]}
            ]

        print(json.dumps({"status": "failed", "exception": type(e).__name__,
                          "cause_types": cause_types(e),
                          "detail": str(e)[:250]}), file=sys.stderr)
        return 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"status": "passed", "total_tools": report["total_tools_across_separate_surfaces"],
                      "checks": report["total_cases"], "sources_attempted": 0,
                      "v3_deployed": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
