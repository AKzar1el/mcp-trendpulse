"""Bounded, source-linked concept research; not customer-demand validation.

All concept searches include Hacker News and Stack Overflow. Their existing
read-only adapters own their own cache, cooldown and daily quotas; the caller
can never silently turn them off. GitHub hybrid issues use the authenticated
REST API when an existing environment token is available, with honest lexical
fallback reporting (never masquerading as hybrid). No paid service or scraper.
"""
from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from contextlib import closing
from typing import Any
from urllib.parse import urlencode, urlsplit

from mcp_trendpulse.intelligence_core import BudgetCache, Plan, collect, plan_source
from mcp_trendpulse.intelligence_hn_algolia import discover_hn_discussions
from mcp_trendpulse.intelligence_stackexchange import discover_stackoverflow_questions

_TERM = re.compile(r"[A-Za-z0-9][A-Za-z0-9 .+_-]{2,79}\Z")
_OWNER = r"[A-Za-z0-9][A-Za-z0-9_.-]{0,38}"
_REPO = r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}"
_ISSUE_URL = re.compile(rf"https://github[.]com/{_OWNER}/{_REPO}/issues/[1-9][0-9]*\Z")
_REPO_URL = re.compile(rf"https://github[.]com/{_OWNER}/{_REPO}\Z")
_WORDS = re.compile(r"[a-z0-9]{3,}", re.ASCII)
_STOP = frozenset(("the", "and", "for", "with", "from", "into", "using", "web", "app",
                   "can", "how", "this", "that", "about", "are"))
_MAX_ROWS = 10


def _concept(value: str) -> str:
    if not isinstance(value, str) or _TERM.fullmatch(value) is None or value != value.strip():
        raise ValueError("Concept must be a plain 3-80 character ASCII research phrase")
    return value


def _tag_for(concept: str, stack_tag: str | None) -> tuple[str, bool]:
    if stack_tag is not None:
        if (not isinstance(stack_tag, str)
                or re.fullmatch(r"[a-z0-9][a-z0-9.+#-]{1,34}", stack_tag) is None):
            raise ValueError("Use a single lowercase Stack Overflow technology tag")
        return stack_tag, False
    words = set(_WORDS.findall(concept.lower()))
    if "python" in words:
        return "python", True
    if "firebase" in words:
        return "firebase", True
    if "chrome" in words or "extension" in words:
        return "google-chrome-extension", True
    return "javascript", True


def _headers(execute: bool) -> dict[str, str]:
    if not execute:
        return {}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if isinstance(token, str) and 8 <= len(token) <= 4096 and all(32 <= ord(c) < 127 for c in token):
        return {"Authorization": f"Bearer {token}"}
    return {}


def _github_hybrid_plan(term: str, days: int, limit: int, execute: bool) -> Plan:
    original = plan_source("github_issues", keyword=term, limit=limit, lookback_days=days)
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()
    # Unquoted natural language is essential: quoted-only searches are lexical.
    query = f"{term} is:issue is:public created:>={cutoff}"
    url = "https://api.github.com/search/issues?" + urlencode({
        "q": query, "search_type": "hybrid", "per_page": limit,
    })
    return replace(
        original, url=url, headers={**original.headers, **_headers(execute)},
        caution=("GitHub hybrid relevance is not independently verified issue pain. "
                 "Provider may fall back to lexical; inspect returned search_type. "
                 "Authenticated results require explicit public repository visibility."),
    )


def _other_plan(source: str, *, phrase: str = "", dataset: str = "",
                limit: int = 8, execute: bool = False) -> Plan:
    plan = plan_source(source, keyword=phrase, identifier=dataset, limit=limit)
    if source == "github_repositories":
        plan = replace(plan, headers={**plan.headers, **_headers(execute)})
    return plan


def _metadata(response: Any) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(response, dict):
        return "invalid_response", {}, []
    status = response.get("status", "unavailable")
    if not isinstance(status, str) or len(status) > 70:
        status = "unavailable"
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    observations = response.get("observations")
    rows = observations.get("sample") if isinstance(observations, dict) else []
    rows = rows if isinstance(rows, list) else []
    return status, data, [r for r in rows[:_MAX_ROWS] if isinstance(r, dict)]


def _issues(response: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    status, data, sample = _metadata(response)
    mode = data.get("search_type")
    output = []
    for r in sample:
        link, title = r.get("html_url"), r.get("title")
        if (not isinstance(link, str) or _ISSUE_URL.fullmatch(link) is None
                or not isinstance(title, str) or not 2 <= len(title) <= 180
                or r.get("pull_request") is not None):
            continue
        output.append({
            "source": "github_hybrid_issues", "title": title, "url": link,
            "created_at": r.get("created_at"), "issue_evidence_type": r.get("issue_evidence_type"),
            "semantic_match_not_human_confirmed": True,
        })
    return {
        "source": "github_hybrid_issues", "status": status,
        "requested_search_type": "hybrid",
        "effective_search_type": mode if mode in {"hybrid", "lexical", "semantic"} else "unverified",
        "fallback_reason": data.get("fallback_reason"),
        "source_reported_total_matches": data.get("total_count"),
        "sample_complete": False, "records": len(output),
        "cache_hit": bool(response.get("cache_hit")),
        "requires_existing_github_auth": status == "unavailable" and response.get("http_status") == 401,
    }, output


def _repositories(response: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    status, data, sample = _metadata(response)
    output = []
    for r in sample:
        link, title = r.get("html_url"), r.get("full_name")
        if (not isinstance(link, str) or _REPO_URL.fullmatch(link) is None
                or not isinstance(title, str) or len(title) > 145):
            continue
        desc = r.get("description")
        output.append({
            "source": "github_repositories", "title": title,
            "description": desc[:220] if isinstance(desc, str) else None,
            "url": link, "updated_at": r.get("updated_at"),
            "stars": r.get("stargazers_count") if type(r.get("stargazers_count")) is int else None,
            "archived": r.get("archived") is True,
            "fork": r.get("fork") is True,
            "feature_equivalence_verified": False,
        })
    return {
        "source": "github_repositories", "status": status,
        "source_reported_total_matches": data.get("total_count"),
        "sample_complete": False, "records": len(output),
        "cache_hit": bool(response.get("cache_hit")),
    }, output


def _community_query(concept: str) -> str:
    """Focus scarce first-page community queries on a two-term problem, not a long sentence."""
    words = concept.split()
    return " ".join(words[-2:]) if len(words) > 2 else concept


def _devpost_urls(links: list[str] | None) -> list[dict[str, Any]]:
    if links is None:
        return []
    if not isinstance(links, list) or len(links) > 8:
        raise ValueError("Supply at most eight direct Devpost software project links")
    result = []
    for value in links:
        if not isinstance(value, str):
            raise ValueError("Devpost links must be canonical HTTPS project URLs")
        parts = urlsplit(value)
        if (parts.scheme != "https" or parts.hostname != "devpost.com"
                or parts.netloc != "devpost.com" or parts.query or parts.fragment
                or re.fullmatch(r"/software/[a-z0-9][a-z0-9-]{1,89}", parts.path) is None):
            raise ValueError("Only direct https://devpost.com/software/slug references are accepted")
        if value in [r["url"] for r in result]:
            continue
        result.append({
            "source": "devpost_caller_reference", "url": value,
            "title": parts.path.split("/")[-1].replace("-", " "),
            "project_retrieved": False, "feature_equivalence_verified": False,
            "manual_reference_not_independent_source_evidence": True,
        })
    return result


def _competitor_shortlist(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": row.get("title"), "url": row.get("url"),
            "source": row.get("source"),
            "feature_equivalence_verified": False,
            "review_question": "Does this project already solve the same task end-to-end?",
        }
        for row in records
        if row.get("source") in {"github_repositories", "devpost_caller_reference"}
    ][:12]


def _community(query: str, tag: str, limit: int, days: int,
               execute: bool, cache: BudgetCache | None):
    try:
        hn = discover_hn_discussions(
            query=query, tag="story", days=min(days, 30),
            limit=min(limit, 10), execute=execute, cache=cache,
        )
    except (OSError, TypeError, ValueError, sqlite3.Error):
        hn = {"source": "hacker_news_algolia", "status": "unavailable",
              "records": [], "requests_attempted": 0}
    # Always attempt the Stack Exchange adapter independently of HN failures.
    try:
        so = discover_stackoverflow_questions(
            tag=tag, term=query, days=min(days, 30),
            limit=min(limit, 10), execute=execute, cache=cache,
        )
    except (OSError, TypeError, ValueError, sqlite3.Error):
        so = {"source": "stackexchange_question_mentions", "status": "unavailable",
              "questions": [], "requests_attempted": 0}
    rows = []
    for row in hn.get("records", [])[:_MAX_ROWS]:
        if not isinstance(row, dict):
            continue
        link, title = row.get("hn_url"), row.get("title")
        if isinstance(link, str) and re.fullmatch(r"https://news[.]ycombinator[.]com/item[?]id=[1-9][0-9]*", link) and isinstance(title, str):
            rows.append({
                "source": "hacker_news_algolia", "title": title,
                "url": link, "created_at": row.get("created_at"),
                "discussion_not_buyer_validation": True,
            })
    for row in so.get("questions", [])[:_MAX_ROWS]:
        if not isinstance(row, dict):
            continue
        title, qid = row.get("title"), row.get("question_id")
        if isinstance(title, str) and type(qid) is int and qid > 0:
            rows.append({
                "source": "stackexchange_question_mentions", "title": title,
                "url": f"https://stackoverflow.com/questions/{qid}",
                "created_at_epoch": row.get("creation_date"),
                "question_not_buyer_validation": True,
            })
    coverage = [
        {
            "source": "hacker_news_algolia", "status": hn.get("status"),
            "query": query, "query_provenance": "auto_shortened_from_user_concept",
            "records": len([r for r in rows if r["source"] == "hacker_news_algolia"]),
            "cache_hit": hn.get("cache_hit", False),
            "requests_attempted": hn.get("requests_attempted", 0),
            "matching_hits_not_fetched_reported": hn.get("matching_hits_not_fetched_reported"),
        },
        {
            "source": "stackexchange_question_mentions", "status": so.get("status"),
            "tag": tag, "query": query,
            "query_provenance": "auto_shortened_from_user_concept",
            "records": len([r for r in rows if r["source"] == "stackexchange_question_mentions"]),
            "cache_hit": so.get("cache_hit", False),
            "requests_attempted": so.get("requests_attempted", 0),
            "has_more": so.get("has_more"),
        },
    ]
    return coverage, rows


def rank_evidence(concept: str, records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    """Memory-only SQLite FTS5 BM25; lexical rank never establishes truth."""
    tokens = list(dict.fromkeys(t for t in _WORDS.findall(concept.lower()) if t not in _STOP))[:9]
    if not tokens or not records:
        return records[:12], "unranked"
    columns = {i: r.get("title", "") + " " + str(r.get("description") or "") for i, r in enumerate(records)}
    try:
        with closing(sqlite3.connect(":memory:")) as conn:
            conn.execute("CREATE VIRTUAL TABLE terms USING fts5(text)")
            conn.executemany("INSERT INTO terms(rowid,text) VALUES (?,?)",
                             [(i + 1, title) for i, title in columns.items()])
            fts_query = " OR ".join(f'"{token}"' for token in tokens)
            hits = [row[0] - 1 for row in conn.execute(
                "SELECT rowid FROM terms WHERE terms MATCH ? ORDER BY bm25(terms) LIMIT 50",
                (fts_query,),
            ).fetchall()]
    except sqlite3.OperationalError:
        scored = [(sum(term in str(text).lower() for term in tokens), i)
                  for i, text in columns.items()]
        scored.sort(key=lambda x: (-x[0], x[1]))
        hits = [i for score, i in scored if score > 0]
        method = "token_overlap_fallback"
    else:
        method = "sqlite_fts5_bm25"
    unique_order = list(dict.fromkeys(hits + list(columns)))
    return [records[i] for i in unique_order[:12]], method


def validate_concept(
    concept: str, *, stack_tag: str | None = None, dataset_id: str = "",
    devpost_urls: list[str] | None = None,
    limit: int = 8, lookback_days: int = 30,
    execute: bool = False, cache: BudgetCache | None = None,
) -> dict[str, Any]:
    """Always consider GitHub issues, repositories, HN and Stack Overflow.

    execute=False is offline and reads no cache. execute=True uses exactly
    one bounded call per source, or its existing cache/cooldown. No scraping.
    """
    concept = _concept(concept)
    if type(limit) is not int or not 1 <= limit <= 10:
        raise ValueError("limit must be 1..10")
    if type(lookback_days) is not int or not 7 <= lookback_days <= 90:
        raise ValueError("lookback_days must be 7..90")
    if type(execute) is not bool:
        raise ValueError("execute must be Boolean")
    tag, inferred_tag = _tag_for(concept, stack_tag)
    community_phrase = _community_query(concept)
    devpost_candidates = _devpost_urls(devpost_urls)
    plans: dict[str, Plan] = {
        "github_hybrid_issues": _github_hybrid_plan(concept, lookback_days, limit, execute),
        "github_repositories": _other_plan("github_repositories", phrase=concept, limit=limit, execute=execute),
    }
    if dataset_id:
        plans["hf_dataset_details"] = _other_plan("hf_dataset_details", dataset=dataset_id,
                                                   limit=1, execute=execute)
    if not execute:
        hn_coverage, _ = _community(community_phrase, tag, limit, lookback_days, False, None)
        return {
            "status": "planned", "concept": concept, "source_count": 4 + bool(dataset_id),
            "network_performed": False, "no_paid_services": True,
            "community_sources_always_considered": True,
            "stack_tag_inferred": inferred_tag,
            "community_query": community_phrase,
            "devpost_caller_references": devpost_candidates,
            "sources": [
                *[{"source": key, "status": "planned", "plan": p.public()}
                  for key, p in plans.items()], *hn_coverage,
            ], "dataset_content_downloaded": False,
            "candidate_validity_not_established": True,
        }
    store = cache or BudgetCache()
    evidence: list[dict[str, Any]] = []
    coverage = []
    for name, plan in plans.items():
        try:
            raw = collect(plan, cache=store, fetch=True, timeout=16)
            if name == "github_hybrid_issues":
                meta, rows = _issues(raw)
            elif name == "github_repositories":
                meta, rows = _repositories(raw)
            else:
                _, data, sample = _metadata(raw)
                meta = {
                    "source": name, "status": raw.get("status"),
                    "license": data.get("license"), "gated": data.get("gated"),
                    "private": data.get("private"), "last_modified": data.get("lastModified"),
                    "license_granted_by_metadata": False,
                    "data_rows_downloaded": False,
                }
                rows = []
                if sample:
                    meta["dataset_name"] = sample[0].get("id")
            evidence.extend(rows)
            coverage.append(meta)
        except (OSError, TypeError, ValueError, sqlite3.Error):
            coverage.append({"source": name, "status": "unavailable",
                             "reason": "bounded_collection_failed"})
    try:
        community_status, community_rows = _community(community_phrase, tag, limit, lookback_days, True, store)
    except (OSError, TypeError, ValueError, sqlite3.Error):
        community_status = [
            {"source": s, "status": "unavailable", "records": 0}
            for s in ("hacker_news_algolia", "stackexchange_question_mentions")
        ]
        community_rows = []
    coverage.extend(community_status)
    evidence.extend(community_rows)
    ranked, ranking_method = rank_evidence(concept, evidence)
    return {
        "status": "observed_partial" if evidence else "no_validated_topical_evidence",
        "concept": concept, "source_count": len(coverage),
        "no_paid_services": True, "community_sources_always_considered": True,
        "stack_tag_inferred": inferred_tag, "community_query": community_phrase,
        "sources": coverage, "devpost_caller_references": devpost_candidates,
        "competitor_review_shortlist": _competitor_shortlist(evidence + devpost_candidates),
        "ranked_candidate_evidence": ranked, "ranking_method": ranking_method,
        "source_sampling_is_partial": True,
        "semantic_search_does_not_prove_relevance": True,
        "incumbent_feature_equivalence_verified": False,
        "customer_demand_verified": False, "dataset_content_downloaded": False,
        "validation_needed": [
            "Human-review source-linked issues, discussions and competing repository features.",
            "Compare candidate task outcomes against working alternatives and a simple baseline.",
            "Confirm dataset license, gating and updates before any content reuse.",
        ],
    }
