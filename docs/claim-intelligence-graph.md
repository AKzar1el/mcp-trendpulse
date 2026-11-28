# V5.01: claim/evidence graph contract

Internal, experimental offline API in `claim_intelligence_graph.py`. No automatic extraction, fact verdict, publisher authentication, source-independence inference, model sampling, MCP registry change, network request, paid dependency or body persistence.

## Contract

- **SourceRevision:** exact immutable V4 NewsArticle observation (headline only, source kind unknown), or caller-described document revision with public citation URL, title, explicit revision label, capture time when known and caller-declared source kind (primary document, secondary reporting, opinion or unknown). A primary document is not necessarily truthful. Optional retention policy and SHA-256 bind an exact supplied UTF-8 text representation, not an original downloaded file.
- **EvidenceAnchor:** source revision, exact headline span, permitted document span, or unresolved page/section locator. Offsets are zero-based Unicode code points, end exclusive. Headline anchors match existing headline text. Permitted document spans require the matching complete ephemeral representation and span digest. Excerpt retention additionally requires explicit permission; hash-only inputs never return document text. Locator-only evidence never claims verified text. Caller establishes rights; no raw bodies persisted.
- **AtomicClaim:** caller-annotated subject, predicate, object, polarity, modality (including allegation, quote, projection, opinion and question), attribution, explicit asserted date/precision, scoped geography/calendar period/qualifiers and origin anchor. Unknown stays unknown; never substitute publication/capture for assertion date. Exact proposition fingerprint excludes the speaker and origin; claim fingerprint preserves the separate attributed occurrence. No claim of semantic atomicity, identity resolution or paraphrase equivalence.
- **EvidenceRelation:** one claim, one to five jointly annotated evidence anchors, supports/contradicts/context/insufficient, scope alignment and rationale. Supports/contradicts are **caller labels**, not truth outcomes. They require declared matching scope and checked document spans from primary or secondary material, not headlines/opinion/unknown-source/locator-only evidence or the exact origin anchor. Questions, opinions and unknown polarity are not automatically checkable. Conflicting edges coexist; no verdict or independent-source count is calculated.
- **ClaimEvidenceGraph:** validates bounded typed records, unique IDs, all references, anchor/check consistency, explicit cutoff and deterministic ordering; graph fingerprint covers the complete output. Up to 80 sources and claims, 160 anchors, 240 relations, eight ephemeral documents (256 KiB each, 1 MiB total), 512-character spans. Document-check receipts verify supplied bytes and offsets at build time; serialized graph revalidation checks structure and IDs, not historical source authenticity. Unknown source dates remain unknown; declared assertion calendar days after the UTC cutoff day are rejected conservatively.

## V4 integration

`source_from_observation(row)` converts a typed V4 NewsArticle without altering the original observation. In a V4 investigation result, `all_sample_and_context.event_report.observations` contains these records. Deserialize each with `NewsArticle.model_validate_json` and pass to the adapter. Preserve the separate investigation source scopes; the graph does not infer topical relevance from context.

`build_claim_graph(as_of=..., sources=..., evidence=..., claims=..., relations=..., document_texts=...)` checks document anchors using the optional in-memory mapping of source revision ID to explicitly permitted exact text. It returns an immutable typed graph. Building a source-only graph is valid, without inventing claims. Source text is untrusted data, never executed or used to dispatch actions.

## Evaluation plan (not benchmark results)

1. Synthetic regressions for relation scope, exact anchors/offsets, changed revisions, unsupported sources, competing relations, untrusted metadata, rights policy, unknown dates, dangling IDs, bounds and V4 adapter.
2. Independently labeled, held-out corpus with claim decompositions, attribution, evidence sets, modality, temporal scope, and challenging negative examples. Keep labeled sources and revisions frozen; separate development and evaluation data by event/source family to reduce leakage.
3. Measure claim extraction precision/recall, exact source-anchor accuracy, complete evidence-set recall, relation-label macro-F1, per-class abstention, false-support/false-contradiction rates and disagreement. Include conflicting evidence, quotations/projections, repeated stories, multilingual variants and prompt-injection text. Record sampling, missing sources and annotator disagreements. No aggregate commercial quality claim from synthetic fixtures.
4. FEVER supplies an established evidence-set evaluation pattern, not a representative live-news benchmark. W3C PROV-O supplies provenance concepts; Schema.org ClaimReview separates claim from review. No claim of formal standards compliance or fact-check certification.

References: https://www.w3.org/TR/prov-o/ ; https://schema.org/ClaimReview ; https://fever.ai/2018/task.html ; https://aclanthology.org/N18-1074/ .

Next: V5.02 conservative claim extraction; V5.03 source independence and lineage; V5.04 primary-record search; V5.05 evidence assessment. Real-world labeled evaluation and the earlier V4 live gates remain open.
