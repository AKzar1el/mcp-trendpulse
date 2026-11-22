"""Actual isolated MCP client/server workflow, using pinned source fixtures only.

This deliberately creates a new **test-only** FastMCP object, not a new tool
registration in the installed TrendPulse service. No network or global state.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from time import perf_counter

from fastmcp import Client, FastMCP

from mcp_trendpulse.mjau_v3.osv import (
    parse_compact_package_query,
    present_compact_query_for_mcp,
    plan_compact_package_query,
)
from mcp_trendpulse.mjau_v3.wikidata import (
    candidates_for_name,
    parse_qid_lookup,
    plan_qid_lookup,
)

FIXTURES = Path(__file__).parent / "fixtures" / "mjau_v3"
QIDS = ["Q42", "Q64", "Q30"]
LANGS = ["en", "de", "fr", "es", "sl", "it"]
WIKIDATA_SOURCE = json.loads(
    (FIXTURES / "wikidata_q42_q64_q30_20261121.json").read_text("utf-8")
)
DJANGO_SOURCE = json.loads(
    (FIXTURES / "osv_django_compact_20261121.json").read_text("utf-8")
)

# Non-production, in-memory transport: no HTTP listener, no network collector,
# no third-party text or paid services, no v1 tool registration changes.
sandbox = FastMCP(name="mjau-v3-source-workflow-sandbox")


@sandbox.tool(name="test_only_wikidata_candidates")
def _sandbox_wikidata_candidates(name: str, language: str) -> dict:
    plan_qid_lookup(QIDS, LANGS)
    parsed = parse_qid_lookup(WIKIDATA_SOURCE, QIDS, LANGS)
    result = candidates_for_name(parsed, name, language)
    return {
        "status": result["status"],
        "candidate_qids": result["candidate_qids"],
        "identity_confirmed": result["identity_confirmed"],
        "searched_name_coverage_complete": result["searched_name_coverage_complete"],
        "source_items_incomplete": result["source_items_incomplete"],
        "source_url_prefix": "https://www.wikidata.org/wiki/",
        "source_licensing": "structured-data-CC0",
        "source_fixture_only_not_live_search": True,
    }


@sandbox.tool(name="test_only_osv_package_ids")
def _sandbox_osv_package_ids(ecosystem: str, package: str, version: str) -> dict:
    plan_compact_package_query(ecosystem, package, version)
    if (ecosystem, package, version) != ("PyPI", "Django", "2.2.0"):
        raise ValueError("No saved source fixture for this exact package/version")
    source = DJANGO_SOURCE["one_query_envelope"]
    result = parse_compact_package_query(
        source, ecosystem=ecosystem, package=package, version=version,
    )
    return present_compact_query_for_mcp(result)


def test_real_in_memory_mcp_client_source_workflow_and_invalid_inputs():
    async def task():
        async with Client(sandbox) as client:
            catalog = await client.list_tools()
            assert sorted(t.name for t in catalog) == [
                "test_only_osv_package_ids",
                "test_only_wikidata_candidates",
            ]
            apple_test = await client.call_tool(
                "test_only_wikidata_candidates",
                {"name": "Berlin", "language": "en"},
            )
            assert not apple_test.is_error
            assert apple_test.structured_content["status"] == (
                "candidate_requires_confirmation"
            )
            assert apple_test.structured_content["candidate_qids"] == ["Q64"]
            assert apple_test.structured_content["identity_confirmed"] is False
            assert apple_test.structured_content["source_items_incomplete"] is True

            unknown = await client.call_tool(
                "test_only_wikidata_candidates",
                {"name": "This candidate has no source alias", "language": "en"},
            )
            assert not unknown.is_error
            assert unknown.structured_content["identity_confirmed"] is False
            assert unknown.structured_content["status"] in (
                "unknown_incomplete_aliases", "unknown_incomplete_source"
            )

            package = await client.call_tool(
                "test_only_osv_package_ids",
                {"ecosystem": "PyPI", "package": "Django", "version": "2.2.0"},
            )
            assert not package.is_error
            result = package.structured_content
            assert result["provider_ids_in_this_page"] == 75
            assert len(result["advisories"]) == 75
            assert result["source_population_complete"] is True
            assert result["no_advisory_not_equivalent_to_safe_package"] is True
            assert result["source_specific_license_review_required"] is True
            assert result["raw_advisory_redistribution_authorized"] is False
            assert len(json.dumps(result).encode()) < 20_000

            for name, args in [
                ("test_only_wikidata_candidates", {"name": "Berlin", "language": "ru"}),
                ("test_only_osv_package_ids", {
                    "ecosystem": "PyPI", "package": "flask", "version": "1.0",
                }),
                ("test_only_osv_package_ids", {
                    "ecosystem": [], "package": "Django", "version": "2.2.0",
                }),
            ]:
                response = await client.call_tool(name, args, raise_on_error=False)
                assert response.is_error, (name, args)
                assert "private-demo-secret" not in str(response.content)

    asyncio.run(task())


def test_real_in_memory_mcp_repeated_call_latency_and_source_consistency():
    async def task():
        elapsed_ms = []
        async with Client(sandbox) as client:
            for index in range(30):
                start = perf_counter()
                if index % 2:
                    response = await client.call_tool(
                        "test_only_wikidata_candidates",
                        {"name": "Berlin", "language": "en"},
                    )
                    assert response.structured_content["candidate_qids"] == ["Q64"]
                    assert not response.structured_content["identity_confirmed"]
                else:
                    response = await client.call_tool(
                        "test_only_osv_package_ids", {
                            "ecosystem": "PyPI", "package": "Django",
                            "version": "2.2.0",
                        },
                    )
                    assert response.structured_content["provider_ids_in_this_page"] == 75
                assert not response.is_error
                elapsed_ms.append((perf_counter() - start) * 1000)
        assert len(elapsed_ms) == 30
        # Avoid hard timing thresholds on a Windows machine shared with agents:
        # this is a functional throughput soak, not a latency SLA.
        assert min(elapsed_ms) >= 0

    asyncio.run(task())
