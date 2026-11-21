"""Guarded FastMCP localhost transport: no broad HTTP deployment defaults."""

from __future__ import annotations

import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import pytest

from mcp_trendpulse.mjau_v3.http_security import run_guarded_loopback_http


class RecordingMcp:
    def __init__(self):
        self.settings = None

    def run(self, **kwargs):
        self.settings = kwargs


@pytest.mark.parametrize("port", [False, True, -1, 0, 80, 65536, "8080", None])
def test_rejects_untrusted_or_privileged_local_port(port):
    server = RecordingMcp()
    with pytest.raises(ValueError, match="localhost"):
        run_guarded_loopback_http(server, port=port)
    assert server.settings is None


def test_strict_loopback_origin_and_host_are_not_caller_overridable():
    server = RecordingMcp()
    run_guarded_loopback_http(server, port=8131)
    assert server.settings == {
        "transport": "http",
        "host": "127.0.0.1",
        "port": 8131,
        "path": "/mcp",
        "show_banner": False,
        "host_origin_protection": True,
        "allowed_hosts": ["127.0.0.1", "localhost"],
        "allowed_origins": ["http://127.0.0.1", "http://localhost"],
    }


@pytest.mark.integration
def test_real_local_http_blocks_dns_rebinding_and_accepts_local_client():
    """Execute an isolated FastMCP 3.4 process; never touch shared services."""
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as bind:
        bind.bind(("127.0.0.1", 0))
        port = bind.getsockname()[1]
    program = (
        "from mcp_trendpulse.intelligence_mcp import intel_mcp;"
        "from mcp_trendpulse.mjau_v3.http_security import "
        "run_guarded_loopback_http;"
        f"run_guarded_loopback_http(intel_mcp,port={port})"
    )
    env = dict(os.environ, PYTHONPATH=str(root / "src"))
    process = subprocess.Popen(
        [sys.executable, "-u", "-c", program],
        cwd=root,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 40
        ready = False
        while time.monotonic() < deadline and process.poll() is None:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.4):
                    ready = True
                    break
            except OSError:
                time.sleep(0.25)
        assert ready, "Local guarded test server did not start"
        request = json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25", "capabilities": {},
                "clientInfo": {"name": "b08-local-test", "version": "1"},
            },
        })
        for host, origin, expected in [
            (f"127.0.0.1:{port}", None, 200),
            ("evil.example.com", None, 421),
            (f"127.0.0.1:{port}", "http://evil.example.com", 403),
            ("evil.example.com", "http://evil.example.com", 421),
        ]:
            headers = {
                "Host": host, "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": "2025-11-25",
            }
            if origin:
                headers["Origin"] = origin
            client = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            try:
                client.request("POST", "/mcp", request, headers)
                response = client.getresponse()
                assert response.status == expected
                response.read()
            finally:
                client.close()
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=6)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=6)
        assert process.poll() is not None
