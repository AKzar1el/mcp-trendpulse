# MJAU v2 B01 — OpenSSF Scorecard research proof

**State:** SOURCE AND DISTINCT-UTILITY PROOF PASSED; FULL PRODUCT ACCEPTANCE PENDING. **Not merged, released, deployed or registered in public MCP.**  
**Owner:** v2 discovery track, separate from v3 and original MJAU v1.  
**Base:** pinned v1 draft SHA `b88b0a974b5dcdb480e4fd8c4da5f7bbca68e98e`.  
**Proof files:** `src/mcp_trendpulse/mjau_v2/openssf_scorecard.py`, `tests/test_mjau_v2_openssf_scorecard.py`, marker and this report.

## Independent source and usefulness

The free official OpenSSF published Scorecard endpoint supplies dated **security-maintenance checks per repository**, not adoption or dependency measurements. The v1 package/download/issue evidence and v2 A03 dependency graphs do not supply this exact repository security check vector.

**Real source observations on 2026-11-21 (native adapter using real Windows \`requests\`, existing v1 \`BudgetCache\`, separate temporary cache directory):**

- `GET https://api.scorecard.dev/projects/github.com/ossf/scorecard` -> **HTTP 200**; scan \`2026-11-21T01:38:51Z\`, aggregate source score **8.8/10**, **18 named checks**. The assessed commit was `b62c617675f5dd81ba2bf89a065040559f92f8d7`. The latest source snippet included Code-Review 4, Security-Policy 10 and Maintained 10. The aggregate is a *risk signal*, never an absolute guarantee of security or a vulnerability exploit assessment. <https://api.scorecard.dev/projects/github.com/ossf/scorecard>
- Identical second call: **validated SQLite cache hit, zero additional provider request**.
- `GET https://api.scorecard.dev/projects/github.com/AKzar1el/mcp-trendpulse` -> **HTTP 404 / not_covered**, \`aggregate_score=null\`, **not** a zero score or an assertion that this repo is insecure. This example directly demonstrates correct noncoverage handling; no score inferred or invented.
- Native process **exit 0**, temporary SQLite directory cleaned after interpreter exit. No production v1 cache/tunnel/worker/agent modified.

**Usefulness delta:** Source-backed per-check scores, dated repo commit and no-score coverage distinguishable from v1 development demand/download evidence. This makes a real competitor due-diligence question answerable: *What public security-health signals are available for this exact repository, and when were they measured?* It does **not** establish market opportunity, customer pain, commercial adoption, or a trustworthy binary secure/insecure ranking. Always use the published source link, score and check coverage with uncertainty.

## Technical safety and testing

- Default plan-only mode: zero network/storage; explicit \`execute=True\` required. Fixed \`api.scorecard.dev\` HTTPS endpoint; no redirects, env proxy, retries, credentials or cloud billing.
- Existing v1 \`BudgetCache\` reused **with separate default root** \`~/.mcp-trendpulse/mjau-v2-intelligence\`. Source cap 4 requests per UTC day, successful cache TTL 24 hours, 96-KiB body max, 120-second cooldown on 429/503.
- Exact repo identity + 40-hex commit and timezone-aware scan date checked. Source tool version required; up to 40 unique named check scores, scores -1 mean **inconclusive** (reported \`null\`), not numeric zero. Scan older than 30 days becomes visibly stale. Raw check reasons/details and unexpected provider metadata are not echoed or cached.
- HTTP 404 returns \`not_covered\`; 401/403/500 unavailable; malformed data invalid; a rate limit never becomes a negative-security finding.

| Gate | Result |
| --- | --- |
| Offline committed test cases | **52/52 actual focused test function cases passed**, 0 failed, on Windows Python 3.13 \`-S\` with minimal standard-library \`pytest\` compatibility shim; **not** an authentic pytest run |
| Regression bug | Fixed fractional-second date comparison: a scan in the same second before observation must not be rejected as future; dedicated test passed |
| Real source | Scored repo + unscored repo with respective 200 and 404 outcomes, native requests + actual v1 SQLite cache |
| Cache and cleanup | Normal cache replay verified with zero network; interpreter exit and temporary cleanup both passed |
| Independent decision usefulness | Demonstrated novel source-backed security-check vector and honest noncoverage |
| Full repository tests and Ruff | Not run due Windows pytest import stalling and Ruff absent on PATH; must be independently verified before release |
| License and terms | Official public read API and no billable requirement; check API data-reuse and attribution terms for commercial research output before publication |
| Code isolation | Only isolated v2 source/tests/docs; no edits to v1/v3, shared schema/CLI/MCP, workers, lockfile, releases or production |

## Strict pass-or-discard decision

**KEEP AS A PROVEN-USEFUL EXPERIMENT, NOT ACCEPTED FOR MERGE.** Require a five-case prospective decision benchmark on at least one additional scored and one missing/stale/low-information repository; compare evidence against any deps.dev Scorecard metadata to ensure it is not redundant. Run authentic pytest/full v1 regressions, lint, resource checks and license review. If redundant, unreliable, misleading or too costly to maintain, **DISCARD** rather than carry an unused public MCP tool. One final integration owner handles all shared wiring after v1 settles.

## Authentic v2 pytest/Ruff verification — 2026-11-21 (supersedes older “not run” lines)

- **Actual project toolchain**, not a mocked pytest shim: venv **pytest 9.1.1**, **Ruff 0.12.1**, Windows, focused source and test staged in a separately scoped temporary directory; production and active v1 tree were untouched. The tested isolated source commit was `982d79f1fcc3553770748d743de6cf5dda416d7e`.
- **Focused tests:** **52/52 PASSED**, no focused failures. **Ruff:** **ALL CHECKS PASSED** for the source and its committed tests.
- **Test note:** Real pytest 52/52 and Ruff clean after fixing E701 in the test helper (commit 46b22d187adcb9d165df131e5cd35d46a65e978c).
- **Existing v1 compatibility baseline** (unchanged checkout `b88b0a974b5dcdb480e4fd8c4da5f7bbca68e98e`): 11 selected MJAU/evidence test modules produced **258 passed and 1 timing-sensitive failure** in `tests/test_intelligence_singleflight.py::test_different_queries_still_fetch_in_parallel` under concurrent machine load. That exact unchanged failing assertion **passed** on an isolated rerun. The result is NOT a single fully green broad regression and NOT the full repository suite. The 15 async tests failed on an earlier runner with `pytest-asyncio` disabled; all passed after the installed plugin was explicitly loaded. No source code regression was attributed to the new v2 adapters, because they have **not** been wired into v1.
- **Still required for inclusion:** a single integration-owner review on current v1 contracts, correct free-source license/attribution, independent decision usefulness and false-positive comparison, no material CPU/RAM/latency regression, and a successful combined regression on the *final merged commit*. **Strict prove-or-discard still applies.**
