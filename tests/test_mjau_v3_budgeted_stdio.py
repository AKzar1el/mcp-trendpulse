"""Real subprocess stdio MCP compatibility for optional two-source module.

No execute=True requests: not allowed to change provider budgets during CI.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
import pytest


@pytest.mark.integration
def test_exact_optional_module_starts_real_stdio_mcp_without_network_or_cache(tmp_path):
    root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "PYTHONPATH": str(root / "src"),
        "TRENDPULSE_INTEL_CACHE_DIR": str(tmp_path / "must-not-be-created"),
    }
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "mcp_trendpulse.mjau_v3.mcp"],
        env=env,
        cwd=str(root),
        keep_alive=False,
        log_file=tmp_path / "stdio-child-stderr.log",
    )

    async def verify():
        # Cold Windows imports on the shared 8GB workstation can exceed 30s;
        # a generous bounded initialization limit avoids misdiagnosing a
        # startup-latency problem as protocol failure.
        async with Client(transport, timeout=90, init_timeout=90) as client:
            names = sorted(x.name for x in await client.list_tools())
            assert names == [
                "mjau_v3_osv_advisory_ids",
                "mjau_v3_wikidata_names",
            ]
            plan_wikidata = await client.call_tool(
                "mjau_v3_wikidata_names", {
                    "qids": ["Q64"], "languages": ["en"], "name": "Berlin",
                },
            )
            assert not plan_wikidata.is_error
            w = plan_wikidata.structured_content
            assert w["status"] == "planned"
            assert w["source"] == "wikidata_action_api"
            assert not w["network_performed"]
            assert w["daily_request_cap"] == 8

            plan_osv = await client.call_tool(
                "mjau_v3_osv_advisory_ids", {
                    "ecosystem": "npm", "package": "lodash",
                    "version": "4.17.11",
                },
            )
            assert not plan_osv.is_error
            o = plan_osv.structured_content
            assert o["status"] == "planned"
            assert o["source"] == "osv_public_api"
            assert o["daily_request_cap"] == 10
            assert o["max_request_count"] == 1
            assert not o["network_performed"]

            bad = await client.call_tool(
                "mjau_v3_osv_advisory_ids", {
                    "ecosystem": "wrong_ecosystem", "package": "lodash",
                    "version": "4.17.11",
                }, raise_on_error=False,
            )
            assert bad.is_error

    asyncio.run(verify())
    assert not (tmp_path / "must-not-be-created").exists()
