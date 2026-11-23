"""Offline Devpost project due-diligence: evidence gaps, not commercial predictions.

This deliberately does not crawl Devpost, download code, call Google Trends,
or interpret user-provided citations as independent verification. The goal is
a repeatable handoff between existing research tools and real buyer testing.
"""
from __future__ import annotations

import ipaddress
import json
import re
from datetime import date, timedelta
from typing import Any
from urllib.parse import parse_qsl, urlsplit, urlunsplit

MAX_CANDIDATES = 20
MAX_EVIDENCE = 200
MAX_BYTES = 128 * 1024
IDENT = re.compile(r"[a-z][a-z0-9_-]{1,47}\Z")
HOST = re.compile(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?\.[a-z]{2,63}\Z")
DEVPOST_PATH = re.compile(r"/software/[a-z0-9][a-z0-9-]{1,79}/?\Z")
SENSITIVE = re.compile(
    r"(?i)(?:sk-[a-z0-9_-]{16,}|ghp_[a-z0-9_-]{16,}"
    r"|bearer\s+[a-z0-9._-]{12,}|[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,})"
)
EVIDENCE_KINDS = frozenset({
    "project_award", "project_demo", "repo_license",
    "independent_test", "problem_report", "competitor_product",
    "competitor_price", "buyer_interview", "paid_pilot",
    "operating_cost", "search_interest", "news_headline",
})
EVIDENCE_STATUSES = frozenset({"observed", "unavailable", "contradicted"})
GATES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("prize_details", ("project_award",)),
    ("functioning_demo", ("project_demo",)),
    ("reuse_rights", ("repo_license",)),
    ("independent_functional_test", ("independent_test",)),
    ("problem_evidence", ("problem_report", "buyer_interview", "paid_pilot")),
    ("competitor_landscape", ("competitor_product",)),
    ("competitor_pricing", ("competitor_price",)),
    ("buyer_discovery", ("buyer_interview", "paid_pilot")),
    ("purchase_experiment", ("paid_pilot",)),
    ("operating_costs", ("operating_cost",)),
    ("search_or_news_attention", ("search_interest", "news_headline")),
)
ACTIONS = {
    "prize_details": "Open the Devpost submission and confirm the actual prize category.",
    "functioning_demo": "Verify the demo or reproduce the advertised core user flow.",
    "reuse_rights": "Inspect the exact repository license; public GitHub does not grant reuse rights.",
    "independent_functional_test": "Run independent tests against representative inputs and failure cases.",
    "problem_evidence": "Find first-hand examples of this exact recurring workflow problem.",
    "competitor_landscape": "Identify the incumbent workflow and at least two existing alternatives.",
    "competitor_pricing": "Check actual public prices or obtain a documented vendor quote.",
    "buyer_discovery": "Interview reachable buyers about the last real occurrence and its cost.",
    "purchase_experiment": "Seek a meaningful commitment such as a paid pilot; do not infer payment.",
    "operating_costs": "Measure compute, provider, data, maintenance and integration costs for an MVP.",
    "search_or_news_attention": "Collect comparable query variants and current context; quota gaps mean unknown.",
}


def _text(value: Any, field: str, limit: int, *, required: bool = True) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text")
    text = " ".join(value.split())
    if (required and not text) or len(text) > limit or SENSITIVE.search(text):
        raise ValueError(f"{field} has invalid length, is missing, or contains sensitive-looking text")
    return text


def _day(value: Any, label: str) -> date:
    if not isinstance(value, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
        raise ValueError(f"{label} must be YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a real date") from exc


def _url(value: Any, *, devpost: bool = False) -> str:
    if not isinstance(value, str) or not 12 <= len(value) <= 1800 or SENSITIVE.search(value):
        raise ValueError("Expected a public HTTPS evidence reference without secrets")
    try:
        parts = urlsplit(value)
        host = (parts.hostname or "").lower()
        port = parts.port
        if (parts.scheme != "https" or not HOST.fullmatch(host)
                or parts.username or parts.password or parts.fragment
                or port not in (None, 443)
                or host.endswith((".local", ".internal", ".localhost", ".test"))):
            raise ValueError("Invalid reference")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError("IP references are not permitted")
        if any(re.search(r"(?i)(?:secret|token|api.?key|password|authorization|session|credential)", key)
               for key, _ in parse_qsl(parts.query, keep_blank_values=True)):
            raise ValueError("Sensitive query parameter")
        if devpost and (host != "devpost.com" or not DEVPOST_PATH.fullmatch(parts.path.lower())):
            raise ValueError("Project source must be a Devpost /software/ submission")
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Expected a public HTTPS reference without credentials or sensitive parameters") from exc
    if devpost:
        return urlunsplit(("https", "devpost.com", parts.path.lower().rstrip("/"), "", ""))
    return urlunsplit(("https", host, parts.path, parts.query, ""))


def review_devpost_candidates(
    candidates: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    *,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Build a conservative, source-linked due-diligence queue without network."""
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= MAX_CANDIDATES:
        raise ValueError("Supply 1-20 Devpost project candidates")
    if not isinstance(evidence, list) or len(evidence) > MAX_EVIDENCE:
        raise ValueError("Supply at most 200 evidence records")
    try:
        if len(json.dumps([candidates, evidence], ensure_ascii=False).encode("utf-8")) > MAX_BYTES:
            raise ValueError("Review input exceeds 128 KiB")
    except (TypeError, UnicodeError) as exc:
        raise ValueError("Review input must be bounded JSON") from exc
    today = _day(as_of, "as_of") if as_of else date.today()
    if today > date.today():
        raise ValueError("as_of cannot be in the future")

    parsed = {}
    urls = set()
    for raw in candidates:
        if not isinstance(raw, dict):
            raise ValueError("Each candidate must be an object")
        ident = _text(raw.get("id"), "candidate.id", 48)
        if IDENT.fullmatch(ident) is None or ident in parsed:
            raise ValueError("Duplicate or invalid candidate ID")
        project_url = _url(raw.get("devpost_url"), devpost=True)
        if project_url in urls:
            raise ValueError("Duplicate Devpost submission")
        urls.add(project_url)
        form = raw.get("product_type")
        if form not in {"saas", "platform", "github_repo", "hybrid"}:
            raise ValueError("product_type must be saas, platform, github_repo or hybrid")
        country = raw.get("geography", "GLOBAL")
        if not isinstance(country, str) or re.fullmatch(r"[A-Z]{2}|GLOBAL", country) is None:
            raise ValueError("geography must be a two-letter country or GLOBAL")
        repo = raw.get("repo_url", "")
        repo_url = _url(repo) if repo else ""
        if repo_url and urlsplit(repo_url).hostname != "github.com":
            raise ValueError("repo_url must point to a public GitHub repository")
        if repo_url and re.fullmatch(
            r"/[A-Za-z0-9_.-]{1,39}/[A-Za-z0-9_.-]{1,100}/?",
            urlsplit(repo_url).path,
        ) is None:
            raise ValueError("repo_url must identify a GitHub repository root")
        terms = raw.get("search_terms", [])
        if not isinstance(terms, list) or len(terms) > 5:
            raise ValueError("Provide at most five search terms per candidate")
        clean_terms = [_text(x, "search_term", 80) for x in terms]
        if len(set(x.casefold() for x in clean_terms)) != len(clean_terms):
            raise ValueError("Duplicate candidate search term")
        parsed[ident] = {
            "id": ident,
            "name": _text(raw.get("name"), "candidate.name", 120),
            "problem": _text(raw.get("problem"), "candidate.problem", 280),
            "product_type": form,
            "geography": country,
            "buyer_hypothesis": _text(raw.get("buyer_hypothesis", ""), "buyer_hypothesis", 160, required=False),
            "devpost_url": project_url,
            "repo_url": repo_url,
            "search_terms": clean_terms,
        }

    records: dict[str, list[dict[str, Any]]] = {key: [] for key in parsed}
    seen_ids = set()
    duplicate_references = 0
    seen_references = set()
    for raw in evidence:
        if not isinstance(raw, dict):
            raise ValueError("Evidence must be an object")
        ident = _text(raw.get("id"), "evidence.id", 64)
        if ident in seen_ids:
            raise ValueError("Duplicate evidence ID")
        seen_ids.add(ident)
        candidate = raw.get("candidate")
        if candidate not in parsed:
            raise ValueError("Evidence references unknown candidate")
        kind, status = raw.get("kind"), raw.get("status")
        if kind not in EVIDENCE_KINDS or status not in EVIDENCE_STATUSES:
            raise ValueError("Unknown evidence kind or status")
        observed = _day(raw.get("observed_at"), "observed_at")
        published = _day(raw["published_at"], "published_at") if raw.get("published_at") else None
        if (published is not None and published > observed) or observed > today:
            raise ValueError("Evidence cannot be published after observation or in the future")
        source = raw.get("source_url", "")
        source_url = _url(source) if source else ""
        if status != "unavailable" and not source_url:
            raise ValueError("Observed and contradicted evidence needs a source URL")
        note = _text(raw.get("note", ""), "evidence.note", 320, required=False)
        key = (candidate, kind, source_url, status, note.casefold())
        if key in seen_references:
            duplicate_references += 1
            continue
        seen_references.add(key)
        records[candidate].append({
            "kind": kind, "status": status, "source_url": source_url,
            "observed_at": observed.isoformat(),
            "published_at": published.isoformat() if published else None,
            "note": note, "stale": observed < today - timedelta(days=365),
        })

    results = []
    for candidate in parsed.values():
        items = records[candidate["id"]]
        state = {}
        for label, kinds in GATES:
            matched = [r for r in items if r["kind"] in kinds and not r["stale"]]
            if any(r["status"] == "contradicted" for r in matched):
                state[label] = "contested_caller_evidence"
            elif any(r["status"] == "observed" for r in matched):
                state[label] = "source_supplied_not_independently_verified"
            elif any(r["status"] == "unavailable" for r in matched):
                state[label] = "source_unavailable_unknown"
            else:
                state[label] = "not_supplied"
        gaps = [x for x, v in state.items()
                if v not in {"source_supplied_not_independently_verified"}]
        actions = []
        if not candidate["buyer_hypothesis"]:
            actions.append("Name a specific reachable buyer and who controls the purchasing budget.")
        if not candidate["search_terms"]:
            actions.append("Define problem-oriented query variants; project names are weak demand proxies.")
        for gap in gaps:
            if len(actions) >= 7:
                break
            actions.append(ACTIONS[gap])
        results.append({
            **candidate,
            "evidence_status": state,
            "open_evidence_gaps": gaps,
            "next_actions": actions[:7],
            "provided_evidence_count": len(items),
            "source_domains_in_caller_evidence": sorted({
                urlsplit(r["source_url"]).hostname
                for r in items if r["source_url"]
            }),
            "stale_records": sum(r["stale"] for r in items),
            "contradicted_records": sum(r["status"] == "contradicted" for r in items),
            "unavailable_records": sum(r["status"] == "unavailable" for r in items),
            "buyer_spending_independently_verified": False,
            "project_works_independently_verified": False,
            "code_reuse_rights_independently_verified": False,
            "success_probability": None,
            "decision": "research_and_independent_validation_required",
        })

    return {
        "report_type": "devpost_candidate_evidence_gap_review",
        "as_of": today.isoformat(),
        "candidate_count": len(results),
        "evidence_count": sum(len(x) for x in records.values()),
        "duplicate_evidence_ignored": duplicate_references,
        "network_performed": False,
        "source_metadata_attested_by_caller": True,
        "outcomes_and_permissions_not_independently_verified": True,
        "ranked_business_predictions": False,
        "results": results,
    }
