"""Release-only smoke of the installed wheel's CLI and MCP stdio transport.

Run this file with the isolated wheel-smoke virtualenv's Python, not the
checkout's development environment. No live provider call is performed.
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import subprocess
import sys
import tomllib
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


NEWS_TOOLS = {
    "get_news_by_keyword",
    "get_news_by_location",
    "get_news_by_topic",
    "get_top_news",
    "get_news_by_site",
}
OTHER_TOOLS = {"get_trending_terms", "get_top_trends", "get_growth", "get_categories"}


def _entrypoint(name: str) -> str:
    suffix = ".exe" if sys.platform == "win32" else ""
    executable = Path(sys.executable).with_name(name + suffix)
    if not executable.is_file():
        raise AssertionError(f"Installed console entrypoint missing: {executable}")
    return str(executable)


async def _check_stdio() -> int:
    server = StdioServerParameters(command=_entrypoint("mcp-trendpulse"), args=[])
    async with stdio_client(server) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            initialized = await asyncio.wait_for(session.initialize(), timeout=20)
            if initialized.serverInfo.name != "mcp-trendpulse":
                raise AssertionError(f"Unexpected MCP server identity: {initialized.serverInfo.name}")

            listed = await asyncio.wait_for(session.list_tools(), timeout=15)
            by_name = {tool.name: tool for tool in listed.tools}
            missing = (NEWS_TOOLS | OTHER_TOOLS) - by_name.keys()
            if missing:
                raise AssertionError(f"Installed MCP tools missing: {sorted(missing)}")
            if len(by_name) < 16:
                raise AssertionError(f"Expected at least 16 MCP tools, got {len(by_name)}")

            for name in NEWS_TOOLS:
                args = by_name[name].inputSchema.get("properties", {})
                if "headlines_only" not in args:
                    raise AssertionError(f"Installed {name} lacks headlines_only argument")
            for name in ("query", "limit", "offset"):
                args = by_name["get_categories"].inputSchema.get("properties", {})
                if name not in args:
                    raise AssertionError(f"Installed get_categories lacks {name} argument")
            return len(by_name)


def main() -> None:
    expected = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]["version"]
    installed = importlib.metadata.version("mcp-trendpulse")
    if installed != expected:
        raise AssertionError(
            f"Wheel metadata version {installed} does not match source {expected}"
        )

    cli = subprocess.run(
        [_entrypoint("mcp-trendpulse-cli"), "--help"],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if cli.returncode != 0 or not cli.stdout.strip():
        raise AssertionError(
            f"Installed CLI --help failed (code={cli.returncode}): "
            f"{cli.stderr[:300]}"
        )

    count = asyncio.run(asyncio.wait_for(_check_stdio(), timeout=45))
    print(f"PASS: installed wheel {installed}, CLI entrypoint, MCP stdio, {count} tools")


if __name__ == "__main__":
    main()
