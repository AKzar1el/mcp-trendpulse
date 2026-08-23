import json
from importlib.metadata import version
from pathlib import Path

from fastmcp import Client

from mcp_trendpulse import server


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_FILES = ("manifest.json", "server.json")


def _load_json(filename: str) -> dict:
    with (PROJECT_ROOT / filename).open(encoding="utf-8") as handle:
        return json.load(handle)


async def test_registry_manifests_match_live_tool_names():
    async with Client(server.mcp) as client:
        live_tools = await client.list_tools()

    live_names = {tool.name for tool in live_tools}
    assert len(live_names) == 16

    for filename in REGISTRY_FILES:
        manifest = _load_json(filename)
        declared_names = {tool["name"] for tool in manifest["tools"]}
        assert declared_names == live_names, f"{filename} tool registry is stale"


def test_registry_manifest_versions_match_package_version():
    package_version = version("mcp-trendpulse")

    for filename in REGISTRY_FILES:
        manifest = _load_json(filename)
        assert manifest["version"] == package_version, f"{filename} version is stale"
