"""Measure source-only MJAU v3 cold Python imports without provider queries.

The combined 36-tool app preserves V1 and V2 and necessarily imports their
startup dependencies. The separate two-tool V3 app avoids them. Benchmark
these modes on the same machine rather than attributing shared import costs
to V3 or claiming setup time is end-user research productivity.

Usage:
    python scripts/measure_unified_cold_start.py --rounds 3
    python scripts/measure_unified_cold_start.py --child unified
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
from time import perf_counter


MODULES = {
    "unified": (
        "fastmcp",
        "mcp_trendpulse.server",
        "mcp_trendpulse.intelligence_mcp",
        "mcp_trendpulse.mjau_v3.mcp",
        "mcp_trendpulse.mjau_v3.unified_mcp",
    ),
    "v3-only": ("fastmcp", "mcp_trendpulse.mjau_v3.mcp"),
}


def _child(mode: str) -> None:
    phases = []
    started = perf_counter()
    for module_name in MODULES[mode]:
        before = perf_counter()
        importlib.import_module(module_name)
        phases.append({
            "module": module_name,
            "wall_ms": round((perf_counter() - before) * 1000, 2),
        })
    total = round((perf_counter() - started) * 1000, 2)
    print(json.dumps({
        "mode": mode,
        "python": sys.version.split()[0],
        "phases": phases,
        "total_import_ms": total,
        "provider_queries_executed": 0,
        "cold_process": True,
        "research_productivity_measured": False,
    }), flush=True)


def _parent(rounds: int) -> None:
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join((
        str(root / "src"),
        env.get("PYTHONPATH", ""),
    )).strip(os.pathsep)
    observations = []
    for iteration in range(rounds):
        order = ("unified", "v3-only") if iteration % 2 == 0 else (
            "v3-only", "unified",
        )
        for mode in order:
            started = perf_counter()
            proc = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()),
                 "--child", mode],
                cwd=root, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace",
                timeout=120, check=False,
            )
            wall_ms = round((perf_counter() - started) * 1000, 2)
            if proc.returncode != 0:
                raise RuntimeError(
                    f"{mode} failed ({proc.returncode}): {proc.stderr[-500:]}"
                )
            result = json.loads(proc.stdout)
            if (result["mode"] != mode
                    or result["provider_queries_executed"] != 0):
                raise RuntimeError("Unexpected child measurement receipt")
            observations.append({
                "round": iteration + 1,
                "mode": mode,
                "process_plus_import_ms": wall_ms,
                **result,
            })
            print("COLD_IMPORT_TRIAL=" + json.dumps(
                observations[-1], sort_keys=True), flush=True)

    aggregate = {}
    for mode in MODULES:
        rows = [r for r in observations if r["mode"] == mode]
        steps = {}
        for name in MODULES[mode]:
            vals = [
                phase["wall_ms"] for row in rows
                for phase in row["phases"] if phase["module"] == name
            ]
            steps[name] = round(statistics.median(vals), 2)
        vals = [r["process_plus_import_ms"] for r in rows]
        aggregate[mode] = {
            "rounds": len(rows),
            "median_process_plus_import_ms": round(statistics.median(vals), 2),
            "range_process_plus_import_ms": [min(vals), max(vals)],
            "median_module_import_ms": steps,
        }
    print("COLD_IMPORT_SUMMARY=" + json.dumps({
        "comparison_limit": (
            "Two-tool V3-only mode is not feature-equivalent to the unified "
            "36-tool mode; these are startup attribution diagnostics, not "
            "research productivity or task-result A/B measurements."
        ),
        "results": aggregate,
        "all_processes_exited": True,
        "provider_queries_executed": 0,
    }, sort_keys=True), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--child", choices=tuple(MODULES))
    options = parser.parse_args()
    if options.child:
        _child(options.child)
    else:
        if not 1 <= options.rounds <= 12:
            parser.error("rounds must be between 1 and 12")
        _parent(options.rounds)


if __name__ == "__main__":
    main()
