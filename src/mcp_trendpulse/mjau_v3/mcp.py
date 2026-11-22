"""Separate opt-in, minimal-data MJAU v3 MCP; does not modify the live 16 tools.

Start explicitly with: python -m mcp_trendpulse.mjau_v3.mcp
Default is plan-only (execute=False). No scheduled workers or paid APIs.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from mcp_trendpulse.mjau_v3.budgeted_sources import (
    osv_package_ids, wikidata_identity,
)

mjau_v3_mcp = FastMCP(
    name="trendpulse-mjau-v3-optional-free-sources",
    instructions=(
        "An explicitly started, credential-free, opt-in read-only source adjunct. "
        "Two fixed official sources only: CC0 Wikidata QID names and OSV "
        "package/version advisory identifiers. Defaults to plan-only; execute=True "
        "spends one durable local UTC-day budget or returns cached validated metadata. "
        "Never upload private package lists or secrets, and do not interpret OSV "
        "missing records as secure packages. Wikidata text matching is not verified "
        "identity. OSV original feed licenses differ; source attribution review "
        "and possible commercial-reuse permission remain mandatory. "
        "No raw OSV descriptions, exploit instructions, business conclusions or "
        "automatic remediation are included. This separate server does not "
        "extend the regular TrendPulse MCP installation."
    ),
)
READ_ONLY = {
    "readOnlyHint": True,
    "openWorldHint": True,
    "destructiveHint": False,
}


@mjau_v3_mcp.tool(
    description=(
        "Return exactly 1-3 explicit Wikidata QIDs' bounded labels, aliases "
        "and descriptions in 1-6 supported languages. Optional exact text "
        "candidate comparison never confirms identity. Plan-only unless "
        "execute=True; one fixed-origin CC0 public request within UTC-day budget."
    ),
    annotations=READ_ONLY,
)
def mjau_v3_wikidata_names(
    qids: list[str],
    languages: list[str],
    name: str = "",
    match_language: str = "en",
    execute: bool = False,
) -> dict[str, Any]:
    return wikidata_identity(
        qids, languages, name=name, match_language=match_language,
        execute=execute,
    )


@mjau_v3_mcp.tool(
    description=(
        "Return factual OSV advisory IDs and modification dates only for "
        "a single exact PyPI/npm package+version; source ID != independent "
        "vulnerability and empty results != secure. Plan-only unless execute=True; "
        "fixed HTTPS /v1/querybatch endpoint, bounded output and persistent budget. "
        "Do not infer commercial redistribution permission from advisory ID prefixes."
    ),
    annotations=READ_ONLY,
)
def mjau_v3_osv_advisory_ids(
    ecosystem: str,
    package: str,
    version: str,
    execute: bool = False,
) -> dict[str, Any]:
    return osv_package_ids(
        ecosystem, package, version, execute=execute,
    )


def main() -> None:
    mjau_v3_mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
