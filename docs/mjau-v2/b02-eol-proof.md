# MJAU v2 B02 — End-of-life / support-cycle evidence proof

**State:** TECHNICAL AND SOURCE USEFULNESS PROOF OBSERVED; **NOT ACCEPTED INTO PUBLIC MCP, NOT MERGED OR RELEASED**.  
**Branch:** `feat/mjau-v2-discovery-b02-eol-20261121`, from v1 MJAU draft base `b88b0a974b5dcdb480e4fd8c4da5f7bbca68e98e`. No v1 or v3 edits.  
**Scope:** `src/mcp_trendpulse/mjau_v2/endoflife_release.py`, B02 tests, package marker and this report. No shared CLI/MCP, lockfile, dependency, worker, automation or production change.

## Why this is a distinct useful observation

MJAU v1 and v2 A02/A03 cover attention, downloads, developer issues and dependencies—not product **support-phase and end-of-life dates**. The key new question is: *For a specific named software release cycle, what end-of-active-support versus end-of-life dates are actually published?* End-of-support changes may motivate migration investigation, **not verified demand, revenue or permission for automated migration**.

Free public API: https://endoflife.date/docs/api/v1/ ; open source with MIT license and a versioned public v1 contract. Product evidence is community-curated; verify original vendor docs for consequential upgrades or compliance.

**Actual native-source checks on 2026-11-21** — exact one release per GET, official v1 JSON, original v1 SQLite BudgetCache with **isolated temporary directory**, one request per item then zero-network validated cache replay:

| Source release | EOL flag | End active support flag | Maintained flag | Recorded EOL date | Calendar days to published EOL (at 2026-11-21 UTC) |
| --- | --- | --- | --- | --- | --- |
| `nodejs` release `22` | false | true | true | 2027-04-30 | 160 |
| `python` release `3.12` | false | true | true | 2028-10-31 | 710 |

Source version \`1.2.1\`, generated \`2026-11-21T00:08:00+00:00\`; source links <https://endoflife.date/api/v1/products/nodejs/releases/22> and <https://endoflife.date/api/v1/products/python/releases/3.12>.

**Important:** \`isEoas=true\` and \`isEol=false\` with \`isMaintained=true\` are *not* contradictory. Active support ending is not identical to total end-of-life; maintenance may continue under extended/security support. The adapter preserves these separate provider facts rather than creating a single unsupported label or an inferred urgency score.

## Engineering and proof record

- **Plan-only by default:** no network/cache. Fixed HTTPS \`endoflife.date/api/v1/products/<product>/releases/<release>\`; exact validated product slug and release identifier; no redirects (renames become explicit \`rename_redirect_not_followed\`), proxy, retries or credentials.
- Separate v2 default cache at \`~/.mcp-trendpulse/mjau-v2-intelligence\`, opt-in \`execute=True\`, four daily provider GET reservations, 24h sanitized cache, 64KiB response cap and 429/503 cooldown.
- Validates v1 JSON envelope, schema version, timezone-aware data-generation timestamp, exact release name, explicit independent EOL/EOAS/EoES/LTS/maintained booleans and date-only fields. Unknown date remains null, not day zero. Stale source over 30 days is visibly \`observed_stale\` and not cached as fresh.
- HTTP 404 is \`not_found\`, not evidence that an unknown software is unsupported. Other errors, including 429, never become a false EOL observation.
- No raw provider custom fields, secrets or marketing text stored as evidence.

| Gate | Outcome |
| --- | --- |
| Offline committed test bodies | **54/54** executed with Windows Python 3.13 \`-S\` and minimal stdlib pytest-compatible test runner; **not** a full authentic pytest invocation |
| Native real API and cache | **2/2** release cycles returned observed, source-attributed results, one original-source GET then a zero-network SQLite replay each |
| Temporary cleanup | Python exit 0 and separate SQLite temp cache removed successfully |
| New useful evidence class | Published status, phase and dates, distinct from versioned downloads and dependencies |
| Negative cases | Missing dates, contradictory types, unknown releases, invalid calendar dates, future timestamps, stale source, redirect, 404, 429, 503, cache poisoning and secret-safe failures tested |
| Full repository regression/Ruff | **Not run** (Windows pytest import stall and Ruff not available on PATH); required before release |
| Licence and data-reuse | Free public endpoint and MIT open-source dataset, but confirm specific publisher data attribution/terms and vendor cross-check requirements before commercial integration |
| Current decision | **PROOF-OF-VALUE PASS / FINAL ACCEPTANCE PENDING** — independent review and full compatibility/lint still required |

## Stop/discard rule

Do not add B02 as a global tool merely because it returns dates. Benchmark whether release-cycle questions become more accurate and actionable than v1 while avoiding misleading migration urgency. Verify one case with primary vendor documentation, run full tests, check large-product response limits and correct interpretation of support phases. A feature that cannot pass those gates is **DISCARDED**, not retained as an unused endpoint.

## Authentic v2 pytest/Ruff verification — 2026-11-21 (supersedes older “not run” lines)

- **Actual project toolchain**, not a mocked pytest shim: venv **pytest 9.1.1**, **Ruff 0.12.1**, Windows, focused source and test staged in a separately scoped temporary directory; production and active v1 tree were untouched. The tested isolated source commit was `523252f3d357f9bdbda2bcf909571c09f9373cb7`.
- **Focused tests:** **54/54 PASSED**, no focused failures. **Ruff:** **ALL CHECKS PASSED** for the source and its committed tests.
- **Test note:** Real pytest 54/54 and Ruff clean after fixing E701 in the test helper (commit d20e970abf0149dc3ae8f310b6073d4f859a67f1).
- **Existing v1 compatibility baseline** (unchanged checkout `b88b0a974b5dcdb480e4fd8c4da5f7bbca68e98e`): 11 selected MJAU/evidence test modules produced **258 passed and 1 timing-sensitive failure** in `tests/test_intelligence_singleflight.py::test_different_queries_still_fetch_in_parallel` under concurrent machine load. That exact unchanged failing assertion **passed** on an isolated rerun. The result is NOT a single fully green broad regression and NOT the full repository suite. The 15 async tests failed on an earlier runner with `pytest-asyncio` disabled; all passed after the installed plugin was explicitly loaded. No source code regression was attributed to the new v2 adapters, because they have **not** been wired into v1.
- **Still required for inclusion:** a single integration-owner review on current v1 contracts, correct free-source license/attribution, independent decision usefulness and false-positive comparison, no material CPU/RAM/latency regression, and a successful combined regression on the *final merged commit*. **Strict prove-or-discard still applies.**

## Source contradiction correction and updated release gate (2026-11-21)

The independent prospective Node.js 20 case surfaced a **real provider inconsistency**, not a test-fixture inconsistency: the official endoflife.date v1 endpoint returned `isEol=true`, `isMaintained=true`, with the published EOL date `2026-04-30`. The original Node.js project schedule agrees with that EOL date, but the endoflife.date OpenAPI defines `isMaintained` as some level of support; those flags should not be silently combined into "supported."

- B02 source commit `3c3328774a416e250713ad05d659ab37792bac0c` explicitly labels `provider_phase_conflicts=["eol_true_but_maintained_true"]`, sets `provider_phase_consistent=false` and returns `status=observed_partial`. Partial conflicting records are **not persisted as fully validated cache evidence**.
- Test commit `b6fa98ad1ed4ab99d7be66fd096c96fa2e5b332c` covers that contradiction, calendar/flag inconsistency and consistent-source baseline. **57/57 authentic pytest passed, Ruff passed.**
- One live native adapter GET against `nodejs/20` confirmed `observed_partial` with the exact conflict tag; **exit 0**, separate test cache removed.
- Combined A01/A02/A03/A07/B01/B02 isolated suite with updated B02: **342/342 authentic pytest cases passed, Ruff clean**, against locally observed v1 `876957a874e4bc81c0470095254b5a6b0b189397`; local v1 HEAD remained fixed and checkout clean throughout the test. This is a focused compatibility check, **not the final shared-MCP integration test**.
- Prospectively scored usefulness: 2 date/phase positive records consistent, one EOL date independently corroborated but support flags conflict, unknown release 404 not a fabricated deadline, no automatic buying/migration urgency. See `docs/mjau-v2/b02-usefulness-protocol.md`.

**Decision remains BLOCKED FOR FULL ACCEPTANCE**, although the bounded lifecycle-date lookup is useful. Before inclusion establish a conservative UI policy for provider conflicts and verify primary vendor dates; never output an unconditional "maintained" label from a conflicted source.

Source provenance: https://endoflife.date/api/v1/products/nodejs/releases/20 ; https://github.com/nodejs/Release/blob/main/schedule.json ; https://github.com/endoflife-date/endoflife.date/blob/master/api_v1/openapi.yml .
