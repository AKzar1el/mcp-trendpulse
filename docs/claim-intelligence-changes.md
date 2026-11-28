V5.06 — correction, retraction and revision traceability

Internal offline API: track_source_changes(graph, as_of=..., changes=(), previous_assessment=None). Supported caller-declared events: correction, retraction, withdrawal, replacement, clarification and archive snapshot. Each event links an exact prior source revision to an optional successor and a separate notice source revision/evidence anchor. Notice must be a captured primary/secondary document span checked against a supplied exact representation and must literally contain its notice wording and exact target/successor locator strings. Claim IDs must actually reference the target revision in the graph. All inputs bounded; cycles rejected; deterministic ordered ledger and report fingerprint.

Old and successor source revisions remain immutable and visible. A change notice never silently edits original claims, relation bundles, assessment results or prior reports. If a supplied prior assessment predates the declared notice, affected claims are flagged for reassessment; if its timestamp is later or equal, inclusion of the notice is not assumed. Reassessment is a separate explicit operation against a new graph revision. The output says the notice was caller-declared and its span checked; it does not authenticate the publisher, interpret correction semantics, decide truth, fetch archives or claim that a change is justified. A retraction is not itself proof that every assertion in the source was false.

Google ClaimReview literal archivedAt/correction/appearance references from V5.04 remain candidate links only; they can be imported by a user and then included as exact graph sources/notices after independent rights and content checks. No automated URL crawling or archive fetch. Dataset/source retention permissions remain caller responsibility.

V5.05 assessment report fingerprint and exact graph ID are checked before linking prior statuses. Historical report is not altered. reassessment_required only records that the prior assessment predates a declared change notice; it is not a retraction verdict. No automatic evidence edges/status change. No network, model, new dependency, persistent database, registry or production changes.

Evaluation: synthetic tests cover corrections, retractions, withdrawal, replacement, clarification, archive snapshots, checked notice spans, exact target/replacement references, affected claim linkage, future notices, cycles, immutable prior assessment and deterministic replay. Not a benchmark of publisher correction detection or semantic validity. Live correction/archive discovery and independently labeled temporal change evaluation remain release gates.

References: W3C PROV-O https://www.w3.org/TR/prov-o/ ; Schema.org ClaimReview https://schema.org/ClaimReview ; FEVER https://fever.ai/2018/task.html .

Next: V5.07 integrated evidence investigation and report assembly.


A prior assessment is bound to its own earlier graph revision. V5.06 checks the assessment report fingerprint and carries its statuses forward only for claim IDs that still exist in the newer graph; graph fingerprints are expected to differ after added correction/successor sources. Claims absent from the older assessment do not receive invented prior statuses.
