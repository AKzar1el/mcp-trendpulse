"""Keyless, bounded U.S. Federal Register document-search adapter.

Published regulatory documents are research context, not proof of legal effect,
an enforceable obligation, customer demand or a willing buyer.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from mcp_trendpulse.intelligence_core import IntelligenceError, Plan

SOURCE = "federal_register"
SOURCES = {
    SOURCE: {
        "wave": 1,
        "access": "public/no-key",
        "signal": "U.S. federal published rules, proposed rules and notices",
        "docs": "https://www.federalregister.gov/developers/documentation/api/v1",
        "notes": (
            "Published documents are not proof a proposed rule is effective, "
            "a regulation is currently binding, or a buyer has a budget. "
            "Verify legal status against the official edition and eCFR."
        ),
    },
}
# Only printable literal topical terms; never expose the provider's full
# free-form query syntax or accept user-provided hosts/paths/filters.
_TOPIC = re.compile(r"[A-Za-z0-9][A-Za-z0-9 .,/()'\-]{0,79}\Z")


def validate_topic(topic: str) -> str:
    if not isinstance(topic, str):
        raise IntelligenceError("Federal Register topic must be text")
    clean = " ".join(topic.split())
    if not _TOPIC.fullmatch(clean):
        raise IntelligenceError(
            "Federal Register topic must be 1-80 ordinary ASCII text characters"
        )
    return clean


def build(source: str, p: dict, env: dict[str, str]) -> Plan:
    if source != SOURCE:
        raise IntelligenceError("Unknown Federal Register source")
    topic = validate_topic(p["keyword"])
    lookback = p["lookback_days"] if p["lookback_days"] is not None else 30
    if isinstance(lookback, bool) or not isinstance(lookback, int) or not 7 <= lookback <= 90:
        raise IntelligenceError("Federal Register lookback must be 7-90 days")
    since = (datetime.now(timezone.utc).date() - timedelta(days=lookback - 1)).isoformat()
    # Explicit columns keep responses small. Do not fetch article bodies,
    # arbitrary user-selected fields, personal submissions or full-text XML.
    columns = (
        "document_number", "title", "publication_date", "type",
        "html_url", "effective_on", "comments_close_on",
    )
    params = [
        ("conditions[term]", topic),
        ("conditions[publication_date][gte]", since),
        ("per_page", str(p["limit"])),
        ("order", "newest"),
        *[("fields[]", column) for column in columns],
    ]
    url = "https://www.federalregister.gov/api/v1/documents.json?" + urlencode(params)
    return Plan(
        source=SOURCE, wave=1, method="GET", url=url,
        docs=SOURCES[SOURCE]["docs"], caution=SOURCES[SOURCE]["notes"],
        budget_per_day=20,
    )
