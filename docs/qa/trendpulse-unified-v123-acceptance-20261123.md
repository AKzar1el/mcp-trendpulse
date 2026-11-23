# V1 + V2 + V3 unified MCP: cross-tool acceptance and productivity study

Date: 2026-11-23. Source base: `7f6aa5466a12186d5a584424b68089e883a7bbea`.

**Status:** Local integration, bounded combinatorial QA, live cross-version source acceptance, exact-wheel full regression and controlled three-round A/B are complete. GitHub source review/CI and post-merge cleanup remain separate gates. This protocol was frozen before the new combined *live* and A/B trials; the initial 35-tool discovery and V3 plan-only smoke had already run. It is **not** a blinded human trial or statistical productivity proof.

## Scope and non-negotiable constraints

- One **local opt-in** stdio server: `python -m mcp_trendpulse.mjau_v3.unified_mcp`, mounting the existing 16 community, 17 intelligence, and two narrow V3 official-source tools.
- All 35 tools are still read-only, no paid API keys and no publication/hosted app changes. V3 remains inside the excluded-from-wheel `mjau_v3` source package; this trial is not authorization to release OSV-derived data commercially, move V3 into the public distribution or hot-reload the live 33-tool source.
- Google Trends unofficial/24h Explore rate limits remain expected, per AGENTS.md. No bypasses, aggressive retries, or exhaustive live sampling of limited provider methods.
- **Exhaustive in-scope combination coverage:** all 35 schemas individually validate; **all 595 unordered pairs** execute concurrent invalid-input MCP calls to prove per-route rejection/no cross-routing, and all **6,545 unordered triples** are checked for unique registry entries/schema coexistence. This does **not** test every input combination or every 2-/3-step valid source workflow.
- Real cross-family workflows, valid input variants, source truth checking, cache and rate-limit degradation are evaluated separately; failures must not yield fictitious demand, confirmed identities, or secure-package guarantees.

## Predeclared real tasks and grading

Two noncontrived research decisions:

**R1: Software supply-chain research briefing.** A Node.js app imports a known version of npm minimist. Use V1 recent supply-chain headlines for context; V2 Node.js release lifecycle and/or npm dependency metadata for exact version scope; V3 OSV for exact advisory IDs. A source-backed success includes correct article dates, release/version, advisory IDs, original URLs, and explicit warning that security status requires independent review. RSS headline is not full article; OSV empty does not mean safe.

**R2: Source/organization disambiguation.** Use V1 headline evidence about Google/Apple (if available); V2 published public research/scorecard as separate corroboration with scope warning; V3 exact Wikidata Q95 and Q312 labels with name matching. Must not merge two entities or treat a Wikidata name as an independently verified legal entity.

**R3: No-evidence market question.** V1 Slovenian RSS trend; V2 seedless three-source discovery or zero-evidence opportunity evaluation; V3 plan-only source readiness. Correct result is a date/source-qualified lead with no automatic buyer verification or growth forecast, and no Google 24h/Explore retry loop.

For each: **0 = unusable/wrong**, **1 = partial or justified abstention**, **2 = source-backed and decision-useful with caveats**. The scorer is the same assistant, so report the rubric as descriptive evidence only. Predeclared correctness assertions (source IDs, dates, versions, null handling and prompt safety) are stronger than narrative scores.

## A/B performance design

**B0 direct-original:** Query the *same* official-source endpoint for the same exact QIDs/package version once or a bounded number of times; record response bytes, execution wall-time, and agreement on IDs. Do not compare raw body size to projected metadata as token costs or call a direct API an apples-to-apples MCP transport.

**B1 separated:** Three independent local stdio MCP connections (community, intelligence, V3) using the same no-network task plan, same Python, same machine; measure elapsed startup/list/calls/overall and correctness.

**B2 unified:** One local stdio MCP connection with all 35 tools, the same no-network task plan, same Python and machine; measure elapsed startup/list/calls/overall, and response equivalence. Alternate B1/B2 order in >=3 trial rounds to reduce first-run bias.

**Live unified:** One additional end-to-end source workflow R1/R2 within explicit source budgets, real provider URLs and zero secret disclosure. Repeated cached V3 calls are expected to be quicker than first calls; small-N, no long-term uptime claim.

**A true productivity advantage** needs comparable correctness plus reduced completion time or human steps, not merely more tools. We will state if B2 is **slower** or indistinguishable, and we will not invent saved euros or human minutes. Benchmarks are one-machine, low-N, not generalized.

## Results and limitations

### Actual one-client V1 + V2 + V3 execution

The source-only unified stdio server started, advertised **35** tools, and completed a live research sequence in **13,691 ms including 8,062 ms cold startup**. It performed actual bounded source calls, not synthetic agent responses:

| Workflow step | Observed wall ms | Validation |
| --- | ---: | --- |
| V1 software-supply-chain Google News RSS | 763 | Four dated original-headline/publisher/link records; no article body claims |
| V2 Node.js 22 release lifecycle | 39 | Provider-reported EOL **2027-04-30**, no warranty of specific support entitlement |
| V2 npm:minimist@0.0.8 dependency graph | 1,017 | Requested ecosystem/package/version and graph scope matched; not users or customers |
| V3 OSV exact package/version advisory IDs | 658 | **GHSA-vh95-rmgr-6w4m** and **GHSA-xvch-5gv4-984h**; same IDs independently returned by official OSV `/v1/querybatch`, direct request **483 ms** |
| V3 Wikidata explicit QIDs | 500 | `Q95` Google candidate only, **not verified organizational identity** |
| V3 cached comparison on identical QIDs | 20 | `Q312` Apple Inc. matched instead, correctly re-evaluated text without another provider call |
| V2 empty-evidence buyer evaluation | 39 | `insufficient`, `success_probability=null`, `buying_intent_confirmed=false` |
| V2 three-source seedless discovery, compact | 1,811 | Real OpenAlex/CFPB/TED observations; no verified buyers or demand growth |
| Same discovery, full cached | 29 | All three source cache hits; exact candidates unchanged |
| Invalid V3 QID, followed by valid V2 plan | 146 + 12 | Bad request rejected, other version tools still functional |

Full discovery response was **14,825 JSON characters**, compact was **5,194** on this live source sample (**64.96% shorter** while preserving candidates, official TED audit, source coverage and no-buyer caveats). Characters are **not** measured LLM token cost.

The original V1, V2 and V3 FastMCP objects remained unchanged when the unified parent module was imported; only the deliberately started parent exposed all 35 tools. Existing installed/public 33-tool services were not restarted or modified.

### Exhaustive bounded cross-tool routing scope

- **35/35** tool schemas were observed as read-only, input type object, with extra parameters disallowed and nonempty descriptions.
- **35/35** tools rejected an unknown argument without contacting provider APIs.
- **All 595 unordered pairs** ran real **concurrent** invalid-input MCP calls (**1,190 calls** total); both routes independently rejected the unknown input every time.
- **All 6,545 unordered triples** had compatible registry names and input metadata. Triples were *enumerated/schema-checked*, not executed as valid tool chains, to avoid a combinatorial explosion and abuse of public provider quotas.
- Positive same-client cross-family plans, concurrent V2/V3 plans, transient V3 source exception fault injection, V2 follow-up after a V3 fault, and separate original-server catalog preservation were all tested.

**CI workload policy:** the 1,190-call pairwise *stress* test passed locally but the first GitHub Python 3.14 shared runner received a shutdown/cancellation signal after several minutes at that test, **not a failed contract assertion**. It is therefore an explicitly opt-in stress test: set `TRENDPULSE_QA_FULL_PAIRWISE=1` to repeat all 595 real concurrent pairs on a dedicated capable runner. Normal CI still executes 35 individual invalid-input cases, five real cross-family concurrent pairs, every triple's metadata check, the positive/fault tests, and the comprehensive existing per-tool suite. This is not hiding a product failure; it is separating long-running load coverage from the routine bounded regression gate. The pre-change PR-head CI cancellation is not counted as a green check.

This supports broad dispatch, validation, isolation and failure resilience **but is not literally all argument combinations**, arbitrary model-driven workflows, or independent production readiness of every provider. Existing per-tool unit and adversarial tests remain necessary.

### Controlled A/B benchmark results (real stdio clients)

All **three** alternating-order local trial rounds ran the **same three public-data plan tasks**, in parallel when using separate servers. All **9/9 expected source plans** were exactly equal between separate and unified executions. Plans made **zero external requests**, so this specifically measures **connection/startup and MCP orchestration**, not the quality or duration of live research.

| Round | Unified 35-tool app | Three separate 16/17/2-tool servers |
| --- | ---: | ---: |
| 1 | 11,477 ms | 21,669 ms |
| 2 | 6,325 ms | 13,472 ms |
| 3 | 7,852 ms | 9,330 ms |
| **Median** | **7,852 ms** | **13,472 ms** |

The measured median startup-and-plan advantage was **5,620 ms / 41.7% less elapsed time** for the unified option under this specific small-N setup. It did not require paying for any API. This is not a measured 41.7% gain in human research output, backend source freshness or long-run reliability, and independent human task grading is still required.

For the one exact OSV real-source call, **unified MCP first use (658 ms) was slower than direct original OSV API (483 ms)**, but the same-payload local cached query is much faster on reuse; this distinction matters when describing productivity. A single extra primary-source API call was used to verify the advisory IDs. The small sample size does **not** justify a production SLA or robust significance claim.

### Environment mismatch diagnosed, not hidden

The first complete local suite on the checkout passed **3,211** tests but failed **two** registry-version assertions because the shared `.venv` had an older installed distribution `mcp-trendpulse==0.2.47`, whereas the repository `pyproject.toml` and all its release manifests are `0.3.1`. This is a **test-environment distribution-metadata mismatch**, not evidence of stale production manifests or an application regression. An isolated offline local `0.3.1` wheel was built and installed under the disposable QA tree, preserving the shared environment; the same **7 registry manifest tests then passed** with the correct metadata.

The isolated wheel/sdist security packaging check **PASS** confirmed **75** public V1/V2 Python modules, **V3 excluded**, and enforced dependency floors. The separate V3 integration and the QA report live only in source checkout. The disposable QA helper import-lint issue was corrected. **Final full default repository run with the correct local 0.3.1 wheel metadata:** **3,213 passed, 0 failed, 15 opt-in integration tests deselected, three nonfatal warnings**, completed in 93.88 seconds. Full-repo Ruff: **PASS**. Four separately selected real stdio/HTTP integration tests, including **the new same-session V1+V2+V3 combined live test**, were run with opt-in marker and an isolated local cache: **4 passed, 0 failed**. Eleven other integration-marked cases were not rerun in this phase. GitHub exact-head checks must pass independently before merging.

**Latest bounded-CI revision (supersedes the earlier full-suite line):** the 595-pair real RPC stress is now an opt-in job, and five representative concurrent cross-family pairs run by default. The entire repository suite against isolated version-matched 0.3.1 metadata ran again: **3,213 passed, 1 explicitly skipped, 15 deselected, 0 failures, 3 nonfatal warnings** in 99.73 seconds; Ruff passed. The separate full 595-pair stress had already passed locally before that run. This avoids recurrent CI runner cancellations without removing the stress proof.

### Remaining limits and gates

1. **Not yet proof of an actual human productivity gain.** The benchmark proves a low-N, machine-specific startup/plan speed advantage and output equivalence; it does not establish faster independent human fact finding or more paying users. A human-blinded head-to-head with equal permissions/model and fixed external evidence is the next scientific gate.
2. **Live coverage isn't combinatorially exhaustive.** Every pair was routed with deliberately invalid arguments; only selected version-spanning positive public workflows were actually executed. Do not claim 595 independently useful business decisions.
3. **Source policy:** Wikimedia entity records have CC0 structured data scope; OSV mixes source licensing, so the two-tool V3 output remains narrow and fully attributed. Unverified legal rights for public/commercial bulk reuse and independent-review signoff are still gates.
4. **Google Trends:** RSS health does not establish 24-hour ranked/Explore availability. The AGENTS.md policy applies unchanged; no unofficial quota bypass or abusive retries were performed.
5. **Release:** the unified entrypoint is *source-only under `mjau_v3`*, requiring explicit local start. It does not enable a public/hosted 35-tool server, does not change current 33-tool live source, and does not alter worker scheduling.
