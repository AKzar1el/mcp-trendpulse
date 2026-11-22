"""Measure reproducible process-local cold imports without contacting providers.

Run from repo with PYTHONPATH=src. Reports cumulative import-segment wall times,
not startup latency under production load. A separate shell stopwatch captures
interpreter process launch overhead.
"""
from __future__ import annotations

import json
import sys
import time

steps = []
prev = time.perf_counter()

import fastmcp  # noqa: E402, F401

now = time.perf_counter()
steps.append({"segment": "import fastmcp", "wall_ms": round((now - prev) * 1000, 2)})
prev = now

from mcp_trendpulse import intelligence_core  # noqa: E402, F401

now = time.perf_counter()
steps.append({"segment": "import intelligence_core", "wall_ms": round((now - prev) * 1000, 2)})
prev = now

from mcp_trendpulse import intelligence_jobs  # noqa: E402, F401

now = time.perf_counter()
steps.append({"segment": "import intelligence_jobs", "wall_ms": round((now - prev) * 1000, 2)})
prev = now

from mcp_trendpulse import intelligence_mcp  # noqa: E402, F401

now = time.perf_counter()
steps.append({"segment": "import intelligence_mcp register 17 tools", "wall_ms": round((now - prev) * 1000, 2)})

print(json.dumps({"python": sys.version.split()[0], "steps": steps,
                  "sum_segment_wall_ms": round(sum(x["wall_ms"] for x in steps), 2),
                  "providers_called": 0}))
