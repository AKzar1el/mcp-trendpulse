"""Real, read-only multi-source evidence *compatibility* smoke via MCP stdio.

Do not treat multiple public records as proof of commercial demand. Uses one
single-topic probe across three different evidence classes with no credentials,
no model inference, no unattended schedulers, and no changes to the main MCP.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

TOPIC = "battery"
# These are source *classes*, not votes or scores. Geographic coverage differs.
CASES: tuple[tuple[str, str, dict[str, Any]], ...] = (
    ("cordis", "funded_research", {"source": "cordis", "keyword": TOPIC, "limit": 2}),
    ("cellar", "legal_metadata", {"source": "cellar", "keyword": TOPIC, "limit": 2}),
    ("usaspending", "public_awards", {"source": "usaspending", "keyword": TOPIC, "limit": 2}),
)


def assess(observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Produce a bounded, *non-predictive* coverage status, never a demand score.

    Neither a topic match nor multiple independent publishers proves that any
    business will pay. Different jurisdictions and dates must not be combined
    into one growth rate or financial market-size estimate.
    """
    if not observations:
        raise ValueError("Need at least one source observation")
    seen = set()
    normalized = []
    for item in observations:
        source = item["source"]
        if source in seen:
            raise ValueError("Duplicate source may not inflate cross-source coverage")
        seen.add(source)
        if item["source_class"] not in {"funded_research", "legal_metadata", "public_awards"}:
            raise ValueError("Unrecognized evidence class")
        if item["record_count"] < 0:
            raise ValueError("Negative observation count")
        normalized.append({
            "source": source,
            "evidence_class": item["source_class"],
            "status": item["status"],
            "records_in_bounded_sample": item["record_count"],
            "topic_seen_in_sample": item["topic_seen_in_sample"],
            "cache_replayed": item["cache_replayed"],
            "source_url": item["source_url"],
            "retrieved_at": item["retrieved_at"],
        })
    valid = [x for x in normalized if x["status"] == "observed"
             and x["records_in_bounded_sample"] > 0]
    classes = {x["evidence_class"] for x in valid}
    topic_classes = {x["evidence_class"] for x in valid
                     if x["topic_seen_in_sample"]}
    return {
        "topic": TOPIC,
        "sources_observed": len(valid),
        "distinct_evidence_classes": len(classes),
        "classes_with_topic_in_sample": len(topic_classes),
        "technical_cross_source_compatible": len(classes) >= 2,
        "semantic_topic_overlap_observed": len(topic_classes) >= 2,
        "customer_purchasing_intent_validated": False,
        "opportunity_rankable": False,
        "time_periods_normalized": False,
        "jurisdictions_comparable": False,
        "reason": (
            "Research, legal metadata and US award observations are different "
            "evidence classes and cannot establish demand without dated events, "
            "common entities, comparable units, buyer budgets and external validation."
        ),
        "sources": normalized,
    }


def offline_safety_tests() -> int:
    example = {
        "source": "cordis", "source_class": "funded_research",
        "record_count": 2, "status": "observed",
        "topic_seen_in_sample": True, "cache_replayed": True,
        "source_url": "https://cordis.europa.eu/datalab/sparql/query",
        "retrieved_at": "2026-11-18T00:00:00+00:00",
    }
    second = {
        **example, "source": "cellar", "source_class": "legal_metadata",
        "source_url": "https://publications.europa.eu/webapi/rdf/sparql",
        "topic_seen_in_sample": False,
    }
    assert not assess([example])["technical_cross_source_compatible"]
    result = assess([example, second])
    assert result["technical_cross_source_compatible"]
    assert not result["semantic_topic_overlap_observed"]
    assert not result["opportunity_rankable"]
    assert result["customer_purchasing_intent_validated"] is False
    assert result["jurisdictions_comparable"] is False
    try:
        assess([example, example])
    except ValueError:
        pass
    else:
        raise AssertionError("Duplicate source was incorrectly counted")
    try:
        assess([example, {**second, "source_class": "unknown"}])
    except ValueError:
        pass
    else:
        raise AssertionError("Unsupported evidence class was accepted")
    unavailable = unavailable_observation(
        "cordis", "funded_research",
        {"source": "cordis", "status": "unavailable", "reason": "HTTPError",
         "http_status": 302}, 1,
    )
    third = {**example, "source": "usaspending", "source_class": "public_awards"}
    partial = assess([unavailable, second, third])
    assert partial["sources_observed"] == 2
    assert partial["technical_cross_source_compatible"]
    assert not strict_pass(partial)
    assert not assess([unavailable])["technical_cross_source_compatible"]
    assert strict_pass(assess([example, second, third]))
    assert unavailable["http_status"] == 302
    assert not unavailable["cache_replayed"]
    print(json.dumps({"mode": "offline", "status": "passed",
                      "cases": 7, "spurious_opportunity_scores": 0}), flush=True)
    return 0


def unpack(result: Any) -> dict[str, Any]:
    if result.isError:
        raise AssertionError("MCP returned an unsuccessful result")
    payload = result.structuredContent
    if payload is None:
        texts = [c.text for c in result.content if getattr(c, "type", "") == "text"]
        if len(texts) != 1:
            raise AssertionError("MCP returned no usable structured result")
        payload = json.loads(texts[0])
    if isinstance(payload, dict) and set(payload) == {"result"}:
        payload = payload["result"]
    if not isinstance(payload, dict):
        raise AssertionError("Expected MCP object response")
    return payload


async def call(session: ClientSession, args: dict[str, Any]) -> dict[str, Any]:
    return unpack(await session.call_tool(
        "intelligence_collect", args, read_timeout_seconds=timedelta(seconds=35)
    ))


def unavailable_observation(
    source: str, signal_class: str, response: dict[str, Any], cold_ms: int,
) -> dict[str, Any]:
    status = response.get("status")
    if status not in ("unavailable", "rate_limited", "invalid_source_shape", "no_data"):
        status = "unavailable"
    code = response.get("http_status")
    reason = response.get("reason")
    if reason not in (
        "HTTPError", "URLError", "TimeoutError", "OSError", "provider_cooldown",
        "provider_rate_limited", "local_daily_budget_exhausted", "invalid_source_shape",
    ):
        reason = "source_not_observed"
    return {
        "source": source, "source_class": signal_class, "status": status,
        "record_count": 0, "topic_seen_in_sample": False, "cache_replayed": False,
        "source_url": None, "retrieved_at": None, "cold_ms": cold_ms,
        "cached_ms": None,
        "reason": reason,
        "http_status": code if type(code) is int and 100 <= code <= 599 else None,
    }


def strict_pass(result: dict[str, Any]) -> bool:
    return (
        result["sources_observed"] == len(CASES)
        and result["technical_cross_source_compatible"]
        and result["semantic_topic_overlap_observed"]
        and not result["customer_purchasing_intent_validated"]
        and not result["opportunity_rankable"]
        and all(row["cache_replayed"] for row in result["sources"])
    )


async def live(report: Path) -> int:
    output = []
    with tempfile.TemporaryDirectory(prefix="trendpulse-combine-") as root:
        param = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_trendpulse.intelligence_mcp"],
            env={
                "TRENDPULSE_INTEL_CACHE_DIR": str(Path(root) / "cache"),
                "PYTHONPATH": str(Path(__file__).resolve().parent.parent / "src"),
            },
        )
        async with stdio_client(param) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                init = await session.initialize()
                if init.serverInfo.name != "trendpulse-free-market-intelligence":
                    raise AssertionError("Wrong opt-in MCP server")
                names = {x.name for x in (await session.list_tools()).tools}
                if "intelligence_collect" not in names:
                    raise AssertionError("Collector was not advertised")
                for source, signal_class, arguments in CASES:
                    now = time.perf_counter()
                    first = await call(session, {**arguments, "execute": True})
                    cold_ms = round((time.perf_counter() - now) * 1000)
                    if first.get("source") != source:
                        raise AssertionError("Source identity mismatch")
                    if first.get("status") != "observed":
                        row = unavailable_observation(source, signal_class, first, cold_ms)
                        output.append(row)
                        print(json.dumps({
                            "source": source, "status": row["status"],
                            "reason": row["reason"],
                            "http_status": row["http_status"], "cold_ms": cold_ms,
                        }), flush=True)
                        continue
                    if first.get("evidence_level") != "public_source_snapshot_not_purchasing_validation":
                        raise AssertionError("Source was incorrectly promoted to purchasing proof")
                    if not first.get("source_documentation") or not first.get("retrieved_at"):
                        raise AssertionError("Provider provenance or observation date missing")
                    projections = first.get("observations") or {}
                    samples = projections.get("sample") or []
                    count = projections.get("record_count")
                    if not isinstance(count, int) or count < 1 or not samples:
                        raise AssertionError(f"{source}: no usable evidence rows")
                    now = time.perf_counter()
                    second = await call(session, {**arguments, "execute": True})
                    warm_ms = round((time.perf_counter() - now) * 1000)
                    if second.get("cache_hit") is not True:
                        raise AssertionError("Repeated source query did not use cache")
                    if second.get("retrieved_at") != first.get("retrieved_at"):
                        raise AssertionError("Replay unexpectedly changed retrieval time")
                    sample_text = json.dumps(samples, ensure_ascii=False).lower()
                    row = {
                        "source": source, "source_class": signal_class,
                        "record_count": count, "status": first["status"],
                        "topic_seen_in_sample": TOPIC in sample_text,
                        "cache_replayed": True,
                        "source_url": first.get("source_url"),
                        "retrieved_at": first["retrieved_at"],
                        "cold_ms": cold_ms, "cached_ms": warm_ms,
                    }
                    output.append(row)
                    print(json.dumps({
                        "source": source, "status": "observed",
                        "record_count": count,
                        "topic_seen_in_sample": row["topic_seen_in_sample"],
                        "cache_hit": True, "cold_ms": cold_ms, "cached_ms": warm_ms,
                    }), flush=True)
    result = assess(output)
    passed = strict_pass(result)
    result["status"] = "passed" if passed else "failed"
    result["source_failures"] = [
        {"source": x["source"], "status": x["status"], "reason": x["reason"],
         "http_status": x["http_status"]}
        for x in output if x["status"] != "observed"
    ]
    result["checked_at"] = datetime.now(timezone.utc).isoformat()
    result["mode"] = "live_mcp_cross_source"
    result["cache_replay_all"] = all(x["cache_replayed"] for x in output)
    result["cold_request_ms"] = {x["source"]: x["cold_ms"] for x in output}
    result["cached_request_ms"] = {x["source"]: x["cached_ms"] for x in output}
    report.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "mode": "live_mcp_cross_source", "status": result["status"],
        "sources": result["sources_observed"],
        "independent_classes": result["distinct_evidence_classes"],
        "topic_overlap_classes": result["classes_with_topic_in_sample"],
        "commercial_validation": False,
    }), flush=True)
    return 0 if passed else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["offline", "live"], default="offline")
    parser.add_argument("--report", default="intelligence-cross-source.json")
    args = parser.parse_args()
    try:
        return offline_safety_tests() if args.mode == "offline" else asyncio.run(live(Path(args.report)))
    except Exception as exc:
        # Never expose external payloads or network credentials in CI errors.
        print(json.dumps({"mode": args.mode, "status": "failed",
                          "error_type": type(exc).__name__}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
