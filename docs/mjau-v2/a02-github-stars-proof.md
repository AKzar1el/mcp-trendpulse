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
