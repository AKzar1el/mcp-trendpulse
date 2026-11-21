# MJAU v3 — Evidence Quality, Identity and Specialist Intelligence

**Track:** V3 (Agent 2), one of two complementary, parallel workstreams.  
**Status:** PLANNED / SELECTED FOR PROOF; **zero v3 features implemented or accepted** at time of split (2026-11-21).  
**Repository:** https://github.com/AKzar1el/mcp-trendpulse  
**Planning branch:** `research/mjau-v2-plan-20261121` (planning-only; not the original v1 feature branch).  
**This plan:** `.planning/mjau-v3-plan.md`. **Companion:** [MJAU v2](https://github.com/AKzar1el/mcp-trendpulse/blob/research/mjau-v2-plan-20261121/.planning/mjau-v2-plan.md).  
**Original MJAU v1:** `.planning/mjau-plan.md` on `feat/free-intelligence-8-lanes-20261118`, draft PR #328. Separate v1 PRs #370–#374 may be in flight; do not modify them.  
**Owned IDs:** A04, A05, A09, A10, A11, B05, B06, B08, B09, B10, B18, B19, B20, B22, B23, B24, B26, B27, B28, B29, B30.  
**Scope balance:** 21 of 41 total candidates (7 selected for testing, 14 research-only). Companion owns 20.  
**User mandate:** **Test each candidate against v1, prove genuine usefulness, or discard it.** Nothing automatically ships.

## 0. Agent assignment and coordination

**Agent 2 mission:** Resolve identities, measure evidence provenance and historical quality, validate MCP interoperability, add bounded security/health/science/energy/consumer/standards datasets and optimize tool selection only if benchmarked.

**Exclusivity:** This agent owns only the IDs in THIS document. The other agent owns disjoint IDs, and neither is allowed to implement the other's adapters, modules, datasets, benchmarks or internal search tools. Cross-track requirements are reported as proposals, not silent edits to the other track. **No ID is owned by both agents.**

**Selected-for-proof:** A04, A05, A09, A10, A11, B08, B09. This means bounded experiments/testing may be undertaken when the operator launches the agent; it is **not a commitment to keep the feature**. Each milestone must meet pass-or-discard gates. **Research-only:** B05, B06, B10, B18, B19, B20, B22, B23, B24, B26, B27, B28, B29, B30; investigate feasibility and keep notes, but do not implement these without an additional explicit user decision.

**Work isolation:**
- Before writing, read this plan by **exact GitHub branch/path**, read v1's current M00/M14 contracts and PR state, and check worktree status. `main` currently lacks much of v1; never accidentally build a v2/v3 implementation against plain `main` while assuming v1 APIs exist.
- Use your own repo worktree/clone and branch prefix `feat/mjau-v3-evidence-`, based on an explicitly pinned, tested v1 staging commit agreed at agent start. Record that SHA in each PR; later update to v1's settled merge base only after review. Two agents must not share an active working directory, Codexify session state, mutable git index or PR branch. Independent worktrees are supported by Git: https://git-scm.com/docs/git-worktree.
- Own files under `src/mcp_trendpulse/mjau_v3/`, `tests/test_mjau_v3_*.py`, and `docs/mjau-v3/` in your own branch. This ownership is **proposed isolation for new files**, not permission to restructure the original repository. Prefer reusing existing stable v1 modules via imports/composition.
- Both agents must **not independently edit** `src/mcp_trendpulse/cli.py`, `intelligence_mcp.py`, `intelligence_signal.py`, `intelligence_core.py`, shared cache/config/credentials, `pyproject.toml`, `uv.lock`, root README, CI workflows, `.planning/mjau-plan.md`, or the other track's plan/source/tests. Queue common-file changes for **one designated integration owner after both tracks' passing proofs**.
- Each agent records its own decision ledger as versioned notes in `docs/mjau-v3/` on its isolated implementation branch. Treat this planning branch and both plan documents as read-only while parallel coding proceeds; do not have two agents concurrently update the same GitHub plan file.
- Do not enter the existing MJAU v1 Windows worktree, reset ACLs, bypass `.request_locks`, reset quotas, or silently open paid APIs. Use a distinct test-only local SQLite/cache directory (never overwrite the v1 state); count upstream quotas separately and coordinate bounded live probes so concurrent work does not exceed provider shared limits.
- Independent testing may begin while v1 is unfinished, but shared CLI/MCP wiring, release, merges to main and provider schedule changes **wait for v1 stability and a single reviewed integration pass**. This is how parallel execution saves time without racing against M14.
- No added permanent worker, tunnel, production polling, paid compute, token/secret in chat/repo or release permission. Existing community MCP, production, PR #328 and child drafts stay untouched.

**Read-only exchange format:** Emit existing validated v1 `TrendSignal` records and optional offline source-attributed JSON snapshots (with original source IDs, timestamp meanings, units, geo/language and coverage). No consumer may assume unverified data is a complete source population. Consume v1-compatible saved records without rewriting v2's collectors; any new cross-source schema or policy is an integration proposal, not a unilateral mutation. Do not introduce a shared mandatory dependency before M14 contracts are frozen.

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

## 2. THIS TRACK ONLY — selected candidates to prove (7)

A-series selected capabilities (research selection is **NOT** acceptance):

| ID | Priority / proof status | Feature | Incremental source/benefit | Acceptance limitation |
| --- | --- | --- | --- | --- |
| A04 | P1 / SELECTED-FOR-PROOF | Wikidata entity identity and multilingual aliases | Exact QID/property/alias lookups from official Wikimedia APIs to support cross-language company/product/topic joins | Absent or ambiguous ID -> unknown; never merge same-looking phrases automatically; no unbounded public SPARQL |
| A05 | P0 / SELECTED-FOR-PROOF | Real historical evidence benchmark | Curated legally obtained, dated, independently labelable historical topic cases, source-replay offline and blinded evaluation | No synthetic tests used as proof of forecasting power; evaluate precision@K, false positives, abstention, citation correctness, calibration only when valid labels exist |
| A09 | P2 / PILOT-GATED / SELECTED-FOR-PROOF | Consumer App Store competitive catalog | Official Apple iTunes Search API for narrowly requested app terms/countries/IDs | Check metadata use terms and search throttling; avoid storing icons/artwork or other licensed promotional assets; app ranking is not downloads or revenue |
| A10 | P1 / SELECTED-FOR-PROOF | Open-source vulnerability evidence | Official public OSV API: affected package/version, vulnerability ID, publication/update, advisory link | A known vulnerability is not buyer demand; no personal data or automated remediation; limit response/paging despite provider having no fixed cap |
| A11 | P2 / BENCHMARK-GATED / SELECTED-FOR-PROOF | MCP tool discovery efficiency | Benchmark existing FastMCP 3 BM25SearchTransform on the optional intelligence MCP before exposing any search proxy | Only enable when real agent task success/latency/context usage improves; never hide default 16 community tools or bypass permission/authorization policies |

B-series selected for proof:

| ID | Priority / proof status | Candidate | Incremental source/benefit | Free access / limitations |
| --- | --- | --- | --- | --- |
| B08 | VERY HIGH / SELECTED-FOR-PROOF | Official MCP conformance suite + Inspector CLI | Catch protocol drift and real interoperability bugs more directly than unit tests; includes revision-specific requirements | Open-source local developer tooling; check exact spec revision/transport and package-license notices; test only, no hosted service |
| B09 | VERY HIGH / SELECTED-FOR-PROOF | Evidence-origin and syndication graph | Explicitly link press-release rewrites, original publications, same-company/repo events and downstream reporting; prevent false independent corroboration | Prefer standard-library offline graph keyed by verified original ID/URL, publisher and provenance. Does not require another API or a vector DB; extends, not duplicates, existing URL/root dedup |

### Candidate-specific tests — existing A-series

- **A04:** Resolve straightforward named entities and deliberately ambiguous names in at least six languages; reject incorrect automatic merges and preserve Unicode.
- **A05:** Build a replayable dataset with source-observed-at and known-after dates. Start with 20–40 independently reviewed cases if feasible; no fabricated labels. Compare v1 vs v2 top-N relevance, false corroboration, missingness, safety, and resource usage; report sample uncertainty.
- **A09:** Verify a two-country lookup and a title search under Apple terms; output IDs, store links and allowed factual metadata only.
- **A10:** Query one known public package/version plus one known OSV ID, validate advisory identity and missingness, avoid storing entire vulnerability feeds.
- **A11:** Run repeated tool-selection tasks with and without BM25 on the same optional tool catalog, track correct-tool@1, successful invocation, median/p95 time, token/context overhead and wrong-tool rate; preserve access checks and fall back if worse.

### Candidate-specific tests — selected B-series

- **B08:** Run a real isolated MCP process through the official conformance suite for a pinned specification revision; distinguish REQUIRED from extension/not-scored scenarios and report failures without hiding them; never modify running v1 services.
- **B09:** Evaluate real saved news/press-release or software-release source records with common origin and independent sources; demonstrate fewer false independent corroborations than v1 while preserving legitimately distinct sources. No raw publication-copy licensing misuse.

**Execution order within selected work:** (1) A05 baseline/evaluation harness and B09 offline source-origin falsification as separate modules; (2) B08 real-MCP conformance baseline; (3) A04 Wikidata entity joins and A10 OSV vulnerability evidence; (4) A09 Apple catalog pilot; (5) A11 existing FastMCP BM25 on observed tool set only after baseline. Cross-track samples can be imported read-only but no implementation may block on the other agent's unfinished API.

## 3. THIS TRACK ONLY — research backlog (not authorized for implementation; 14 items)

These are free-access **candidates**, not validated production sources. Before implementation they need an additional specific user selection, and all proof gates still apply.

### Original-source candidates (B01–B13)

| ID | Priority / research status | Candidate | Potential unique value | Access, licensing and evidence caveat |
| --- | --- | --- | --- | --- |
| B05 | HIGH / RESEARCH-ONLY | arXiv research-preprint metadata | Observe early research topics and new preprint categories before mature citations, distinct timestamps from OpenAlex | Free public descriptive metadata (CC0); one legacy API request/3 sec across machines; do not redistribute papers or claim commercial adoption |
| B06 | MEDIUM-HIGH / RESEARCH-ONLY | Crossref DOI/publisher corrections | Validate original DOI/publisher IDs, post-publication corrections/retractions and publication-date meaning in MJAU's existing OpenAlex/CORDIS research trail | Free polite REST with no sign-up; premium Metadata Plus explicitly excluded; incremental value must beat existing OpenAlex overlap |
| B10 | MEDIUM / CONDITIONAL | Change-point and seasonality falsification | Detect regime breaks vs one-time spikes only for fully comparable historical series; reduce false trends | Start with existing pandas/statistics; consider optional ruptures/statsmodels only after measurable gain and sufficient observed history; M13 already has conservative lifecycle labels |

### Broader multi-industry candidates (B14–B30)

| ID | Niche | Potential candidate and distinctive question | Official free path / caveat | Feasibility decision |
| --- | --- | --- | --- | --- |
| B18 | Practical security urgency | **CISA KEV + FIRST EPSS:** confirmed known-exploited CVE catalog and distinct model-estimated exploitation likelihood enrich A10 OSV; adds change chronology | Official CISA CC0 JSON mirror; EPSS free no-registration small-batch lookup. **Never conflate KEV confirmation with EPSS probability or a buyer budget** | VERY HIGH / RESEARCH-ONLY |
| B19 | Health and biomed innovation | **ClinicalTrials.gov API v2:** registered trial status, sponsors, interventions and dated trials; emerging clinical research activity | NLM public REST/OpenAPI 3; no patient-level data. A registered study is not treatment efficacy or business demand | HIGH / RESEARCH-ONLY |
| B20 | Public biomedical research funding | **NIH RePORTER v2:** funded grants, organizations and research aims; distinguish actual awards from research papers | US NIH official API; recommend <=1 request/second and bounded pages. NIH award != commercial product purchase | HIGH / RESEARCH-ONLY |
| B22 | Research-organization identity | **ROR registry:** exact institution IDs for OpenAlex, Crossref and NIH joins, beyond generic Wikidata names | Free CC0 global open API. Institutions are not businesses/buyers merely because names match | HIGH / RESEARCH-ONLY |
| B23 | Environmental & climate events | **NASA EONET v3:** geolocated near-real-time curated natural event metadata, e.g. wildfire/storm patterns for specialist niches | Public NASA API; curated event selection is not a complete hazard census, insured loss, forecast or safety advisory | MEDIUM / RESEARCH-ONLY |
| B24 | Energy industry analytics | **US EIA Open Data API v2:** electricity/fuels/supply/retail series across US and some international categories; separate from EU ENTSO-E | Free with registration and free key; validate period/frequency/geography/metric, never sum to unlike ENTSO-E values | MEDIUM / RESEARCH-ONLY |
| B26 | Consumer packaged-goods research | **Open Food Facts:** real SKU attributes/category/labels and competitive product catalogs | Public API; ODbL/database and image licenses require legal compatibility review, search <=10/min/IP and product read <=15/min/IP. Crowdsourced data quality varies | MEDIUM / LICENSE-GATED |
| B27 | Consumer product safety | **openFDA food enforcement/recalls:** dated manufacturer/product recall evidence for consumer/food compliance niches | Official keyless low-quota API (or free key); public weekly reporting, changes/lag; cannot infer safety of unlisted products or medical care | HIGH / RESEARCH-ONLY |
| B28 | Revision-aware macroeconomic evidence | **FRED/ALFRED:** retrieve economic time series at the date they were *known* to avoid hindsight bias in opportunity backtests | Free FRED account and API key, with API terms; historical vintages/revisions explicitly supported. Do not duplicate v1 ECB/World Bank series without demonstrated value | HIGH / RESEARCH-ONLY |
| B29 | Technical standards | **IETF Datatracker document JSON:** track public internet-draft/RFC status transitions and standards proposals relevant to emerging technology niches | Simplified doc.json retrieval keyless; distinguish draft from published RFC, and standards work from actual deployment | MEDIUM / RESEARCH-ONLY |
| B30 | Scientific network validation | **OpenCitations Index API:** bounded DOI/PMID incoming/outgoing citation metadata for research-topic diffusion and independent paper chains | Free REST, <=180 calls/min/IP official limit; API token encouraged for integration; citation count alone != adoption, impact, or buyer need; OpenAlex overlap must be measured | MEDIUM / RESEARCH-ONLY |

## 4. Output, quality and proof-before-merge workflow

**This track's responsibility in the final report:** Supply identity/provenance validation, source-dependence diagnostics and contradictions, historical replay/evaluation, exact specialist-domain evidence where permitted, correct MCP behavior, and measured tool-discovery efficiency if applicable. Do not create fake overall demand or prediction probabilities.

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

- Wikidata access: https://www.wikidata.org/wiki/Wikidata:Data_access
- Apple iTunes/App Store search: https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/
- OSV public API: https://google.github.io/osv.dev/api/
- FastMCP BM25 tool-search transform: https://github.com/PrefectHQ/fastmcp/blob/main/docs/v3/servers/transforms/tool-search.mdx
- arXiv metadata API: https://info.arxiv.org/help/api/index.html ; https://info.arxiv.org/help/api/tou.html
- Crossref public REST: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- Official MCP Conformance: https://github.com/modelcontextprotocol/conformance ; Inspector: https://github.com/modelcontextprotocol/inspector
- CISA KEV official JSON mirror (CC0): https://github.com/cisagov/kev-data
- FIRST EPSS public scoring API and 30-day history: https://www.first.org/epss/data.html ; https://www.first.org/epss/faq
- ClinicalTrials.gov API v2: https://clinicaltrials.gov/data-api/api ; https://www.nlm.nih.gov/pubs/techbull/ma24/ma24_clinicaltrials_api.html
- NIH RePORTER v2 public award projects: https://api.reporter.nih.gov/
- ROR research-affiliation registry and CC0 metadata: https://ror.org/about/faqs/
- NASA EONET v3: https://eonet.gsfc.nasa.gov/docs/v3
- US EIA Open Data API: https://www.eia.gov/opendata/
- Open Food Facts usage and license: https://openfoodfacts.github.io/documentation/docs/Product-Opener/api/
- openFDA public recall records and free keyless-tier limits: https://open.fda.gov/apis/food/enforcement/ ; https://open.fda.gov/apis/authentication/
- FRED/ALFRED as-known-on-date historical vintages: https://fred.stlouisfed.org/docs/api/fred/series_observations.html ; https://fred.stlouisfed.org/docs/api/fred/realtime_period.html
- IETF Datatracker document API: https://datatracker.ietf.org/api/
- OpenCitations v2 public REST: https://api.opencitations.net/index/v2/
- Official MCP conformance requirement sets and inspector CLI: https://github.com/modelcontextprotocol/conformance ; https://github.com/modelcontextprotocol/inspector
- Git independent worktrees: https://git-scm.com/docs/git-worktree

### Researched but deliberately not in the implementation backlog

- **GH Archive BigQuery / full bulk GitHub events:** public data exists, but arbitrary scans/downloads could incur nontrivial compute/bytes or exceed a resource-constrained local machine; official privacy-safe GitHub star-history is preferable for A02.
- **Common Crawl wide web index:** free archive but high querying/index/load complexity and poor directly comparable topical denominators. Not a general-market trend estimate.
- **Reddit commercial API, paid Similarweb/keyword volume tools, Google Trends unofficial quota-bypass scraping, Bluesky firehose, paid data brokers:** excluded from this free-only project.
- **TrendRadar / WorldMonitor code copying:** study architecture only. TrendRadar is GPL-3.0; WorldMonitor core is AGPL-3.0-only. Both have obligations incompatible with casually pasting sections into TrendPulse's MIT codebase without a deliberate licensing decision. Their public dashboards do not grant rights to reuse their hosted API outputs.
- **New full framework/vector DB/LLM embedding model:** not justified by current source sizes or demonstrated query errors; avoid unless offline A05 measurements demand it.
- **Competitor ratings, raw estimated users, revenue and global searches from popularity metadata:** unavailable as validated data in the proposed free sources.

## 6. Launch instruction for Agent 2

> Work exclusively on **MJAU v3 Evidence Quality, Identity and Specialist Intelligence** in `AKzar1el/mcp-trendpulse`. Before changing anything, read `.planning/mjau-v3-plan.md` from GitHub ref `research/mjau-v2-plan-20261121` and the canonical v1 plan `.planning/mjau-plan.md` from `feat/free-intelligence-8-lanes-20261118`. Use an isolated worktree and your own `feat/mjau-v3-evidence-*` branch; do not touch v1 active worktrees, PRs #328/#370–#374, shared mutable files or the companion agent's folders. Start with the first selected-for-proof candidate in this document, verify overlap and baseline, perform scoped offline/real free-source tests within provider limits, and record measured incremental usefulness. **If it fails any critical gate or does not improve real usefulness, DISCARD it, rather than integrating it.** Research-only items need separate user selection. Send one candidate's evidence and decision at a time for review. No merge/release/secret/billing/schedule change without user approval.

## 7. Accountability checkpoint

- **Selected for proof:** A04, A05, A09, A10, A11, B08, B09; 7 total, none accepted yet.
- **Research-only, not automatically implementable:** B05, B06, B10, B18, B19, B20, B22, B23, B24, B26, B27, B28, B29, B30; 14 total.
- **Other track owns exclusively:** A01, A02, A03, A06, A07, A08, B01, B02, B03, B04, B07, B11, B12, B13, B14, B15, B16, B17, B21, B25.
- **One decision owner for central integration:** not assigned yet; the parallel agents must not merge each other's work.
- **No work was started by this plan split.** Split is documentation and task ownership only; no tests run or external source acceptance is implied.
