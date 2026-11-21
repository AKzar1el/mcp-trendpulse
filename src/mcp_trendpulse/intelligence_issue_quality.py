"""Conservative, deterministic quality screening for public GitHub issue samples.

Issue metadata are search results, never proof of customer demand. The body is
read only in-memory for bounded classification: raw narrative, author identity
and arbitrary links are not projected to the intelligence tool.
"""
from __future__ import annotations

import re
from typing import Any

_PROMO = re.compile(
    r"\b(?:market\s+(?:size|forecast|report|growth|outlook|analysis)|"
    r"market.{0,75}\b(?:to\s+reach|worth|valued\s+at|projected\s+to|"
    r"cagr|million|billion)|"
    r"(?:cagr|compound annual growth rate)|"
    r"(?:million|billion)\s+by\s+20\d{2})\b",
    re.IGNORECASE,
)
_HYPOTHETICAL = re.compile(
    r"\b(?:hypothetical|fictional|imaginary|thought experiment|"
    r"not based on actual|no real[- ]world observations|"
    r"not claim that any .* has been collected)\b",
    re.IGNORECASE,
)
_REPRO = re.compile(
    r"\b(?:steps to reproduce|reproduction steps|actual behavior|"
    r"observed behavior|expected vs actual|reproducible|"
    r"users (?:report|experience)|customer (?:reports|experiences))\b",
    re.IGNORECASE,
)
_FAILURE = re.compile(
    r"\b(?:fails?|failed|failure|crash(?:es|ed)?|broken|"
    r"regression|incorrect|timeout|cannot|error|bug)\b",
    re.IGNORECASE,
)
_GITHUB_ISSUE_URL = re.compile(
    r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/issues/[0-9]+\Z"
)
_IMPLEMENTATION = re.compile(
    r"^(?:extract|refactor|implement|migrate|add|write|create|"
    r"document|publish|release|split|move)\b",
    re.IGNORECASE,
)


def classify_github_issue(
    title: Any, body: Any = None, url: Any = None,
) -> str:
    """Return coarse evidence class, never a computed market confidence."""
    t = " ".join(title.split())[:250] if isinstance(title, str) else ""
    # A whole GitHub issue may be long. Check bounded, in-memory content only.
    b = body[:6000] if isinstance(body, str) else ""
    if _PROMO.search(t) or _PROMO.search(b[:1500]):
        return "promotional_market_claim"
    if _HYPOTHETICAL.search(b) or _HYPOTHETICAL.search(t):
        return "hypothetical_or_unverified_design"
    if isinstance(url, str):
        match = _GITHUB_ISSUE_URL.fullmatch(url)
        if match and match.group(1).casefold() == match.group(2).casefold():
            return "profile_repository_work_item"
    if (_REPRO.search(b) and _FAILURE.search(t + " " + b[:3000])):
        return "reported_operational_problem"
    if _IMPLEMENTATION.search(t):
        return "internal_implementation_work_item"
    return "unverified_public_issue"


# Promotions and hypothetical documents can be useful contextual research,
# but may not count as a fresh operational problem or new purchasing activity.
EXCLUDED_FROM_CURRENT_HUNT = frozenset({
    "promotional_market_claim",
    "hypothetical_or_unverified_design",
    "profile_repository_work_item",
    "internal_implementation_work_item",
})
