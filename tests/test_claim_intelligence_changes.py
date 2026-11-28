"""Synthetic revision/correction traceability contract tests."""
import hashlib
import pytest

from mcp_trendpulse.claim_intelligence_graph import (
    AtomicClaim, EvidenceAnchor, EvidenceRelation, SourceRevision, build_claim_graph,
)
from mcp_trendpulse.claim_intelligence_assess import assess_claim_evidence
from mcp_trendpulse.claim_intelligence_changes import SourceChange, track_source_changes
from mcp_trendpulse.news_intelligence_schema import _digest

CUT = "2026-11-28T12:00:00Z"


def source(name,title,body,kind="primary_document",url=None,capture=CUT):
    s = SourceRevision(basis="caller_document",source_kind=kind,url=url or f"https://{name}.example.org/doc",
                       title=title,captured_at=capture,revision_label=name,retention="permitted_excerpt",
                       text_sha256=hashlib.sha256(body.encode()).hexdigest(),text_character_count=len(body))
    a = EvidenceAnchor(source_revision_id=s.source_revision_id,selector="document_span",start=0,end=len(body),
                       excerpt=body,span_sha256=hashlib.sha256(body.encode()).hexdigest())
    return s,a,body


def make_graph():
    old = source("old","Original report","Original report stated 100 units.",capture="2026-11-26T12:00:00Z")
    notice = source("notice","Correction notice",
                    "Correction notice: Original report at https://old.example.org/doc is superseded by Revised report at https://new.example.org/doc.")
    new = source("new","Revised report","Revised report states 80 units.")
    supporting = source("supporting","Supporting record","Separate supporting record confirms a measurement.",capture="2026-11-26T12:00:00Z")
    claim = AtomicClaim(subject="Acme",predicate="produced",object="100 units",polarity="affirmed",
                        modality="allegation",origin_evidence_id=old[1].evidence_id)
    edge = EvidenceRelation(claim_id=claim.claim_id,evidence_ids=(supporting[1].evidence_id,),
                            relation="supports",scope_alignment="matched",rationale="Separate supporting record")
    g = build_claim_graph(as_of=CUT,sources=[old[0],notice[0],new[0],supporting[0]],
                          evidence=[old[1],notice[1],new[1],supporting[1]],claims=[claim],relations=[edge],
                          document_texts={x[0].source_revision_id:x[2] for x in (old,notice,new,supporting)})
    change = SourceChange(change_type="correction",target_revision_id=old[0].source_revision_id,
                          successor_revision_id=new[0].source_revision_id,notice_revision_id=notice[0].source_revision_id,
                          notice_anchor_id=notice[1].evidence_id,affected_claim_ids=(claim.claim_id,),
                          announced_at=CUT,target_locator_text=old[0].url,successor_locator_text=new[0].url,
                          notice_reference_text="Correction notice")
    return g,claim,old,notice,new,supporting,change


def prior_graph(g, claim, old, supporting, as_of="2026-11-27T12:00:00Z"):
    return build_claim_graph(as_of=as_of,sources=[old[0],supporting[0]],
                             evidence=[old[1],supporting[1]],claims=[claim],relations=g.relations,
                             document_texts={old[0].source_revision_id:old[2],
                                             supporting[0].source_revision_id:supporting[2]})


def test_correction_preserves_history_and_marks_prior_assessment_for_recheck():
    g,c,old,notice,new,supporting,change = make_graph()
    earlier = assess_claim_evidence(prior_graph(g,c,old,supporting),as_of="2026-11-27T12:00:00Z")
    result = track_source_changes(g,as_of=CUT,changes=[change],previous_assessment=earlier)
    assert result["change_count"] == 1
    assert result["revision_edges"] == [{"from_revision_id":old[0].source_revision_id,
                                         "to_revision_id":new[0].source_revision_id}]
    impact = result["affected_claims"][0]
    assert impact["claim_status"] == "not_recomputed" and impact["reassessment_required"]
    assert impact["changes"][0]["prior_assessment_status"] == "supported"
    assert result["historical_revisions_preserved"] and not result["automatic_graph_mutation"]
    assert result["semantic_change_verified"] is False
    assert result["report_id"] == _digest({k:v for k,v in result.items() if k!="report_id"})
    assert result == track_source_changes(g,as_of=CUT,changes=[change],previous_assessment=earlier)


@pytest.mark.parametrize("kind,successor",[
    ("retraction",False),("withdrawal",False),("replacement",True),("clarification",True),
    ("archive_snapshot",True)])
def test_revision_kinds_and_required_successors(kind,successor):
    g,c,old,notice,new,supporting,base = make_graph()
    change = SourceChange(change_type=kind,target_revision_id=old[0].source_revision_id,
                          successor_revision_id=new[0].source_revision_id if successor else None,
                          notice_revision_id=notice[0].source_revision_id,notice_anchor_id=notice[1].evidence_id,
                          affected_claim_ids=(c.claim_id,),announced_at=CUT,target_locator_text=old[0].url,
                          successor_locator_text=new[0].url if successor else None,
                          notice_reference_text="Correction notice")
    out = track_source_changes(g,as_of=CUT,changes=[change])
    assert out["change_ledger"][0]["change_type"] == kind
    assert len(out["revision_edges"]) == (1 if successor else 0)


def test_no_notice_or_future_event_or_missing_claim():
    g,c,old,notice,new,supporting,change = make_graph()
    bad = SourceChange(**{**change.model_dump(),"change_id":None,"notice_anchor_id":old[1].evidence_id})
    with pytest.raises(ValueError,match="checked, captured"):
        track_source_changes(g,as_of=CUT,changes=[bad])
    future = SourceChange(**{**change.model_dump(),"change_id":None,"announced_at":"2026-11-29T00:00:00Z"})
    with pytest.raises(ValueError,match="after cutoff"):
        track_source_changes(g,as_of=CUT,changes=[future])
    unknown = SourceChange(**{**change.model_dump(),"change_id":None,"affected_claim_ids":("0"*64,)})
    with pytest.raises(ValueError,match="unknown claim"):
        track_source_changes(g,as_of=CUT,changes=[unknown])


def test_locator_must_match_exact_notice_and_successor():
    g,c,old,notice,new,supporting,change = make_graph()
    bad = SourceChange(**{**change.model_dump(),"change_id":None,"target_locator_text":"Invented source"})
    with pytest.raises(ValueError,match="exact revision reference"):
        track_source_changes(g,as_of=CUT,changes=[bad])
    bad = SourceChange(**{**change.model_dump(),"change_id":None,"successor_locator_text":"Other revision"})
    with pytest.raises(ValueError,match="exact revision reference"):
        track_source_changes(g,as_of=CUT,changes=[bad])


def test_claim_must_really_reference_target_revision():
    g,c,old,notice,new,supporting,change = make_graph()
    bad = SourceChange(**{**change.model_dump(),"change_id":None,"target_revision_id":notice[0].source_revision_id})
    with pytest.raises(ValueError,match="not linked to target"):
        track_source_changes(g,as_of=CUT,changes=[bad])


def test_assessment_temporal_order_is_not_inferred():
    g,c,old,notice,new,supporting,change = make_graph()
    prior = assess_claim_evidence(prior_graph(g,c,old,supporting,as_of=CUT),as_of=CUT)
    result = track_source_changes(g,as_of=CUT,changes=[change],previous_assessment=prior)
    state = result["affected_claims"][0]["changes"][0]["reassessment_state"]
    assert state == "temporal_order_does_not_establish_inclusion"


def test_change_cycle_rejected():
    old = source("old","Original report","Original report stated 100 units.")
    notice = source("notice","Notice","Correction notice: https://old.example.org/doc https://new.example.org/doc.")
    new = source("new","Revised report","Revised report states 80 units.")
    claim = AtomicClaim(subject="Acme",predicate="produced",object="100 units",polarity="affirmed",
                        modality="allegation",origin_evidence_id=old[1].evidence_id)
    context_edge = EvidenceRelation(claim_id=claim.claim_id,evidence_ids=(new[1].evidence_id,),
                                    relation="context",scope_alignment="unknown",rationale="Revision context")
    g = build_claim_graph(as_of=CUT,sources=[old[0],notice[0],new[0]],
                          evidence=[old[1],notice[1],new[1]],claims=[claim],relations=[context_edge],
                          document_texts={x[0].source_revision_id:x[2] for x in (old,notice,new)})
    a = SourceChange(change_type="correction",target_revision_id=old[0].source_revision_id,
                     successor_revision_id=new[0].source_revision_id,notice_revision_id=notice[0].source_revision_id,
                     notice_anchor_id=notice[1].evidence_id,affected_claim_ids=(claim.claim_id,),announced_at=CUT,
                     target_locator_text=old[0].url,successor_locator_text=new[0].url,notice_reference_text="Correction notice")
    b = SourceChange(change_type="correction",target_revision_id=new[0].source_revision_id,
                     successor_revision_id=old[0].source_revision_id,notice_revision_id=notice[0].source_revision_id,
                     notice_anchor_id=notice[1].evidence_id,affected_claim_ids=(claim.claim_id,),announced_at=CUT,
                     target_locator_text=new[0].url,successor_locator_text=old[0].url,notice_reference_text="Correction notice")
    with pytest.raises(ValueError,match="cycle"):
        track_source_changes(g,as_of=CUT,changes=[a,b])


def test_prior_assessment_fingerprint_scope_and_immutability():
    g,c,old,notice,new,supporting,change = make_graph()
    prior = assess_claim_evidence(prior_graph(g,c,old,supporting),as_of="2026-11-27T12:00:00Z")
    tampered = {**prior,"assessments":[]}
    tampered["report_id"] = _digest({k:v for k,v in tampered.items() if k!="report_id"})
    with pytest.raises(ValueError,match="coverage"):
        track_source_changes(g,as_of=CUT,changes=[change],previous_assessment=tampered)
    result = track_source_changes(g,as_of=CUT,changes=[change],previous_assessment=prior)
    assert prior["assessments"][0]["status"] == "supported"
    assert result["change_ledger"][0]["target_revision_id"] == old[0].source_revision_id
    assert result["change_ledger"][0]["successor_revision_id"] == new[0].source_revision_id
    assert result["change_ledger"][0]["notice_status"] == "caller_declared_change_checked_against_supplied_text"
