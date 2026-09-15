# Revenue Workflow V4-C Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Project constraint:** the approved design forbids introducing subagents/Worker Pool execution into this workflow, so execute inline with `superpowers:executing-plans` and the three dedicated Codexify connectors.

**Goal:** Mature the three V4 workflows with rigorously gated quiescent wakes, compact run-quality telemetry/SLOs, and incident-to-eval candidate capture, while reducing repetitive toil without weakening money pursuit or release safety.

**Architecture:** V4-C sits on production-proven V4-A and V4-B. Quiescence is not a new release reason; it is a mechanically validated `QUEUE_EXHAUSTED` fast path available only after a previous rigorous strategy-exhaustion epoch. `EPOCH_CLOSE` gains compact quality telemetry, and material workflow incidents produce deduped `EVAL_CASE_CANDIDATE` ledger records for later engineering conversion into deterministic tests. Prompt reduction remains deferred until V4-C evals are stable.

**Tech Stack:** Node.js ESM, `node:test`, LOCAL_FILE_V1 JSON state/JSONL ledger, PowerShell, Scheduled Tasks.

**Spec:** `docs/superpowers/specs/2026-09-15-revenue-workflow-v4-design.md`

## Global Constraints

- Start only after V4-B local evals and live branch-learning canaries pass on all three projects.
- Keep `QUEUE_EXHAUSTED` as the release reason; do not add `QUIESCENT_HANDOFF` in V4-C initial rollout.
- Quiescent mode never bypasses fresh money, buyer, or reopen triggers.
- A quiescent fast wake may skip the ordinary current-wake 10-minute/deep-work floor only when durable prior proof satisfies the complete spec gate.
- No sleeping/polling to fill time; quiescent mode exists specifically to eliminate proven toil.
- Reliability SLOs are diagnostic initially, not new release blockers.
- Business metrics remain separate from reliability metrics.
- `EVAL_CASE_CANDIDATE` captures structured incident facts only; it does not auto-modify code/tests/prompts.
- Repeated incident fingerprints dedupe/update rather than append noise.
- Do not reduce scheduler prompts until V4-A/B/C eval coverage is stable and equivalent behavior is proven.
- All behavior changes TDD-first; isolated tests may not mutate production state/ledger.

## File Structure

- Each project's `.revenue-control/control.mjs` - quiescent fast-path validation, close scorecard, incident-candidate dedupe, V4-C version stamps.
- Each project's `.revenue-control/test_control_node.mjs` - quiescent/reopen/scorecard/incident regressions.
- Each project's `.revenue-control/report-quality.mjs` - read-only local ledger quality/SLO aggregator.
- Each project's `.revenue-control/test_report_quality_node.mjs` - synthetic JSONL tests for the reporter.
- Existing `state.json`/`ledger.jsonl` - durable quiescence proof/current summaries and append-only quality/incident records; never bulk rewritten.
- ChatGPT Scheduled Task prompts - compact quiescence/reopen/incident policy, updated sequentially after tests pass.

---

### Task 1: Add quiescent state schema to GodPrompt

**Files:**
- Modify: GodPrompt `.revenue-control/test_control_node.mjs`
- Modify: GodPrompt `.revenue-control/control.mjs`

**Interfaces:**

At the same time bump diagnostic workflow stamps for this stage:

```text
CONTROL_IMPL_VERSION: v4-c.1
WORKFLOW_POLICY_VERSION: v4-c
SCHEDULED_PROMPT_VERSION: gp-rs1-v4c-1
```

```js
QUIESCENT_MODE: false,
QUIESCENT_ESTABLISHED_EPOCH: 0,
QUIESCENT_PROOF_RESULT: '',
QUIESCENT_REOPEN_TRIGGERED: false,
NEXT_USEFUL_AT: 'NONE',
QUIESCENT_REOPEN_CONDITIONS: [],
```

- [ ] **Step 1: Write failing schema tests**

Assert invalid established epoch, malformed future timestamp, empty proof while mode=true, non-array reopen conditions, and same-epoch quiescent establishment are rejected.

- [ ] **Step 2: Prove RED**

Run full test suite.

- [ ] **Step 3: Implement safe defaults/validation**

Legacy states may omit quiescent fields; normal claim defaults `QUIESCENT_REOPEN_TRIGGERED=false` while preserving previously established quiescent proof unless a trigger invalidates it.

- [ ] **Step 4: Prove GREEN**

Run suite.

---

### Task 2: Add deterministic `QUIESCENT_QUEUE_EXHAUSTED` validation branch to GodPrompt

**Files:** GodPrompt `test_control_node.mjs`, `control.mjs`.

**Interfaces:** `QUEUE_EXHAUSTED` may take the quiescent fast branch only when all required durable fields are valid.

- [ ] **Step 1: Write failing positive/negative quiescence tests**

Valid fast-path fixture must contain:

```js
QUIESCENT_MODE: true,
QUIESCENT_ESTABLISHED_EPOCH: currentEpoch - 1,
QUIESCENT_PROOF_RESULT: 'RIGOROUS_FRONTIER_EXHAUSTION_E39',
QUIESCENT_REOPEN_TRIGGERED: false,
SURVIVING_EXECUTABLE_ACTIONS: [],
NEXT_USEFUL_AT: '2026-09-16T08:00:00.000Z',
QUIESCENT_REOPEN_CONDITIONS: ['BUYER_REPLY', 'PAYABILITY_CHANGE'],
```

Also require strategy frontier contains no `OPEN` branch and every `WATCH`/`BLOCKED` item has an explicit reopen condition.

Negative tests:

```text
same-epoch quiescent proof -> reject
OPEN strategy branch -> reject
positive-EV unsaturated executable branch -> reject
reopen triggered -> reject
NEXT_USEFUL_AT already due -> reject unless an explicit checked event condition remains valid
missing proof result -> reject
survivor nonempty -> reject
```

- [ ] **Step 2: Prove RED**

Run tests before implementation.

- [ ] **Step 3: Implement a separate validation path**

In `QUEUE_EXHAUSTED` validation:

```js
if (state.QUIESCENT_MODE === true) {
  validateQuiescentQueueExhausted(state, now);
  return;
}
```

`validateQuiescentQueueExhausted()` must require `SURVIVING_EXECUTABLE_ACTIONS=[]` and current-wake proof that all three permitted reconciliations ran: money, buyer/inbound, and reopen-trigger reconciliation. It deliberately does **not** require the ordinary five-pass final-closure cycle, because the approved spec defines a quiescent wake as only those three bounded reconciliations. The fast path waives ordinary current-wake deep/10-minute/final-closure work only because a prior epoch already established rigorous exhaustion.

- [ ] **Step 4: Prove GREEN**

Run suite.

---

### Task 3: Clear quiescence automatically on fresh trigger

**Files:** GodPrompt tests/control.

**Interfaces:** checkpoint that records money/buyer/reopen trigger must set `QUIESCENT_REOPEN_TRIGGERED=true` and/or clear `QUIESCENT_MODE` before executable work resumes.

- [ ] **Step 1: Write failing tests**

Cover explicit trigger types:

```text
new attributable money evidence
new substantive buyer inbound
branch reopen condition fired
NEXT_USEFUL_AT reached
```

Assert the next planner stage becomes normal `RECONCILE/PLAN`, not fast release.

- [ ] **Step 2: Prove RED**

Run suite.

- [ ] **Step 3: Implement conservative trigger clearing**

The control helper must not infer buyer/money events from prose; it responds only to explicit structured checkpoint fields supplied after external verification.

- [ ] **Step 4: Prove GREEN**

Run suite.

---

### Task 4: Add run-quality scorecard to `EPOCH_CLOSE`

**Files:** GodPrompt tests/control.

**Interfaces:** every new close record stores:

```js
workflow_versions,
elapsed_minutes,
substantive_active_minutes,
tool_failure_count,
retry_count,
unknown_outcome_count,
advancement_units,
information_gain_count,
strategy_branches_opened,
strategy_branches_closed,
strategy_branches_saturated,
duplicate_actions_suppressed,
external_mutations_attempted,
external_mutations_verified,
buyer_signal_count,
money_status,
release_reason,
```

- [ ] **Step 1: Write failing close-record test**

Execute a valid fixture run, read the resulting `EPOCH_CLOSE`, and assert every scorecard field exists with the expected primitive type.

- [ ] **Step 2: Prove RED**

Run test suite.

- [ ] **Step 3: Add compact scorecard derivation**

Derive only from validated state fields and timestamps. For elapsed minutes use claim/close timestamps; do not fabricate active minutes from elapsed time.

- [ ] **Step 4: Add consistency validation**

Examples:

```text
external_mutations_verified <= external_mutations_attempted
retry_count >= 0
unknown_outcome_count >= 0
elapsed_minutes >= 0
substantive_active_minutes >= 0
```

- [ ] **Step 5: Prove GREEN**

Run suite.

---

### Task 5: Add deduped incident-to-eval candidate records

**Files:** GodPrompt tests/control.

**Interfaces:** ledger record:

```js
{
  type: 'EVAL_CASE_CANDIDATE',
  incident_fingerprint,
  observed_bad_behavior,
  expected_invariant,
  minimal_state_fixture_hint,
  severity,
  first_seen_epoch,
}
```

- [ ] **Step 1: Write failing dedupe tests**

Append the same incident twice and assert exactly one durable candidate record. Append a distinct fingerprint and assert a second record appears.

- [ ] **Step 2: Prove RED**

Run tests.

- [ ] **Step 3: Extend `#recordKey()`**

Use stable key:

```js
['EVAL_CASE_CANDIDATE', incident_fingerprint]
```

Do not store transcripts, secrets, credentials, or unnecessary PII.

- [ ] **Step 4: Prove GREEN**

Run suite.

---

### Task 6: Port V4-C to mcp-geo

**Files:** mcp-geo tests/control.

**Interfaces:** use `CONTROL_IMPL_VERSION: v4-c.1`, `WORKFLOW_POLICY_VERSION: v4-c`, `SCHEDULED_PROMPT_VERSION: mcpgeo-rs1-v4c-1` while preserving the existing audit contract.

- [ ] **Step 1: Add all V4-C eval cases RED**

Use mcp-geo strategy/frontier fixtures; verify an audit/buyer/reopen trigger breaks quiescence.

- [ ] **Step 2: Prove RED**

Run suite.

- [ ] **Step 3: Port validated GodPrompt mechanics only**

Preserve no-cold-outreach and exact production scope.

- [ ] **Step 4: Prove GREEN + 10 stress iterations**

Hash production state/ledger before/after and require equality.

---

### Task 7: Port V4-C to TrendPulse

**Files:** TrendPulse tests/control.

**Interfaces:** use `CONTROL_IMPL_VERSION: v4-c.1`, `WORKFLOW_POLICY_VERSION: v4-c`, `SCHEDULED_PROMPT_VERSION: trendpulse-rs1-v4c-1` while preserving all V3 caps/backlog/Gmail constraints.

- [ ] **Step 1: Add all V4-C eval cases RED**

Include explicit test that a newly open V3 buyer-send slot or substantive buyer reply breaks quiescence immediately.

- [ ] **Step 2: Prove RED**

Run suite.

- [ ] **Step 3: Port mechanics without weakening V3**

A future rolling-cap reopen may support `NEXT_USEFUL_AT`; once due, the fast path is invalid until the P90 gate/backlog is reconciled.

- [ ] **Step 4: Prove GREEN + stress**

Run all tests 10 times and verify production hashes unchanged.

---

### Task 8: Add local SLO derivation/reporting without a dashboard dependency

**Files:**
- Create in each local ignored control directory: `.revenue-control/report-quality.mjs`
- Create in each local ignored control directory: `.revenue-control/test_report_quality_node.mjs`
- Test via fixture ledger files; do not mutate state.

**Interfaces:** CLI reads ledger and emits JSON diagnostics:

```json
{
  "clean_release_rate": 1.0,
  "duplicate_external_mutation_rate": 0,
  "unknown_outcome_blind_retry_rate": 0,
  "stale_owner_mutation_rate": 0,
  "split_brain_count": 0,
  "money_signal_rate": 0.0,
  "qualified_buyer_signal_rate": 0.0,
  "advancement_rate": 0.0,
  "information_gain_rate": 0.0,
  "strategy_saturation_rate": 0.0,
  "branch_revisit_suppression_rate": 0.0
}
```

- [ ] **Step 1: Write fixture tests for scorecard aggregation**

Use synthetic JSONL, not production ledger.

- [ ] **Step 2: Prove RED**

Run the reporter test before creating implementation.

- [ ] **Step 3: Implement read-only reporter**

No writes, no network, no scheduler actions. Initial SLO targets are informational:

```text
clean READY/NONE release rate >=99% of claimed completed runs
duplicate externally visible mutation rate = 0
unknown-outcome blind retry rate = 0
stale-owner mutation rate = 0
control split-brain = 0
```

- [ ] **Step 4: Prove GREEN on fixtures then run against production ledger read-only**

Do not turn an SLO miss into automatic control mutation.

---

### Task 9: Update prompts for V4-C quiescence/incident behavior

**Systems:** three production Scheduled Tasks.

- [ ] **Step 1: Bump prompt versions**

Use:

```text
gp-rs1-v4c-1
mcpgeo-rs1-v4c-1
trendpulse-rs1-v4c-1
```

and `WORKFLOW_POLICY_VERSION: v4-c`.

- [ ] **Step 2: Add compact quiescence rule**

Prompt wording must state:

```text
Use quiescent fast path only when control.mjs accepts durable prior saturation proof.
A fresh money/buyer/reopen trigger clears quiescence and resumes normal substantive work.
Do not manufacture work merely to satisfy time after rigorous exhaustion is already established.
```

- [ ] **Step 3: Add incident-candidate rule**

When a genuinely new material workflow failure violates an invariant, append one structured deduped `EVAL_CASE_CANDIDATE`; do not auto-edit code/tests from inside the business run.

- [ ] **Step 4: Read task cards back**

Schedules, deadlines, enabled/paused state, and frozen commercial policies unchanged.

---

### Task 10: Live V4-C quiescent canaries

**Systems:** each production workflow.

- [ ] **Step 1: Establish quiescence only through a rigorous ordinary run**

Do not manually seed `QUIESCENT_MODE=true`. A real run must earn the state after V4-B shows no OPEN/positive-EV branch and all reopen metadata is complete.

- [ ] **Step 2: Run a subsequent no-change wake**

Expected: reconcile money + buyer + reopen triggers, then clean `QUEUE_EXHAUSTED` fast release without fake ten-minute research.

- [ ] **Step 3: Test reopen behavior on the next genuine trigger**

When a real trigger occurs naturally, verify quiescence clears and normal work resumes. Do not fabricate external buyer/payment events merely to test.

- [ ] **Step 4: Confirm scorecard written and status READY/NONE**

Inspect `EPOCH_CLOSE` and local status.

---

### Task 11: V4-C eval campaign and incident corpus

**Files:** existing project test files plus read-only reporter tests.

- [ ] **Step 1: Verify required V4-C eval cases**

At minimum:

```text
rigorous saturation enables quiescence
quiescent no-change wake may finish quickly
fresh buyer/money/reopen trigger clears quiescence
OPEN/executable branch prevents fast path
future NOT_BEFORE preserves branch metadata
scorecard complete and internally consistent
new incident creates one eval candidate
repeated incident dedupes
```

- [ ] **Step 2: Seed engineering regression corpus from known real incidents**

Ensure deterministic tests already cover or add fixtures for:

```text
E39 GodPrompt premature handoff
E57 mcp-geo premature handoff
stale proof contamination
expired owner mutation attempt
concurrent claim race
advancement-bearing queue bypass
duplicate closure families
malformed closure mode
duplicate registry-mirror research
unknown remote side effect
human verification/policy non-bypass
quiescent-with-executable-work regression
```

- [ ] **Step 3: Run complete suites 10 times per project**

Require zero failures and unchanged production state/ledger hashes.

---

### Task 12: Defer prompt reduction until explicit post-V4 review

**Files/Systems:** no runtime mutation in this task.

- [ ] **Step 1: Measure whether V4-A/B/C prompts and control behavior are stable**

Use live run evidence + eval suites + quality reporter.

- [ ] **Step 2: Do not shrink prompts as part of initial V4-C rollout**

The eventual target kernel may contain only root/authority, frozen contract location, control helper location, policy version, safety boundary, terminal date, and output contract, but migration requires a separate design/review proving behavior equivalence.

---

### Task 13: V4 final completion verification

**Files:** all three `.revenue-control` implementations and tests; scheduler readback.

- [ ] **Step 1: Fresh syntax and full test verification**

All three:

```powershell
node --check .revenue-control/control.mjs
node --test .revenue-control/test_control_node.mjs
```

- [ ] **Step 2: Fresh stress verification**

10 iterations/project including concurrent claim race and V4-B/V4-C evals.

- [ ] **Step 3: Verify production controls**

Each ends READY/NONE after its latest completed canary, with no duplicate externally visible mutation and no stale owner.

- [ ] **Step 4: Verify quality reporter**

Read-only metrics parse successfully; no automatic action follows an SLO miss.

- [ ] **Step 5: Verify scheduler cards**

Correct prompt versions, original schedules/deadlines, and user/platform pause state respected.

- [ ] **Step 6: Produce final V4 evidence report**

For each project record: implementation hash, test count, stress count, live-canary epoch/result, branch-learning evidence, quiescent evidence if established, action-unknown reconciliation evidence if exercised, reliability metrics, and remaining external/platform limitations.
