# MJAU v2 A03 — deps.dev resolved dependency intelligence, proof ledger

**Status (2026-11-21): PROOF OBSERVED / FULL ACCEPTANCE STILL GATED.** Selected-for-proof, not merged or released.
**Owned files:** `src/mcp_trendpulse/mjau_v2/depsdev_graph.py`, `tests/test_mjau_v2_depsdev_graph.py`, package marker and this report; **no edits** to v1, v3, CLI, MCP registration, common schemas, CI, dependencies, workers or lockfiles.
**Pinned base:** v1 draft PR #328 commit `b88b0a974b5dcdb480e4fd8c4da5f7bbca68e98e`.
**Latest isolated proof:** commit `48e4913aded0287136b5ba350dc7b2a523865ac9`. Note earlier source at `433710151d318e2ed3def980de4417e0a79d7a15` was used for native live results; the only subsequent change was isolating the default cache root. Retest latest commit before final acceptance.

## Distinct decision utility

Existing MJAU M09/M10 draft additions measure **package downloads**, not exact package dependency graph relationships. Google's deps.dev v3 resolved graph provides versioned **dependency edges** and direct/indirect relationships for npm, PyPI, Cargo, and Maven. This is a genuinely different measurement class useful for package assessment and competitor context; it is **not** a market-share, users, installs, project dependents or revenue metric.

Examples (real original-source observations, 2026-11-21):

| Question | V1 download-history response | A03 deps.dev evidence | Limitation |
| --- | --- | --- | --- |
| What directly resolves from npm `is-odd@3.0.1`? | Package-download aggregate cannot answer dependency edges | Resolved dependency `is-number`, 2 version nodes, 1 edge | Source corresponds to a generic 64-bit Linux resolver; not all consumer installations |
| Does PyPI `colorama@0.4.6` resolve a dependency in the provider graph? | Download count cannot answer | 1 root node, 0 graph edges | Zero is specific to this exact version/provider graph, not proof of no use or demand |
| Can these records prove package adoption growth? | Downloads offer a *different* scoped measurement | Explicitly NO: graph has no users/downloads/revenue counts | Preserve metric unit/source identity |

**Provider documentation:** https://docs.deps.dev/api/v3/. Generated deps.dev data is published CC BY 4.0 and caching is expressly permitted; original upstream source data carry separate terms and Google's API terms apply. A brief commercial reuse/attribution review is still required before exposing an aggregator's outputs beyond their factual metadata.

## Safety and behavior

- Plan-only default performs **zero** network/cache operations; execution must be explicit.
- Validates a concrete source ecosystem, package and version; percent-encodes scoped npm names and Maven coordinates; only allowed host `api.deps.dev`, HTTPS and fixed path; no redirect, environment proxy or retry.
- Applies conservative 128-KiB response, 512-node and 2048-edge ceilings. Too large/malformed/unavailable is **NOT** represented as an empty dependency graph.
- Graph root must match the requested ecosystem/package/version. An actual first-run falsification test discovered an unrelated-root acceptance bug; fixed with ecosystem-specific canonical name checks and an exact version requirement. No cross-ecosystem join or case-insensitive Maven alias guess.
- All nodes, graph indices, relations, edge references, errors and numeric values are checked. Duplicate graph nodes remain separate from distinct version keys. A resolution error is reported as **partial**, never complete; partial graphs are not cached as full evidence.
- Cache stores only normalized, whitelisted graph data and revalidates on reuse. 12-hour TTL and local 4-request/day provider reservation; HTTP 429/503 opens local cooldown.
- The default v2 research cache is **separate from v1**: `~/.mcp-trendpulse/mjau-v2-intelligence` (but tests use isolated temporary caches). Does not touch original Windows v1 request-lock ACL state or the v3 cache.

## Evidence and test record

| Gate | Observed result | Status |
| --- | --- | --- |
| Independent source schema | Official deps.dev v3 docs + real two-ecosystem HTTP JSON responses | PASS (feasibility) |
| Offline unit cases | **65/65 case bodies passed** from the committed test file using a standalone Python 3.13 `-S` compatibility runner (pytest decorators/raises/monkeypatch shim) | PASS (not a full pytest invocation) |
| Python parse/compile | `python -S -m py_compile` on actual isolated source | PASS |
| Initial root-falsification run | Failed 1 of 7 checks because an unrelated package root was accepted | BUG FOUND AND FIXED |
| Re-run after root fix | **7/7** standalone assertions, including two real HTTP calls and zero-network cached replays | PASS |
| Native adapter and original v1 SQLite BudgetCache | **npm:** status `observed`, one network GET, then cache replay; 1 distinct direct dependency, ~6.41s one-shot. **PyPI:** status `observed`, one network GET then replay; 0 direct dependencies, ~0.18s one-shot. Uses actual adapter `requests` path and original v1 SQLite class with isolated temporary root | PASS on pre-cache-path-change commit (same parsing/fetch) |
| Temporary cleanup | Native test process exited zero and temporary SQLite directory cleaned after Python exit | PASS |
| Full pytest and full-repo regression | Windows machine's normal pytest import hung, process was terminated without modifying source; standalone test-function runner was used instead | BLOCKED / NOT RUN |
| Ruff | No standalone `ruff` executable on PATH in tested Windows shell; not installed simply to pass a gate | NOT RUN |
| Predeclared five-case real decision-usefulness benchmark | Preliminary distinct question proof above, but full five-case scoring and independent reviewer not completed | INCOMPLETE |
| Licenses, resource budgets | Free read API, official data attribution available, 4/day local quota and bounded response; no payment, cloud project or API key used | TECHNICAL PASS; COMPLIANCE REVIEW OPEN |
| Code integration | Private branch only; no shared MCP, dependencies, CI, worker, scheduled tasks or production change | PASS |

## Required objective decision

This research feature is **NOT ACCEPTED INTO THE FINAL PRODUCT** until the strict mandatory proof-or-discard gate is satisfied: run latest commit through an authentic pytest or equivalent independent validation, inspect Ruff/full v1 regressions, complete a five-case predeclared source-backed usefulness comparison against v1 M09/M10, assess edge cases in source terms and graph sizes, and record adverse cases. A clear duplicate, unreliable source or failed usefulness comparison means **DISCARD and do not merge**, not "keep just in case".

No automatic schedulers, global MCP tools, live trading, paid services or code copied from licensing-incompatible projects.
