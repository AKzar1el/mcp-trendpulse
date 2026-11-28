# V5.05 — claim evidence assessment

Internal experimental offline API: `assess_claim_evidence(graph, as_of=..., policies=(), lineage_report=None)`. Consumes a typed V5.01 ClaimEvidenceGraph and optional structurally fingerprinted V5.03 lineage report. It never retrieves sources, invokes a model, authenticates publisher or human review, or asserts ground truth. It reports the direction of explicit caller-annotated evidence relations.

## Status contract

- **supported:** at least one graph edge explicitly labels checked, permitted primary/secondary document spans as supporting, with declared matching scope, and no opposing direction. This means the *evidence annotation* supports the proposition, not that the proposition has been independently verified.
- **contradicted:** analogous caller-labelled contradiction and no supporting direction.
- **disputed:** both supporting and contradicting evidence directions exist. Preserve both; no majority vote or net score.
- **unverified:** context/insufficient evidence only, stale/currentness downgrade, missing required scope or missing specific-period scope.
- **unknown:** no evidence relations.
- **independently_corroborated:** reserved but never assigned by automation. V5.03 cannot prove independence; no-pair-found is not an independence result.

## Time, scope and evidence

`AssessmentPolicy` explicitly declares stable/current/specific_period/unknown claim relevance. Current requires caller-set maximum age (0–36,500 days); compares only exact source capture/retrieval time to assessment cutoff. Unknown capture is unknown, never fresh. Stable claims get no invented decay window and freshness remains not_assessed, not implicitly fresh. The upstream V5.01 graph already rejects support/contradiction annotations whose checked document capture time is unknown. Claim's own temporal/geographic/qualifier scope is preserved. Requiring explicit scope or a specific period without scope downgrades a one-sided status to unverified. Relation scope alignment is still a caller declaration, not semantic evaluation.

Per-source details preserve revision IDs, source kind (primary/secondary/opinion/unknown), capture time and distinct reported publication/provider-seen times; do not conflate them. Directional evidence source revisions and original relation bundles are separate. A multi-source joint bundle is one annotation, not N independent witnesses. The report exposes dependency-review pair counts if a matching V5.03 lineage receipt exists, but never upgrades independence; all independent counts remain null. Source-kind counts are not source-quality scores. Original ClaimReview ratings are deliberately absent.

No numeric probability, overall confidence score, universal publisher trust ranking, model confidence, truth verdict or automatic evidence relation is produced. The report fingerprint covers all output. Bounds inherit the V5.01 graph and V5.03 report caps. This assessment is reproducible only for the supplied graph and caller annotations; document authenticity, review receipts and semantic correctness are not re-authenticated.

## Evaluation and design references

Synthetic tests cover one-sided and opposing evidence, same source on both sides, context-only, stale/missing timestamps, explicit scope, unknown independence, future cutoffs and deterministic replay. This is a contract test suite, not a benchmark of claim truth or calibrated human agreement. Future held-out evaluation must separately measure evidence-set citation faithfulness, scope alignment, freshness, false support/contradiction, disputed detection, abstention, calibration and expert disagreement.

Research supports separating claim-level source traceability, evidence strength, uncertainty and contextual scope rather than relying on source reputation or fluent verdicts:
- https://aclanthology.org/2025.findings-emnlp.1170/
- https://pmc.ncbi.nlm.nih.gov/articles/PMC13771472/
- https://pmc.ncbi.nlm.nih.gov/articles/PMC12890942/
- https://journals.sagepub.com/doi/full/10.1177/02673231251319145
- https://www.w3.org/TR/prov-o/

Next: V5.06 corrections/retractions and assessment revision history, then V5.07 integrated evidence investigation. Real-world evaluation and all previous V4/V5 live-source gates remain open.
