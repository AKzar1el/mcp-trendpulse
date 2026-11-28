"""Synthetic graph contract tests; annotations are not independent fact checks."""
import hashlib
import json

import pytest

from mcp_trendpulse import claim_intelligence_graph as graph
from mcp_trendpulse.news_intelligence_schema import NewsArticle

CUT = "2026-11-28T12:00:00Z"
HEAD = "Acme claims a regional project produced 100 units of energy"
DOC = "Synthetic official record: measured production was 80 units. Private fixture tail."


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def headline(title=HEAD):
    row = NewsArticle(discovery_provider="gdelt_doc", link_type="publisher_candidate",
                      reported_url="https://example.org/report", title=title,
                      capture_mode="legacy_import", captured_at=CUT)
    source = graph.source_from_observation(row)
    anchor = graph.EvidenceAnchor(source_revision_id=source.source_revision_id,
                                  selector="headline_span", start=0, end=len(title), excerpt=title)
    return source, anchor


def document(text=DOC, *, retention="permitted_hash", kind="primary_document", url="https://example.org/record"):
    source = graph.SourceRevision(
        basis="caller_document", source_kind=kind, url=url, title="Synthetic record",
        captured_at=CUT, revision_label="2026-11-28 edition", retention=retention,
        text_sha256=sha(text) if retention != "metadata_only" else None,
        text_character_count=len(text) if retention != "metadata_only" else None,
    )
    if retention == "metadata_only":
        anchor = graph.EvidenceAnchor(source_revision_id=source.source_revision_id,
                                      selector="document_locator", locator="Page 4, table 1")
    else:
        span = text[:text.index(".") + 1]
        anchor = graph.EvidenceAnchor(
            source_revision_id=source.source_revision_id, selector="document_span",
            start=0, end=len(span), span_sha256=sha(span),
            excerpt=span if retention == "permitted_excerpt" else None,
        )
    return source, anchor


def claim(anchor, **kwargs):
    return graph.AtomicClaim(**{
        "subject": "Acme", "predicate": "produced", "object": "100 units of energy",
        "polarity": "affirmed", "modality": "allegation", "origin_evidence_id": anchor.evidence_id,
        "attribution": "Acme", **kwargs,
    })


def edge(c, *anchors, **kwargs):
    return graph.EvidenceRelation(**{
        "claim_id": c.claim_id, "evidence_ids": tuple(a.evidence_id for a in anchors),
        "relation": "contradicts", "scope_alignment": "matched", "rationale": "Caller reports a difference.",
        **kwargs,
    })


def test_headline_adapter_preserves_attribution_uncertainty():
    s, a = headline()
    c = claim(a)
    result = graph.build_claim_graph(as_of=CUT, sources=[s], evidence=[a], claims=[c])
    assert result.sources[0].observation.title == HEAD
    assert result.sources[0].source_kind == "unknown"
    assert result.claims[0].modality == "allegation"
    assert result.claims[0].asserted_at is None and result.claims[0].attribution == "Acme"
    assert result.anchor_checks[0].status == "exact_headline"
    assert result.semantic_verification == "not_performed"
    assert not result.network_performed


def test_checked_hash_only_document_relation_roundtrip_and_order():
    s, a = headline()
    d, b = document()
    c = claim(a)
    e = edge(c, b)
    inputs = dict(as_of=CUT, sources=[s,d], evidence=[a,b], claims=[c], relations=[e],
                  document_texts={d.source_revision_id: DOC})
    result = graph.build_claim_graph(**inputs)
    replay = graph.build_claim_graph(**{**inputs, "sources": [d,s], "evidence": [b,a]})
    assert result == replay
    assert {x.status for x in result.anchor_checks} == {"exact_headline", "checked_against_supplied_text"}
    assert result.relations[0].relation == "contradicts"
    assert result.source_independence == "unknown"
    wire = result.model_dump_json()
    assert DOC not in wire and "Private fixture tail" not in wire and "measured production" not in wire
    assert graph.ClaimEvidenceGraph.model_validate_json(wire) == result


def test_explicit_excerpt_rights_and_exact_offsets():
    s, a = document(retention="permitted_excerpt")
    g = graph.build_claim_graph(as_of=CUT, sources=[s], evidence=[a], document_texts={s.source_revision_id: DOC})
    assert g.evidence[0].excerpt == DOC[:a.end]
    assert "Private fixture tail" not in g.model_dump_json()
    h, b = document()
    forged = graph.EvidenceAnchor(source_revision_id=h.source_revision_id, selector="document_span",
                                  start=b.start, end=b.end, span_sha256=b.span_sha256, excerpt=DOC[:b.end])
    with pytest.raises(ValueError, match="Excerpt retention"):
        graph.build_claim_graph(as_of=CUT, sources=[h], evidence=[forged],
                                document_texts={h.source_revision_id: DOC})


def test_document_hash_and_span_mismatch_fail_closed():
    s, a = document()
    for texts, reason in (({}, "requires ephemeral"), ({s.source_revision_id: "X"*len(DOC)}, "digest mismatch")):
        with pytest.raises(ValueError, match=reason):
            graph.build_claim_graph(as_of=CUT, sources=[s], evidence=[a], document_texts=texts)
    bad = graph.EvidenceAnchor(source_revision_id=s.source_revision_id, selector="document_span",
                               start=0, end=4, span_sha256=sha("FAKE"))
    with pytest.raises(ValueError, match="does not match"):
        graph.build_claim_graph(as_of=CUT, sources=[s], evidence=[bad], document_texts={s.source_revision_id: DOC})


@pytest.mark.parametrize("kind", ["headline", "opinion", "unknown", "locator", "origin"])
def test_weak_anchors_cannot_be_support_or_contradiction(kind):
    s, a = headline()
    c = claim(a)
    documents = {}
    if kind == "headline":
        d, b = headline("Acme says production was lower than expected")
    elif kind == "origin":
        d, b = s, a
    elif kind == "locator":
        d, b = document(retention="metadata_only")
    else:
        d, b = document(kind=kind)
        documents[d.source_revision_id] = DOC
    sources = [s] if d == s else [s,d]
    anchors = [a] if b == a else [a,b]
    args = dict(as_of=CUT, sources=sources, evidence=anchors, claims=[c], document_texts=documents)
    with pytest.raises(ValueError, match="verification evidence|checked document evidence"):
        graph.build_claim_graph(**args, relations=[edge(c,b)])
    g = graph.build_claim_graph(**args, relations=[edge(c,b,relation="context",scope_alignment="unknown")])
    assert g.relations[0].relation == "context"


def test_joint_relations_preserve_conflicts_without_verdict():
    s, a = headline()
    d, b = document()
    t = "Synthetic secondary record reports measured production of 100 units."
    d2, b2 = document(t, kind="secondary_reporting", url="https://other.org/report")
    c = claim(a)
    g = graph.build_claim_graph(as_of=CUT, sources=[s,d,d2], evidence=[a,b,b2], claims=[c],
                                relations=[edge(c,b), edge(c,b2,relation="supports"), edge(c,b,b2,relation="context")],
                                document_texts={d.source_revision_id:DOC,d2.source_revision_id:t})
    assert {e.relation for e in g.relations} == {"supports","contradicts","context"}
    assert any(len(e.evidence_ids) == 2 for e in g.relations)
    assert g.semantic_verification == "not_performed"


def test_claim_ids_keep_scope_polarity_modality_and_origin_distinct():
    _, a = headline()
    base = claim(a)
    other = claim(a, modality="quotation", attribution="Different speaker")
    assert base.proposition_id == other.proposition_id and base.claim_id != other.claim_id
    assert base.proposition_id != claim(a, polarity="negated").proposition_id
    assert base.proposition_id != claim(a, scope=graph.ClaimScope(geography="Slovenia")).proposition_id
    assert claim(a, scope=graph.ClaimScope(qualifiers=("b","a"))) == claim(
        a, scope=graph.ClaimScope(qualifiers=("a","b")))
    assert base.proposition_id != claim(a, object="80 units of energy").proposition_id


def test_claim_dates_and_scope_are_not_source_dates():
    s, a = headline()
    c = claim(a, asserted_at="2026-11-28T11:00:00+01:00", asserted_at_precision="timestamp")
    assert c.asserted_at == "2026-11-28T10:00:00+00:00"
    assert c.scope.period_start is None
    for kwargs in ({"asserted_at": "2026-11-28"}, {"asserted_at_precision": "day"}):
        with pytest.raises(ValueError):
            claim(a, **kwargs)
    with pytest.raises(ValueError, match="Reversed"):
        graph.ClaimScope(period_start="2026-11-28",period_end="2026-11-27")
    for val, precision in (("2026-11-29","day"), ("2026-11-28T13:00:00Z","timestamp")):
        with pytest.raises(ValueError, match="after graph cutoff"):
            graph.build_claim_graph(as_of=CUT, sources=[s], evidence=[a],
                                    claims=[claim(a, asserted_at=val, asserted_at_precision=precision)])


def test_mismatched_scope_unknown_polarity_and_opinion_guard():
    s, a = headline()
    d, b = document()
    with pytest.raises(ValueError, match="matching scope"):
        edge(claim(a), b, scope_alignment="unknown")
    for c in (claim(a, modality="opinion"), claim(a, polarity="unknown"), claim(a, modality="question")):
        with pytest.raises(ValueError, match="noncheckable"):
            graph.build_claim_graph(as_of=CUT, sources=[s,d], evidence=[a,b], claims=[c],
                                    relations=[edge(c,b)], document_texts={d.source_revision_id:DOC})


def test_dangling_duplicate_and_forged_references_rejected():
    s, a = headline()
    c = claim(a)
    with pytest.raises(ValueError, match="Dangling source"):
        graph.build_claim_graph(as_of=CUT, evidence=[a])
    with pytest.raises(ValueError, match="Dangling claim origin"):
        graph.build_claim_graph(as_of=CUT, sources=[s], claims=[c])
    with pytest.raises(ValueError, match="Dangling claim"):
        graph.build_claim_graph(as_of=CUT, sources=[s], evidence=[a], relations=[edge(c,a,relation="context")])
    with pytest.raises(ValueError, match="Duplicate"):
        graph.build_claim_graph(as_of=CUT, sources=[s,s])
    with pytest.raises(ValueError, match="Invalid graph input"):
        graph.build_claim_graph(as_of=CUT, sources=[s.model_copy(update={"url":"https://127.0.0.1/"})])
    bad = graph.EvidenceAnchor(source_revision_id=s.source_revision_id, selector="headline_span",
                               start=0, end=4, excerpt="Fake")
    with pytest.raises(ValueError, match="does not match"):
        graph.build_claim_graph(as_of=CUT, sources=[s], evidence=[bad])


def test_no_future_source_and_no_unpermitted_document_input():
    s,a = headline()
    with pytest.raises(ValueError, match="after graph cutoff"):
        graph.build_claim_graph(as_of="2026-11-27T12:00:00Z", sources=[s], evidence=[a])
    d,b = document(retention="metadata_only")
    with pytest.raises(ValueError, match="permitted revision scope"):
        graph.build_claim_graph(as_of=CUT, sources=[d], evidence=[b], document_texts={d.source_revision_id:DOC})


def test_bounded_input_and_invalid_graph_fingerprint():
    s,a = headline()
    with pytest.raises(ValueError, match="bounded"):
        graph.build_claim_graph(as_of=CUT,sources=[s]*(graph.MAX_SOURCES+1))
    result = graph.build_claim_graph(as_of=CUT,sources=[s],evidence=[a])
    data = json.loads(result.model_dump_json())
    data["as_of"] = "2026-11-29T12:00:00Z"
    with pytest.raises(ValueError, match="identity"):
        graph.ClaimEvidenceGraph.model_validate_json(json.dumps(data))


def test_actual_v4_investigation_observations_adapter():
    import asyncio
    from mcp_trendpulse.news_intelligence_investigate import investigate_news
    from mcp_trendpulse.news_intelligence_schema import parse_news_capture
    capture = [{
        "url":"https://news.google.com/rss/articles/abc", "title":HEAD,
        "meta_data":{"content_level":"rss_headline_only","source":"google_news_rss"},
    }]
    batch = parse_news_capture(json.dumps(capture).encode(),provider="google_news_rss",captured_at=CUT)
    report = asyncio.run(investigate_news("energy",sources=(),imported_batches=[batch]))
    rows = report["all_sample_and_context"]["event_report"]["observations"]
    sources = [graph.source_from_observation(NewsArticle.model_validate_json(json.dumps(row))) for row in rows]
    assert len(sources) == 1
    assert graph.build_claim_graph(as_of=CUT,sources=sources).sources[0].title == HEAD
