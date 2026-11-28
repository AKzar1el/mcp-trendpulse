"""V4.06: offline coverage normalization and source concentration.

Counts are scoped to supplied captures. Article identifiers are provider-scoped;
event candidates are not verified events. Publisher labels/hosts are not owners
or independent reporting sources. No network, registry change or persistence.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from mcp_trendpulse.news_intelligence_dedup import MAX_OBSERVATIONS
from mcp_trendpulse.news_intelligence_events import cluster_news_events
from mcp_trendpulse.news_intelligence_schema import (
    GDELT_ATTRIBUTION,
    GdeltCoverage,
    NewsBatch,
    _utc,
    gdelt_doc_request,
)

MAX_BATCHES = 16
_SUCCESS = frozenset({"observed", "partial", "empty"})
_TIMELINE_STATES = frozenset({"planned", "observed", "empty", "invalid", "unavailable"})


def _share(matched, monitored):
    # Avoid rounding a small nonzero measured share into a false zero.
    return 100 * matched / monitored if monitored else None


def _distribution(groups):
    # One known label per provider-scoped article; conflicting/missing values
    # are unknown, not a fictitious publisher or an independent source.
    counts = Counter()
    unknown = conflicting = 0
    for labels in groups.values():
        if len(labels) == 1:
            counts[next(iter(labels))] += 1
        elif labels:
            conflicting += 1
        else:
            unknown += 1
    known = sum(counts.values())
    total = len(groups)
    ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    return {
        "article_key_count": total,
        "known_label_article_count": known,
        "unknown_label_article_count": unknown,
        "conflicting_label_article_count": conflicting,
        "distinct_known_labels": len(counts),
        "known_label_coverage_pct": _share(known, total),
        "largest_known_label_share_pct": _share(ranked[0][1], known) if ranked else None,
        "top_three_known_label_share_pct": _share(sum(n for _, n in ranked[:3]), known),
        "hhi_known_labels_0_to_10000": round(10000 * sum(n*n for n in counts.values()) / (known*known), 6)
        if known else None,
        "labels": [{"label": label, "article_keys": count, "share_of_known_pct": _share(count, known)}
                   for label, count in ranked],
    }


def summarize_news_snapshot(batches, *, as_of, hints=()):
    """Describe a bounded sample, with event candidates computed from its evidence.

    A batch is a capture, not an exhaustive query or a disjoint population.
    Source counts are not summed across overlapping captures.
    """
    cutoff = _utc(as_of)
    end = datetime.fromisoformat(cutoff)
    if not isinstance(batches, (list, tuple)) or len(batches) > MAX_BATCHES:
        raise ValueError("Expected a bounded news batch sequence")
    clean = []
    for batch in batches:
        if not isinstance(batch, NewsBatch):
            raise ValueError("Expected a typed news batch")
        try:
            batch = NewsBatch.model_validate_json(batch.model_dump_json())
        except (ValueError, TypeError):
            raise ValueError("Invalid news batch") from None
        if batch.captured_at and datetime.fromisoformat(batch.captured_at) > end:
            raise ValueError("Batch capture after cutoff")
        clean.append(batch)
    raw = [row for batch in clean for row in batch.articles]
    if len(raw) > MAX_OBSERVATIONS:
        raise ValueError("Snapshot observation budget exceeded")
    # Reuse the event API's observation validation and cutoff checks. Preserve
    # every distinct revision, rather than count repeated captures as articles.
    event_report = cluster_news_events(raw, as_of=cutoff, hints=hints)
    observations = {row.observation_id: row for row in raw}
    by_article = defaultdict(list)
    for row in observations.values():
        by_article[row.article_id].append(row)

    publishers = {}
    hosts = {}
    providers = Counter()
    for key, rows in by_article.items():
        providers[rows[0].discovery_provider] += 1
        publishers[key] = {r.publisher_label.casefold() for r in rows if r.publisher_label}
        # Google RSS links are discovery links, not publisher host evidence.
        hosts[key] = {urlsplit(r.reported_url).hostname for r in rows
                      if r.link_type == "publisher_candidate" and urlsplit(r.reported_url).hostname}

    successful = [batch for batch in clean if batch.status in _SUCCESS]
    status = "unavailable" if not successful else (
        "partial" if any(b.status in ("partial", "invalid", "unavailable") or b.possibly_capped
                         for b in clean) else "observed" if raw else "empty"
    )
    # A known empty supplied capture can establish zero within that capture,
    # but unavailable/no captures alone cannot establish even a sample zero.
    known = bool(successful)
    stamps = Counter()
    publication_days = Counter()
    publication_utc_days = Counter()
    seen_utc_days = Counter()
    capture_utc_days = Counter()
    for row in observations.values():
        if row.published_at is None:
            stamps["publication_unknown"] += 1
        elif row.published_at.precision == "day":
            publication_days[row.published_at.value] += 1
        else:
            publication_utc_days[_utc(row.published_at.value)[:10]] += 1
        if row.provider_seen_at is None:
            stamps["provider_seen_unknown"] += 1
        else:
            seen_utc_days[_utc(row.provider_seen_at.value)[:10]] += 1
        if row.captured_at is None:
            stamps["capture_unknown"] += 1
        else:
            capture_utc_days[row.captured_at[:10]] += 1
    batch_summaries = [
        {"provider": b.provider, "status": b.status, "captured_at": b.captured_at,
         "source_count": b.source_count, "accepted_records": len(b.articles) if b.source_count is not None else None,
         "invalid_count": b.invalid_count, "duplicate_count": b.duplicate_count,
         "truncated_count": b.truncated_count, "possibly_capped": b.possibly_capped, "reason": b.reason}
        for b in clean
    ]
    # Preserve input batch order only through the stable serialized summaries.
    batch_summaries.sort(key=lambda x: json.dumps(x, sort_keys=True))
    return {
        "schema_version": 1, "method": "bounded_news_snapshot_v1",
        "as_of": cutoff, "status": status, "network_performed": False,
        "batch_count": len(clean), "batch_status_counts": dict(sorted(Counter(b.status for b in clean).items())),
        "capture_summaries": batch_summaries,
        "supplied_accepted_observations": len(raw) if known else None,
        "distinct_observations": len(observations) if known else None,
        "exact_replays_removed": len(raw) - len(observations) if known else None,
        "provider_scoped_article_keys": len(by_article) if known else None,
        "distinct_reported_url_strings": len({r.reported_url for r in observations.values()}) if known else None,
        "distinct_discovery_providers": len(providers) if known else None,
        "provider_article_key_counts": dict(sorted(providers.items())) if known else None,
        "publisher_label_concentration": _distribution(publishers) if known else None,
        "reported_publisher_host_concentration": _distribution(hosts) if known else None,
        "event_candidate_count": event_report["candidate_count"] if known else None,
        "event_mention_count": event_report["mention_count"] if known else None,
        "verified_event_count": None, "independent_reporting_source_count": None,
        "monitored_universe_count": None, "normalized_coverage_pct": None,
        "unknown_time_counts": {k: stamps[k] for k in (
            "publication_unknown", "provider_seen_unknown", "capture_unknown"
        )} if known else None,
        "observation_date_breakdowns": {
            "unit": "distinct_observations_not_unique_articles",
            "reported_publication_calendar_day": dict(sorted(publication_days.items())),
            "reported_publication_timestamp_utc_day": dict(sorted(publication_utc_days.items())),
            "provider_seen_utc_day": dict(sorted(seen_utc_days.items())),
            "capture_utc_day": dict(sorted(capture_utc_days.items())),
        } if known else None,
        "event_report": event_report if known else None,
        "limitations": [
            "Only the supplied captures are described; successful feeds and capped article lists are not a monitored universe.",
            "Provider-scoped article keys may represent the same article across providers; URLs can change or be reused.",
            "Publisher labels and exact reported hosts are not ownership, syndication or independent-source counts.",
            "Concentration is calculated only over known nonconflicting labels; no market-share or antitrust interpretation.",
            "Candidate events and mentions are not verified occurrences. Publication and provider-seen timestamps stay separate.",
        ],
    }


def summarize_gdelt_coverage(report, *, expected_interval_seconds=None):
    """Normalize an existing collector receipt, not bare counts of unknown scope.

    Optional grid diagnostics apply only to a caller-declared aligned cadence.
    Returned intervals are the aggregation scope, never assumed exhaustive.
    The collector request and evidence are revalidated without performing I/O.
    """
    if not isinstance(report, dict) or len(report) > 24 or report.get("source") != "gdelt_timeline":
        raise ValueError("Expected a GDELT timeline collector receipt")
    if report.get("provider") != "gdelt_doc" or report.get("attribution") != GDELT_ATTRIBUTION:
        raise ValueError("Incorrect timeline provenance")
    scope = report.get("scope")
    required = {"coverage", "query", "as_of", "days", "country_filter", "language_filter", "pagination", "limit", "mode"}
    if not isinstance(scope, dict) or set(scope) != required or (
        scope["mode"] != "timelinevolraw" or scope["country_filter"] is not None
        or scope["language_filter"] is not None or scope["limit"] is not None
        or scope["pagination"] != "none"
        or scope["coverage"] != "GDELT monitored news, translated search, not all worldwide news"
    ):
        raise ValueError("Unsupported timeline scope")
    end = datetime.fromisoformat(_utc(scope["as_of"]))
    plan = gdelt_doc_request(scope["query"], as_of=end.isoformat(), days=scope["days"], mode="timelinevolraw")
    if report.get("url") != plan["url"] or report.get("method") != "GET":
        raise ValueError("Timeline must match the unsmoothed raw-count request")
    start = end - timedelta(days=scope["days"])
    if expected_interval_seconds is not None and (
        type(expected_interval_seconds) is not int or expected_interval_seconds not in (900, 3600, 86400)
    ):
        raise ValueError("Unsupported declared interval cadence")
    if expected_interval_seconds is not None:
        step = timedelta(seconds=expected_interval_seconds)
        epoch = datetime(1970, 1, 1, tzinfo=end.tzinfo)
        if (start - epoch) % step or (end - epoch) % step:
            raise ValueError("Declared grid requires aligned query boundaries")

    status = report.get("status")
    if not isinstance(status, str) or status not in _TIMELINE_STATES:
        raise ValueError("Unsupported timeline status")
    evidence = report.get("evidence")
    capture = report.get("captured_at")
    points = ()
    if status in ("observed", "empty"):
        # Collector outcomes may be cache replays (no HTTP status), but an
        # explicit contradictory HTTP status cannot establish a measurement.
        if report.get("http_status") not in (None, 200):
            raise ValueError("Timeline measurement conflicts with HTTP status")
        if not isinstance(evidence, dict) or not isinstance(evidence.get("points"), (list, tuple)):
            raise ValueError("Missing timeline evidence")
        if len(evidence["points"]) > 500:
            raise ValueError("Timeline exceeds point budget")
        capture = _utc(capture)
        if datetime.fromisoformat(capture) < end:
            raise ValueError("Timeline capture precedes requested cutoff")
        try:
            typed = GdeltCoverage.model_validate_json(json.dumps(evidence, allow_nan=False))
        except (ValueError, TypeError):
            raise ValueError("Invalid timeline evidence") from None
        if typed.status != status:
            raise ValueError("Timeline status mismatch")
        points = typed.points
        for point in points:
            at = datetime.fromisoformat(point.interval_at)
            if not start <= at <= end or at > datetime.fromisoformat(capture):
                raise ValueError("Timeline point outside requested window")
    elif evidence is not None:
        raise ValueError("Unobserved timeline must not contain measurements")
    else:
        capture = None

    rows = [
        {"interval_at": p.interval_at, "matched": p.matched, "monitored": p.monitored,
         "coverage_pct": _share(p.matched, p.monitored)}
        for p in points
    ]
    matched = sum(p.matched for p in points) if points else None
    monitored = sum(p.monitored for p in points) if points else None
    grid = None
    if expected_interval_seconds is not None:
        # A diagnostic against a caller-declared start-labelled half-open grid;
        # not a provider guarantee. Do not infer missing bins as zero.
        expected = int((end - start) // step)
        aligned = {p.interval_at for p in points if datetime.fromisoformat(p.interval_at) < end
                   and (datetime.fromisoformat(p.interval_at) - start) % step == timedelta(0)}
        grid = {
            "declared_interval_seconds": expected_interval_seconds,
            "expected_bins_on_declared_grid": expected,
            "observed_aligned_bins": len(aligned) if points else None,
            "missing_bins_on_declared_grid": expected - len(aligned) if points else None,
            "off_grid_or_end_boundary_points": len(points) - len(aligned) if points else None,
            "provider_completeness_verified": False,
        }
    return {
        "schema_version": 1, "method": "gdelt_unsmoothed_coverage_v1",
        "provider": "gdelt_doc", "attribution": GDELT_ATTRIBUTION,
        "status": status, "network_performed": False, "captured_at": capture,
        "query": scope["query"], "window_start": start.isoformat(), "window_end": end.isoformat(),
        "source_request_url": plan["url"], "returned_interval_count": len(rows) if status in ("observed", "empty") else None,
        "zero_denominator_intervals": sum(p.monitored == 0 for p in points) if points else None,
        "matched_articles_in_returned_intervals": matched,
        "monitored_articles_in_returned_intervals": monitored,
        "weighted_coverage_pct": _share(matched, monitored) if monitored is not None else None,
        "points": rows, "declared_grid_diagnostics": grid,
        "full_window_coverage_verified": False, "worldwide_news_coverage_verified": False,
        "limitations": [
            "Weighted share = sum of matched counts divided by sum of monitored counts over returned intervals.",
            "Only unsmoothed GDELT monitored counts are comparable here; the monitored population is not all news.",
            "Missing intervals and zero denominators have unknown shares; an empty result is not zero articles.",
            "Counts are interval totals, not unique articles across a whole period, people, events or commercial demand.",
            "Caller-supplied collector receipts are structurally validated, not authenticated provider responses.",
        ],
    }
