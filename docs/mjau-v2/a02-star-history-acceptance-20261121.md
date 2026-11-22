# MJAU V2 A02 - source-attested GitHub aggregate star-history

Date 2026-11-21. Candidate status: **ACCEPT for one narrow, opt-in read-only repository attention observation**, pending exact-commit full regression, real MCP stdio acceptance and protected GitHub CI. Not a product success score, competitor ranking, net historical star growth, user count or forecast.

## Real baseline comparison to V1

V1 includes GitHub issues and package-download context but does not query official GitHub star-history cohorts. V1 also explicitly reports competition as not_measured.

The predeclared five-case protocol on the isolated A02 branch was checked:
1. fastapi/fastapi: earlier original-source proof recorded 10 latest provider weeks; four-week present-day surviving-star cohorts **1,737** recent and **801** prior, yielding descriptive **+116.85%**. This is a current snapshot grouped by original star date, not observed net historical growth, user installs or customer adoption.
2. AKzar1el/mcp-trendpulse: one new real official API read on 2026-11-21 returned 10 provider weeks, status observed_partial; after excluding the newest two weeks, recent four-week surviving-star events **2**, preceding four-week **0**. Percent change correctly **null**, not infinity. Identical replay from validated original SQLite returned cache_hit true, network_performed false, requests_attempted zero. Disposable SQLite directory was deleted immediately on Windows.
3. Date semantics: API week/day boundaries are provider-defined and are NOT guaranteed to align with UTC. The adapter does not invent UTC day dates or geography.
4. Privacy/demand guardrail: no individual stargazer lists or usernames accessed, and the counts are NOT users, net history, downloads, product adoption or revenue. Events involving removed stars cannot be recovered.
5. Failure guardrail: malformed or insufficient weeks, 401/403/404, 429/503, 0 historical baseline and corrupted cache return unavailable/inconclusive and never a forecast or fabricated zero.

**Outcome:** 2/2 positive source-specific due-diligence questions gained a new bounded observed answer relative to V1; 3/3 negative/abstention gates were retained. This is proof of incremental descriptive source evidence, **not** prediction accuracy or customer acquisition. Each result is partial one-page provider coverage.

## Rights and operational cost

Official API: https://docs.github.com/en/rest/activity/starring?apiVersion=2026-03-10
Public unauthenticated GET /repos/{owner}/{repo}/stargazers/history, version 2026-03-10. No profiles harvested; original API URL retained for attribution, no broad metadata redistribution licensed by mere public access.

Default execute=false accesses **zero** network or SQLite; explicit live uses a single fixed HTTPS GitHub endpoint, source-specific 4-per-UTC-day local request cap, max 12 provider weeks and 96 KiB, no redirects/proxies/retries, 12h validated source cache and 120-second 429/503 cooldown. Two prior original-source A02 calls and this one new read were documented today, total **3** research requests; no fourth needed or authorized for this experiment.

40 seeded-fixture offline microbenchmarks on Windows Python 3.13.5 (no actual provider network): plan p50 0.103 ms, p95 0.307 ms; 40 real SQLite cache-hit calls p50 5.169 ms, p95 14.209 ms; one synthetic source response seeded them. These timings are NOT HTTP latencies, and peak isolated process RSS was not captured in that microbenchmark. The MCP test process uses full library dependencies; do not misattribute total process RSS to this adapter.

## Integration and rollback

One new function intelligence_repository_star_history in the **existing separately opt-in** intelligence MCP, with read-only annotations and default plan-only. Current community/hosted catalogs, V3 work, workers and service configs do not change. Acceptance requires local full tests, independent actual stdio JSON-RPC 15-tool contract and latest-head protected GitHub checks; do not merge if any fail. The separately merged V1 manual-only GHCR publish guard remains required.

Rollback is a normal revert of the A02 commit or removal of its optional tool registration; no source state migration or daemon cleanup is required. No release/deployment is authorized by this source proof.

## Real independent MCP SDK protocol acceptance

An independent client spawned the optional intelligence MCP with real stdio JSON-RPC, initialized the server, discovered exactly **15 read-only tools**, checked all non-destructive annotations and called A02, A03 and B01 in default plan-only mode. **11/11 checks PASSED**, zero paid/source calls from these plans. The test also covered original V1 source catalog, plan/no-network safety, provider credential redaction and rejecting bad arguments.

The first attempt failed with "Unexpected MCP toolset" because the MCP SDK intentionally filters inherited subprocess environment variables; PYTHONPATH was not forwarded and the child loaded a stale **14-tool installed package** instead of the checked-out 15-tool source. This was a **test-harness source selection issue**, not a provider/adapter failure. scripts/intelligence_mcp_client_e2e.py now explicitly passes the checkout's src path in the child environment, with no user credentials. The retest confirmed the child traceback referenced the intended isolated source checkout and all 11 JSON-RPC checks passed. This prevents false acceptance of an old installed package during future code reviews.

## Local release-candidate verification receipt

- Original A02-only source tests: **46/46 passed**, Ruff clean.
- After isolated 15-tool MCP wiring: **70/70 targeted tests passed**, Ruff clean.
- Real independent stdio SDK client: **11/11 acceptance checkpoints passed**, including 15 read-only tools and A02/A03/B01 plan-only calls, **0 paid/provider requests** in these calls. The previous subprocess source-import mismatch was corrected, then retested successfully.
- Full V1+V2+A02 repository offline regression on the actual scoped current-main worktree: **2,672 passed, 10 intentionally deselected, 3 preexisting nonfatal warnings, zero failures**, Windows Python 3.13.5. Ruff checked the whole worktree clean. UV lock verification resolved 135 packages offline, zero dependency edits.
- During integration pytest, Windows process working-set was about 186 MiB with observed peak about 196 MiB. This is the full test/collection process, **not isolated adapter RAM**; the adapter itself imports no heavy inference library.
- No independent V3 experimental files, permanent service, worker schedule, browser, GitHub Actions reruns or production MCP installations were changed by local QA.

Latest GitHub branch CI, protected-main mergeability and manual-only GHCR publication safeguards are independent remaining release gates.
