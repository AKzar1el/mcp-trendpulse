"""Independent five-job MJAU V2 end-user workflow probe via real MCP stdio.

Run from repo: python scripts/mjau_v2_user_workflow_probe.py --mode plan|live
Public metadata only; --live explicitly consumes source-specific free budgets.
No credentials, model/dataset contents, background workers or publisher action.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


CASES = (
    ("P1_stars", "intelligence_repository_star_history",
     {"owner": "AKzar1el", "repo": "mcp-trendpulse", "limit": 10}),
    ("P2_dependencies", "intelligence_dependency_graph",
     {"ecosystem": "npm", "package": "is-odd", "version": "3.0.1"}),
    ("P3_scorecard", "intelligence_repository_scorecard",
     {"owner": "pallets", "repo": "flask"}),
    ("P4_lifecycle", "intelligence_release_lifecycle",
     {"product": "nodejs", "release": "20"}),
    ("P5_hub_models", "intelligence_hf_catalog",
     {"kind": "models", "limit": 2}),
)


def _body(result):
    if result.isError:
        raise AssertionError("MCP call returned an error")
    body = result.structuredContent
    if body is None:
        chunks = [c.text for c in result.content if getattr(c, "type", "") == "text"]
        if not chunks:
            raise AssertionError("MCP call lacked a result")
        body = json.loads(chunks[0])
    if isinstance(body, dict) and set(body) == {"result"}:
        body = body["result"]
    if not isinstance(body, dict):
        raise AssertionError("Expected object source report")
    return body


async def _call(session, tool, args):
    start = time.perf_counter()
    result = await session.call_tool(
        tool, args, read_timeout_seconds=timedelta(seconds=40)
    )
    return _body(result), (time.perf_counter() - start) * 1000


def _percentile(values, fraction):
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction))], 3)


def _valid(source_id, payload):
    if payload.get("status") not in {"observed", "observed_partial", "observed_stale"}:
        return False
    if source_id == "P1_stars":
        return (isinstance(payload.get("weeks"), list)
                and payload.get("individual_stargazer_data_collected") is False)
    if source_id == "P2_dependencies":
        return (isinstance(payload.get("summary"), dict)
                and payload.get("provider_root_identity_verified") is True
                and payload.get("not_installs_or_dependents_or_customers") is True)
    if source_id == "P3_scorecard":
        return (isinstance(payload.get("source_scan_date"), str)
                and payload.get("not_a_security_audit_or_vulnerability_guarantee") is True)
    if source_id == "P4_lifecycle":
        return (payload.get("support_entitlement_verified") is False
                and payload.get("official_vendor_support_verified_by_api") is False
                and isinstance(payload.get("eol_from"), str))
    if source_id == "P5_hub_models":
        return (isinstance(payload.get("records"), list)
                and len(payload["records"]) >= 2
                and payload.get("customer_demand_verified") is False
                and payload.get("model_weights_or_dataset_files_downloaded") is False)
    return False


def _evidence_summary(task, payload):
    """Only fixed, source-specific fields; never serialize untrusted source text."""
    status = payload.get("status")
    out = {
        "status": status,
        "status_known_observation": status in {"observed", "observed_partial", "observed_stale"},
        "cache_hit": payload.get("cache_hit"),
        "network_performed": payload.get("network_performed"),
        "requests_attempted": payload.get("requests_attempted"),
    }
    if task == "P1_stars":
        out["weekly_rows"] = len(payload.get("weeks") or [])
        out["cohort_comparison_status"] = (payload.get("comparison") or {}).get("status")
    elif task == "P2_dependencies":
        out["root_verified"] = payload.get("provider_root_identity_verified", False)
        out["direct_versions"] = (payload.get("summary") or {}).get(
            "distinct_direct_dependency_versions"
        )
    elif task == "P3_scorecard":
        out["source_scan_date"] = payload.get("source_scan_date")
        out["aggregate_inconclusive"] = payload.get("aggregate_inconclusive")
        out["published_checks"] = payload.get("reported_check_count")
    elif task == "P4_lifecycle":
        out["eol_date"] = payload.get("eol_from")
        out["eol"] = payload.get("is_eol")
        out["scope_caveats"] = payload.get("support_scope_caveats", [])
    elif task == "P5_hub_models":
        out["model_ids"] = [
            x.get("repository_id") for x in (payload.get("records") or [])[:2]
        ]
        out["gating_flags"] = [
            x.get("gated") for x in (payload.get("records") or [])[:2]
        ]
    return out


async def run(mode: str):
    root = Path(__file__).resolve().parent.parent
    env = {"PYTHONPATH": str(root / "src")}
    # Deliberately do not inherit a provider credential or pass a cache-dir
    # override: the real local source quota is shared across projects.
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_trendpulse.intelligence_mcp"],
        env=env,
    )
    tasks = []
    result = {
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "mcp_transport": "stdio_child_process_sdk",
        "case_count": len(CASES),
        "requires_paid_api": False,
        "baseline_v1_specific_provider_tasks_answerable": 0,
        "v2_source_observed": 0,
        "v2_source_scoped_answers": 0,
        "provider_requests_attempted": 0,
        "plans_p50_ms": None,
        "plans_p95_ms": None,
        "task_results": tasks,
    }
    plan_latencies = []
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            init = await session.initialize()
            if init.serverInfo.name != "trendpulse-free-market-intelligence":
                raise AssertionError("Unexpected server identity")
            tools = await session.list_tools()
            by_name = {tool.name: tool for tool in tools.tools}
            if len(by_name) != 17:
                raise AssertionError("Expected exactly 17 optional tools")
            for case, tool_name, arguments in CASES:
                schema = by_name[tool_name]
                if (not schema.annotations or
                    schema.annotations.readOnlyHint is not True or
                    schema.annotations.destructiveHint is not False):
                    raise AssertionError("Unsafe or missing tool annotation")
                plan, duration = await _call(session, tool_name, arguments)
                plan_latencies.append(duration)
                if (plan.get("status") != "planned" or
                    plan.get("requests_attempted") != 0 or
                    plan.get("network_performed") is not False or
                    plan.get("cache_hit") is not False):
                    raise AssertionError("Plan-only unexpectedly used source/cache")
                row = {"task": case, "tool": tool_name,
                       "plan_latency_ms": round(duration, 3),
                       "plan_only_zero_network": True}
                if mode == "live":
                    observed, elapsed = await _call(
                        session, tool_name, {**arguments, "execute": True}
                    )
                    row["live_latency_ms"] = round(elapsed, 3)
                    row["observation"] = _evidence_summary(case, observed)
                    result["provider_requests_attempted"] += observed.get(
                        "requests_attempted", 0
                    )
                    if row["observation"]["status_known_observation"]:
                        result["v2_source_observed"] += 1
                    if _valid(case, observed):
                        result["v2_source_scoped_answers"] += 1
                    # Cache replay is meaningful only for observed data:
                    # failures and stale scores must never become false cache hits.
                    if (observed.get("status") in {"observed", "observed_partial"}
                        and observed.get("rejected_rows", 0) == 0
                        and not observed.get("provider_phase_conflicts")
                        and not (observed.get("summary") or {}).get("graph_has_resolution_errors")):
                        again, replay_ms = await _call(
                            session, tool_name, {**arguments, "execute": True}
                        )
                        row["replay_latency_ms"] = round(replay_ms, 3)
                        row["replay"] = {
                            "status": again.get("status"),
                            "cache_hit": again.get("cache_hit"),
                            "requests_attempted": again.get("requests_attempted"),
                        }
                        # If source validation intentionally refused caching,
                        # preserve that fact instead of retrying a rate-limited
                        # source. A partial result with rejected provider rows
                        # may legitimately be uncacheable.
                        if again.get("cache_hit") is False:
                            row["warning"] = "not_cacheable_or_provider_changed"
                tasks.append(row)
    result["plans_p50_ms"] = _percentile(plan_latencies, 0.5)
    result["plans_p95_ms"] = _percentile(plan_latencies, 0.95)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["plan", "live"], default="plan")
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = asyncio.run(run(args.mode))
    except Exception as exc:
        # Never print untrusted upstream values or credentials.
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}),
              file=sys.stderr)
        return 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": "completed",
        "mode": args.mode,
        "source_observed": report["v2_source_observed"],
        "source_scoped_answers": report["v2_source_scoped_answers"],
        "requests_attempted": report["provider_requests_attempted"],
        "plans_p95_ms": report["plans_p95_ms"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
