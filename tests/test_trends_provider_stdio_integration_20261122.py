"""Real isolated stdio MCP fault injection; never calls public providers."""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
import pytest


@pytest.mark.integration
def test_live_stdio_reports_sanitized_trends_failure_and_remains_healthy(tmp_path):
    root = Path(__file__).resolve().parents[1]
    launcher = tmp_path / "broken_trends_stdio.py"
    launcher.write_text(
        'from types import SimpleNamespace\n'
        'from fastmcp import FastMCP\n'
        'from mcp_trendpulse import news\n'
        'from mcp_trendpulse.server import mcp as standard_mcp\n'
        'from mcp_trendpulse.intelligence_mcp import intel_mcp\n'
        'def broken(**kwargs):\n'
        '    raise TypeError("the JSON object must be str, bytes or bytearray, not NoneType")\n'
        'news.tr = SimpleNamespace(trending_now=broken)\n'
        'mcp = FastMCP("trendpulse-v2-fault-injection")\n'
        'mcp.mount(standard_mcp, namespace=None)\n'
        'mcp.mount(intel_mcp, namespace=None)\n'
        'mcp.run(transport="stdio")\n',
        encoding="utf-8",
    )

    async def scenario():
        transport = StdioTransport(
            command=sys.executable,
            args=[str(launcher)],
            cwd=str(root),
            env={"PYTHONPATH": str(root / "src")},
            keep_alive=False,
            log_file=tmp_path / "stdio-stderr.txt",
        )
        async with Client(transport, timeout=120, init_timeout=150) as client:
            names = {tool.name for tool in await client.list_tools()}
            assert len(names) == 33
            assert not any(name.startswith("mjau_v3_") for name in names)
            failed = await client.call_tool(
                "get_ranked_trends",
                {"geo": "US", "sort": "recent_growth_pct", "limit": 3},
                raise_on_error=False,
            )
            assert failed.is_error is True
            text = " ".join(getattr(part, "text", "") for part in failed.content)
            assert "provider_unavailable" in text
            assert "NoneType" not in text

            invalid = await client.call_tool(
                "get_ranked_trends",
                {"geo": "../../private", "limit": 3},
                raise_on_error=False,
            )
            assert invalid.is_error is True

            planned = await client.call_tool(
                "intelligence_hf_catalog",
                {"kind": "models", "search": "text embedding",
                 "limit": 3, "execute": False},
                raise_on_error=False,
            )
            assert planned.is_error is False
            assert planned.data["status"] == "planned"
            assert planned.data["network_performed"] is False

    asyncio.run(scenario())
