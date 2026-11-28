"""V5.02: deterministic claim candidates from complete, bounded source text.

No model, sampling, retrieval, actions, external calls, or inferred verdicts.
All sources are untrusted. Unsupported grammar is reported as abstention.
"""
from __future__ import annotations

from mcp_trendpulse.claim_intelligence_graph import (
    MAX_SOURCES, MAX_SPAN, AtomicClaim, EvidenceAnchor, SourceRevision,
    _typed, _sha, build_claim_graph, source_from_observation,
)
from mcp_trendpulse.claim_intelligence_rules import parse_numeric_claim
from mcp_trendpulse.news_intelligence_schema import NewsArticle, _digest, _text

_METHOD = "deterministic_numeric_candidates_v1"


def extract_claim_candidates(*, as_of, sources=(), document_texts=None):
    """Emit one candidate or controlled abstention per supplied source.

    A document is eligible only if its entire supplied text representation
    fits the span budget and the caller explicitly permits excerpt retention.
    Longer, hash-only, unavailable, or opinion documents remain context.
    The graph checks all supplied document digests and retained anchors.
    """
    sources = _typed(sources, SourceRevision, MAX_SOURCES)
    # Validate rights, digest, cutoff, and unique IDs before reading any text
    # into a candidate. This graph is not persisted.
    initial = build_claim_graph(as_of=as_of, sources=sources, document_texts=document_texts)
    texts = {} if document_texts is None else document_texts
    anchors, claims, outcomes = [], [], []
    for source in initial.sources:
        sid = source.source_revision_id
        text = None
        reason = None
        if source.source_kind == "opinion":
            reason = "opinion_source"
        elif source.basis == "news_observation":
            text = source.title
        elif source.retention != "permitted_excerpt":
            reason = "excerpt_retention_not_permitted"
        elif source.text_character_count > MAX_SPAN:
            reason = "document_not_standalone"
        elif sid not in texts:
            reason = "document_text_unavailable"
        else:
            try:
                text = _text(texts[sid], MAX_SPAN)
            except ValueError:
                reason = "document_not_standalone"

        fields = None
        if text is not None:
            fields, reason = parse_numeric_claim(text)
        if fields is None:
            outcomes.append({"source_revision_id": sid, "status": "abstained",
                             "reason": reason, "claim_id": None})
            continue
        anchor = EvidenceAnchor(
            source_revision_id=sid,
            selector="headline_span" if source.basis == "news_observation" else "document_span",
            start=0, end=len(text), excerpt=text,
            span_sha256=None if source.basis == "news_observation" else _sha(text),
        )
        claim = AtomicClaim(**fields, origin_evidence_id=anchor.evidence_id,
                            extraction_method="deterministic_numeric_v1")
        anchors.append(anchor)
        claims.append(claim)
        outcomes.append({"source_revision_id": sid, "status": "candidate",
                         "reason": None, "claim_id": claim.claim_id})
    graph = build_claim_graph(as_of=initial.as_of, sources=initial.sources, evidence=anchors,
                              claims=claims, document_texts=document_texts)
    report = {
        "schema_version": 1, "method": _METHOD, "as_of": graph.as_of,
        "source_count": len(sources), "candidate_count": len(claims),
        "abstained_count": len(sources) - len(claims), "outcomes": outcomes,
        "graph": graph.model_dump(mode="json"),
        "network_performed": False, "paid_services_used": False, "model_sampling_performed": False,
        "semantic_verification": "not_performed",
        "limitations": [
            "English numeric templates only; no semantic extraction or coreference resolution.",
            "A candidate preserves a reported statement, not a verified fact.",
            "Quantities, qualifiers, predicate tense, and explicit period wording remain lexical.",
            "A supplied document representation is not authenticated or guaranteed complete.",
            "Abstention is not evidence of absence, falsehood, or lack of checkable claims.",
        ],
    }
    report["report_id"] = _digest(report)
    return report


def extract_observation_claims(observations, *, as_of):
    """Connect directly to typed V4 observations; preserve original IDs."""
    rows = _typed(observations, NewsArticle, MAX_SOURCES)
    unique = {r.observation_id: r for r in rows}
    return extract_claim_candidates(as_of=as_of, sources=[
        source_from_observation(row) for row in unique.values()
    ])
