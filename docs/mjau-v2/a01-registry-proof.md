# MJAU v2 A01 — official MCP Registry discovery proof

**Status: IN PROGRESS / NOT ACCEPTED.** Isolated source proof only; no default MCP tool, shared CLI wiring, production change, release or scheduling. The A01 umbrella also includes other source-backed competitor types that are not implemented here.

**Isolation:** `feat/mjau-v2-discovery-a01-registry-20261121` based on exact original MJAU v1 staging SHA `b88b0a974b5dcdb480e4fd8c4da5f7bbca68e98e`. V3 owns different files and IDs. Never edit PR #328 or its draft children on behalf of this feature.

## Problem, baseline and sample

V1's `intelligence_idea_map.py` produces `competition: not_measured`. The official registry has a free, unauthenticated read-only server-name search using `GET /v0.1/servers?search=...&version=latest&limit=...`. It does **not** search capabilities or descriptions. A result is an independently traceable *candidate alternative*, not established functional equivalence, commercial demand, downloads or market share.

Official source documentation: https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/api/official-registry-api.md and https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/registry-aggregators.mdx . The Registry is preview-stage, with no uptime or durability guarantee. The official docs permit public, unauthenticated read access and recommend infrequent cached synchronization. Do not interpret this as an unrestricted license for all repository/server metadata.

An independent public web read (2026-11-21) of `https://registry.modelcontextprotocol.io/v0.1/servers` returned versioned records including `ac.inference.sh/mcp` version `2.0.1`, marked active/latest. That validates *a real provider response example*, **not this new adapter's actual network execution** and not that a specific query yields that record. No full discovery census was performed.

## Isolated component

- `src/mcp_trendpulse/mjau_v2/registry_competitors.py`: plan-only default, single-page, limited 1–15, query length 3–80, latest active filter, 128-KiB body ceiling, name-ID deduplication, allowlisted source URLs, explicit partial-results signal, no semantic similarity claims.
- Uses existing `intelligence_core.BudgetCache` only when explicitly executing, with **4/day local provider reservations**, 6-hour validated cache, 120-second cooldown on 429/503, no proxies, redirects, automatic retries, extra workers or paid endpoints.
- A cached result is validated again and unexpected source attributes are discarded; samples with rejected rows are not cached as complete evidence.
- No changes to `cli.py`, `intelligence_mcp.py`, `intelligence_core.py`, `intelligence_signal.py`, project dependencies, lockfiles, README, CI or other tracks.

## Evidence ledger

| Gate | Result | Interpretation |
| --- | --- | --- |
| Distinct utility | Candidate alternatives gain a registry name, version, repository link when present and exact primary-source link | Useful *kind of information* absent from v1's `competition: not_measured`, but no verified research-task uplift yet |
| Offline tests | **50 passed**, 0 failed, Python 3.13.5, pytest, isolated import; `PYTHONPATH=src pytest -q tests/test_mjau_v2_registry_competitors.py` | Covers input validation, current/latest metadata, dedup, limited first page, HTTP failures and cooldown, budget errors, secret-safe errors, cache replay/poisoning, source status and bounded transport with fake HTTP session |
| Real provider schema | Independent public web request returned source response with active latest version | Adapter real network call **not performed** |
| Full-repository regression/ruff | **Not run**; dedicated Codexify TrendPulse tunnel unavailable and this container lacks the full dependency suite | No claim that full CI is green |
| API use/cost | Public official registry GET, no key; local 4/day and six-hour cache | No paid dependencies; formal live availability and terms audit still open |
| Agent isolation | No shared core edits, no production/worker/PR #328 changes | Supports parallel v3 testing |
| Measured task uplift | **Not yet measured** beyond a minimal source-shaped offline comparison | Strict pass-or-discard gate remains **OPEN** |

## Decision and next bounded checks

**Decision: BLOCKED FOR ACCEPTANCE**, not ACCEPT and not DISCARD. Continue only with one real read from the new adapter (an exact three-result or smaller query), a zero-network cached replay, original current-source/terms verification, and five predeclared question-and-answer comparisons against v1, including no-signal and misleading-competitor cases. An adapter that is reliable but cannot improve actual research decisions must be discarded. Do not force network testing through a disconnected tunnel, bypass quotas, or start CI workflows solely to compensate.

**No claims of A01 completion, ready-to-merge integration, significant performance improvement, or full MJAU v2 production readiness.**
