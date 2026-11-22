# TrendPulse MJAU V2 - post-merge functional, bug and usefulness QA

Date: 2026-11-22. Baseline: merged main `c4ce899ab7eb75d206822c1ea5791187972ded19`.
Current work is confined to `qa/mjau-v2-postmerge-effectiveness-20261122`.
Separate V3, user agents, hosted/community catalog and production services remain untouched.

## What was *actually* exercised

This is not a claim of blinded human preference, higher conversions, better AI
reasoning, verified model quality, improved SEO traffic, commercial demand, or
frozen-spec MCP conformance. It is a preregistered, real MCP protocol
source-answer/cost benchmark plus deterministic red/green reliability QA.
The five user jobs and five counterclaim tests were fixed before source sampling:
`postmerge-user-workflow-benchmark-20261122.md`.

**Deployment/availability distinction:** a read-only check of Codexify's
existing upstream `mcp-trendpulse` showed the standard **16-tool connector
connected and healthy**; that is NOT the separately opt-in V2 **17-tool
intelligence MCP**. Our new optional server has been proven with independently
started real SDK stdio clients, but this audit has **not** registered or
enabled its tools in the live connector. This intentional activation boundary
is an outstanding *distribution/availability choice*, not a failed parser
test or authorization to restart users' services.

### Pass 1 - independent MCP user workflows (actual public sources)

A fresh Python MCP SDK client launched the opt-in FastMCP server as a
separate **stdio process**, initialized JSON-RPC, discovered exactly 17
read-only tools, and called five ordinary researcher tasks through the same
protocol used by a real MCP client:

| Real research question | Source | Result and accurate scope |
| --- | --- | --- |
| P1: what do this repo's recent GitHub star cohorts show? | GitHub A02 | observed_partial, 10 source weeks and descriptive cohorts; not historical net star growth |
| P2: exact `is-odd@3.0.1` direct dependencies? | deps.dev A03 | observed, verified root, 1 distinct direct dependency; not download counts |
| P3: published source Scorecard for `pallets/flask`? | OpenSSF B01 | observed, source scan 2026-11-09, 14 checks; not vulnerability verification |
| P4: Node.js 20 EOL and any maintenance caveat? | endoflife.date B02 | observed_partial, EOL 2026-04-30; commercial/extended support possible, caller entitlement unverified |
| P5: current public Hub model IDs? | Hugging Face A07 | observed_partial, two source IDs; gated flags unknown, source counters not proven adoption |

**5/5 source-scoped positive tasks returned grounded, caveated observations.**
The older V1 catalog had **0 of these five provider-specific read-only
tools**; that is a precise source-coverage comparison, **not** proof that a
human with V1 could never research these topics another way.

- Five plan-only MCP calls: zero SQLite/network source access by contract;
  p50 **71.222 ms**, p95 **74.540 ms**, end-to-end JSON-RPC roundtrip.
- Five live calls: **4 real source GETs** (GitHub, deps.dev, OpenSSF,
  endoflife.date) and one previously cached Hugging Face answer. The four
  source GETs took **2.36-3.60 seconds** end-to-end each.
- All five immediate repeats returned validated SQLite cache hits,
  **zero additional source GETs**.
- Following the singleflight patch, all five tasks were independently
  repeated through a fresh MCP stdio subprocess: **5/5 valid source answers,
  0 additional provider calls**; warm replies **42.764-51.540 ms**.
  This is cache speed, **not** source HTTP speed or a new improvement
  attributed solely to the lock patch.
- The measured MCP transport overhead is materially larger than the earlier
  0.1-ms in-process planning microbench. Report both with correct scope.

### What a researcher can act on from these real observations

- **Node.js 20 lifecycle:** the public source reports 2026-04-30 EOL.
  A deployment owner can check actual vendor/third-party support entitlement
  and plan a verified upgrade path; the tool correctly **cannot** promise
  that their installation receives paid maintenance.
- **Exact npm dependency mapping:** `is-odd@3.0.1` yielded one resolved
  direct dependency in the provider's generic Linux scenario. This tells a
  maintainer what dependency to investigate next, but cannot decide whether
  it is vulnerable or how many installations use it.
- **AI model shortlist:** two source-ranked public Hub IDs were returned
  without file downloads. These are candidates for a **manual quality,
  license and task-fit evaluation**, not recommendations to deploy or
  investments justified by the provider's current trending counters.

These are practical next research steps produced from real source facts,
not an independently blinded study of operator time savings.

Machine-readable source-shape/latency receipts:
`postmerge-plan-receipt-20261122.json`,
`postmerge-live-receipt-20261122.json`,
`postmerge-afterfix-receipt-20261122.json`.
Receipts retain public source IDs and source-derived dates only, no API keys,
private stargazer identities or downloaded model/dataset contents.

### Pass 2 - reproducible bug hunt (red -> green)

**Confirmed real bug in ALL FIVE V2 adapters:** two simultaneous identical
cacheable misses both consumed a free daily source reservation and issued
duplicate provider calls, despite V1 core already having per-key
cross-process singleflight. Five native SQLite+slow-fake-provider concurrency
tests reproduced **5/5 failures before the fix** (2 GETs each, expected 1).

Surgical repair: a shared `mjau_v2/singleflight.py` wrapper guards
`execute=True` behind the existing SQLite cache-root per-key file locks and
re-runs the source's validated cache lookup **inside** the lock. Distinct
requests use disjoint locks, as in V1 core. Plan-only never opens a
cache/lock/network. Failed locks fail closed as `unavailable` with zero
provider requests; no quota override, retry bypass, credentials, dependencies
or new service. If a caller intentionally injects a fake test cache with no
real database path, its existing test-double semantics remain unchanged.

- Same five cases now **5/5 GREEN**, with exactly one provider GET, one
  quota reservation and the other caller served from cache.
- Separate Windows **spawned-process** case also passed, confirming the
  SQLite-root file lock works beyond Python threads.
- Two different Hugging Face queries were proved to run concurrently,
  without a global provider lock or unnecessary serialization.
- HTTP 429 first response activated cooldown; a repeat made no HTTP request.
- Synthetic filesystem/lock error abstained without a source fetch.
- Five predeclared false-assurance cases passed: unknown stars not zero,
  unavailable dependencies not zero, unscored repository not insecure,
  post-EOL commercial eligibility not guaranteed, gated dataset metadata not
  permission to download or proof of customers.
- Seeded **2,500 malformed provider envelope** inputs across all five
  parsers produced zero unhandled exceptions. They are structured random
  malformed inputs, not a formal proof of absence of all vulnerabilities.
- A fresh independent SDK subprocess ran the existing broader MCP
  acceptance: **11/11 protocol/permissions/redaction checkpoints passed**
  with zero paid/source requests in plan-only mode.
- Before the full repository run, **310 source-focused tests**, **19 new
  concurrency/abstention/fuzz checks** and **45 MCP+entrypoint tests**
  passed independently.

Expected safety constraints preserved: 4/free-source UTC-day local caps,
bounded transport bodies, allowlisted HTTPS origins, no redirects or
automatic retries, validated SQLite replay, source provenance and
unknown-vs-zero distinctions. Existing `BudgetCache` is reused; neither
the database schema nor the worker/scheduler is modified.
Noncacheable provider failures (notably HTTP 404) can still be queried
again after the first lock holder completes. We deliberately did not
introduce persistent negative caching that could misstate newly available
data; bounded source quotas and 429/503 cooldown remain in force.

### Pass 3 - integration and protected CI gates

On the isolated QA branch after the last source change:

- **Full Windows Python 3.13 repository suite: 2,819 passed, 10 intentionally
  deselected, 3 existing warnings, 0 failed, in 289.62 seconds.**
- Whole-project Ruff clean; unchanged 135-package `uv lock --check --offline`
  clean. The source lock helper introduces no new dependency.
- Independent SDK MCP stdio handshake/discovery/calls: **11/11 passed**.
  The optional catalog still has **17 read-only tools**; the standard
  community and hosted catalogs are unchanged.
- The initial GitHub CI head `e2662caf` correctly **FAILED** the new
  multiprocess test on Linux (all Python 3.11-3.14 jobs) while its other
  **2,818** tests passed. The test initially used Windows-compatible
  `multiprocessing.get_context("spawn")`, but the Linux pytest-imported
  `tests.*` module was not importable to its spawned child
  (`ModuleNotFoundError: No module named 'tests'`). The production V2
  implementation was not implicated. The fixture now tests separate Linux
  processes through the supported POSIX `fork` context and preserves
  actual Windows `spawn`; the corrected local Windows multiprocess/thread
  QA is **9/9 passed**. Do **not** count failed initial CI as green;
  the corrected latest-head CI must still prove the fix.

The remaining release gate is the **exact latest-head protected GitHub
Python 3.11-3.14, package validation, MCP, and Docker CI**, plus an explicit
post-merge main check. **Do not declare those gates passed or merge until
they are independently verified.**

## Effectiveness interpretation

- **Positive workflow source coverage: 5/5** in this predeclared sample.
- **No false reassurance: 5/5** negative cases in deterministic fixtures.
- **Free quota efficiency:** two identical concurrent queries changed from
  2 source calls before fix to 1 after fix (50% fewer calls *for this
  exact concurrency scenario*, not across all workloads).
- **Warm response:** around 43-52 ms through a real MCP stdio client with
  existing validated cache, 0 new GETs.
- **Limits:** five selected tasks do not estimate global user satisfaction,
  conversion, willingness to pay, all-country availability, or future
  uptime. Provider-specific source statuses can become stale or unavailable;
  the tool must abstain rather than invent missing evidence.

## Official evidence and independent reproduction

- GitHub star-history REST API and provider-week semantics:
  https://docs.github.com/en/rest/activity/starring?apiVersion=2026-03-10
- deps.dev resolved graph scope: https://docs.deps.dev/api/v3/
- Published OpenSSF scorecards: https://api.scorecard.dev/
- endoflife.date v1 source support semantics:
  https://github.com/endoflife-date/endoflife.date/blob/master/api_v1/openapi.yml
- Hugging Face official public API and rate limits:
  https://huggingface.co/docs/hub/api
  https://huggingface.co/docs/hub/rate-limits
- MCP official conformance project (not claimed passed in full):
  https://github.com/modelcontextprotocol/conformance

**Change/release policy:** update only this V2 patch, regression tests,
a small independent MCP benchmark script and this evidence. No V3 work,
production restart, manual-dispatch GHCR, PyPI release or paid compute.
