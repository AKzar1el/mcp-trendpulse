"""V5.03: claim-scoped source lineage and dependency review.

Lineage links are caller annotations grounded in supplied graph anchors.
They are not authenticated derivations. No ownership or independence oracle,
network access, new dependency, persistent content, or fact verdict.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from itertools import combinations
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator

from mcp_trendpulse.claim_intelligence_graph import ClaimEvidenceGraph, _typed
from mcp_trendpulse.news_intelligence_dedup import analyze_news_duplicates
from mcp_trendpulse.news_intelligence_extract import ArticleExtraction
from mcp_trendpulse.news_intelligence_schema import Digest, FrozenModel, _digest, _text

MAX_LINKS = 240
MAX_OWNERSHIP_HINTS = 80
MAX_CLAIM_PAIR_COMPARISONS = 20000
_METHOD = "claim_source_lineage_v1"
LinkKind = Literal["wire_copy", "press_release", "quoted_primary_source", "repost",
                   "shared_dataset", "revision", "other_derivation"]


class LineageLink(FrozenModel):
    """Caller declares a claim-specific reliance on an exact upstream revision."""

    link_id: Digest | None = None
    claim_id: Digest
    dependent_source_id: Digest
    upstream_source_id: Digest
    kind: LinkKind
    declaration_anchor_id: Digest
    # Literal credit/reference wording, not inferred publisher identity.
    reference_text: str = Field(min_length=1, max_length=160)
    method: Literal["caller_annotation"] = "caller_annotation"

    @field_validator("reference_text")
    @classmethod
    def _label(cls, value):
        return _text(value, 160)

    @model_validator(mode="after")
    def _check(self):
        if self.dependent_source_id == self.upstream_source_id:
            raise ValueError("Self-lineage is invalid")
        expected = _digest(self.model_dump(mode="json", exclude={"link_id"}))
        if self.link_id not in (None, expected):
            raise ValueError("Lineage identity mismatch")
        object.__setattr__(self, "link_id", expected)
        return self


class OwnershipHint(FrozenModel):
    """Literal caller-described ownership signal, not verified control."""

    hint_id: Digest | None = None
    source_revision_id: Digest
    declaration_anchor_id: Digest
    publisher_reference: str = Field(min_length=1, max_length=160)
    owner_label: str = Field(min_length=1, max_length=160)
    method: Literal["caller_annotation"] = "caller_annotation"

    @field_validator("publisher_reference", "owner_label")
    @classmethod
    def _label(cls, value):
        return _text(value, 160)

    @model_validator(mode="after")
    def _check(self):
        if self.publisher_reference.casefold() == self.owner_label.casefold():
            raise ValueError("Owner must be a separate label")
        expected = _digest(self.model_dump(mode="json", exclude={"hint_id"}))
        if self.hint_id not in (None, expected):
            raise ValueError("Ownership hint identity mismatch")
        object.__setattr__(self, "hint_id", expected)
        return self


def _unique(items, field):
    by_id = {getattr(x, field): x for x in items}
    if len(by_id) != len(items):
        raise ValueError("Duplicate lineage input")
    return tuple(by_id[k] for k in sorted(by_id))


def _reachable(start, adjacency):
    """Return all reachable revision IDs and link IDs; finite even on cycles."""
    visited = set()
    links = set()
    todo = [start]
    while todo:
        current = todo.pop()
        if current in visited:
            continue
        visited.add(current)
        for target, link_id in adjacency.get(current, ()):
            links.add(link_id)
            todo.append(target)
    return visited, links


def _publisher_host(source):
    if source.observation is not None and source.observation.link_type == "google_news_rss":
        return None
    return urlsplit(source.url).hostname


def _publisher_labels(source):
    values = set()
    host = _publisher_host(source)
    if host:
        values.add(host.casefold())
    if source.observation is not None and source.observation.publisher_label:
        values.add(source.observation.publisher_label.casefold())
    return values


def _literal_in(text, excerpt):
    # Exact case-sensitive substring to avoid inventing aliases. Still a
    # lexical anchor, not semantic validation of a declared relationship.
    return bool(excerpt and text in excerpt)


def _graph_input(graph):
    if not isinstance(graph, ClaimEvidenceGraph):
        raise ValueError("Expected typed claim graph")
    try:
        return ClaimEvidenceGraph.model_validate_json(graph.model_dump_json())
    except (ValueError, TypeError):
        raise ValueError("Invalid claim graph") from None


def analyze_source_lineage(graph, *, links=(), ownership_hints=(), extractions=(),
                           ephemeral_bodies=None):
    """Describe candidate dependencies without counting independent witnesses.

    Graph checks are historical structural receipts, not re-authentication.
    Explicit links must be anchored in the dependent source revision and be
    connected to the corresponding claim's origin/evidence. Shared-copy
    evidence is recomputed using V4, never accepted as a naked pair label.
    """
    graph = _graph_input(graph)
    links = _unique(_typed(links, LineageLink, MAX_LINKS), "link_id")
    ownership_hints = _unique(_typed(ownership_hints, OwnershipHint, MAX_OWNERSHIP_HINTS), "hint_id")
    extractions = _typed(extractions, ArticleExtraction, len(graph.sources))
    sources = {s.source_revision_id: s for s in graph.sources}
    anchors = {e.evidence_id: e for e in graph.evidence}
    checks = {c.evidence_id: c.status for c in graph.anchor_checks}
    claims = {c.claim_id: c for c in graph.claims}
    obs_to_source = {s.observation.observation_id: sid for sid, s in sources.items()
                     if s.observation is not None}
    cutoff = datetime.fromisoformat(graph.as_of)
    for receipt in extractions:
        if (receipt.discovery.observation_id not in obs_to_source
                or (receipt.completed_at and datetime.fromisoformat(receipt.completed_at) > cutoff)):
            raise ValueError("Extraction outside graph scope or cutoff")
    duplicate = analyze_news_duplicates(
        [s.observation for s in sources.values() if s.observation is not None],
        extractions=extractions, ephemeral_bodies=ephemeral_bodies,
    )
    duplicate_pairs = {}
    for pair in duplicate["pairs"]:
        key = tuple(sorted(obs_to_source[pair[x]] for x in ("left_observation_id", "right_observation_id")))
        duplicate_pairs[key] = pair

    # Keep origin, support, contradiction and contextual sources separate.
    roles = {cid: defaultdict(set) for cid in claims}
    for cid, claim in claims.items():
        roles[cid][anchors[claim.origin_evidence_id].source_revision_id].add("claim_origin")
    for edge in graph.relations:
        for eid in edge.evidence_ids:
            roles[edge.claim_id][anchors[eid].source_revision_id].add(edge.relation)

    adjacency = defaultdict(lambda: defaultdict(list))
    for link in links:
        if (link.claim_id not in claims or link.dependent_source_id not in sources
                or link.upstream_source_id not in sources):
            raise ValueError("Dangling lineage reference")
        anchor = anchors.get(link.declaration_anchor_id)
        if (anchor is None or anchor.source_revision_id != link.dependent_source_id
                or checks[anchor.evidence_id] == "locator_only"
                or not _literal_in(link.reference_text, anchor.excerpt)):
            raise ValueError("Lineage needs literal declaration in the dependent revision")
        adjacency[link.claim_id][link.dependent_source_id].append((link.upstream_source_id, link.link_id))

    owner_labels = defaultdict(set)
    for hint in ownership_hints:
        source = sources.get(hint.source_revision_id)
        anchor = anchors.get(hint.declaration_anchor_id)
        if (source is None or anchor is None or checks[anchor.evidence_id] != "checked_against_supplied_text"
                or hint.publisher_reference.casefold() not in _publisher_labels(source)
                or not _literal_in(hint.publisher_reference, anchor.excerpt)
                or not _literal_in(hint.owner_label, anchor.excerpt)):
            raise ValueError("Ownership hint needs checked literal publisher and owner references")
        owner_labels[hint.source_revision_id].add(hint.owner_label.casefold())

    # Bound the worst-case output before building pair rows.
    count = sum(len(rs) * (len(rs) - 1) // 2 for rs in roles.values())
    if count > MAX_CLAIM_PAIR_COMPARISONS:
        raise ValueError("Claim lineage pair budget exceeded")

    results = []
    for cid in sorted(claims):
        attached = roles[cid]
        adj = adjacency[cid]
        reachable = {sid: _reachable(sid, adj) for sid in attached}
        all_reached = set().union(*(value[0] for value in reachable.values()))
        if not set(adj).issubset(all_reached):
            raise ValueError("Lineage must connect to the specified claim evidence")
        # A source in a directed cycle cannot establish a unique ultimate origin.
        cyclic = sorted(sid for sid in all_reached
                        if any(sid in _reachable(target, adj)[0] for target, _ in adj.get(sid, ())))
        pair_rows = []
        for a, b in combinations(sorted(attached), 2):
            sa, sb = sources[a], sources[b]
            a_reach, a_links = reachable[a]
            b_reach, b_links = reachable[b]
            common = sorted(a_reach & b_reach)
            signal = []
            if common:
                signal.append("declared_common_lineage")
            if sa.url == sb.url:
                signal.append("same_reported_url")
            ha, hb = _publisher_host(sa), _publisher_host(sb)
            if ha and ha == hb:
                signal.append("same_reported_publisher_host")
            la = sa.observation.publisher_label if sa.observation else None
            lb = sb.observation.publisher_label if sb.observation else None
            if la and lb and la.casefold() == lb.casefold():
                signal.append("same_reported_publisher_label")
            if sa.text_sha256 and sa.text_sha256 == sb.text_sha256:
                signal.append("matching_document_text_digest")
            dp = duplicate_pairs.get((a, b))
            if dp:
                if dp["shared_text_candidate"]:
                    signal.append("v4_substantive_shared_copy_candidate")
                if "matching_extracted_digest" in dp["relations"]:
                    signal.append("v4_matching_extracted_digest")
                if any(r in dp["relations"] for r in ("same_resolved_url", "resolved_reported_url_match")):
                    signal.append("v4_reported_resolved_link_match")
                if any(r in dp["relations"] for r in ("headline_exact_candidate", "headline_near_candidate",
                                                       "canonical_candidate_match")):
                    signal.append("v4_weak_similarity_or_canonical_hint")
            shared_owners = sorted(owner_labels[a] & owner_labels[b])
            if shared_owners:
                signal.append("shared_declared_owner_label")
            if len(owner_labels[a]) > 1 or len(owner_labels[b]) > 1:
                signal.append("conflicting_owner_labels")
            if not signal:
                continue
            pair_rows.append({
                "left_source_id": a, "right_source_id": b,
                "left_roles": sorted(attached[a]), "right_roles": sorted(attached[b]),
                "signals": signal, "shared_upstream_revision_ids": common,
                "reachable_lineage_link_ids": sorted(a_links | b_links) if common else [],
                "shared_owner_labels": shared_owners,
                "duplicate_evidence": dp,
                "source_independence": "unknown",
            })
        # One source revision may appear in several opposing or supporting
        # bundles. Counts are exact revision counts, not independent witnesses.
        support = sorted(s for s, r in attached.items() if "supports" in r)
        contradict = sorted(s for s, r in attached.items() if "contradicts" in r)
        results.append({
            "claim_id": cid,
            "source_roles": [
                {"source_revision_id": s, "roles": sorted(attached[s]),
                 "declared_upstream_revision_ids": sorted(reachable[s][0] - {s}),
                 "reachable_lineage_link_ids": sorted(reachable[s][1]),
                 "declared_owner_labels": sorted(owner_labels[s])}
                for s in sorted(attached)
            ],
            "relation_ids": sorted(e.relation_id for e in graph.relations if e.claim_id == cid),
            "supporting_revision_ids": support, "contradicting_revision_ids": contradict,
            "sources_annotated_on_both_sides": sorted(set(support) & set(contradict)),
            "lineage_cycle_revision_ids": cyclic,
            "pair_comparisons": len(attached) * (len(attached) - 1) // 2,
            "pairs_requiring_dependency_review": pair_rows,
            "independent_supporting_source_count": None, "independent_contradicting_source_count": None,
            "source_independence": "unknown",
        })
    report = {
        "schema_version": 1, "method": _METHOD, "graph_id": graph.graph_id,
        "as_of": graph.as_of, "source_count": len(sources),
        "claim_count": len(claims), "pair_comparisons": count,
        "lineage_links": [x.model_dump(mode="json") for x in links],
        "ownership_hints": [x.model_dump(mode="json") for x in ownership_hints],
        "claim_reviews": results,
        "source_authentication": "not_performed", "semantic_verification": "not_performed",
        "source_independence": "unknown", "network_performed": False, "paid_services_used": False,
        "limitations": [
            "Declared lineage and ownership are caller annotations, not verified relationships.",
            "Same URL, host, owner label, digest or similar headline does not establish dependence or independence.",
            "Shared upstream revision candidates are claim-scoped; cycles and unknown roots are not resolved.",
            "V4 shared-copy candidates are recomputed from supplied receipts; document anchors are historical structural checks.",
            "No pair without a signal is declared independent; no independent corroboration count or truth verdict is produced.",
        ],
    }
    report["report_id"] = _digest(report)
    return report
