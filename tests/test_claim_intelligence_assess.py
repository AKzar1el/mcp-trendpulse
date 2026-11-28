"""Synthetic conservative evidence assessment regressions."""
import pytest

from mcp_trendpulse.claim_intelligence_graph import (
    AtomicClaim, EvidenceAnchor, EvidenceRelation, SourceRevision, build_claim_graph,
)
from mcp_trendpulse.claim_intelligence_assess import AssessmentPolicy, assess_claim_evidence
from mcp_trendpulse.claim_intelligence_lineage import analyze_source_lineage
from mcp_trendpulse.news_intelligence_schema import _digest

CUT = "2026-11-28T12:00:00Z"


def source(key, *, kind="primary_document", capture=CUT, text=None):
    text = text or f"Synthetic evidence record {key} supports the proposition."
    import hashlib
    s = SourceRevision(basis="caller_document", source_kind=kind,
                       url=f"https://{key}.example.org/record", title=key,
                       captured_at=capture, revision_label="test revision",
                       retention="permitted_excerpt", text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                       text_character_count=len(text))
    a = EvidenceAnchor(source_revision_id=s.source_revision_id, selector="document_span",
                       start=0, end=len(text), excerpt=text, span_sha256=hashlib.sha256(text.encode()).hexdigest())
    return s,a,text


def graph(*, supporting=(), contradicting=(), context=(), claim_scope=None, dual_direction_same=False):
    origin_text = "Acme claims output reached 100 units."
    import hashlib
    os = SourceRevision(basis="caller_document",source_kind="unknown",url="https://origin.example.org/report",
                        title="Original claim",captured_at=CUT,revision_label="origin",
                        retention="permitted_excerpt",text_sha256=hashlib.sha256(origin_text.encode()).hexdigest(),
                        text_character_count=len(origin_text))
    oa = EvidenceAnchor(source_revision_id=os.source_revision_id,selector="document_span",start=0,
                        end=len(origin_text),excerpt=origin_text,span_sha256=hashlib.sha256(origin_text.encode()).hexdigest())
    claim = AtomicClaim(subject="Acme",predicate="produced",object="100 units",polarity="affirmed",
                        modality="allegation",attribution="Acme",origin_evidence_id=oa.evidence_id,
                        scope=claim_scope or __import__("mcp_trendpulse.claim_intelligence_graph",fromlist=["ClaimScope"]).ClaimScope())
    items = [(os, oa, origin_text)]
    items.extend(supporting)
    items.extend(contradicting)
    items.extend(context)
    if dual_direction_same:
        items = [items[0], supporting[0]]
    all_sources = [x[0] for x in items]
    all_anchors = [x[1] for x in items]
    relations=[]
    idx=1
    for group,kind in ((supporting,"supports"),(contradicting,"contradicts"),(context,"context")):
        for _ in group:
            anchor_idx = 1 if dual_direction_same and kind == "contradicts" else idx
            relations.append(EvidenceRelation(claim_id=claim.claim_id,evidence_ids=(all_anchors[anchor_idx].evidence_id,),
                                              relation=kind,scope_alignment="matched" if kind in ("supports","contradicts") else "unknown",
                                              rationale="Synthetic reviewer annotation"))
            if not (dual_direction_same and kind == "contradicts"):
                idx+=1
    g = build_claim_graph(as_of=CUT, sources=all_sources, evidence=all_anchors, claims=[claim], relations=relations,
                          document_texts={x[0].source_revision_id: x[2] for x in items if x[2] is not None})
    return g, claim


def assess(g, claim, **kwargs):
    return assess_claim_evidence(g,as_of=CUT,**kwargs)["assessments"][0]


def test_no_edges_is_unknown_not_false():
    g, c = graph()
    r=assess(g,c)
    assert r["status"]=="unknown" and r["numeric_confidence"] is None
    assert r["source_independence"]=="unknown"


def test_one_scope_matched_primary_support_is_provisional_supported():
    a=source("support")
    g,c=graph(supporting=[a])
    r=assess(g,c)
    assert r["status"]=="supported"
    assert r["status_reason"]=="caller_annotated_scope_matched_document_evidence"
    assert r["supporting_source_revision_ids"]==[a[0].source_revision_id]
    assert r["source_independence"]=="unknown"
    assert r["independent_supporting_source_count"] is None


def test_opposing_sources_are_disputed_not_net_scored():
    a,b=source("support"),source("counter")
    g,c=graph(supporting=[a],contradicting=[b])
    r=assess(g,c)
    assert r["status"]=="disputed"
    assert len(r["supporting_evidence_bundles"])==1 and len(r["contradicting_evidence_bundles"])==1
    assert r["numeric_confidence"] is None


def test_same_revision_on_both_sides_remains_disputed():
    a=source("shared")
    g,c=graph(supporting=[a],contradicting=[a],dual_direction_same=True)
    r=assess(g,c)
    assert r["status"]=="disputed"
    assert r["supporting_source_revision_ids"]==r["contradicting_source_revision_ids"]


def test_context_only_is_unverified_not_supported():
    a=source("context")
    g,c=graph(context=[a])
    assert assess(g,c)["status"]=="unverified"


def test_current_freshness_policy_downgrades_old_evidence():
    old=source("old",capture="2026-01-01T00:00:00Z")
    g,c=graph(supporting=[old])
    p=AssessmentPolicy(claim_id=c.claim_id,temporal_relevance="current",max_evidence_age_days=30)
    r=assess(g,c,policies=[p])
    assert r["status"]=="unverified" and r["freshness_status"]=="stale"
    assert r["freshness_by_source"][0]["status"]=="stale"


def test_unknown_capture_cannot_be_promoted_to_directional_verification():
    item=source("unknown",capture=None)
    with pytest.raises(ValueError,match="known capture"):
        graph(supporting=[item])


def test_stable_claim_does_not_invent_staleness_threshold():
    old=source("old",capture="2000-01-01T00:00:00Z")
    g,c=graph(supporting=[old])
    p=AssessmentPolicy(claim_id=c.claim_id,temporal_relevance="stable")
    r=assess(g,c,policies=[p])
    assert r["status"]=="supported" and r["freshness_status"]=="not_assessed"
    assert r["freshness_by_source"][0]["status"]=="not_assessed"


def test_specific_period_and_required_scope():
    a=source("period")
    g,c=graph(supporting=[a])
    p=AssessmentPolicy(claim_id=c.claim_id,temporal_relevance="specific_period",require_explicit_claim_scope=True)
    r=assess(g,c,policies=[p])
    assert r["status"]=="unverified" and r["status_reason"]=="specific_period_claim_scope_missing"


def test_future_capture_and_cutoff_rejected():
    item=source("future",capture="2026-11-29T00:00:00Z")
    with pytest.raises(ValueError,match="after graph cutoff"):
        graph(supporting=[item])
    g,c=graph()
    with pytest.raises(ValueError,match="cutoff"):
        assess_claim_evidence(g,as_of="2026-11-27T00:00:00Z")


def test_lineage_review_never_turns_pair_absence_into_independence():
    a, b = source("a"), source("b")
    g,c=graph(supporting=[a,b])
    lineage=analyze_source_lineage(g)
    r=assess(g,c,lineage_report=lineage)
    assert r["status"]=="supported"
    assert r["source_independence"]=="unknown"
    assert r["independent_supporting_source_count"] is None
    assert r["dependency_review_pair_count"]==0


def test_lineage_dependency_pair_is_visible_in_assessment():
    a,b=source("a"),source("b")
    g,c=graph(supporting=[a,b])
    # Two different source revisions with a common upstream root, all source
    # revisions are graph members; declaration anchors contain exact wording.
    # Existing generic source bodies do not contain literal attribution.
    # Exercise the pair-review interface by mutating a valid report below.
    lineage=analyze_source_lineage(g)
    lineage["claim_reviews"][0]["pairs_requiring_dependency_review"]=[{"signals":["declared_common_lineage"]}]
    lineage["report_id"]=_digest({k:v for k,v in lineage.items() if k!="report_id"})
    r=assess(g,c,lineage_report=lineage)
    assert r["dependency_review_pair_count"]==1
    assert r["source_independence"]=="unknown"


@pytest.mark.parametrize("kwargs",[
    {"temporal_relevance":"current"},{"temporal_relevance":"stable","max_evidence_age_days":3},
    {"temporal_relevance":"current","max_evidence_age_days":True},
])
def test_invalid_policy(kwargs):
    with pytest.raises(ValueError):
        AssessmentPolicy(claim_id="0"*64,**kwargs)


def test_unknown_policy_duplicate_and_deterministic_fingerprint():
    a = source("a")
    g, c = graph(supporting=[a])
    result=assess_claim_evidence(g,as_of=CUT)
    assert result==assess_claim_evidence(g,as_of=CUT)
    assert result["report_id"]==_digest({k:v for k,v in result.items() if k!="report_id"})
    with pytest.raises(ValueError,match="Duplicate"):
        assess_claim_evidence(g,as_of=CUT,policies=[
            AssessmentPolicy(claim_id=c.claim_id),AssessmentPolicy(claim_id=c.claim_id)])
    with pytest.raises(ValueError,match="unknown claim"):
        assess_claim_evidence(g,as_of=CUT,policies=[AssessmentPolicy(claim_id="0"*64)])


def test_factcheck_rating_does_not_enter_evidence_assessment():
    a=source("support");g,c=graph(supporting=[a])
    r=assess(g,c)
    assert r["status"]=="supported"
    assert r["numeric_confidence"] is None
    assert not any("rating" in str(k).lower() for k in r)
