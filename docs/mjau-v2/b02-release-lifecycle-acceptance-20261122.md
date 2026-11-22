# MJAU V2 B02 - verified, narrowly scoped software lifecycle observations

Decision: ACCEPT the free, optional, read-only release-cycle source only after the exact final commit passes the full offline suite, real 16-tool MCP stdio checks, and protected GitHub CI. Never imply a vendor guarantee, commercial-support entitlement, buyer demand, or automatic migration urgency. A community-curated record is NOT a vendor-issued contract.

Original isolated proof branch: feat/mjau-v2-discovery-b02-eol-20261121 (1d31da7). Integration was prepared from protected main 57c2a9f. This change is disjoint from V3.

## Predeclared five-case real evidence comparison versus V1

V1 measures developer/package attention and dependency/security evidence, but has no release lifecycle-date tool.

1. Node.js 22: source EOL 2027-04-30, active support already over and release not EOL. Original Node.js Working Group schedule agrees exactly 2027-04-30.
2. Python 3.12: source EOL 2028-10-31; Python Developer Guide confirms only October 2028. Do NOT treat October 31 as independently vendor-certified day precision.
3. Node.js 20: one new real versioned endoflife.date API v1 call returned schema 1.2.1, generated 2026-11-21T16:49:28Z, isEol=true, isMaintained=true, isEoes=false, EOL 2026-04-30. Official Node.js schedule verifies upstream EOL 2026-04-30. The endoflife.date documentation defines isMaintained as ANY support, even commercial/extended support. Its Node.js product page explicitly lists commercial support Yes for 20. This is a support SCOPE ambiguity, not an inherent contradiction: the user does not automatically receive commercial updates.
4. Unknown release: prior true source HTTP404 meant not_found, never 0 days or no customer demand.
5. Adversarial: vendor EOL, end of active support, extended maintenance availability and user eligibility are separate concepts. Unknown dates, stale/contradictory source dates, HTTP429/503, malformed envelopes and source/cycle mismatches must not create a migration/security claim.

Outcome: three source-backed lifecycle lookups add correct evidence absent from V1, with day/month precision preserved and two abstention safeguards. No study of all products, predictive conversion or actual buyer demand is claimed.

## Exact, free, bounded operational design

Only fixed-host endoflife.date v1 GET for a single product/cycle; no credentials, billing, redirects, retries, arbitrary URLs, workers or GSC/GA4. Default execute=false performs no SQLite/network; explicit execute=true uses existing V1 BudgetCache, local cap 4 requests/UTC day, <=64KiB body, 24h validated source cache and 120-second 429/503 cooldown. Single Node20 adapter GET performed during this integration; Windows disposable cache directory deleted normally.

A current record with only a post-EOL commercial/extended support caveat is allowed into cache as observed_partial WITH its warning. Actual contradictory calendar dates/phase flags and source data older than 30 days are never cached as fresh. Neither isMaintained=true nor isEoes=false establishes the caller's access to a contract. Output preserves original source URL/dates and includes false values for support_entitlement_verified, official_vendor_support_verified_by_api, and unconditional_support_or_migration_advice_allowed.

Informational official upstream URLs for Node.js and Python are supplied but NOT fetched by the API call. Source licensing is MIT per original endoflife.date repository; respect attribution, provider limits and original vendor rights. No new dependency or runtime restart.

Primary official references:
https://github.com/nodejs/Release/blob/main/schedule.json
https://nodejs.org/en/about/eol
https://endoflife.date/nodejs
https://github.com/endoflife-date/endoflife.date/blob/master/api_v1/openapi.yml
https://devguide.python.org/versions/

Release gates: focused and full pytest, Ruff, exact locked dependencies, actual 16-tool MCP read-only stdio plan-only acceptance, protected GitHub CI and post-merge container smokes. No automatic GHCR/PyPI publication. Exclude B02 and mark BLOCKED if any gate fails.

## Final local acceptance receipts (before GitHub CI)

- Original B02 proof: 57/57 focused pytest, Ruff clean. After conservative support-scope correction: 61/61 source pytest, Ruff clean.
- Combined B02+existing optional MCP+entrypoints: initial 85/86 passed, 1 test-fixture failure because a fake generated_at timestamp was newer by microseconds than the observation. The adapter correctly rejected future source data. Fixed the *fixture* to be five seconds old; exact B02 SQLite replay test rerun PASSED. This source-validation safety was not weakened.
- Independent real MCP SDK stdio: 16 read-only optional intelligence tools, 11/11 real protocol checks PASSED, including B02/A02/A03/B01 plan-only calls with zero external/paid requests, and original V1 security guards.
- Current-main+B02 full offline pytest: 2,736 PASSED, 1 FAILED, 10 deselected, 3 existing warnings. The only failure was unchanged tests/test_article_preflight_worker_lifetime.py::test_rss_decoder_timeout_retains_slot_and_returns_no_article, in its 1-second worker release wait after a tight preflight timeout under Windows CPU load. Both this test file and src/mcp_trendpulse/news.py are byte-identical to protected main 57c2a9f. The exact failing test PASSED on isolated rerun. Do NOT call the full local suite completely green; GitHub CI remains a mandatory release gate.
- Full Ruff check PASS; uv lock --check --offline PASS (135 existing packages, no dependency change); git diff --check PASS.
- Fresh original-source post-fix Node.js20 v1 GET observed source schema1.2.1, generated 2026-11-22T00:08:24Z, correct provider EOL/commercial caveat and no false conflict; identical second run served from SQLite cache with zero network, and disposable Windows SQLite cleanup passed. Two new real Node20 v1 source GETs total were made on 2026-11-22 UTC during this milestone, within the manually coordinated four-per-day research request limit; no 429 retries.
- Offline latency with 30 plan-only calls: p50 0.055ms, p95 0.087ms; 30 warm SQLite cache hits: p50 5.186ms, p95 12.746ms. Uses one injected source fixture, ZERO HTTP; these figures are NOT provider latency measurements. No new package or large archive, model or scheduler.
- Only separately opt-in intelligence MCP gains one new read-only B02 tool; community/hosted catalogs, V3, existing running services remain unchanged.

Final release requires complete protected GitHub tests, exact SHA review, no runtime restart and manual-only GHCR push skips.
