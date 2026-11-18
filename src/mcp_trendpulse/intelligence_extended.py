"""Full free-only source adapters previously listed as catalogue placeholders.

All network destinations are fixed, inputs encoded, and calls use read-only
semantics. The Copernicus route is **satellite catalogue metadata**, not
climate-model retrieval. EPO requires free registered OAuth credentials.
"""

from __future__ import annotations

import base64
import json
import re
from datetime import date, timedelta
from urllib.parse import urlencode, quote
from urllib.request import Request

from mcp_trendpulse.intelligence_core import IntelligenceError, Plan, _required

SOURCES = {
    "cfpb": {
        "wave": 2, "access": "public/no-key",
        "signal": "structured financial product complaints, without narratives",
        "docs": "https://cfpb.github.io/ccdb5-api/",
        "notes": "2026 narrative removal; category counts are reporting data, not population prevalence.",
    },
    "cordis": {
        "wave": 2, "access": "public/no-key",
        "signal": "CORDIS EURIO EU-funded project titles and grant IDs",
        "docs": "https://cordis.europa.eu/about/sparql",
        "notes": "Free public SPARQL; endpoint path is undocumented, so failures must be reported.",
    },
    "copernicus": {
        "wave": 3, "access": "public/no-key",
        "signal": "Copernicus Data Space satellite collection metadata",
        "docs": "https://dataspace.copernicus.eu/news/2026-10-16-new-sfeos-stac-catalogue-endpoint",
        "notes": "Satellite catalogue only; not the Copernicus Climate Data Store reanalysis or a climate-loss measure.",
    },
    "epo": {
        "wave": 3, "access": "free registration + OAuth client",
        "signal": "EPO worldwide published patent bibliographic records",
        "docs": "https://www.epo.org/en/searching-for-patents/data/web-services/ops",
        "notes": "EPO OPS free volume 4GB/week, max roughly ten searches/minute under fair use; never paid-overage.",
    },
    "opsi_slovenia": {
        "wave": 3, "access": "public/no-key",
        "signal": "Slovenian CKAN public dataset metadata",
        "docs": "https://podatki.gov.si/data/metadata-api-docs",
        "notes": "Searches metadata; licensing and file download terms vary by dataset.",
    },
    "changedetection_local": {
        "wave": 3, "access": "self-hosted only",
        "signal": "read-only change monitor inventory on local machine",
        "docs": "https://changedetection.io/docs/api_v1/",
        "notes": "Requires your own local changedetection.io instance; never contacts hosted paid service.",
    },
}


def build(source: str, p: dict, env: dict[str, str]) -> Plan:
    keyword, limit = p["keyword"], p["limit"]
    meta = SOURCES[source]
    common = {
        "source": source, "wave": meta["wave"],
        "docs": meta["docs"], "caution": meta["notes"],
    }
    if source == "cfpb":
        # Since September 2026 narratives are removed from public responses.
        # Leave format absent: the API's format=csv is an export mode that ignores size.
        since = (date.today() - timedelta(days=365)).isoformat()
        url = ("https://www.consumerfinance.gov/data-research/"
               "consumer-complaints/search/api/v1/?"
               + urlencode({
                   "size": limit, "sort": "created_date_desc",
                   "no_aggs": "true", "no_highlight": "true",
                   "date_received_min": since,
                   **({"search_term": keyword, "field": "all"} if keyword else {}),
               }))
        return Plan(method="GET", url=url, budget_per_day=30, **common)
    if source == "cordis":
        keyword = _required(keyword, "project topic")
        # Query explicitly names the projects graph. Unbounded default-graph
        # queries silently produce empty rows; do not let that masquerade as no demand.
        literal = json.dumps(keyword, ensure_ascii=False)
        query = (
            "PREFIX eurio: <http://data.europa.eu/s66#> "
            "SELECT DISTINCT ?id ?title WHERE { "
            "GRAPH <http://data.europa.eu/s66/graph/projects> { "
            "?project a eurio:Project ; eurio:identifier ?id ; eurio:title ?title . "
            f"FILTER(CONTAINS(LCASE(STR(?title)), LCASE({literal}))) "
            "} } "
            f"LIMIT {limit}"
        )
        return Plan(
            method="POST", url="https://cordis.europa.eu/datalab/sparql/query",
            body={"query": query}, body_encoding="form",
            headers={"Accept": "application/sparql-results+json"},
            budget_per_day=12, **common,
        )
    if source == "copernicus":
        # 2026 OpenSearch STAC endpoint supports free-text collection search.
        # This is metadata only; actual raster/physical observations are separate.
        url = "https://stac.opensearch.dataspace.copernicus.eu/v1/collections"
        if keyword:
            url += "?" + urlencode({"q": keyword, "limit": limit})
        return Plan(method="GET", url=url, budget_per_day=30, **common)
    if source == "epo":
        keyword = _required(keyword, "patent CQL search")
        if not re.fullmatch(r"[A-Za-z0-9 ()\"=.+*/:-]{1,120}", keyword):
            raise IntelligenceError("EPO query must use a bounded basic CQL expression")
        url = "https://ops.epo.org/3.2/rest-services/published-data/search?" + urlencode({
            "q": keyword, "Range": f"1-{limit}",
        })
        return Plan(
            method="GET", url=url, content_type="xml", budget_per_day=40, **common,
        )
    if source == "opsi_slovenia":
        keyword = _required(keyword, "dataset search phrase")
        url = "https://podatki.gov.si/api/3/action/package_search?" + urlencode({
            "q": keyword, "rows": limit, "start": 0,
        })
        return Plan(method="GET", url=url, budget_per_day=30, **common)
    if source == "changedetection_local":
        token = env.get("TRENDPULSE_INTEL_CHANGEDETECTION_KEY", "").strip()
        if not token:
            raise IntelligenceError("Set local changedetection.io API key in TRENDPULSE_INTEL_CHANGEDETECTION_KEY")
        return Plan(
            method="GET", url="http://127.0.0.1:5000/api/v1/watch",
            headers={"x-api-key": token}, allow_loopback=True,
            budget_per_day=40, **common,
        )
    raise IntelligenceError("Unknown extended source")


def epo_oauth_token(env: dict[str, str], opener, timeout: int = 12) -> str:
    """Obtain an EPO OAuth token without putting credentials in URLs or logs."""
    consumer = env.get("TRENDPULSE_INTEL_EPO_CONSUMER_KEY", "").strip()
    secret = env.get("TRENDPULSE_INTEL_EPO_CONSUMER_SECRET", "").strip()
    if not consumer or not secret:
        raise IntelligenceError(
            "Free EPO OPS consumer key and secret required in local environment"
        )
    encoded = base64.b64encode(f"{consumer}:{secret}".encode("utf-8")).decode("ascii")
    req = Request(
        "https://ops.epo.org/3.2/auth/accesstoken",
        data=b"grant_type=client_credentials",
        headers={
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    with opener.open(req, timeout=timeout) as response:
        if response.headers.get("Content-Type", "").lower().find("json") == -1:
            raise IntelligenceError("EPO OAuth response was not JSON")
        data = json.loads(response.read(4096))
    token = data.get("access_token") if isinstance(data, dict) else None
    if not isinstance(token, str) or not 8 <= len(token) <= 2048:
        raise IntelligenceError("EPO OAuth did not supply a usable access token")
    return token
