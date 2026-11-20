"""M02: bounded, offline lexical keyword clustering with RapidFuzz.

Preserves original source evidence; never combines metrics or asserts that fuzzy
matches are semantically equivalent or have shared search volumes.
"""
from __future__ import annotations

import unicodedata
from collections import defaultdict
from collections.abc import Sequence
from time import perf_counter
from typing import Any

from pydantic import ValidationError
from rapidfuzz import fuzz

from mcp_trendpulse.intelligence_signal import TrendSignal

MAX_KEYWORD_SIGNALS = 200
DEFAULT_SIMILARITY_THRESHOLD = 95
# Differences in these tokens can reverse an intent or commercial distinction.
_INTENT_TERMS = frozenset({
    "no", "not", "without", "with", "free", "paid", "buy", "sell",
    "cheap", "expensive", "open", "closed", "vs", "versus",
    "before", "after", "best", "worst",
})


def normalize_keyword(text: str) -> str:
    """NFC Unicode, casefold and conservative separator handling.

    Do not transliterate, strip accents or remove C++ / C# language markers.
    Exact duplicates are deliberately more constrained than semantic matches.
    """
    if not isinstance(text, str):
        raise ValueError("Keyword must be text")
    text = unicodedata.normalize("NFC", text).casefold()
    # Normalize punctuation variants while retaining their meaningful symbols.
    text = text.replace("’", "'").replace("‘", "'")
    text = "".join("-" if c in "‐‑‒–—−" else c for c in text)
    out: list[str] = []
    for i, ch in enumerate(text):
        cat = unicodedata.category(ch)
        if ch == "-" and i and i < len(text) - 1:
            # Hyphens between words are lexical separators; code markers stay.
            out.append(" ")
        elif cat.startswith("Z") or ch in "\t\r\n":
            out.append(" ")
        elif cat.startswith("P") and ch not in {"#", "+"}:
            out.append(" ")
        elif cat.startswith("C"):
            continue
        else:
            out.append(ch)
    result = " ".join("".join(out).split())
    if not result:
        raise ValueError("Keyword becomes empty after normalization")
    return result


def _accentless(text: str) -> str:
    # Used only to detect a diacritic-only difference and refuse fuzzy merging.
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def _safe_near_duplicate(left: str, right: str, threshold: float) -> float | None:
    if left == right:
        return 100.0
    # Short terms and abbreviations are too ambiguous for fuzzy grouping.
    if min(len(left), len(right)) < 9 or abs(len(left) - len(right)) > 3:
        return None
    if _accentless(left) == _accentless(right):
        return None
    if any(char in left for char in "+#") != any(char in right for char in "+#"):
        return None
    if ("+" in left) != ("+" in right) or ("#" in left) != ("#" in right):
        return None
    lt, rt = left.split(), right.split()
    if len(lt) != len(rt) or len(lt) < 2:
        return None
    # Require an unchanged anchor token to avoid pairing unrelated lookalikes.
    shared = set(lt) & set(rt)
    if not shared:
        return None
    if ({t for t in lt if t in _INTENT_TERMS}
            != {t for t in rt if t in _INTENT_TERMS}):
        return None
    # A single-token spelling variation may join a lexical family. Do not
    # let token-set/subsequence matchers collapse entirely different queries.
    if len(set(lt) ^ set(rt)) > 2:
        return None
    # Preserve meaningful product names and polarities: 'OpenAI Code' is not
    # 'OpenAI Codex'; 'reliability' must not merge with 'unreliability'.
    changed_left = [token for token in lt if token not in shared]
    changed_right = [token for token in rt if token not in shared]
    if len(changed_left) == len(changed_right) == 1:
        first, second = changed_left[0], changed_right[0]
        if first.startswith(second) or second.startswith(first):
            return None
        for prefix in ("un", "non", "anti", "dis", "in", "im", "ir", "il"):
            if first == prefix + second or second == prefix + first:
                return None
    score = fuzz.ratio(left, right, score_cutoff=threshold)
    if score < threshold:
        return None
    return float(score)


def cluster_keyword_signals(
    raw_signals: Sequence[TrendSignal | dict[str, Any]],
    *,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> dict[str, Any]:
    """Deterministic, source-preserving clusters; zero network and zero aggregation.

    Country and language must match exactly, even if both terms are similar.
    Each record stays intact. Clusters serve research exploration, not metric sums.
    """
    if not isinstance(raw_signals, (list, tuple)) or not 0 <= len(raw_signals) <= MAX_KEYWORD_SIGNALS:
        raise ValueError(f"Keyword signals must be a bounded list (0..{MAX_KEYWORD_SIGNALS})")
    if (not isinstance(similarity_threshold, (float, int))
            or isinstance(similarity_threshold, bool)
            or not 90 <= similarity_threshold <= 100):
        raise ValueError("Similarity threshold must be a number between 90 and 100")
    clean: list[tuple[int, TrendSignal, str]] = []
    for index, raw in enumerate(raw_signals):
        try:
            signal = raw if isinstance(raw, TrendSignal) else TrendSignal.model_validate(raw)
        except (TypeError, ValueError, ValidationError) as exc:
            raise ValueError(f"Invalid source signal at index {index}") from exc
        clean.append((index, signal, normalize_keyword(signal.raw_term)))

    scoped: dict[tuple[str | None, str | None], list[tuple[int, TrendSignal, str]]] = defaultdict(list)
    for record in clean:
        scoped[(record[1].country, record[1].language)].append(record)

    clusters: list[dict[str, Any]] = []
    exact_groups = 0
    fuzzy_pairs = 0
    comparisons = 0
    for (country, language), items in sorted(
        scoped.items(), key=lambda item: (item[0][0] or "", item[0][1] or "")
    ):
        # Deterministic clusters regardless of original arrival order.
        items.sort(key=lambda r: (r[2], r[1].raw_term.casefold(), r[1].source_id, r[0]))
        grouped: list[dict[str, Any]] = []
        for index, signal, normalized in items:
            # Avoid fuzzy single-link chaining: a candidate must match every
            # distinct normalized term already inside its proposed cluster.
            selected = None
            score = None
            basis = "distinct"
            for cluster in grouped:
                keys = cluster["_keys"]
                if normalized in keys:
                    selected, score, basis = cluster, 100.0, "exact"
                    break
            if selected is None:
                for cluster in grouped:
                    keys = cluster["_keys"]
                    comparisons += len(keys)
                    scores = [_safe_near_duplicate(normalized, x, float(similarity_threshold))
                              for x in keys]
                    if all(x is not None for x in scores):
                        selected = cluster
                        score = min(scores)
                        basis = "fuzzy"
                        fuzzy_pairs += 1
                        break
            member = {
                "input_index": index,
                "raw_term": signal.raw_term,
                "normalized_term": normalized,
                "source_id": signal.source_id,
                "source_url": signal.source_url,
                "metric_type": signal.metric_type,
                "metric_unit": signal.metric_unit,
                "value": signal.value,
                "value_label": signal.value_label,
                "observed_at": signal.observed_at.isoformat(),
                "coverage_status": signal.coverage_status,
                "match_basis": basis,
                "lexical_similarity": score,
            }
            if selected is None:
                grouped.append({
                    "country": country, "language": language,
                    "representative": signal.raw_term,
                    "representative_normalized": normalized,
                    "members": [member], "_keys": {normalized},
                })
            else:
                selected["members"].append(member)
                selected["_keys"].add(normalized)
                if basis == "exact":
                    exact_groups += 1
        for cluster in grouped:
            cluster.pop("_keys")
            clusters.append(cluster)

    return {
        "schema_version": 1,
        "mode": "offline_rapidfuzz_lexical_keyword_clusters",
        "input_records": len(clean),
        "cluster_count": len(clusters),
        "exact_duplicate_records": exact_groups,
        "fuzzy_matched_records": fuzzy_pairs,
        "candidate_comparisons": comparisons,
        "similarity_threshold": float(similarity_threshold),
        "network_performed": False,
        "metrics_aggregated": False,
        "semantic_equivalence_claimed": False,
        "scope_note": (
            "Country and language boundaries are exact. A missing market is "
            "not worldwide coverage. Similar terms may have different intent."
        ),
        "clusters": clusters,
    }


def benchmark_clustering(*, count: int = MAX_KEYWORD_SIGNALS) -> dict[str, float | int]:
    """Small repeatable CPU diagnostic without network, fixtures or global state."""
    from datetime import date, datetime, timezone

    from mcp_trendpulse.intelligence_signal import SignalPeriod, SignalProvenance
    if not 1 <= count <= MAX_KEYWORD_SIGNALS:
        raise ValueError("Benchmark count must be between 1 and 200")
    now = datetime(2026, 11, 20, tzinfo=timezone.utc)
    rows = []
    for i in range(count):
        label = f"developer agent reliability technique {i:03d}"
        rows.append(TrendSignal(
            source_id="synthetic_benchmark",
            source_url="https://example.org/benchmark",
            observed_at=now,
            country="US", language="en",
            raw_term=label, normalized_term=label,
            metric_type="generated_keyword_candidate", metric_unit="none",
            period=SignalPeriod(start_date=date(2026, 11, 20),
                                end_date=date(2026, 11, 20),
                                granularity="point_in_time"),
            value=None, coverage_status="not_measured",
            sampling_scope="synthetic offline benchmark only",
            provenance=SignalProvenance(method="derived",
                                        sampling_basis="synthetic_fixture",
                                        is_observed_search_query=False),
        ))
    start = perf_counter()
    result = cluster_keyword_signals(rows)
    return {
        "records": count,
        "elapsed_seconds": round(perf_counter() - start, 5),
        "comparisons": result["candidate_comparisons"],
        "clusters": result["cluster_count"],
    }
