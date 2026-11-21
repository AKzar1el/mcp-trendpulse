# MJAU v2 A02 — Privacy-safe GitHub star-history proof

**Status: BLOCKED FOR FINAL ACCEPTANCE — NOT MERGED OR RELEASED.**

**Isolated branch:** `feat/mjau-v2-discovery-a02-github-stars-20261121`.  
**Base commit:** `b88b0a974b5dcdb480e4fd8c4da5f7bbca68e98e` (original MJAU v1 draft PR #328).  
**Feature:** A02 historical repository momentum, not an added automatic MCP tool.  
**Scope:** only `src/mcp_trendpulse/mjau_v2/github_stars.py`, its tests, package marker and this report. No global CLI, MCP server registry, source contracts, dependency/lock, worker, config or CI modifications. Parallel v3 track unaffected.

## Why it may be useful and why it is not accepted yet

MJAU v1 can observe source-backed developer issues and package-download histories but does not yet compare GitHub's new privacy-safe weekly repository star cohorts. GitHub's official endpoint returns aggregate weekly counts, day-slot counts and zero-filled weeks. The user can investigate whether an open-source alternative shows recent attention *without collecting any named stargazer*.

**Important semantics:**
- GitHub API: `GET https://api.github.com/repos/{owner}/{repo}/stargazers/history`. Public resources may be read without authentication; API version `2026-03-10` and JSON Accept.
- Each row is `{"week": UNIX epoch, "total": count, "days": [7 integer counts]}` newest-first. Week/day boundaries are **not guaranteed UTC**; we preserve provider epochs and day slots rather than inventing UTC dates or ISO-country inference.
- Weekly counts are original star dates for **stars still active at current observation**, not immutable historical daily-star totals. **Unstar events are not provided**. They are not unique product users, paid customers, users active today, software installations, downloads, transaction volume or market share.
- Output marks one-page coverage as partial by design, even for a valid result. Conservative descriptive comparison requires **10 contiguous weekly rows**, excludes the newest 2 and compares two four-week windows; when the previous baseline is zero, percentage remains `null`.
- No source-backed claim of acceleration or prediction. Data from separate repos remains source-scoped, never summed as a global market measurement.

Official documentation:
- https://docs.github.com/en/rest/activity/starring?apiVersion=2026-03-10
- https://github.com/orgs/community/discussions/206104 (GitHub clarification about surviving stars/unstar history)

## Safety and isolated implementation

- **Plan-only default:** `github_star_history(owner="AKzar1el", repo="mcp-trendpulse")` performs no SQLite/cache/network work.
- Explicit `execute=True` is required for a source operation.
- Fixed official HTTPS endpoint and validated repo path; first page only, up to 12 weeks, local ceiling 4 per UTC day, successful-cache TTL 12 hours, response max 96 KiB, no user account or API token, 4/10-second connect/read timeouts, no redirects/proxies, no retries.
- Existing original v1 `BudgetCache` is reused only when explicitly executed; in a real developer trial use a **new isolated cache directory**, not the original v1 worker state.
- Cache is reconstructed from validated whitelisted weekly counters; wrong-owner cached data, invalid week sums, malformed JSON, out-of-order weeks, and missing weeks cannot silently turn into growth evidence.
- Provider 429/503 open a conservative 120-second local cooldown. 401/403/404, network failures and local daily-limit exhaustion yield unavailable, never zero activity.

## Verification ledger (2026-11-21)

| Gate | Verified observation | State |
| --- | --- | --- |
| Upstream API and free method | Official GitHub REST docs identify public unauthenticated aggregate history and 2026-03-10 schema | DOC-VERIFIED |
| Deterministic tests | **46 passing**, Python 3.13.5, isolated import, command `PYTHONPATH=/mnt/data/trendpulse-v2-a02/src pytest -q /mnt/data/trendpulse-v2-a02/tests/test_mjau_v2_github_stars.py`. First test run exposed an issue in the test helper's explicit `None` fixture handling; helper repaired and all 46 reran successfully | OFFLINE-VERIFIED |
| Live adapter network acceptance | The connected Codexify TrendPulse tunnel is unavailable; isolated container cannot resolve public GitHub network hosts. GitHub connector supports repository metadata but rejects this unlisted star-history API endpoint; no genuine adapter live call was performed | BLOCKED |
| Source-output cache replay | Tested with injected responses and test-local Store; real SQLite+provider replay not yet observed | MOCK-VERIFIED ONLY |
| Entire v1 repo regression and linter | Full source/dependency environment not available in isolated offline container; no full-suite-green claim | NOT RUN |
| Research-task gain | New information is distinguishable from v1 issue/download evidence but no honest measured decision accuracy against 5 real historical user questions yet | NOT PROVED |
| Production compatibility | Only isolated new source, test, docs and package marker; no changes to v1 or companion v3 | ISOLATED |

## Required follow-up, then strict decision

1. Obtain one consented, bounded, actual `execute=True` response against a public repo from an isolated full v1 checkout and real `BudgetCache`; replay the exact request with **zero network**. Do not bypass 429 or shared GitHub limits.
2. Compare five predeclared real research questions against current MJAU v1: two real positive trend/competitor examples, one no-signal case, one missing/partial history case and one misleading-popularity case. Verify citations and correct uncertainty, not merely nonempty JSON.
3. Measure independent value, failure handling, RAM, API calls, cache hits and latency; run the full relevant repo suite/Ruff. Preserve existing MJAU v1 behavior.
4. If all mandatory gates pass -> ACCEPT for later single-owner integration review. If provider blocked -> BLOCKED. If useful improvement cannot be established or costs/performance regress -> DISCARD. Remove discarded code before release.

**No new background jobs, PR merge, release, deployment, paid API, credentials, schema changes or workers were authorized or performed by this proof.**

## Bounded real-source acceptance on Windows (2026-11-21)

**Supersedes the earlier adapter-network blocker above.** Through the healthy shared Codexify God v5 bridge, the exact pinned A02 source at commit `a8dfc081a08285080b22138d23820b4d6138120d` was loaded in memory alongside the v1 `BudgetCache`. A new temporary cache was used; the v1 branch and running agents were untouched.

- First execution: `owner=AKzar1el`, `repo=mcp-trendpulse`, `limit=10`, `execute=True`; provider read yielded `status=observed_partial`, `network_performed=true`, `requests_attempted=1`, **ten dated provider-week cohorts** and `comparison_status=descriptive_cohort_window_comparison`. The official API separately returned HTTP 200. Cohorts count surviving stars from original star dates, not unique users or actual historical unstar events.
- Identical second execution: `cache_hit=true`, `network_performed=false`, `requests_attempted=0` (real cache replay).
- The one-shot Windows wrapper returned nonzero **after** these outputs because `TemporaryDirectory` encountered a temporary SQLite handle lock while deleting its own cache. The directory was explicitly verified and cleaned after process termination. The two source operations themselves succeeded; full clean test-harness exit was not claimed.

**Current decision:** source transport and replay **OBSERVED**; A02 remains **NOT ACCEPTED** until the five-case baseline-usefulness evaluation, license/quotas, resource profiling, Ruff and full relevant regression gates pass. No production, v1 shared files, v3, merge, or release changes.

## Authentic v2 pytest/Ruff verification — 2026-11-21 (supersedes older “not run” lines)

- **Actual project toolchain**, not a mocked pytest shim: venv **pytest 9.1.1**, **Ruff 0.12.1**, Windows, focused source and test staged in a separately scoped temporary directory; production and active v1 tree were untouched. The tested isolated source commit was `71ca1dbb6cc81296da735f6c46f8c9f3482956b8`.
- **Focused tests:** **46/46 PASSED**, no focused failures. **Ruff:** **ALL CHECKS PASSED** for the source and its committed tests.
- **Test note:** Authentic pytest passed after test collection isolation; Ruff E701 in local test exception class was corrected in commit 719a9e15e52dbf0a88df3c5f3d44fe00ecf145ba, then both checks passed.
- **Existing v1 compatibility baseline** (unchanged checkout `b88b0a974b5dcdb480e4fd8c4da5f7bbca68e98e`): 11 selected MJAU/evidence test modules produced **258 passed and 1 timing-sensitive failure** in `tests/test_intelligence_singleflight.py::test_different_queries_still_fetch_in_parallel` under concurrent machine load. That exact unchanged failing assertion **passed** on an isolated rerun. The result is NOT a single fully green broad regression and NOT the full repository suite. The 15 async tests failed on an earlier runner with `pytest-asyncio` disabled; all passed after the installed plugin was explicitly loaded. No source code regression was attributed to the new v2 adapters, because they have **not** been wired into v1.
- **Still required for inclusion:** a single integration-owner review on current v1 contracts, correct free-source license/attribution, independent decision usefulness and false-positive comparison, no material CPU/RAM/latency regression, and a successful combined regression on the *final merged commit*. **Strict prove-or-discard still applies.**
