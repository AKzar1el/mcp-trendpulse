"""V5.06: source correction, retraction and revision traceability.

Change events are caller-annotated and checked against exact supplied notice
spans. Preserve historical revisions and prior assessments; never rewrite a
claim graph, infer truth, fetch archives or silently erase retracted material.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from mcp_trendpulse.claim_intelligence_graph import ClaimEvidenceGraph, _typed
from mcp_trendpulse.news_intelligence_schema import Digest, FrozenModel, _digest, _text, _utc

MAX_CHANGES = 120
MAX_NOTICE_LOCATOR = 200


class SourceChange(FrozenModel):
    change_id: Digest | None = None
    change_type: Literal["correction", "retraction", "withdrawal", "replacement",
                         "clarification", "archive_snapshot"]
    target_revision_id: Digest
    successor_revision_id: Digest | None = None
    notice_revision_id: Digest
    notice_anchor_id: Digest
    affected_claim_ids: tuple[Digest, ...] = Field(min_length=1, max_length=80)
    announced_at: str
    target_locator_text: str = Field(min_length=1, max_length=MAX_NOTICE_LOCATOR)
    successor_locator_text: str | None = None
    notice_reference_text: str = Field(min_length=1, max_length=MAX_NOTICE_LOCATOR)
    method: Literal["caller_annotation"] = "caller_annotation"

    @field_validator("announced_at")
    @classmethod
    def _time(cls, value):
        return _utc(value)

    @field_validator("target_locator_text", "successor_locator_text", "notice_reference_text")
    @classmethod
    def _labels(cls, value):
        return None if value is None else _text(value, MAX_NOTICE_LOCATOR)

    @model_validator(mode="after")
    def _check(self):
        required = self.change_type in ("correction", "replacement", "clarification", "archive_snapshot")
        if required != (self.successor_revision_id is not None):
            raise ValueError("Change type has incorrect successor revision requirement")
        if self.successor_revision_id == self.target_revision_id:
            raise ValueError("A source revision cannot supersede itself")
        if self.successor_revision_id is None and self.successor_locator_text is not None:
            raise ValueError("No successor locator without successor revision")
        if self.successor_revision_id is not None and not self.successor_locator_text:
            raise ValueError("Successor revision requires a literal notice locator")
        if tuple(sorted(set(self.affected_claim_ids))) != self.affected_claim_ids:
            raise ValueError("Affected claim IDs must be unique and sorted")
        expected = _digest(self.model_dump(mode="json", exclude={"change_id"}))
        if self.change_id not in (None, expected):
            raise ValueError("Change identity mismatch")
        object.__setattr__(self, "change_id", expected)
        return self


def _graph(value):
    if not isinstance(value, ClaimEvidenceGraph):
        raise ValueError("Expected typed claim evidence graph")
    try:
        return ClaimEvidenceGraph.model_validate_json(value.model_dump_json())
    except (ValueError, TypeError):
        raise ValueError("Invalid claim evidence graph") from None


def _assessment(value, graph):
    if value is None:
        return None
    if not isinstance(value, dict) or value.get("method") != "claim_evidence_assessment_v1" or len(value) > 32:
        raise ValueError("Invalid prior assessment report")
    if value.get("report_id") != _digest({k:v for k,v in value.items() if k != "report_id"}):
        raise ValueError("Prior assessment fingerprint mismatch")
    if value.get("graph_id") != graph.graph_id or value.get("semantic_verification") != "not_performed":
        raise ValueError("Prior assessment graph mismatch")
    assessed_at = _utc(value.get("as_of"))
    rows = value.get("assessments")
    if not isinstance(rows, list) or len(rows) > 80:
        raise ValueError("Invalid prior assessment rows")
    mapping = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("claim_id") in mapping or row.get("status") not in (
            "supported", "independently_corroborated", "unverified", "disputed", "contradicted", "unknown"
        ):
            raise ValueError("Invalid prior claim assessment")
        mapping[row["claim_id"]] = row["status"]
    if set(mapping) != {c.claim_id for c in graph.claims}:
        raise ValueError("Prior assessment claim coverage mismatch")
    return datetime.fromisoformat(assessed_at), mapping, value["report_id"]


def track_source_changes(graph, *, as_of, changes=(), previous_assessment=None):
    """Build a deterministic change ledger; no source content or assessment is mutated."""
    graph = _graph(graph)
    cutoff_text = _utc(as_of)
    cutoff = datetime.fromisoformat(cutoff_text)
    if cutoff < datetime.fromisoformat(graph.as_of):
        raise ValueError("Change ledger cutoff precedes graph")
    changes = _typed(changes, SourceChange, MAX_CHANGES)
    if len({c.change_id for c in changes}) != len(changes):
        raise ValueError("Duplicate source change")
    sources = {s.source_revision_id:s for s in graph.sources}
    anchors = {a.evidence_id:a for a in graph.evidence}
    checks = {a.evidence_id:a.status for a in graph.anchor_checks}
    claims = {c.claim_id:c for c in graph.claims}
    claim_sources = {cid:{anchors[c.origin_evidence_id].source_revision_id} for cid,c in claims.items()}
    for edge in graph.relations:
        for eid in edge.evidence_ids:
            claim_sources[edge.claim_id].add(anchors[eid].source_revision_id)
    previous = _assessment(previous_assessment, graph)
    previous_at, previous_status, previous_id = previous if previous else (None, {}, None)
    edges = {}
    normalized = []
    for change in changes:
        if change.target_revision_id not in sources or change.notice_revision_id not in sources:
            raise ValueError("Change references unknown source revision")
        if change.successor_revision_id is not None and change.successor_revision_id not in sources:
            raise ValueError("Change references unknown successor revision")
        if not set(change.affected_claim_ids).issubset(claims):
            raise ValueError("Change references unknown claim")
        notice = sources[change.notice_revision_id]
        anchor = anchors.get(change.notice_anchor_id)
        if (anchor is None or anchor.source_revision_id != change.notice_revision_id
                or checks.get(change.notice_anchor_id) != "checked_against_supplied_text"
                or notice.source_kind not in ("primary_document", "secondary_reporting")
                or notice.captured_at is None or anchor.excerpt is None):
            raise ValueError("Change notice needs checked, captured document evidence")
        literals = [change.notice_reference_text, change.target_locator_text]
        if change.successor_locator_text:
            literals.append(change.successor_locator_text)
        if any(literal not in anchor.excerpt for literal in literals):
            raise ValueError("Change notice does not contain exact revision reference text")
        announced = datetime.fromisoformat(change.announced_at)
        if announced > cutoff or announced > datetime.fromisoformat(notice.captured_at):
            raise ValueError("Change announcement after cutoff or notice capture")
        if any(change.target_revision_id not in claim_sources[cid] for cid in change.affected_claim_ids):
            raise ValueError("Affected claim is not linked to target source revision")
        if change.successor_revision_id is not None:
            edges.setdefault(change.target_revision_id,set()).add(change.successor_revision_id)
        normalized.append(change)

    visiting, visited = set(), set()
    def walk(node):
        if node in visiting:
            raise ValueError("Source revision history contains a cycle")
        if node in visited:
            return
        visiting.add(node)
        for successor in sorted(edges.get(node, ())):
            walk(successor)
        visiting.remove(node)
        visited.add(node)
    for node in sorted(edges):
        walk(node)

    ledger, impacts = [], {}
    for change in sorted(normalized,key=lambda x:(x.announced_at,x.change_id)):
        target = sources[change.target_revision_id]
        successor = sources[change.successor_revision_id] if change.successor_revision_id else None
        ledger.append({
            "change_id":change.change_id,"change_type":change.change_type,
            "target_revision_id":change.target_revision_id,
            "successor_revision_id":change.successor_revision_id,
            "notice_revision_id":change.notice_revision_id,"notice_anchor_id":change.notice_anchor_id,
            "affected_claim_ids":list(change.affected_claim_ids),"announced_at":change.announced_at,
            "target_url":target.url,"target_title":target.title,
            "successor_url":successor.url if successor else None,
            "successor_title":successor.title if successor else None,
            "notice_url":notice.url,"notice_title":notice.title,
            "notice_status":"caller_declared_change_checked_against_supplied_text",
            "semantic_change_verified":False,"source_authentication":"not_performed",
            "prior_assessment_report_id":previous_id,
        })
        for cid in change.affected_claim_ids:
            prior_status = previous_status.get(cid) if previous else None
            prior_precedes = bool(previous_at and previous_at < announced)
            impacts.setdefault(cid,[]).append({
                "change_id":change.change_id,"change_type":change.change_type,
                "target_revision_id":change.target_revision_id,
                "successor_revision_id":change.successor_revision_id,
                "prior_assessment_status":prior_status,
                "prior_assessment_as_of":previous_at.isoformat() if previous_at else None,
                "reassessment_required":prior_precedes if previous else None,
                "reassessment_state":"required" if prior_precedes else (
                    "no_prior_assessment" if not previous else "temporal_order_does_not_establish_inclusion"),
            })
    result = {
        "schema_version":1,"method":"source_change_traceability_v1",
        "graph_id":graph.graph_id,"as_of":cutoff_text,
        "change_count":len(ledger),"change_ledger":ledger,
        "revision_edges":[{"from_revision_id":a,"to_revision_id":b}
                          for a,values in sorted(edges.items()) for b in sorted(values)],
        "affected_claims":[{"claim_id":cid,"changes":impacts[cid],
                            "reassessment_required":any(x["reassessment_required"] is True for x in impacts[cid]),
                            "claim_status":"not_recomputed"} for cid in sorted(impacts)],
        "prior_assessment_report_id":previous_id,
        "historical_revisions_preserved":True,"automatic_graph_mutation":False,
        "semantic_change_verified":False,"source_authentication":"not_performed",
        "source_independence":"unknown","network_performed":False,"paid_services_used":False,
        "limitations":[
            "Change events are caller annotations checked against exact supplied notice text, not authenticated publisher actions.",
            "Correction/retraction semantics are not inferred from a URL or heading; the notice remains an anchored candidate.",
            "Old and successor revisions remain immutable; claim graphs and assessments are never silently rewritten.",
            "Reassessment-required means a prior assessment predates the declared notice, not that the notice is substantively valid.",
            "A retraction is not proof that every assertion in the source was false.",
        ],
    }
    result["report_id"]=_digest(result)
    return result
