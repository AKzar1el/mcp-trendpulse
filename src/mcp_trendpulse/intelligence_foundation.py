"""Wave 1: freely accessible public baseline and demand signals."""

from __future__ import annotations

import json
import re
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
    "github_repositories": {
        "wave": 1, "access": "public/keyless or existing GitHub auth",
        "signal": "public open-source repository alternatives, not feature equivalence",
        "docs": "https://docs.github.com/en/rest/search/search",
        "notes": "First-page public repositories; descriptions and stars do not prove direct competition.",
    },
    "hf_dataset_details": {
        "wave": 1, "access": "public/no-key",
        "signal": "public dataset license, gating and maintenance metadata",
        "docs": "https://huggingface.co/docs/hub/api",
        "notes": "A public card is not permission to reuse contents; gated and license-unknown remain unverified.",
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
            "query": query, "fields": [
                "publication-number", "publication-date", "notice-type",
                "notice-title", "title-proc", "official-language",
                "buyer-name", "buyer-country", "buyer-identifier",
                "procedure-identifier", "classification-cpv",
                "main-classification-proc",
                "deadline-receipt-tender-date-lot",
                "estimated-value-proc", "estimated-value-cur-proc",
            ],
            "limit": limit, "page": 1, "paginationMode": "PAGE_NUMBER",
        }
        return Plan(method="POST", url="https://api.ted.europa.eu/v3/notices/search",
                    body=body, budget_per_day=20, **common)
    if source == "cellar":
        # CDM titles live on expressions, not on legal Work nodes.
        # Virtuoso indexed full-text search avoids unbounded title scans.
        term = _required(keyword, "legal-title keyword")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 -]{0,59}", term):
            raise IntelligenceError("CELLAR legal-title keywords must be alphanumeric words")
        full_text = json.dumps("'" + term.strip().lower() + "'")
        sparql = (
            "PREFIX cdm: <http://publications.europa.eu/ontology/cdm#> "
            "SELECT DISTINCT ?work ?title WHERE { "
            "?expr cdm:expression_belongs_to_work ?work ; "
            "cdm:expression_uses_language "
            "<http://publications.europa.eu/resource/authority/language/ENG> ; "
            "cdm:expression_title ?title . "
            f"?title bif:contains {full_text} . "
            f"}} LIMIT {limit}"
        )
        return Plan(method="POST",
                    url="https://publications.europa.eu/webapi/rdf/sparql",
                    body={"query": sparql, "format": "application/sparql-results+json"},
                    body_encoding="form", headers={"Accept": "application/sparql-results+json"},
                    budget_per_day=5, **common)
    if source == "github_issues":
        terms = _required(keyword, "keyword")
        query = f'"{terms}" is:issue is:open is:public'
        # Created recently, not merely an old issue updated this week.
        if p["lookback_days"] is not None:
            from datetime import datetime, timedelta, timezone

            cutoff = datetime.now(timezone.utc).date() - timedelta(
                days=p["lookback_days"]
            )
            query += f" created:>={cutoff.isoformat()}"
        owner_repo = p["identifier"]
        if owner_repo:
            # Narrow extremely large issue-search responses to one named public
            # repository. Free-text phrases cannot inject GitHub search operators.
            if (".." in owner_repo or
                    re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,38}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", owner_repo) is None):
                raise IntelligenceError("GitHub repo selector must be owner/repo")
            query += f" repo:{owner_repo}"
        params = {"q": query, "per_page": limit}
        # GitHub defaults to best match when sort is omitted.
        if not p.get("relevance_first"):
            params.update({
                "sort": "created" if p["lookback_days"] is not None else "updated",
                "order": "desc",
            })
        url = "https://api.github.com/search/issues?" + urlencode(params)
        return Plan(method="GET", url=url, budget_per_day=12, **common)
    if source == "github_repositories":
        term = _required(keyword, "repository research phrase")
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 .+_-]{2,79}", term) is None:
            raise IntelligenceError("Repository search needs a plain 3-80 character phrase")
        url = "https://api.github.com/search/repositories?" + urlencode({
            "q": term + " in:name,description is:public", "per_page": min(limit, 10),
        })
        return Plan(method="GET", url=url, budget_per_day=12, **common)
    if source == "hf_dataset_details":
        dataset_id = _required(p["identifier"], "public HF dataset owner/name")
        if re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}/[A-Za-z0-9][A-Za-z0-9_.-]{0,95}",
            dataset_id,
        ) is None or ".." in dataset_id:
            raise IntelligenceError("Dataset must use a public Hugging Face owner/name ID")
        # Hugging Face's default dataset-info response may exceed the 256 KiB
        # collector ceiling due to large file manifests; request metadata only.
        fields = (
            "cardData", "createdAt", "lastModified", "gated",
            "private", "likes", "downloads",
        )
        url = "https://huggingface.co/api/datasets/" + dataset_id + "?" + urlencode(
            [("expand[]", name) for name in fields],
        )
        return Plan(method="GET", url=url, budget_per_day=6, **common)
    if source == "worldbank":
        country = _required(p["country"], "country")
        indicator = _required(p["identifier"], "World Bank indicator ID")
        if not all(part.replace(".", "").isalnum() for part in indicator.split(".")):
            raise IntelligenceError("Invalid World Bank indicator ID")
        url = f"https://api.worldbank.org/v2/country/{country}/indicator/{quote(indicator, safe='')}?" + urlencode(
            {"format": "json", "per_page": limit, "mrv": min(limit, 10)})
        return Plan(method="GET", url=url, budget_per_day=20, **common)
    raise IntelligenceError("Unknown foundation source")
