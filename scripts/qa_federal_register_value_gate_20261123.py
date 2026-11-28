"""Pre-registered, read-only research-utility gate for PR #425.

Compares existing seedless discovery with one optional Federal Register
context request across fixed hackathon-relevant questions. Evaluates
coverage, source freshness, topical *title* match, abstention, latency,
cache behavior and local request cost. Does NOT infer legal effect,
commercial demand, startup viability or human productivity improvement.
No private keys, paid APIs, user accounts or uncontrolled web crawling.
"""
from __future__ import annotations

import json
import os
import statistics
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from mcp_trendpulse.intelligence_core import BudgetCache
from mcp_trendpulse.intelligence_discovery import discover_current
from mcp_trendpulse.intelligence_regulatory import enrich_regulatory_context

# Frozen before observing live documents. More than one domain prevents a
# cherry-picked "artificial intelligence" search from winning by default.
TASKS = (
    {
        "lane": "private_document_ai",
        "question": "Are there current U.S. federal publications relevant to privacy-first document AI?",
        "term": "data privacy",
        "title_tokens": ("privacy", "personal data", "data protection", "confidentiality"),
    },
    {
        "lane": "accessibility",
        "question": "Are there current U.S. federal publications about digital accessibility needs?",
        "term": "accessibility",
        "title_tokens": ("accessibility", "accessible", "disability", "assistive"),
    },
    {
        "lane": "developer_incident_response",
        "question": "Are there current U.S. federal publications relevant to incident-response tooling?",
        "term": "cybersecurity",
        "title_tokens": ("cybersecurity", "cyber", "incident", "information security"),
    },
    {
        "lane": "field_inspection",
        "question": "Are there current U.S. federal publications relevant to field safety inspection?",
        "term": "workplace safety",
        "title_tokens": ("occupational", "workplace", "safety", "inspection"),
    },
    {
        "lane": "hybrid_ai_regulatory_context",
        "question": "Are there current U.S. federal publications directly discussing artificial intelligence?",
        "term": "artificial intelligence",
        "title_tokens": ("artificial intelligence", "machine learning", "ai system"),
    },
    {
        "lane": "negative_control",
        "question": "Can an unrelated, hyper-specific offline bug report query produce an apparent government mandate?",
        "term": "offline bug report generator",
        "title_tokens": ("offline bug report", "bug report generator"),
    },
)


def _round_ms(seconds: float) -> int:
    return int(round(seconds * 1000))


def _extract(row: dict, title_tokens: tuple[str, ...]) -> dict:
    title = row.get("title", "")
    title_hit = any(token in title.casefold() for token in title_tokens)
    return {
        "title": title[:240],
        "published": row.get("publication_date", ""),
        "document_type": row.get("type", ""),
        "url": row.get("html_url", ""),
        "title_match": title_hit,
        "source_cited": str(row.get("html_url", "")).startswith(
            "https://www.federalregister.gov/documents/"),
        "legal_effect_verified": row.get("legal_effect_verified"),
    }


def main() -> int:
    started = datetime.now(timezone.utc).isoformat()
    with tempfile.TemporaryDirectory(prefix="trendpulse-fr-value-") as root:
        cache = BudgetCache(Path(root))
        t0 = time.perf_counter()
        try:
            baseline = discover_current(
                execute=True, lookback_days=30, limit=10,
                cache=cache, env={},
            )
            baseline_error = None
        except (OSError, ValueError, RuntimeError) as exc:
            baseline = {
                "status": "unavailable", "candidates": [],
                "research_observations": [], "source_coverage": [],
                "paid_buyers_verified": False, "queries_budgeted": 0,
            }
            baseline_error = type(exc).__name__
        baseline_ms = _round_ms(time.perf_counter() - t0)
        baseline_summary = {
            "status": baseline.get("status", "observed"),
            "error_type": baseline_error,
            "time_ms": baseline_ms,
            "candidate_count": len(baseline.get("candidates", [])),
            "queries_budgeted": baseline.get("queries_budgeted"),
            "source_coverage": [
                {"source": r.get("source"), "status": r.get("status")}
                for r in baseline.get("source_coverage", [])
            ],
            "has_federal_register": "regulatory_context" in baseline,
            "paid_buyers_verified": baseline.get("paid_buyers_verified", False),
        }
        print(json.dumps({"checkpoint": "baseline", **baseline_summary}), flush=True)

        # Automatic query selection is an independent claim. If the prior
        # research offers no admissible topic, abstaining is valid.
        t0 = time.perf_counter()
        derived = enrich_regulatory_context(
            baseline, lookback_days=30, limit=10, cache=cache, env={},
        )
        derived_ms = _round_ms(time.perf_counter() - t0)
        derived_summary = {
            "status": derived.get("status"),
            "topic": derived.get("topic", ""),
            "topic_origin": derived.get("topic_origin"),
            "time_ms": derived_ms,
            "sampled_docs": derived.get("sampled_documents")
            if derived.get("status") == "observed" else None,
            "requests_budgeted": derived.get("source_requests_budgeted"),
            "docs": [
                _extract(doc, ("privacy", "accessibility", "cybersecurity", "artificial intelligence"))
                for doc in derived.get("documents", [])[:5]
            ],
        }
        print(json.dumps({"checkpoint": "auto_derived_topic", **derived_summary}), flush=True)

        rows = []
        for task in TASKS:
            t0 = time.perf_counter()
            fresh = enrich_regulatory_context(
                baseline, regulatory_term=task["term"],
                lookback_days=30, limit=10, cache=cache, env={},
            )
            cold_ms = _round_ms(time.perf_counter() - t0)
            t0 = time.perf_counter()
            replay = enrich_regulatory_context(
                baseline, regulatory_term=task["term"],
                lookback_days=30, limit=10, cache=cache, env={},
            )
            warm_ms = _round_ms(time.perf_counter() - t0)
            observed = fresh.get("status") == "observed"
            documents = [
                _extract(doc, task["title_tokens"])
                for doc in fresh.get("documents", [])[:10]
            ] if observed else []
            candidates = [
                doc for doc in documents
                if doc["title_match"] and doc["source_cited"]
            ]
            row = {
                "lane": task["lane"],
                "question": task["question"],
                "term": task["term"],
                "baseline_official_us_documents": 0,
                "source_status": fresh.get("status"),
                "failure_reason": fresh.get("reason_code"),
                "http_status": fresh.get("http_status"),
                "source_requests_budgeted": fresh.get("source_requests_budgeted"),
                "cache_replay": replay.get("cache_hit", False),
                "cold_ms": cold_ms,
                "warm_ms": warm_ms,
                "documents_observed": len(documents) if observed else None,
                "title_level_matches": len(candidates) if observed else None,
                "docs": documents,
                "legal_effect_verified": fresh.get("legal_effect_verified", False),
                "buyer_demand_verified": fresh.get("buyer_demand_verified", False),
            }
            if (row["legal_effect_verified"] is not False
                    or row["buyer_demand_verified"] is not False):
                raise AssertionError("Regulatory contextual evidence was promoted to proof")
            rows.append(row)
            print(json.dumps({"checkpoint": "research_task", **row},
                             ensure_ascii=True), flush=True)

        observed_rows = [r for r in rows if r["source_status"] == "observed"]
        usable = [r for r in observed_rows if r["title_level_matches"] > 0]
        positive = [r for r in usable if r["lane"] != "negative_control"]
        invalid_negative = any(
            r["lane"] == "negative_control" and r["title_level_matches"] > 0
            for r in rows
        )
        # This is a cautious *proxy*, not a claim of better user productivity.
        decision = (
            "needs_manual_relevance_review"
            if positive and not invalid_negative and len(observed_rows) >= 4
            else "no_demonstrated_research_value"
        )
        report = {
            "method": "pre_registered_six_question_live_source_title_proxy",
            "measured_at": started,
            "baseline": baseline_summary,
            "automatic_topic": derived_summary,
            "tasks": rows,
            "summary": {
                "task_count": len(TASKS),
                "source_observed_tasks": len(observed_rows),
                "tasks_with_title_match": len(usable),
                "positive_tasks_with_title_match": len(positive),
                "negative_control_title_match": invalid_negative,
                "additional_public_source_documents": sum(
                    r["documents_observed"] for r in observed_rows
                ),
                "title_matched_public_documents": sum(
                    r["title_level_matches"] for r in observed_rows
                ),
                "cold_ms_median_observed": (
                    int(statistics.median(r["cold_ms"] for r in observed_rows))
                    if observed_rows else None
                ),
                "cache_replay_ms_median_observed": (
                    int(statistics.median(r["warm_ms"] for r in observed_rows))
                    if observed_rows else None
                ),
                "new_provider_requests_budgeted": (
                    derived.get("source_requests_budgeted", 0)
                    + sum(r.get("source_requests_budgeted", 0) for r in rows)
                ),
                "unavailable_is_not_zero_activity": True,
                "actual_user_time_saved_measured": False,
                "business_decision_quality_measured": False,
                "review_gate": decision,
            },
            "limits": (
                "The baseline has no official US Federal Register adapter. "
                "Title substring matches are a narrow topical proxy, not "
                "independent human relevance scoring, actual legal status, "
                "market demand, or measured researcher productivity. "
                "Data are biased to a recent-first 10-document sample. "
                "Baseline collection occurs once; its cost is amortized across tasks. "
                "Unavailability is excluded rather than scored as zero."
            ),
        }
        dest = Path(os.environ.get(
            "TRENDPULSE_FR_UTILITY_REPORT", "federal-register-utility-20261123.json",
        ))
        dest.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
        print(json.dumps({"checkpoint": "summary", **report["summary"]}), flush=True)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
