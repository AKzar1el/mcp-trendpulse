# Revenue Workflow V4-B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Project constraint:** the approved design forbids introducing subagents/Worker Pool execution into this workflow, so execute inline with `superpowers:executing-plans` and the three dedicated Codexify connectors.

**Goal:** Add durable commercial strategy learning and professional backtracking to all three Revenue Shots so repeated negative evidence suppresses weak branches, positive buyer/money evidence attracts more effort, genuinely different unexplored branches still receive bounded exploration, and dead strategies reopen only on explicit triggers.

**Architecture:** Build on production-proven V4-A. Keep `STRATEGY_FRONTIER` compact in each project's local `state.json` and detailed branch evidence in append-only ledger records. Deterministic pure helpers validate branches, score them, compact the hot frontier, and calculate parent updates; the model still chooses/executes commercial work under each project's frozen contract, but cannot masquerade `ADVANCEMENT_UNITS` as business reward or use score to override caps/safety/NOT_BEFORE.

**Tech Stack:** Node.js ESM, `node:test`, LOCAL_FILE_V1 state/JSONL ledger, PowerShell, ChatGPT Scheduled Tasks.

**Spec:** `docs/superpowers/specs/2026-09-15-revenue-workflow-v4-design.md`

## Global Constraints

- V4-B starts only after V4-A passes local regression/stress suites and one live canary per project.
- Keep each project isolated; no shared writable strategy store.
- `STRATEGY_FRONTIER` hot state max: 12 active/top-ranked branches.
- Allowed branch status: `OPEN`, `WATCH`, `BLOCKED`, `INVALIDATED`, `SATURATED`, `DONE`.
- Score inputs are integer ordinals `0..3`: `money_proximity`, `evidence_strength`, `trigger_freshness`, `information_gain_remaining`, `execution_cost`, `risk`.
- Deterministic score: `4*money_proximity + 3*evidence_strength + 2*trigger_freshness + 2*information_gain_remaining + exploration_bonus - 2*execution_cost - 3*risk`.
- `exploration_bonus` is `0..2`; it must never override hard contract/safety/capability/send/NOT_BEFORE gates.
- `ADVANCEMENT_UNITS` remains release/work proof only and MUST NOT feed business score.
- Business-signal ladder remains: attributable money > buyer purchase/request > substantive qualified buyer reply > verified conversion/payment transition > verified qualified distribution/exposure transition > information gain.
- No chain-of-thought in state/ledger; persist only structured evidence/result codes/decision metadata.
- Do not keep invalidated/saturated/done history in hot frontier unless a reopen trigger fires; ledger retains history.
- Same-family variants do not count as independent diversification solely because URLs/names differ.
- All behavior changes TDD-first and production state/ledger hashes must remain unchanged under fixtures.
- V4-B diagnostic versions are `CONTROL_IMPL_VERSION: v4-b.1` and `WORKFLOW_POLICY_VERSION: v4-b`; project prompt versions are `gp-rs1-v4b-1`, `mcpgeo-rs1-v4b-1`, and `trendpulse-rs1-v4b-1`.

## File Structure

- Each project's `.revenue-control/control.mjs` - pure strategy validation/scoring/learning/reopen/compaction helpers plus bounded hot-frontier state validation.
- Each project's `.revenue-control/test_control_node.mjs` - project-specific strategy-tree eval fixtures and hard-gate regressions.
- Each project's existing `state.json` - compact current `STRATEGY_FRONTIER` only, initialized naturally through owned claim/checkpoint flow.
- Each project's existing `ledger.jsonl` - append-only structured strategy events; no historical rewrite.
- ChatGPT Scheduled Task prompts - project-specific branch families and operator loop, updated sequentially after local mechanics pass.

---

### Task 1: Add branch schema and validation to GodPrompt

**Files:**
- Modify: `C:\Users\Tomi\Desktop\lol\godprompt-suite\.revenue-control\test_control_node.mjs`
- Modify: `C:\Users\Tomi\Desktop\lol\godprompt-suite\.revenue-control\control.mjs`

**Interfaces:**
- Produces `STRATEGY_FRONTIER: StrategyBranch[]`.
- Bumps GodPrompt diagnostic stamps to `CONTROL_IMPL_VERSION: v4-b.1`, `WORKFLOW_POLICY_VERSION: v4-b`, `SCHEDULED_PROMPT_VERSION: gp-rs1-v4b-1` on the first V4-B claim.
- `StrategyBranch` keys:

```js
{
  branch_id,
  parent_branch_id,
  family,
  hypothesis,
  status,
  attempt_count,
  positive_evidence_count,
  negative_evidence_count,
  last_result_code,
  last_tested_epoch,
  money_proximity,
  evidence_strength,
  trigger_freshness,
  information_gain_remaining,
  execution_cost,
  risk,
  expected_value_band,
  reopen_condition,
  not_before,
}
```

- [ ] **Step 1: Write failing schema tests**

Add a valid branch fixture and assert malformed status, duplicate `branch_id`, ordinal outside `0..3`, missing `family`, or malformed `not_before` is rejected.

```js
const branch = {
  branch_id: 'distribution:findmcp',
  parent_branch_id: 'distribution',
  family: 'PASSIVE_MCP_DIRECTORIES',
  hypothesis: 'A distinct directory creates qualified discovery',
  status: 'OPEN',
  attempt_count: 0,
  positive_evidence_count: 0,
  negative_evidence_count: 0,
  last_result_code: 'UNTESTED',
  last_tested_epoch: 0,
  money_proximity: 1,
  evidence_strength: 1,
  trigger_freshness: 3,
  information_gain_remaining: 3,
  execution_cost: 1,
  risk: 0,
  expected_value_band: 'MEDIUM',
  reopen_condition: '',
  not_before: 'NONE',
};
```

- [ ] **Step 2: Prove RED**

Run the full test file and require the new schema tests fail before implementation.

- [ ] **Step 3: Implement pure `validateStrategyFrontier()`**

Export the helper for tests; require array length <=12 for hot state, unique branch IDs, valid parent IDs when parent is present in hot state, and documented enums/ordinals.

At the same time update the V4 diagnostic constants from V4-A to V4-B; these remain metadata only and do not grant authority.

- [ ] **Step 4: Wire validation into state/checkpoint**

Legacy state may omit `STRATEGY_FRONTIER`; claim defaults it to `[]`. Any checkpoint containing the field must pass validation before state write.

- [ ] **Step 5: Prove GREEN**

Run all GodPrompt tests.

---

### Task 2: Add deterministic branch scoring to GodPrompt

**Files:** GodPrompt `test_control_node.mjs`, `control.mjs`.

**Interfaces:**
- Export `scoreStrategyBranch(branch, { explorationBonus }) -> number`.
- Export `rankStrategyFrontier(frontier, { now }) -> StrategyBranch[]`.

- [ ] **Step 1: Write failing scoring tests**

```js
assert.equal(scoreStrategyBranch({
  money_proximity: 3,
  evidence_strength: 3,
  trigger_freshness: 2,
  information_gain_remaining: 1,
  execution_cost: 1,
  risk: 0,
}, { explorationBonus: 0 }), 25);
```

Add tests that a high-money branch beats generic research, an untested different-family branch can gain at most +2 exploration, and `ADVANCEMENT_UNITS` is ignored even if supplied in the object.

- [ ] **Step 2: Prove RED**

Run tests before implementation.

- [ ] **Step 3: Implement score exactly as spec**

```js
return 4 * mp + 3 * evidence + 2 * freshness + 2 * info + exploration - 2 * cost - 3 * risk;
```

Clamp/validate every ordinal; reject arbitrary floats/negative values rather than silently normalizing them.

- [ ] **Step 4: Add hard eligibility filter before score sort**

`rankStrategyFrontier()` must exclude from executable ranking:

```text
WATCH without fired reopen
BLOCKED
INVALIDATED
SATURATED
DONE
future NOT_BEFORE
contract/safety/capability-ineligible branch
```

The caller supplies explicit eligibility metadata; score never re-enables an ineligible branch.

- [ ] **Step 5: Prove GREEN**

Run full suite.

---

### Task 3: Add child-result -> parent-learning and saturation helpers to GodPrompt

**Files:** GodPrompt `test_control_node.mjs`, `control.mjs`.

**Interfaces:**
- Export `applyStrategyResult(frontier, result) -> { frontier, events }`.
- Result contains `branch_id`, `result_code`, `positive`, `negative`, `information_gain`, `reopen_condition`, `epoch`.

- [ ] **Step 1: Write failing learning tests**

Cover:

1. one invalid child only updates that child;
2. materially distinct negative children increment parent negative evidence;
3. parent does NOT saturate on duplicate same-family variants;
4. parent becomes `SATURATED` only after multiple materially distinct negative children, recent negative/unchanged evidence, no reversible test, and explicit reopen condition;
5. positive child prevents automatic saturation;
6. saturated parent removes unopened same-family variants from top executable ranking;
7. sibling family becomes next-ranked.

- [ ] **Step 2: Prove RED**

Run test file and require expected missing behavior.

- [ ] **Step 3: Implement deterministic result application**

Do not infer commercial facts. `applyStrategyResult` only updates counters/status from the explicit structured result supplied by the workflow. It must return ledger-event payloads, not append them itself.

- [ ] **Step 4: Add ledger event keys**

Support deduped event types:

```text
STRATEGY_BRANCH_CREATED
STRATEGY_BRANCH_RESULT
STRATEGY_PARENT_UPDATED
STRATEGY_BRANCH_REOPENED
STRATEGY_BRANCH_SATURATED
```

Use `branch_id + result_code + epoch` or equivalent stable transition keys.

- [ ] **Step 5: Prove GREEN**

Run all GodPrompt tests.

---

### Task 4: Separate work proof, information gain, and business signals

**Files:** GodPrompt `test_control_node.mjs`, `control.mjs`.

**Interfaces:**
- Add compact per-run state:

```js
INFORMATION_GAIN_COUNT: 0,
BUSINESS_SIGNAL_COUNTS: {
  attributable_money: 0,
  buyer_purchase_request: 0,
  qualified_buyer_reply: 0,
  conversion_payment_transition: 0,
  qualified_distribution_transition: 0,
},
```

- [ ] **Step 1: Write failing separation tests**

Assert increasing `ADVANCEMENT_UNITS` alone cannot increase any business signal or branch score. Assert an explicit qualified buyer signal can update the corresponding counter and increase the branch's `money_proximity` only through an explicit strategy checkpoint.

- [ ] **Step 2: Prove RED**

Run tests.

- [ ] **Step 3: Implement state defaults and validation**

Reset per-run counters on claim while preserving durable strategy branch evidence. Do not treat these counters as SUCCESS; existing money verification remains authoritative.

- [ ] **Step 4: Prove GREEN**

Run suite.

---

### Task 5: Add reopen/backtrack/compaction semantics to GodPrompt

**Files:** GodPrompt `test_control_node.mjs`, `control.mjs`.

**Interfaces:**
- Export `reopenStrategyBranch(frontier, { branchId, triggerCode, epoch })`.
- Export `compactStrategyFrontier(frontier, { limit = 12 })`.

- [ ] **Step 1: Write RED tests**

Verify:

```text
SATURATED without trigger -> remains suppressed
BLOCKED without trigger -> remains suppressed
matching trigger -> returns OPEN or WATCH-current as explicitly supplied
future NOT_BEFORE -> not executable
compaction -> <=12 hot branches
historical closed branches -> represented by ledger, not hot-state padding
```

- [ ] **Step 2: Prove RED**

Run suite.

- [ ] **Step 3: Implement bounded reopen and compaction**

Reopen requires exact `branch_id` + externally established `triggerCode`/condition match. No fuzzy model-generated “close enough” trigger inside control helper.

- [ ] **Step 4: Prove GREEN**

Run suite and stress it 10 iterations.

---

### Task 6: Port V4-B strategy primitives to mcp-geo

**Files:**
- Modify: mcp-geo `.revenue-control/control.mjs`
- Modify: mcp-geo `.revenue-control/test_control_node.mjs`

**Interfaces:** identical mechanical branch schema/scoring/learning helpers; project-specific branch families and commercial gates stay in runtime prompt/contract.

Use diagnostic versions `CONTROL_IMPL_VERSION: v4-b.1`, `WORKFLOW_POLICY_VERSION: v4-b`, `SCHEDULED_PROMPT_VERSION: mcpgeo-rs1-v4b-1`.

- [ ] **Step 1: Add mcp-geo V4-B eval matrix RED tests**

Use representative mcp-geo branches such as buyer-trigger timing, audit fulfillment, owned discovery, passive distribution, transport/reliability. Cover all ten spec V4-B matrix cases.

- [ ] **Step 2: Prove RED**

Run test suite.

- [ ] **Step 3: Port the already-green GodPrompt helpers**

Do not copy GodPrompt-specific payability/Sponsors semantics.

- [ ] **Step 4: Prove GREEN and hash production state/ledger unchanged**

Run full suite and 10-iteration stress.

---

### Task 7: Port V4-B strategy primitives to TrendPulse

**Files:** TrendPulse `.revenue-control/control.mjs`, `.revenue-control/test_control_node.mjs`.

**Interfaces:** same mechanics; TrendPulse V3 caps/backlog rules remain hard eligibility gates before scoring.

Use diagnostic versions `CONTROL_IMPL_VERSION: v4-b.1`, `WORKFLOW_POLICY_VERSION: v4-b`, `SCHEDULED_PROMPT_VERSION: trendpulse-rs1-v4b-1`.

- [ ] **Step 1: Add RED tests with TrendPulse-specific examples**

Model branches such as qualified buyer, conversion/payment friction, owned trust/discovery, triggered listing maintenance, passive distribution, fulfillment, reliability. Include a test proving P90 send-gated/backlog-saturated state cannot be overridden by a higher numeric branch score.

- [ ] **Step 2: Prove RED**

Run suite.

- [ ] **Step 3: Port helpers and wire hard gate metadata**

Branch scoring can reorder eligible work only. It cannot relax V3 max-touch, rolling-24h, backlog, jurisdiction, Gmail-dedupe, or human-verification constraints.

- [ ] **Step 4: Prove GREEN and stress**

Run all tests and 10 iterations; production state/ledger hashes unchanged.

---

### Task 8: Seed strategy frontier naturally, without bulk state rewrite

**Files/Systems:** production control states through normal claim/checkpoint only.

**Interfaces:** project prompts produce initial `STRATEGY_FRONTIER` from current durable frontier/history on the next valid owned run.

- [ ] **Step 1: Do NOT hand-edit current production state**

No JSON migration script over live `state.json`.

- [ ] **Step 2: Add scheduler instruction for first V4-B owned wake**

On first V4-B run, derive at most 12 current branches from existing durable action/freshness/dedupe state, assigning conservative ordinal scores and explicit status/reopen metadata. Do not resurrect invalidated historical routes.

- [ ] **Step 3: Require first frontier checkpoint to validate mechanically**

If validation fails, no external mutation should be justified by the invalid strategy state; correct the branch data first.

---

### Task 9: Update Scheduled Task prompts sequentially for V4-B

**Systems:** same three production Scheduled Tasks.

- [ ] **Step 1: GodPrompt prompt update**

Bump `WORKFLOW_POLICY_VERSION`/prompt string to `v4-b` / `gp-rs1-v4b-1` and add the compact operator loop:

```text
After material result: LEARN child -> update parent -> RERANK siblings.
Suppress INVALIDATED/SATURATED/BLOCKED branches until exact reopen.
Score only eligible branches; money/buyer evidence outranks generic research.
ADVANCEMENT_UNITS is not business reward.
Keep <=12 hot branches; detailed history stays in ledger.
```

- [ ] **Step 2: Canary GodPrompt before touching next prompt**

Require a real run to persist/consume strategy frontier and release READY/NONE.

- [ ] **Step 3: Update and canary mcp-geo**

Use `mcpgeo-rs1-v4b-1`; preserve audit contract and no-cold-outreach.

- [ ] **Step 4: Update and canary TrendPulse**

Use `trendpulse-rs1-v4b-1`; preserve V3 gates exactly.

---

### Task 10: V4-B strategy eval campaign

**Files:** existing test files only.

- [ ] **Step 1: Verify all ten required V4-B evals exist in each project**

Required cases:

```text
invalid child updates child initially
enough independent negative children saturate parent
saturated parent backtracks to sibling
high-money positive branch beats generic research
exploration bonus gives new distinct family a bounded chance
same-family variants do not fake diversity
reopen trigger reactivates branch
score cannot override hard gate/NOT_BEFORE/safety
ADVANCEMENT_UNITS do not alter business reward
frontier compaction <=12
```

- [ ] **Step 2: Run 10 full iterations per project**

Use the V4-A stress command.

- [ ] **Step 3: Reverify production hashes were not touched by fixtures**

Require equality.

- [ ] **Step 4: Inspect one real V4-B run per project**

Require evidence that at least one real branch result caused either child update, parent update, backtrack, suppression, or explicit no-change decision—without violating frozen commercial gates.

- [ ] **Step 5: Gate V4-C**

Do not introduce quiescent fast paths until strategy saturation/backtracking is mechanically tested and live behavior is stable.
