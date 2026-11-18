"""Offline checks for the isolated intelligence CLI/MCP entry points."""

import json

from click.testing import CliRunner
from fastmcp import Client

from mcp_trendpulse.cli import cli
from mcp_trendpulse.intelligence_mcp import intel_mcp
from mcp_trendpulse.server import mcp as community_mcp


def test_intel_cli_lists_all_waves_and_dry_runs():
    runner = CliRunner()
    sources = runner.invoke(cli, ["intelligence", "sources"])
    assert sources.exit_code == 0, sources.output
    registered = json.loads(sources.output)
    assert {item["wave"] for item in registered} == {1, 2, 3}
    result = runner.invoke(cli, ["intelligence", "query", "--source", "gdelt",
                                 "--keyword", "consumer spending"])
    assert result.exit_code == 0, result.output
    parsed = json.loads(result.output)
    assert parsed["network_performed"] is False
    assert parsed["status"] == "planned"


def test_intel_cli_offline_ats_file(tmp_path):
    payload = {"jobs": [{"id": "123", "title": "Operations Lead",
                          "content": "Reduce manual data entry and maintain audit compliance."}]}
    candidate = tmp_path / "jobs.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")
    result = CliRunner().invoke(cli, [
        "intelligence", "jobs-analyze", "--source", "greenhouse",
        "--company", "example", "--input-json", str(candidate)])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["postings_received"] == 1
    assert any(item["category"] == "manual_work" for item in report["pain_hypotheses"])


async def test_intel_mcp_is_separate_and_readonly():
    async with Client(intel_mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}
        assert len(tools) == 4
        assert set(tools) == {
            "intelligence_source_catalog", "intelligence_plan",
            "intelligence_collect", "intelligence_analyze_job_postings"
        }
        for tool in tools.values():
            assert tool.annotations.readOnlyHint is True
            assert tool.annotations.destructiveHint is False
        response = await client.call_tool("intelligence_plan", {
            "source": "gleif", "keyword": "Example AG"})
        assert response.structured_content["network_performed"] is False


async def test_existing_community_surface_is_not_expanded():
    async with Client(community_mcp) as client:
        names = {tool.name for tool in await client.list_tools()}
    assert "intelligence_collect" not in names
    assert len(names) == 16
