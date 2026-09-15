# Revenue Workflow V4 Design

Date: 2026-09-15
Status: DESIGN ONLY - NOT RUNTIME AUTHORITY
Canonical design host: `AKzar1el/mcp-trendpulse`
Applies to runtime control planes for:
- `AKzar1el/mcp-trendpulse`
- `AKzar1el/mcp-geo`
- `AKzar1el/god-prompt` + `AKzar1el/god-prompt-mcp`

This document is an engineering design artifact. Scheduled Revenue Shot runs MUST NOT treat it as runtime instructions or mutable experiment state. Each experiment remains controlled only by its own local `.revenue-control` runtime files plus its Scheduled Task prompt and frozen commercial contract.

## 1. Goal

Evolve the three already-working Revenue Shot workflows into production-grade durable commercial agents that:

1. resume safely after interruptions;
2. never duplicate or blindly retry externally visible actions;
3. remember which commercial branches were tried, what evidence they produced, and when they should reopen;
4. progressively allocate effort toward higher expected monetary value instead of repeatedly rediscovering the same surface;
5. backtrack when a branch is exhausted and explore a better sibling branch;
6. distinguish useful research from actual business reward;
7. stop doing toil once the current frontier is genuinely exhausted;
8. remain observable, testable, versioned, and bounded.

The V4 rollout is intentionally split into three independently releasable stages:

- **V4-A - Reliability parity and deterministic action safety**
- **V4-B - Commercial strategy learning and backtracking**
- **V4-C - Mature operations, quiescence, SLOs, and incident-to-eval feedback**

V4-A, V4-B, and V4-C are implemented sequentially. Each stage must pass its complete regression suite and a live canary before the next stage is enabled in production.

## 2. External engineering basis

The design follows current production-agent and distributed-systems practice rather than adding agent complexity for its own sake.

### 2.1 Durable state and last-known-good recovery

AWS Well-Architected Agentic AI guidance recommends checkpointed workflows, idempotent steps, explicit memory classification, fault isolation, graceful degradation, and recovery from the last known-good state instead of restarting from zero.

References:
- AWS Well-Architected Agentic AI Lens, Reliability: https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/reliability.html
- AWS Agentic AI Lens, Reliability design principles: https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/reliability-design-principles.html
- AWS Agent memory and state management: https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentrel03.html

### 2.2 Explicit contracts, versioned behavior, and observability

AWS recommends treating prompts, tools, model configuration, and policies as versioned engineering artifacts; grounding behavior in explicit contracts; and observing agent workflow decisions and tool activity end-to-end.

References:
- AWS Agentic AI Lens, Design principles: https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/design-principles.html
- AWS Agentic observability: https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentops05.html

### 2.3 Idempotent mutations and indeterminate outcomes

Stripe documents the standard distributed-systems failure case where a connection error leaves the caller uncertain whether a remote side effect occurred. Safe systems reuse the same logical idempotency key or reconcile the remote postcondition rather than blindly reissuing the mutation.

References:
- Stripe idempotent requests: https://docs.stripe.com/api/idempotent_requests
- Stripe error handling: https://docs.stripe.com/error-handling

### 2.4 Agent evaluation from real failures

Anthropic recommends building agent evals from representative real-world tasks and failures, while OpenAI recommends end-to-end trace grading and systematic evaluation of agent workflows. V4 therefore turns incidents such as E39/E57, stale leases, duplicate route research, and unknown side effects into permanent regression cases.

References:
- Anthropic, Demystifying evals for AI agents: https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- OpenAI, AgentKit / agent eval capabilities: https://openai.com/index/introducing-agentkit/
- OpenAI, practical guide to building agents: https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/

### 2.5 Context curation instead of unbounded history

Anthropic recommends keeping agent context high-signal and retrieving durable details just in time rather than continually injecting full historical transcripts. V4 therefore stores episodic details in append-only ledger records and keeps only compact current summaries in `state.json`.

Reference:
- Anthropic, Effective context engineering for AI agents: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents

### 2.6 Explore/exploit with reproducible logging

Microsoft Research's Decision Service work describes a production learning loop of explore -> log -> learn -> deploy, emphasizing reproducible decision logging to avoid technical debt. V4-B adopts the principle without introducing an online ML dependency: commercial branches receive transparent deterministic scores and bounded exploration bonuses.

Reference:
- Microsoft Research, Making Contextual Decisions with Low Technical Debt: https://www.microsoft.com/en-us/research/publication/making-contextual-decisions-with-low-technical-debt/

### 2.7 SRE: reduce toil, monitor behavior, learn from incidents

Google SRE emphasizes monitoring, SLOs, simplicity, toil reduction, and postmortem learning. V4-C applies those ideas to Revenue Shot workflow quality rather than infrastructure availability alone.

References:
- Google SRE, Monitoring Distributed Systems: https://sre.google/sre-book/monitoring-distributed-systems/
- Google SRE Workbook foundations: https://sre.google/workbook/part-I-foundations/

### 2.8 Bounded autonomy and agent control

OWASP's current agent guidance recommends least privilege, explicit human control for high-impact actions, resource/retry limits, structured audit metadata, and runtime control over agent actions. V4 keeps the three experiments isolated and does not introduce cross-project writable authority.

References:
- OWASP AI Agent Security Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html
- OWASP Agent Control Standard: https://genai.owasp.org/resource/agent-control-standard-acs/

## 3. Current baseline and gap analysis

The three control planes intentionally remain separate. There is no shared runtime database and no central orchestrator.

### 3.1 GodPrompt

GodPrompt is the current reliability reference implementation. It already has:

- Node-only local control;
- exclusive file lock;
- lease ownership;
- expired-owner recovery;
- full per-run proof reset;
- expired-owner heartbeat/checkpoint/close fencing;
- post-last-advancement deep replenishment;
- >=10-minute ordinary release floor;
- distinct closure-family and closure-mode validation;
- concurrent-claim stress coverage;
- absolute suite-root control invocation.

It does not yet have V4 action journaling, strategy-branch learning, workflow-version telemetry, quiescent fast path, or shared run quality metrics.

### 3.2 mcp-geo

mcp-geo already has post-last-advancement deep-replenishment and the >=10-minute release gate. It still needs parity with the latest GodPrompt hardening, especially:

- full per-run proof reset;
- expired-owner heartbeat/checkpoint/close fencing;
- distinct closure-family validation;
- closure-mode validation;
- equivalent claim-race and stale-proof tests.

### 3.3 TrendPulse

TrendPulse has demonstrated strong substantive behavior in recent runs, but its mechanical control gate is behind the other two. It still needs:

- post-last-advancement deep-replenishment enforcement;
- automatic post-advancement proof reset;
- >=10-minute advancement-bearing ordinary release gate;
- full per-run proof reset;
- expired-owner heartbeat/checkpoint/close fencing;
- distinct closure-family and closure-mode validation;
- advancement-bearing `QUEUE_EXHAUSTED` bypass prevention.

TrendPulse's existing V3 send caps, future-buyer backlog saturation, Gmail dedupe, and commercial rules remain unchanged.

## 4. Non-goals and hard boundaries

V4 MUST NOT:

- create a central writable runtime control plane shared by the three experiments;
- allow one experiment to mutate another experiment's state;
- introduce subagents or Worker Pool execution;
- add automatic prompt self-rewriting;
- let an agent change its own commercial contract, payer, price, payment rail, success definition, deadline, or permissions;
- auto-enable a Scheduled Task that the platform or user has paused;
- add a new payment rail;
- weaken current Gmail dedupe, send caps, legal/channel rules, human-verification boundaries, or repository safety rules;
- turn `ADVANCEMENT_UNITS` into the business reward function;
- manufacture work to satisfy elapsed-time targets;
- turn research quantity into a success metric.

## 5. Common V4 conceptual model

All three control planes implement the same conceptual model independently. No runtime package import is required across repositories.

```text
COMMERCIAL CONTRACT
        |
        v
DURABLE CONTROL
 claim / lease / checkpoint / release
        |
        v
RUN STAGE
 reconcile / plan / execute / learn / rerank / close
        |
        v
STRATEGY FRONTIER
 commercial branches + hypotheses + reopen rules
        |
        v
ACTION INTENT JOURNAL
 deterministic action key + side-effect state
        |
        v
EXECUTION
 tools / email / repository / external surfaces
        |
        v
POSTCONDITION VERIFICATION
 independently establish what actually happened
        |
        v
LEARNING
 child result -> parent branch update
        |
        v
RERANK / BACKTRACK
```

## 6. State storage model

### 6.1 Keep control-file schema compatibility

`SCHEMA_VERSION: 1` continues to mean the on-disk LOCAL_FILE_V1 control envelope. V4 does not need an incompatible file-format migration.

Add a separate workflow field:

```text
WORKFLOW_SCHEMA_VERSION: 4
```

Missing V4 fields are defaulted safely during claim/checkpoint logic until each production state has naturally migrated.

### 6.2 Compact state, detailed ledger

`state.json` stores only current operational summaries needed for the next decision. Long historical details stay in append-only `ledger.jsonl`.

This prevents state/context growth from degrading agent quality.

### 6.3 Version stamps

Every claim records:

```text
CONTROL_IMPL_VERSION
WORKFLOW_POLICY_VERSION
SCHEDULED_PROMPT_VERSION
CONTRACT_VERSION
```

Version values are explicit strings, for example:

```text
CONTROL_IMPL_VERSION: v4-a.1
WORKFLOW_POLICY_VERSION: v4-a
SCHEDULED_PROMPT_VERSION: gp-rs1-v4a-1
CONTRACT_VERSION: frozen-2026-09-14
```

The versions are diagnostic metadata only. They do not grant authority.

## 7. V4-A - Reliability parity and deterministic action safety

### 7.1 Control-plane parity

Port the latest GodPrompt invariants into mcp-geo and TrendPulse:

1. claim resets all epoch-local proof fields;
2. heartbeat/checkpoint/close reject an expired lease;
3. only a fresh claim can recover an expired owner;
4. ordinary advancement-bearing release requires post-last-advancement proof;
5. `NORMAL_HANDOFF` and advancement-bearing `QUEUE_EXHAUSTED` use the same post-advancement/time floor;
6. final closure requires >=5 distinct families;
7. closure pass mode must be exactly `FRESH_PROBE` or `FRESHNESS_RECONCILE`;
8. invalid close writes no `EPOCH_CLOSE` and leaves ownership intact.

GodPrompt retains those rules and receives new regression coverage for all V4-A additions below.

### 7.2 Explicit run stages

Add compact state field:

```text
RUN_STAGE
```

Allowed values:

```text
RECONCILE
PLAN
EXECUTE
LEARN
RERANK
DEEP_REPLENISHMENT
FINAL_CLOSURE
RELEASE
```

Stage transitions are checkpointed after meaningful boundaries. They are diagnostic/resumption hints, not independent authority.

After abandoned-run recovery, the next wake uses the last durable stage plus action state to decide which postcondition must be reconciled before proceeding.

### 7.3 Deterministic semantic action key

Every externally visible mutation gets a semantic action key before execution.

Canonical material:

```text
experiment_id
commercial_action_kind
target_identity
intent_fingerprint
reopen_generation
```

Example:

```text
trendpulse|EMAIL_FIRST_TOUCH|example.com|tp-rs1-candidate-abc|0
```

The action key MUST represent the logical business operation, not the run id. A retry of the same logical operation reuses the same key. A genuinely reopened/new operation increments or changes its explicit `reopen_generation`/intent fingerprint.

The implementation may store a SHA-256 of the canonical material as the compact key while retaining the human-readable fingerprint in the ledger.

### 7.4 Action lifecycle

State keeps at most one current mutation intent:

```text
ACTIVE_ACTION: {
  action_key,
  kind,
  target,
  intent_fingerprint,
  state,
  started_at,
  failure_class,
  not_before,
  verification_hint
}
```

Allowed action states:

```text
PLANNED
EXECUTING
UNKNOWN
VERIFIED
FAILED_RETRYABLE
FAILED_PERMANENT
BLOCKED
```

Rules:

- `PLANNED -> EXECUTING` is checkpointed before the external mutation.
- External success is not trusted until independently verified when practical.
- Verified effect becomes `VERIFIED`.
- Clear no-effect transient failure becomes `FAILED_RETRYABLE` with bounded retry metadata.
- Permanent/policy/human blockers become `FAILED_PERMANENT` or `BLOCKED` with reopen conditions.
- A timeout, interrupted tool call, lost acknowledgement, or ambiguous response after possible execution becomes `UNKNOWN`.
- `UNKNOWN` may never be blindly re-executed.
- If a run dies while the durable action state is still `EXECUTING`, the next owner MUST conservatively promote that stale `EXECUTING` state to `UNKNOWN` before any new execution. It cannot know whether the previous process crossed the external side-effect boundary.
- When a downstream API natively supports idempotency keys, reuse the semantic action key (or a deterministic derivative accepted by that API). When it does not, the local action key remains the durable dedupe/reconciliation key and the workflow relies on independently observable postconditions rather than pretending the remote system is idempotent.

### 7.5 Unknown-outcome reconciliation

When `ACTIVE_ACTION.state == UNKNOWN`, the next eligible step is always:

```text
RECONCILE_EXTERNAL_POSTCONDITION
```

Possible outcomes:

```text
effect exists        -> VERIFIED
effect absent        -> safe new execution attempt using same action key
still ambiguous      -> WATCH/BLOCKED, no duplicate mutation
```

This applies to Gmail sends, directory submissions, GitHub mutations, releases/deployments, and any future externally visible action for which an observable postcondition exists.

### 7.6 Action ledger records

Append structured records, deduped by action key + transition:

```text
ACTION_INTENT
ACTION_EXECUTION_RESULT
ACTION_POSTCONDITION
ACTION_FAILURE
```

These records carry compact facts, not model reasoning transcripts.

### 7.7 Shared failure taxonomy

Material tool/action failures use one structured classification:

```text
TRANSIENT
RATE_LIMITED
AUTH_REQUIRED
CAPABILITY_UNAVAILABLE
POLICY_BLOCKED
HUMAN_REQUIRED
PERMANENT
UNKNOWN_OUTCOME
```

Each failure stores:

```text
failure_fingerprint
failure_class
lane
action_key if relevant
evidence
retry_budget_used
not_before
reopen_condition
```

Behavior:

- `TRANSIENT`: bounded immediate retry if action safety is proven;
- `RATE_LIMITED`: backoff/NOT_BEFORE, no hammering;
- `AUTH_REQUIRED`: block dependent lane only;
- `CAPABILITY_UNAVAILABLE`: degrade that lane, rerank others;
- `POLICY_BLOCKED`: never bypass;
- `HUMAN_REQUIRED`: WATCH/BLOCKED until explicit human/external state change;
- `PERMANENT`: suppress until explicit reopen condition;
- `UNKNOWN_OUTCOME`: reconcile postcondition before any retry.

### 7.8 Retry budgets

No generic unlimited retries.

Each action keeps a small explicit retry budget. Default V4-A policy:

```text
immediate transient retries: max 1
total same-wake execution attempts: max 2
```

Existing stricter Gmail/email rules override these defaults.

Rate limits and external-review waits use `NOT_BEFORE` rather than consuming the retry budget through polling.

### 7.9 V4-A acceptance criteria

For all three control planes:

- stale epoch proof cannot satisfy a new run;
- expired owners cannot heartbeat/checkpoint/close;
- concurrent claims elect exactly one owner;
- short advancement-bearing handoffs are rejected;
- advancement-bearing `QUEUE_EXHAUSTED` cannot bypass deep proof;
- duplicate closure families are rejected;
- invalid closure modes are rejected;
- semantic action keys dedupe same-intent retries;
- `UNKNOWN` action state cannot execute until reconciliation occurs;
- failure taxonomy drives deterministic retry/suppress behavior;
- production state/ledger are byte-for-byte unchanged by the isolated test suite;
- one live canary per project ends READY/NONE without duplicate external mutation.

## 8. V4-B - Commercial strategy learning and backtracking

### 8.1 Purpose

V4-A makes actions safe. V4-B makes the commercial search progressively smarter.

The core unit is no longer just an action. It is a durable commercial hypothesis/branch.

### 8.2 Strategy branch record

Keep a bounded compact `STRATEGY_FRONTIER` in state. Detailed evidence remains in ledger records.

Each branch contains:

```text
branch_id
parent_branch_id
family
hypothesis
status
attempt_count
positive_evidence_count
negative_evidence_count
last_result_code
last_tested_epoch
money_proximity
evidence_strength
trigger_freshness
information_gain_remaining
execution_cost
risk
expected_value_band
reopen_condition
not_before
```

Allowed branch status:

```text
OPEN
WATCH
BLOCKED
INVALIDATED
SATURATED
DONE
```

### 8.3 Branch hierarchy

Typical top-level families remain experiment-specific but map to the same conceptual hierarchy:

```text
MONEY / BUYER
CONVERSION / PAYMENT
DISTRIBUTION / DISCOVERY
TRUST
FULFILLMENT / READINESS
RELIABILITY
```

Children represent concrete hypotheses/routes.

Example:

```text
DISTRIBUTION
  -> PASSIVE_MCP_DIRECTORIES
       -> PIPEWORX
       -> FINDMCP
       -> MCP_DIRECTORY
```

### 8.4 Learn child -> update parent -> rerank siblings

Every completed branch investigation records two decisions:

1. child result;
2. parent-level effect.

Examples:

```text
PIPEWORX = INVALIDATED_REGISTRY_MIRROR
parent PASSIVE_MCP_DIRECTORIES = still viable
```

After enough independent negative child evidence:

```text
PASSIVE_MCP_DIRECTORIES = SATURATED_LOW_EV
reopen = material new directory / attribution signal / ecosystem change
```

Once a parent is saturated, its unopened same-family variants lose exploration priority. The planner backtracks to another top-level family instead of searching endlessly for near-identical variants.

### 8.5 Separate work proof, information, and business reward

V4 keeps three concepts separate:

```text
ADVANCEMENT_UNITS
  = execution/release-quality proof

INFORMATION_GAIN
  = decision-quality improvement from reducing uncertainty

BUSINESS_SIGNAL
  = external evidence closer to money
```

`ADVANCEMENT_UNITS` MUST NOT be used as the optimization reward.

Business-signal ladder, highest first:

```text
attributable money
buyer purchase/request
substantive qualified buyer reply
verified conversion/payment transition
verified qualified distribution/exposure transition
information gain
```

Money remains the only experiment SUCCESS condition.

### 8.6 Deterministic branch scoring

Do not introduce an online ML dependency. Use transparent ordinal scoring.

Each candidate gets 0-3 values for:

```text
money_proximity
evidence_strength
trigger_freshness
information_gain_remaining
execution_cost
risk
```

Suggested deterministic score:

```text
score =
  4 * money_proximity
+ 3 * evidence_strength
+ 2 * trigger_freshness
+ 2 * information_gain_remaining
+ exploration_bonus
- 2 * execution_cost
- 3 * risk
```

`exploration_bonus` is bounded to 0-2:

- 2: genuinely untested, materially different family;
- 1: lightly tested but uncertainty remains;
- 0: known/current branch.

The score ranks actions; it never overrides hard contract/safety/capability gates.

### 8.7 Exploit vs explore

Planner behavior:

```text
high score + current positive evidence -> exploit
untested distinct branch + useful uncertainty -> explore
repeatedly negative same-family evidence -> suppress
explicit reopen event -> reactivate
```

The planner must not maintain artificial equal attention across families.

### 8.8 Saturation rules

A branch may become `SATURATED` only when:

- multiple materially distinct children or probes have been consumed;
- recent evidence is negative/unchanged;
- no concrete reversible test remains;
- an explicit reopen condition is recorded.

A single failed URL/tool call never saturates a parent family.

### 8.9 Strategy ledger records

Append compact events:

```text
STRATEGY_BRANCH_CREATED
STRATEGY_BRANCH_RESULT
STRATEGY_PARENT_UPDATED
STRATEGY_BRANCH_REOPENED
STRATEGY_BRANCH_SATURATED
```

No chain-of-thought is stored. Only externally supportable facts, structured scores, result codes, and decision metadata are persisted.

### 8.10 Bounded frontier size

To preserve context quality:

- state keeps at most 12 active/top-ranked strategy branches;
- lower-priority historical branches live only in ledger history;
- claim/reconcile loads only the compact frontier plus explicitly relevant historical fingerprints;
- branches marked DONE/INVALIDATED/SATURATED do not remain in the hot frontier unless a reopen trigger fires.

### 8.11 V4-B acceptance criteria

- a failed concrete route is not retried without its reopen condition;
- multiple failed same-family routes can downgrade/saturate the parent;
- saturation causes planner backtracking to a sibling family;
- a positive buyer/conversion branch outranks generic research;
- branch scoring cannot override send caps, safety, legal rules, or NOT_BEFORE;
- advancement cannot be gamed into strategy reward;
- a newly reopened branch returns to consideration;
- frontier remains bounded and does not grow indefinitely;
- synthetic strategy-tree evals reproduce the intended backtracking behavior.

## 9. V4-C - Mature operations

### 9.1 Quiescent fast path without weakening exhaustion proof

Do NOT add a new release reason initially. Reuse `QUEUE_EXHAUSTED` and add explicit compact fields:

```text
QUIESCENT_MODE: true|false
QUIESCENT_ESTABLISHED_EPOCH
QUIESCENT_PROOF_RESULT
QUIESCENT_REOPEN_TRIGGERED: true|false
NEXT_USEFUL_AT
QUIESCENT_REOPEN_CONDITIONS
```

A run may use the fast quiescent path only if a prior rigorous run already established:

- no OPEN strategy branch;
- no positive-EV unsaturated branch;
- every WATCH/BLOCKED branch has an explicit reopen condition;
- all relevant NOT_BEFORE values are in the future;
- mandatory deep exploration was previously completed;
- no fresh external trigger is present;
- `NEXT_USEFUL_AT` or an event-based reopen condition exists.

The control helper must enforce a separate deterministic `QUIESCENT_QUEUE_EXHAUSTED` validation branch. It may waive the ordinary current-wake 10-minute/deep-replenishment requirements only when all of the following durable proof exists:

```text
QUIESCENT_MODE: true
QUIESCENT_ESTABLISHED_EPOCH < current CONTROL_EPOCH
QUIESCENT_PROOF_RESULT is non-empty
QUIESCENT_REOPEN_TRIGGERED: false
SURVIVING_EXECUTABLE_ACTIONS: []
NEXT_USEFUL_AT is future OR explicit event-based reopen conditions exist
```

The prior establishing epoch must itself have satisfied the full normal exhaustion/deep-work rules. A run cannot establish quiescence and consume the fast path in the same epoch.

A quiescent wake performs only:

```text
money reconciliation
buyer/inbound reconciliation
reopen-trigger reconciliation
```

If nothing changed, it may quickly release `QUEUE_EXHAUSTED` while retaining quiescent mode. It does NOT need to manufacture ten minutes of research that was already rigorously exhausted.

Any reopen trigger immediately clears quiescent mode and returns to the normal substantive-work rules.

This fast path is introduced only after V4-B proves branch saturation/backtracking correctly.

### 9.2 Compact run-quality scorecard

Every `EPOCH_CLOSE` records or references:

```text
workflow versions
elapsed_minutes
substantive_active_minutes
tool_failure_count
retry_count
unknown_outcome_count
advancement_units
information_gain_count
strategy_branches_opened
strategy_branches_closed
strategy_branches_saturated
duplicate_actions_suppressed
external_mutations_attempted
external_mutations_verified
buyer_signal_count
money_status
release_reason
```

### 9.3 Workflow SLOs

Track engineering SLOs locally from ledger history. Initial targets are diagnostic, not release blockers:

```text
clean READY/NONE release rate >= 99% of claimed completed runs
duplicate externally visible mutation rate = 0
unknown-outcome blind retry rate = 0
stale-owner mutation rate = 0
control-plane ownership split-brain = 0
```

Business metrics remain separate from reliability SLOs.

Useful commercial diagnostics include:

```text
money-signal rate
qualified buyer-signal rate
advancement rate
information-gain rate
strategy-family saturation rate
reopen-to-action latency
branch revisit suppression rate
```

### 9.4 Incident -> eval candidate loop

When a new material workflow incident occurs, append a structured record:

```text
EVAL_CASE_CANDIDATE
```

Fields:

```text
incident_fingerprint
observed_bad_behavior
expected_invariant
minimal_state_fixture_hint
severity
first_seen_epoch
```

This does NOT auto-edit code or tests. During engineering maintenance, accepted candidates become deterministic regression tests.

Known initial corpus includes:

- E39 GodPrompt premature handoff;
- E57 mcp-geo premature handoff;
- stale proof contamination;
- expired owner attempting heartbeat/checkpoint/close;
- concurrent claim race;
- advancement-bearing `QUEUE_EXHAUSTED` bypass;
- duplicate closure families;
- malformed closure mode;
- duplicate registry mirror research;
- unknown Gmail/send/submission outcome;
- human-verification blocker;
- lane-local failure incorrectly promoted to global boundary;
- saturated branch reopened without trigger;
- quiescent fast path incorrectly used while executable work remains.

### 9.5 Prompt reduction comes last

Only after V4-A/B/C eval coverage is stable may the Scheduled Task prompts be reduced.

Target eventual scheduler kernel:

```text
root / connector authority
frozen contract location
control helper location
workflow policy version
hard safety boundaries
claim/release protocol
terminal deadline
```

Mechanical workflow invariants remain in `control.mjs`; high-signal commercial policy remains in frozen local contract/policy files.

Prompt reduction is NOT part of the initial V4-C implementation unless the eval suite proves equivalent behavior.

## 10. Project-specific preserved behavior

### 10.1 TrendPulse

Preserve unchanged:

- TP-RS1 EUR49 offer;
- V3 total/per-wake/rolling-24h send caps;
- P90 viable-future-backlog target;
- exact Gmail dedupe and SENT verification;
- 5-touch diagnosis and 10-touch pause;
- max passive-directory attempt rules;
- human verification non-bypass;
- fixed terminal time.

V4 learning may lower the priority of repeatedly weak distribution families, but cannot relax buyer/send caps.

### 10.2 mcp-geo

Preserve unchanged:

- EUR99 one-time audit;
- no proactive cold outreach;
- exact repo/Worker mutation scope;
- DigestSEO flat-tool-name mismatch remains outside experiment scope;
- Wrangler pin and current production safety requirements;
- buyer-initiated Gmail only;
- fixed terminal time.

### 10.3 GodPrompt

Preserve unchanged:

- US$49 Agent Harness Review;
- GitHub Sponsors-only payment rail;
- payability gate;
- warm-touch cap;
- no new third-party GitHub promotional mutation;
- exact two-repo scope;
- absolute suite-root control invocation;
- fixed terminal time.

## 11. Migration and rollout strategy

### 11.1 No bulk production-state rewrite

Avoid hand-editing current production `state.json`.

New V4 fields are initialized safely on the next valid claim and checkpoint. Existing historical fields remain readable. Ledger history is never rewritten.

### 11.2 Sequential rollout

Implement in this order:

1. GodPrompt as reference test bed for new V4-A action-journal/failure-taxonomy primitives;
2. port V4-A to mcp-geo;
3. port V4-A to TrendPulse, including its larger post-advancement parity gap;
4. one isolated fixture stress suite per project;
5. one live canary per project;
6. only after all three pass, introduce V4-B branch learning sequentially;
7. after V4-B live behavior is stable, introduce V4-C quiescence/metrics/eval-candidate features.

At no point are all three runtime control planes changed blindly in one unverified batch.

### 11.3 Scheduler prompt updates

Scheduled Task prompts are changed only after the corresponding local control implementation and regression suite pass.

Prompt additions should describe only behavior the control plane can enforce or safely support. Do not duplicate large mechanical code invariants in prose when the control helper already enforces them.

### 11.4 Live proof requirement

Unit/stress tests prove local invariants, not scheduler behavior.

Each stage is considered production-proven for a project only after a real Scheduled Task/manual wake successfully:

```text
claim -> work -> checkpoint -> close -> READY/NONE
```

under the new workflow version.

## 12. Test strategy

All behavior changes use TDD.

### 12.1 V4-A regression matrix

At minimum:

1. claim clears stale run proof;
2. duplicate live claim rejected;
3. concurrent claims elect exactly one owner;
4. expired heartbeat rejected;
5. expired checkpoint rejected;
6. expired close rejected;
7. expired owner recovered by next claim;
8. E39-style short advancement handoff rejected;
9. E57-style short advancement handoff rejected;
10. advancement resets post-adv proof;
11. advancement-bearing queue bypass rejected;
12. zero-adv freshness-only exhaustion rejected;
13. duplicate closure families rejected;
14. invalid closure mode rejected;
15. valid production-grade handoff accepted;
16. close idempotence after release;
17. action-key same intent deduped;
18. reopened intent receives distinct generation/fingerprint;
19. unknown action cannot execute without reconcile;
20. verified unknown postcondition becomes VERIFIED;
21. absent unknown postcondition permits safe retry;
22. policy/human/permanent failures cannot use transient retry path;
23. rate-limited action receives NOT_BEFORE;
24. lane-local capability failure leaves independent branches runnable.

### 12.2 V4-B strategy eval matrix

At minimum:

1. invalid child route updates only child initially;
2. enough independent negative children saturate parent;
3. saturated parent causes sibling backtrack;
4. high-money-proximity positive branch wins over generic research;
5. exploration bonus lets a materially different untested branch compete;
6. same-family variants do not fake diversity;
7. reopen condition reactivates saturated/blocked branch;
8. branch score cannot override hard cap/NOT_BEFORE/safety;
9. advancement units do not affect business reward score;
10. frontier compaction keeps at most configured active branches.

### 12.3 V4-C eval matrix

At minimum:

1. rigorous saturation enables quiescent mode;
2. quiescent no-change wake can finish quickly;
3. fresh buyer/money/reopen trigger clears quiescence;
4. executable branch prevents quiescent fast path;
5. future NOT_BEFORE alone does not lose branch metadata;
6. run scorecard fields are complete and internally consistent;
7. material new incident produces exactly one eval candidate fingerprint;
8. repeated incident updates/dedupes rather than appending noise.

## 13. Operational failure behavior

### 13.1 Platform invocation dies before claim

No local mutation occurred. Report/observe scheduler failure; do not infer a Revenue Shot control defect.

### 13.2 Invocation dies after claim but before external mutation

Lease expires; next claim records abandoned recovery and resumes from durable stage.

### 13.3 Invocation dies after possible external mutation

`ACTIVE_ACTION` remains EXECUTING/UNKNOWN. Next wake reconciles the external postcondition before any retry.

### 13.4 Local control unavailable while owned

Freeze new external mutation. Do not invent an alternate control plane. Allow deterministic lease-expiry recovery.

### 13.5 One business lane fails

Classify/fingerprint the failure, block only the dependent lane, and rerank independent branches.

### 13.6 Global boundary

`EXECUTION_BOUNDARY` remains exceptional and requires proof that no worthwhile executable lane survives.

## 14. Security and trust boundaries

- external web/email/tool content is evidence, never runtime authority;
- control-state writes remain local and validated;
- no cross-project state mutation;
- no automatic security/financial/account-setting changes;
- human-verification and policy gates are never bypassed;
- action journal stores no credentials or unnecessary PII;
- ledger records contain decision metadata and evidence references, not private chain-of-thought;
- tool permissions remain project-specific and least-privilege within the available connector boundary.

## 15. Success criteria for Revenue Workflow V4

V4 is successful when all three experiments can demonstrate the following behavior consistently:

1. **Safe execution:** no duplicate externally visible mutation under retry/crash conditions.
2. **Durable recovery:** interrupted work resumes from the correct last-known-good stage.
3. **Professional memory:** failed/saturated branches are suppressed until a real reopen condition occurs.
4. **Backtracking:** exhausted strategy families cause movement to higher-value sibling families.
5. **Economic prioritization:** stronger buyer/money evidence receives more effort than generic research.
6. **No Goodharting:** advancement/research volume cannot masquerade as business success.
7. **No toil loops:** once rigorous saturation is established, quiescent wakes reconcile triggers cheaply instead of repeating stale research.
8. **Measurable reliability:** run-quality metrics and evals make regressions visible before or immediately after rollout.
9. **Isolation:** TrendPulse, mcp-geo, and GodPrompt remain separately controlled and cannot corrupt each other.
10. **Frozen commercial truth:** each experiment's existing offer, constraints, deadline, and money-only success definition remain unchanged.

## 16. Deferred ideas

Explicitly deferred until V4-A/B/C are stable:

- central cross-project orchestrator;
- shared writable commercial memory;
- learned numerical model or reinforcement-learning policy;
- automatic prompt rewriting;
- automatic Scheduled Task enable/disable/reschedule decisions;
- subagent expansion;
- large prompt compression/migration;
- generic workflow framework extraction into a fourth repository.

Those may be reconsidered only if production evidence shows the isolated V4 architecture is insufficient.
