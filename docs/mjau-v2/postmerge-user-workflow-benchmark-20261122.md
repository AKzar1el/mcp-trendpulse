# MJAU V2 post-merge user-workflow and reliability benchmark

Date: 2026-11-22. Base: `main` commit `c4ce899ab7eb75d206822c1ea5791187972ded19`.
This protocol is fixed **before** this round's provider calls and defect repairs.

## Scope and credibility

Question: Does the independently started optional 17-tool market intelligence MCP give
better source-grounded answers for five concrete research jobs than the merged V1
capability set, without false assurances or unbounded network/latency costs?

This is *technical and source-coverage usefulness*, not blinded human preference
testing, real user adoption, increased sales, or measured business productivity.
A missing provider response is `unavailable/unknown`, never an incorrect zero.
No paid provider, API token, private data, browser scraping, bulk feeds, model
weights, new worker, V3, or production restart is permitted.

## Five source-positive tasks (P1-P5)

- P1: What do recent public GitHub repository stars show for
  `AKzar1el/mcp-trendpulse`? Source: A02; source-scoped weekly cohorts
  and limitation that present-day surviving stars are not historical net growth.
- P2: What direct/resolved dependencies does exact npm `is-odd@3.0.1`
  have in the generic deps.dev Linux resolver? Source: A03; verified
  root identity, bounded direct preview; no installs or buyers inference.
- P3: Does OpenSSF publish a recent Scorecard for `pallets/flask`?
  Source: B01; published scan date, inconclusive checks, not a vulnerability audit.
- P4: What is the reported Node.js 20 EOL and what does
  post-EOL `isMaintained` mean? Source: B02; report EOL date if
  supported, distinguish commercial/extended availability from entitlement.
- P5: Name two public trending Hub model IDs and their provider-defined
  counters. Source: A07; no historical growth, model quality or licenses implied.

For each task score (1) source-specific answerable, (2) provenance, (3) bounded
execution, (4) no unsupported business/safety implication, (5) repeated
call zero extra GET if first is validated/cached. Record original source status
and any unavailable/partial/unknown separately rather than counting as a pass.

## Five negative/abstention tasks (N1-N5)

- N1: Incorrect GitHub repo name cannot be interpreted as zero stars.
- N2: Unknown deps.dev package/version cannot be treated as verified zero dependencies.
- N3: No published Scorecard is not proof the repository is insecure.
- N4: EOL with commercial support possible never confirms support contract.
- N5: A gated Hugging Face model entry cannot be downloaded or promoted
  to verified quality/customer demand by a metadata query.

## Cross-cutting passes

**Pass 1**: fresh independent MCP SDK stdio client, discover read-only catalog,
run all five plan-only workflow calls and inspect result contract, latency and
zero network/cache mutation. Execute one permitted bounded public query per
source where budget/availability permits; repeat once; compare the source facts
and missingness to vendor/provider semantics. Baseline: V1 has no source-specific
function for these tasks; general research may still use existing broader
source tools. Report source-specific answer coverage, not invented time savings.

**Pass 2**: seeded malformed-source fuzz, cache-poison resistance, strict input
and secret-leak tests, quota race with two concurrent identical requests,
transient errors, stale data, and clean disposal. A failed concurrency
singleflight test is a real defect if identical simultaneous calls spend
two local reservations for one research answer.

**Pass 3**: full local regression, Python 3.11-3.14 protected CI,
real independent MCP stdio, source budget/backoff checks, and container
smokes. Compare latency p50/p95 and overhead; repair only measured defects.

## Official source baselines

- https://docs.github.com/en/rest/activity/starring?apiVersion=2026-03-10
- https://docs.deps.dev/api/v3/
- https://api.scorecard.dev/
- https://github.com/endoflife-date/endoflife.date/blob/master/api_v1/openapi.yml
- https://huggingface.co/docs/hub/api
- https://huggingface.co/docs/hub/rate-limits
- https://github.com/modelcontextprotocol/conformance

Record source timestamps and the actual **observable** result. Source API
references do not certify reliability or entitlement. No PR/merge until
reproduction, explicit tests, and protected checks are green.
