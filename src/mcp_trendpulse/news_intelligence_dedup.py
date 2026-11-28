"""V4.04: bounded, source-preserving offline news duplicate evidence.

Exact repeated observation IDs may be collapsed for display. Link equality,
body matches, and headline similarity are different relations; none establishes
event identity, original reporting, or independent corroboration. No network,
persistence, URL rewriting, or new dependencies.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date, datetime
from itertools import combinations

from rapidfuzz import fuzz

from mcp_trendpulse.intelligence_keywords import normalize_keyword
from mcp_trendpulse.news_intelligence_extract import ArticleExtraction
from mcp_trendpulse.news_intelligence_schema import NewsArticle, _utc

MAX_OBSERVATIONS = 80
MAX_BODY_INPUTS = 16
MAX_BODY_BYTES = 512 * 1024
MAX_TOTAL_BODY_BYTES = 2 * 1024 * 1024
MAX_BODY_TOKENS = 30000
_ALGORITHM = "news_duplicate_evidence_v1"
_TITLE_RATIO = 96.0
_BODY_SHINGLE_RATIO = 0.90
_NUMBER = re.compile(r"[+\-\u2212]?\d+(?:[.,:/]\d+)*(?:\s?[%‰])?")
_WORD = re.compile(r"\w+|[^\w\s]", re.UNICODE)
# Small, conservative guard, NOT a general multilingual negation detector.
_POLARITY = frozenset({
    "no", "not", "never", "without", "denies", "denied", "rejects", "rejected",
    "approves", "approved", "bans", "banned", "lifts", "lifted", "rises", "falls",
    "up", "down", "before", "after", "wins", "loses", "kein", "keine", "nicht",
    "ohne", "nie", "nein", "ne", "ni", "niso", "brez", "nikoli",
})


def _strict_sequence(value, maximum):
    if not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValueError("Expected bounded observation or extraction list")
    return value


def _normalized(value):
    try:
        return normalize_keyword(value)
    except ValueError:
        return ""


def _markers(value):
    text = unicodedata.normalize("NFC", value).casefold()
    numbers = tuple(sorted(match.group().replace(" ", "") for match in _NUMBER.finditer(text)))
    words = re.findall(r"\w+", text)
    polarity = tuple(sorted(word for word in words if word in _POLARITY))
    # Preserve important symbols even where lexical normalization strips them.
    symbols = tuple(sorted(c for c in text if c in "+-−#%‰$€£¥<>="))
    return numbers, polarity, symbols


def _date_distance(left, right):
    # Publication and provider-seen time are never treated as interchangeable.
    if left.published_at is not None and right.published_at is not None:
        a, b = left.published_at, right.published_at
    elif left.provider_seen_at is not None and right.provider_seen_at is not None:
        a, b = left.provider_seen_at, right.provider_seen_at
    else:
        return None
    if (a.precision == "day") != (b.precision == "day"):
        return None
    if a.precision == "day":
        return abs((date.fromisoformat(a.value) - date.fromisoformat(b.value)).days) * 86400
    return abs((datetime.fromisoformat(_utc(a.value)) - datetime.fromisoformat(_utc(b.value))).total_seconds())


def _language(observation, receipt):
    # No inferred translations or equivalence between provider language labels.
    labels = {x.strip().casefold() for x in (
        observation.reported_language, receipt.extractor_language if receipt else None
    ) if x}
    return labels


def _body_features(text, expected):
    if not isinstance(text, str) or len(text) > MAX_BODY_BYTES:
        raise ValueError("Invalid ephemeral body input")
    try:
        raw = text.encode("utf-8", "strict")
    except UnicodeError:
        raise ValueError("Invalid ephemeral body encoding") from None
    if len(raw) > MAX_BODY_BYTES or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Ephemeral body does not match permitted extraction digest")
    normalized = unicodedata.normalize("NFC", text).casefold()
    tokens = _WORD.findall(normalized)
    if len(tokens) > MAX_BODY_TOKENS:
        raise ValueError("Ephemeral body token budget exceeded")
    # Full-length 5-token shingles; no partial/subset score and no boilerplate
    # claim. Short/repetitive bodies abstain even if normalized text matches.
    shingles = frozenset(tuple(tokens[i:i + 5]) for i in range(max(0, len(tokens) - 4)))
    if len(tokens) < 80 or len(shingles) < 40:
        return len(raw), None
    fingerprint = hashlib.sha256(" ".join(normalized.split()).encode("utf-8")).hexdigest()
    return len(raw), (fingerprint, shingles, len(tokens), _markers(text))


def _headline_features(observation):
    key = _normalized(observation.title)
    return key, tuple(key.split()), _markers(observation.title)


def _compare(left, right, receipts, bodies, headlines):
    li, ri = left.observation_id, right.observation_id
    le, re_ = receipts.get(li), receipts.get(ri)
    relations = []
    guards = []
    if left.reported_url == right.reported_url:
        relations.append("same_reported_url")
    lr = le.resolved_url if le else None
    rr = re_.resolved_url if re_ else None
    if lr and rr and lr == rr:
        relations.append("same_resolved_url")
    if (lr and lr == right.reported_url) or (rr and rr == left.reported_url):
        relations.append("resolved_reported_url_match")
    lc = le.canonical_url_candidate if le else None
    rc = re_.canonical_url_candidate if re_ else None
    if (lc and lc in (right.reported_url, rr, rc)) or (rc and rc in (left.reported_url, lr)):
        relations.append("canonical_candidate_match")
    # These digest receipts are caller-provided, not cryptographic proof of origin.
    if le and re_ and le.body_sha256 and le.body_sha256 == re_.body_sha256:
        relations.append("matching_extracted_digest")
    ll, rl = _language(left, le), _language(right, re_)
    if len(ll) > 1 or len(rl) > 1:
        guards.append("language_label_conflict")
    elif ll and rl and ll != rl:
        guards.append("different_language_labels")
    distance = _date_distance(left, right)
    if distance is None:
        guards.append("comparable_date_unknown")
    elif distance > 72 * 3600:
        guards.append("reported_dates_apart")
    ln, lt, lm = headlines[li]
    rn, rt, rm = headlines[ri]
    if lm != rm:
        guards.append("different_headline_factual_markers")

    title_score = None
    if min(len(ln), len(rn)) >= 30 and min(len(lt), len(rt)) >= 6:
        title_score = float(fuzz.ratio(ln, rn))
        shared = set(lt) & set(rt)
        union = set(lt) | set(rt)
        if title_score >= _TITLE_RATIO and len(shared) / len(union) >= 0.80:
            # Unknown date may warrant manual review, never a strong duplicate.
            if any(g in guards for g in (
                "different_headline_factual_markers", "reported_dates_apart",
                "different_language_labels", "language_label_conflict",
            )):
                relations.append("headline_similarity_blocked")
            elif ln == rn:
                relations.append("headline_exact_candidate")
            elif abs(len(lt) - len(rt)) <= 1:
                relations.append("headline_near_candidate")
    body_score = None
    lb, rb = bodies.get(li), bodies.get(ri)
    if lb is not None and rb is not None:
        lf, ls, lcount, lmark = lb
        rf, rs, rcount, rmark = rb
        body_score = len(ls & rs) / len(ls | rs)
        length_ratio = min(lcount, rcount) / max(lcount, rcount)
        if body_score >= _BODY_SHINGLE_RATIO and length_ratio >= 0.95:
            if lmark != rmark or lm != rm:
                guards.append("different_body_or_headline_factual_markers")
                relations.append("body_similarity_blocked")
            elif any(g in guards for g in ("different_language_labels", "language_label_conflict")):
                relations.append("body_similarity_blocked")
            elif lf == rf:
                relations.append("normalized_body_match")
            else:
                relations.append("near_body_match_candidate")
    if not relations:
        return None
    body_match = any(r in relations for r in (
        "matching_extracted_digest", "normalized_body_match", "near_body_match_candidate"
    ))
    return {
        "left_observation_id": li, "right_observation_id": ri,
        "relations": relations, "guards": guards,
        "headline_similarity": round(title_score, 3) if title_score is not None else None,
        "body_shingle_jaccard": round(body_score, 6) if body_score is not None else None,
        "comparable_date_distance_seconds": distance,
        "shared_text_candidate": body_match,
        "source_independence": "unknown",
        "automatic_merge": False,
    }


def analyze_news_duplicates(observations, *, extractions=(), ephemeral_bodies=None):
    """Analyze a bounded snapshot; return direct pair evidence, not transitive clusters.

    Each receipt must refer to exactly one included observation. Optional caller-
    supplied ephemeral bodies require matching operator-permitted extraction
    digests, and are processed only in memory. No text or shingles are returned.
    Exact IDs are replay-deduplicated, but every distinct observation is preserved.
    """
    observations = _strict_sequence(observations, MAX_OBSERVATIONS)
    extractions = _strict_sequence(extractions, MAX_OBSERVATIONS)
    unique = {}
    for raw in observations:
        if not isinstance(raw, NewsArticle):
            raise ValueError("Expected typed news observation")
        try:
            row = NewsArticle.model_validate_json(raw.model_dump_json())
        except (ValueError, TypeError):
            raise ValueError("Invalid news observation") from None
        unique[row.observation_id] = row
    receipts = {}
    extraction_ids = {}
    for raw in extractions:
        if not isinstance(raw, ArticleExtraction):
            raise ValueError("Expected typed extraction receipt")
        try:
            receipt = ArticleExtraction.model_validate_json(raw.model_dump_json())
        except (ValueError, TypeError):
            raise ValueError("Invalid extraction receipt") from None
        oid = receipt.discovery.observation_id
        if unique.get(oid) != receipt.discovery:
            raise ValueError("Extraction receipt is outside the observation snapshot")
        if oid in receipts and receipts[oid] != receipt:
            raise ValueError("Select one extraction revision per observation")
        receipts[oid] = receipt
        extraction_ids[receipt.extraction_id] = receipt
    if ephemeral_bodies is None:
        ephemeral_bodies = {}
    if not isinstance(ephemeral_bodies, dict) or len(ephemeral_bodies) > MAX_BODY_INPUTS:
        raise ValueError("Invalid ephemeral body input collection")
    bodies = {}
    total = 0
    for eid, text in ephemeral_bodies.items():
        receipt = extraction_ids.get(eid)
        if (receipt is None or receipt.status != "extracted" or not receipt.body_sha256
                or receipt.body_digest_policy != "operator_permitted"):
            raise ValueError("Body requires a permitted matching extraction receipt")
        size, features = _body_features(text, receipt.body_sha256)
        total += size
        if total > MAX_TOTAL_BODY_BYTES:
            raise ValueError("Total ephemeral body budget exceeded")
        bodies[receipt.discovery.observation_id] = features

    rows = [unique[key] for key in sorted(unique)]
    headlines = {row.observation_id: _headline_features(row) for row in rows}
    pairs = []
    for a, b in combinations(rows, 2):
        pair = _compare(a, b, receipts, bodies, headlines)
        if pair is not None:
            pairs.append(pair)
    # Only exact replay IDs are collapsed. Pairwise evidence cannot cause
    # transitive A~B~C merges or silently increase independent source counts.
    return {
        "schema_version": 1, "algorithm_version": _ALGORITHM,
        "network_performed": False, "metrics_aggregated": False,
        "source_independence_established": False, "event_identity_established": False,
        "input_observation_count": len(observations), "unique_observation_count": len(rows),
        "exact_replays_removed": len(observations) - len(rows),
        "comparisons": len(rows) * (len(rows) - 1) // 2,
        "ephemeral_body_inputs": len(ephemeral_bodies),
        "body_inputs_with_sufficient_features": sum(x is not None for x in bodies.values()),
        "observations": [row.model_dump(mode="json") for row in rows],
        "extraction_refs": [{"observation_id": key, "extraction_id": receipts[key].extraction_id}
                            for key in sorted(receipts)],
        "pairs": pairs,
        "limitations": [
            "Caller-supplied receipts are not authenticated origin evidence.",
            "Similar headlines, canonical hints and identical links do not establish shared copies.",
            "Shared text does not establish which publisher originated it or whether claims are true.",
            "Multilingual semantics, full lineage and event clustering are separate tasks.",
        ],
    }
