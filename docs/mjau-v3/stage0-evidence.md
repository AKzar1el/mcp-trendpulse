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

### 2026-11-21 extension: two genuine events, four official source records

To avoid a misleading one-event-only proof, the independent God v5 Windows worktree fetched a **second** GitHub/PyPI source pair from the official MCP Python SDK releases. Only public IDs, version names, dates, canonical URLs and SHA-256 hashes were preserved in `tests/fixtures/mjau_v3/mcp_release_pypi_two_events_20261121.json`, not release-note text or package files.

| Event | Original GitHub release | Published UTC | PyPI mcp first upload UTC | Source raw SHA-256 (GitHub / PyPI) |
| --- | --- | --- | --- | --- |
| v2.3.0 | [402184404](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.3.0) | 2026-10-02 22:02:27 | 2026-10-02 22:06:52 | `5eeade981fe66c9963ad88615c42946eb5adaee7c82ecae3f99f7733cc5775c8` / `d9348a2813cdf05df82f7852afb9f13d8a8035d62c3a5e07fb9657bc5382aad7` |
| v2.2.0 | [384197183](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.2.0) | 2026-09-07 15:53:57 | 2026-09-07 16:06:19 | `425b3cd734918055779898f8677e4faa4cacb1573ebdf32ce922645a28491ef5` / `1983ff600264ca5a21d531b282d349c4fac4d3d2b05e1e8592b4e739f013f538` |

The PyPI JSON metadata for both versions explicitly links `project_urls.Repository` to `https://github.com/modelcontextprotocol/python-sdk`. The reviewer manually attested each PyPI distribution to its corresponding GitHub version **event**; the algorithm does NOT derive that relationship from titles/semantic similarity. Distinct v2.2.0 versus v2.3.0 releases must **not** be merged.

**Observed B09 four-record outcome:** two verified original events, two same-event PyPI records, **zero unresolved** (under manual linkage assertions), one original publisher, and two apparent publisher labels before lineage. An unreviewed link abstains and a falsified original URL fails closed. The v1 publisher-count proxy remains **not the actual v1 evaluator**; the four source classes cannot be compared end-to-end without controlled v1-compatible data. These are **two releases**, not two validated buyers or independent demand signals.

**Regression:** `PYTHONPATH=src python -m pytest -q tests/test_mjau_v3_historical.py tests/test_mjau_v3_origin_graph.py tests/test_mjau_v3_origin_snapshot.py` yielded **36/36 passed** on Windows Python 3.13.5; Ruff and compileall passed. The five additional tests use the saved original-source-derived fixture only, with network blocked. Four official free metadata requests, $0 cost, no new dependencies, paid feeds, raw text redistribution or permanent worker.

**Decision remains BLOCKED:** real metadata provenance and distinct-event preservation are demonstrated, but a genuine separately published news/press-release lineage sample, actual v1 comparison and independent reviewer approval are still outstanding. This case alone is insufficient to claim fewer false confirmations in v1 production.

## B08 — official MCP conformance: BLOCKED (separate track)

Reference: https://github.com/modelcontextprotocol/conformance and https://github.com/modelcontextprotocol/inspector .

The official local conformance runner targets an HTTP MCP endpoint using requirements for a specified protocol revision; the current optional TrendPulse server is stdio-based. Requirements for dated 2025-11-25 are not automatically identical to newer draft revisions. The dedicated TrendPulse Codexify tunnel returned "Tunnel-client has not been seen for 300 seconds". **Initial sandbox** had no live Windows access; a later independent God v5 Windows session successfully validated the real stdio MCP and temporary loopback HTTP startup. Nevertheless **no official MCP conformance suite was executed**, because pinned npm and Bun test-only installs timed out. The updated evidence and exact limitations appear in `docs/mjau-v3/connection-and-real-mcp-20261121.md`; do not change shared MCP registration just to satisfy conformance.

**Decision:** BLOCKED, not compliant/passing. Never count an import-only unit test as official MCP acceptance.

## Reproducible test and resource observations

From the feature checkout: PYTHONPATH=src python -m pytest -q tests/test_mjau_v3_historical.py tests/test_mjau_v3_origin_graph.py ; PYTHONPATH=src python -m compileall -q src/mcp_trendpulse/mjau_v3 tests/test_mjau_v3_*.py .

**Local pilot:** Python 3.13.5 on Linux, 31/31 deterministic tests passed in 0.06s. Tests cover positives, negatives, missingness, chronology, duplicate ranks/source IDs, same-event/independent roots, stale/future rows, malformed/private references, credentials, size bounds and human-review uncertainty. This is the **isolated v3 suite only**; full v1 regression and real-MCP tests have NOT been executed.

**Small local performance sample (200 invocations, tracemalloc enabled, no network):**
- A05 with 24 synthetic cases: median 3.154 ms; p95 3.531 ms; peak tracked allocation 51,341 B; JSON output 797 B.
- B09 with two original-source metadata records: median 0.403 ms; p95 0.560 ms; peak tracked allocation 13,800 B; JSON output 838 B.

These are individual **initial offline pilot** measurements, NOT Windows 8-GB production or statistically reliable workload performance guarantees. That initial pilot made zero network calls; the later four-source B09 proof above used four free, bounded official metadata requests. There are no third-party dependencies or copied article bodies/artwork. GitHub/PyPI metadata remains linked, not redistributed wholesale.

**Rollback:** Revert only the isolated commit(s) or remove src/mcp_trendpulse/mjau_v3/, tests/test_mjau_v3_*.py and docs/mjau-v3/ from the feature branch. No runtime migration or production rollback is needed.

**Final release gate:** Stay draft/unmerged. Before acceptance require real audited source/outcome evidence, direct measured v1-versus-v3 utility, real MCP conformance, security/regression/lint review against a stable v1 staging commit and explicit owner approval. If those cannot demonstrate added value, DISCARD rather than merge. A04 and A10 subsequently received independent live-source and source-snapshot proofs in draft PRs #377 and #378, but are not release-accepted. A09 remains LICENSE-BLOCKED; A11 was subsequently REJECTED/DISCARDED by its preregistered real-MCP lexical benchmark. No permission to expand research-only candidates.

## 2026-11-21 real v1 evaluator compatibility check for B09

The initial B09 publisher-count proxy is **not** an end-to-end comparison with v1. To test that limitation directly, the same four source-derived GitHub Release / PyPI version records were converted to honest v1 evidence envelopes with their **actual** `source_id` values (`github_releases` and `pypi_catalog`), then evaluated by the **actual** `intelligence_opportunities.evaluate_opportunities()` function from the pinned v1 staging baseline. The candidate used the existing `research_to_product` lane with source-derived dates, URLs and no claimed buyer.

**Observed v1 result:** **4/4 evidence records rejected** with `Unknown or non-free source`, the evaluated candidate remained `status=insufficient`, its `independent_publishers=0`, and `buying_intent_confirmed=false`. By contrast, the independent B09 lineage audit reports **two distinct release events**, **two same-event distribution records** and one original publisher. These outputs address **different source contracts and questions**: no `precision`, `uplift`, `false-confirmation reduction` or comparative effect size can legitimately be calculated from them. The previous two-publisher count is merely a source-label proxy, **not a v1 baseline score**.

**Verification:** a new deterministic fixture-backed test `test_real_v1_evaluator_rejects_release_metadata_not_supported_by_its_source_contract` exercises both original modules, without network or raw release-note content. Windows Python 3.13.5, with v1 opportunity-evaluator regression included: `PYTHONPATH=src python -m pytest -q tests/test_mjau_v3_historical.py tests/test_mjau_v3_origin_graph.py tests/test_mjau_v3_origin_snapshot.py tests/test_intelligence_opportunities.py` yielded **88/88 passing**, Ruff and compilation checks green.

**B09 decision remains BLOCKED** because the actual v1-supported source pair and independently reviewed original/syndication linkage necessary for meaningful comparison have **not** been acquired. The current release/PyPI source classes would first need separately reviewed source-contract expansion before the origin graph can change v1 opportunity outcomes; do not silently assign them to unrelated v1 `source` values. The latest v1 draft PR #328 remains open; its shared core has advanced beyond the v3 staging pin, so integration must use a single reviewed post-v1 base and explicit owner authorization. No shared evaluator, source manifest, worker or deployment was touched.

## FINAL 2026-11-21 B09 decision — DISCARD, overrides the older BLOCKED status

The additional **source-compatible** `github_issues` comparison required above was completed after pre-registering the pass threshold in commit `9361c2e1156e7834eed80233149ae5a8b44f2309`. Public original issue [#3551](https://github.com/modelcontextprotocol/python-sdk/issues/3551) and explicit duplicate [#3596](https://github.com/modelcontextprotocol/python-sdk/issues/3596), plus distinct [#3100](https://github.com/modelcontextprotocol/python-sdk/issues/3100), produced v1 **2 correct origins, 1 duplicate, no buyer confirmation**. The B09 graph produced the **same** 2/1 and did not autonomously identify an unreviewed duplicate. Extra correct decisions: **0**. The benchmark FAILED the predeclared value gate, so B09 is **REJECTED / REMOVED FROM ACTIVE SCOPE**. Preserve `docs/mjau-v3/b09-last-chance-results.md` and historical test commit `c8b382ce9534637efccdcf85b75ab594f6854680`; remove the experimental `origin_graph.py`, tests and original-only JSON fixtures from this branch. This does not modify working v1 origin deduplication.

The full current 21-candidate pruning policy and two-feature release scope are in `docs/mjau-v3/lean-release-scope-20261121.md`. A05 stays offline research only, A09/B18 deferred, A11 permanently excluded, and the other niche research-only B candidates are removed from active work. B08 remains a real conformance-quality check, not a feature.
