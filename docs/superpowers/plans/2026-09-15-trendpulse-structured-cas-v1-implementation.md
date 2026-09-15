# TrendPulse STRUCTURED_CAS_V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace TrendPulse Scheduled Task shell-based LOCAL_FILE_V1 control with a zero-shell structured compare-and-swap transport that preserves the qualified V4-A ownership, lease, semantic-action, release, and recovery invariants.

**Architecture:** Scheduled runtime authority remains `.revenue-control/state.json`, but every scheduler control mutation is performed with Codexify structured `apply_patch` after a structured `read_file`. A focused pure Node oracle validates and models STRUCTURED_CAS_V1 state/journal transitions for offline TDD; each owned epoch also has a per-run JSON journal used instead of scheduler JSONL append commands. `control.mjs` remains the legacy/manual validator and imports/re-exports the structured oracle without being executed by Scheduled Tasks.

**Tech Stack:** Node.js ESM, `node:test`, LOCAL_FILE_V1 JSON state, structured Codexify `read_file` / `write_file` / `apply_patch`, ChatGPT Scheduled Tasks.

**Spec:** `docs/superpowers/specs/2026-09-15-trendpulse-structured-cas-v1-design.md`

## Global Constraints

- TrendPulse only. Do not modify or enable GodPrompt or mcp-geo.
- Scheduled runtime uses zero `exec_command`/shell operations for control, preflight, qualification, heartbeat, checkpoint, or release.
- Preserve `WORKFLOW_SCHEMA_VERSION=4`, `CONTROL_IMPL_VERSION=v4-a.1`, `WORKFLOW_POLICY_VERSION=v4-a`, `SCHEDULED_PROMPT_VERSION=trendpulse-rs1-v4a-1`, and `CONTRACT_VERSION=frozen-2026-09-14`.
- Preserve frozen TP-RS1 commercial/safety rules and V3 touch/Gmail caps.
- `state.json` remains current-state authority; per-run journals are evidence, never ownership authority.
- Every mutation is exact-context compare-and-swap; a context mismatch fails closed and is never broadened or blindly retried.
- `UNKNOWN` semantic actions never blind retry; ordinary release cannot leave `EXECUTING`/`UNKNOWN` unresolved.
- Release is two-phase: exactly one legal journal `EPOCH_CLOSE`, then exact-context READY/NONE state patch.
- Do not restore hourly production cadence until two consecutive real Scheduled Task runs advance E129 -> E130 -> E131 and each returns READY/NONE without manual repair.
- Never bypass or route around a platform safety/approval stop.

---

### Task 1: Add the pure STRUCTURED_CAS_V1 transition oracle

**Files:**
- Create: `.revenue-control/structured_cas.mjs`
- Create: `.revenue-control/test_structured_cas.mjs`
- Modify: `.revenue-control/control.mjs`

**Interfaces:**
- Produces `STRUCTURED_CAS_TRANSPORT = 'STRUCTURED_CAS_V1'`.
- Produces `createStructuredClaim(state, { runId, source, now }) -> { state, journal }`.
- Produces `createStructuredHeartbeat(state, { runId, now }) -> state`.
- Produces `createStructuredCheckpoint(state, { runId, patch, event, now }) -> { state, event }`.
- Produces `createStructuredRecovery(state, { now }) -> { state, event }` for expired owners only.
- Produces `createStructuredClose(state, journal, { runId, reason, closeFields, now }) -> { state, journal }`.
- Produces `validateStructuredState(state)` and `validateStructuredJournal(journal)`.

- [ ] **Step 1: Write failing claim/duplicate/recovery tests**

Add tests that require a READY/NONE E129/G237 fixture to claim as E130/G238 with `SCHEDULER_CONTROL_TRANSPORT='STRUCTURED_CAS_V1'`, reset the same per-run proof fields as `ControlPlane.claim`, reject a live owner, and recover only an expired owner. A recovered `EXECUTING` action must become same-key `UNKNOWN/UNKNOWN_OUTCOME` before the next claim.

- [ ] **Step 2: Run the focused tests and prove RED**

Run: `node --test .revenue-control/test_structured_cas.mjs`

Expected: FAIL because `structured_cas.mjs` and the exported functions do not exist.

- [ ] **Step 3: Implement minimal claim/state validation**

Implement pure JSON transforms only: no filesystem, shell, Git, network, or scheduler calls. State validation must enforce READY/OWNED ownership equivalence, monotonic integer generation/epoch, exact V4-A stamps when present, valid lease ordering, exact transport marker on structured-owned states, and the existing V4-A semantic-action shape.

- [ ] **Step 4: Add heartbeat/checkpoint tests, then implementation**

Tests must prove owner/run/generation fencing, +1 generation per accepted mutation, ten-minute lease renewal, stale owner rejection, advancement resetting post-advancement deep proof, and legal semantic-action transitions including UNKNOWN reconciliation.

- [ ] **Step 5: Add journal/close tests, then implementation**

Tests must prove journal identity `{transport, epoch, run_id}`, monotonically increasing `next_event_seq`, deduped action transition evidence, exactly one `EPOCH_CLOSE`, ordinary release rejection with unresolved `EXECUTING`/`UNKNOWN`, legal release reasons only, and final READY/NONE with the same V4-A release gates as current `ControlPlane.close`.

- [ ] **Step 6: Re-export the oracle from `control.mjs` and run both suites**

Run:
`node --test .revenue-control/test_structured_cas.mjs`
`node --test .revenue-control/test_control_node.mjs`
`node --check .revenue-control/control.mjs`
`node --check .revenue-control/structured_cas.mjs`

Expected: all PASS; legacy/manual control behavior remains green.

---

### Task 2: Publish the scheduler protocol/manifest contract

**Files:**
- Create: `.revenue-control/structured-cas-v1-protocol.json`
- Modify: `.revenue-control/scheduler-manifest-v4a.txt`
- Test: `.revenue-control/test_structured_cas.mjs`

**Interfaces:**
- Protocol identifies exact transport/version, authoritative state path, journal directory, V4-A stamps, claim reset fields, allowed release reasons, action states/transitions, and fail-closed rules.
- Manifest includes `SCHEDULER_CONTROL_TRANSPORT=STRUCTURED_CAS_V1`, `STRUCTURED_PROTOCOL=.revenue-control/structured-cas-v1-protocol.json`, and `STRUCTURED_JOURNAL_DIR=.revenue-control/runs`.

- [ ] **Step 1: Write failing protocol/manifest integrity tests**

Tests parse the protocol JSON and manifest and assert exact transport, state path, journal directory, frozen contract SHA, V4-A stamps, claim reset keys, and zero-shell policy.

- [ ] **Step 2: Prove RED**

Run: `node --test .revenue-control/test_structured_cas.mjs`

Expected: FAIL because the protocol file/manifest fields do not exist yet.

- [ ] **Step 3: Create the machine-readable protocol and update the manifest**

Keep the protocol compact and factual. It must explicitly state that Scheduled Tasks may use only `get_agent_brief`, `read_file`, `write_file` for creation of a new journal, and `apply_patch`; shell fallback is forbidden.

- [ ] **Step 4: Run protocol tests and full control tests**

Run both Node test suites and syntax checks. Expected: PASS.

---

### Task 3: Deploy one real E130 Scheduled Task canary with zero shell

**Files / surfaces:**
- Modify Scheduled Task `TrendPulse Revenue Shot` (`6aa2d65a2d14819184fd30074f5198a2`).
- Modify Scheduled Task `Qualify TrendPulse V4-A` (`6aa936a3bc048191b547db8b03a1879c`) into the STRUCTURED_CAS_V1 stability qualifier.
- Runtime files: `.revenue-control/state.json`, `.revenue-control/runs/130-<run_id>.json`.

**Interfaces:**
- Production task uses only Codexify Trendpulse structured file tools for local control.
- Qualifier is strictly structured-read-only.

- [ ] **Step 1: Read current state and require baseline E129 / READY / NONE**

Require exact V4-A stamps and no live owner before scheduling the canary. Do not mutate if baseline differs.

- [ ] **Step 2: Install the zero-shell production prompt**

Prompt algorithm: fixed-root proof -> structured protocol/manifest/state read -> exact-context structured claim -> create journal -> structured heartbeat/checkpoints -> Revenue Shot work while freshly owned -> journal EPOCH_CLOSE -> structured READY/NONE release -> structured final readback. Any CAS mismatch or tool rejection stops new external mutation. No `exec_command` is present anywhere in the prompt.

- [ ] **Step 3: Schedule one E130 canary and a later read-only qualifier**

Use one-time exact schedules with enough time for the >=10-minute release floor. Leave GodPrompt/mcp-geo disabled.

- [ ] **Step 4: Qualification acceptance**

Qualifier requires epoch 130, structured transport marker, exact V4-A stamps, scheduler control-canary terminal VERIFIED/suppressed correctly, no unresolved EXECUTING/UNKNOWN, one legal journal EPOCH_CLOSE, and final READY/NONE. If the run is still owned, report PENDING instead of failing it.

---

### Task 4: Prove a second consecutive E131 run before restoring cadence

**Files / surfaces:**
- Same TrendPulse production and qualifier Scheduled Tasks.
- Runtime files: `.revenue-control/state.json`, `.revenue-control/runs/131-<run_id>.json`.

**Interfaces:**
- Consumes an independently qualified E130 READY/NONE state.
- Produces an independently qualified E131 READY/NONE state with no manual control repair between E130 and E131.

- [ ] **Step 1: Run the second one-time production wake**

The same zero-shell prompt must claim E131 from E130 READY/NONE without any operator state repair.

- [ ] **Step 2: Run the second structured-read-only qualifier**

Require the same acceptance invariants as E130 and prove the two journals belong to distinct consecutive epochs/runs.

- [ ] **Step 3: Final verification before cadence restoration**

Require local state E131/READY/NONE, no unresolved action, no live lease, both E130 and E131 legal EPOCH_CLOSE evidence, and zero scheduler shell usage. Only then may the existing hourly schedule be restored in a separate operator action.

---

## Self-review

- Spec coverage: scheduler transport, claim, lease/heartbeat, checkpoint fencing, expired-owner recovery, per-run journal, two-phase release, offline validation, failure policy, and two-consecutive-run qualification are each covered.
- Placeholder scan: no deferred implementation placeholders are present.
- Interface consistency: all tasks use `STRUCTURED_CAS_V1`, `.revenue-control/state.json`, `.revenue-control/runs`, and the same pure oracle function names.