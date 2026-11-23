"""Cross-version 35-tool registry, pairwise routing, isolation and failure QA.

The 595 pairwise negative-input interactions exercise real MCP dispatch and
validation without contacting Google Trends or external providers. These do
NOT claim exhaustive combinations of argument values, tool result content,
or network availability.
"""
from __future__ import annotations

import asyncio
import importlib
from itertools import combinations

from fastmcp import Client
import pytest

from mcp_trendpulse.server import mcp as community_mcp
from mcp_trendpulse.intelligence_mcp import intel_mcp
from mcp_trendpulse.mjau_v3.mcp import mjau_v3_mcp
from mcp_trendpulse.mjau_v3.unified_mcp import unified_mcp


EXPECTED = (16, 17, 2)
INVALID_ARGS = {"__trendpulse_unknown_no_provider_call__": True}


def _classify(names):
    return (
        {n for n in names if not n.startswith(("intelligence_", "mjau_v3_"))},
        {n for n in names if n.startswith("intelligence_")},
        {n for n in names if n.startswith("mjau_v3_")},
    )


@pytest.mark.asyncio
async def test_combined_real_fastmcp_tools_match_separate_servers():
    async with Client(unified_mcp) as unified:
        all_tools = await unified.list_tools()
        names = [t.name for t in all_tools]
        assert len(names) == len(set(names)) == sum(EXPECTED)
        v1, v2, v3 = _classify(names)
        assert (len(v1), len(v2), len(v3)) == EXPECTED
        assert v3 == {"mjau_v3_wikidata_names", "mjau_v3_osv_advisory_ids"}
        for tool in all_tools:
            assert tool.annotations and tool.annotations.readOnlyHint is True, tool.name
            assert tool.inputSchema.get("additionalProperties") is False, tool.name
            assert tool.description and len(tool.description) > 20, tool.name
            assert tool.inputSchema.get("type") == "object", tool.name

    # Unified module is imported but must not mutate other root servers.
    for server, expected_names in (
        (community_mcp, v1),
        (intel_mcp, v2),
        (mjau_v3_mcp, v3),
    ):
        async with Client(server) as client:
            assert {t.name for t in await client.list_tools()} == expected_names


@pytest.mark.asyncio
async def test_each_tool_rejects_unknown_parameter_without_provider():
    async with Client(unified_mcp) as client:
        for tool in await client.list_tools():
            result = await client.call_tool(
                tool.name, INVALID_ARGS, raise_on_error=False,
            )
            assert result.is_error, f"{tool.name} accepted unrecognized args"


@pytest.mark.asyncio
async def test_all_595_unique_pairs_reject_unknown_parameters_independently():
    async with Client(unified_mcp) as client:
        names = sorted(t.name for t in await client.list_tools())
        seen = 0
        for first, second in combinations(names, 2):
            a, b = await asyncio.gather(
                client.call_tool(first, INVALID_ARGS, raise_on_error=False),
                client.call_tool(second, INVALID_ARGS, raise_on_error=False),
            )
            assert a.is_error, (first, second)
            assert b.is_error, (first, second)
            seen += 1
        assert seen == 595


@pytest.mark.asyncio
async def test_all_6545_tool_triples_coexist_without_names_or_schema_conflicts():
    async with Client(unified_mcp) as client:
        tools = await client.list_tools()
        names = sorted(t.name for t in tools)
        assert len(tools) == 35
        assert len(list(combinations(names, 3))) == 6545
        assert len({n for trio in combinations(names, 3) for n in trio}) == 35
        assert all(t.inputSchema.get("additionalProperties") is False for t in tools)


@pytest.mark.asyncio
async def test_v2_and_v3_plan_only_shared_context_stays_bounded():
    async with Client(unified_mcp) as client:
        run = [
            ("intelligence_plan", {"source": "worldbank", "country": "SI",
                                   "identifier": "SP.POP.TOTL"}),
            ("mjau_v3_wikidata_names", {"qids": ["Q95", "Q312"],
                                       "languages": ["en"], "execute": False}),
            ("mjau_v3_osv_advisory_ids", {"ecosystem": "npm",
                                         "package": "minimist", "version": "0.0.8",
                                         "execute": False}),
            ("intelligence_release_lifecycle", {"product": "nodejs",
                                                "release": "22", "execute": False}),
        ]
        for name, args in run + list(reversed(run)):
            result = await client.call_tool(name, args)
            assert not result.is_error, name
            assert result.structured_content["network_performed"] is False, name
        assert {t.name for t in await client.list_tools()} == {
            t.name for t in await client.list_tools()
        }


@pytest.mark.asyncio
async def test_concurrent_plan_only_cross_family_calls_do_not_interfere():
    async with Client(unified_mcp) as client:
        calls = [
            ("intelligence_discover_current",
             {"execute": False, "compact": True, "limit": 5}),
            ("intelligence_plan",
             {"source": "worldbank", "country": "SI", "identifier": "SP.POP.TOTL"}),
            ("intelligence_release_lifecycle",
             {"product": "nodejs", "release": "22", "execute": False}),
            ("mjau_v3_wikidata_names",
             {"qids": ["Q95"], "languages": ["en"], "execute": False}),
            ("mjau_v3_osv_advisory_ids",
             {"ecosystem": "npm", "package": "minimist",
              "version": "0.0.8", "execute": False}),
        ]
        result = await asyncio.gather(*[
            client.call_tool(name, args) for name, args in calls
        ])
        assert all(not row.is_error for row in result)
        assert all(row.structured_content["network_performed"] is False
                   for row in result)
        assert result[0].structured_content["status"] == "planned"
        assert result[-1].structured_content["status"] == "planned"


@pytest.mark.asyncio
async def test_v3_source_crash_cannot_break_v1_v2_dispatch(monkeypatch):
    v3_module = importlib.import_module("mcp_trendpulse.mjau_v3.mcp")

    def fault(*args, **kwargs):
        raise TimeoutError("simulated V3 upstream outage")

    monkeypatch.setattr(v3_module, "osv_package_ids", fault)
    async with Client(unified_mcp) as client:
        failed = await client.call_tool("mjau_v3_osv_advisory_ids", {
            "ecosystem": "npm", "package": "minimist",
            "version": "0.0.8", "execute": True,
        }, raise_on_error=False)
        assert failed.is_error
        catalog = await client.call_tool("intelligence_source_catalog", {"wave": 1})
        assert not catalog.is_error
        assert len(catalog.structured_content.get("result", [])) >= 1
        wiki = await client.call_tool("mjau_v3_wikidata_names", {
            "qids": ["Q95"], "languages": ["en"], "execute": False,
        })
        assert not wiki.is_error
        assert wiki.structured_content["network_performed"] is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_same_live_session_combines_news_official_info_and_v3_sources():
    async with Client(unified_mcp, timeout=90) as client:
        requests = [
            ("get_news_by_keyword", {
                "keyword": "software supply chain", "max_results": 3,
                "period": 7, "headlines_only": True, "summarize": False,
            }),
            ("intelligence_release_lifecycle", {
                "product": "nodejs", "release": "22", "execute": True,
            }),
            ("mjau_v3_osv_advisory_ids", {
                "ecosystem": "npm", "package": "minimist",
                "version": "0.0.8", "execute": True,
            }),
            ("mjau_v3_wikidata_names", {
                "qids": ["Q95", "Q312"], "languages": ["en"], "name": "Google",
                "match_language": "en", "execute": True,
            }),
        ]
        output = {}
        for name, args in requests:
            result = await client.call_tool(name, args)
            assert not result.is_error, name
            output[name] = result.structured_content
        article_rows = output["get_news_by_keyword"]
        assert article_rows, "V1 must return recent RSS headlines"
        assert output["intelligence_release_lifecycle"]["release"] == "22"
        assert output["mjau_v3_osv_advisory_ids"]["status"] in {
            "source_advisories_returned", "no_returned_advisories",
        }
        assert output["mjau_v3_wikidata_names"]["status"] == "source_entities_observed"
        assert output["mjau_v3_wikidata_names"]["name_candidates"]["identity_confirmed"] is False
