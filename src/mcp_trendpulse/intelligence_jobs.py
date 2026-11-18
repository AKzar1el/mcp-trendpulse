"""Explain job-board responsibilities as *hypotheses* about business pain.

Pure offline analysis only: does not invent budgets, contact companies, or infer
a vacancy count is equal to a market size. Source URLs are retained for review.
"""

from __future__ import annotations

import html
import re
from collections import defaultdict
from html.parser import HTMLParser
from typing import Any

PAIN_PATTERNS = {
    "manual_work": r"\b(manual(?:ly)?|spreadsheet|copy.and.paste|data entry|repetitive|time.consuming)\b",
    "integration": r"\b(integrat(?:e|ion|ions|ing)|interoperab(?:le|ility)|data silo|sync(?:hroniz(?:e|ation))?)\b",
    "compliance": r"\b(compliance|regulatory|audit(?:ing)?|reporting obligation|gdpr|risk assessment)\b",
    "reliability": r"\b(incident|downtime|outage|error prone|reliability|observability|monitor(?:ing)?)\b",
    "cost_pressure": r"\b(cost optimiz(?:e|ation)|reduce costs?|budget constraints?|operational efficiency)\b",
    "customer_operations": r"\b(customer support|ticket triage|escalation|customer onboarding|case management)\b",
}


class _StripHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str):
        self.parts.append(data)


def _plain(value: Any) -> str:
    raw = html.unescape(str(value or ""))
    if "<" in raw and ">" in raw:
        parser = _StripHTML()
        parser.feed(raw)
        raw = " ".join(parser.parts)
    return " ".join(raw.split())[:12000]


def normalize_jobs(source: str, company: str, response: Any, limit: int = 100) -> list[dict[str, Any]]:
    """Unify public Greenhouse/Lever/Ashby/SmartRecruiters board records."""
    if source not in {"greenhouse", "lever", "ashby", "smartrecruiters"}:
        raise ValueError("Unsupported public ATS board")
    if not company or not company.strip():
        raise ValueError("company board slug is required")
    if not 1 <= limit <= 100:
        raise ValueError("limit must be 1..100")
    if source == "lever":
        raw = response
    elif source == "smartrecruiters":
        raw = response.get("content", []) if isinstance(response, dict) else []
    elif source == "greenhouse" and isinstance(response, dict) and response.get("id"):
        raw = [response]  # One full description from greenhouse_job.
    else:
        raw = response.get("jobs", []) if isinstance(response, dict) else []
    if not isinstance(raw, list):
        raise ValueError("Invalid public ATS response")
    jobs = []
    seen = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        ident = str(item.get("id", "")).strip()
        if not ident or ident in seen:
            continue
        seen.add(ident)
        if source == "greenhouse":
            title = item.get("title", "")
            description = item.get("content", "")
            url = item.get("absolute_url", "")
            location = (item.get("location") or {}).get("name", "") if isinstance(item.get("location"), dict) else ""
        elif source == "lever":
            title = item.get("text", "")
            description = item.get("descriptionPlain", item.get("description", ""))
            url = item.get("hostedUrl", "")
            location = (item.get("categories") or {}).get("location", "") if isinstance(item.get("categories"), dict) else ""
        elif source == "ashby":
            title = item.get("title", "")
            description = item.get("descriptionPlain", item.get("descriptionHtml", ""))
            url = item.get("jobUrl", "")
            location = item.get("location", "")
        else:
            title = item.get("name", "")
            description = item.get("jobAd", "")
            url = item.get("ref", "")
            location = (item.get("location") or {}).get("city", "") if isinstance(item.get("location"), dict) else ""
        jobs.append({
            "id": ident, "source": source, "company": company,
            "title": _plain(title)[:200], "location": _plain(location)[:120],
            "description": _plain(description), "url": str(url)[:1000],
            "posted_at": str(item.get("updated_at", item.get("publishedAt", "")))[:40],
        })
        if len(jobs) >= limit:
            break
    return jobs


def extract_job_pains(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    """Conservative signals with attributable quotations, not business claims."""
    if not isinstance(jobs, list) or len(jobs) > 500:
        raise ValueError("Provide at most 500 normalized jobs")
    by_pain = defaultdict(lambda: {"postings": 0, "companies": set(), "examples": []})
    checked = 0
    for job in jobs:
        if not isinstance(job, dict):
            continue
        description = _plain(job.get("description", ""))
        if not description:
            continue
        checked += 1
        for label, pattern in PAIN_PATTERNS.items():
            match = re.search(pattern, description, flags=re.IGNORECASE)
            if match is None:
                continue
            pain = by_pain[label]
            pain["postings"] += 1
            pain["companies"].add(str(job.get("company", "")))
            if len(pain["examples"]) < 4:
                start = max(0, match.start() - 110)
                end = min(len(description), match.end() + 150)
                pain["examples"].append({
                    "company": job.get("company", ""),
                    "role": job.get("title", ""),
                    "posting_url": job.get("url", ""),
                    "excerpt": description[start:end],
                })
    sorted_pains = []
    for label, record in sorted(by_pain.items(), key=lambda p: (-len(p[1]["companies"]), -p[1]["postings"], p[0])):
        sorted_pains.append({
            "category": label, "postings": record["postings"],
            "distinct_companies": len(record["companies"]),
            "examples": record["examples"],
            "interpretation": "Employer-described responsibility; not proof of budget for an external product.",
        })
    return {
        "postings_received": len(jobs), "descriptions_examined": checked,
        "pain_hypotheses": sorted_pains,
        "validation_needed": [
            "Compare the same category across independent employers and time windows.",
            "Find procurement, spending, customer interview or paid-pilot evidence.",
            "Distinguish hiring to build internally from willingness to buy externally.",
            "Review the role's full description before inferring a business problem.",
        ],
    }
