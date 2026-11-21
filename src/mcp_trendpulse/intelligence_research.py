"""M14: offline, inspectable cross-source intelligence report.

Typed source evidence remains source-scoped. No provider calls, cross-unit
aggregation, fabricated demand scores, forecasting, billing or network I/O.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from collections import Counter, defaultdict
from datetime import timedelta
from statistics import mean
from typing import Any
from urllib.parse import urlsplit

from pydantic import ValidationError

from mcp_trendpulse.intelligence_keywords import (
    cluster_keyword_signals,
)
from mcp_trendpulse.intelligence_signal import (
    METRIC_DEFINITIONS,
    TrendSignal,
)

MAX_INPUT_BYTES = 128 * 1024
MAX_INPUT_SIGNALS = 120
MAX_REPORT_ITEMS = 120
MAX_KEYWORD_FAMILIES = 80
MAX_GAPS = 24
MAX_SAMPLES_PER_GROUP = 12
_SOURCE_ATTESTED_METHODS = frozenset({
    "official_api", "public_api", "public_dataset",
    "community_provider", "public_rss",
})
_QUERY_METRICS = frozenset({
    "google_trends_normalized_interest", "bing_keyword_impressions",
})
_SEARCH_METRICS = frozenset({
    "google_trends_normalized_interest", "google_trending_traffic_bucket",
    "google_bigquery_rank", "bing_keyword_impressions",
})
_ATTENTION_METRICS = frozenset({
    "wikimedia_pageviews", "news_mention_count",
})
_DEVELOPER_METRICS = frozenset({
    "hacker_news_story_mentions", "github_issue_mentions",
    "stackexchange_question_mentions",
})
_PACKAGE_METRICS = frozenset({
    "npm_package_downloads", "pypi_package_downloads",
})
_SECRET = re.compile(
    r"(?i)(?:\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    r"|sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9_-]{16,}"
    r"|AKIA[0-9A-Z]{16})"
)


def _checked_url(value: str) -> None:
    try:
        parts = urlsplit(value)
        host = parts.hostname or ""
        if (
            parts.scheme != "https"
            or not host or parts.port not in (None, 443)
            or parts.username or parts.password or parts.fragment
            or host == "localhost"
            or host.endswith((".local", ".internal", ".localhost"))
            or _SECRET.search(value)
        ):
            raise ValueError
        try:
            if not ipaddress.ip_address(host).is_global:
                raise ValueError
        except ValueError as exc:
            # The host can be a DNS name, or it can be a non-public IP.
            if re.fullmatch(r"[0-9.]+", host) or ":" in host:
                raise ValueError("Unsafe or private source reference") from exc
    except ValueError as exc:
        raise ValueError("Unsafe or private source reference") from exc


def _checked_signal(raw: Any) -> TrendSignal:
    try:
        signal = TrendSignal.model_validate(raw)
    except (ValidationError, TypeError, ValueError) as exc:
        raise ValueError("Input includes invalid typed source evidence") from exc
    _checked_url(signal.source_url)
    texts = (
        signal.raw_term, signal.normalized_term, signal.sampling_scope,
        signal.provenance.sampling_basis, signal.provenance.source_record_id or "",
    )
    if any(_SECRET.search(t) for t in texts):
        raise ValueError("Source evidence contains sensitive terms")
    return signal


def _identity(s: TrendSignal) -> tuple[Any, ...]:
    """Independent evidence record identity, not a customer/source count."""
    return (
        s.source_id, s.source_url, s.metric_type, s.metric_unit,
        s.normalized_term, s.country, s.language, s.sampling_scope,
        s.provenance.source_record_id,
        s.provenance.method, s.provenance.sampling_basis,
        s.period.granularity, s.period.start_date.isoformat(),
        s.period.end_date.isoformat(), s.observed_at.isoformat(),
        s.raw_term, s.coverage_status, s.value, s.value_label,
        s.provenance.is_observed_search_query,
    )


def _ref_id(identity: tuple[Any, ...]) -> str:
    encoded = json.dumps(
        identity, ensure_ascii=False, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:20]


def _sortkey(s: TrendSignal) -> tuple[str, ...]:
    return tuple("" if item is None else str(item) for item in _identity(s))


def _level(s: TrendSignal) -> str:
    if s.metric_type == "generated_keyword_candidate":
        return "generated_keyword_hypothesis"
    if s.coverage_status in ("unavailable", "no_data"):
        return "unavailable_or_no_data_source"
    if s.provenance.method in ("operator_supplied", "derived"):
        return "operator_or_derived_source_claim"
    if (
        s.metric_type in _QUERY_METRICS
        and s.provenance.is_observed_search_query
        and s.provenance.method in _SOURCE_ATTESTED_METHODS
    ):
        return "source_attested_query"
    if s.metric_type == "google_trends_normalized_interest":
        return "relative_search_interest_not_volume"
    if s.metric_type == "google_trending_traffic_bucket":
        return "approximate_trending_bucket"
    if s.metric_type == "google_bigquery_rank":
        return "relative_source_rank"
    if s.metric_type == "bing_keyword_impressions":
        return "keyword_research_impressions_not_search_logs"
    if s.metric_type in _PACKAGE_METRICS:
        return "package_download_adoption_proxy"
    if s.metric_type in _DEVELOPER_METRICS:
        return "public_developer_discussion"
    if s.metric_type in _ATTENTION_METRICS:
        return "public_attention_proxy"
    return "source_measurement_not_search_volume"


def _source_item(s: TrendSignal) -> dict[str, Any]:
    identity = _identity(s)
    level = _level(s)
    return {
        "evidence_id": _ref_id(identity),
        "evidence_level": level,
        "source_id": s.source_id,
        "source_url": s.source_url,
        "source_record_id": s.provenance.source_record_id,
        "source_method": s.provenance.method,
        "sampling_basis": s.provenance.sampling_basis,
        "sampling_scope": s.sampling_scope,
        "raw_term": s.raw_term,
        "normalized_term": s.normalized_term,
        "country": s.country,
        "language": s.language,
        "observed_at": s.observed_at.isoformat(),
        "period": s.period.model_dump(mode="json"),
        "metric_type": s.metric_type,
        "metric_unit": s.metric_unit,
        "coverage_status": s.coverage_status,
        "measured_value": s.value if s.coverage_status == "observed" else None,
        "partial_source_value": (
            s.value if s.coverage_status == "partial" else None
        ),
        "source_value_label": s.value_label,
        "observed_query_flag": (
            level == "source_attested_query"
        ),
        "original_source_metadata_schema_validated": True,
        "source_recontacted_for_this_report": False,
        "source_claim_reverified_online": False,
        "unique_people_or_customers_verified": False,
    }


def _sample_group(
    items: list[dict[str, Any]],
    *, kind: str,
) -> list[dict[str, Any]]:
    """Bounded direct primary-source references; never sum source counts."""
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        key = (
            item["source_id"], item["source_url"], item["normalized_term"],
            item["country"], item["language"], item["metric_type"],
            item["metric_unit"], item["sampling_scope"],
            item["source_method"], item["sampling_basis"],
        )
        groups[key].append(item)
    result = []
    for key in sorted(groups, key=lambda v: tuple(str(x or "") for x in v)):
        members = sorted(
            groups[key],
            key=lambda obj: (obj["period"]["start_date"], obj["evidence_id"]),
        )
        result.append({
            "family": kind,
            "source_id": key[0],
            "source_url": key[1],
            "term": key[2],
            "country": key[3],
            "language": key[4],
            "metric_type": key[5],
            "metric_unit": key[6],
            "sampling_scope": key[7],
            "source_method": key[8],
            "sampling_basis": key[9],
            "source_records_in_supplied_sample": len(members),
            "source_records_are_not_people_or_customers": True,
            "first_source_period": members[0]["period"]["start_date"],
            "last_source_period": members[-1]["period"]["start_date"],
            "observations": members[:MAX_SAMPLES_PER_GROUP],
            "observations_truncated": len(members) > MAX_SAMPLES_PER_GROUP,
            "source_metric_values_summed": False,
            "source_coverage_partial_or_unavailable": any(
                obj["coverage_status"] != "observed" for obj in members
            ),
        })
    return result[:MAX_REPORT_ITEMS]


def _keyword_families(
    sourced: list[TrendSignal],
    refs: dict[tuple[Any, ...], dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    """M02 conservative lexical grouping; never mix evidence levels.

    Exact source repeats of a term are grouped before the potentially
    quadratic RapidFuzz comparisons. Every original source reference is
    retained, subject to a transparently labeled output sample cap.
    """
    by_level: dict[str, dict[tuple[Any, ...], list[TrendSignal]]] = defaultdict(
        lambda: defaultdict(list),
    )
    for signal in sourced:
        if signal.coverage_status not in ("observed", "partial", "not_measured"):
            continue
        level = _level(signal)
        key = (signal.country, signal.language, signal.raw_term.casefold())
        by_level[level][key].append(signal)
    result: list[dict[str, Any]] = []
    for level in sorted(by_level):
        raw_groups = by_level[level]
        groups = [
            raw_groups[key] for key in sorted(
                raw_groups, key=lambda k: tuple(str(x or "") for x in k),
            )
        ]
        representatives = [
            sorted(group, key=_sortkey)[0] for group in groups
        ]
        clustered = cluster_keyword_signals(
            representatives, similarity_threshold=95.0,
        )
        for family in clustered["clusters"]:
            members = [
                row for item in family["members"]
                for row in groups[item["input_index"]]
            ]
            member_refs = sorted(
                [refs[_identity(s)] for s in members],
                key=lambda item: item["evidence_id"],
            )
            result.append({
                "representative": family["representative"],
                "country": family["country"],
                "language": family["language"],
                "evidence_level": level,
                "lexical_grouping": "M02_complete_link_RapidFuzz_95",
                "source_metric_values_aggregated": False,
                "semantic_equivalence_verified": False,
                "consumer_intent_verified": False,
                "member_terms": sorted({
                    item["normalized_term"] for item in member_refs
                }),
                "source_ids": sorted({
                    item["source_id"] for item in member_refs
                }),
                "source_reference_count": len(member_refs),
                "evidence_refs": [
                    {
                        "evidence_id": item["evidence_id"],
                        "source_id": item["source_id"],
                        "source_url": item["source_url"],
                        "source_record_id": item["source_record_id"],
                        "metric_type": item["metric_type"],
                        "coverage_status": item["coverage_status"],
                    }
                    for item in member_refs[:MAX_SAMPLES_PER_GROUP]
                ],
                "references_truncated": len(member_refs) > MAX_SAMPLES_PER_GROUP,
            })
    result.sort(key=lambda f: (
        f["evidence_level"], f["country"] or "", f["language"] or "",
        f["representative"].casefold(),
    ))
    return result[:MAX_KEYWORD_FAMILIES], len(result) > MAX_KEYWORD_FAMILIES


def _rising_queries(
    candidates: list[TrendSignal],
) -> list[dict[str, Any]]:
    """Only 14 fully observed contiguous daily source query points.

    This is a narrow two-window source-specific change, not M13's
    acceleration/seasonality, absolute market query count or forecast.
    """
    grouped: dict[tuple[Any, ...], list[TrendSignal]] = defaultdict(list)
    for s in candidates:
        if _level(s) != "source_attested_query":
            continue
        key = (
            s.source_id, s.source_url, s.normalized_term, s.country,
            s.language, s.metric_type, s.metric_unit, s.sampling_scope,
            s.provenance.method, s.provenance.sampling_basis,
        )
        grouped[key].append(s)
    outputs = []
    for key in sorted(grouped, key=lambda k: tuple(str(x or "") for x in k)):
        rows = grouped[key]
        if any(
            s.coverage_status != "observed" or s.value is None
            or s.period.granularity != "daily"
            or s.period.start_date != s.period.end_date
            for s in rows
        ):
            continue
        # The normalized Google 0-100 scale is ONLY comparable within
        # one exact provider observation batch (same UTC timestamp).
        if (
            key[5] == "google_trends_normalized_interest"
            and len({s.observed_at for s in rows}) != 1
        ):
            continue
        by_day: dict[Any, list[TrendSignal]] = defaultdict(list)
        for row in rows:
            by_day[row.period.start_date].append(row)
        if any(
            len({(s.value, s.observed_at) for s in matches}) > 1
            for matches in by_day.values()
        ):
            continue
        unique = sorted(
            (
                min(matches, key=_sortkey)
                for matches in by_day.values()
            ),
            key=lambda s: s.period.start_date,
        )
        if len(unique) < 14:
            continue
        window = unique[-14:]
        if any(
            b.period.start_date-a.period.start_date != timedelta(days=1)
            for a, b in zip(window, window[1:])
        ):
            continue
        previous = [float(s.value) for s in window[:7]]
        recent = [float(s.value) for s in window[7:]]
        older_mean = mean(previous)
        newer_mean = mean(recent)
        if older_mean <= 0 or newer_mean < older_mean * 1.25:
            continue
        # Do not promote a single explosive outlier as sustained rise.
        peak = max(recent)
        if peak >= 4*older_mean:
            remaining = list(recent)
            remaining.remove(peak)
            if abs(mean(remaining)-older_mean) / older_mean <= .3:
                continue
        outputs.append({
            "term": key[2], "country": key[3], "language": key[4],
            "source_id": key[0], "source_url": key[1],
            "metric_type": key[5], "metric_unit": key[6],
            "comparison_type": "two_complete_source_specific_7day_windows",
            "first_window_start": window[0].period.start_date.isoformat(),
            "first_window_end": window[6].period.start_date.isoformat(),
            "second_window_start": window[7].period.start_date.isoformat(),
            "second_window_end": window[13].period.start_date.isoformat(),
            "previous_window_mean_in_original_unit": round(older_mean, 4),
            "recent_window_mean_in_original_unit": round(newer_mean, 4),
            "source_specific_change_pct": round(
                (newer_mean/older_mean-1)*100, 2,
            ),
            "source_reference_ids": [
                _ref_id(_identity(s)) for s in window
            ],
            "source_units_not_comparable_across_providers": True,
            "search_volume_verified": False,
            "acceleration_verified": False,
            "future_growth_forecast": False,
        })
    return outputs[:MAX_REPORT_ITEMS]


def _validation_action(
    *,
    rising: list[dict[str, Any]],
    query_terms: list[dict[str, Any]],
    developers: list[dict[str, Any]],
    package: list[dict[str, Any]],
) -> dict[str, Any]:
    if not query_terms:
        return {
            "priority": "source_attested_search_queries",
            "action": (
                "Validate actual keyword demand with a qualified, "
                "rate-limit-respecting official public keyword-research "
                "source, keeping country, language and period explicit."
            ),
            "reason": (
                "No source-attested observed search query is present in the "
                "provided sample; discussion and downloads cannot replace it."
            ),
            "automatic_provider_request": False,
        }
    if not rising:
        return {
            "priority": "comparable_historical_query_windows",
            "action": (
                "Collect two complete, identically normalized and scoped "
                "source query windows before claiming rising demand."
            ),
            "reason": "No source query has met the strict growth evidence gate.",
            "automatic_provider_request": False,
        }
    if developers:
        return {
            "priority": "primary_source_problem_validation",
            "action": (
                "Review the linked public developer discussions to verify "
                "a repeated, unresolved problem with actual users before "
                "proposing a commercial product."
            ),
            "reason": (
                "The sampled discussion records do not prove customer "
                "pain, independent users or ability to pay."
            ),
            "automatic_provider_request": False,
        }
    if package:
        return {
            "priority": "independent_developer_validation",
            "action": (
                "Validate whether package download events represent "
                "real users and an independently expressed need."
            ),
            "reason": "Registry download events are not verified adopters.",
            "automatic_provider_request": False,
        }
    return {
        "priority": "independent_primary_source_corroboration",
        "action": (
            "Seek a second genuinely independent public source in the "
            "same market and period; verify user need before product claims."
        ),
        "reason": "One source measurement cannot establish market demand.",
        "automatic_provider_request": False,
    }


def synthesize_public_research(payload: Any) -> dict[str, Any]:
    """Build a no-network, source-auditable research report from M00 signals."""
    if isinstance(payload, list):
        raw = payload
    elif isinstance(payload, dict) and set(payload) == {"signals"}:
        raw = payload["signals"]
    else:
        raise ValueError("Expected a list of M00 typed signals or {'signals': [...]}")

    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_INPUT_SIGNALS:
        raise ValueError("Expected between 1 and 120 source signals")
    try:
        compact = json.dumps(
            raw, ensure_ascii=False, allow_nan=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Unserializable source signal input") from exc
    if len(compact.encode("utf-8")) > MAX_INPUT_BYTES:
        raise ValueError("Source signal input exceeds 128 KiB")

    source_records = sorted(
        [_checked_signal(row) for row in raw], key=_sortkey,
    )
    unique: dict[tuple[Any, ...], TrendSignal] = {}
    for record in source_records:
        unique.setdefault(_identity(record), record)
    records = sorted(unique.values(), key=_sortkey)
    ref_by_identity = {
        _identity(record): _source_item(record) for record in records
    }
    refs = list(ref_by_identity.values())

    interest = [
        row for row in refs
        if row["metric_type"] in _SEARCH_METRICS
        and row["evidence_level"] != "unavailable_or_no_data_source"
    ]
    attention = [
        row for row in refs
        if row["metric_type"] in _ATTENTION_METRICS
        and row["evidence_level"] != "unavailable_or_no_data_source"
    ]
    developers = [
        row for row in refs
        if row["metric_type"] in _DEVELOPER_METRICS
        and row["evidence_level"] != "unavailable_or_no_data_source"
    ]
    packages = [
        row for row in refs
        if row["metric_type"] in _PACKAGE_METRICS
        and row["evidence_level"] != "unavailable_or_no_data_source"
    ]
    generated = [
        row for row in refs
        if row["evidence_level"] == "generated_keyword_hypothesis"
    ]
    attested = [
        row for row in refs
        if row["evidence_level"] == "source_attested_query"
    ]
    rising = _rising_queries(records)
    families, families_truncated = _keyword_families(
        records, ref_by_identity,
    )

    # A generated term does not become a product recommendation until
    # independently validated. It only supplies an explicit question.
    hypotheses = [
        {
            "hypothesis_term": row["raw_term"],
            "country": row["country"],
            "language": row["language"],
            "evidence_level": "hypothetical_business_opportunity",
            "grounded_in_generated_source_claim": row["evidence_id"],
            "source_url": row["source_url"],
            "source_record_id": row["source_record_id"],
            "validation_question": (
                "Do independent users report a recurring, unresolved need "
                f"related to '{row['raw_term']}' and express willingness "
                "to use or pay for a concrete solution?"
            ),
            "demand_verified": False,
            "buyer_intent_verified": False,
            "product_recommendation": False,
        }
        for row in generated[:MAX_REPORT_ITEMS]
    ]
    gaps = []
    if not attested:
        gaps.append({
            "kind": "observed_query_missing",
            "detail": (
                "No qualified source-attested literal search query exists "
                "in the supplied records; topics and seed research are not user logs."
            ),
        })
    if not rising:
        gaps.append({
            "kind": "rising_query_evidence_missing",
            "detail": (
                "No query met the strict two fully observed, comparable "
                "seven-day windows and >=25% source-specific change gate."
            ),
        })
    if any(row["country"] is None for row in refs):
        gaps.append({
            "kind": "market_geography_unspecified",
            "detail": "Null country is an unknown market, not global coverage.",
        })
    if developers:
        gaps.append({
            "kind": "developer_need_not_verified",
            "detail": (
                "Public issues, Stack Overflow questions and HN stories "
                "are discussion evidence, not verified unique unresolved problems."
            ),
        })
    if packages:
        gaps.append({
            "kind": "download_events_not_people",
            "detail": (
                "Registry downloads can contain mirrors, CI, bots, indirect "
                "dependency installs and repeated requests. Unique users "
                "and paid adoption are not verified."
            ),
        })
    gaps.append({
        "kind": "business_impact_not_measured",
        "detail": (
            "No purchase intent, conversions, competition, SEO difficulty "
            "or causal market size is measured from these source signals."
        ),
    })

    source_gaps: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for row in refs:
        if row["coverage_status"] in ("partial", "unavailable", "no_data"):
            source_gaps[(
                row["source_id"], row["source_url"], row["coverage_status"],
            )].append(row["evidence_id"])
    for (source_id, source_url, status), identifiers in sorted(source_gaps.items()):
        gaps.append({
            "kind": "source_coverage",
            "source_id": source_id,
            "source_url": source_url,
            "status": status,
            "affected_input_observation_count": len(identifiers),
            "sample_evidence_ids": sorted(identifiers)[:3],
            "missing_is_zero": False,
            "action": "Check original source coverage without bypassing provider limits.",
        })
    # Exact lexical term overlaps identify source diversity only, not
    # genuinely independent people or topic-level semantic support.
    by_term: dict[tuple[Any, ...], set[str]] = defaultdict(set)
    for row in refs:
        if row["coverage_status"] in ("observed", "partial") and (
            row["evidence_level"] not in (
                "generated_keyword_hypothesis",
                "operator_or_derived_source_claim",
            )
        ):
            by_term[(
                row["normalized_term"], row["country"], row["language"],
            )].add(row["source_id"])
    overlaps = [
        {
            "normalized_term": key[0],
            "country": key[1],
            "language": key[2],
            "distinct_source_ids": sorted(sources),
            "source_count": len(sources),
            "semantic_or_customer_independence_verified": False,
        }
        for key, sources in sorted(
            by_term.items(),
            key=lambda item: tuple(str(x or "") for x in item[0]),
        )
        if len(sources) >= 2
    ]
    note = (
        "Source counts describe this supplied input, not all results "
        "on a platform or independent people. No unlike numeric metrics "
        "are summed; a shared term across sources does not establish causality."
    )
    return {
        "schema_version": 1,
        "mode": "offline_source_attributed_cross_source_research",
        "network_performed": False,
        "source_provider_operations": 0,
        "sqlite_or_quotas_modified": False,
        "paid_services_used": False,
        "site_property_required": False,
        "new_background_automation_created": False,
        "input_signal_records": len(raw),
        "deduplicated_source_records": len(records),
        "exact_input_duplicates_collapsed": len(raw) - len(records),
        "source_metric_values_aggregated": False,
        "semantic_equivalence_or_causality_verified": False,
        "market_demand_score": None,
        "search_volume_estimate": None,
        "rising_queries": rising,
        "observed_query_candidates": sorted(
            attested, key=lambda r: r["evidence_id"],
        ),
        "keyword_families": families,
        "keyword_families_truncated": families_truncated,
        "country_language_interest": _sample_group(interest, kind="search_interest"),
        "independent_attention": _sample_group(attention, kind="public_attention"),
        "developer_problem_evidence": _sample_group(
            developers, kind="developer_discussion_unverified_problem",
        ),
        "package_adoption_evidence": _sample_group(
            packages, kind="package_download_events_not_unique_users",
        ),
        "product_hypotheses": hypotheses,
        "data_gaps": gaps[:MAX_GAPS],
        "data_gaps_truncated": len(gaps) > MAX_GAPS,
        "next_validation_action": _validation_action(
            rising=rising, query_terms=attested,
            developers=developers, package=packages,
        ),
        "source_diversity_exact_term_only": overlaps[:MAX_REPORT_ITEMS],
        "metric_definitions": {
            name: {"unit": unit, "evidence_class": level}
            for name, (unit, level) in METRIC_DEFINITIONS.items()
        },
        "supplied_evidence_level_counts": dict(sorted(Counter(
            row["evidence_level"] for row in refs
        ).items())),
        "source_inventory": [
            {
                "source_id": source,
                "source_observations_in_input": sum(
                    item["source_id"] == source for item in refs
                ),
                "independent_humans_verified": False,
            }
            for source in sorted({row["source_id"] for row in refs})
        ],
        "methodology_note": note,
        "offline_evidence_caution": (
            "Typed source claims are validated structurally but NOT "
            "re-fetched or independently verified online by this report. "
            "Source date, attribution and coverage must be verified by "
            "the original bounded provider adapters."
        ),
    }


def format_public_research(report: dict[str, Any]) -> str:
    lines = [
        "M14 OFFLINE SOURCE-ATTRIBUTED RESEARCH",
        f"Source records: {report['deduplicated_source_records']} "
        f"(from {report['input_signal_records']} input records)",
        "No network. No summed demand score, forecasts or site property.",
        f"Verified within-source rising query windows: {len(report['rising_queries'])}",
        f"Attested search-query candidate records: {len(report['observed_query_candidates'])}",
        f"Lexical keyword families: {len(report['keyword_families'])}",
    ]
    for key, title in (
        ("country_language_interest", "Search interest / source query metrics"),
        ("independent_attention", "Public attention proxies"),
        ("developer_problem_evidence", "Developer discussion, NOT verified problems"),
        ("package_adoption_evidence", "Package download events, NOT unique users"),
    ):
        groups = report[key]
        lines.append(f"{title}: {len(groups)} source/term groups")
        for item in groups[:8]:
            lines.append(
                f"- {item['term']} | {item['source_id']}:"
                f"{item['metric_type']} ({item['metric_unit']}) | "
                f"{item['source_records_in_supplied_sample']} sampled source rows "
                f"| {item['source_url']}"
            )
        if len(groups) > 8:
            lines.append("  ...additional groups are present in JSON")
    lines.append(
        f"Unmeasured product hypotheses: {len(report['product_hypotheses'])}"
    )
    lines.append(f"Data gaps: {len(report['data_gaps'])}")
    for gap in report["data_gaps"][:6]:
        lines.append(f"- {gap['kind']}: {gap.get('detail', gap.get('status', ''))}")
    lines.append(
        "Next validation: " + report["next_validation_action"]["action"]
    )
    return "\n".join(lines)
