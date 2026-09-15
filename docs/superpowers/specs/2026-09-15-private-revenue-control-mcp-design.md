# Private Revenue Control MCP Design

Date: 2026-09-15
Initial qualification project: AKzar1el/mcp-trendpulse
Shared targets: AKzar1el/mcp-trendpulse, AKzar1el/mcp-geo, AKzar1el/god-prompt + AKzar1el/god-prompt-mcp
Excluded target: Privatizmo

## Problem

The Revenue Shot Scheduled Tasks need durable local ownership, heartbeat, checkpoint, semantic-action, and release mutations. Two scheduler control transports have now demonstrated that ChatGPT's host safety layer can reject a mutation before it reaches the local machine:

- generic `exec_command` was rejected before execution;
- generic structured `apply_patch` succeeded for some control writes, including the E130 run and the E131 claim, but the E131 heartbeat was later rejected as `PLATFORM_BLOCKED_BEFORE_EXECUTION`.

The latest failure was not a local CAS conflict, malformed state, expired lease, bad baseline, or TrendPulse validator failure. E131 successfully claimed and created its run journal before the host rejected the later heartbeat operation.

The control plane therefore needs a narrower MCP surface whose tool semantics describe the actual operation instead of exposing arbitrary shell or arbitrary file mutation.

## Goal

Create one private Revenue Control MCP service, registered once with Codexify, that exposes only bounded Revenue Shot control operations. Use the same service for TrendPulse, mcp-geo, and GodPrompt with project-specific configuration only. Do not add the control surface to the public mcp-trendpulse product and do not integrate Privatizmo.

The first acceptance target is TrendPulse. The service is not considered qualified for mcp-geo or GodPrompt until TrendPulse passes two consecutive real Scheduled Task runs without manual repair.

## Non-goals

- Do not bypass or disguise ChatGPT/OpenAI safety or approval controls.
- Do not add arbitrary shell, arbitrary path, arbitrary file-write, or arbitrary command execution to the new MCP service.
- Do not expose Revenue Shot control tools as normal public mcp-trendpulse product tools.
- Do not modify Privatizmo or add a Privatizmo adapter/project id.
- Do not change Revenue Shot commercial contracts, Gmail policy, V4-A action semantics, or current fixed experiment end dates.
- Do not implement V4-B or V4-C as part of this transport change.
- Do not migrate runtime authority back to Google Docs, Drive, or Supabase.

## Architecture

### 1. One private MCP service

Register one local MCP source with Codexify, provisionally named `revenue_control`. The implementation lives in a private local workspace and is not packaged or published with any public product repository.

The service runs as a local Node process and performs control operations directly. It does not invoke `exec_command`, PowerShell, cmd, or a shell subprocess internally.

### 2. Reuse the existing project control implementations

All three approved control planes already expose a Node `ControlPlane` class from `.revenue-control/control.mjs` with the same core methods:

- `status()`
- `claim(source)`
- `heartbeat(runId)`
- `checkpoint(runId, {patch, event})`
- `close(runId, reason, {closeFields})`

The private service dynamically imports the allowlisted project's existing `control.mjs` and delegates state transitions to that implementation. This preserves each project's current V4-A invariants, file locking, action validation, release gates, ledger dedupe, atomic state writes, and expired-owner recovery instead of reimplementing them in the MCP layer.

Project-specific differences remain inside each existing control implementation: repository identity, prompt version, contract SHA, run-id prefix, and commercial proof fields.

### 3. Hard project registry

The MCP server accepts a project id enum, never a filesystem path.

The initial registry is exactly:

- `trendpulse` -> `C:\Users\Tomi\Desktop\lol\mcp-trendpulse\.revenue-control`
- `mcpgeo` -> `C:\Users\Tomi\Desktop\lol\mcp-geo\.revenue-control`
- `godprompt` -> `C:\Users\Tomi\Desktop\lol\godprompt-suite\.revenue-control`

There is no `privatizmo` project id and no generic path escape hatch. Unknown project ids fail before filesystem access.

Each registry entry also pins the expected control identity, including expected repository/repositories and frozen contract identity. A project is unusable if the resolved root, manifest/state identity, or contract integrity does not match its registry entry.

### 4. Tool surface

The v1 runtime surface is intentionally small.

#### `revenue_status(project)`

Read-only. Returns the validated control snapshot needed by the scheduler: epoch, generation, control state, active run/source, lease, V4-A versions, transport marker, release reason, active action summary, advancement/proof summary, and contract-integrity result.

It does not return arbitrary files and does not accept a path.

#### `revenue_claim(project, source)`

Mutating. `source` is a bounded enum; Scheduled Tasks use `SCHEDULED`.

The server validates the project registry entry and contract, then calls the project's existing `ControlPlane.claim`. Existing behavior remains authoritative: a live owner yields duplicate-wake failure; an expired owner is recovered under the existing lock before a new epoch is claimed; READY/NONE is required for the new owner; generation and epoch advance according to the project validator.

The tool returns the exact new run id, epoch, generation, lease, and control identity. No business or external mutation may occur until the caller observes a successful claim result.

#### `revenue_heartbeat(project, run_id)`

Mutating. Extends only the validated owner's lease through the project's existing `ControlPlane.heartbeat`. A stale run id, expired lease, wrong owner, or malformed state fails closed.

The tool returns the resulting generation and lease timestamps. There is no alternate file-write or shell fallback.

#### `revenue_checkpoint(project, run_id, patch, event)`

Mutating. Delegates to the project's existing `ControlPlane.checkpoint`, with an additional MCP-layer schema guard:

- every patch key must already exist in the current state;
- reserved ownership/version fields are rejected;
- payload size is bounded;
- event type and event payload size are bounded;
- the service cannot create an arbitrary new state field;
- no filesystem path or executable input is accepted.

The project validator remains responsible for V4-A semantic-action transitions, UNKNOWN reconciliation, advancement-triggered post-advancement proof, and state validity.

An empty proof patch with a validated event is allowed when a factual journal/ledger event must be recorded without changing business proof fields.

#### `revenue_release(project, run_id, reason, close_fields)`

Mutating. `reason` is the existing fixed release-reason enum. `close_fields` is subject to the same existing-key/non-reserved/bounded-payload guard as checkpoints.

The service calls the project's existing `ControlPlane.close`. Existing release validation remains authoritative, including no surviving executable actions, closure/deep-work gates, action resolution, one deduped `EPOCH_CLOSE`, READY/NONE transition, and post-write verification.

The service returns final epoch, generation, release reason, and READY/NONE proof.

### 5. No generic recovery tool in the scheduler surface

Expired-owner recovery already exists inside each project's `ControlPlane.claim` under the same local lock. The runtime API therefore does not add a second generic recovery implementation.

The currently stranded TrendPulse E131 owner is a migration case. Before the first new-transport canary, perform one operator-controlled recovery/migration after confirming the E131 lease is expired. The migration must preserve evidence of the failed E131 heartbeat and leave TrendPulse at a validated READY/NONE baseline with the new transport marker. It is not performed by a Scheduled Task.

Future expired runs are recovered by the next `revenue_claim` according to the existing project control implementation.

## Transport identity

The new scheduler transport marker is:

`SCHEDULER_CONTROL_TRANSPORT=REVENUE_CONTROL_MCP_V1`

The one-time operator migration changes only the transport marker and whatever recovery fields the existing control protocol requires. V4-A schema, implementation, workflow policy, scheduled prompt version, and frozen contract version remain project-specific and unchanged.

Scheduled prompts must not use `exec_command`, `apply_patch`, `write_file`, or another generic local mutation mechanism for Revenue Shot control once this transport is active.

## Scheduler data flow

A normal wake is:

1. Call `revenue_status(project)` and validate the expected READY/NONE baseline or a documented recoverable expired owner.
2. Call `revenue_claim(project, "SCHEDULED")`.
3. Reconcile money and buyer inbound only after successful ownership proof.
4. Use `revenue_checkpoint` for V4-A stage/proof/action transitions.
5. Use `revenue_heartbeat` between meaningful work chunks and before critical external side effects when the lease is no longer fresh.
6. Perform external business side effects only while the returned run id still owns an unexpired lease.
7. Use `revenue_release` for the truthful final reason.
8. Call `revenue_status` and independently require final READY/NONE.

If any Revenue Control MCP mutation is rejected by the host before execution, the scheduler freezes new external mutation immediately and reports the exact failed tool/operation. It must not route around the rejection through shell, structured file tools, another Codexify connector, or alternate wording.

## Platform-safety interpretation

This design is not a safety bypass. Its purpose is to give the host a narrow, semantically explicit action surface such as `revenue_heartbeat(project="trendpulse", run_id="...")` instead of an arbitrary shell command or arbitrary JSON file patch.

A host rejection of the narrow mutating tool remains authoritative. If a real Scheduled Task still produces `PLATFORM_BLOCKED_BEFORE_EXECUTION` for the dedicated heartbeat/checkpoint/release tools, this architecture is considered unsuitable for Scheduled Task control and no further prompt-shape or command-shape bypass attempts are allowed.

At that point the control executor must move outside ChatGPT Scheduled Tasks, for example to a local service/scheduler, with ChatGPT operating at a higher-level orchestration boundary.

## Privatizmo boundary

Privatizmo is not part of the project registry, is not modified, and gets no Revenue Control adapter.

Because the current Codexify installation uses a global multi-project MCP catalogue, the private Revenue Control source may be discoverable from chats bound to other Codexify projects. Discoverability is not authority: the service can resolve only the three hardcoded Revenue Shot project ids and has no generic path argument.

This design does not claim caller-level invisibility from Privatizmo chats. Achieving per-project source invisibility would require Codexify-level project-specific source filtering and is outside this transport change. The hard runtime boundary is that there is no Privatizmo project id/root/action target in this service.

## Error model

The service returns stable machine-readable error codes rather than raw filesystem exceptions where possible:

- `PROJECT_NOT_ALLOWED`
- `PROJECT_IDENTITY_MISMATCH`
- `CONTRACT_INTEGRITY_FAILED`
- `CONTROL_STATE_INVALID`
- `DUPLICATE_WAKE`
- `OWNERSHIP_ERROR`
- `LEASE_EXPIRED`
- `PATCH_FIELD_NOT_ALLOWED`
- `EVENT_NOT_ALLOWED`
- `RELEASE_GATE_FAILED`
- `INTERNAL_CONTROL_ERROR`

Errors never trigger an automatic alternate transport.

## Testing

### Service unit tests

Test the project registry, unknown-project rejection, path non-acceptance, identity/contract fencing, payload bounds, existing-key checkpoint guard, error mapping, and tool annotations.

### Adapter contract tests

For TrendPulse, mcp-geo, and GodPrompt, run the same adapter suite against isolated temporary copies of state/ledger/control fixtures:

- status validation;
- claim from READY/NONE;
- duplicate live claim rejection;
- expired-owner recovery on claim;
- heartbeat ownership and expiry checks;
- checkpoint generation monotonicity;
- semantic action transition acceptance/rejection;
- UNKNOWN reconciliation behavior;
- release-gate enforcement;
- exactly one deduped EPOCH_CLOSE;
- final READY/NONE.

The test suite must prove that the shared MCP wrapper does not weaken any project's existing ControlPlane validation.

### No-shell test

Fail the service test suite if runtime implementation contains a shell/subprocess control fallback. The intended v1 implementation dynamically imports the allowlisted `control.mjs` modules and invokes their exported `ControlPlane` methods directly.

## Rollout

### Phase 1: TrendPulse

1. Build and test the private Revenue Control MCP service.
2. Register it once with the existing Codexify service.
3. Perform the operator-controlled E131 expired-owner recovery and switch the TrendPulse transport marker to `REVENUE_CONTROL_MCP_V1`.
4. Run a direct interactive read-only `revenue_status("trendpulse")` canary to prove service reachability, root/contract identity, and the migrated READY/NONE baseline. Do not consume a live epoch merely to test transport.
5. Update only the TrendPulse Scheduled Task to use the dedicated Revenue Control tools for control mutations.
6. Run two consecutive real Scheduled Task qualification wakes without manual repair. The first scheduled wake is the first live mutation canary for the new host-facing tool surface.
7. Independently qualify both resulting epochs read-only.

TrendPulse passes only if both real runs complete ownership, heartbeats, checkpoints, closure, one EPOCH_CLOSE each, and final READY/NONE without `PLATFORM_BLOCKED_BEFORE_EXECUTION` on the dedicated control tools.

### Phase 2: mcp-geo

Only after TrendPulse passes, enable the same MCP transport for mcp-geo. Required project-specific work is limited to registry identity/configuration, transport-marker migration, prompt/tool-name adaptation, and qualification. Do not redesign the service.

### Phase 3: GodPrompt

Only after mcp-geo passes, enable the same transport for GodPrompt. As with mcp-geo, changes are configuration/migration/prompt adaptation plus qualification, not a new control architecture.

## Rollback

If the private MCP service or Scheduled Task canary fails before external business mutation, leave the production Revenue Shot task disabled and restore a validated READY/NONE state using the existing offline control authority.

If failure occurs after a potentially effectful business action, preserve the existing V4-A UNKNOWN/postcondition reconciliation rules. Do not mark the action retryable until the real-world postcondition is reconciled.

Do not restore generic shell or generic structured-file mutation as a scheduler fallback.

## Acceptance criteria

The architecture is accepted for production Revenue Shot scheduling only when all of the following are true:

- one private Revenue Control MCP source is registered with Codexify;
- only `trendpulse`, `mcpgeo`, and `godprompt` project ids resolve;
- no arbitrary path, shell, or generic file-write capability exists in the service;
- Privatizmo is absent from the registry and unchanged;
- the wrapper reuses each project's existing `ControlPlane` implementation and preserves V4-A validators;
- TrendPulse passes two consecutive real Scheduled Task runs with dedicated claim/heartbeat/checkpoint/release tools and no manual repair;
- independent read-only qualification confirms one close per completed epoch and final READY/NONE;
- if the host blocks a dedicated mutating tool before execution, rollout stops rather than attempting another bypass.
