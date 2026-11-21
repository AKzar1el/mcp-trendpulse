# mjau plan — TrendPulse free global trends and keyword intelligence

> **Canonical task plan.** Refer to this document as **mjau plan** in any ChatGPT/Codexify conversation. Repository: `AKzar1el/mcp-trendpulse`; path: `.planning/mjau-plan.md`; initial staging branch: `feat/free-intelligence-8-lanes-20261118` (draft PR #328). The file is intentionally **not linked from README**. This is still a **public repository**: an unlinked/dot-directory file and the draft branch are discoverable and are **not private**. Never store secrets or internal credentials here.

**Created:** 2026-11-20 | **Status:** M00?M03, M05?M07 and M09?M10 source-live verified in separately staged branches; M04 in a parallel verification chat, M08 offline-verified but its live gate remains blocked in independent draft PR #370. **Next unstarted milestone:** M11 Stack Exchange. No merge/release/deployment implied.

## Mission and non-negotiable scope

Build a **global, domain-independent**, free-only trend/keyword discovery engine: find newly rising search terms and topic momentum; validate against independent attention, developer discussion and software-adoption evidence; generate useful language/region-specific keyword families and credible product-research leads. Historical observations are not automatically verified trends, search volumes, paying customers or market growth.

- **No Google Search Console / mcp-gsc integration, no GA4 / property analytics, no website-dependent keyword suggestions, no paid API or billing account, no proxies to evade quotas, no captcha bypass, no new tunnel/worker/scheduler, no auto-publishing.** This is generic market research, not website performance reporting.
- Markets: all source-supported global markets. A 'global keyword tool' means arbitrary terms independent of the verified website; it does **not** imply every country or global-volume coverage. Always preserve country, language, source, dates, locale and metric semantics. Missing market data is **unknown**.
- Reuse existing `trendspy`, `requests`, `pandas`, `nltk`, Python `sqlite3`, existing provider/caching/MCP/CLI facilities. Check installed versions and API behavior before changing dependencies.
- Libraries implement text matching, parsing and statistics; TrendPulse owns source adapters, provenance, permission boundaries, budgets, result schemas and CLI/MCP orchestration. Prefer no library when stdlib/existing dependency suffices.
- No GitHub changes besides the currently selected milestone, its tests, minimal docs and task-list update; do not merge or release without eligibility checks and user authorization. Existing revenue/fleet automation should remain untouched.

## Cross-conversation operating instructions

1. Read **this file in full**, inspect current GitHub branch/PR and the relevant module/tests and upstream official docs **before** each task; use live state rather than assuming this text is up to date.
2. Execute exactly **one unchecked milestone** at a time, in the order below (unless the user explicitly changes priority). No speculative multi-source expansion. Implement, test, run one bounded live source test if access/quota permits, review results, then check off **only** when all acceptance gates pass.
3. Each milestone must finish with: files/commit or PR, deterministic test names + counts, one small live query and source evidence or explicit reason live unavailable, API quota/cost check, compatibility check, and the next unchecked item. Update this file in the **same branch/PR** as the milestone (or with its own traceable docs commit).
4. If a live provider is inaccessible or requires unsupported access, mark **BLOCKED** (not complete), record exact dependency, and proceed only if user explicitly allows deferring it. M05 Bing has an explicit **SKIP** decision because it is credential-gated.
5. Never create a fake measurement from a synthetic fixture or imply scraping yields official Google volume. Keep search interest, news attention, repository activity, complaint counts, package downloads and customer demand distinct. Source terms and generated suggestions are labeled differently.
6. Save no API keys to Git, local logs, URLs that are printed, issue descriptions or the history database. Redact credentials in HTTP errors; validate response shapes; include HTTP timeouts, local budgets and cache TTL; never retry around a local source quota.

## Shared milestone release gates (every milestone)

- [ ] Exact public source/API terms, access method, geo/language reach, quotas and metric meanings verified; do not infer absent capabilities.
- [ ] Small deterministic offline tests cover happy path, empty, invalid response, stale/partial coverage, same-day duplicate, rate limit, source failure, and credential redaction where applicable.
- [ ] At least one permitted bounded end-to-end fetch with real source data; otherwise mark blocked/unverified and do **not** call milestone complete.
- [ ] Existing unit/integration tests and lint green (or specific unrelated failure documented with evidence), CLI/MCP interfaces backward compatible.
- [ ] No paid spend, billing account dependency, unsupported data access, separate tunnel/automation or hidden unbounded retries.
- [ ] Final result is source-attributed, market/date-aware, clearly distinguishes observed vs estimated vs hypothesis and reports missingness rather than fabricated zeros.

## Library decisions (minimal base installation)

| Library | Status | Why | When |
| --- | --- | --- | --- |
| `trendspy` | Existing core | Google Trends community provider, related searches and RSS-capable functionality; reuse before evaluating any replacement | M00, M01, M04 |
| `requests` | Existing core | Bounded HTTP for Wikimedia, HN Algolia, Bing JSON REST, npm, PyPI, Stack Exchange | M05–M11 |
| `pandas` | Existing core | Comparable-date transformations, aggregations and time series | M12–M13 |
| `nltk` | Existing core | Lightweight language/phrase preprocessing; test language handling | M12 |
| `sqlite3` (stdlib) | Existing | Local source/term observation ledger, cache, no hosted database | All |
| `rapidfuzz` | **Add** (MIT; Python >=3.11 compatible) | Efficient exact/near-exact keyword matching; avoid accidental unrelated or cross-language merges | M02 |
| `google-cloud-bigquery` | Optional extra, not base | Query the official Google Trends public dataset in a **no-billing sandbox** when the operator enables Google auth | M03 |
| `rake-nltk` | Optional extra, only if NLTK/token spans insufficient | Lightweight unsupervised candidate phrase extraction | M12 |
| `statsmodels` | Optional extra, only with adequate history | STL seasonality decomposition after multiple comparable cycles; not a core dependency | M13 |
| Extra RSS parser | Avoid initially | Existing provider/stdlib is enough if RSS source shape can be parsed safely | M01 |
| `pytrends`, `trendspyg`, scikit-learn, KeyBERT, DuckDB, `ruptures` | **Do not add by default** | Archived/overlapping or heavier than demonstrated needs; revisit only after profiling and documented justification | Future only |

## M00 baseline inventory — 2026-11-20 (implementation review)

- Baseline branch at start: `392a9c2fffc0a45e0be79f87378023f90300bcd1` (draft PR #328), **14/14 successful GitHub Actions workflows**.
- Locked Python dependencies: `trendspy 0.1.6`, `requests 2.34.2`, `pandas 3.0.5`, `nltk 3.10.4`, `pydantic 2.13.4`, `fastmcp 3.4.11`, `pytest 9.1.1`, `ruff 0.12.1`; supported Python >=3.11.
- **RSS M01 already partly exists**: `news.get_trending_terms` invokes `trendspy.Trends.trending_now_by_rss`; community `TrendsProvider.get_trending_terms` and CLI `trending-terms` already expose it. M01 should harden and map the existing RSS results, **not add a duplicate RSS client or provider**.
- **BigQuery M03 already partly exists**: `bigquery_trends.build_discovery_sql` supports US/international top/rising public datasets using allowlisted tables, snapshot partition predicates and capped query SQL; CLI `bigquery-sql` prints SQL **only** and does not execute or spend. M03 adds optional authenticated sandbox execution, not a second SQL builder.
- Existing Google Trends community provider exposes normalized interest, related queries/topics, ranked trends, region interest, and suggestions. Current `intelligence_keyword_probe` is explicit opt-in and locally capped at **two provider operations per UTC day**; `trends_rate_control` shares pacing/429 cooldown.
- Existing intelligence collectors: **25 catalogued adapters**, source-specific local free daily request budgets and caching; baseline discovery uses OpenAlex, CFPB and TED only, not all 25. Existing GitHub Issues adapter is shared with future M08.
- Existing historical source sightings and normalized Trends watch evidence live in SQLite; these are separate from global keyword signal metrics.
- Actual live-source baseline: existing Actions `Free intelligence live contract smoke` run **44729613503**, job **136265700670**, recorded **15/15 sources passed** on 2026-11-20 (including GDELT, Eurostat, TED, CFPB, GitHub Issues). It confirms live public-source access, **not** a new Google Trends RSS live test. M01 still needs its own bounded live RSS confirmation.
- M00 creates only a typed Pydantic `TrendSignal` contract and offline CLI schema inspection; no paid providers, network requests, new system scheduler, new MCP tools or background automation.

## Sequential implementation checklist

### Phase A — search-demand foundation (highest priority)

#### [x] M00 — Baseline and interface contract (no new source)
- **Reuse:** current `trendspy` / `pandas` / `nltk` / `requests`, SQLite quotas and existing Google Trends tools.
- Inventory present features, duplicate implementations, dependencies, existing tests/CI and source caps. Define a typed `TrendSignal` contract: `source_id`, `source_url`, `observed_at`, `published_at?`, `country?`, `language?`, `raw_term`, `normalized_term`, `metric_type`, `metric_unit`, `period`, `value?`, `sampling_scope`, `coverage_status`, `provenance`.
- Preserve named types for absolute Bing impressions, normalized Google Trends interest, topic mentions, pageviews, downloads and merely generated keyword candidates. `null` for missing values; no common numeric growth score without calibrated evidence.
- **Acceptance:** existing tests pass; no duplicate adapter created; contract tests verify missingness/region/source attribution; small CLI output demonstration. Record actual versions and observed capabilities.
- **COMPLETE 2026-11-20.** Implementation commits: `fa7a7e4c7ed5a3befdb2de4ec1dda4c543e58def` (new contract, offline CLI and tests), `e27bcd803391ed6a28dd64ed83f520ab30f4fc66` (Ruff cleanup). Delivered `src/mcp_trendpulse/intelligence_signal.py`, `tests/test_intelligence_signal_contract.py` and `intelligence signal-schema --format text|json`. The immutable Pydantic model enforces source/metric unit and class, provenance and country/language, explicit time windows, normalized vs absolute data, search-query vs keyword-hypothesis distinction, missingness and secret-safe public URLs.
- **Verification:** GitHub Actions for implementation SHA `e27bcd803391ed6a28dd64ed83f520ab30f4fc66`: **14/14 workflows successful**, Python 3.11/3.12/3.13/3.14 CI matrix successful; release validation **1,888 tests passed, 10 deselected, 3 existing warnings**, Ruff clean. `Free intelligence live contract smoke` run `44731831297`, job `136273284756`: **15/15 existing free sources observed** (not a Google Trends RSS measurement). Package publish correctly skipped because PR remains draft. CLI deterministic tests cover JSON schema and human-readable text with network collector forbidden.
- **No changes:** no added package, source adapter, network fetch in schema CLI, new MCP tool, schedule, credentials, merged branch or release. M01 still requires its own two-country bounded RSS live verification.

#### [x] M01 — Google Trending Now via public RSS
- **Source:** Google Trending Now RSS (public); no auth, no browser, no site association.
- **Reuse:** `trendspy` if it actually provides a stable RSS method. Only fall back to existing HTTP/XML parser if the available version lacks safe RSS handling.
- **Output:** observed trending terms, publication time, source location, related news when supplied, source market. Optional traffic buckets must retain their original semantics; no invented exact volume.
- **Acceptance:** two permitted countries where supported, live RSS parsing, duplicate removal, empty/malformed XML/429 tests, daily cache, no Chrome or auth.
- **M01 implementation note (2026-11-20):** reuse the `get_provider_set().trends.get_trending_terms(..., full_data=True)` adapter, which already calls `trendspy.trending_now_by_rss`. New `intelligence trending-now --geo US --execute` CLI is explicitly opt-in. Source-attributed `TrendSignal` records retain source RSS country, approximate *bucket* (never exact count), feed start date when available, source news references, and grouped-label provenance; language remains unknown unless the source provides it. Offline mode requires no cache or network. Local persistent `BudgetCache` provides 15-minute TTL and hard 12/UTC-day source-call cap; repeated queries are cached, and 429 shares a local cooldown. Limited RSS list is not complete Google searches.
- **VERIFIED COMPLETE on 2026-11-20.** Implementation commit: `5337ea8f10f68fb83d46e8341342fe94de5b0832`, draft PR #328. GitHub Actions **14/14 successful**; release package validation **1,912 tests passed, 10 deselected, 3 warnings, Ruff clean**; existing free-provider smoke **15/15**. New bounded live RSS smoke run `44736869005`, job `136290351240`: **US 10/10** and **GB 10/10** observed labels, source-published UTC start dates, approximate traffic buckets and three related news items per displayed sample; one provider operation per country, neither cached. No property registration, browser or paid requests. RSS lists are capped and do **not** represent full market keyword volume. Two-country live smoke is gated to M01 integration changes (or explicit manual dispatch) so unrelated future PR commits don't repeatedly poll the feed. CLI: `mcp-trendpulse-cli intelligence trending-now --geo US --execute --format json`; without `--execute` it only plans and never fetches.

#### [x] M02 — RapidFuzz keyword normalization, dedup and lexical clusters
- **Library:** add `rapidfuzz` to core only after reviewing binary wheels/lockfile and Windows Python 3.11–3.14 support.
- Normalize Unicode, whitespace and punctuation carefully; preserve diacritics, original phrase, market and language. Exact duplicates first, conservative RapidFuzz near-duplicates second. Do not merge semantic synonyms or translations merely because strings look related.
- **Acceptance:** multilingual regression cases (Slovenian/English and accents), brand names, unrelated lookalikes, stable representative terms, lightweight CPU profiling, no merge across incompatible markets.
- **M02 implementation in validation:** `intelligence_keywords.py` uses RapidFuzz `fuzz.ratio` only after exact Unicode NFC/casefold and scope grouping. It is strictly offline and capped at 200 validated `TrendSignal` inputs. Strict country/language partitioning, accent-sensitive text, protected programming symbols/negations and all-member matching prevent unsafe merges. Every source's original raw term, source reference and original metric survive; never sum traffic buckets or invent keyword volumes.
- **CLI:** `intelligence cluster-keywords --input existing-m01-rss.json --format json` (or an array of M00 signals). No API call. Tests include multilingual variants, typos, negation/intent differences, M01 payload, 200-signal CPU benchmark and bounded input sizes.
- **VERIFIED COMPLETE on 2026-11-20.** Implementation `0c4ba15ff941e6af3c12c25f0b358ceedbe90ca1` + lock `ca9ca9b8d6f543170903843643e94b5997848088` + corrected fixture `489680bb760ef8e80388593045c8a1dfdb2dabdc` + false-positive guards `0c29f7ccb9f7677622e6e3922b1646b0cf8e9a8e`. Package `rapidfuzz 3.14.6` locked and CI Python 3.11–3.14 wheels supported, `--no-build-package rapidfuzz` protected on 3.14. One-off lock workflow **removed** after generating lock.
- **Test evidence:** on `0c29f7ccb9f7677622e6e3922b1646b0cf8e9a8e`, **14/14 GitHub Actions workflows successful**, release job **1,937 passed, 10 deselected, 3 warnings**, Ruff clean. Includes conservative exact+one-typo matches, intent changes, source-provenance retention, country/language isolation, Unicode NFC and diacritics, punctuation, C++/C# and brand `OpenAI Codex` vs `OpenAI Code` safeguards, bounded 200-record CPU benchmark, and CLI consuming an M01 RSS-shaped JSON fixture with no network. M02 is an offline algorithm, **not a new provider**: validated M01 US/GB live RSS source from the previous milestone (and user GB real run on 2026-11-20) is its input contract; no additional paid/live API call was necessary.
- **Output semantics:** all individual raw source measurements and source references remain separate; fuzzy similarity is lexical only, never evidence of demand or semantic equivalence. No GSC/GA4, browsing, scheduler or new infrastructure.

#### [x] M03 — Google Trends official BigQuery dataset (no billing)
**VERIFIED COMPLETE 2026-11-20.** The
existing SQL-only preview remains unchanged. M03 adds a separate operator-only,
opt-in discovery path with an optional official Google BigQuery Python SDK;
it never loads cloud credentials in the normal/offline path. Before any query
job it checks the Cloud Billing projects.getBillingInfo response and requires
no attached billing account. Missing/ambiguous verification fails closed.
It reserves from a persistent local three-per-UTC-day source budget, dry-runs,
rejects byte estimates above 100 MiB, and sets maximum_bytes_billed on the
actual job. No job retries, paid fallback, separate worker, GSC, GA4 or site
property. Results preserve source, geography, snapshot date, rank semantics,
unknown language and lack of measured total search volume. See
docs/bigquery-trends.md and tests/test_mjau_bigquery_sandbox.py.

**Offline verification:** 39 focused existing+new BigQuery tests passed again
2026-11-20; full repo Ruff clean. google-cloud-bigquery 3.47.0 installed
as optional extra; actual dry-run/job-config interfaces exercised. Earlier
full offline suite: **1,729 pass, 10 deselected, 2 unrelated local failures,
3 warnings**. Failures were pre-existing OpenAlex Authorization header
planning assertion with a locally configured redacted header and a
thread-parallel timing assertion on busy Windows; unrelated singleflight
test passed on isolated retry. Full local green is not claimed.

**Live acceptance, 2026-11-20 (operator-owned project trendpulse-new):**
Google Cloud Resource Manager returned project ACTIVE; Cloud Billing API
verified exactly the expected project, billingEnabled=false and no attached
billingAccountName; BigQuery Service Usage confirmed ENABLED. Existing
operator ADC authenticated, without credential sharing. Read/write access
to the original local budget directory was restored by an operator-approved
Windows ACL grant; SQLite quick_check=ok and original budget entries
preserved. The first GB rising query for 2026-11-19 returned **no_data**
because the international public dataset's latest published partition was
2026-11-18 (confirmed with BigQuery metadata list_partitions). The
2026-11-18 GB query's dry run estimated **309,018,782 bytes**, exceeding
the immutable **104,857,600-byte** ceiling; no live data query followed.
The final source-supported US rising Top 5 request for snapshot
**2026-11-18** dry-ran at **61,072,200 bytes**, then returned
**5 genuinely observed source rows, zero rejected**, with source rank
values 1..5 and correctly attributed US market/snapshot, unknown
language and no claim of absolute search volume or buyer demand. Source
terms: sixpence; nsa; argentina vs costa rica; pistons vs spurs;
penny lane. Existing local daily BigQuery sandbox reservation count
is **3/3**, with no retries, quota reset/bypass or billing attachment.
All three runs used the same no-billing verification, source/table/date
allowlist, and maximum_bytes_billed guard. No BigQuery query after this
daily quota is permitted until UTC reset. See
tests/test_mjau_bigquery_sandbox.py and docs/bigquery-trends.md.

**Scope:** M03 complete for one bounded source-supported market and date.
This does not establish international partition affordability at the
100 MiB cap; that larger GB partition was deliberately refused, not
queried at a higher limit. M04 was separately user-authorized ahead of
M03 live acceptance and remains independently unchecked.
- **Source:** public `bigquery-public-data.google_trends` international/US top and rising terms; daily snapshots, source-covered countries only; generally **Top 25** daily, **30-day publication partitions**, historical metric backfills for included terms. This is **not every keyword or exact search-volume data**.
- **Library:** optional `google-cloud-bigquery` with operator-managed sandbox auth; do not require Google Cloud credentials for normal TrendPulse operation.
- **Hard rule:** allow only Google BigQuery **sandbox/no billing account**, query dry run, source/table/partition allowlist, explicit `maximumBytesBilled`, small row limit, date/country partition predicates, local query budget. Sandbox free query tier does not authorize enabling billing.
- **Acceptance:** one bounded public-data query with recorded bytes estimate, a supported country and dates, original source metric semantics; graceful `no_sandbox_credentials` or unsupported geography without paid fallback.

#### [ ] M04 — Google Trends Explore and related search evidence
**IMPLEMENTED/OFFLINE VERIFIED 2026-11-20; NOT COMPLETE — LIVE LOCAL BUDGET BLOCKED.**
The user explicitly deferred only M03 live verification and permitted
implementation of M04 while away. New opt-in CLI:
intelligence explore-evidence --term "AI agents" --country SI
--timeframe "today 3-m" [--execute] --format json,
or --source-file observed-m01-or-m03.json to select one fresh, validated
source-backed M01/M03 term. Default remains strictly offline; no credentials,
site property, browser or billing needed. Reuses existing TrendSpy related
queries and interest-over-time adapter, **the same shared 2/UTC-day local
provider-operation budget** as the earlier idea keyword probe, six-hour
cached repeats, the existing paced worker and cooldown, and 429 local
circuit breaker. Top and rising values remain within-query relative
scores and prior comparable-period percentages. Google's Breakout is
**greater than 5000%**, not 5000 searches or an exact volume. Interest
points are validated original date-scoped 0–100 normalized TrendSignals;
no cross-request calibration, invented absolute volume, or keyword-demand
verification. See src/mcp_trendpulse/intelligence_explore.py,
tests/test_mjau_explore.py, and docs/google-trends-explore.md.

**Verification:** 65 scoped M00–M04/legacy probe tests passed including
the final cache-hardening rerun; full Ruff checks passed. Full local repository run after the
initial implementation: **1,742 passed, 1 failed, 10 deselected, 3
warnings** in 75 seconds. Failure is the same pre-existing
test_discover_cli_plan_only_and_history_gate assertion against the
local OpenAlex Authorization header label, even though its value
is redacted; no M04 tests failed. GitHub CI for the M04 head must be
recorded separately.

**Additional M04 validation, 2026-11-20 (same existing draft PR):**
Checked the persisted local shared quota SQLite directly: quick_check=ok,
Google Trends related-query operations **2/2** for this UTC day.
No source-provider request was made. Offline adversarial tests exposed
three issues in the newly implemented M04 adapter: nonempty malformed
related-query rows were misclassified as observed_empty; dropped,
deduplicated and series-capped related rows could be reported as fully
observed; corrupted SQLite cached related list items could crash the
command or arbitrary extra cached interest fields could leak into
output. Changes now explicitly report observed_partial with original
row/omission counts, fail closed for invalid-only inputs, validate cache
containers before reading, and reconstruct cache results from strictly
validated/whitelisted evidence fields only. The focused M04/M01/M03
compatibility suite reached **70 passed**, Ruff clean; later full
suite/PR checks are recorded separately. Neither the 2/day quota,
unofficial provider behavior nor the privacy/source limitations changed.

**Broader recheck:** repository-wide offline pytest completed with
**1,747 passed, 1 failed, 10 deselected and 3 warnings**. The sole
failure is the same unchanged OpenAlex plan-only Authorization-header
assertion against a redacted, locally configured source header;
no new M04 test failed and full green is not claimed. An opt-in
M04 CLI invocation for the explicitly named test seed
agent reliability / SI returned
local_daily_budget_exhausted for both operations with
**provider_operations_attempted=0** and **network_performed=false**;
the existing shared SQLite counter remained **2/2** for
2026-11-20 UTC. No source observation was manufactured or simulated.

**Live gate:** The earlier bounded M01 GB RSS seed attempt returned
local_budget_store_unavailable before any provider call because of
Windows ACLs. The operator subsequently granted Modify access on that
same original directory, without resetting or replacing its SQLite
quota history; SQLite quick_check=ok. The shared
google_trends_idea_related_queries UTC-day budget was already **2/2**
on 2026-11-20, so no additional M04 provider request was made.
M04 remains unchecked until the budget legitimately resets and one
bounded, source-attributed Explore result is observed.

- **Reuse:** existing `trendspy` and current optional Google Trends `intelligence_keyword_probe` quota/cooldown implementation, not a second client.
- Seed with genuinely observed M01/M03 terms and user-supplied market/topic. Retrieve top/rising related queries and normalized interest where supported; retain timeframe, country and comparative-series basis. Do not derive exact search volume.
- **Acceptance:** one small permitted live request or explicit upstream restriction, cached repeat, 429/cooldown/quota test, correct 'breakout' semantics, no infinite retries/proxies, no website property.

#### [x] M05 — Bing **global keyword research** through REST/JSON (access-gated, conditional)
**VERIFIED COMPLETE — 2026-11-20 UTC (operator explicitly deferred M04).**
Microsoft's documentation confirms that GetKeywordStats accepts q, country,
language; GetRelatedKeywords also accepts startDate and endDate; **neither**
method requires siteUrl or returns a verified site's search-performance
rows. Adding/verifying a site is the **credential issuance** prerequisite,
not a filter on arbitrary market keyword research. JSON/HTTP REST is
supported; SOAP/POX were retired on 2026-08-31. An existing user-managed
BING_WEBMASTER_API_KEY was already securely configured in the Windows
operator environment; no credentials were generated, exposed or stored
in the repository. The official Bing GET interface requires a query
apikey in flight, so the new adapter uses a fixed allowlisted TLS
endpoint, no redirects, proxies, or logged/persisted authenticated URLs.

**Implementation:** src/mcp_trendpulse/intelligence_bing_keywords.py,
the opt-in CLI intelligence bing-keywords (--term, --country, --language,
--kind stats|related, optional bounded related date window, --execute),
and a secure bing_webmaster provider profile in intelligence_settings.
Strictly offline preview by default; a single bounded read-only GET per
executed command, 128 KiB response limit, timeouts, no retries/fallback,
original SQLite source budget **3 requests/UTC day shared** across both
methods, 3-hour credential-isolated cache, 429/503 cooldown and
redacted errors. KeywordStats are normalized as separately sourced
weekly **exact** and **broad** Bing impressions TrendSignals, with
Microsoft /Date(milliseconds+offset)/ timestamp handling. Related
keyword counts are explicitly period-wide aggregates, **not** inferred
weekly observations. Empty provider rows are unknown/no_data rather
than fabricated zero impressions or buyer demand. See
docs/bing-keyword-research.md and tests/test_mjau_bing_keywords.py.

**Independent real-source acceptance:** A deliberately non-site-related
keyword, **crochet patterns**, US/en-US, was queried against the
operator's official REST/JSON GetKeywordStats: **HTTP 200**, 24 sourced
weekly records, all with Query, Date, Impressions and BroadImpressions.
The new CLI repeated that fixed official call, normalized **6 most
recent weekly records and 12 distinct exact/broad source signals**.
Bing-reported week 2026-11-14: exact impressions **742**; broad **3475**.
GetRelatedKeywords on the same unrelated term and US/en-US market,
2026-10-20 through 2026-11-19, returned **100** source records; the
CLI emitted **10** bounded results, including crochet (5367 exact,
72888 broad), free crochet patterns (1990 exact, 4420 broad) and
crocheting (1232 exact, 1894 broad). Both capped outputs are correctly
reported observed_partial because earlier/lower-ranked source rows
were omitted. Exact repeat requests hit validated caches with
**requests_attempted=0**, **network_performed=false**.
The original Bing local UTC-day budget is **3/3** including the initial
live schema/access probe, SQLite quick_check=ok. M04's separate
unofficial Google Trends provider budget remained **2/2**, unchanged
and unbypassed. Bing does **not** provide global-all-engine or Google
search volume and these impression counts do **not** prove customers.
A separate authenticated Bing Webmaster GUI comparison was not made;
live source API results and independent documented response fields
were verified instead.

**Validation:** 88 focused M05/M04/M03, secure-settings and legacy
provider tests passed; full Ruff clean. Full local Windows suite:
**1,783 passed, 3 unrelated failures, 10 deselected, 3 warnings**.
Two pre-existing OpenAlex freshness tests compare local calendar day
with UTC source dates across the 2026-11-20/21 midnight boundary;
another pre-existing OpenAlex CLI assertion rejects a *redacted*
Authorization header label in plan-only output. None fail within M05
or its direct compatibility tests. Do not claim full green or silently
change unrelated discovery behavior. On M05 implementation commit
c721e008dae1bc8dac4efd991957f4ebbb70d708, GitHub check-runs
finished **25 SUCCESS / 2 intentionally SKIPPED**, zero failed or
pending. The draft PR remains unmerged; publishing checks are skipped.

**Priority and handoff:** user explicitly requested M05 while deferring
M04's live Google Trends source acceptance until they remind us.
M04 remains [ ] unchecked; M05's successful Bing REST validation
neither resolves nor bypasses it. Do not start M06 until separately
authorized or M04 is completed.
- **Purpose:** Bing-wide (not the verified site's) keyword histories, related terms, arbitrary queries, markets/languages, possibly search-volume impressions. No GSC, Bing property performance or any domain-filtered report.
- **Access:** free Bing Webmaster login. Microsoft says a website must be added/verified to create an API key. **This verification is to obtain credentials; not a keyword restriction.** The keyword methods accept `q`, `country`, `language` (and dates for related terms), with **no `siteUrl`**. Must verify this with an unrelated keyword using the live REST API before building a full adapter.
- **REST only:** `GET https://ssl.bing.com/webmaster/api.svc/json/GetKeywordStats` and `/GetRelatedKeywords` with documented parameters; legacy SOAP/POX retired 2026-08-31. Use secure credentials from env/settings; never expose API key in reports, exceptions, trace/log output or persisted URLs. Verify current authentication requirements, response form, provider limits and terms first.
- **Acceptance:** arbitrary non-site keyword tested in at least one country+language; returns documented week/date, impressions/broad vs exact semantics or related terms; compared against Bing Webmaster UI where possible; no dependency on site traffic; graceful no-key/403/429 and hard daily caps.
- **Decision:** **KEEP** only after confirming access is free and live API data is domain-independent. If access cannot be obtained or keywords are site-bound, mark SKIPPED/BLOCKED with proof and continue; never emulate by scraping authenticated UI. Bing search impressions are **Bing-specific**, not Google's or global all-search-market volumes.

### Phase B — independent attention and developer adoption

#### [x] M06 — Wikimedia Pageviews
**LIVE VERIFIED — 2026-11-20 UTC (operator separately authorized M06 while M04 remains deferred).**
The official Wikimedia Analytics per-article daily Pageviews API is free,
no user credentials or paid plan required, data CC0 1.0. A meaningful
contact User-Agent is mandatory; 2026 provider rate limits apply. Use
only the official read-only mediawiki Action API metadata and Analytics
API endpoints, one language-specific Wikipedia project and one manually
specified exact article at a time. No inferred country of readers,
search volume, customer demand, bot counts or unique visitors.
API HTTP 404 can mean zero or not-yet-loaded and omitted dates can
mean missing/zero; NEVER replace these unknowns with fabricated zeros.

**Implementation:** src/mcp_trendpulse/intelligence_wikimedia.py and
opt-in CLI intelligence wikimedia-pageviews --article "Python
(programming language)" --project en.wikipedia.org --days 7
--end-date 2026-11-17 [--execute] --format json.
Default preview never opens SQLite or uses network. Fixed-host HTTPS
allowlist with no redirects, proxies or retries; 5s connect/12s read
timeout; 96 KiB limit; user-agent contains repository contact link.
One bounded read-only Action API canonical-title/pageprops check
refuses missing pages, namespace mismatches, redirects, disambiguation
and title mismatches without automatic resolution. Then one bounded
per-article daily source fetch for exactly two contiguous equal-length
periods (1–30 days each), with source-attributed daily TrendSignals.
Added atomic reserve_many to the existing BudgetCache, with a **shared
4 provider operations per UTC-day** cap for M06; both possible source
requests are reserved atomically before any network request. 6-hour
validated cache and 429/503 shared cooldown, no fallbacks, no dependency
additions. For incomplete source periods, totals and percent change
remain unknown; compare sums only with all daily observations present,
and percent difference only when the prior total is positive.
See docs/wikimedia-pageviews.md and tests/test_mjau_wikimedia.py.

**Live acceptance:** The operator explicitly selected the known canonical
English Wikipedia article Python (programming language) with requested
windows **2026-11-04..2026-11-10** and **2026-11-11..2026-11-17**.
First read-only Action query verified the exact canonical article was
neither a redirect nor a disambiguation page. One AQS per-article request
returned **14/14** real daily *all-access/user* pageview observations,
zero rejected/missing, with distinct source dates, article project,
language and access/agent provenance. Prior seven-day total **26,965**;
current seven-day total **25,846**; normalized comparison **−4.15%**
(−1,119 pageview requests between equal-length periods). These are
not unique readers, geographic user shares or keyword popularity.
The identical second CLI invocation hit validated SQLite cache with
**requests_attempted=0**, **network_performed=false**, 14 reconstructed
signals and unchanged sums. Original local M06 quota **2/4** for
2026-11-20 UTC; M04 separate Google Trends budget remains **2/2**
and M05 Bing budget **3/3** for that UTC day; SQLite quick_check=ok.

**Validation:** 109 focused M06/M05/M04/security compatibility tests
passed, full Ruff clean. Full Windows offline suite after M06:
**1,828 passed, 3 unrelated failures, 10 deselected, 3 warnings**.
The failures are the same pre-existing OpenAlex CLI-plan label assertion
(the word Authorization remains visible although the value is redacted)
and two local-calendar-date vs UTC-source-date freshness assertions
around the midnight boundary; no M06 test failed. Do not claim
the full Windows suite is green. GitHub CI evidence is tracked
separately at the exact pushed PR head. Tests include title/redirect/disambiguation
refusal, nonexistent page, canonical mismatch, date bounds/locale,
source project contamination, daily gaps, 404 unknown, successful
empty result, transport timeout/size/redirect/proxy restrictions,
atomic cap with only one leftover operation, cooldown, malformed
or secret-bearing cached payloads, one-call cache repeat, and offline
CLI preview. User expressly deferred M04 and allowed M06 without
M04 acceptance, so M04 remains unchecked. M07+ untouched.

**GitHub CI, M06 implementation commit
f61cd9ff1d49dc9bf4fec224775dacd021c4888c:**
**25 SUCCESS / 2 intentionally SKIPPED publication checks** at the
final verification, no pending or failed checks. One Python 3.12 job
initially failed in the **pre-existing unrelated**
test_intelligence_singleflight::test_different_queries_still_fetch_in_parallel
timing assertion: two independent calls had each succeeded but the
runner observed peak concurrency 1 rather than 2. The same GitHub
Actions run 44837365393 was retried **once** with --failed; attempt
2 passed with no source changes. All M06 tests passed in CI before and
after. This is a flaky timing condition, not proof that the unrelated
test is permanently fixed. The PR stays OPEN/DRAFT/unmerged.
- **Library:** existing `requests`; source Wikimedia Analytics API.
- Map user-observed topics to unambiguous page titles with language/project metadata; compare normalized pageview windows; disambiguation and missing article are not zero interest.
- **Acceptance:** daily series and same-length comparison periods for one known page, stable cache, HTTP/429 tests, article rename/disambiguation handling.

#### [x] M07 — Hacker News via Algolia
**LIVE VERIFIED — 2026-11-20 UTC.** The user explicitly authorized
continuing beyond M06 while deferring M04. HN Search powered by
Algolia offers a public keyless search_by_date API with stable numeric
objectID, created_at_i, story/comment/show_hn/ask_hn tags, numericFilters,
hitsPerPage and page. This is an indexed community search, not an HN
Firebase census or a verified market-demand measurement.
Implementation: src/mcp_trendpulse/intelligence_hn_algolia.py;
opt-in CLI intelligence hn-discussions with query, tag, days, limit
and --execute, tests/test_mjau_hn_algolia.py, and
docs/hn-algolia-discussions.md.

Strict fixed HTTPS hn.algolia.com origin, no redirects, proxies or
retries, 5s connect/12s read timeout, 160 KiB decoded JSON response
cap, descriptive User-Agent; zero-network preview by default.
Lookback 1–30 days, a 2-hour UTC snapshot anchor, exactly **one
first page of at most 20 source items**, never unbounded pagination.
Original SQLite shared BudgetCache adds dedicated HN source budget
**5 calls per UTC-day**, 2-hour validated cache and durable 429/503
cooldown. No API key, website ownership, paid service or new dependency.

Each accepted item validates stable HN ID, kind/tag, source UTC
timestamp within the requested filter, and story/comment hierarchy.
Duplicate/malformed records or unqueried source-index matches are
marked observed_partial, not complete. Story/Show HN/Ask HN pages
emit **partial daily story mention signals** by distinct story ID;
comment pages count matching comment IDs and distinct parent
story threads, with **no** story signals or invented buyer counts.
Source-reported nbHits is NOT a full census and no sentiment or
relevance judgment is implied. Raw comment bodies, author identities
and unapproved external links are not returned. Missing engagement
measures remain null rather than fabricated zero.

**Bounded real-source acceptance:** A narrow manual query
model context protocol returned valid no_data for 14 recent days.
The manual, user-relevant phrase **AI agents** returned:
story: **10 unique source records** first-page, 550 source-reported
matches (540 outside the page); comment: **10 comments in 8
distinct parent threads**, 1329 source-reported indexed matches
(1319 outside page), **zero** story signals; show_hn: **8 unique
launch posts**, 210 source-reported matches (202 outside page).
All three first-page samples happened to be dated 2026-11-20 UTC,
which is NOT a claim of one-day community momentum. Source item IDs
included 50582844 and 50580804. Identical story/comment requests
repeated from **validated cache with zero network**.
Original source quota **4/5** for 2026-11-20 UTC and SQLite
quick_check=ok. Independent M04 TrendSpy quota remains **2/2**
unchanged. All data is partial, source-specific community evidence,
not paid-customer validation or general search growth.

Deterministic offline verification: **38 M07 tests passed**; combined
M07/M06/M05/M04/source-contract **162 tests passed**, full Ruff clean.
Full local Windows offline suite on M07 code: **1,866 passed,
3 existing unrelated OpenAlex failures, 10 deselected, 3 warnings**.
The failures are the same two OpenAlex local-calendar vs UTC date
assertions around midnight and one plan-only assertion about the
redacted Authorization header label; no M07 tests failed. Full local
green is NOT claimed. Actual GitHub PR CI results are recorded against
the pushed head separately.

**GitHub CI on M07 implementation commit
6293fc149a88ca662c9ea26e0fbb1184b3ed117d:**
24 SUCCESS, 2 expected SKIPPED publish checks, and **1 FAILED**
unrelated live cross-source integration check: Independent MCP
source-combination and cache compatibility, Actions run 44840693560.
Both initial run and a **single controlled retry** (attempt 2)
successfully observed and cache-replayed CORDIS and CELLAR, then
exited around 12s later with a redacted ExceptionGroup before the
third configured source (USAspending) could emit its source result.
That script, scripts/intelligence_cross_source_smoke.py, exercises
three older existing MCP sources and does **not** invoke the new
HN adapter. The exact underlying external connection/status of the
earlier failures is unverified because the smoke redacts exceptions;
do not diagnose them as an M07 defect or a confirmed USAspending outage.
No provider quota bypass, repeated retries, or alteration of that
unrelated smoke script was made.

**Subsequent fresh CI on the documentation-only follow-up head
64313d582239a219047363be84f1a2bab1b97006:**
25 SUCCESS, 2 expected SKIPPED, zero failures/pending, including
the cross-source smoke which **passed without source-code fixes**.
Thus the earlier external failure was transient at least on this
later run, but no long-term provider reliability guarantee is
claimed. This is evidence for that exact tested head only; always
revalidate the actual current PR head. The PR remains OPEN/DRAFT
and unmerged; no deployment or publishing was performed.
M04 stays unchecked until the user's reminder; M08+ untouched.
- **Library:** existing `requests`; source public HN Algolia search.
- Search genuine recent technical discussions and launches using observed topic phrases; dedupe repeated posts by stable ID, distinguish story and comment counts, count unique days/topics not raw repeated mentions.
- **Acceptance:** one bounded query with timestamps and source IDs; handle deletion and pagination cap; no false customer demand.

#### [ ] M08 — Reuse existing GitHub Issues source (no duplicate provider)
- **Library:** current `intelligence_foundation` GitHub Issues adapter.
- Add only a thin normalized signal transform where absent: distinct issue IDs, repository, time, state and topic relevance, source caps and cooldown.
- **Acceptance:** no duplicate GitHub API adapter, owner/repo bias explicit, verified sampled issues and no fabricated independent buyers.

#### [x] M09 ? npm package-download trend
- **Implementation / LIVE VERIFIED 2026-11-21 UTC:** New shared package
  source adapter, opt-in CLI intelligence npm-downloads, deterministic
  offline fixtures and docs/package-download-history.md. Official
  keyless https://api.npmjs.org/downloads/range/last-week/zod returned
  7/7 source-dated daily downloads, **2026-11-13..2026-11-19**,
  total **475,488,459** npm tarball download *events*, 0 missing or
  rejected, 2-day availability lag. Seven source-attributed daily
  npm_package_downloads TrendSignals; provenance official_api.
  Exact repeated CLI command: **cache_hit=true, requests_attempted=0,
  network_performed=false** and identical verified daily total.
  Original SQLite dedicated npm source budget **1/5** on 2026-11-21
  UTC; shared quota DB PRAGMA quick_check=ok.

  Single exact package (also supports URL-encoded scoped names),
  periods seven/30 source days, source identity, inclusive dates,
  partial/missing vs actual zero, nonnegative integer count, UTC
  lag and stale shape checks. Source 404 does not mean zero users.
  Fixed official HTTPS origin, 128KiB body, 5/12s timeout, no
  redirects/proxies/retries, durable 429/503 cooldown and validated
  24-hour cache; zero new dependency/credentials/paid service.
  **npm download events include CI/CD, bots and dependency installs:
  not unique users, customers, search interest or market demand.**
  Focused package fixture tests and repository CI recorded in
  implementation branch; do not merge while related other branch
  conversations remain unresolved.

#### [x] M10 ? PyPI download statistics
- **Implementation / LIVE VERIFIED 2026-11-21 UTC:** Same opt-in
  bounded source adapter and CLI intelligence pypi-downloads
  with normalized PEP503 project names and a seven/30-day window.
  Official https://pypistats.org/api/packages/pydantic/overall?mirrors=false
  returned 181 historical daily without_mirrors observations;
  the selected verified latest **7/7 daily source dates
  2026-11-13..2026-11-19** yielded **285,184,650**
  mirror-excluded Python package download *events*,
  0 missing/rejected, source lag 2 days. Seven typed
  pypi_package_downloads provenance signals use public_api.
  An identical second CLI request was a validated **cache hit,
  requests_attempted=0, network_performed=false**, preserving values.
  Dedicated original SQLite PyPI Stats source budget **1/3** on
  UTC 2026-11-21. M04/M08 state/budgets untouched.

  PyPI Stats is a separately hosted limited-resource public API,
  with daily refresh and ~180-day history. Explicit mirrors=false
  requires without_mirrors source category, refuses mixed categories,
  malformed/duplicate/missing dates, wrong package and invented zero.
  Stable 24-hour cache, max 160KiB response, fixed official
  HTTPS host, no proxy/redirect/retry/account/API key/payment.
  Known mirror clients are excluded; CI/CD still counts.
  **Never add npm and PyPI download counts or represent the totals
  as distinct humans or paying buyers.** See
  docs/package-download-history.md and
  tests/test_mjau_package_downloads.py. M11+ untouched.

**Verified offline on the isolated M09/M10 branch:** 62 dedicated
package-source tests passed; combined M09?M10 + M04/M05/M06/M07/typed
source compatibility 224 passed; full repository Ruff clean and
git diff --check clean. Full Windows repository suite **1,930 passed,
1 previously existing unrelated OpenAlex plan-only redacted
Authorization-header-label assertion failure, 10 deselected and
3 warnings**, all M09/M10 tests passed. The full local suite is
NOT claimed green. Review the specific GitHub CI results at the
actual pushed branch head rather than inferring green CI from local.

#### [ ] M11 — Stack Exchange API
- **Library:** existing `requests`; free API with quota/backoff instructions.
- Track topic/tag question recurrence and accepted/open problem patterns, without treating questions as search volume or sales.
- **Acceptance:** one limited search/tag call, source-provided throttle honored, metadata + timestamps saved, nonrepresentative-sample caveat.

### Phase C — combine and make useful

#### [ ] M12 — Keyword/phrase extraction and intent hypotheses
- **Libraries:** first existing `nltk`, regex and M02 `rapidfuzz`; add `rake-nltk` only if tests prove improved extraction and its license/dependency suitability.
- Extract observed query terms separately from generated phrase hypotheses; classify informational/problem/commercial intent as **heuristic**; keep original-language evidence; rank relevance without inventing search volume or SEO competition.
- **Acceptance:** multilingual fixtures and source-to-keyword provenance, deterministic duplicate grouping, human-readable explanation of intent heuristic.

#### [ ] M13 — Historical momentum and trend lifecycle
- **Libraries:** existing `pandas` / `statistics`; add optional `statsmodels` STL only after enough comparable full cycles exist.
- Compare aligned time windows, require minimum sample-days, handle data gaps, first-seen / repeat observations, distinguish one-off spikes, new, accelerating, sustained, seasonal and declining. Do not compare unlike provider units.
- **Acceptance:** controlled increasing/flat/seasonal/irregular synthetic fixtures, an actual source-history test, no false 'growth' when coverage is partial.

#### [ ] M14 — Cross-source evidence, recommendations and final CLI/MCP output
- Reuse all qualified source adapters, normalized schema, RapidFuzz clusters, SQLite provenance and existing CLI/MCP interfaces.
- Produce compact user-facing research: `rising_queries`, `keyword_families`, `country_language_interest`, `independent_attention`, `developer_problem_evidence`, `package_adoption_evidence`, `product_hypotheses`, `data_gaps`, `next_validation_action`.
- Clearly label levels: observed search query / relative interest / source mention / adoption metric / generated keyword / hypothetical business opportunity. Independent source corroboration is not automatic causal proof.
- **Acceptance:** one real multi-source research example with direct primary-source references, one offline deterministic report, readable text+JSON, bounded execution, no GSC/GA4, no fake demand metrics. No new background automation.

## Decision log and deferred/non-scope integrations

- **Bing**: M05 conditional candidate **accepted for evaluation** because Bing Keyword Research and `GetKeywordStats` are query-oriented rather than a site's query-performance report; still requires one verified site to get an account-level API key. Do not claim working automated access until tested.
- **Google official Trends API**: approval-based alpha; do not make it a prerequisite. Reconsider only after public general availability and free costs are verified.
- **Google Search Console, Bing site-performance queries, GA4**: explicitly excluded. Generic keyword research must work without linking an owned site to a source's result selection.
- **Reddit API**: commercial permissions can require a contract; excluded under strict free-only until verified and authorized.
- **Paid keyword datasets/APIs, Google Ads Keyword Planner requiring an Ads authorization process, scraping authenticated dashboards, proxy rotation to defeat limits**: excluded.
- **Existing OpenAlex, TED procurement, CFPB, CORDIS, World Bank etc.** remain intact for their own workflows but are **not required** to make the new global keyword engine function; no further procurement-expansion work under this plan.
- **`feedparser`, `scikit-learn`, `KeyBERT`, `DuckDB`, `ruptures`**: not required; introduce only if source format, profiling or audited workload makes them clearly beneficial.

## Reference documentation (checked on 2026-11-20; recheck at implementation)

- Bing Keyword Research (generic query + global geography + questions): https://www.bing.com/webmasters/help/keyword-research-628070b6
- Bing Webmaster API access (verified site for account API key): https://learn.microsoft.com/en-us/bingwebmaster/getting-access
- Bing Webmaster REST and legacy retirement notice: https://learn.microsoft.com/en-us/bingwebmaster/
- Bing `GetKeywordStats` parameters: https://learn.microsoft.com/en-us/dotnet/api/microsoft.bing.webmaster.api.interfaces.iwebmasterapi.getkeywordstats
- Bing `GetRelatedKeywords`: https://learn.microsoft.com/en-us/dotnet/api/microsoft.bing.webmaster.api.interfaces.iwebmasterapi.getrelatedkeywords
- BigQuery sandbox no credit card: https://docs.cloud.google.com/bigquery/docs/sandbox
- Official international Google Trends BigQuery source and 30-day partitions: https://cloud.google.com/blog/products/data-analytics/international-google-trends-datasets-in-bigquery
- RapidFuzz library: https://github.com/rapidfuzz/RapidFuzz
- Google Trends background: https://developers.google.com/search/docs/monitor-debug/trends-start

## Progress ledger

| Milestone | State | Verification and commit | Notes |
| --- | --- | --- | --- |
| M00 | COMPLETE — 2026-11-20 | PR #328; `e27bcd803391ed6a28dd64ed83f520ab30f4fc66`; 1,888 tests, Ruff clean, 14/14 CI, live smoke 15/15 | Offline signal contract/CLI and source inventory verified; existing RSS and BigQuery must be reused |
| M01 | COMPLETE — 2026-11-20 | PR #328; `5337ea8f10f68fb83d46e8341342fe94de5b0832`; 1,912 tests, Ruff clean, 14/14 CI; US+GB 10 labels each, one RSS call per market | Existing TrendSpy RSS reused; offline/opt-in CLI; M00 signal provenance, 15-min cache, 12/day local budget, safe related news. Next M02 |
| M02 | COMPLETE — 2026-11-20 | PR #328; `0c29f7ccb9f7677622e6e3922b1646b0cf8e9a8e`; RapidFuzz 3.14.6 locked; 1,937 tests and Ruff clean; 14/14 CI | Offline 200-signal lexical clusters, market/language isolation, branded/polarity safeguards; M03 next |
| M03 | COMPLETE — 2026-11-20 | PR #328; implementation df41073; focused 39 passed and full Ruff clean; real US rising Top 5, 2026-11-18, 61,072,200 dry-run bytes <=104,857,600 maximum; five source rows, zero rejected | Project trendpulse-new ACTIVE with billing disabled and no attached account; GB 2026-11-19 no data, GB 2026-11-18 >100 MiB refused; local budget 3/3 UTC day; source ranks not absolute volumes |
| M04 | IMPLEMENTED/OFFLINE VERIFIED; LIVE PENDING — 2026-11-20 | PR #328; original feature 5e2d279a00f453c1521204fc4b6faa27da2d93f3; M04 adversarial source/cache hardening on feature branch; 70 focused tests, full Ruff clean, local full 1,747 passed / 1 existing unrelated failure / 10 deselected | Original SQLite quota directory accessible; historical shared TrendSpy provider daily budget 2/2 used on 2026-11-20; actual M04 CLI refused with zero provider operations; no live source observation until UTC reset; M04 remains unchecked |
| M05 | COMPLETE — 2026-11-20 | PR #328; implementation c721e008dae1bc8dac4efd991957f4ebbb70d708; 88 focused pass, full Ruff clean, 1,783 full-local pass / 3 unrelated fails; CI at M05 implementation head 25 success / 2 expected skip; live Bing GET stats 24 history rows (6 emitted), related 100 rows (10 emitted), both HTTP 200; zero-call cache repeats | Arbitrary crochet patterns US/en-US (no siteUrl), Bing exact/broad impression semantics, original UTC-day local budget 3/3, no key leaks/paid fallback; M04 remains unchecked per user |
| M06 | COMPLETE — 2026-11-20 | PR #328; implementation f61cd9ff1d49dc9bf4fec224775dacd021c4888c; 109 focused pass and full Ruff clean; 1,828 full-local pass / 3 unrelated existing fails / 10 deselected; GitHub CI 25 success / 2 expected skip after one unrelated Python 3.12 concurrency-test retry; 14 sourced daily views across 7+7 days, cache repeat 0 calls | Canonical en.wikipedia.org Python programming language page; prior 26,965 vs current 25,846 views (−4.15%, not search volume), original M06 daily quota 2/4, M04 deferred unchanged; no new dependencies/paid services |
| M07 | COMPLETE — 2026-11-20 | PR #328; code 6293fc149a88ca662c9ea26e0fbb1184b3ed117d; 38 focused/162 mixed tests pass, full local 1,866 pass / 3 unrelated old OpenAlex fails, full Ruff clean; first CI had unrelated transient cross-source failure, follow-up head 64313d5 green **25 success/2 expected skip** | Live AI agents first-page sample: 10 stories (provider 550), 10 comments across 8 threads (1329), 8 Show HN launches (210); 0-call cache hits; HN quota 4/5 and M04 quota unchanged; PR remains draft/unmerged |
| M08 | ☐ NOT STARTED | — | — |
| M09 | COMPLETE ? 2026-11-21 source-live verified | npm zod Nov13?19: 7/7 daily counts, 475,488,459 downloads, no missing, two-day source lag, exact 0-network cached repeat, quota 1/5 | Counts include CI/bots/dependency installs and are not unique users; independent implementation PR, M04/M08 untouched |
| M10 | COMPLETE ? 2026-11-21 source-live verified | PyPI Stats pydantic without_mirrors Nov13?19: 7/7 daily counts, 285,184,650 downloads, two-day lag, source history 181 dates, cache repeat 0 network, quota 1/3 | Excludes known mirrors but CI remains included; distinct ecosystem no npm sum, no purchase/unique-user claim, independent implementation PR |
| M11 | ☐ NOT STARTED | — | — |
| M12 | ☐ NOT STARTED | — | — |
| M13 | ☐ NOT STARTED | — | — |
| M14 | ☐ NOT STARTED | — | — |

**How to update:** Replace a milestone's `[ ]` with `[x]` only after all gates and actual bounded live verification pass. Change progress-ledger state to `COMPLETE`, with commit/PR, test evidence and next task. For failures use `BLOCKED` or for M05 `SKIPPED` (reason), not `COMPLETE`. Do not check future steps speculatively.

## Ready-made prompt for another conversation

> In `AKzar1el/mcp-trendpulse`, find the file `.planning/mjau-plan.md` on branch `feat/free-intelligence-8-lanes-20261118` (draft PR #328) or on `main` if merged. This is the canonical **mjau plan**. Read it fully, inspect current repo and source status, and implement exactly the next unchecked milestone with tests and a quota-safe live verification. Respect free-only, global/domain-independent research, and no GSC/GA4. Update the same plan with evidence and commit references. Do not start the following milestone until the current one passes its gates.
