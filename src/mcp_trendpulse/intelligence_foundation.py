"""Wave 1: freely accessible public baseline and demand signals."""

from __future__ import annotations

import json
from urllib.parse import urlencode, quote

from mcp_trendpulse.intelligence_core import IntelligenceError, Plan, _required

SOURCES = {
    "gdelt_latest": {
        "wave": 1, "access": "public/no-key",
        "signal": "GDELT global event 15-minute batch manifest, not keyword searches",
        "docs": "https://www.gdeltproject.org/",
        "notes": "Latest raw batch only; DOC keyword API frequently returns HTTP 429."
    },
    "eurostat": {
        "wave": 1, "access": "public/no-key", "signal": "official population and economic time series",
        "docs": "https://ec.europa.eu/eurostat/en/web/user-guides/data-browser/api-data-access/api-getting-started",
        "notes": "Requires dataset code and geographic filter; JSON-stat observations are not keyword search."
    },
    "ted": {
        "wave": 1, "access": "public/no-key", "signal": "published EU procurement notices",
        "docs": "https://docs.ted.europa.eu/api/latest/search.html",
        "notes": "Uses TED expert-query syntax; awards and tenders are distinct."
    },
    "cellar": {
        "wave": 1, "access": "public/no-key", "signal": "EU legal metadata",
        "docs": "https://op.europa.eu/en/web/cellar/cellar-data/metadata/knowledge-graph",
        "notes": "General legal-text search may be incomplete; status must be confirmed on original act."
    },
    "github_issues": {
        "wave": 1, "access": "public/no-key", "signal": "open-source problems and workarounds",
        "docs": "https://docs.github.com/en/rest/search/search",
        "notes": "GitHub issues skew toward technical users; public API has tight rate limits."
    },
    "worldbank": {
        "wave": 1, "access": "public/no-key", "signal": "official cross-country macroeconomic indicators",
        "docs": "https://datahelpdesk.worldbank.org/knowledgebase/articles/889392",
        "notes": "Requires an indicator ID; time series can be delayed or revised."
    },
}


def build(source: str, p: dict, env: dict[str, str]) -> Plan:
    keyword, limit = p["keyword"], p["limit"]
    meta = SOURCES[source]
    common = {"source": source, "wave": 1, "docs": meta["docs"], "caution": meta["notes"]}
    if source == "gdelt_latest":
        return Plan(method="GET",
                    url="https://data.gdeltproject.org/gdeltv2/lastupdate.txt",
                    content_type="text", budget_per_day=48, **common)
    if source == "eurostat":
        dataset = _required(p["dataset"], "dataset")
        country = _required(p["country"], "country")
        url = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
               + quote(dataset, safe="") + "?" + urlencode(
                   {"geo": country, "lastTimePeriod": 3, "lang": "EN"}))
        return Plan(method="GET", url=url, budget_per_day=20, **common)
    if source == "ted":
        # Expert queries are a domain-specific search language, never HTTP input.
        query = _required(keyword, "TED expert-query")
        if any(c in query for c in "\r\n{};") or len(query) > 140:
            raise IntelligenceError("Unsafe or oversized TED query")
        body = {
            "query": query, "fields": ["publication-number", "notice-title",
                                      "buyer-name", "publication-date", "notice-type"],
            "limit": limit, "page": 1, "paginationMode": "PAGE_NUMBER",
        }
        return Plan(method="POST", url="https://api.ted.europa.eu/v3/notices/search",
                    body=body, budget_per_day=20, **common)
    if source == "cellar":
        # Exact legal-title term matching via bounded SPARQL: no arbitrary user query.
        term = _required(keyword, "keyword")
        literal = json.dumps(term, ensure_ascii=False)
        sparql = (
            "PREFIX cdm: <http://publications.europa.eu/ontology/cdm#> "
            "SELECT DISTINCT ?work ?title WHERE { "
            "?work cdm:resource_legal_title ?title . "
            f"FILTER(CONTAINS(LCASE(STR(?title)), LCASE({literal}))) "
            f"}} LIMIT {limit}"
        )
        return Plan(method="POST",
                    url="https://publications.europa.eu/webapi/rdf/sparql",
                    body={"query": sparql, "format": "application/sparql-results+json"},
                    body_encoding="form", headers={"Accept": "application/sparql-results+json"},
                    budget_per_day=5, **common)
    if source == "github_issues":
        terms = _required(keyword, "keyword")
        query = f'"{terms}" is:issue is:open'
        url = "https://api.github.com/search/issues?" + urlencode(
            {"q": query, "per_page": limit, "sort": "updated", "order": "desc"})
        return Plan(method="GET", url=url, budget_per_day=12, **common)
    if source == "worldbank":
        country = _required(p["country"], "country")
        indicator = _required(p["identifier"], "World Bank indicator ID")
        if not all(part.replace(".", "").isalnum() for part in indicator.split(".")):
            raise IntelligenceError("Invalid World Bank indicator ID")
        url = f"https://api.worldbank.org/v2/country/{country}/indicator/{quote(indicator, safe='')}?" + urlencode(
            {"format": "json", "per_page": limit, "mrv": min(limit, 10)})
        return Plan(method="GET", url=url, budget_per_day=20, **common)
    raise IntelligenceError("Unknown foundation source")
