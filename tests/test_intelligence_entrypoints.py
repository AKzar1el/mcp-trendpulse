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
        assert len(tools) == 18
        assert set(tools) == {
            "intelligence_source_catalog", "intelligence_plan",
            "intelligence_collect", "intelligence_analyze_job_postings",
            "intelligence_provider_settings", "intelligence_provider_setup",
            "intelligence_opportunity_lanes", "intelligence_evaluate_opportunities",
            "intelligence_walk_forward_backtest", "intelligence_observe_source_snapshots",
            "intelligence_hunt_current", "intelligence_discover_current",
            "intelligence_dependency_graph", "intelligence_repository_scorecard",
            "intelligence_repository_star_history",
            "intelligence_release_lifecycle",
            "intelligence_hf_catalog", "intelligence_validate_concept",
        }
        for tool in tools.values():
            assert tool.annotations.readOnlyHint is True
            assert tool.annotations.destructiveHint is False
        response = await client.call_tool("intelligence_plan", {
            "source": "gleif", "keyword": "Example AG"})
        assert response.structured_content["network_performed"] is False


async def test_optional_discovery_mcp_propagates_bounded_source_flags_without_network():
    # Optional discovery flags extend its schema without changing community MCP.
    # The separately opt-in intelligence server also contains two V2 tools.
    async with Client(intel_mcp) as client:
        found = {tool.name: tool for tool in await client.list_tools()}
        tool = found["intelligence_discover_current"]
        for prop in (
            "measure_trends", "broad_topic_scan", "corroborate_issues",
            "cross_source_hunt",
        ):
            assert prop in tool.inputSchema["properties"]
        response = await client.call_tool("intelligence_discover_current", {
            "lookback_days": 30, "limit": 20, "execute": False,
            "measure_trends": True, "broad_topic_scan": True,
            "corroborate_issues": True, "cross_source_hunt": True,
        })
    payload = response.structured_content
    assert payload["network_performed"] is False
    assert payload["source_count"] == 3
    assert payload["request_count"] == 3
    assert payload["max_requests_with_trend_measurement"] == 29
    evidence = payload["trend_evidence"]
    assert evidence["cross_source_hunt_opted_in"] is True
    assert evidence["corroborate_issues_opted_in"] is True
    assert evidence["broad_topic_scan_opted_in"] is True
    assert evidence["max_additional_source_requests"] == 26
    assert evidence["cross_source_hunt_source_ids"] == [
        "cordis", "usaspending",
    ]


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
    assert len(json.loads(lanes.output)) == 18

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


def test_offline_observation_cli_keeps_sources_and_coverage_separate(tmp_path):
    from click.testing import CliRunner
    from mcp_trendpulse.cli import cli

    batch = {
        "topic": "battery", "as_of": "2026-11-19",
        "snapshots": [{
            "source": "openalex", "status": "observed",
            "observations": {
                "record_count": 1, "sample": [{
                    "id": "https://openalex.org/W2741809807",
                    "display_name": "Battery recycling research",
                    "publication_date": "2026-11-15",
                }],
            },
        }],
    }
    file = tmp_path / "observations.json"
    file.write_text(json.dumps(batch), encoding="utf-8")
    result = CliRunner().invoke(
        cli, ["intelligence", "observe", "--input-json", str(file)]
    )
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["dated_recent_sample_records"] == 1
    assert report["source_coverage"][0]["population_coverage_verified"] is False
    assert report["paid_customer_outcome_verified"] is False


def test_current_hunter_cli_plan_only_never_calls_network(monkeypatch):
    from click.testing import CliRunner
    from mcp_trendpulse.cli import cli
    from mcp_trendpulse import intelligence_hunter

    def no_network(*_args, **_kwargs):
        raise AssertionError("Plan-only hunt cannot execute a network request")
    monkeypatch.setattr(intelligence_hunter, "collect", no_network)
    result = CliRunner().invoke(cli, [
        "intelligence", "hunt", "--topic", "battery recycling",
        "--source", "github_issues", "--lookback-days", "30",
    ])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["status"] == "planned"
    assert report["network_performed"] is False
    assert report["request_count"] == 1


def test_current_hunter_history_requires_live_opt_in():
    from click.testing import CliRunner
    from mcp_trendpulse.cli import cli

    result = CliRunner().invoke(cli, [
        "intelligence", "hunt", "--record-history",
    ])
    assert result.exit_code != 0
    assert "--record-history requires --execute" in result.output


def test_intelligence_query_supports_explicit_bounded_timeout_without_retry(monkeypatch):
    from mcp_trendpulse import intelligence_core as core

    calls = []
    def fake_collect(plan, *, fetch, timeout):
        calls.append((plan.source, fetch, timeout))
        return {"source": plan.source, "status": "unavailable",
                "reason": "TimeoutError", "retry_automatically": False}

    monkeypatch.setattr(core, "collect", fake_collect)
    result = CliRunner().invoke(cli, [
        "intelligence", "query", "--source", "gdelt_latest",
        "--execute", "--timeout", "30",
    ])
    assert result.exit_code == 0, result.output
    response = json.loads(result.output)
    assert response["status"] == "unavailable"
    assert response["reason"] == "TimeoutError"
    assert calls == [("gdelt_latest", True, 30)]

    invalid = CliRunner().invoke(cli, [
        "intelligence", "query", "--source", "gdelt_latest",
        "--execute", "--timeout", "31",
    ])
    assert invalid.exit_code != 0
    assert calls == [("gdelt_latest", True, 30)]


def test_discover_cli_plan_only_and_history_gate(monkeypatch):
    from mcp_trendpulse import intelligence_discovery

    def forbidden(*_a, **_k):
        raise AssertionError("Seedless discovery planning must not contact providers")

    monkeypatch.setattr(intelligence_discovery, "collect", forbidden)
    result = CliRunner().invoke(cli, [
        "intelligence", "discover", "--lookback-days", "30", "--limit", "12",
    ])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["status"] == "planned"
    assert data["network_performed"] is False
    assert {plan["source"] for plan in data["plans"]} == {
        "openalex", "cfpb", "ted",
    }
    assert "Authorization" not in result.output

    bad = CliRunner().invoke(cli, [
        "intelligence", "discover", "--record-history",
    ])
    assert bad.exit_code != 0
    assert "--record-history requires --execute" in bad.output
