# MJAU v3 PR #382 — three-pass self-review protocol (frozen before this round)

**Date:** 2026-11-22. **Target:** draft PR #382, head `33b8f3f5e7fea27f9a6f8b48117e0bcec6a41d0b`. **Evaluator:** assistant engineering review; no external reviewers. **No new live provider requests** this round: reuse original-source metadata snapshots plus injected fake provider replies. Same user deliberately requested three passes instead of manually rating 14 checklist items. No automatic release, merge or live MCP restart.

## Scoring and decision rule

Each pass has **14 separately documented criteria**, scored **0** (failed/wrong), **1** (correct but unclear, incomplete, or pending additional verification), **2** (complete and demonstrated), or **N/T** (unverified; NOT a pass). A pass earns at most 28 points. For **technical readiness to start supervised, local, opt-in testing**, require:
- Pass 1 **>=24/28** and zero incorrect entity confirmations / false secure-package claims.
- Pass 2 **28/28**, because every item is a security/quotas/transport control.
- Pass 3's **engineering controls >=20 points**, but **independent human review and any unapproved original-source commercial rights remain separate absolute blockers to public/commercial release** regardless of numerical score.
- Record test paths, original-source snapshot links and actual result for every criterion; do not assume code correctness from a prior assistant summary. For any missing data, score N/T and explain why, never inflate denominator.
- The three passes intentionally employ different methods (user-task output comparison; active fault injection; legal policy/source citation and deployment configuration/static review). They are **not** three independent human reviews, legal opinions, peer reviews or experiments measuring commercial adoption.

### Pass 1 — 14 representative actual user goals (source-grounded answer quality)
1. Distinguish exact English names apple fruit Q89 vs Apple Inc. Q312; no auto-merge.
2. Distinguish the same entities in Slovenian source labels; identify locale-specific coverage.
3. Ambiguous English Mercury Q308/Q1150 returns both source candidates, not false identity.
4. Ambiguous German Merkur Q308/Q1150 similarly returns both candidates.
5. Known Q64 Berlin is source-grounded across English/German/Slovenian.
6. Unobserved source Q42 label does not invent a name or claim verified identity.
7. Missing requested QID returns explicitly unknown, never definitive negative.
8. Unseen alias past eight-item projection keeps name search incomplete.
9. Answer a user asking for a name **without** QIDs; determine whether tool directly serves that goal or needs QIDs first (partial usability is not a false safety assertion).
10. OSV source-backed Django==2.2.0 yields original exact ID subset/count and links, not full bodies.
11. OSV source-backed Jinja2==2.10.1 retains original advisory IDs.
12. OSV empty six/react result never claims package secure; explain what it establishes.
13. OSV source-backed lodash==4.17.11 retains six ids and source context.
14. Answer user asking "what should I patch?" from ID-only OSV metadata without hallucinating severities/fixes; evaluate usefulness versus safe abstention.

### Pass 2 — 14 adversarial and runtime controls (active testing)
1. Plan-only MCP does not create cache or network.
2. execute type validation; no silent execution.
3. GET Wikidata restricted to exact HTTPS/path, no injected arbitrary origins.
4. POST OSV restricted to exact HTTPS/path and one-item request plan.
5. Redirect disabled even to HTTPS.
6. 192,000-byte response cap is effective.
7. Invalid MIME, duplicate JSON keys, nonfinite and invalid UTF8 fail closed.
8. 8-second timeout is applied.
9. Persistent Wikidata 8/day cap, no overrun.
10. Persistent OSV 10/day cap, no overrun.
11. HTTP 429 cooldown prevents subsequent source fetch; source not marked clean zero.
12. Eight-way concurrent duplicate calls reserve one request; cached result contains only validated metadata.
13. Cache cannot leak one user's QID/name comparison into another name.
14. The actual two-tool stdio MCP and guarded HTTP example initialize, have no credentials and no prod registration.

### Pass 3 — 14 publisher-rights, attribution and operations controls
1. Wikidata structured labels have direct original CC0 documentation.
2. Every exposed Wikidata QID can be attributed to a source URL.
3. OSV officially documents ID-only querybatch and exact source record semantics.
4. GHSA and PYSEC source rights verified as CC BY 4.0, not a blanket OSV grant.
5. Restricted Chainguard/Wolfi original source rights identified and treated as a blocker for unreviewed commercial bodies.
6. CC BY 4.0 attribution/license/change notices are explicitly present and intelligible to the user.
7. Per-record true original-source provenance is verified, not merely inferred by GHSA/PYSEC prefix.
8. No raw OSV descriptions, severity, exploit contents or original body cached/shared.
9. User-visible 'unknown source'/'no advisory' warnings and no commercial approval claims.
10. Optional MCP is separate, explicitly started, with no default production registration.
11. Budgets, request limits, network controls and rollback are documented and runnable.
12. Branch remains draft/unmerged; GitHub CI checks correspond to exact head.
13. An external human (other than assistant) has signed **independent** unfamiliar-user workflow usability/correctness.
14. Legal/owner reviewer has approved **intended public/commercial source uses**, including all mixed original-feed licenses.

### Evidence and report format

Record `docs/mjau-v3/three-pass-self-review-results-20261122.json` with each item code, 0/1/2/N/T score, evidence field and any blocker; include a readable Markdown review, three separate pass totals and **two distinct verdicts**: supervised private opt-in test vs public/commercial release. Re-run tests and audit newly uncovered gaps conservatively. No user action required for the assistant's three engineering passes; only later optional outside approval can satisfy criteria P3-13/P3-14.
