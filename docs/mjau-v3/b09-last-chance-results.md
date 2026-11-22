# B09 real v1-compatible paired utility trial — REJECTED / REMOVE FROM RELEASE

**Decision (21 November 2026): DISCARDED FROM ACTIVE MJAU v3 RELEASE.**

The preregistered threshold was recorded **before scoring** in `docs/mjau-v3/b09-last-chance-preregistered.md` (committed `9361c2e1156e7834eed80233149ae5a8b44f2309`). Because it delivered no additional correct user decision versus v1 on identical genuine provenance, **B09 is not worth the extra code/tool count and review costs.** Do not resurrect the separate origin-graph implementation as a production tool without an explicit new scope decision and new independent value proof.

## Real public-source data

- [modelcontextprotocol/python-sdk#3551](https://github.com/modelcontextprotocol/python-sdk/issues/3551): first reported 2026-09-20, stdin worker/stdio shutdown issue.
- [modelcontextprotocol/python-sdk#3596](https://github.com/modelcontextprotocol/python-sdk/issues/3596): reported 2026-09-29, explicitly starts **"Duplicate of #3551"**, and closes in favor of #3551.
- [modelcontextprotocol/python-sdk#3100](https://github.com/modelcontextprotocol/python-sdk/issues/3100): reported 2026-07-16, independent Pydantic schema/serialization issue, not the stdin-worker event.

All three are exact original GitHub issue URLs with `source=github_issues`, an accepted real v1 source. No author data, long issue bodies, press-release copies or paid API data retained. Observed 2026-11-21, so the test is a current source replay, **not** historically as-of-safe forecasting.

## Frozen A/B result

| Predeclared measure | Actual v1 `evaluate_opportunities` | B09 `audit_origin_evidence` |
| --- | --- | --- |
| Valid source records accepted | 3/3; rejected 0 | 3/3 |
| Actual distinct origins | 2 | 2 |
| Explicit dependent duplicate observations | 1, `ignored_reasons.duplicate_origin` | 1, `dependent_or_same_event_records` |
| Independent source publisher count | 1 | 1 |
| Incorrect independent confirmations | 0 | 0 |
| Additional correct origins/corrections over v1 | baseline | **0** |
| Candidate buyer intent | Not confirmed | Not inferred |
| Human origin review | Caller supplies stable `origin_id` using public duplicate citation | Caller sets `reviewed_origin=true` using that same citation |
| Without human-reviewed duplication relationship | Naive unique origin IDs would over-count (3) | **Abstains** on the duplicate rather than proving linkage; does not infer it |

Actual v1 outcome: `status=monitor`, `supporting_origins=2`, `independent_publishers=1`, `buying_intent_confirmed=false`. The B09 graph adds a distinct report object, **not** a better decision, source-independent provenance inference, or a reduction in false confirmations under the same supplied information. Using an extra human assertion to repair bad v1 `origin_id` inputs is not the prespecified incremental utility; the same assertion can correct the v1 inputs directly.

An isolated direct Python execution of the original comparison and graph exited **0** with `B09_V1_CORRECT_DISTINCT_ORIGINS 2`, `B09_GRAPH_VERIFIED_ORIGINS 2`, `B09_GRAPH_NEW_CORRECT_ORIGIN_COUNT 0` and `B09_PREREG_PASS_THRESHOLD_NOT_MET=True`. All **4 new focused assertions** also reported PASS under pytest before a test-runner shutdown stall on the Windows host; because that subprocess was interrupted, no clean pytest-suite exit is claimed for that run. Ruff and compileall on the test file passed. The direct independent replay is the authoritative successful subprocess for this test.

## Cleanup and limits

B09's existing `origin_graph.py` pilot and its tests/fixtures shall be **removed from the currently active Stage0 draft branch**, but the prior git revision containing this source-backed experiment is retained as an archived Git commit and linked in the ledger. No v1 `intelligence_opportunities` code or source catalog is modified. Even though this test cannot rule out future specialized syndication use cases, **this candidate failed its one approved usefulness chance and is permanently excluded from the MJAU v3 release scope** absent new user direction.

**Resource/cost:** all scoring offline, zero external test calls after fetching original source records through the connected public GitHub API; no new installed library, cache, daemon, user configuration, worker or production state. Rollback of the pilot is an isolated Stage0-branch code/test deletion, not a production rollback.
