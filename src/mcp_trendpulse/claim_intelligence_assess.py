"""V5.05: deterministic evidence-direction assessment with freshness and conflict.

Consumes only explicit caller-annotated graph relations. Never estimates truth
probability, authenticates sources, assumes independence or turns ratings into
verdicts. All results remain provisional evidence status, not fact certification.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from pydantic import Field, field_validator, model_validator

from mcp_trendpulse.claim_intelligence_graph import ClaimEvidenceGraph
from mcp_trendpulse.news_intelligence_schema import Digest, FrozenModel, _digest, _utc

MAX_POLICIES = 80
MAX_DEPENDENCY_PAIRS = 200


class AssessmentPolicy(FrozenModel):
    """Caller declares whether this claim is current and how old evidence may be."""

    claim_id: Digest
    temporal_relevance: Literal["stable", "current", "specific_period", "unknown"] = "unknown"
    max_evidence_age_days: int | None = Field(default=None, ge=0, le=36500, strict=True)
    require_explicit_claim_scope: bool = False

    @model_validator(mode="after")
    def _check(self):
        if (self.temporal_relevance == "current") != (self.max_evidence_age_days is not None):
            raise ValueError("Current claims require an explicit freshness threshold; other types must omit it")
        return self


def _typed_graph(graph):
    if not isinstance(graph, ClaimEvidenceGraph):
        raise ValueError("Expected a typed claim evidence graph")
    try:
        return ClaimEvidenceGraph.model_validate_json(graph.model_dump_json())
    except (ValueError, TypeError):
        raise ValueError("Invalid claim evidence graph") from None


def _validate_lineage(report, graph):
    if report is None:
        return None
    if not isinstance(report, dict) or len(report) > 32 or report.get("method") != "claim_source_lineage_v1":
        raise ValueError("Invalid source-lineage assessment receipt")
    if report.get("report_id") != _digest({k:v for k,v in report.items() if k != "report_id"}):
        raise ValueError("Source-lineage fingerprint mismatch")
    if (report.get("graph_id") != graph.graph_id or report.get("source_independence") != "unknown"
            or report.get("semantic_verification") != "not_performed"
            or report.get("source_authentication") != "not_performed"):
        raise ValueError("Source-lineage scope mismatch")
    if report.get("network_performed") is not False or report.get("paid_services_used") is not False:
        raise ValueError("Unexpected lineage execution mode")
    reviews = report.get("claim_reviews")
    if not isinstance(reviews, list) or len(reviews) > 80:
        raise ValueError("Invalid source-lineage claim reviews")
    ids = [row.get("claim_id") for row in reviews if isinstance(row, dict)]
    if len(ids) != len(reviews) or len(set(ids)) != len(ids) or not set(ids).issubset({c.claim_id for c in graph.claims}):
        raise ValueError("Invalid source-lineage claim IDs")
    for row in reviews:
        pairs = row.get("pairs_requiring_dependency_review")
        if not isinstance(pairs, list) or len(pairs) > MAX_DEPENDENCY_PAIRS:
            raise ValueError("Invalid source dependency pairs")
        if row.get("source_independence") != "unknown" or (
            row.get("independent_supporting_source_count") is not None
            or row.get("independent_contradicting_source_count") is not None
        ):
            raise ValueError("Lineage cannot assert independent sources")
    return {row["claim_id"]: row for row in reviews}


def assess_claim_evidence(graph, *, as_of, policies=(), lineage_report=None):
    """Report provisional evidence direction, scope and freshness for each claim.

    A "supported"/"contradicted" status means that supplied checked-document
    relation annotations point in that direction. It is not an adjudication.
    Both directions -> disputed. If current evidence exceeds caller's age
    threshold, a lone directional status is downgraded to unverified.
    """
    graph = _typed_graph(graph)
    cutoff_text = _utc(as_of)
    cutoff = datetime.fromisoformat(cutoff_text)
    if cutoff < datetime.fromisoformat(graph.as_of):
        raise ValueError("Assessment cutoff precedes graph cutoff")
    if not isinstance(policies, (list, tuple)) or len(policies) > MAX_POLICIES:
        raise ValueError("Assessment policy budget exceeded")
    clean = []
    for policy in policies:
        if not isinstance(policy, AssessmentPolicy):
            raise ValueError("Expected typed assessment policy")
        try:
            clean.append(AssessmentPolicy.model_validate_json(policy.model_dump_json()))
        except (ValueError, TypeError):
            raise ValueError("Invalid assessment policy") from None
    if len({p.claim_id for p in clean}) != len(clean):
        raise ValueError("Duplicate assessment policy")
    claims = {c.claim_id:c for c in graph.claims}
    policy_by_claim = {p.claim_id:p for p in clean}
    if not set(policy_by_claim).issubset(claims):
        raise ValueError("Policy references unknown claim")
    lineage = _validate_lineage(lineage_report, graph)
    sources = {s.source_revision_id:s for s in graph.sources}
    anchors = {e.evidence_id:e for e in graph.evidence}
    checks = {e.evidence_id:e.status for e in graph.anchor_checks}
    relations = {cid:[] for cid in claims}
    for edge in graph.relations:
        relations[edge.claim_id].append(edge)

    results = []
    for cid in sorted(claims):
        claim = claims[cid]
        policy = policy_by_claim.get(cid, AssessmentPolicy(claim_id=cid))
        attached = relations[cid]
        role_sources = {"supports":set(), "contradicts":set(), "context":set(), "insufficient":set()}
        role_bundles = {key:[] for key in role_sources}
        evidence_rows = {}
        for edge in attached:
            source_ids = []
            for eid in edge.evidence_ids:
                anchor = anchors[eid]
                sid = anchor.source_revision_id
                source = sources[sid]
                source_ids.append(sid)
                evidence_rows[eid] = {
                    "evidence_id":eid, "source_revision_id":sid,
                    "source_kind":source.source_kind, "anchor_check":checks[eid],
                    "captured_at":source.captured_at,
                    "reported_publication": source.observation.published_at.model_dump(mode="json")
                        if source.observation and source.observation.published_at else None,
                    "provider_seen_at": source.observation.provider_seen_at.model_dump(mode="json")
                        if source.observation and source.observation.provider_seen_at else None,
                }
                role_sources[edge.relation].add(sid)
            role_bundles[edge.relation].append({
                "relation_id":edge.relation_id, "evidence_ids":list(edge.evidence_ids),
                "source_revision_ids":sorted(set(source_ids)),
                "scope_alignment":edge.scope_alignment, "rationale":edge.rationale,
                "method":edge.method,
            })
        directional = role_sources["supports"] | role_sources["contradicts"]
        # A multi-source bundle is one caller-annotated joint evidence set;
        # don't present it as N separate independent witnesses.
        directional_bundles = [
            b for role in ("supports","contradicts") for b in role_bundles[role]
        ]
        freshness = []
        age_by_source = {}
        for sid in sorted(directional):
            captured = sources[sid].captured_at
            if captured is None:
                state, age = "unknown", None
            else:
                age = (cutoff - datetime.fromisoformat(captured)).total_seconds() / 86400
                if age < 0:
                    raise ValueError("Evidence capture after assessment cutoff")
                threshold = policy.max_evidence_age_days
                state = ("stale" if threshold is not None and age > threshold else "within_policy")
            age_by_source[sid] = state
            freshness.append({"source_revision_id":sid,"captured_at":captured,
                              "age_days":None if age is None else round(age,6),
                              "status":state,"threshold_days":policy.max_evidence_age_days})
        support = role_sources["supports"]
        contradict = role_sources["contradicts"]
        support_fresh = {sid for sid in support if age_by_source[sid] == "within_policy"}
        contradict_fresh = {sid for sid in contradict if age_by_source[sid] == "within_policy"}
        both = bool(support and contradict)
        if both:
            status = "disputed"
            reason = "opposing_evidence_directions"
        elif support and not contradict:
            if policy.temporal_relevance == "current" and not support_fresh:
                status, reason = "unverified", "supporting_evidence_stale_or_capture_unknown"
            elif policy.require_explicit_claim_scope and not (
                claim.scope.geography or claim.scope.period_start or claim.scope.period_end or claim.scope.qualifiers
            ):
                status, reason = "unverified", "claim_scope_not_explicit"
            else:
                status, reason = "supported", "caller_annotated_scope_matched_document_evidence"
        elif contradict and not support:
            if policy.temporal_relevance == "current" and not contradict_fresh:
                status, reason = "unverified", "contradicting_evidence_stale_or_capture_unknown"
            elif policy.require_explicit_claim_scope and not (
                claim.scope.geography or claim.scope.period_start or claim.scope.period_end or claim.scope.qualifiers
            ):
                status, reason = "unverified", "claim_scope_not_explicit"
            else:
                status, reason = "contradicted", "caller_annotated_scope_matched_document_evidence"
        elif attached:
            status, reason = "unverified", "context_or_insufficient_evidence_only"
        else:
            status, reason = "unknown", "no_assessed_evidence_relations"
        if policy.temporal_relevance == "specific_period" and not (
            claim.scope.period_start or claim.scope.period_end
        ):
            status, reason = "unverified", "specific_period_claim_scope_missing"
        if any(x == "unknown" for x in age_by_source.values()):
            freshness_status = "unknown"
        elif any(x == "stale" for x in age_by_source.values()):
            freshness_status = "stale"
        elif age_by_source:
            freshness_status = "within_policy"
        else:
            freshness_status = "not_assessed"
        if not directional:
            coverage = "no_directional_evidence"
        elif both:
            coverage = "opposing_directions_present"
        elif policy.temporal_relevance == "current" and status == "unverified":
            coverage = "directional_evidence_not_currently_usable"
        else:
            coverage = "one_or_more_caller_annotated_evidence_bundles"
        lineage_row = lineage.get(cid) if lineage else None
        dependency_pairs = lineage_row["pairs_requiring_dependency_review"] if lineage_row else []
        results.append({
            "claim_id":cid, "proposition_id":claim.proposition_id,
            "claim_text_parts":{"subject":claim.subject,"predicate":claim.predicate,"object":claim.object,
                                "polarity":claim.polarity,"modality":claim.modality,
                                "attribution":claim.attribution,"scope":claim.scope.model_dump(mode="json")},
            "status":status,"status_reason":reason,
            "evidence_coverage":coverage,"freshness_status":freshness_status,
            "freshness_by_source":freshness,
            "supporting_source_revision_ids":sorted(support),
            "contradicting_source_revision_ids":sorted(contradict),
            "context_source_revision_ids":sorted(role_sources["context"]),
            "insufficient_source_revision_ids":sorted(role_sources["insufficient"]),
            "supporting_evidence_bundles":role_bundles["supports"],
            "contradicting_evidence_bundles":role_bundles["contradicts"],
            "context_evidence_bundles":role_bundles["context"],
            "insufficient_evidence_bundles":role_bundles["insufficient"],
            "evidence_sources": [evidence_rows[k] for k in sorted(evidence_rows)],
            "source_kind_counts": {
                kind:sum(1 for sid in directional if sources[sid].source_kind == kind)
                for kind in ("primary_document","secondary_reporting","opinion","unknown")
            },
            "source_independence":"unknown",
            "dependency_review_pair_count":len(dependency_pairs),
            "independent_supporting_source_count":None,
            "independent_contradicting_source_count":None,
            "numeric_confidence":None,
            "policy": policy.model_dump(mode="json"),
            "limitations":[
                "Status describes caller-annotated evidence direction, not a verified fact verdict.",
                "No automatic semantic support, contradiction or independence assessment was performed.",
                "One joint bundle is not multiple independent witnesses; no source count is an independent-source count.",
                "Document source kinds and capture times are caller-declared metadata, not authenticated.",
                "Capture time is retrieval time, not necessarily evidence publication, validity or occurrence time.",
                "Third-party fact-check ratings are not included as TrendPulse verdicts.",
            ],
        })
    report = {
        "schema_version":1,"method":"claim_evidence_assessment_v1",
        "graph_id":graph.graph_id,"as_of":cutoff_text,
        "claim_count":len(results),"assessments":results,
        "status_counts":{key:sum(x["status"]==key for x in results)
                         for key in ("supported","independently_corroborated","unverified","disputed","contradicted","unknown")},
        "independently_corroborated_count":0,
        "source_independence":"unknown","semantic_verification":"not_performed",
        "numeric_confidence":"not_produced","network_performed":False,"paid_services_used":False,
        "limitations":[
            "A supported or contradicted status means caller-labelled checked-document evidence points in that direction.",
            "Independent corroboration is never inferred from counts, publisher labels, distinct URLs or absence of detected copying.",
            "Currentness uses an explicit caller threshold and source capture time only; publication and seen time are not interchangeable.",
            "Specific-period and geographic scope require explicit claim metadata; relation scope alignment remains a caller declaration.",
            "No evidence does not mean the claim is false; stale evidence does not prove a changed fact.",
            "No calibrated probability or universal source trust ranking is calculated.",
        ],
    }
    report["report_id"] = _digest(report)
    return report
