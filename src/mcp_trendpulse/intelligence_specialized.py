"""Wave 3: specialization in legal entities, energy, climate and local monitoring.

A listed source is not automatically available: some require free registration,
separately confirmed data licenses or infrastructure that must be self-hosted.
No API token is ever appended to a URL.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode

from mcp_trendpulse.intelligence_core import IntelligenceError, Plan, _required

SOURCES = {
    "gleif": {
        "wave": 3, "access": "public/no-key", "signal": "LEI entity names, status and cross-company identity",
        "docs": "https://www.gleif.org/en/lei-data/gleif-api/",
        "notes": "An LEI match or registration does not prove revenue, hiring or an unmet need.",
    },
    "ecb": {
        "wave": 3, "access": "public/no-key", "signal": "ECB economic and financial SDMX time series",
        "docs": "https://data.ecb.europa.eu/help/api/data",
        "notes": "Requires a specific dataflow and series key; bounded recent observations only.",
    },
    "entsoe": {
        "wave": 3, "access": "free registration + API token", "signal": "electricity load for a named EIC domain",
        "docs": "https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html",
        "notes": "Requires free API approval and domain EIC; reported energy load is not revenue opportunity.",
    },
    "rsshub_local": {
        "wave": 3, "access": "local self-hosted only", "signal": "site-specific public RSS via a local RSSHub installation",
        "docs": "https://github.com/DIYgod/RSSHub",
        "notes": "Only 127.0.0.1:1200 is permitted; route must be verified against RSSHub documentation.",
    },
    "copernicus": {
        "wave": 3, "access": "free registration", "signal": "climate reanalysis and physical exposure",
        "docs": "https://cds.climate.copernicus.eu/",
        "notes": "Large downloads and dataset-specific licensing; API intentionally not auto-fetched.",
    },
    "epo": {
        "wave": 3, "access": "free registered quota", "signal": "patent filing and technology maturation",
        "docs": "https://www.epo.org/en/searching-for-patents/data/web-services/ops",
        "notes": "Registered OAuth flow and quotas require separate validation; no paid fallback.",
    },
    "opsi_slovenia": {
        "wave": 3, "access": "open-data portal", "signal": "Slovenian official public datasets",
        "docs": "https://podatki.gov.si/",
        "notes": "No universal dataset API assumed; inspect license and distribution URL individually.",
    },
    "changedetection_local": {
        "wave": 3, "access": "local self-hosted only", "signal": "official-page and competitor change detection",
        "docs": "https://github.com/dgtlmoon/changedetection.io",
        "notes": "Local service and explicit watch configuration required; no website crawling is enabled.",
    },
}


def build(source: str, p: dict, env: dict[str, str]) -> Plan:
    meta = SOURCES[source]
    common = {"source": source, "wave": 3, "docs": meta["docs"], "caution": meta["notes"]}
    limit = p["limit"]
    if source in {"copernicus", "epo", "opsi_slovenia", "changedetection_local"}:
        raise IntelligenceError(
            f"{source} is catalogued for free-only use but is not fetch-enabled; "
            "configure and verify its specific public data distribution first"
        )
    if source == "gleif":
        name = _required(p["keyword"], "legal entity name")
        url = "https://api.gleif.org/api/v1/lei-records?" + urlencode({
            "filter[entity.legalName]": name, "page[size]": limit,
        })
        return Plan(method="GET", url=url, budget_per_day=15, **common)
    if source == "ecb":
        reference = _required(p["identifier"], "ECB flow/key identifier")
        if re.fullmatch(r"[A-Z0-9_]{1,16}/[A-Za-z0-9._-]{3,100}", reference) is None:
            raise IntelligenceError("ECB identifier must be FLOW/series-key, for example EXR/D.USD.EUR.SP00.A")
        url = "https://data-api.ecb.europa.eu/service/data/" + quote(reference, safe="/.") + "?" + urlencode({
            "format": "csvdata", "lastNObservations": min(limit, 10),
            "detail": "dataonly",
        })
        return Plan(method="GET", url=url, content_type="csv", budget_per_day=12, **common)
    if source == "entsoe":
        domain = _required(p["identifier"], "ENTSO-E EIC domain")
        if re.fullmatch(r"[0-9A-Z-]{16}", domain) is None:
            raise IntelligenceError("ENTSO-E domain must be a 16-character EIC code")
        token = env.get("TRENDPULSE_INTEL_ENTSOE_TOKEN", "").strip()
        if not token:
            raise IntelligenceError("ENTSO-E free-registration token is required; paid tokens are not supported")
        end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        start = end - timedelta(hours=24)
        url = "https://web-api.tp.entsoe.eu/api?" + urlencode({
            "documentType": "A65", "processType": "A16",
            "outBiddingZone_Domain": domain, "periodStart": start.strftime("%Y%m%d%H%M"),
            "periodEnd": end.strftime("%Y%m%d%H%M"),
        })
        return Plan(method="GET", url=url, content_type="xml",
                    headers={"SECURITY_TOKEN": token}, budget_per_day=6, **common)
    if source == "rsshub_local":
        route = _required(p["identifier"], "RSSHub route")
        if re.fullmatch(r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_.-]+){0,5}", route) is None or ".." in route:
            raise IntelligenceError("RSSHub route must be a bounded public slash-separated route")
        return Plan(method="GET", url=f"http://127.0.0.1:1200/{route}",
                    content_type="xml", budget_per_day=20, allow_loopback=True, **common)
    raise IntelligenceError("Unknown specialized source")
