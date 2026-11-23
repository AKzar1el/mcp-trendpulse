"""Frozen offline BM25 proxy for TrendPulse tool-description discoverability.

This script evaluates MCP descriptions only, NOT Codexify's actual search
algorithm or autonomous agent task completion. No provider/network access.
Run: python tests/qa_trendpulse_discovery_benchmark.py
"""
from __future__ import annotations

import asyncio
from collections import Counter
import json
from math import log
import re

from mcp_trendpulse.server import mcp
from mcp_trendpulse.intelligence_mcp import intel_mcp

TOKEN = re.compile(r"[a-z0-9]+")

# Original 12 tasks measured using the connected Codexify tool search before
# modifying source tool metadata. 12 further holdouts check overfitting.
TASKS = (
    ("Compare Google Trends interest over time for ChatGPT and Claude", "get_trends", "baseline"),
    ("Find Google News headlines from the last three days about AI regulation", "get_news_by_keyword", "baseline"),
    ("Show what's trending now in Slovenia", "get_trending_terms", "baseline"),
    ("Find when Python 3.12 reaches end of life", "intelligence_release_lifecycle", "baseline"),
    ("Inspect npm React 18.2.0 dependency graph", "intelligence_dependency_graph", "baseline"),
    ("Find trending Hugging Face embedding models", "intelligence_hf_catalog", "baseline"),
    ("Find published OpenSSF Scorecard for ossf/scorecard", "intelligence_repository_scorecard", "baseline"),
    ("Look at GitHub star history for vercel next.js", "intelligence_repository_star_history", "baseline"),
    ("Discover current themes across research, complaints and EU tenders without topics", "intelligence_discover_current", "baseline"),
    ("Hunt current MCP server reliability issues across public research sources", "intelligence_hunt_current", "baseline"),
    ("Evaluate opportunities with dated public buyer evidence", "intelligence_evaluate_opportunities", "baseline"),
    ("List free market intelligence sources and coverage", "intelligence_source_catalog", "baseline"),
    ("Is Python 3.12 still supported or past EOL?", "intelligence_release_lifecycle", "holdout"),
    ("When does Node.js 20 reach end of support?", "intelligence_release_lifecycle", "holdout"),
    ("Check if an old Node.js version is end of life", "intelligence_release_lifecycle", "holdout"),
    ("Read today's breaking AI regulation headlines from Google News without fetching article bodies", "get_news_by_keyword", "holdout"),
    ("Search headlines only for EU artificial intelligence law from the past week", "get_news_by_keyword", "holdout"),
    ("Find Google News story headlines mentioning climate tech across publishers", "get_news_by_keyword", "holdout"),
    ("Which countries search for Python the most?", "get_interest_by_region", "holdout"),
    ("Get the latest Google News TECHNOLOGY category feed", "get_news_by_topic", "holdout"),
    ("List market intelligence sources and free API coverage", "intelligence_source_catalog", "holdout"),
    ("Compare the npm lodash package dependency tree for a specific version", "intelligence_dependency_graph", "holdout"),
    ("Check the published OpenSSF security Scorecard for a GitHub repository", "intelligence_repository_scorecard", "holdout"),
    ("Show terms trending right now in the US", "get_trending_terms", "holdout"),
)


def rank(query: str, docs: dict[str, str]) -> list[str]:
    """A transparent, deterministic, standard BM25 *proxy*, not Codexify scoring."""
    words = {key: Counter(TOKEN.findall(value.lower())) for key, value in docs.items()}
    document_length = {k: sum(w.values()) for k, w in words.items()}
    n = len(docs)
    avg_length = sum(document_length.values()) / max(n, 1)
    tokens = set(TOKEN.findall(query.lower()))
    frequency = {term: sum(term in doc for doc in words.values()) for term in tokens}
    idf = {term: log(1 + (n - count + 0.5) / (count + 0.5)) for term, count in frequency.items()}
    def score(key: str) -> float:
        length = document_length[key]
        return sum(
            idf[term] * (cnt * 2.2 / (cnt + 1.2 * (0.25 + 0.75 * length / avg_length)))
            for term in tokens if (cnt := words[key][term])
        )
    return sorted(docs, key=lambda k: (-score(k), k))


async def collect():
    tools = list(await mcp.list_tools()) + list(await intel_mcp.list_tools())
    assert len(tools) == 34 and len({t.name for t in tools}) == 34
    return {t.name: t.name.replace("_", " ") + " " + t.description for t in tools}


def evaluate(docs: dict[str, str]) -> dict[str, object]:
    rows = []
    for query, expected, group in TASKS:
        ranked = rank(query, docs)
        rows.append({"group": group, "query": query, "expected": expected,
                     "rank": ranked.index(expected) + 1, "top3": ranked[:3]})
    totals = {}
    for group in ("baseline", "holdout", "all"):
        scope = [row for row in rows if row["group"] == group or group == "all"]
        totals[group] = {"count": len(scope), "top1": sum(r["rank"] == 1 for r in scope),
                         "top3": sum(r["rank"] <= 3 for r in scope)}
    return {"method": "offline_bm25_description_proxy_not_codexify",
            "tool_count": len(docs), "totals": totals, "tasks": rows}


if __name__ == "__main__":
    print(json.dumps(evaluate(asyncio.run(collect())), indent=2, ensure_ascii=True))
