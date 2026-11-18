"""Independent MCP client end-to-end contract, through a real stdio subprocess.

No ChatGPT connection, paid provider, production worker, or user key is used.
The real MCP SDK negotiates protocol initialization and calls the server's
advertised tools over JSON-RPC; the server cannot rely on imported test state.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

TOOLS = {
    "intelligence_source_catalog",
    "intelligence_plan",
    "intelligence_collect",
    "intelligence_analyze_job_postings",
    "intelligence_provider_settings",
    "intelligence_provider_setup",
    "intelligence_opportunity_lanes",
    "intelligence_evaluate_opportunities",
    "intelligence_walk_forward_backtest",
}
FAKE_TOKEN = "SYNTHETIC_OFFLINE_E2E_TOKEN_NOT_A_PROVIDER_KEY"


def _unpack(response: Any, *, expect_error: bool = False) -> Any:
    if bool(response.isError):
        if expect_error:
            return {"is_error": True}
        raise AssertionError("MCP tool returned an error")
    if expect_error:
        raise AssertionError("MCP request unexpectedly accepted invalid arguments")
    body = response.structuredContent
    if body is None:
        text = [x.text for x in response.content if getattr(x, "type", "") == "text"]
        if not text:
            raise AssertionError("MCP tool produced no structured or JSON text response")
        body = json.loads(text[0])
    if isinstance(body, dict) and set(body) == {"result"}:
        return body["result"]
    return body


async def _call(session: ClientSession, name: str, args: dict[str, Any],
                *, error: bool = False, timeout: int = 45) -> Any:
    result = await session.call_tool(name, args, read_timeout_seconds=timedelta(seconds=timeout))
    return _unpack(result, expect_error=error)


class Checkpoints(list):
    """Print safe test case names; never print values from external tool outputs."""

    def append(self, record):
        super().append(record)
        print(json.dumps({"checkpoint": record["case"], "status": "passed"}),
              flush=True)


async def exercise(mode: str, result_path: Path) -> int:
    checked: list[dict[str, Any]] = Checkpoints()
    with tempfile.TemporaryDirectory(prefix="trendpulse-intel-mcp-") as root:
        cache_dir = Path(root) / "cache"
        env = {
            "TRENDPULSE_INTEL_CACHE_DIR": str(cache_dir),
            "TRENDPULSE_INTEL_OPENALEX_KEY": FAKE_TOKEN,
        }
        if mode == "changedetection":
            # The CI job injects an *ephemeral local instance's* test API key.
            key = os.environ.get("TRENDPULSE_INTEL_CHANGEDETECTION_KEY")
            if not key:
                raise AssertionError("Ephemeral local change-monitor API key missing")
            env["TRENDPULSE_INTEL_CHANGEDETECTION_KEY"] = key

        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_trendpulse.intelligence_mcp"],
            env=env,
        )
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                init = await session.initialize()
                if init.serverInfo.name != "trendpulse-free-market-intelligence":
                    raise AssertionError("Unexpected MCP server identity")
                tools = await session.list_tools()
                names = {tool.name for tool in tools.tools}
                if names != TOOLS:
                    raise AssertionError("Unexpected MCP toolset; default architecture may have changed")
                for tool in tools.tools:
                    if not tool.annotations or not tool.annotations.readOnlyHint:
                        raise AssertionError("Unmarked writable tool")
                    if tool.annotations.destructiveHint is not False:
                        raise AssertionError("Unexpected destructive tool flag")
                    schema = json.dumps(tool.inputSchema).lower()
                    if '"api_key"' in schema or '"secret"' in schema or '"token"' in schema:
                        raise AssertionError("Secret-bearing MCP argument schema exposed")
                checked.append({"case": "initialize_discover_nine_read_only_tools", "ok": True})

                catalogue = await _call(session, "intelligence_source_catalog", {})
                if not isinstance(catalogue, list) or len(catalogue) != 25:
                    raise AssertionError("Expected exactly 25 global-source records")
                if {row["wave"] for row in catalogue} != {1, 2, 3}:
                    raise AssertionError("One or more waves not registered")
                if any(row["id"] == "opsi_slovenia" for row in catalogue):
                    raise AssertionError("Removed Slovenia provider is still exposed")
                wave3 = await _call(
                    session, "intelligence_source_catalog", {"wave": 3}
                )
                if not wave3 or any(x["wave"] != 3 for x in wave3):
                    raise AssertionError("Wave filter did not work through MCP")
                checked.append({"case": "catalogue_wave_filter_and_regional_removal", "ok": True})

                status = await _call(session, "intelligence_provider_settings", {})
                openalex = next((x for x in status if x["provider"] == "openalex"), None)
                if not openalex or not openalex["ready_for_live_auth_test"]:
                    raise AssertionError("Synthetic free-key readiness was not detected")
                guide = await _call(
                    session, "intelligence_provider_setup", {"provider": "epo"}
                )
                if "TRENDPULSE_INTEL_EPO_CONSUMER_KEY" not in guide["field_names"]:
                    raise AssertionError("EPO setup guide missing required field")
                plan_secret = await _call(
                    session, "intelligence_plan",
                    {"source": "openalex", "keyword": "energy storage", "limit": 1},
                )
                all_visible = json.dumps([status, guide, plan_secret], ensure_ascii=False)
                if FAKE_TOKEN in all_visible:
                    raise AssertionError("Synthetic credential leaked over MCP")
                if plan_secret["headers"].get("Authorization") != "<configured>":
                    raise AssertionError("API credential header was not redacted")
                checked.append({"case": "settings_setup_header_redaction", "ok": True})

                sample_jobs = {"jobs": [
                    {
                        "id": 12345678,
                        "title": "Operations Lead",
                        "content": (
                            "<p>Manually reconcile spreadsheets, maintain "
                            "compliance audits and reduce repetitive data entry.</p>"
                        ),
                        "absolute_url": "https://job-boards.greenhouse.io/example/jobs/12345678",
                    }
                ]}
                pain = await _call(
                    session, "intelligence_analyze_job_postings",
                    {
                        "source": "greenhouse", "company": "example",
                        "public_board_json": sample_jobs,
                    },
                )
                categories = {x["category"] for x in pain["pain_hypotheses"]}
                if not {"manual_work", "compliance"} <= categories:
                    raise AssertionError("Job-pain categories missing for sourced sample")
                if not all(x["examples"][0].get("posting_url")
                           for x in pain["pain_hypotheses"]):
                    raise AssertionError("Job pain lost its source URLs")
                checked.append({"case": "job_pain_extraction_with_provenance", "ok": True})

                lanes = await _call(session, "intelligence_opportunity_lanes", {})
                if len(lanes) != 12:
                    raise AssertionError("Not all 12 opportunity combinations were exposed")
                case = {
                    "id": "incident-workflow",
                    "title": "Sourced reliability problem",
                    "lane": "developer_reliability",
                    "geography": "US",
                    "buyer": "Public agencies",
                    "buyer_entity": "agency-test",
                    "workflow": "incident_triage",
                }
                items = []
                for i, source in enumerate(("github_issues", "greenhouse_job", "usaspending")):
                    items.append({
                        "id": f"incident-example-{i}", "candidate": case["id"],
                        "source": source, "origin_id": f"origin-example-{i}",
                        "buyer_entity": "agency-test" if source == "usaspending" else "",
                        "publisher": f"publisher-example-{i}",
                        "geography": "US", "workflow": "incident_triage",
                        "url": f"https://example.org/real-reference-format/{i}",
                        "published_at": "2026-11-10", "observed_at": "2026-11-12",
                        "claim": "Offline synthetic evidence fixture",
                    })
                assessed = await _call(session, "intelligence_evaluate_opportunities", {
                    "candidates": [case], "evidence": items, "as_of": "2026-11-18",
                })
                if assessed["results"][0]["status"] != "buyer_interview_priority":
                    raise AssertionError("Buyer gate did not evaluate consistent evidence")
                if assessed["results"][0]["success_probability"] is not None:
                    raise AssertionError("Untrained success probability was invented")
                fail = await _call(session, "intelligence_evaluate_opportunities", {
                    "candidates": [case], "evidence": items, "as_of": "2026-11-18",
                    "source_health": {"github_issues": "timeout"},
                })
                if fail["results"][0]["status"] != "partial_provider_coverage":
                    raise AssertionError("Provider failure did not degrade prioritization")
                labels = await _call(session, "intelligence_walk_forward_backtest", {
                    "examples": [{
                        "candidate": case, "evidence": items, "as_of": "2026-11-18",
                        "outcome_at": "2027-01-15", "outcome": "no_purchase",
                        "outcome_verified": True, "outcome_url": "https://example.org/label",
                    }]
                })
                if labels["status"] != "insufficient_verified_outcomes":
                    raise AssertionError("One synthetic label was treated as prediction accuracy")
                checked.append({"case": "opportunity_lanes_buyer_gate_failure_and_backtest", "ok": True})

                plan = await _call(
                    session, "intelligence_collect",
                    {"source": "gleif", "keyword": "Siemens", "limit": 1},
                )
                if plan.get("status") != "planned" or plan.get("network_performed") is not False:
                    raise AssertionError("Default tool call performed a network request")
                if cache_dir.exists():
                    raise AssertionError("Plan-only call created a network/cache side effect")
                checked.append({"case": "plan_default_no_network", "ok": True})

                await _call(session, "intelligence_plan", {
                    "source": "https://127.0.0.1/secrets", "keyword": "x"
                }, error=True)
                await _call(session, "intelligence_collect", {
                    "source": "rsshub_local", "identifier": "../private", "execute": True
                }, error=True)
                await _call(session, "intelligence_provider_setup", {
                    "provider": "unknown-service"
                }, error=True)
                await _call(session, "intelligence_plan", {
                    "source": "gleif", "keyword": "Siemens", "limit": 999
                }, error=True)
                checked.append({"case": "reject_bad_sources_routes_settings_and_limits", "ok": True})

                public = (
                    [("gleif", {"source": "gleif", "keyword": "Siemens", "limit": 1}),
                     ("copernicus", {"source": "copernicus", "limit": 1})]
                    if mode == "public" else []
                )
                if mode == "rsshub":
                    public = [(
                        "rsshub_local",
                        {"source": "rsshub_local", "identifier": "test/1", "limit": 1},
                    )]
                if mode == "changedetection":
                    public = [("changedetection_local", {
                        "source": "changedetection_local", "limit": 1
                    })]
                for source, arguments in public:
                    fetch_args = {**arguments, "execute": True}
                    first = await _call(
                        session, "intelligence_collect", fetch_args, timeout=45
                    )
                    if first.get("status") != "observed":
                        raise AssertionError(
                            f"{source} not observed through MCP: {first.get('status')}"
                        )
                    if first.get("source") != source or not first.get("retrieved_at"):
                        raise AssertionError("Live result missing source provenance")
                    count = (first.get("observations") or {}).get("record_count")
                    if not isinstance(count, int) or count < (
                        0 if source == "changedetection_local" else 1
                    ):
                        raise AssertionError("Provider returned no usable observations")
                    again = await _call(
                        session, "intelligence_collect", fetch_args, timeout=45
                    )
                    if again.get("cache_hit") is not True:
                        raise AssertionError(f"{source} repeated call missed SQLite cache")
                    if again.get("retrieved_at") != first.get("retrieved_at"):
                        raise AssertionError("Cache replay changed source timestamp")
                    if source == "rsshub_local":
                        items = first["data"].get("observations") or []
                        if not any(x.get("element") == "title" and
                                   x.get("text") == "Test 1" for x in items):
                            raise AssertionError("Live RSSHub test title not observed via MCP")
                    checked.append({
                        "case": f"live_mcp_{source}_cache_replay",
                        "ok": True,
                        "observations": count,
                    })
        report = {
            "mode": mode,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "stdio_handshake": True,
            "independent_sdk_client": True,
            "cases_passed": len(checked),
            "checks": checked,
            "paid_requests": 0,
            "credential_values_in_report": False,
        }
        result_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({
            "mode": mode, "status": "passed",
            "checks": len(checked), "live_sources": [x["case"] for x in checked
                                                      if x["case"].startswith("live_mcp_")],
        }), flush=True)
        return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["offline", "public", "rsshub", "changedetection"],
                        default="offline")
    parser.add_argument("--report", default="intelligence-mcp-e2e.json")
    args = parser.parse_args()
    try:
        return asyncio.run(exercise(args.mode, Path(args.report)))
    except Exception as exc:
        # Groups come from stdio task groups; only print leaf exception
        # *classes* and our own static assertions. Never print remote payloads.
        def leaf_types(error):
            if isinstance(error, BaseExceptionGroup):
                return [name for inner in error.exceptions for name in leaf_types(inner)]
            return [type(error).__name__]

        def own_assertions(error):
            if isinstance(error, BaseExceptionGroup):
                return [name for inner in error.exceptions for name in own_assertions(inner)]
            if isinstance(error, (AssertionError, AttributeError)):
                return [str(error).replace(FAKE_TOKEN, "<redacted>")[:140]]
            return []

        print(json.dumps({
            "mode": args.mode, "status": "failed",
            "error_type": type(exc).__name__,
            "leaf_types": leaf_types(exc),
            "assertions": own_assertions(exc),
        }), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
