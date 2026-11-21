"""Integration regression: public previews must not reveal credential headers."""
import json

from mcp_trendpulse.intelligence_core import Plan


def test_plan_public_metadata_never_lists_credential_header_names_or_values():
    raw_headers = {
        "Authorization": "Bearer fake-fixture-secret",
        "X-API-Key": "fake-fixture-api-key",
        "X-Custom-Token": "fake-fixture-token",
        "Cookie": "session=fake-fixture-cookie",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "trendpulse-test",
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
        "Accept": "<configured>",
        "Content-Type": "<configured>",
        "User-Agent": "<configured>",
    }
    shown = json.dumps(preview)
    for secret in ("Authorization", "X-API-Key", "X-Custom-Token", "Cookie",
                   "fake-fixture-secret", "fake-fixture-api-key",
                   "fake-fixture-token", "fake-fixture-cookie"):
        assert secret not in shown
    # Source execution still has the original privately held credentials.
    assert plan.headers == raw_headers
    assert plan.headers["Authorization"] == "Bearer fake-fixture-secret"


def test_sensitive_header_name_matching_is_case_insensitive():
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
    assert plan.public()["headers"] == {"ACCEPT": "<configured>"}
    assert "authorization" not in json.dumps(plan.public())
