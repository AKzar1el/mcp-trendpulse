"""Source-only, explicitly opted-in unified V1/V2/V3 evaluation MCP.

Start from a repository checkout, NOT the published wheel:

    python -m mcp_trendpulse.mjau_v3.unified_mcp

This keeps the established community service and its lifespan/middleware,
mounts the separate V2 research tools, and adds only the two narrow V3
official-source tools. This module stays inside mjau_v3, which is excluded
from the public distribution. Never register or deploy it automatically.

Google Trends throttling is expected; V3 plan-only is the safe default.
V3 source licensing/redistribution and independent-human evaluation
remain open release gates.
"""

from __future__ import annotations

from fastmcp import FastMCP

from mcp_trendpulse.server import (
    COMMUNITY_SERVER_INSTRUCTIONS,
    lifespan as community_lifespan,
    mcp as community_mcp,
)
from mcp_trendpulse.intelligence_mcp import intel_mcp
from mcp_trendpulse.mjau_v3.mcp import mjau_v3_mcp


unified_mcp = FastMCP(
    name="trendpulse-v1-v2-v3-local-evaluation",
    instructions=(
        COMMUNITY_SERVER_INSTRUCTIONS + " This is an explicitly opted-in "
        "source-only unified V1/V2/V3 evaluation server. V2 public research "
        "is plan-only by default and never verifies paying customers. "
        "V3 Wikidata QID names and OSV advisory IDs are also plan-only by "
        "default, and require execute=True for bounded, official-source "
        "queries. Never infer verified identity, secure packages, authorized "
        "commercial reuse, customer demand, or Google Trends quota recovery "
        "from these results. Do not turn on public publishing or workers."
    ),
    lifespan=community_lifespan,
)

# Dynamic mounts preserve all existing tool names. The separate parent does
# not modify the original community/V2/V3 module-level server objects,
# so importing this optional entrypoint cannot break existing tests/callers.
unified_mcp.mount(community_mcp)
unified_mcp.mount(intel_mcp)
unified_mcp.mount(mjau_v3_mcp)


def main() -> None:
    unified_mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
