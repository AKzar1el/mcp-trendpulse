"""Opt-in full 37-tool MCP localhost contract and safe rollback check.

Starts a single explicitly owned, guarded localhost server. Never contacts
external providers, modifies production source registration or leaves daemons.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastmcp import Client
import pytest


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def _initialize_status(endpoint: str, extra: dict[str, str] | None = None) -> int:
    body = json.dumps({
        "jsonrpc": "2.0", "id": 17, "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "trendpulse-local-qa", "version": "1"},
        },
    }).encode("utf-8")
    request = Request(
        endpoint, data=body, method="POST", headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Mcp-Protocol-Version": "2025-11-25",
            **(extra or {}),
        },
    )
    try:
        with urlopen(request, timeout=3) as response:
            response.read(4096)
            return response.status
    except HTTPError as exc:
        exc.read(4096)
        return exc.code


@pytest.mark.integration
def test_unified_37_tool_guarded_http_stops_without_production_side_effects(tmp_path):
    root = Path(__file__).resolve().parents[1]
    port = _free_local_port()
    endpoint = f"http://127.0.0.1:{port}/mcp"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root / "src")
    env["TRENDPULSE_INTEL_CACHE_DIR"] = str(tmp_path / "isolated_budget")
    cmd = (
        "from mcp_trendpulse.mjau_v3.unified_mcp import unified_mcp;"
        "from mcp_trendpulse.mjau_v3.http_security import run_guarded_loopback_http;"
        f"run_guarded_loopback_http(unified_mcp, port={port})"
    )
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    stderr_file = tmp_path / "unified-stderr.log"
    with stderr_file.open("wb") as err:
        server = subprocess.Popen(
            [sys.executable, "-c", cmd],
            cwd=root, env=env, stdout=subprocess.DEVNULL,
            stderr=err, stdin=subprocess.DEVNULL,
            creationflags=flags,
        )
        try:
            # A cold Windows server can take longer than a ready HTTP call.
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if server.poll() is not None:
                    raise AssertionError(
                        f"Guarded unified server exited: {server.returncode}, "
                        f"stderr={stderr_file.read_text('utf-8', errors='replace')[-800:]}"
                    )
                try:
                    if _initialize_status(endpoint) == 200:
                        break
                except (URLError, TimeoutError, OSError):
                    pass
                time.sleep(0.25)
            else:
                raise AssertionError("Guarded unified MCP not ready in 90s")

            assert _initialize_status(
                endpoint, {"Host": "evil.example.com"}) == 421
            assert _initialize_status(
                endpoint, {"Origin": "http://evil.example.com"}) == 403
            assert _initialize_status(endpoint) == 200

            async def exercise() -> None:
                async with Client(endpoint, timeout=60) as client:
                    tools = await client.list_tools()
                    names = {t.name for t in tools}
                    assert len(names) == len(tools) == 37
                    assert {
                        "get_news_by_keyword",
                        "intelligence_source_catalog",
                        "mjau_v3_wikidata_names",
                        "mjau_v3_osv_advisory_ids",
                    }.issubset(names)
                    for tool, args in (
                        ("intelligence_source_catalog", {"wave": 1}),
                        ("mjau_v3_wikidata_names", {
                            "qids": ["Q95", "Q312"],
                            "languages": ["en"], "execute": False,
                        }),
                        ("mjau_v3_osv_advisory_ids", {
                            "ecosystem": "npm", "package": "minimist",
                            "version": "0.0.8", "execute": False,
                        }),
                    ):
                        response = await client.call_tool(tool, args)
                        assert not response.is_error
                        if tool.startswith("mjau_v3_"):
                            assert response.structured_content["network_performed"] is False
                            assert response.structured_content["status"] == "planned"
                    for tool in ("get_news_by_keyword", "mjau_v3_osv_advisory_ids"):
                        error = await client.call_tool(
                            tool, {"unexpected_key": True},
                            raise_on_error=False,
                        )
                        assert error.is_error
                    assert len(await client.list_tools()) == 37

            asyncio.run(exercise())
            assert not (tmp_path / "isolated_budget").exists()
        finally:
            # Terminate exactly the local process spawned by this test.
            if server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)
            assert server.poll() is not None

    # Process shims and Windows socket teardown can lag a few hundred ms.
    # Do not call that lag a leak; do not terminate unrelated Python processes.
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.6)
            port_is_closed = sock.connect_ex(("127.0.0.1", port)) != 0
        if port_is_closed:
            break
        time.sleep(0.25)
    assert port_is_closed, "Test-owned listener is still reachable after shutdown"
