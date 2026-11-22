# B09 last usefulness gate — preregistration before paired scoring (2026-11-21)

**One trial, then stop.** User instruction: no more low-value origin-graph engineering; if it does not beat v1 on an honest paired task, **remove B09 from the active release** and preserve this experiment only as archival evidence.

## Original-source test input (both are already v1-compatible)

Real public issue records in `modelcontextprotocol/python-sdk`, fetched through the connected GitHub read API on 2026-11-21:

- **Original:** [#3551](https://github.com/modelcontextprotocol/python-sdk/issues/3551) reported **2026-09-20**: stdio server Ctrl+C/hung stdin worker.
- **Explicit duplicate:** [#3596](https://github.com/modelcontextprotocol/python-sdk/issues/3596), reported **2026-09-29**, closed the same day. The public body begins: **"Duplicate of #3551, which reports the same blocked stdin worker thread and predates this. Closing in favour of that issue."**
- **Distinct negative control:** [#3100](https://github.com/modelcontextprotocol/python-sdk/issues/3100), reported **2026-07-16**, Pydantic structured output/schema mismatch. It is not the stdin-worker issue, nor a duplicate of it.

These are all **`github_issues`**, an existing v1 accepted source. Their dates/URLs/explicit duplicate relation are source-backed, not speculative third-party news syndication. Do **not** infer independent customers, budget, exploitable vulnerabilities or product demand from these issues. For comparable source-observation cutoffs, set `observed_at=2026-11-21` (when inspected), `as_of=2026-11-21` and `published_at` to the original issue date, not the linked closure date. This test audits **deduplication semantics**, not hindsight forecasting.

## Frozen paired scoring protocol

1. **Actual v1 evaluator** `evaluate_opportunities()`: use its real `developer_reliability` lane, `github_issues` source, one named narrow incident-triage workflow, three genuine issue URL/ID/date references, one public repository publisher and no inferred paid buyer; each evidence item has a stable caller-provided `origin_id` that groups the independently verified #3596 duplicate with #3551 and leaves #3100 distinct. No relabeling as a fake source or invented buyers.
2. **B09 origin graph** `audit_origin_evidence()`: feed the same three source IDs, URLs, dates, known original/duplicate relationship, distinct #3100 root. `reviewed_origin=True` is only a *local source-audit assertion* based on #3596's explicit original-reference text; it does not independently validate unrelated articles.
3. **Adversarial unreviewed control:** remove the review assertion for the duplicate. B09 must abstain, never assert independence. Both paths must keep #3100 distinct.
4. **Measured correctness:** count false independent origins, missed true distinct origins, false merges, unreviewed abstentions, changes to evaluator priority/status, data/network cost, and whether B09 actually yields a new validated decision that v1 cannot make.

## Before-seeing-results pass/fail decision

**KEEP B09 for release only if** it fixes **at least one** wrong independently source-grounded v1 origin/conclusion on these inputs **without extra paid data or stronger manual provenance than the baseline**, preserves both distinct original issues and does not falsely confirm buying intent. A mere separate `verified_original_event_count` field, an interesting graph, extra source wrappers, or relying on *additional* human review unavailable to v1 **does not count as improvement**.

**Otherwise: CUT/DISCARD from the active v3 release**, record actual numbers and preserve only this frozen research artifact/test evidence (not integrated source code/MCP tool). This is a representative single narrow case, not proof the graph can never help a larger future corpus. A new B09 proposal would require fresh user authorization and new independent data, not ongoing work by default.

**Safety:** offline only, no network during replay, no mutable shared v1 state, no dependency/CI/registration edits, no original issue bodies copied to fixtures.
