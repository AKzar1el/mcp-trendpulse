"""V5.01: bounded, offline claim/evidence graph; no truth adjudication.

Exact source anchors are checked against supplied material, not authenticated
publisher content. All claim decomposition and semantic relations are caller
annotations. No network, model sampling, persistence, or tool invocation.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from mcp_trendpulse.news_intelligence_schema import (
    Digest, FrozenModel, NewsArticle, _digest, _text, _url, _utc,
)
from mcp_trendpulse.rss_url_validation import is_google_news_rss_url

MAX_SOURCES = 80
MAX_CLAIMS = 80
MAX_EVIDENCE = 160
MAX_RELATIONS = 240
MAX_DOCUMENTS = 8
MAX_DOCUMENT_BYTES = 256 * 1024
MAX_TOTAL_DOCUMENT_BYTES = 1024 * 1024
MAX_SPAN = 512
_METHOD = "claim_evidence_graph_v1"
_RELATIONS = ("supports", "contradicts")
Kind = Literal["primary_document", "secondary_reporting", "opinion", "unknown"]


def _sha(text):
    return hashlib.sha256(text.encode("utf-8", "strict")).hexdigest()


def _identity(model, field, value):
    expected = _digest(value)
    if getattr(model, field) not in (None, expected):
        raise ValueError("Record identity mismatch")
    object.__setattr__(model, field, expected)


def _day(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Calendar date required")
    date.fromisoformat(value)
    return value


def _optional_text(value, maximum):
    return _text(value, maximum) if value is not None else None


class SourceRevision(FrozenModel):
    """Exact observation or caller-described document revision.

    Document hashes are hashes of the exact supplied UTF-8 text representation,
    not hashes of the original HTML, PDF or publisher file.
    """

    source_revision_id: Digest | None = None
    basis: Literal["news_observation", "caller_document"]
    source_kind: Kind = "unknown"
    url: str
    title: str
    captured_at: str | None = None
    observation: NewsArticle | None = None
    revision_label: str | None = None
    retention: Literal["metadata_only", "permitted_hash", "permitted_excerpt"] = "metadata_only"
    text_sha256: Digest | None = None
    text_character_count: int | None = Field(default=None, ge=1, le=MAX_DOCUMENT_BYTES)

    @field_validator("url")
    @classmethod
    def _citation(cls, value):
        return _url(value)

    @field_validator("title", "revision_label")
    @classmethod
    def _labels(cls, value):
        return _optional_text(value, 512)

    @field_validator("captured_at")
    @classmethod
    def _capture(cls, value):
        return _utc(value) if value is not None else None

    @model_validator(mode="after")
    def _check(self):
        if self.basis == "news_observation":
            row = self.observation
            if (row is None or self.url != row.reported_url or self.title != row.title
                    or self.captured_at != row.captured_at or self.source_kind != "unknown"
                    or self.revision_label is not None or self.retention != "metadata_only"):
                raise ValueError("News source must preserve the original headline observation")
        elif self.observation is not None or not self.revision_label:
            raise ValueError("Document needs an explicit caller revision label")
        elif is_google_news_rss_url(self.url):
            raise ValueError("RSS discovery URL is not a document revision citation")
        has_digest = self.text_sha256 is not None and self.text_character_count is not None
        if self.retention == "metadata_only":
            if self.text_sha256 is not None or self.text_character_count is not None:
                raise ValueError("Metadata-only source cannot retain a body digest")
        elif self.basis != "caller_document" or not has_digest:
            raise ValueError("Permitted document retention requires text digest and length")
        _identity(self, "source_revision_id", self.model_dump(mode="json", exclude={"source_revision_id"}))
        return self


def source_from_observation(observation):
    """V4 adapter: never promote a feed headline into a primary document."""
    if not isinstance(observation, NewsArticle):
        raise ValueError("Expected a typed news observation")
    try:
        row = NewsArticle.model_validate_json(observation.model_dump_json())
    except (ValueError, TypeError):
        raise ValueError("Invalid news observation") from None
    return SourceRevision(basis="news_observation", url=row.reported_url, title=row.title,
                          captured_at=row.captured_at, observation=row)


class EvidenceAnchor(FrozenModel):
    evidence_id: Digest | None = None
    source_revision_id: Digest
    selector: Literal["headline_span", "document_span", "document_locator"]
    # Unicode code-point offsets in the exact supplied representation; end exclusive.
    start: int | None = Field(default=None, ge=0, le=MAX_DOCUMENT_BYTES)
    end: int | None = Field(default=None, ge=1, le=MAX_DOCUMENT_BYTES)
    locator: str | None = None
    excerpt: str | None = None
    span_sha256: Digest | None = None

    @field_validator("locator", "excerpt")
    @classmethod
    def _bounded(cls, value):
        return _optional_text(value, MAX_SPAN)

    @model_validator(mode="after")
    def _check(self):
        if self.selector == "document_locator":
            if not self.locator or any(x is not None for x in (self.start, self.end, self.excerpt, self.span_sha256)):
                raise ValueError("Unresolved document locator cannot assert an exact span")
        else:
            if self.start is None or self.end is None or not 1 <= self.end - self.start <= MAX_SPAN:
                raise ValueError("Invalid evidence span offsets")
            if self.selector == "headline_span":
                if self.excerpt is None or self.span_sha256 is not None or self.locator is not None:
                    raise ValueError("Headline span needs exact headline excerpt")
            elif self.span_sha256 is None:
                raise ValueError("Document span requires a permitted digest")
            if self.excerpt is not None:
                if len(self.excerpt) != self.end - self.start:
                    raise ValueError("Excerpt length does not match offsets")
                if self.span_sha256 and _sha(self.excerpt) != self.span_sha256:
                    raise ValueError("Excerpt digest mismatch")
        _identity(self, "evidence_id", self.model_dump(mode="json", exclude={"evidence_id"}))
        return self


class ClaimScope(FrozenModel):
    geography: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    qualifiers: tuple[str, ...] = Field(default=(), max_length=8)

    @field_validator("geography")
    @classmethod
    def _geo(cls, value):
        return _optional_text(value, 160)

    @field_validator("period_start", "period_end")
    @classmethod
    def _period(cls, value):
        return _day(value) if value is not None else None

    @model_validator(mode="after")
    def _check(self):
        if self.period_start and self.period_end and self.period_start > self.period_end:
            raise ValueError("Reversed claim period")
        for item in self.qualifiers:
            _text(item, 160)
        if len(set(self.qualifiers)) != len(self.qualifiers):
            raise ValueError("Repeated claim qualifier")
        object.__setattr__(self, "qualifiers", tuple(sorted(self.qualifiers)))
        return self


class AtomicClaim(FrozenModel):
    """A caller-proposed decomposition, not proof of semantic atomicity."""

    claim_id: Digest | None = None
    proposition_id: Digest | None = None
    subject: str
    predicate: str
    object: str
    polarity: Literal["affirmed", "negated", "unknown"]
    modality: Literal["assertion", "allegation", "quotation", "projection", "opinion", "question", "unknown"]
    scope: ClaimScope = Field(default_factory=ClaimScope)
    attribution: str | None = None
    asserted_at: str | None = None
    asserted_at_precision: Literal["day", "timestamp", "unknown"] = "unknown"
    origin_evidence_id: Digest
    extraction_method: Literal["caller_annotation"] = "caller_annotation"

    @field_validator("subject", "predicate", "object", "attribution")
    @classmethod
    def _bounded(cls, value):
        return _optional_text(value, 512)

    @model_validator(mode="after")
    def _check(self):
        if (self.asserted_at is None) != (self.asserted_at_precision == "unknown"):
            raise ValueError("Unknown assertion date must remain unknown")
        if self.asserted_at_precision == "day":
            _day(self.asserted_at)
        elif self.asserted_at_precision == "timestamp":
            object.__setattr__(self, "asserted_at", _utc(self.asserted_at))
        # Exact field equality only; no inferred paraphrase/entity equivalence.
        _identity(self, "proposition_id", [self.subject, self.predicate, self.object, self.polarity,
                                           self.scope.model_dump(mode="json")])
        _identity(self, "claim_id", self.model_dump(mode="json", exclude={"claim_id"}))
        return self


class EvidenceRelation(FrozenModel):
    relation_id: Digest | None = None
    claim_id: Digest
    # A bundle is jointly annotated; each individual item need not suffice.
    evidence_ids: tuple[Digest, ...] = Field(min_length=1, max_length=5)
    relation: Literal["supports", "contradicts", "context", "insufficient"]
    scope_alignment: Literal["matched", "mismatched", "unknown"] = "unknown"
    rationale: str
    method: Literal["caller_annotation"] = "caller_annotation"

    @field_validator("rationale")
    @classmethod
    def _reason(cls, value):
        return _text(value, 512)

    @model_validator(mode="after")
    def _check(self):
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("Repeated evidence in relation")
        object.__setattr__(self, "evidence_ids", tuple(sorted(self.evidence_ids)))
        if self.relation in _RELATIONS and self.scope_alignment != "matched":
            raise ValueError("Support or contradiction requires declared matching scope")
        _identity(self, "relation_id", self.model_dump(mode="json", exclude={"relation_id"}))
        return self


class AnchorCheck(FrozenModel):
    evidence_id: Digest
    status: Literal["exact_headline", "checked_against_supplied_text", "locator_only"]


def _source_anchor(source, anchor):
    if source.basis == "news_observation":
        if anchor.selector != "headline_span" or anchor.end > len(source.title):
            raise ValueError("News observation only supplies headline evidence")
        if source.title[anchor.start:anchor.end] != anchor.excerpt:
            raise ValueError("Headline excerpt does not match original revision")
        return "exact_headline"
    if anchor.selector == "headline_span":
        raise ValueError("Caller document is not a news headline observation")
    if anchor.selector == "document_locator":
        return "locator_only"
    if source.retention == "metadata_only" or anchor.end > source.text_character_count:
        raise ValueError("Document span requires permitted revision text")
    if source.retention != "permitted_excerpt" and anchor.excerpt is not None:
        raise ValueError("Excerpt retention not permitted")
    return "checked_against_supplied_text"


def _unique(items, field):
    result = {}
    for item in items:
        key = getattr(item, field)
        if key in result:
            raise ValueError("Duplicate graph identifier")
        result[key] = item
    return result


class ClaimEvidenceGraph(FrozenModel):
    schema_version: Literal[1] = 1
    method: Literal["claim_evidence_graph_v1"] = _METHOD
    graph_id: Digest | None = None
    as_of: str
    sources: tuple[SourceRevision, ...] = Field(max_length=MAX_SOURCES)
    evidence: tuple[EvidenceAnchor, ...] = Field(max_length=MAX_EVIDENCE)
    anchor_checks: tuple[AnchorCheck, ...] = Field(max_length=MAX_EVIDENCE)
    claims: tuple[AtomicClaim, ...] = Field(max_length=MAX_CLAIMS)
    relations: tuple[EvidenceRelation, ...] = Field(max_length=MAX_RELATIONS)
    semantic_verification: Literal["not_performed"] = "not_performed"
    source_authentication: Literal["not_performed"] = "not_performed"
    source_independence: Literal["unknown"] = "unknown"
    network_performed: Literal[False] = False

    @field_validator("as_of")
    @classmethod
    def _cutoff(cls, value):
        return _utc(value)

    @model_validator(mode="after")
    def _check(self):
        for field, key in (("sources", "source_revision_id"), ("evidence", "evidence_id"),
                           ("anchor_checks", "evidence_id"), ("claims", "claim_id"),
                           ("relations", "relation_id")):
            values = getattr(self, field)
            _unique(values, key)
            object.__setattr__(self, field, tuple(sorted(values, key=lambda x: getattr(x, key))))
        sources = _unique(self.sources, "source_revision_id")
        evidence = _unique(self.evidence, "evidence_id")
        checks = _unique(self.anchor_checks, "evidence_id")
        claims = _unique(self.claims, "claim_id")
        cutoff = datetime.fromisoformat(self.as_of)
        if set(checks) != set(evidence):
            raise ValueError("Every anchor requires exactly one check receipt")
        for source in self.sources:
            if source.captured_at and datetime.fromisoformat(source.captured_at) > cutoff:
                raise ValueError("Source capture after graph cutoff")
            if source.observation:
                for stamp in (source.observation.published_at, source.observation.provider_seen_at):
                    if stamp and stamp.precision != "day" and datetime.fromisoformat(_utc(stamp.value)) > cutoff:
                        raise ValueError("Source reported timestamp after graph cutoff")
        for anchor in self.evidence:
            source = sources.get(anchor.source_revision_id)
            if source is None:
                raise ValueError("Dangling source revision reference")
            if checks[anchor.evidence_id].status != _source_anchor(source, anchor):
                raise ValueError("Anchor check receipt inconsistent with source")
        for claim in self.claims:
            if claim.origin_evidence_id not in evidence:
                raise ValueError("Dangling claim origin reference")
            if claim.asserted_at_precision == "timestamp" and datetime.fromisoformat(claim.asserted_at) > cutoff:
                raise ValueError("Assertion timestamp after graph cutoff")
            if claim.asserted_at_precision == "day" and claim.asserted_at > cutoff.date().isoformat():
                raise ValueError("Assertion calendar date after graph cutoff UTC day")
        for edge in self.relations:
            claim = claims.get(edge.claim_id)
            if claim is None or any(eid not in evidence for eid in edge.evidence_ids):
                raise ValueError("Dangling claim or evidence relation reference")
            if edge.relation in _RELATIONS:
                if claim.modality in ("opinion", "question", "unknown") or claim.polarity == "unknown":
                    raise ValueError("Unsupported evaluative relation for noncheckable claim")
                if claim.origin_evidence_id in edge.evidence_ids:
                    raise ValueError("Claim appearance itself cannot be verification evidence")
                origin = evidence[claim.origin_evidence_id]
                for eid in edge.evidence_ids:
                    anchor = evidence[eid]
                    source = sources[anchor.source_revision_id]
                    if (checks[eid].status != "checked_against_supplied_text"
                            or source.source_kind not in ("primary_document", "secondary_reporting")
                            or source.captured_at is None):
                        raise ValueError("Support or contradiction needs checked document evidence with known capture")
                    if anchor.source_revision_id == origin.source_revision_id:
                        if origin.selector == "document_locator" or (
                            anchor.start < origin.end and origin.start < anchor.end
                        ):
                            raise ValueError("Overlapping or unresolved claim appearance cannot be verification evidence")
        _identity(self, "graph_id", self.model_dump(mode="json", exclude={"graph_id"}))
        return self


def _typed(items, model, maximum):
    if not isinstance(items, (list, tuple)) or len(items) > maximum:
        raise ValueError("Graph input exceeds bounded collection")
    result = []
    for item in items:
        if not isinstance(item, model):
            raise ValueError("Expected typed graph input")
        try:
            result.append(model.model_validate_json(item.model_dump_json()))
        except (ValueError, TypeError):
            raise ValueError("Invalid graph input record") from None
    return tuple(result)


def build_claim_graph(*, as_of, sources=(), evidence=(), claims=(), relations=(), document_texts=None):
    """Verify exact anchors and build an immutable, deterministic graph.

    Caller establishes rights before supplying document text. Text is transient;
    only explicit permitted excerpts/digests and metadata are retained in output.
    Parsing a serialized graph later validates structure/IDs, not its historical
    document-check receipts. No source authentication or semantic evaluation.
    """
    sources = _typed(sources, SourceRevision, MAX_SOURCES)
    evidence = _typed(evidence, EvidenceAnchor, MAX_EVIDENCE)
    claims = _typed(claims, AtomicClaim, MAX_CLAIMS)
    relations = _typed(relations, EvidenceRelation, MAX_RELATIONS)
    by_id = _unique(sources, "source_revision_id")
    if document_texts is None:
        document_texts = {}
    if not isinstance(document_texts, dict) or len(document_texts) > MAX_DOCUMENTS:
        raise ValueError("Invalid ephemeral document collection")
    total = 0
    for sid, text in document_texts.items():
        source = by_id.get(sid)
        if (source is None or source.basis != "caller_document" or source.retention == "metadata_only"
                or not isinstance(text, str) or len(text) != source.text_character_count):
            raise ValueError("Ephemeral document not in permitted revision scope")
        try:
            raw = text.encode("utf-8", "strict")
        except UnicodeError:
            raise ValueError("Invalid document encoding") from None
        total += len(raw)
        if len(raw) > MAX_DOCUMENT_BYTES or total > MAX_TOTAL_DOCUMENT_BYTES:
            raise ValueError("Ephemeral document byte budget exceeded")
        if hashlib.sha256(raw).hexdigest() != source.text_sha256:
            raise ValueError("Document revision digest mismatch")
    checks = []
    for anchor in evidence:
        source = by_id.get(anchor.source_revision_id)
        if source is None:
            raise ValueError("Dangling source revision reference")
        status = _source_anchor(source, anchor)
        if status == "checked_against_supplied_text":
            text = document_texts.get(source.source_revision_id)
            if text is None:
                raise ValueError("Document span requires ephemeral revision text")
            actual = text[anchor.start:anchor.end]
            if _sha(actual) != anchor.span_sha256 or (anchor.excerpt is not None and anchor.excerpt != actual):
                raise ValueError("Evidence span does not match supplied revision")
        checks.append(AnchorCheck(evidence_id=anchor.evidence_id, status=status))
    return ClaimEvidenceGraph(as_of=as_of, sources=sources, evidence=evidence, anchor_checks=tuple(checks),
                              claims=claims, relations=relations)
