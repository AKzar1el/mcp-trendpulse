"""Prevent regressions in the frozen 33-tool offline description-search proxy.

This is not an in-product Codexify search result; actual live index/agent
selection must be independently checked after a future connector refresh.
"""
from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

from mcp_trendpulse.server import mcp
from mcp_trendpulse.intelligence_mcp import intel_mcp

suite = Path(__file__).with_name("qa_trendpulse_discovery_benchmark.py")
spec = importlib.util.spec_from_file_location("trendpulse_frozen_discovery_suite", suite)
assert spec and spec.loader
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def test_frozen_natural_language_retrieval_improves_prior_quality():
    assert len(benchmark.TASKS) == 24
    assert sum(item[2] == "baseline" for item in benchmark.TASKS) == 12
    report = benchmark.evaluate(asyncio.run(benchmark.collect()))
    assert report["tool_count"] == 33
    assert report["totals"]["all"]["top1"] >= 21
    assert report["totals"]["all"]["top3"] == 24
    assert report["totals"]["holdout"]["top1"] >= 12


def test_tool_selection_descriptions_remain_truthful_and_read_only():
    tools = {
        t.name: t
        for server in (mcp, intel_mcp)
        for t in asyncio.run(server.list_tools())
    }
    expected = {
        "intelligence_release_lifecycle": (
            "python 3.12", "node.js 20", "end of life",
            "community-curated", "execute=true",
        ),
        "get_news_by_keyword": (
            "headlines", "free-form", "headlines_only=true", "get_news_by_topic",
        ),
        "get_interest_by_region": (
            "countries", "geographic", "search interest", "get_trends",
            "not absolute demand",
        ),
    }
    for name, phrases in expected.items():
        tool = tools[name]
        doc = tool.description.lower()
        for phrase in phrases:
            assert phrase in doc, (name, phrase)
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False
    assert all(not name.startswith("mjau_v3_") for name in tools)
