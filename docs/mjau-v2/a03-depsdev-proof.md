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

## Authentic v2 pytest/Ruff verification — 2026-11-21 (supersedes older “not run” lines)

- **Actual project toolchain**, not a mocked pytest shim: venv **pytest 9.1.1**, **Ruff 0.12.1**, Windows, focused source and test staged in a separately scoped temporary directory; production and active v1 tree were untouched. The tested isolated source commit was `48e4913aded0287136b5ba350dc7b2a523865ac9`.
- **Focused tests:** **65/65 PASSED**, no focused failures. **Ruff:** **ALL CHECKS PASSED** for the source and its committed tests.
- **Test note:** Real pytest 65/65 and Ruff clean with updated isolated cache-default source; no new root identity mismatch failures.
- **Existing v1 compatibility baseline** (unchanged checkout `b88b0a974b5dcdb480e4fd8c4da5f7bbca68e98e`): 11 selected MJAU/evidence test modules produced **258 passed and 1 timing-sensitive failure** in `tests/test_intelligence_singleflight.py::test_different_queries_still_fetch_in_parallel` under concurrent machine load. That exact unchanged failing assertion **passed** on an isolated rerun. The result is NOT a single fully green broad regression and NOT the full repository suite. The 15 async tests failed on an earlier runner with `pytest-asyncio` disabled; all passed after the installed plugin was explicitly loaded. No source code regression was attributed to the new v2 adapters, because they have **not** been wired into v1.
- **Still required for inclusion:** a single integration-owner review on current v1 contracts, correct free-source license/attribution, independent decision usefulness and false-positive comparison, no material CPU/RAM/latency regression, and a successful combined regression on the *final merged commit*. **Strict prove-or-discard still applies.**

## Canonical package/version identity — 2026-11-21

**Fixed and verified in isolated A03 source commits `637c168e780a1c85817aa21fa16fe4e8b9b59bb9` and `8c81d541070625e2f20cf731c85b608c06c461bf`; tests `3a0023db1c99fef21293baf833ce9fe886de36ae`.**

Official deps.dev v3 `GetDependencies` documentation explicitly states the provider can return a normalized package **or version** identity that differs from the request. The original A03 rejected all version changes, even when they are canonical equivalent forms.

- Scoped correction: request PyPI `Colorama@0.04.6` returned source root `PYPI:colorama@0.4.6`, a legitimate PEP 503 name alias plus PEP 440 numeric release normalization. The adapter now accepts only exact versions, or **simple numeric PyPI releases with equal component integers, allowing PEP 440 zero-padding**. No new dependency or generic SemVer parser. All npm/Cargo/Maven version changes, PyPI prerelease/postrelease/local ambiguity or unrelated names remain untrusted.
- Accepted canonical roots explicitly retain the *requested* identity separately from the *provider-returned* canonical root and set `provider_root_canonicalized=true`. They never silently rewrite source provenance. A structurally valid graph with an unproven version alias returns **`status=identity_unverified`**, `summary=null`, `not_evidence_for_requested_version=true`; it cannot be cached as a complete dependency observation.
- All edges and node identities are validated **before** reporting identity-unverified, so an invalid graph cannot masquerade as a well-formed version alias. A root with unrelated ecosystem/package remains invalid source shape.
- **77/77 authentic pytest cases passed**, Ruff clean. Native Windows adapter against **actual deps.dev GET** for `Colorama@0.04.6`: `status=observed`, returned root `colorama@0.4.6`, one network request (**4.600 seconds**), valid v1 SQLite cache replay with **zero additional network**. Peak tracemalloc Python allocations ~**3.689 MiB** (not full process RSS). The independent temporary SQLite directory was removed successfully.

Source provenance:
- https://docs.deps.dev/api/v3/ (`GetDependencies`, canonicalized provider version keys)
- https://packaging.python.org/en/latest/specifications/name-normalization/
- https://packaging.python.org/en/latest/specifications/version-specifiers/
- https://api.deps.dev/v3/systems/pypi/packages/Colorama/versions/0.04.6:dependencies

**Gate status:** The concrete root canonicalization defect is **RESOLVED** for demonstrated, tightly constrained PyPI numeric aliases. Non-provable identities are deliberately **INCONCLUSIVE**. Other A03 constraints remain: generic-Linux scope, limited graph size, source attribution, independent decision utility and final merged MCP regression. This fixes one technical blocker, not global acceptance.
