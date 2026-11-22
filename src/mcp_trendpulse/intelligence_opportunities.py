"""Opt-in source-aware opportunity *triage*, never a probability of success.

Takes caller-supplied, source-attributed evidence. Does not scrape, send messages,
make payments, query arbitrary URLs, or touch the community MCP. The data
contract distinguishes publisher independence, dated provenance and verified
purchases from mere topic matches. No LLM synthesis is used.
"""

from __future__ import annotations

import ipaddress
import json
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from urllib.parse import parse_qsl, urlsplit
from typing import Any

# Provider classes describe what an adapter can actually establish, not what a
# speculative business case wishes the source could prove.
SOURCE_KIND: dict[str, str] = {
    "gdelt_latest": "manifest_only",
    "eurostat": "macro_context",
    "ted": "procurement_notice",
    "cellar": "legal_metadata",
    "github_issues": "reported_problem",
    "worldbank": "macro_context",
    "greenhouse": "hiring",
    "greenhouse_job": "hiring",
    "lever": "hiring",
    "ashby": "hiring",
    "smartrecruiters": "hiring",
    "sec_companyfacts": "financial_context",
    "sec_companyconcept": "financial_context",
    "openalex": "research",
    "companies_house": "corporate_registry",
    "usaspending": "public_award",
    "cfpb": "reported_problem",
    "cordis": "research_funding",
    "gleif": "corporate_registry",
    "ecb": "macro_context",
    "entsoe": "energy_activity",
    "rsshub_local": "monitoring",
    "changedetection_local": "monitoring",
    "copernicus": "satellite_catalogue",
    "epo": "patent_publication",
}

# All mapped sources exist in the current 25-source opt-in extension. A
# combination is an investigation recipe, not an automatic proof of demand.
LANES: dict[str, dict[str, Any]] = {
    "agent_safety": {"sources": ("github_issues", "greenhouse", "cellar", "ted"),
                     "question": "Who buys safeguards and incident response beyond platform controls?"},
    "agent_commerce": {"sources": ("github_issues", "greenhouse", "cfpb", "usaspending"),
                       "question": "Are merchants funding machine transaction and dispute workflows?"},
    "sme_margin": {"sources": ("eurostat", "greenhouse", "ted", "worldbank"),
                   "question": "Which reachable SME buyers have measured workflow costs?"},
    "compliance": {"sources": ("cellar", "ted", "greenhouse", "usaspending"),
                   "question": "Is a rule effective and is spend directed to a new obligation?"},
    "fraud_identity": {"sources": ("cfpb", "github_issues", "ted", "gleif"),
                       "question": "Is a specific purchaser paying to solve identifiable fraud?"},
    "household_finance": {"sources": ("ecb", "eurostat", "cfpb", "worldbank"),
                          "question": "Who pays for a demonstrably measurable consumer saving?"},
    "care_automation": {"sources": ("cordis", "greenhouse", "worldbank", "ted"),
                        "question": "Who reimburses or buys the operational care solution?"},
    "energy_software": {"sources": ("entsoe", "ted", "cellar", "copernicus"),
                        "question": "Is there a software buyer beyond a capital investment?"},
    "developer_reliability": {"sources": ("github_issues", "greenhouse_job", "usaspending"),
                              "question": "Which buyer funds costly reliability remediation?"},
    "research_to_product": {"sources": ("cordis", "openalex", "epo", "greenhouse"),
                            "question": "Has research moved beyond publication into budgets?"},
    "procurement_regulation": {"sources": ("cellar", "ted", "usaspending"),
                               "question": "Can binding obligations be linked to procurement?"},
    "corporate_identity": {"sources": ("gleif", "companies_house", "cellar", "ted"),
                           "question": "Can an identified organization justify paid identity checks?"},
    "privacy_operations": {"sources": ("cellar", "ted", "github_issues", "greenhouse_job"),
                           "question": "Which EU privacy operations have funded implementation pain rather than headlines?"},
    "vendor_due_diligence": {"sources": ("gleif", "companies_house", "ted", "greenhouse", "cellar"),
                             "question": "Are named buyers paying to validate counterparties and suppliers?"},
    "public_cloud_finops": {"sources": ("usaspending", "github_issues", "greenhouse", "greenhouse_job", "sec_companyconcept"),
                            "question": "Which US public buyers face repeat cloud-cost work not solved internally?"},
    "customer_dispute_ops": {"sources": ("cfpb", "greenhouse", "github_issues", "usaspending", "sec_companyconcept"),
                             "question": "Are regulated US firms budgeting to reduce documented dispute handling?"},
    "industrial_maintenance": {"sources": ("ted", "greenhouse", "cordis", "epo", "entsoe"),
                               "question": "Are EU operators buying maintenance software rather than physical equipment?"},
    "research_procurement": {"sources": ("cordis", "openalex", "epo", "ted", "greenhouse_job"),
                             "question": "Is a funded research result creating paid deployment procurement?"},
}

MATERIAL = {"hiring", "reported_problem", "procurement_notice", "public_award"}
CONTEXT_ONLY = {
    "macro_context", "research", "research_funding", "legal_metadata",
    "financial_context", "corporate_registry", "energy_activity",
    "satellite_catalogue", "patent_publication", "monitoring", "manifest_only",
}
# Event streams may support daily counts after verifying complete collection.
# Static catalogues, macroeconomic indexes, batch manifests and entity registries
# cannot legitimately produce daily topical event momentum.
TREND_SOURCES = {
    "github_issues", "cfpb", "ted", "usaspending", "cordis",
    "greenhouse", "greenhouse_job", "lever", "ashby", "smartrecruiters",
    "openalex", "epo", "rsshub_local", "changedetection_local",
}
# Different ATS connectors do not automatically mean independent underlying
# employers. Monitoring wrappers likewise may report the same original event.
TREND_FAMILIES = {
    "greenhouse": "hiring_ats", "greenhouse_job": "hiring_ats",
    "lever": "hiring_ats", "ashby": "hiring_ats",
    "smartrecruiters": "hiring_ats",
    "rsshub_local": "monitoring_transport",
    "changedetection_local": "monitoring_transport",
}
UNHEALTHY = {"unavailable", "rate_limited", "timeout", "stale",
             "not_configured", "invalid_source_shape"}
# Patents are contextual enrichment, not a buying-signal requirement.
# EPO may require invasive registration and is never needed to use a lane.
OPTIONAL_ENRICHMENT_SOURCES = {"epo"}

SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{1,79}$")
REGION = re.compile(r"^(?:[A-Z]{2}|GLOBAL)$")
HEALTH = {"ok", *UNHEALTHY}
MAX_BYTES = 180_000


def _day(value: Any, label: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"{label} must be ISO date YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} is not a valid calendar date") from exc


def _ident(value: Any, label: str) -> str:
    if not isinstance(value, str) or SLUG.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase stable identifier (2-80 chars)")
    return value


def _string(value: Any, label: str, maximum: int, *, required: bool = True) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text")
    clean = " ".join(value.split())
    if len(clean) > maximum or (required and not clean):
        raise ValueError(f"{label} missing or too long")
    return clean


def _safe_url(value: Any) -> str:
    url = _string(value, "source_url", 700)
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.fragment or parsed.port not in (None, 443)):
        raise ValueError("source_url must be a public HTTPS evidence reference")
    host = parsed.hostname.lower()
    if (host == "localhost" or host.endswith((".localhost", ".local", ".internal"))
            or "." not in host):
        raise ValueError("source_url must be a public HTTPS evidence reference")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass  # Public DNS names are only stored as references, never fetched.
    else:
        if not address.is_global:
            raise ValueError("source_url must not address private or loopback IP space")
    if any(any(word in key.lower() for word in
               ("secret", "token", "apikey", "api_key", "password", "auth"))
           for key, _ in parse_qsl(parsed.query, keep_blank_values=True)):
        raise ValueError("source_url must not contain credential-looking query keys")
    return url

def _canonical_evidence_url(url: str) -> tuple[str, str, tuple[tuple[str, str], ...]]:
    """Deduplicate tracking variants; retain original URL for audit references."""
    parsed = urlsplit(url)
    query = tuple(sorted(
        (key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {
            "fbclid", "gclid", "mc_cid", "mc_eid", "igshid", "ref",
        }
    ))
    return (parsed.hostname.lower(), parsed.path.rstrip("/") or "/", query)


def _coverage(data: Any) -> dict[str, str]:
    if data is None:
        return {}
    if not isinstance(data, dict) or len(data) > 25:
        raise ValueError("source_health must be a bounded source/status mapping")
    for key, status in data.items():
        if key not in SOURCE_KIND or not isinstance(status, str) or status not in HEALTH:
            raise ValueError("Invalid source_health provider or state")
    return dict(data)


def _input(candidates: Any, evidence: Any) -> None:
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= 20:
        raise ValueError("Provide 1-20 candidate objects")
    if not isinstance(evidence, list) or len(evidence) > 300:
        raise ValueError("Provide at most 300 bounded evidence records")
    try:
        size = len(json.dumps([candidates, evidence], ensure_ascii=False).encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Inputs must be serializable JSON") from exc
    if size > MAX_BYTES:
        raise ValueError("Opportunity input exceeds 180 KB")


def _candidate(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise ValueError("Each candidate must be an object")
    ident = _ident(raw.get("id"), "candidate.id")
    lane = raw.get("lane")
    if lane not in LANES:
        raise ValueError("candidate.lane must be a supported combination")
    region = raw.get("geography")
    if not isinstance(region, str) or not REGION.fullmatch(region):
        raise ValueError("candidate.geography must be an ISO country code or GLOBAL")
    return {
        "id": ident, "lane": lane, "geography": region,
        "title": _string(raw.get("title"), "candidate.title", 140),
        "workflow": _ident(raw.get("workflow"), "candidate.workflow"),
        "buyer": _string(raw.get("buyer", ""), "candidate.buyer", 100, required=False),
        "buyer_entity": (
            _ident(raw["buyer_entity"], "buyer_entity")
            if raw.get("buyer_entity") else ""
        ),
    }


def _evidence(raw: Any, asof: date) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Evidence must be an object")
    source = raw.get("source")
    if source not in SOURCE_KIND:
        raise ValueError("Unknown or non-free source")
    pub, observed = _day(raw.get("published_at"), "published_at"), _day(raw.get("observed_at"), "observed_at")
    if pub > observed:
        raise ValueError("Publication date cannot exceed observation date")
    geography = raw.get("geography")
    if not isinstance(geography, str) or not REGION.fullmatch(geography):
        raise ValueError("Invalid evidence geography")
    sentiment = raw.get("polarity")
    if sentiment not in {"support", "against"}:
        raise ValueError("Invalid evidence polarity")
    return {
        "id": _ident(raw.get("id"), "evidence.id"),
        "candidate": _ident(raw.get("candidate"), "evidence.candidate"),
        "source": source,
        "kind": SOURCE_KIND[source],
        "origin_id": _ident(raw.get("origin_id"), "origin_id"),
        "publisher": _ident(raw.get("publisher"), "publisher"),
        "geography": geography,
        "workflow": _ident(raw.get("workflow"), "evidence.workflow"),
        "url": _safe_url(raw.get("url")),
        "published": pub, "observed": observed,
        "polarity": sentiment,
        "buyer_entity": (
            _ident(raw["buyer_entity"], "evidence.buyer_entity")
            if raw.get("buyer_entity") else ""
        ),
        "claim": _string(raw.get("claim"), "evidence.claim", 320),
        "visible_at_asof": pub <= asof and observed <= asof,
    }


def _trend(trends: Any, candidate: dict[str, str], asof: date,
           health: dict[str, str]) -> dict[str, Any]:
    if trends is None:
        return {"status": "unknown", "reason": "No comparable dated daily measurements"}
    if not isinstance(trends, list) or len(trends) > 900:
        raise ValueError("At most 900 daily trend observations")
    if len(json.dumps(trends, ensure_ascii=False).encode("utf-8")) > 180_000:
        raise ValueError("Trend observations exceed 180 KB")
    selected: dict[str, dict[date, float]] = defaultdict(dict)
    invalid = False
    provider_unavailable = False
    for row in trends:
        if not isinstance(row, dict):
            raise ValueError("Trend observation must be object")
        if row.get("candidate") != candidate["id"]:
            continue
        src = row.get("source")
        if src not in SOURCE_KIND:
            raise ValueError("Unknown trend source")
        if src not in TREND_SOURCES or src not in LANES[candidate["lane"]]["sources"]:
            invalid = True
            continue
        if health.get(src) in UNHEALTHY:
            provider_unavailable = True
            continue
        day = _day(row.get("day"), "trend.day")
        if day > asof:
            continue
        if row.get("geography") != candidate["geography"] or row.get("unit") != "daily_events":
            invalid = True
            continue
        if row.get("coverage_complete") is not True:
            invalid = True
            continue
        value = row.get("value")
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 1_000_000_000:
            raise ValueError("Daily event count must be an integer from 0 to 1 billion")
        if day in selected[src]:
            invalid = True
            continue
        selected[src][day] = float(value)
    if invalid:
        return {"status": "unknown", "reason": "Incomparable or duplicate trend observations"}
    start = asof - timedelta(days=27)
    movements = []
    for src, days in sorted(selected.items()):
        expected = [start + timedelta(days=i) for i in range(28)]
        if not all(day in days for day in expected):
            continue
        baseline = sum(days[d] for d in expected[:14])
        recent = sum(days[d] for d in expected[14:])
        # Sparse event counts are not a meaningful direction estimate.
        if baseline < 10 or recent < 5:
            movement = "unknown"
        elif recent - baseline >= 5 and recent >= 1.25 * baseline:
            movement = "rising"
        elif baseline - recent >= 5 and recent <= 0.8 * baseline:
            movement = "falling"
        else:
            movement = "stable"
        movements.append({
            "source": src, "signal_family": TREND_FAMILIES.get(src, src),
            "direction": movement,
            "previous_14_days": round(baseline, 3),
            "latest_14_days": round(recent, 3),
            "unit": "complete daily events", "not_success_probability": True,
        })
    if provider_unavailable:
        return {"status": "coverage_degraded",
                "reason": "A submitted trend provider has unhealthy collection coverage",
                "per_source": movements, "not_revenue_forecast": True}
    usable_rows = [x for x in movements if x["direction"] != "unknown"]
    usable = [x["direction"] for x in usable_rows]
    independent_families = len({x["signal_family"] for x in usable_rows})
    if not usable:
        return {"status": "unknown", "reason": "Incomplete/sparse 28-day comparable samples",
                "per_source": movements}
    if "rising" in usable and "falling" in usable:
        direction = "conflicted"
    elif independent_families >= 2 and all(x == "rising" for x in usable):
        direction = "rising_multi_source"
    elif independent_families >= 2 and all(x == "falling" for x in usable):
        direction = "falling_multi_source"
    elif all(x == "stable" for x in usable):
        direction = "stable"
    else:
        direction = "mixed_or_single_source"
    return {"status": direction, "per_source": movements,
            "independent_signal_families": independent_families,
            "not_revenue_forecast": True}


def evaluate_opportunities(
    candidates: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    *,
    as_of: str | None = None,
    source_health: dict[str, str] | None = None,
    daily_trends: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Rank *investigations* only, abstain on missing, stale or conflicting data.

    This intentionally has no success probability. Supplier failures appear in
    output; invalid individual records are rejected with indexed reason codes
    without turning the whole batch into fake 'zero demand'.
    """
    _input(candidates, evidence)
    asof = _day(as_of, "as_of") if as_of is not None else date.today()
    health = _coverage(source_health)
    parsed = [_candidate(item) for item in candidates]
    if len({item["id"] for item in parsed}) != len(parsed):
        raise ValueError("Candidate IDs must be unique")
    accepted = defaultdict(list)
    rejected: list[dict[str, Any]] = []
    allowed = {item["id"] for item in parsed}
    validated = []
    for index, raw in enumerate(evidence):
        try:
            record = _evidence(raw, asof)
            if record["candidate"] not in allowed:
                raise ValueError("Evidence references unknown candidate")
            validated.append((index, record))
        except (TypeError, ValueError) as exc:
            rejected.append({"index": index, "reason": str(exc)[:110]})
    owners = defaultdict(set)
    for _, record in validated:
        owners[record["id"]].add(record["candidate"])
    conflicts = {ident for ident, candidates_for_id in owners.items()
                 if len(candidates_for_id) > 1}
    global_ids = set()
    for index, record in validated:
        if record["id"] in conflicts:
            rejected.append({"index": index, "reason": "Duplicate evidence ID across candidates"})
        elif record["id"] in global_ids:
            rejected.append({"index": index, "reason": "Duplicate evidence ID"})
        else:
            global_ids.add(record["id"])
            accepted[record["candidate"]].append(record)
    rejected.sort(key=lambda entry: entry["index"])
    results = []
    for candidate in parsed:
        rows = accepted[candidate["id"]]
        by_origin: dict[str, dict[str, Any]] = {}
        seen_urls: set[tuple[str, str, tuple[tuple[str, str], ...]]] = set()
        ignored = Counter()
        for rec in sorted(rows, key=lambda r: (r["published"], r["id"]), reverse=True):
            if not rec["visible_at_asof"]:
                ignored["future_or_unobserved"] += 1
                continue
            if rec["published"] < asof - timedelta(days=365):
                ignored["older_than_365_days"] += 1
                continue
            if rec["workflow"] != candidate["workflow"]:
                ignored["different_workflow"] += 1
                continue
            if rec["geography"] != candidate["geography"]:
                ignored["different_geography"] += 1
                continue
            if rec["source"] not in LANES[candidate["lane"]]["sources"]:
                ignored["not_in_selected_lane"] += 1
                continue
            if health.get(rec["source"]) in UNHEALTHY:
                ignored["unhealthy_provider"] += 1
                continue
            # Do not count syndicated records under multiple API wrappers.
            canonical_url = _canonical_evidence_url(rec["url"])
            if rec["origin_id"] in by_origin or canonical_url in seen_urls:
                ignored["duplicate_origin"] += 1
                continue
            by_origin[rec["origin_id"]] = rec
            seen_urls.add(canonical_url)
        valid = list(by_origin.values())
        supportive = [x for x in valid if x["polarity"] == "support"]
        against = [x for x in valid if x["polarity"] == "against"]
        kinds = {x["kind"] for x in supportive}
        publishers = {x["publisher"] for x in supportive}
        independent = len(publishers)
        # Multiple vacancies by one employer are not multiple independent votes.
        per_publisher_kind = {(x["publisher"], x["kind"]) for x in supportive}
        class_count = len({kind for _, kind in per_publisher_kind})
        substantive = bool(kinds & MATERIAL)
        buyer_proxy = "public_award" in kinds
        pain_proxy = bool(kinds & {"reported_problem", "hiring"})
        known_buyer = bool(candidate["buyer"])
        buyer_linked_award = bool(
            candidate["buyer_entity"] and any(
                x["kind"] == "public_award"
                and x["buyer_entity"] == candidate["buyer_entity"] for x in supportive
            )
        )
        # Absence of optional patent-enrichment credentials is NOT a
        # failed buyer/workflow investigation. An actual missing core source is.
        degraded = any(
            health.get(src) in UNHEALTHY
            for src in LANES[candidate["lane"]]["sources"]
            if src not in OPTIONAL_ENRICHMENT_SOURCES
        )
        # Caller-supplied archived evidence may still be useful, but missing
        # provider status is not equivalent to a verified healthy source.
        provider_health_reported_ok = all(
            health.get(src) == "ok" for src in LANES[candidate["lane"]]["sources"]
            if src not in OPTIONAL_ENRICHMENT_SOURCES
        )
        optional_sources_unavailable = [
            src for src in LANES[candidate["lane"]]["sources"]
            if src in OPTIONAL_ENRICHMENT_SOURCES
            and health.get(src) != "ok"
        ]
        if len({x["publisher"] for x in against}) >= 2:
            stage = "conflict_review"
            priority = 0
        elif against:
            stage = "contested"
            priority = 0
        elif class_count >= 3 and independent >= 3 and substantive and buyer_proxy and pain_proxy and known_buyer and buyer_linked_award:
            stage = "buyer_interview_priority"
            priority = 3
        elif class_count >= 2 and independent >= 2 and substantive:
            stage = "investigate"
            priority = 2
        elif supportive:
            stage = "monitor"
            priority = 1
        else:
            stage = "insufficient"
            priority = 0
        if degraded and priority > 1:
            priority = 1
            stage = "partial_provider_coverage"
        reasons = []
        if not known_buyer:
            reasons.append("No identifiable buyer has been established")
        if not substantive:
            reasons.append("No concrete problem, hiring, tender, or award evidence")
        if independent < 2:
            reasons.append("Insufficient independent publishers")
        if class_count < 2:
            reasons.append("Insufficient distinct evidence classes")
        if against:
            reasons.append("Counterevidence requires human review")
        if degraded:
            reasons.append("One or more relevant provider signals are unavailable")
        elif not provider_health_reported_ok:
            reasons.append("Provider health was not reported for every lane source")
        if optional_sources_unavailable:
            reasons.append("Optional patent enrichment not verified; this is not negative demand")
        if rejected:
            reasons.append("Some evidence input records were rejected; inspect reasons")
        if not buyer_proxy:
            reasons.append("No public contract award was observed (not required for investigation)")
        if buyer_proxy:
            reasons.append("Public award is a buying proxy, NOT proof of product-market fit")
        if buyer_proxy and not buyer_linked_award:
            reasons.append("Awarding buyer identity has not been matched to the candidate")
        if not reasons:
            reasons = ["No buyer payment, purchase intent, or market-size forecast has been verified"]
        result = {
            "id": candidate["id"], "title": candidate["title"],
            "lane": candidate["lane"], "buyer": candidate["buyer"],
            "workflow": candidate["workflow"], "geography": candidate["geography"],
            "status": stage, "priority_order": priority,
            "provider_health_reported_ok": provider_health_reported_ok,
            "optional_enrichment_unavailable": optional_sources_unavailable,
            "independent_publishers": independent,
            "evidence_classes": sorted(kinds),
            "distinct_classes": class_count,
            "supporting_origins": len(supportive),
            "contradicting_origins": len(against),
            "source_health": {
                src: health.get(src, "unknown") for src in LANES[candidate["lane"]]["sources"]
            },
            "ignored_reasons": dict(ignored),
            "caveats": reasons,
            "trend": _trend(daily_trends, candidate, asof, health),
            "buying_intent_confirmed": False,
            "success_probability": None,
            "next_test": (
                "Interview named budget owner about the last costly occurrence and paid workaround"
                if priority >= 2 else
                "Collect independent current problem and buyer-budget evidence"
            ),
            "source_references": [
                {"id": x["id"], "source": x["source"], "published_at": x["published"].isoformat(),
                 "url": x["url"], "polarity": x["polarity"]}
                for x in sorted(valid, key=lambda x: x["id"])[:30]
            ],
        }
        results.append(result)
    results.sort(key=lambda x: (-x["priority_order"], -x["independent_publishers"],
                                -x["distinct_classes"], x["id"]))
    return {
        "as_of": asof.isoformat(),
        "mode": "offline_hypothesis_triage",
        "evaluated": len(results),
        "rejected_records": rejected[:100],
        "rejected_count": len(rejected),
        "results": results,
        "not_a_winning_business_forecast": True,
        "requires_external_commercial_validation": True,
        "model_training_or_network_calls_performed": False,
        "lane_count": len(LANES),
    }


def lane_catalog() -> list[dict[str, Any]]:
    return [{"id": key, "sources": list(meta["sources"]),
             "question": meta["question"]} for key, meta in LANES.items()]
