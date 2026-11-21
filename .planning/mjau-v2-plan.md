# MJAU v2 — Discovery, Competition and Market Signals

**Track:** V2 (Agent 1), one of two complementary, parallel workstreams.  
**Status:** PLANNED / SELECTED FOR PROOF; **zero v2 features implemented or accepted** at time of split (2026-11-21).  
**Repository:** https://github.com/AKzar1el/mcp-trendpulse  
**Planning branch:** `research/mjau-v2-plan-20261121` (planning-only; not the original v1 feature branch).  
**This plan:** `.planning/mjau-v2-plan.md`. **Companion:** [MJAU v3](https://github.com/AKzar1el/mcp-trendpulse/blob/research/mjau-v2-plan-20261121/.planning/mjau-v3-plan.md).  
**Original MJAU v1:** `.planning/mjau-plan.md` on `feat/free-intelligence-8-lanes-20261118`, draft PR #328. Separate v1 PRs #370–#374 may be in flight; do not modify them.  
**Owned IDs:** A01, A02, A03, A06, A07, A08, B01, B02, B03, B04, B07, B11, B12, B13, B14, B15, B16, B17, B21, B25.  
**Scope balance:** 20 of 41 total candidates (8 selected for testing, 12 research-only). Companion owns 21.  
**User mandate:** **Test each candidate against v1, prove genuine usefulness, or discard it.** Nothing automatically ships.

## 0. Agent assignment and coordination

**Agent 1 mission:** Find emerging topics, rivals, releases, software ecosystem adoption, public media/social attention and public market/regulatory/skills/procurement context.

**Exclusivity:** This agent owns only the IDs in THIS document. The other agent owns disjoint IDs, and neither is allowed to implement the other's adapters, modules, datasets, benchmarks or internal search tools. Cross-track requirements are reported as proposals, not silent edits to the other track. **No ID is owned by both agents.**

**Selected-for-proof:** A01, A02, A03, A06, A07, A08, B01, B02. This means bounded experiments/testing may be undertaken when the operator launches the agent; it is **not a commitment to keep the feature**. Each milestone must meet pass-or-discard gates. **Research-only:** B03, B04, B07, B11, B12, B13, B14, B15, B16, B17, B21, B25; investigate feasibility and keep notes, but do not implement these without an additional explicit user decision.

**Work isolation:**
- Before writing, read this plan by **exact GitHub branch/path**, read v1's current M00/M14 contracts and PR state, and check worktree status. `main` currently lacks much of v1; never accidentally build a v2/v3 implementation against plain `main` while assuming v1 APIs exist.
- Use your own repo worktree/clone and branch prefix `feat/mjau-v2-discovery-`, based on an explicitly pinned, tested v1 staging commit agreed at agent start. Record that SHA in each PR; later update to v1's settled merge base only after review. Two agents must not share an active working directory, Codexify session state, mutable git index or PR branch. Independent worktrees are supported by Git: https://git-scm.com/docs/git-worktree.
- Own files under `src/mcp_trendpulse/mjau_v2/`, `tests/test_mjau_v2_*.py`, and `docs/mjau-v2/` in your own branch. This ownership is **proposed isolation for new files**, not permission to restructure the original repository. Prefer reusing existing stable v1 modules via imports/composition.
- Both agents must **not independently edit** `src/mcp_trendpulse/cli.py`, `intelligence_mcp.py`, `intelligence_signal.py`, `intelligence_core.py`, shared cache/config/credentials, `pyproject.toml`, `uv.lock`, root README, CI workflows, `.planning/mjau-plan.md`, or the other track's plan/source/tests. Queue common-file changes for **one designated integration owner after both tracks' passing proofs**.
- Each agent records its own decision ledger as versioned notes in `docs/mjau-v2/` on its isolated implementation branch. Treat this planning branch and both plan documents as read-only while parallel coding proceeds; do not have two agents concurrently update the same GitHub plan file.
- Do not enter the existing MJAU v1 Windows worktree, reset ACLs, bypass `.request_locks`, reset quotas, or silently open paid APIs. Use a distinct test-only local SQLite/cache directory (never overwrite the v1 state); count upstream quotas separately and coordinate bounded live probes so concurrent work does not exceed provider shared limits.
- Independent testing may begin while v1 is unfinished, but shared CLI/MCP wiring, release, merges to main and provider schedule changes **wait for v1 stability and a single reviewed integration pass**. This is how parallel execution saves time without racing against M14.
- No added permanent worker, tunnel, production polling, paid compute, token/secret in chat/repo or release permission. Existing community MCP, production, PR #328 and child drafts stay untouched.

**Read-only exchange format:** Emit existing validated v1 `TrendSignal` records and optional offline source-attributed JSON snapshots (with original source IDs, timestamp meanings, units, geo/language and coverage). No consumer may assume unverified data is a complete source population. Provide bounded source artifacts without implementing v3's origin graph or inventing a unified popularity score. Do not introduce a shared mandatory dependency before M14 contracts are frozen.

## 1. Non-negotiable scope and proof gate

## 1. Goal and non-negotiable constraints

Build an unusually useful but lightweight global, domain-independent, evidence-first intelligence system: discover new topics, compare independent public observations, find existing alternatives, make product and keyword research more actionable, and avoid false demand claims. Make each addition justify its complexity and provider cost.

- **Free-only, including execution**: no credit-card dependency, billable cloud project, subscription, API credits, external model inference fees, paid proxies, scraping around technical safeguards, or quota evasion. Free/public endpoints are not automatically licensed for unrestricted commercial reuse.
- Reuse MJAU v1's Pydantic TrendSignal contract, strict source identity, SQLite request budgets/cache/locks, CLI and separate opt-in intelligence MCP. No parallel replica of its collectors. V1 already covers Google Trends RSS/Explore/BigQuery, Bing keyword research, Wikimedia pageviews, Hacker News Algolia, GitHub Issues, npm/PyPI downloads, Stack Exchange questions, lexical phrase families, source-scoped lifecycle analysis and planned M14 cross-source reporting.
- No GSC, GA4, website-dependent keyword recommendations or SEO-property integrations in this initiative. No permanent additional worker, new tunnel, background scheduler, browser scraping or outbound marketing. Normal 16-tool community MCP and hourly workers remain unchanged until separately authorized.
- Prefer existing Python dependencies and stdlib, tiny bounded HTTP responses, offline summaries, deterministic tests and explicit opt-in execution. The operator's Windows device is resource-constrained; no required local LLM, vector DB, full-text crawl or giant archives.
- Respect country, language, publisher, original source URL/ID, timestamp meaning, measurement unit, sampling basis, completeness and original source licensing. Never sum unlike measurements; a missing observation is unknown, not zero.
- **MJAU v1 must finish independently.** The open M04 rate-limit/availability issue, M08 local request-lock ACL gate and M14 integration are not solved or changed by planning v2. Draft child PRs #370–#374 must not be modified/rebased/merged by this plan.

## 2. Selection framework

Each candidate must be evaluated against five independently measured criteria: (1) incremental decision value over existing MJAU features, (2) lawful no-cost data access and expected source availability, (3) evidence quality and geographic/language scope, (4) implementation/maintenance complexity and quota load, and (5) measured uplift in real research tasks. Qualitative priority below is an initial engineering judgment, not performance proof.

Status vocabulary: SELECTED-FOR-PROOF, PILOT-GATED, RESEARCH-ONLY, LICENSE-BLOCKED, PROVED-USEFUL/ACCEPTED, REJECTED/DISCARDED, IMPLEMENTED-VERIFIED. **Research approval is never release approval, and every v2 item is unimplemented and unverified as of this document revision.**

### MANDATORY, NON-NEGOTIABLE PASS-OR-DISCARD RULE (user direction)

**A feature, data adapter, library or MCP function enters the final product ONLY if ALL applicable gates pass. There is no grandfathering for A01–A11 or the four additionally selected B items.** No increase in tool count, code lines, star count or API count alone counts as usefulness. A candidate that fails a mandatory gate is marked **REJECTED/DISCARDED**, its experimental code is excluded/reverted from v2 merge/release, and the evidence/decision is briefly retained in the research ledger so the same failed approach is not reinvented.

1. **Distinct usefulness:** document at least one meaningful user decision/question that v1 cannot already answer as reliably, or a prespecified improvement to a real workflow. Check for existing overlap first, including MJAU M14. No duplicate service, cosmetic schema or busywork wrapper.
2. **Lawful genuinely free access:** verify official provider terms, commercial-use/attribution/derivative rights, real zero-cost account eligibility, quota, keys and no hidden billing. A 'public URL' does NOT automatically pass this gate. If unavailable or licensing remains unresolved -> **LICENSE-BLOCKED** or **DISCARD**, not shipping.
3. **Technical correctness:** targeted deterministic happy/negative/edge tests pass: malformed/empty/stale/partial data, 401/403, 429/503, timeouts, collisions, missing dates, duplicate sources, wrong country/language, privacy and secret redaction. Full relevant v1 regression/tests/lint must not regress; document unrelated failures rather than hiding them.
4. **Observed real acceptance:** for data features, perform one small legitimate, bounded end-to-end request (plus validated zero-network cache replay where supported), preserve exact source/date/unit/provenance, and prove the output's stated semantics. For offline algorithms use at least one actual, previously saved original-source case. For tooling/conformance use a real MCP process/session, not an import-only unit test. **No successful live observation -> cannot pass.** 429/cooldown -> blocked, never bypass or classify as observed zero.
5. **Real utility comparison:** use a *prespecified* set of representative tasks including adversarial no-signal cases, with a recorded v1 baseline. Human- or ground-truth-review independently sourced answers. Must demonstrate a genuinely new validated answer **or** a measurable improvement in correct relevant leads, source traceability, false-positive reduction, actionable clarity, tool-selection success, or lower resource cost. Report both improvements and regressions; do not invent uplift or success probabilities. If there is no defensible measured benefit -> **DISCARD**.
6. **Operational fit:** meet explicit local provider budgets, controlled execution, no automatic retries/extra scheduler, minimal RAM/CPU/dependencies, 8-GB Windows-host compatibility and no weakening of existing production/worker isolation. Bench p50/p95 time, peak memory, calls and cache replay where applicable; no release if a material regression is unresolved.
7. **Independent release review:** all above evidence, versioned test results, source links, license decision and rollback plan are recorded for the precise tested commit. An approved scope proposal or synthetically passing tests alone never authorizes merge or deployment.

**Per-candidate decision record (required):** `ID | baseline user task | tested commit | offline tests & failures | original-source/real-MCP result | observed utility delta | API/license/cost check | resource delta | ACCEPT / BLOCKED / DISCARD | rationale`. A candidate can be retried only after new evidence and explicit owner permission; don't leave dormant experimental functions installed as "just in case".

**Rule applies to all additions in BOTH tracks, including research-only candidates.** No feature in either new agent track has passed these gates yet; researching an API is not implementing or validating the feature.

## 2. THIS TRACK ONLY — selected candidates to prove (8)

A-series selected capabilities (research selection is **NOT** acceptance):

| ID | Priority / proof status | Feature | Incremental source/benefit | Acceptance limitation |
| --- | --- | --- | --- | --- |
| A01 | P0 / SELECTED-FOR-PROOF | Competitor and substitute discovery | Reuse current GitHub/npm/PyPI/TrendPulse search; add official MCP Registry read/search; source-backed map of alternatives, release activity, type and gaps | Discovery lists are not market share, actual users or proof of an unmet need. Same-product duplicates must merge only with corroborating identifiers |
| A02 | P0 / SELECTED-FOR-PROOF | GitHub historical project momentum | Official privacy-safe GitHub REST repository stargazer history, public releases; source-specific aligned weekly/daily counts | Weekly boundaries not guaranteed UTC; histories can be affected by removed stars; star count != installs/customers; no individual stargazer harvesting |
| A03 | P0 / SELECTED-FOR-PROOF | Dependency ecosystem intelligence | Official deps.dev v3 API for package versions/dependency graph/project relationships, complementing M09/M10 downloads | Dependency graph edges are not installed-user counts; preserve ecosystem and package identity; cap traversal to avoid crawling |
| A06 | P1 / PILOT-GATED / SELECTED-FOR-PROOF | GDELT DOC 2.0 topical media timeline | Keyless source-specific article/timeline lookups; different from v1's GDELT 15-min raw feed manifest | Only ship after one bounded live, legal, rate-limit-safe feasibility check; normalize vs raw article counts; monitor 429; distinguish syndication |
| A07 | P1 / SELECTED-FOR-PROOF | Hugging Face emerging AI ecosystem | Official public Hub API: model/dataset/Space metadata, created/updated dates, likes/downloads and available trending ranks | AI-only specialist signal; downloads are not users/payments; use metadata only, do not download model weights or gated assets; observe 5-minute quotas |
| A08 | P2 / PILOT-GATED / SELECTED-FOR-PROOF | Social-community attention | Mastodon instance-specific public trends (tags, links, local week history); Bluesky public AppView read/search only if the exact endpoint works legally without paid access | No single social-network/global-population claim; Bluesky searchPosts may 403 despite public docs, so treat as unavailable until verified; no Jetstream/firehose/background crawl |

B-series selected for proof:

| ID | Priority / proof status | Candidate | Incremental source/benefit | Free access / limitations |
| --- | --- | --- | --- | --- |
| B01 | VERY HIGH / SELECTED-FOR-PROOF | OpenSSF Scorecard | Independent open-source repository security/maintenance context alongside A01/A03/A10; spot fragile competitor projects or ecosystems | Free public precomputed REST reports and weekly dataset; check coverage (not every repo scored); missing scores are unknown and not 'unsafe' |
| B02 | VERY HIGH / SELECTED-FOR-PROOF | endoflife.date v1 API | Software EOL/support window identifies objective upcoming migration and compatibility investigation triggers | Free MIT-licensed dataset/API; use v1 not deprecated v0; dates are context, not confirmed budgets |

### Candidate-specific tests — existing A-series

- **A01:** For five source-backed research prompts, list named alternatives with source links, exact matching identifiers where available, what the source does and does not establish, and explicitly missing competitive evidence.
- **A02:** For two well-known public repositories, reproduce provider weekly records on a fixed date window; reject timezone/partial-week mistakes, compare releases against star events without attributing causality.
- **A03:** For an npm and a non-npm package, verify ecosystem-scoped IDs, package versions and graph depth; never interpret a dependent count as users.
- **A06:** Three allowed fixed-origin samples maximum for first pilot, no automatic retry. Compare volume percentage and raw volume, store distinct original publisher/article evidence; a 429 means BLOCKED.
- **A07:** Verify API pagination/date/metric semantics with one bounded model and dataset query. Cache, no heavyweight files, token optional and never exposed.
- **A08:** Verify one instance-bound Mastodon read and one Bluesky post-search attempt only if permitted, never treat a 403 as empty attention. Store minimal public metadata and quote no private content.

### Candidate-specific tests — selected B-series

- **B01:** Validate published Scorecard origin, report age, missing-repo behavior and correct check coverage. Compare actual competitor due-diligence conclusions against v1; absence is unknown, never a zero security score.
- **B02:** Verify exact product/version support windows, revision dates and unknown support policies from official v1 API; test at least one real migration-readiness question against v1.

**Execution order within selected work:** (1) A01 competitive-source map and v1 baseline; (2) A02 GitHub historical stars and A03 deps.dev; (3) B01 Scorecard and B02 EOL as independent small competitor-context trials; (4) A06 bounded GDELT pilot; (5) A07 Hugging Face; (6) A08 public social-access pilot. Each proceeds only if prior selected item has a decision record, not necessarily ACCEPT (a documented DISCARD permits moving on).

## 3. THIS TRACK ONLY — research backlog (not authorized for implementation; 12 items)

These are free-access **candidates**, not validated production sources. Before implementation they need an additional specific user selection, and all proof gates still apply.

### Original-source candidates (B01–B13)

| ID | Priority / research status | Candidate | Potential unique value | Access, licensing and evidence caveat |
| --- | --- | --- | --- | --- |
| B03 | HIGH / RESEARCH-ONLY | Eclipse Open VSX Registry | Developer-extension marketplace alternatives, public versions and download counts; useful for tool/distribution niches | Public vendor-neutral registry, but not equal to Microsoft's VS Marketplace; verify public API contracts and counter semantics |
| B04 | HIGH / RESEARCH-ONLY | APIs.guru OpenAPI directory | Map existing APIs, recently added providers and API alternatives before recommending another developer-tool idea | Free REST and CC0 contributed specs; sourced third-party API definitions may have different rights; directory includes paid APIs, so index != free execution |
| B07 | MEDIUM-HIGH / CONDITIONAL | GitHub Discussions public developer Q&A | Adds maintainer discussions and resolved/unresolved workflow questions not always represented in Issues/HN | Official GraphQL requires appropriate free GitHub token/permissions; opt-in repository queries, no new personal data, no broad user crawl |
| B11 | MEDIUM / RESEARCH-ONLY | Wikimedia new-page discovery | New article creation can generate seedless emerging topics outside developer ecosystems, complementary to M06 existing pageviews | Official MediaWiki recentchanges action query, bounded 30-day recent window; community editorial activity != public interest or paid demand |
| B12 | HIGH / RESEARCH-ONLY | Competitor changelog and release-event extraction | Turn existing locally saved RSSHub/changedetection or GitHub release snapshots into comparisons: feature additions, breaking changes, pricing-page change hints | Reuse existing locally opt-in RSSHub/changedetection; no broad website crawling, license-violating scraping or unattended monitoring |
| B13 | HIGH POTENTIAL / LICENSE-GATED | ecosyste.ms packages/repositories/usage metadata | Very broad cross-registry dependency, release and repository graph could accelerate A01/A03 | Public APIs and data advertise CC BY-SA 4.0 and separate commercial licenses; check precise use/redistribution obligations and operational rate policies before using in a commercial-facing output; no automatic inclusion |

### Broader multi-industry candidates (B14–B30)

| ID | Niche | Potential candidate and distinctive question | Official free path / caveat | Feasibility decision |
| --- | --- | --- | --- | --- |
| B14 | US policy & compliance | **Federal Register REST:** upcoming/proposed/final rules by agency and date; what regulation changed, exactly when and with what status? Complement v1 EU CELLAR | Public JSON/CSV, no API key; distinguish proposal/publication/effective deadlines and amendment chains | HIGH / RESEARCH-ONLY |
| B15 | Skills, hiring & education | **European Commission ESCO skills/occupation taxonomy:** standardized multilingual role-to-skill joins and skill-gap keywords, bridging v1 ATS jobs | Free online API or selective download in 28 ESCO languages; stable concept identifiers; **taxonomy is not measured job demand**; API-code EUPL licensing review | HIGH / RESEARCH-ONLY |
| B16 | Labor & wage economics | **US Bureau of Labor Statistics public API:** occupation, wages, employment and labor series for targeted market context | Free public HTTP/JSON, optional free registration; stable series IDs, geographic/grain/revision/seasonal adjustment must match | MEDIUM / RESEARCH-ONLY |
| B17 | Entrepreneurship & startup formation | **US Census Business Formation Statistics API:** observed application/formation indices by period/region; an independent business-formation baseline | Public Census time-series API; aggregates, reporting lag and geography, **not buyer intent** or specific company identity | HIGH / RESEARCH-ONLY |
| B21 | Imports, exports & supply chains | **UN Comtrade public/free data:** country-product trade flows and historical changes relevant to industry opportunities | Keyless public preview <=500 records; registered individual free tier currently lists 500 API calls/day, 1/sec. No bulk/premium; verify HS/reporter/partner/unit, coverage and license | MEDIUM-HIGH / RESEARCH-ONLY |
| B25 | Global public-sector procurement | **Open Contracting Data Registry / OCDS:** locate country-specific tender and award datasets beyond existing TED/USAspending, with coverage metadata | Public dataset registry, but per-publisher licenses, update cadence and large downloads differ. Prefer bounded metadata first; no mass downloads | HIGH / LICENSE+FRESHNESS-GATED |

## 4. Output, quality and proof-before-merge workflow

**This track's responsibility in the final report:** Supply a source-backed candidate and alternative landscape: first-seen observations, competitor IDs and releases, developer package relationships, correctly scoped attention/adoption facts, optional jurisdictional/market context, and explicit missingness. Do not publish buyer conversion, SEO volume, market share or causal predictions.

**Shared final report envelope — integration owner only:** discovery, separate attention/adoption metrics, competition, supported problem/possible buyer, source contradictions/quality, and a falsifiable next verification action. Both tracks provide evidence objects; **neither owns central report assembly, shared CLI/MCP registry changes or merge policy**. Keep early prototypes callable as offline Python entrypoints/tests rather than racing to add public MCP tools.

### Required test/quality gates per milestone

- Exact official endpoint and public/free terms confirmed on implementation date. Provider quotas, auth, country/language limits, metric semantics, license and attribution captured in docs.
- Deterministic tests for success, empty, malformed, 401/403, 429/503, timeout, redirects, duplicate IDs, missing/future dates, partial windows, cache poisoning, secret redaction, unsupported language and cross-source mismatch. A negative result never silently becomes zero observations.
- Plan-only mode uses **zero network operations**; live fetch requires explicit execute/opt-in. One bounded legal live sample validates schema and real source semantics; repeat proves zero-network valid cache where appropriate. No repeated automatic retry around 429.
- Preserve previous full compatibility and local-source quota limits. One active writer per branch, independent PR per feature, do not merge without owner review.
- For offline algorithm work require a real historical/source-backed example in addition to synthetic fixtures, and compare against the v1 baseline.
- Measure CPU, peak RAM, JSON output size, cache hit rate, number of provider calls, p50/p95 task wall time and correct top-N lead/tool identification; do not assert productivity improvements without comparison.
- Operate within an 8-GB-RAM Windows host's constraints; no large local model/download, unbounded graph expansion or archive scan.
- Keep synthetic tests separate from independent real-world quality evidence; failing or unavailable provider tests remain visibly blocked.
- No version/release/merge/publish until tests, dependencies, security, license review and owner authorization are documented.

**Per-candidate decision record:** `ID | baseline question | real input / source | tested commit | tests / failures | verified live result or offline-MCP run | v1 vs candidate utility delta | cost/license/quota | runtime/RAM delta | ACCEPT/BLOCKED/DISCARD | why`.

**PASS:** independently verified correct semantics, useful new answer/improvement, no paid/legal/resource/safety regression. **BLOCKED:** unverified license/provider, failed source access (including 429) or missing v1 dependency; do not label complete. **DISCARD:** duplicate, false positives, unproven incremental benefit, unacceptable upkeep/resource cost or reliability/privacy regressions. Revert or isolate discarded prototype from release; document decision. There is **no minimum number of accepted features**.

**Integration acceptance:** after independent proofs, designate one maintainer to unify only ACCEPT features, revalidate against current v1 source, run local integration and real stdio MCP tests, inspect licensed content, approve branches and publish only with separate user authorization. Rebased/merged changes can invalidate previous test evidence; rerun after integration.

## 5. Exclusive public reference inventory

These are references for THIS track only. Source documentation demonstrates a candidate endpoint, **not** successful TrendPulse tests or legal clearance for every reuse scenario.

- MCP official Registry API: https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/api/official-registry-api.md
- GitHub privacy-safe star history: https://docs.github.com/en/rest/activity/starring ; GitHub announcement: https://github.blog/changelog/2026-09-04-new-api-endpoint-provides-privacy-safe-star-history-data/
- Google deps.dev: https://docs.deps.dev/api/v3/
- GDELT DOC 2.0: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
- Hugging Face public APIs and rate tiers: https://huggingface.co/docs/hub/api and https://huggingface.co/docs/hub/rate-limits
- Mastodon source-bounded public trends: https://docs.joinmastodon.org/methods/trends/
- Bluesky AppView: https://endpoints.bsky.app/ ; known post-search auth inconsistency: https://github.com/bluesky-social/bsky-docs/issues/332
- OpenSSF Scorecard and public REST results: https://github.com/ossf/scorecard ; https://api.securityscorecards.dev/
- endoflife.date v1: https://endoflife.date/docs/api/v1/
- Eclipse Open VSX: https://github.com/eclipse-openvsx/openvsx ; https://open-vsx.org/
- APIs.guru OpenAPI directory: https://github.com/APIs-guru/openapi-directory ; https://apis.guru/
- GitHub Discussions: https://docs.github.com/en/graphql/guides/using-the-graphql-api-for-discussions
- MediaWiki recent changes: https://www.mediawiki.org/wiki/API:RecentChanges
- Existing RSSHub and changedetection.io: https://github.com/DIYgod/RSSHub and https://github.com/dgtlmoon/changedetection.io
- ecosyste.ms public API and usage/license notices: https://ecosyste.ms/api and https://ecosyste.ms/
- Federal Register free REST docs: https://www.federalregister.gov/reader-aids/developer-resources/rest-api
- European ESCO public services and datasets: https://esco.ec.europa.eu/en/use-esco/use-esco-services-api ; https://esco.ec.europa.eu/en/use-esco/download
- US Bureau of Labor Statistics developers: https://www.bls.gov/audience/developers.htm
- US Census BFS time-series dataset: https://api.census.gov/data/timeseries/eits/bfs.html
- UN Comtrade free/public preview and tier limits: https://comtrade.un.org/en/api-docs ; https://comtrade.un.org/en/subscriptions
- Open Contracting Data Registry: https://data.open-contracting.org/en/
- OpenSSF precomputed Scorecard REST: https://github.com/ossf/scorecard ; https://api.scorecard.dev/
- Git independent worktrees: https://git-scm.com/docs/git-worktree

### Researched but deliberately not in the implementation backlog

- **GH Archive BigQuery / full bulk GitHub events:** public data exists, but arbitrary scans/downloads could incur nontrivial compute/bytes or exceed a resource-constrained local machine; official privacy-safe GitHub star-history is preferable for A02.
- **Common Crawl wide web index:** free archive but high querying/index/load complexity and poor directly comparable topical denominators. Not a general-market trend estimate.
- **Reddit commercial API, paid Similarweb/keyword volume tools, Google Trends unofficial quota-bypass scraping, Bluesky firehose, paid data brokers:** excluded from this free-only project.
- **TrendRadar / WorldMonitor code copying:** study architecture only. TrendRadar is GPL-3.0; WorldMonitor core is AGPL-3.0-only. Both have obligations incompatible with casually pasting sections into TrendPulse's MIT codebase without a deliberate licensing decision. Their public dashboards do not grant rights to reuse their hosted API outputs.
- **New full framework/vector DB/LLM embedding model:** not justified by current source sizes or demonstrated query errors; avoid unless offline A05 measurements demand it.
- **Competitor ratings, raw estimated users, revenue and global searches from popularity metadata:** unavailable as validated data in the proposed free sources.

## 6. Launch instruction for Agent 1

> Work exclusively on **MJAU v2 Discovery, Competition and Market Signals** in `AKzar1el/mcp-trendpulse`. Before changing anything, read `.planning/mjau-v2-plan.md` from GitHub ref `research/mjau-v2-plan-20261121` and the canonical v1 plan `.planning/mjau-plan.md` from `feat/free-intelligence-8-lanes-20261118`. Use an isolated worktree and your own `feat/mjau-v2-discovery-*` branch; do not touch v1 active worktrees, PRs #328/#370–#374, shared mutable files or the companion agent's folders. Start with the first selected-for-proof candidate in this document, verify overlap and baseline, perform scoped offline/real free-source tests within provider limits, and record measured incremental usefulness. **If it fails any critical gate or does not improve real usefulness, DISCARD it, rather than integrating it.** Research-only items need separate user selection. Send one candidate's evidence and decision at a time for review. No merge/release/secret/billing/schedule change without user approval.

## 7. Accountability checkpoint

- **Selected for proof:** A01, A02, A03, A06, A07, A08, B01, B02; 8 total, none accepted yet.
- **Research-only, not automatically implementable:** B03, B04, B07, B11, B12, B13, B14, B15, B16, B17, B21, B25; 12 total.
- **Other track owns exclusively:** A04, A05, A09, A10, A11, B05, B06, B08, B09, B10, B18, B19, B20, B22, B23, B24, B26, B27, B28, B29, B30.
- **One decision owner for central integration:** not assigned yet; the parallel agents must not merge each other's work.
- **No work was started by this plan split.** Split is documentation and task ownership only; no tests run or external source acceptance is implied.
