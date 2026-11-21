"""Test-only A04/A10 end-to-end over a real protected loopback MCP transport.

Unlike in-process Client(FastMCP), this exercises HTTP JSON-RPC + schema
serialization across a disposable child process. No production registration.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

from fastmcp import Client
import pytest


@pytest.mark.integration
def test_guarded_http_mcp_can_use_both_source_backed_tools_without_network():
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as bound:
        bound.bind(("127.0.0.1", 0))
        port = bound.getsockname()[1]
    program = (
        "from test_mjau_v3_isolated_mcp_workflow import sandbox;"
        "from mcp_trendpulse.mjau_v3.http_security import "
        "run_guarded_loopback_http;"
        f"run_guarded_loopback_http(sandbox,port={port})"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        (str(root / "src"), str(root / "tests"))
    )
    server = subprocess.Popen(
        [sys.executable, "-u", "-c", program],
        cwd=root,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        ready = False
        deadline = time.monotonic() + 50
        while time.monotonic() < deadline and server.poll() is None:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.4):
                    ready = True
                    break
            except OSError:
                time.sleep(0.25)
        assert ready, "Disposable A04/A10 HTTP MCP server did not start"

        async def exercise():
            async with Client(f"http://127.0.0.1:{port}/mcp") as client:
                catalog = await client.list_tools()
                assert sorted(x.name for x in catalog) == [
                    "test_only_osv_package_ids",
                    "test_only_wikidata_candidates",
                ]
                entity = await client.call_tool(
                    "test_only_wikidata_candidates", {
                        "name": "Berlin", "language": "en",
                    },
                )
                assert not entity.is_error
                assert entity.structured_content["candidate_qids"] == ["Q64"]
                assert entity.structured_content["source_items_incomplete"]
                assert entity.structured_content["identity_confirmed"] is False
                package = await client.call_tool(
                    "test_only_osv_package_ids", {
                        "ecosystem": "PyPI", "package": "Django",
                        "version": "2.2.0",
                    },
                )
                assert not package.is_error
                assert package.structured_content["provider_ids_in_this_page"] == 75
                assert package.structured_content["raw_advisory_redistribution_authorized"] is False

                # Wrong/version-crossed source cannot receive unrelated fixture data.
                invalid = await client.call_tool(
                    "test_only_osv_package_ids", {
                        "ecosystem": "npm", "package": "lodash",
                        "version": "4.17.11",
                    }, raise_on_error=False,
                )
                assert invalid.is_error
                assert "Django" not in str(invalid.content)
        asyncio.run(exercise())
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=7)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=7)
        assert server.poll() is not None
