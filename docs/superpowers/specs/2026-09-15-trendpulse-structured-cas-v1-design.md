# TrendPulse STRUCTURED_CAS_V1 Design

Date: 2026-09-15
Project: AKzar1el/mcp-trendpulse
Root: C:\Users\Tomi\Desktop\lol\mcp-trendpulse

## Problem

Normal ChatGPT Scheduled Tasks can reliably use the dedicated Codexify Trendpulse structured file tools (`read_file`, `write_file`, `apply_patch`), including exact-context compare-and-swap style edits. The same scheduler runtime now rejects generic `exec_command` calls before execution, including the TrendPulse `control.mjs` preflight and claim commands. This means the existing scheduler path cannot depend on shell execution for ownership, heartbeat, checkpoint, or release.

The authoritative TrendPulse state is currently healthy at E129 / READY / NONE with V4-A already qualified. The commercial contract and V4-A semantic action rules remain unchanged.

## Goal

Replace only the Scheduled Task control transport with a structured-file control protocol that uses Codexify structured actions and preserves the existing ownership, lease, dedupe, semantic-action, close, and recovery invariants. Keep `control.mjs` as the offline validator/reference implementation and do not weaken V4-A.

## Architecture

### 1. Scheduler runtime transport

The Scheduled Task must use zero generic shell commands for TrendPulse control. Runtime-local control access is limited to:

- `get_agent_brief`
- `read_file`
- `apply_patch`
- `write_file` only for new immutable per-run artifacts where exact overwrite protection is not needed

No `exec_command` is permitted in the scheduler prompt.

### 2. Durable state

`.revenue-control/state.json` remains the single current-state snapshot.

A new field identifies the scheduler transport:

- `SCHEDULER_CONTROL_TRANSPORT = STRUCTURED_CAS_V1`

Existing V4-A version fields remain unchanged.

### 3. Claim protocol

Claim is an exact-context `apply_patch` against the current READY/NONE snapshot. The patch must include enough unchanged context to bind the write to the observed generation, epoch, owner state, and V4-A versions.

A successful claim atomically changes:

- `CONTROL_STATE: READY -> OWNED`
- `CONTROL_EPOCH: n -> n+1`
- `STATE_GENERATION: g -> g+1`
- `ACTIVE_RUN_ID: NONE -> unique run id`
- `ACTIVE_RUN_SOURCE: NONE -> SCHEDULED`
- acquire/heartbeat/lease timestamps
- `LAST_RELEASE_REASON -> PENDING`
- `RUN_STAGE -> RECONCILE`
- reset of all per-run proof fields exactly as current `control.mjs claim()` does

If the exact patch no longer matches, the contender loses the claim and must re-read. It must never broaden the patch, overwrite a live owner, or retry blindly.

### 4. Lease and ownership

The owner is authoritative only while all of these still match:

- exact `ACTIVE_RUN_ID`
- `CONTROL_STATE=OWNED`
- expected epoch/generation
- unexpired `LEASE_EXPIRES_AT`

Heartbeat is another exact-context patch that changes only heartbeat/lease and generation. A heartbeat mismatch means ownership is lost or state changed; external mutation freezes immediately.

Expired-owner recovery uses an exact-context patch from the stale owned snapshot to a recovered READY/NONE state, records a recovery artifact/event, then allows a fresh claim. No recovery is attempted while the lease is still live.

### 5. Checkpoints

Every control checkpoint is an exact-context patch from the owner-observed snapshot to the next snapshot. The patch must include current owner identity and current generation in its context. This prevents stale checkpoints from overwriting newer state.

Duplicate-sensitive side effects retain the V4-A semantic action state machine:

`PLANNED -> EXECUTING -> VERIFIED | UNKNOWN | FAILED_* | BLOCKED`

`UNKNOWN` still requires postcondition reconciliation before retry.

### 6. Per-run journal

Each claimed epoch gets one immutable-identity journal file under:

`.revenue-control/runs/<epoch>-<run_id>.json`

The journal contains the bounded factual event history needed to qualify that run, including:

- claim proof
- heartbeat/checkpoint transitions
- semantic action lifecycle events
- advancement evidence
- deep-replenishment proof
- final closure passes
- exact `EPOCH_CLOSE`

Updates to an existing run journal use exact-context `apply_patch`, not blind overwrite. The journal is not ownership authority; `state.json` remains authority.

### 7. Release protocol

Normal release is two-phase and fail-closed:

1. Write/verify exactly one legal `EPOCH_CLOSE` in the run journal with the final allowed reason and closure evidence.
2. Exact-context patch `state.json` from the owned final snapshot to READY/NONE, preserving the completed run fields and setting the truthful release reason.

If step 1 succeeds but step 2 mismatches/fails, the task must not fabricate a handoff. It freezes new external mutation and leaves lease-expiry recovery for a later wake.

### 8. Offline validator

`control.mjs` remains the canonical validator/oracle for local/manual testing. It gains pure validation helpers for STRUCTURED_CAS_V1 snapshots and run journals where necessary, but Scheduled Tasks do not execute it.

The structured transport must produce states that the same invariants accept:

- ownership iff active run exists
- one owner per epoch
- monotonic generation/epoch
- legal V4-A stages and semantic action transitions
- exactly one `EPOCH_CLOSE`
- no unresolved EXECUTING/UNKNOWN on ordinary release
- final READY/NONE

## Scheduler prompt behavior

The TrendPulse production Scheduled Task will:

1. verify fixed connector root;
2. structured-read manifest/state;
3. structured-CAS claim;
4. structured-CAS heartbeat/checkpoint/journal updates;
5. perform normal Revenue Shot work only while ownership is freshly proven;
6. structured-CAS close;
7. structured-read final READY/NONE proof.

No shell fallback is allowed. A structured-tool rejection is reported directly; the task must not route through another connector or alternate shell syntax.

## Qualification

Before restoring hourly production cadence, TrendPulse must pass:

1. unit tests for claim, duplicate contention, heartbeat, stale-owner recovery, checkpoints, semantic actions, journal close, and release;
2. a concurrent exact-context contention test proving exactly one structured claimant wins;
3. one real Scheduled Task canary that advances E129 -> E130 and returns READY/NONE;
4. an independent read-only qualifier using only structured reads;
5. a second consecutive real Scheduled Task run that advances E130 -> E131 and returns READY/NONE without manual repair.

Only after both consecutive scheduler runs pass is STRUCTURED_CAS_V1 considered stable enough to restore the normal TrendPulse cadence.

## Non-goals

- No GodPrompt or mcp-geo rollout yet.
- No V4-B/V4-C implementation in this change.
- No commercial-contract changes.
- No change to Gmail/research/repo mutation policy.
- No attempt to bypass platform safety controls.
- No migration back to Supabase or Google Docs.

## Failure policy

Any ambiguous CAS result, stale snapshot, malformed state/journal, missing ownership proof, or structured-tool failure is fail-closed. Stop new external mutation, preserve evidence, and recover through the documented lease/state path rather than guessing or broad-overwriting files.
