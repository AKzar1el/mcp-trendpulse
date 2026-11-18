"""Wave 2: company hiring, complaints, corporate disclosures and research signals.

Every request is read-only and bounded. Public job boards reveal investment in
work, not guaranteed purchasing intent or the existence of a SaaS opportunity.
"""

from __future__ import annotations

import base64
import re
from urllib.parse import quote, urlencode

from mcp_trendpulse.intelligence_core import IntelligenceError, Plan, _required

SOURCES = {
    "greenhouse": {
        "wave": 2, "access": "public/no-key", "signal": "company-specific open job responsibilities",
        "docs": "https://developers.greenhouse.io/job-board.html",
        "notes": "Requires a known public board slug; postings are not a universe of all employers."
    },
    "lever": {
        "wave": 2, "access": "public/no-key", "signal": "company-specific open job responsibilities",
        "docs": "https://github.com/lever/postings-api",
        "notes": "Only published public postings; board slug needed; hiring is not vendor budget."
    },
    "ashby": {
        "wave": 2, "access": "public/no-key", "signal": "company-specific open job responsibilities",
        "docs": "https://developers.ashbyhq.com/",
        "notes": "Only published public postings for a named board."
    },
    "smartrecruiters": {
        "wave": 2, "access": "public/no-key", "signal": "public jobs for a named company",
        "docs": "https://developers.smartrecruiters.com/",
        "notes": "Results may be paginated and omit the full job description."
    },
    "sec_companyfacts": {
        "wave": 2, "access": "public/no-key; descriptive User-Agent required",
        "signal": "reported corporate financial facts",
        "docs": "https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
        "notes": "XBRL financial data are not itemized demand signals; named company CIK needed."
    },
    "openalex": {
        "wave": 2, "access": "free limited daily allowance; no paid fallback",
        "signal": "scholarly publications and emerging research topics",
        "docs": "https://help.openalex.org/api/",
        "notes": "Bibliographic activity is not market adoption; hard local cap prevents exhaustion."
    },
    "companies_house": {
        "wave": 2, "access": "free registration key", "signal": "UK company registrations and filings",
        "docs": "https://developer.company-information.service.gov.uk/",
        "notes": "Requires a free Companies House API key; search alone does not establish spending."
    },
    "cfpb": {
        "wave": 2, "access": "public; endpoint requires live revalidation",
        "signal": "U.S. consumer financial product complaint patterns",
        "docs": "https://cfpb.github.io/api/ccdb/release-notes.html",
        "notes": "2026 changes removed narratives and JSON exports; intentionally not auto-fetched."
    },
    "cordis": {
        "wave": 2, "access": "public bulk datasets / linked open data",
        "signal": "EU research grant projects and funded topics",
        "docs": "https://cordis.europa.eu/projects/en",
        "notes": "Bulk dataset ingestion deliberately separate to avoid huge network downloads."
    },
    "usaspending": {
        "wave": 2, "access": "public/no-key; expert filters needed",
        "signal": "U.S. federal awards and actual expenditure",
        "docs": "https://api.usaspending.gov/docs/endpoints",
        "notes": "Procurement results require award-type and fiscal-year normalization."
    },
}


def build(source: str, p: dict, env: dict[str, str]) -> Plan:
    limit, keyword = p["limit"], p["keyword"]
    meta = SOURCES[source]
    common = {"source": source, "wave": 2, "docs": meta["docs"], "caution": meta["notes"]}
    if source in {"cfpb", "cordis", "usaspending"}:
        # Public access alone does not justify guessing a changed API contract.
        raise IntelligenceError(
            f"{source}: catalogued but not fetch-enabled pending schema/size verification; "
            "use the official free data source directly"
        )
    if source in {"greenhouse", "lever", "ashby", "smartrecruiters"}:
        board = _required(p["company"], "company board slug")
        if source == "greenhouse":
            url = f"https://boards-api.greenhouse.io/v1/boards/{quote(board, safe='')}/jobs?content=true"
        elif source == "lever":
            url = f"https://api.lever.co/v0/postings/{quote(board, safe='')}?mode=json"
        elif source == "ashby":
            url = f"https://api.ashbyhq.com/posting-api/job-board/{quote(board, safe='')}?includeCompensation=true"
        else:
            url = (f"https://api.smartrecruiters.com/v1/companies/{quote(board, safe='')}/postings?"
                   + urlencode({"limit": limit, "offset": 0}))
        return Plan(method="GET", url=url, budget_per_day=20, **common)
    if source == "sec_companyfacts":
        cik = _required(p["identifier"], "numeric SEC CIK")
        if not re.fullmatch(r"\d{1,10}", cik):
            raise IntelligenceError("SEC CIK must contain 1-10 digits")
        agent = env.get("TRENDPULSE_INTEL_SEC_USER_AGENT", "").strip()
        if not agent or "@" not in agent or len(agent) > 180:
            raise IntelligenceError("Configure TRENDPULSE_INTEL_SEC_USER_AGENT with a descriptive contact")
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json"
        return Plan(method="GET", url=url, headers={"User-Agent": agent}, budget_per_day=8, **common)
    if source == "openalex":
        term = _required(keyword, "keyword")
        url = "https://api.openalex.org/works?" + urlencode({
            "search": term, "per_page": limit, "select": "id,display_name,publication_year,cited_by_count,doi,primary_location"
        })
        return Plan(method="GET", url=url, budget_per_day=5, **common)
    if source == "companies_house":
        term = _required(keyword, "keyword")
        key = env.get("TRENDPULSE_INTEL_COMPANIES_HOUSE_KEY", "").strip()
        if not key:
            raise IntelligenceError("Free Companies House key required; no paid entitlement is needed")
        auth = base64.b64encode(f"{key}:".encode()).decode("ascii")
        url = "https://api.company-information.service.gov.uk/search/companies?" + urlencode({
            "q": term, "items_per_page": limit, "start_index": 0
        })
        return Plan(method="GET", url=url, headers={"Authorization": f"Basic {auth}"},
                    budget_per_day=15, **common)
    raise IntelligenceError("Unknown commercial source")
