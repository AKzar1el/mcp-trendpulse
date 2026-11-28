"""Synthetic lineage contract tests, not independently authenticated evidence."""
import hashlib
import json

import pytest

from mcp_trendpulse.claim_intelligence_graph import (
    AtomicClaim, EvidenceAnchor, EvidenceRelation, SourceRevision, build_claim_graph, source_from_observation,
)
from mcp_trendpulse.claim_intelligence_lineage import LineageLink, OwnershipHint, analyze_source_lineage
from mcp_trendpulse.news_intelligence_schema import NewsArticle, _digest

CUT = "2026-11-28T12:00:00Z"


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def document(key, text, *, host=None):
    s = SourceRevision(basis="caller_document", source_kind="primary_document",
                       url=f"https://{host or key+'.example.org'}/record", title=key,
                       captured_at=CUT, revision_label="fixture", retention="permitted_excerpt",
                       text_sha256=sha(text), text_character_count=len(text))
    a = EvidenceAnchor(source_revision_id=s.source_revision_id, selector="document_span",
                       start=0, end=len(text), excerpt=text, span_sha256=sha(text))
    return s, a, text


def headline(key, text, *, label=None, url=None):
    s = source_from_observation(NewsArticle(
        discovery_provider="gdelt_doc", link_type="publisher_candidate",
        reported_url=url or f"https://{key}.example.org/story", title=text,
        publisher_label=label, captured_at=CUT, capture_mode="legacy_import"))
    a = EvidenceAnchor(source_revision_id=s.source_revision_id, selector="headline_span",
                       start=0, end=len(text), excerpt=text)
    return s, a, None


def graph_of(items, *, support=(), contradict=(), context=()):
    origin = items[0][1]
    c = AtomicClaim(subject="Acme", predicate="produced", object="100 units", polarity="affirmed",
                    modality="assertion", origin_evidence_id=origin.evidence_id)
    edges = [EvidenceRelation(claim_id=c.claim_id, evidence_ids=(items[i][1].evidence_id,),
                              relation=kind, scope_alignment="matched", rationale="Synthetic annotation")
             for kind, indices in (("supports", support), ("contradicts", contradict), ("context", context))
             for i in indices]
    g = build_claim_graph(as_of=CUT, sources=[x[0] for x in items], evidence=[x[1] for x in items],
                          claims=[c], relations=edges,
                          document_texts={s.source_revision_id:t for s, _, t in items if t is not None})
    return g, c


def link(c, dependent, upstream, kind="wire_copy", text="Wire A"):
    return LineageLink(claim_id=c.claim_id, dependent_source_id=dependent[0].source_revision_id,
                       upstream_source_id=upstream[0].source_revision_id, kind=kind,
                       declaration_anchor_id=dependent[1].evidence_id, reference_text=text)


def review(report):
    return report["claim_reviews"][0]


@pytest.mark.parametrize("kind", ["wire_copy", "press_release", "quoted_primary_source", "repost", "shared_dataset", "revision"])
def test_shared_upstream_is_not_independent_corroboration(kind):
    a = headline("origin", "Acme produced 100 units")
    b = document("b", "Wire A records 100 units.")
    c = document("c", "Wire A reports 100 units.")
    root = document("root", "Original measurement record.")
    g, claim = graph_of([a,b,c,root], support=(1,2))
    links = [link(claim,b,root,kind), link(claim,c,root,kind)]
    report = analyze_source_lineage(g, links=links)
    r = review(report)
    assert len(r["supporting_revision_ids"]) == 2
    pair = next(p for p in r["pairs_requiring_dependency_review"] if "declared_common_lineage" in p["signals"])
    assert pair["shared_upstream_revision_ids"] == [root[0].source_revision_id]
    assert set(pair["lineage_link_ids"]) == {x.link_id for x in links}
    assert r["independent_supporting_source_count"] is None
    assert report["source_independence"] == "unknown"
    assert not report["network_performed"] and not report["paid_services_used"]
    assert report == analyze_source_lineage(g, links=links[::-1])
    assert report["report_id"] == _digest({k:v for k,v in report.items() if k!="report_id"})


def test_shared_lineage_across_opposing_relations_and_cycle():
    a = headline("origin", "Acme produced 100 units")
    b = document("b", "Wire A records 100 units.")
    c = document("c", "Wire A reports 80 units.")
    g, claim = graph_of([a,b,c], support=(1,), contradict=(2,))
    report = analyze_source_lineage(g, links=[link(claim,b,c),link(claim,c,b)])
    r = review(report)
    assert set(r["lineage_cycle_revision_ids"]) == {b[0].source_revision_id,c[0].source_revision_id}
    p = r["pairs_requiring_dependency_review"][0]
    assert "declared_common_lineage" in p["signals"]
    assert {tuple(p["left_roles"]),tuple(p["right_roles"])} == {("supports",),("contradicts",)}
    assert r["independent_contradicting_source_count"] is None


def test_unknown_distinct_publishers_do_not_establish_independence():
    a = headline("origin", "Acme produced 100 units")
    b = document("b", "The record measures production.")
    c = document("c", "Another record reports output.")
    g, _ = graph_of([a,b,c], support=(1,2), contradict=(2,))
    r = review(analyze_source_lineage(g))
    assert r["pair_comparisons"] == 3 and not r["pairs_requiring_dependency_review"]
    assert r["source_independence"] == "unknown"
    assert r["independent_supporting_source_count"] is None
    assert r["sources_annotated_on_both_sides"] == [c[0].source_revision_id]


def test_weak_similarity_and_same_url_not_equivalence():
    title = "Researchers announce a new renewable energy project for regional communities"
    a = headline("a",title)
    b = headline("b",title,url=a[0].url)
    c = headline("c",title)
    g, _ = graph_of([a,b,c], context=(1,2))
    pairs = review(analyze_source_lineage(g))["pairs_requiring_dependency_review"]
    assert any("same_reported_url" in p["signals"] for p in pairs)
    assert any("v4_weak_similarity_or_canonical_hint" in p["signals"] for p in pairs)
    assert all(p["source_independence"] == "unknown" for p in pairs)


def test_identical_document_digest_only_signal():
    a = headline("origin", "Acme produced 100 units")
    b = document("b","Repeated text.")
    c = document("c","Repeated text.")
    g, _ = graph_of([a,b,c],support=(1,2))
    p = review(analyze_source_lineage(g))["pairs_requiring_dependency_review"][0]
    assert p["signals"] == ["matching_document_text_digest"]
    assert p["source_independence"] == "unknown"


def test_ownership_signals_not_used_as_derivation():
    a = headline("a","Acme produced 100 units",label="Outlet A")
    b = headline("b","Beta reports a different result",label="Outlet B")
    d = document("registry","Outlet A and Outlet B are owned by Media Group.")
    g, _ = graph_of([a,b,d],context=(1,))
    hints = [OwnershipHint(source_revision_id=s[0].source_revision_id,
                           declaration_anchor_id=d[1].evidence_id,
                           publisher_reference=label,owner_label="Media Group")
             for s,label in ((a,"Outlet A"),(b,"Outlet B"))]
    p = review(analyze_source_lineage(g,ownership_hints=hints))["pairs_requiring_dependency_review"][0]
    assert p["signals"] == ["shared_declared_owner_label"]
    assert p["shared_upstream_revision_ids"] == [] and p["source_independence"] == "unknown"
    bad = OwnershipHint(source_revision_id=a[0].source_revision_id,
                        declaration_anchor_id=d[1].evidence_id,
                        publisher_reference="Outlet B",owner_label="Media Group")
    with pytest.raises(ValueError,match="Ownership hint"):
        analyze_source_lineage(g,ownership_hints=[bad])


def test_lineage_rejects_missing_anchor_disconnected_claim_and_duplicate():
    a = headline("origin","Acme produced 100 units")
    b = document("b","Wire A records 100 units.")
    c = document("c","Wire A reports 80 units.")
    d = document("d","Wire A reports another figure.")
    g, claim = graph_of([a,b,c,d],support=(1,))
    ok = link(claim,b,c)
    for bad,reason in (
        (link(claim,b,c,text="Invented wire"),"literal declaration"),
        (link(claim,d,c),"connect to"),
        (LineageLink.model_validate({**ok.model_dump(),"link_id":None,"upstream_source_id":"0"*64}),"Dangling"),
        (LineageLink.model_validate({**ok.model_dump(),"link_id":None,
                                     "declaration_anchor_id":c[1].evidence_id}),"literal declaration"),
    ):
        with pytest.raises(ValueError,match=reason):
            analyze_source_lineage(g,links=[bad])
    with pytest.raises(ValueError,match="Duplicate"):
        analyze_source_lineage(g,links=[ok,ok])


def test_claim_scoping_does_not_apply_other_claims_lineage():
    a = headline("origin","Acme produced 100 units")
    b = document("b","Wire A records 100 units.")
    c = document("c","Wire A reports 80 units.")
    root = document("root","Original record.")
    g, first = graph_of([a,b,c,root],support=(1,2))
    second = AtomicClaim(subject="Acme",predicate="produced",object="200 units",polarity="affirmed",
                         modality="assertion",origin_evidence_id=a[1].evidence_id)
    second_edges = [EvidenceRelation(claim_id=second.claim_id,evidence_ids=(x[1].evidence_id,),
                                      relation="context",rationale="Separate claim") for x in (b,c)]
    g2 = build_claim_graph(as_of=CUT,sources=g.sources,evidence=g.evidence,
                           claims=[first,second],relations=[*g.relations,*second_edges],
                           document_texts={s[0].source_revision_id:s[2] for s in (b,c,root)})
    r = analyze_source_lineage(g2,links=[link(first,b,root),link(first,c,root)])
    by_claim = {x["claim_id"]:x for x in r["claim_reviews"]}
    assert any("declared_common_lineage" in p["signals"] for p in by_claim[first.claim_id]["pairs_requiring_dependency_review"])
    assert not any("declared_common_lineage" in p["signals"] for p in by_claim[second.claim_id]["pairs_requiring_dependency_review"])


def test_v4_copy_receipts_recomputed_and_no_body_returned():
    from mcp_trendpulse.news_intelligence_extract import ArticleExtraction
    a = headline("a","Researchers announce a new renewable energy project for regional communities")
    b = headline("b",a[0].title)
    g, _ = graph_of([a,b],context=(1,))
    body = " ".join(f"Researchers recorded experimental observations involving sample group {i} and reported distinct measurements."
                    for i in range(30))
    receipts = [ArticleExtraction(discovery=s[0].observation,status="extracted",started_at=CUT,completed_at=CUT,
                                  content_level="extracted_text",resolved_url=s[0].url,http_status=200,
                                  body_sha256=sha(body),body_digest_policy="operator_permitted") for s in (a,b)]
    r = analyze_source_lineage(g,extractions=receipts,ephemeral_bodies={x.extraction_id:body for x in receipts})
    p = review(r)["pairs_requiring_dependency_review"][0]
    assert "v4_substantive_shared_copy_candidate" in p["signals"]
    assert body not in json.dumps(r)
    with pytest.raises(ValueError,match="does not match"):
        analyze_source_lineage(g,extractions=receipts,ephemeral_bodies={receipts[0].extraction_id:"forged"})
    r = analyze_source_lineage(g,extractions=receipts)
    assert "v4_substantive_shared_copy_candidate" not in review(r)["pairs_requiring_dependency_review"][0]["signals"]


def test_empty_graph_and_forged_graph():
    g = build_claim_graph(as_of=CUT)
    assert analyze_source_lineage(g)["claim_reviews"] == []
    with pytest.raises(ValueError,match="Invalid claim graph"):
        analyze_source_lineage(g.model_copy(update={"as_of":"2026-11-29T12:00:00Z"}))
