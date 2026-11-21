# MJAU v3 Stage 0 — isolated evidence ledger

**Status: PILOT ONLY — A05 BLOCKED, B09 BLOCKED, B08 BLOCKED. NO FEATURE ACCEPTED.**

**Canonical instructions:** [MJAU v3 plan](https://github.com/AKzar1el/mcp-trendpulse/blob/research/mjau-v2-plan-20261121/.planning/mjau-v3-plan.md) (read-only). Companion v2 plan and all shared code remain untouched.

**Pinned v1 staging ancestor:** b88b0a974b5dcdb480e4fd8c4da5f7bbca68e98e (draft PR #328, branch feat/free-intelligence-8-lanes-20261118). The current v1 M14 shared integration is not complete. This pilot is explicitly not based on main.

**Isolated commits:** 352c285c967c4fab4c2f297f78d6b4de7c33046e (A05) and 281832d86e7a1e7b6ade7d6bfcd58cb4afda1026 (B09). Only new v3 Python modules, matching tests, and this ledger are changed. No dependency manifest, shared CLI/MCP registration, credentials, cache, scheduler, release, or permanent worker has been modified.

## A05 — historical baseline: BLOCKED

**Decision question:** Can independent historical source records establish any improvement over v1 in precision@K, false-positive rate, abstention, source traceability or citation correctness?

**Observed v1 baseline:** src/mcp_trendpulse/intelligence_backtest.py handles user-attested commercial outcome labels, needs at least 8 verified outcomes from multiple cutoffs, and explicitly does not claim independent labels, calibration or predictive ability. V1 M14 remains unchecked.

**Implemented offline experiment:** mjau_v3.historical.evaluate_historical_replay accepts at most 40 cases / 160 KB, validates source-observed and source-published dates as known at the cutoff, independently attested outcome labels with known-after / verified-at chronology, public HTTPS citation references without secret query fields, and unique model rankings per historical fold. It tracks unknown/unreviewed labels separately from negative outcomes. Comparisons require 20 comparable independent-reviewed cases, at least two folds, five positives/five negatives, and a single label kind. Otherwise all metrics are withheld. With valid inputs it reports separate per-model descriptive precision@K, false positives, abstention and citation-correct fractions; it never claims forecast accuracy.

**Observed empirical dataset:** 0 out of 20 independently adjudicated historical outcome cases are presently available in this pilot. The 24-case *synthetic* positive/negative matrix is a software test, not real-world predictive evidence. No measured historical uplift is asserted.

**Decision:** BLOCKED pending real reviewed historical labels and an end-to-end v1 comparison on matching saved inputs. Do not integrate.

## B09 — reviewed origin/syndication falsification: BLOCKED

**Decision question:** Can separately published records actually share one underlying origin, so v1's publisher count overstates independent confirmation?

**V1 overlap and gap:** src/mcp_trendpulse/intelligence_opportunities.py already deduplicates exact origin IDs and canonicalized URLs before counting publisher labels. New cross-domain lineage would be additive only if it proves a meaningful benefit beyond those existing protections.

**Real-source *metadata* sample, not demand data:** GitHub release modelcontextprotocol/python-sdk v2.3.0, GitHub release ID 402184404, issued on 2026-10-02; and the PyPI distribution record mcp 2.3.0, also issued 2026-10-02. Sources: https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.3.0 and https://pypi.org/project/mcp/2.3.0/ . These are two public distribution records for one version event, NOT verified article syndication, independent adoption, customers, or revenue.

**Measured limited comparison:** Two publisher labels in an approximate v1-style *proxy*, one explicitly linked original event in the offline review graph, one dependent/same-event record. This is NOT an end-to-end result of the actual v1 opportunity evaluator: the two sample sources are not modeled as normal v1 opportunity source classes. The origin relation is reviewer-asserted and can be wrong. Do not quote this proxy as measured v1 uplift.

**Implemented offline experiment:** mjau_v3.origin_graph.audit_origin_evidence accepts max 120 records / 180 KB. It requires public HTTPS original + lineage references, restricts meaningful query normalization, rejects contradictory record IDs and future dates, excludes unreviewed roots, marks conflicting original publisher claims unresolved, and abstains on ambiguous lineage instead of auto-merging name matches. No network or model inference.

**Decision:** BLOCKED until independently reviewed true article/source lineage with original IDs and a v1-compatible end-to-end comparison shows fewer false confirmations without losing genuinely independent observations. This illustrative two-record release pair alone is insufficient for acceptance.

## B08 — official MCP conformance: BLOCKED (separate track)

Reference: https://github.com/modelcontextprotocol/conformance and https://github.com/modelcontextprotocol/inspector .

The official local conformance runner targets an HTTP MCP endpoint using requirements for a specified protocol revision; the current optional TrendPulse server is stdio-based. Requirements for dated 2025-11-25 are not automatically identical to newer draft revisions. The dedicated TrendPulse Codexify tunnel returned "Tunnel-client has not been seen for 300 seconds". This sandbox cannot install official packages from upstream or access the actual service. **No real official MCP suite result was obtained.** An isolated test-only HTTP adapter and live process are required; do not change shared MCP registration just to satisfy conformance.

**Decision:** BLOCKED, not compliant/passing. Never count an import-only unit test as official MCP acceptance.

## Reproducible test and resource observations

From the feature checkout: PYTHONPATH=src python -m pytest -q tests/test_mjau_v3_historical.py tests/test_mjau_v3_origin_graph.py ; PYTHONPATH=src python -m compileall -q src/mcp_trendpulse/mjau_v3 tests/test_mjau_v3_*.py .

**Local pilot:** Python 3.13.5 on Linux, 31/31 deterministic tests passed in 0.06s. Tests cover positives, negatives, missingness, chronology, duplicate ranks/source IDs, same-event/independent roots, stale/future rows, malformed/private references, credentials, size bounds and human-review uncertainty. This is the **isolated v3 suite only**; full v1 regression and real-MCP tests have NOT been executed.

**Small local performance sample (200 invocations, tracemalloc enabled, no network):**
- A05 with 24 synthetic cases: median 3.154 ms; p95 3.531 ms; peak tracked allocation 51,341 B; JSON output 797 B.
- B09 with two original-source metadata records: median 0.403 ms; p95 0.560 ms; peak tracked allocation 13,800 B; JSON output 838 B.

These are individual local measurements, NOT Windows 8-GB production or statistically reliable workload performance guarantees. This proof made zero network calls and incurred zero provider/API cost. There are no third-party dependencies or copied article bodies/artwork. GitHub/PyPI metadata remains linked, not redistributed wholesale.

**Rollback:** Revert only the isolated commit(s) or remove src/mcp_trendpulse/mjau_v3/, tests/test_mjau_v3_*.py and docs/mjau-v3/ from the feature branch. No runtime migration or production rollback is needed.

**Final release gate:** Stay draft/unmerged. Before acceptance require real audited source/outcome evidence, direct measured v1-versus-v3 utility, real MCP conformance, security/regression/lint review against a stable v1 staging commit and explicit owner approval. If those cannot demonstrate added value, DISCARD rather than merge. A04, A10, A09 and A11 remain unstarted in this Stage 0 checkpoint; no permission to expand research-only candidates.
