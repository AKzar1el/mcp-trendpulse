"""V5.04: bounded import of attributed third-party fact-check metadata.

No remote JSON-LD context resolution, page fetching, credentials, API call,
rating normalization, or claim matching. Caller must establish metadata rights.
"""
from __future__ import annotations

import json
import math
import re
from datetime import date, datetime
from typing import Literal

from mcp_trendpulse.news_intelligence_schema import MAX_BYTES, _digest, _text, _url, _utc

MAX_CLAIMS = 20
MAX_REVIEWS = 40
ReviewFormat = Literal["google_claim_search", "claimreview_jsonld"]


def _object(value):
    if not isinstance(value, dict):
        raise ValueError("Expected metadata object")
    return value


def _optional(value, maximum=512):
    return None if value is None else _text(value, maximum)


def _date(value, captured_at):
    if value is None:
        return None
    _text(value, 64)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        if date.fromisoformat(value) > datetime.fromisoformat(captured_at).date():
            raise ValueError("Review date after capture")
    else:
        # Google can report nanosecond precision. Preserve the exact original
        # string; Python's comparison resolution is microseconds.
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})", value):
            raise ValueError("Unsupported review timestamp")
        if datetime.fromisoformat(value.replace("Z", "+00:00")) > datetime.fromisoformat(captured_at):
            raise ValueError("Review date after capture")
    return value


def _rating(value):
    if value is None:
        return None
    if isinstance(value, str):
        return _text(value, 160)
    if type(value) in (int, float) and abs(value) <= 10**15 and math.isfinite(value):
        return value
    raise ValueError("Unsupported rating representation")


def _row(*, claim, claimant, claim_date, url, publisher, publisher_site, title,
         review_date, language, textual_rating, rating_value, worst_rating, best_rating, captured_at):
    row = {
        "reviewed_claim": _text(claim, 512), "claimant": _optional(claimant, 160),
        "claim_date_reported": _date(claim_date, captured_at),
        "review_url": _url(url), "review_publisher": _text(publisher, 160),
        "publisher_site_reported": _optional(publisher_site, 160),
        "review_title": _optional(title), "review_date_reported": _date(review_date, captured_at),
        "language_reported": _optional(language, 32),
        "original_rating": {
            "text": _optional(textual_rating, 160), "value": _rating(rating_value),
            "worst": _rating(worst_rating), "best": _rating(best_rating),
        },
        "captured_at": captured_at, "target_claim_match": "not_assessed",
        "rating_assessment": "third_party_reported_not_verified",
    }
    if row["original_rating"]["text"] is None and row["original_rating"]["value"] is None:
        raise ValueError("Review has no reported rating")
    row["review_id"] = _digest(row)
    return row


def _google_row(claim, review, captured_at):
    claim, review = _object(claim), _object(review)
    publisher = _object(review.get("publisher"))
    return _row(claim=claim.get("text"), claimant=claim.get("claimant"), claim_date=claim.get("claimDate"),
                url=review.get("url"), publisher=publisher.get("name"), publisher_site=publisher.get("site"),
                title=review.get("title"), review_date=review.get("reviewDate"), language=review.get("languageCode"),
                textual_rating=review.get("textualRating"), rating_value=None, worst_rating=None, best_rating=None,
                captured_at=captured_at)


def _literal_references(value, item):
    # Literal metadata references only; do not infer relationships from URLs
    # or follow archive links. Omitted/malformed references are not evidence.
    found = set()
    rejected = 0
    for kind, obj in (
        ("claim_first_appearance", item.get("firstAppearance")),
        ("claim_appearance", item.get("appearance")),
        ("review_citation", value.get("citation")),
        ("review_correction", value.get("correction")),
        ("review_archived_at", value.get("archivedAt")),
    ):
        if obj is None:
            continue
        entries = obj if isinstance(obj, list) else [obj]
        if len(entries) > 8:
            raise ValueError("Reference list exceeds bound")
        for entry in entries:
            try:
                if isinstance(entry, dict):
                    entry = entry.get("url")
                url = _url(entry)
            except (ValueError, TypeError):
                rejected += 1
                continue
            found.add((kind, url))
    return [{"kind": kind, "url": url} for kind, url in sorted(found)], rejected


def _jsonld_row(value, captured_at):
    value = _object(value)
    rating = _object(value.get("reviewRating"))
    author = _object(value.get("author"))
    item = _object(value.get("itemReviewed", {}))
    claimant = _object(item.get("author", {}))
    row = _row(claim=value.get("claimReviewed"), claimant=claimant.get("name"),
                claim_date=item.get("datePublished"), url=value.get("url"), publisher=author.get("name"),
                publisher_site=None, title=value.get("headline"), review_date=value.get("datePublished"),
                language=value.get("inLanguage"), textual_rating=rating.get("alternateName"),
                rating_value=rating.get("ratingValue"), worst_rating=rating.get("worstRating"),
                best_rating=rating.get("bestRating"), captured_at=captured_at)
    references, rejected = _literal_references(value, item)
    row["literal_reference_candidates"] = references
    row["rejected_reference_count"] = rejected
    row["review_id"] = _digest({k: v for k, v in row.items() if k != "review_id"})
    return row


def _is_claimreview(value):
    return isinstance(value, dict) and (
        value.get("@type") in ("ClaimReview", "https://schema.org/ClaimReview")
        or isinstance(value.get("@type"), list)
        and any(x in ("ClaimReview", "https://schema.org/ClaimReview") for x in value["@type"])
    )


def _reject_constant(_):
    raise ValueError("Nonfinite JSON")


def parse_review_capture(raw, *, format: ReviewFormat, captured_at, permit_metadata=False):
    """Parse explicitly permitted saved metadata; no implicit rights or fetch.

    JSON-LD support is a narrow literal projection, not a general JSON-LD
    processor. Missing/invalid reviews and partial pages never imply falsehood.
    """
    if permit_metadata is not True:
        raise ValueError("Explicit metadata retention permission required")
    if format not in ("google_claim_search", "claimreview_jsonld"):
        raise ValueError("Unknown review format")
    captured_at = _utc(captured_at)
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ValueError("Invalid capture byte budget")
    try:
        payload = json.loads(raw, parse_constant=_reject_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError("Invalid saved review JSON") from None
    candidates = []
    missing = 0
    has_more = False
    if format == "google_claim_search":
        payload = _object(payload)
        if any(key in payload for key in ("error", "errors", "fault")):
            raise ValueError("Review API error envelope")
        has_more = bool(payload.get("nextPageToken"))
        # An omitted claims array is ambiguous; never manufacture an empty result.
        claims = payload.get("claims")
        if claims is None:
            missing = 1
        elif not isinstance(claims, list) or len(claims) > MAX_CLAIMS:
            raise ValueError("Review claim budget or shape invalid")
        else:
            for claim in claims:
                reviews = claim.get("claimReview") if isinstance(claim, dict) else None
                if not isinstance(reviews, list) or not reviews:
                    missing += 1
                    continue
                if len(candidates) + len(reviews) > MAX_REVIEWS:
                    raise ValueError("Review row budget exceeded")
                candidates.extend((claim, review) for review in reviews)
    else:
        # Accept one object, one top-level array or one literal @graph array.
        # Never expand remote contexts or traverse linked objects.
        nodes = payload.get("@graph", [payload]) if isinstance(payload, dict) else payload
        if not isinstance(nodes, list) or len(nodes) > MAX_REVIEWS:
            raise ValueError("ClaimReview node budget or shape invalid")
        candidates = [node for node in nodes if _is_claimreview(node)]
        missing = int(not candidates)

    rows = {}
    rejected = 0
    for candidate in candidates:
        try:
            row = (_google_row(*candidate, captured_at) if format == "google_claim_search"
                   else _jsonld_row(candidate, captured_at))
        except (ValueError, TypeError, OverflowError):
            rejected += 1
            continue
        rows[row["review_id"]] = row
    rejected_refs = sum(row.get("rejected_reference_count", 0) for row in rows.values())
    status = ("partial" if missing or rejected or has_more or rejected_refs else "observed") if rows else (
        "invalid" if rejected else "unavailable" if missing or has_more else "empty")
    report = {
        "schema_version": 1, "method": "saved_review_metadata_v1", "format": format,
        "captured_at": captured_at, "status": status, "review_count": len(rows),
        "supplied_review_rows": len(candidates), "missing_claim_or_review_groups": missing,
        "rejected_rows": rejected, "rejected_reference_count": rejected_refs,
        "exact_replays_removed": len(candidates) - rejected - len(rows),
        "more_results_reported": has_more, "reviews": [rows[k] for k in sorted(rows)],
        "network_performed": False, "claim_verification": "not_performed",
        "limitations": [
            "Caller-supplied metadata and publisher identity are not authenticated.",
            "Original ratings belong to their named publishers and are not converted into TrendPulse verdicts.",
            "Review matching, correction history, original evidence, scope, and independence are not established.",
            "Missing fact-check results do not show that a claim is true or false.",
        ],
    }
    report["report_id"] = _digest(report)
    return report
