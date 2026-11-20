# mjau plan — TrendPulse free global trends and keyword intelligence

> **Canonical task plan.** Refer to this document as **mjau plan** in any ChatGPT/Codexify conversation. Repository: `AKzar1el/mcp-trendpulse`; path: `.planning/mjau-plan.md`; initial staging branch: `feat/free-intelligence-8-lanes-20261118` (draft PR #328). The file is intentionally **not linked from README**. This is still a **public repository**: an unlinked/dot-directory file and the draft branch are discoverable and are **not private**. Never store secrets or internal credentials here.

**Created:** 2026-11-20  | **Status:** M00, M01 COMPLETE (verified)  | **Next task:** M02 — RapidFuzz lexical deduplication.

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

#### [ ] M02 — RapidFuzz keyword normalization, dedup and lexical clusters
- **Library:** add `rapidfuzz` to core only after reviewing binary wheels/lockfile and Windows Python 3.11–3.14 support.
- Normalize Unicode, whitespace and punctuation carefully; preserve diacritics, original phrase, market and language. Exact duplicates first, conservative RapidFuzz near-duplicates second. Do not merge semantic synonyms or translations merely because strings look related.
- **Acceptance:** multilingual regression cases (Slovenian/English and accents), brand names, unrelated lookalikes, stable representative terms, lightweight CPU profiling, no merge across incompatible markets.

#### [ ] M03 — Google Trends official BigQuery dataset (no billing)
- **Source:** public `bigquery-public-data.google_trends` international/US top and rising terms; daily snapshots, source-covered countries only; generally **Top 25** daily, **30-day publication partitions**, historical metric backfills for included terms. This is **not every keyword or exact search-volume data**.
- **Library:** optional `google-cloud-bigquery` with operator-managed sandbox auth; do not require Google Cloud credentials for normal TrendPulse operation.
- **Hard rule:** allow only Google BigQuery **sandbox/no billing account**, query dry run, source/table/partition allowlist, explicit `maximumBytesBilled`, small row limit, date/country partition predicates, local query budget. Sandbox free query tier does not authorize enabling billing.
- **Acceptance:** one bounded public-data query with recorded bytes estimate, a supported country and dates, original source metric semantics; graceful `no_sandbox_credentials` or unsupported geography without paid fallback.

#### [ ] M04 — Google Trends Explore and related search evidence
- **Reuse:** existing `trendspy` and current optional Google Trends `intelligence_keyword_probe` quota/cooldown implementation, not a second client.
- Seed with genuinely observed M01/M03 terms and user-supplied market/topic. Retrieve top/rising related queries and normalized interest where supported; retain timeframe, country and comparative-series basis. Do not derive exact search volume.
- **Acceptance:** one small permitted live request or explicit upstream restriction, cached repeat, 429/cooldown/quota test, correct 'breakout' semantics, no infinite retries/proxies, no website property.

#### [ ] M05 — Bing **global keyword research** through REST/JSON (access-gated, conditional)
- **Purpose:** Bing-wide (not the verified site's) keyword histories, related terms, arbitrary queries, markets/languages, possibly search-volume impressions. No GSC, Bing property performance or any domain-filtered report.
- **Access:** free Bing Webmaster login. Microsoft says a website must be added/verified to create an API key. **This verification is to obtain credentials; not a keyword restriction.** The keyword methods accept `q`, `country`, `language` (and dates for related terms), with **no `siteUrl`**. Must verify this with an unrelated keyword using the live REST API before building a full adapter.
- **REST only:** `GET https://ssl.bing.com/webmaster/api.svc/json/GetKeywordStats` and `/GetRelatedKeywords` with documented parameters; legacy SOAP/POX retired 2026-08-31. Use secure credentials from env/settings; never expose API key in reports, exceptions, trace/log output or persisted URLs. Verify current authentication requirements, response form, provider limits and terms first.
- **Acceptance:** arbitrary non-site keyword tested in at least one country+language; returns documented week/date, impressions/broad vs exact semantics or related terms; compared against Bing Webmaster UI where possible; no dependency on site traffic; graceful no-key/403/429 and hard daily caps.
- **Decision:** **KEEP** only after confirming access is free and live API data is domain-independent. If access cannot be obtained or keywords are site-bound, mark SKIPPED/BLOCKED with proof and continue; never emulate by scraping authenticated UI. Bing search impressions are **Bing-specific**, not Google's or global all-search-market volumes.

### Phase B — independent attention and developer adoption

#### [ ] M06 — Wikimedia Pageviews
- **Library:** existing `requests`; source Wikimedia Analytics API.
- Map user-observed topics to unambiguous page titles with language/project metadata; compare normalized pageview windows; disambiguation and missing article are not zero interest.
- **Acceptance:** daily series and same-length comparison periods for one known page, stable cache, HTTP/429 tests, article rename/disambiguation handling.

#### [ ] M07 — Hacker News via Algolia
- **Library:** existing `requests`; source public HN Algolia search.
- Search genuine recent technical discussions and launches using observed topic phrases; dedupe repeated posts by stable ID, distinguish story and comment counts, count unique days/topics not raw repeated mentions.
- **Acceptance:** one bounded query with timestamps and source IDs; handle deletion and pagination cap; no false customer demand.

#### [ ] M08 — Reuse existing GitHub Issues source (no duplicate provider)
- **Library:** current `intelligence_foundation` GitHub Issues adapter.
- Add only a thin normalized signal transform where absent: distinct issue IDs, repository, time, state and topic relevance, source caps and cooldown.
- **Acceptance:** no duplicate GitHub API adapter, owner/repo bias explicit, verified sampled issues and no fabricated independent buyers.

#### [ ] M09 — npm package-download trend
- **Library:** existing `requests`; public npm downloads endpoint.
- Map package identity, ecosystem and daily/weekly downloads; flag CI/bots and packages with missing history. Downloads are not unique users/customers.
- **Acceptance:** one bounded public package/timeframe query, correct time granularity and cache; missing/invalid package test.

#### [ ] M10 — PyPI download statistics
- **Library:** existing `requests` (or optional `pypistats` only if it substantially simplifies a tested API contract); PyPI Stats public aggregate endpoint.
- Collect Python package daily history; preserve data-source sampling limitations and delivery lag. Normalize concept only for display; **never** add npm and PyPI raw counts.
- **Acceptance:** one bounded observed package, zero vs unavailable tests, source date coverage.

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
| M02 | ☐ NOT STARTED | — | — |
| M03 | ☐ NOT STARTED | — | — |
| M04 | ☐ NOT STARTED | — | — |
| M05 | ☐ NOT STARTED | — | — |
| M06 | ☐ NOT STARTED | — | — |
| M07 | ☐ NOT STARTED | — | — |
| M08 | ☐ NOT STARTED | — | — |
| M09 | ☐ NOT STARTED | — | — |
| M10 | ☐ NOT STARTED | — | — |
| M11 | ☐ NOT STARTED | — | — |
| M12 | ☐ NOT STARTED | — | — |
| M13 | ☐ NOT STARTED | — | — |
| M14 | ☐ NOT STARTED | — | — |

**How to update:** Replace a milestone's `[ ]` with `[x]` only after all gates and actual bounded live verification pass. Change progress-ledger state to `COMPLETE`, with commit/PR, test evidence and next task. For failures use `BLOCKED` or for M05 `SKIPPED` (reason), not `COMPLETE`. Do not check future steps speculatively.

## Ready-made prompt for another conversation

> In `AKzar1el/mcp-trendpulse`, find the file `.planning/mjau-plan.md` on branch `feat/free-intelligence-8-lanes-20261118` (draft PR #328) or on `main` if merged. This is the canonical **mjau plan**. Read it fully, inspect current repo and source status, and implement exactly the next unchecked milestone with tests and a quota-safe live verification. Respect free-only, global/domain-independent research, and no GSC/GA4. Update the same plan with evidence and commit references. Do not start the following milestone until the current one passes its gates.
