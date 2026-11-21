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

## Source-date compatibility fix and native verification (2026-11-21)

OpenSSF's official Scorecard MCP documentation confirms that the published REST API scan `date` appears in **either full RFC 3339 datetime or date-only `YYYY-MM-DD` form**. The original B01 adapter wrongly rejected valid date-only assessments. This is not a conjectural edge case: the real `pallets/flask` and `psf/requests` scores returned date-only values.

- **Source fix:** `9f178a4ee803ffc15d4bad175eaea3e08de4992b`. Date-only scans now set `source_scan_date` to the source day, `source_scan_precision="date"` and `source_scan_at=null`, avoiding fabricated midnight/UTC precision. Fully timestamped scans preserve timezone-aware time and `source_scan_precision="timestamp"`. Invalid/future dates fail closed, and the sanitized cache retains the original level of precision.
- **Test fix:** `344e4a2c4e854a55137570560008ce3857485e81`. Authentic pytest **59/59 passed** and Ruff clean, including date-only, valid cache replay, calendar invalidity, timestamp conversion and unreported-check unknown semantics.
- **Real native Scorecard+SQLite:** `pallets/flask` returned status `observed`, score **7.1**, 14 source checks, scan date **2026-11-09** (day precision), live GET **8.603s**, cached replay **0.110s**. `psf/requests` returned score **7.9**, 14 source checks, scan date **2026-11-16**, live GET **2.640s**, cached replay **0.066s**. Each replay did **zero provider GETs**, native process exited 0 and isolated cache was removed.
- Peak **tracemalloc Python allocations ~3.706 MiB** in the two-repo test process. This does NOT represent peak full process RSS. Two observations do **not** establish p50/p95 true network latency or overall production memory.
- **Coverage truth:** returned check count is the number reported, not all possible Scorecard checks. `full_check_coverage_verified=false`, `unreported_checks_are_unknown=true`; false/inconclusive/missing checks remain distinct. Repository score remains a dated **heuristic security signal**, not certification or verified vulnerability information.
- The official project now also publishes its own lightweight read-only stdio MCP provider. That is an alternative to consider during one-owner integration, but its Go binary and additional tool registration may not fit the intentionally minimal 8-GB machine. **Do not install it automatically** or duplicate its functionality without measuring net value.

Official sources: https://github.com/ossf/scorecard/blob/main/docs/mcp.md ; https://github.com/ossf/scorecard/blob/main/README.md ; https://api.scorecard.dev/projects/github.com/pallets/flask ; https://api.scorecard.dev/projects/github.com/psf/requests.

**Decision:** B01's date-only correctness gate is now verified; keep it as a **provisionally useful isolated adapter**, not merged. The integrated MCP, broader performance distribution and single-owner review remain open.

## First-party OpenSSF MCP overlap decision — 2026-11-21

**Authoritative comparison:** The official experimental `ossf/scorecard` MCP exposes **five read-only tools** (`get_repo_score`, `get_check_result`, `compare_repos`, `list_checks`, `explain_check`) and **two check-catalog resources**. It reads pre-computed results from **the same public Scorecard REST provider**; unlike our lightweight adapter, it includes full check reasons/details, documented missing-check names, repository comparisons and offline methodology references. It does not yet implement on-demand scans inside its MCP.

**B01 overlaps only the narrow `get_repo_score` observation.** Its unique *local deployment benefit* is a single budgeted, plan-first source inside the existing v1 `BudgetCache` and optional intelligence runner, with no separate binary/service/process, no untrusted free-form reasons stored, explicit cache/cooldown and no extra public tool registry. It does **not** claim to be a better or fuller Scorecard MCP.

**Decision:** Keep **B01 only as the limited embedded Scorecard evidence source** useful to TrendPulse's combined research pipeline; **do not build** duplicate `get_check_result`, `compare_repos`, `list_checks`, `explain_check` methods. Users requiring full Scorecard-specific analysis should use the official first-party MCP separately when their environment supports it. If a future integration already makes those richer official results directly accessible with lower overhead, re-evaluate and **discard** B01 duplication rather than expose two equivalent public tools.

**Windows feasibility:** Official GitHub release `v5.7.0` (published 2026-11-19) has a `scorecard_5.7.0_windows_amd64.tar.gz` asset of **29,007,450 bytes** and published SHA-256 checksum. The official README cautions Windows support may experience issues. A checksum-manifest download succeeded, but the bounded large-asset transfer was stopped incomplete (~26.99 MB of 29 MB) and a second transfer attempt failed because `curl.exe` was absent. Both temporary folders were removed. **No official Go executable was run or installed; no valid first-party Windows startup/RAM benchmark is claimed.** Running it is not a prerequisite for accepting a narrow embedded REST read; it *is* a prerequisite before claiming first-party binary superiority on this Windows machine.

Official docs:
- https://github.com/ossf/scorecard/blob/main/docs/mcp.md
- https://github.com/ossf/scorecard/blob/main/README.md
- https://github.com/ossf/scorecard/releases/tag/v5.7.0

**Source-quality protections:** B01 already preserves scan-date precision, check scores, `unreported_checks_are_unknown=true`, and `full_check_coverage_verified=false`. First-party check catalogs may change with version; do not invent complete/missing-check lists from a stale hardcoded catalog. Both offerings are **security heuristics, never a security certification**. Source REST data is CDLA Permissive 2.0.
