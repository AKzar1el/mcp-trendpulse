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
    result = runner.invoke(cli, ["intelligence", "query", "--source", "gdelt_latest",
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
        assert len(tools) == 9
        assert set(tools) == {
            "intelligence_source_catalog", "intelligence_plan",
            "intelligence_collect", "intelligence_analyze_job_postings",
            "intelligence_provider_settings", "intelligence_provider_setup",
            "intelligence_opportunity_lanes", "intelligence_evaluate_opportunities",
            "intelligence_walk_forward_backtest"
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



def test_settings_cli_safe_and_separate(monkeypatch):
    monkeypatch.setenv("TRENDPULSE_INTEL_OPENALEX_KEY", "SECRET_NEVER_OUTPUT_123")
    runner = CliRunner()
    result = runner.invoke(cli, ["intelligence", "settings", "status"])
    assert result.exit_code == 0, result.output
    assert "SECRET_NEVER_OUTPUT_123" not in result.output
    settings = json.loads(result.output)
    assert any(row["provider"] == "openalex" and
               row["ready_for_live_auth_test"] for row in settings)
    guidance = runner.invoke(cli, ["intelligence", "settings", "guide", "openalex"])
    assert guidance.exit_code == 0, guidance.output
    assert "SECRET_NEVER_OUTPUT_123" not in guidance.output
    assert "settings set-key openalex" in guidance.output



def test_secret_entry_cli_keeps_values_out_of_echo(monkeypatch):
    from mcp_trendpulse import intelligence_settings as settings

    received = {}
    monkeypatch.setattr(settings, "_supports_native_store", lambda: True)
    monkeypatch.setattr(settings, "save_provider_credentials",
                        lambda provider, values: received.update(values))
    secret = "CLI_HIDDEN_TEST_KEY_999"
    result = CliRunner().invoke(cli, [
        "intelligence", "settings", "set-key", "openalex"
    ], input=secret + "\n")
    assert result.exit_code == 0, result.output
    assert received["TRENDPULSE_INTEL_OPENALEX_KEY"] == secret
    assert secret not in result.output



def test_new_offline_opportunity_cli_and_backtest(tmp_path):
    runner = CliRunner()
    lanes = runner.invoke(cli, ["intelligence", "opportunities", "lanes"])
    assert lanes.exit_code == 0, lanes.output
    assert len(json.loads(lanes.output)) == 12

    payload = {
        "as_of": "2026-11-18",
        "candidates": [{
            "id": "repair-bottleneck", "title": "Reliability incident triage",
            "lane": "developer_reliability", "geography": "US",
            "workflow": "incident_triage", "buyer": "IT teams",
        }],
        "evidence": [],
    }
    path = tmp_path / "intelligence.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = runner.invoke(cli, [
        "intelligence", "opportunities", "evaluate", "--input-json", str(path),
    ])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["results"][0]["status"] == "insufficient"
    assert data["not_a_winning_business_forecast"]

    labels = tmp_path / "labels.json"
    labels.write_text("[]", encoding="utf-8")
    result = runner.invoke(cli, [
        "intelligence", "opportunities", "backtest", "--input-json", str(labels),
    ])
    assert result.exit_code != 0
