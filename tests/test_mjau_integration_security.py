"""Public discover CLI privacy without breaking other MCP request-plan APIs."""
import json

from click.testing import CliRunner

from mcp_trendpulse.cli import cli
from mcp_trendpulse.intelligence_core import Plan


def test_existing_plan_public_redacts_values_and_preserves_known_header_names():
    raw_headers = {
        "Authorization": "Bearer fake-fixture-secret",
        "x-api-key": "fake-fixture-api-key",
        "SECURITY_TOKEN": "fake-fixture-token",
        "Cookie": "session=fake-fixture-cookie",
        "Accept": "application/json",
    }
    plan = Plan(
        source="test_public_preview",
        wave=1,
        method="GET",
        url="https://example.org/public",
        docs="https://example.org/docs",
        caution="not a real provider request",
        budget_per_day=1,
        headers=raw_headers,
    )
    preview = plan.public()
    assert preview["network_performed"] is False
    assert preview["headers"] == {
        key: "<configured>" for key in raw_headers
    }
    serialized = json.dumps(preview)
    for secret in (
        "fake-fixture-secret", "fake-fixture-api-key",
        "fake-fixture-token", "fake-fixture-cookie",
    ):
        assert secret not in serialized
    # Actual private source request authorization is unaffected.
    assert plan.headers == raw_headers


def test_redacted_header_name_case_is_retained_in_existing_plan_contract():
    plan = Plan(
        source="test_case",
        wave=1,
        method="GET",
        url="https://example.org/public",
        docs="https://example.org/docs",
        caution="test",
        budget_per_day=1,
        headers={
            "authorization": "Bearer hidden",
            "X-Api-Key": "hidden",
            "ACCEPT": "application/json",
            "x-secret-token": "hidden",
        },
    )
    assert plan.public()["headers"] == {
        "authorization": "<configured>",
        "X-Api-Key": "<configured>",
        "ACCEPT": "<configured>",
        "x-secret-token": "<configured>",
    }


def test_offline_discover_cli_strips_sensitive_header_names_but_keeps_plan(monkeypatch):
    monkeypatch.setenv("TRENDPULSE_INTEL_OPENALEX_KEY", "fake-cli-secret-never-print")
    result = CliRunner().invoke(cli, [
        "intelligence", "discover", "--lookback-days", "30", "--limit", "12",
    ])
    assert result.exit_code == 0, result.output
    output = json.loads(result.output)
    assert output["status"] == "planned"
    assert output["network_performed"] is False
    assert {plan["source"] for plan in output["plans"]} == {
        "openalex", "ted", "cfpb",
    }
    for plan in output["plans"]:
        assert set(plan.get("headers", {})) <= {
            "Accept", "Content-Type", "User-Agent",
        }
        assert all(value == "<configured>" for value in plan.get("headers", {}).values())
    assert "Authorization" not in result.output
    assert "fake-cli-secret-never-print" not in result.output
