# MJAU v2 — Free-Only TrendPulse Intelligence Expansion

**Status:** RESEARCH + APPROVED SCOPE RECORDED; **NO V2 CODE IMPLEMENTED**.  
**Created:** 2026-11-21 (Europe/Ljubljana).  
**Repository:** https://github.com/AKzar1el/mcp-trendpulse  
**Document branch:** research/mjau-v2-plan-20261121 (created from main; planning-only; no PR, merge, deployment, worker, tunnel, or source changes).  
**Canonical MJAU v1 plan:** .planning/mjau-plan.md on feat/free-intelligence-8-lanes-20261118, draft PR #328. This v2 file does not supersede v1, alter its milestone ordering, or authorize starting work in the parallel implementation.  
**Decision:** A01–A11 are selected for the v2 roadmap. B01–B13 are additional researched opportunities **NOT YET APPROVED FOR IMPLEMENTATION**. Some selected A items are gated pilots, not guaranteed operational integrations.

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

Status vocabulary: APPROVED-PLANNED, PILOT-GATED, CONDITIONAL, RESEARCH-ONLY, EXCLUDED, IMPLEMENTED-VERIFIED. **Every A item currently remains unimplemented in v2.**

## 3. Approved core roadmap A01–A11

| ID | Priority / status | Feature | Incremental value and proposed free source | Crucial limitation / acceptance gate |
| --- | --- | --- | --- | --- |
| A01 | P0 / APPROVED-PLANNED | Competitor and substitute discovery | Reuse current GitHub/npm/PyPI/TrendPulse search; add official MCP Registry read/search; source-backed map of alternatives, release activity, type and gaps | Discovery lists are not market share, actual users or proof of an unmet need. Same-product duplicates must merge only with corroborating identifiers |
| A02 | P0 / APPROVED-PLANNED | GitHub historical project momentum | Official privacy-safe GitHub REST repository stargazer history, public releases; source-specific aligned weekly/daily counts | Weekly boundaries not guaranteed UTC; histories can be affected by removed stars; star count != installs/customers; no individual stargazer harvesting |
| A03 | P0 / APPROVED-PLANNED | Dependency ecosystem intelligence | Official deps.dev v3 API for package versions/dependency graph/project relationships, complementing M09/M10 downloads | Dependency graph edges are not installed-user counts; preserve ecosystem and package identity; cap traversal to avoid crawling |
| A04 | P1 / APPROVED-PLANNED | Wikidata entity identity and multilingual aliases | Exact QID/property/alias lookups from official Wikimedia APIs to support cross-language company/product/topic joins | Absent or ambiguous ID -> unknown; never merge same-looking phrases automatically; no unbounded public SPARQL |
| A05 | P0 / APPROVED-PLANNED | Real historical evidence benchmark | Curated legally obtained, dated, independently labelable historical topic cases, source-replay offline and blinded evaluation | No synthetic tests used as proof of forecasting power; evaluate precision@K, false positives, abstention, citation correctness, calibration only when valid labels exist |
| A06 | P1 / PILOT-GATED | GDELT DOC 2.0 topical media timeline | Keyless source-specific article/timeline lookups; different from v1's GDELT 15-min raw feed manifest | Only ship after one bounded live, legal, rate-limit-safe feasibility check; normalize vs raw article counts; monitor 429; distinguish syndication |
| A07 | P1 / APPROVED-PLANNED | Hugging Face emerging AI ecosystem | Official public Hub API: model/dataset/Space metadata, created/updated dates, likes/downloads and available trending ranks | AI-only specialist signal; downloads are not users/payments; use metadata only, do not download model weights or gated assets; observe 5-minute quotas |
| A08 | P2 / PILOT-GATED | Social-community attention | Mastodon instance-specific public trends (tags, links, local week history); Bluesky public AppView read/search only if the exact endpoint works legally without paid access | No single social-network/global-population claim; Bluesky searchPosts may 403 despite public docs, so treat as unavailable until verified; no Jetstream/firehose/background crawl |
| A09 | P2 / PILOT-GATED | Consumer App Store competitive catalog | Official Apple iTunes Search API for narrowly requested app terms/countries/IDs | Check metadata use terms and search throttling; avoid storing icons/artwork or other licensed promotional assets; app ranking is not downloads or revenue |
| A10 | P1 / APPROVED-PLANNED | Open-source vulnerability evidence | Official public OSV API: affected package/version, vulnerability ID, publication/update, advisory link | A known vulnerability is not buyer demand; no personal data or automated remediation; limit response/paging despite provider having no fixed cap |
| A11 | P2 / BENCHMARK-GATED | MCP tool discovery efficiency | Benchmark existing FastMCP 3 BM25SearchTransform on the optional intelligence MCP before exposing any search proxy | Only enable when real agent task success/latency/context usage improves; never hide default 16 community tools or bypass permission/authorization policies |

### Acceptance sketches for A features

- **A01:** For five source-backed research prompts, list named alternatives with source links, exact matching identifiers where available, what the source does and does not establish, and explicitly missing competitive evidence.
- **A02:** For two well-known public repositories, reproduce provider weekly records on a fixed date window; reject timezone/partial-week mistakes, compare releases against star events without attributing causality.
- **A03:** For an npm and a non-npm package, verify ecosystem-scoped IDs, package versions and graph depth; never interpret a dependent count as users.
- **A04:** Resolve straightforward named entities and deliberately ambiguous names in at least six languages; reject incorrect automatic merges and preserve Unicode.
- **A05:** Build a replayable dataset with source-observed-at and known-after dates. Start with 20–40 independently reviewed cases if feasible; no fabricated labels. Compare v1 vs v2 top-N relevance, false corroboration, missingness, safety, and resource usage; report sample uncertainty.
- **A06:** Three allowed fixed-origin samples maximum for first pilot, no automatic retry. Compare volume percentage and raw volume, store distinct original publisher/article evidence; a 429 means BLOCKED.
- **A07:** Verify API pagination/date/metric semantics with one bounded model and dataset query. Cache, no heavyweight files, token optional and never exposed.
- **A08:** Verify one instance-bound Mastodon read and one Bluesky post-search attempt only if permitted, never treat a 403 as empty attention. Store minimal public metadata and quote no private content.
- **A09:** Verify a two-country lookup and a title search under Apple terms; output IDs, store links and allowed factual metadata only.
- **A10:** Query one known public package/version plus one known OSV ID, validate advisory identity and missingness, avoid storing entire vulnerability feeds.
- **A11:** Run repeated tool-selection tasks with and without BM25 on the same optional tool catalog, track correct-tool@1, successful invocation, median/p95 time, token/context overhead and wrong-tool rate; preserve access checks and fall back if worse.

## 4. Deeper research backlog: discoveries beyond A01–A11

**These are not auto-approved.** Their main benefit is new source classes or better validation, not maximizing the number of advertised MCP tools.

| ID | Rank / status | Candidate | Why it might materially help | Free access, licensing and technical caveat |
| --- | --- | --- | --- | --- |
| B01 | VERY HIGH / RESEARCH-ONLY | OpenSSF Scorecard | Independent open-source repository security/maintenance context alongside A01/A03/A10; spot fragile competitor projects or ecosystems | Free public precomputed REST reports and weekly dataset; check coverage (not every repo scored); missing scores are unknown and not 'unsafe' |
| B02 | VERY HIGH / RESEARCH-ONLY | endoflife.date v1 API | Software EOL/support window identifies objective upcoming migration and compatibility investigation triggers | Free MIT-licensed dataset/API; use v1 not deprecated v0; dates are context, not confirmed budgets |
| B03 | HIGH / RESEARCH-ONLY | Eclipse Open VSX Registry | Developer-extension marketplace alternatives, public versions and download counts; useful for tool/distribution niches | Public vendor-neutral registry, but not equal to Microsoft's VS Marketplace; verify public API contracts and counter semantics |
| B04 | HIGH / RESEARCH-ONLY | APIs.guru OpenAPI directory | Map existing APIs, recently added providers and API alternatives before recommending another developer-tool idea | Free REST and CC0 contributed specs; sourced third-party API definitions may have different rights; directory includes paid APIs, so index != free execution |
| B05 | HIGH / RESEARCH-ONLY | arXiv research-preprint metadata | Observe early research topics and new preprint categories before mature citations, distinct timestamps from OpenAlex | Free public descriptive metadata (CC0); one legacy API request/3 sec across machines; do not redistribute papers or claim commercial adoption |
| B06 | MEDIUM-HIGH / RESEARCH-ONLY | Crossref DOI/publisher corrections | Validate original DOI/publisher IDs, post-publication corrections/retractions and publication-date meaning in MJAU's existing OpenAlex/CORDIS research trail | Free polite REST with no sign-up; premium Metadata Plus explicitly excluded; incremental value must beat existing OpenAlex overlap |
| B07 | MEDIUM-HIGH / CONDITIONAL | GitHub Discussions public developer Q&A | Adds maintainer discussions and resolved/unresolved workflow questions not always represented in Issues/HN | Official GraphQL requires appropriate free GitHub token/permissions; opt-in repository queries, no new personal data, no broad user crawl |
| B08 | VERY HIGH / RESEARCH-ONLY | Official MCP conformance suite + Inspector CLI | Catch protocol drift and real interoperability bugs more directly than unit tests; includes revision-specific requirements | Open-source local developer tooling; check exact spec revision/transport and package-license notices; test only, no hosted service |
| B09 | VERY HIGH / RESEARCH-ONLY | Evidence-origin and syndication graph | Explicitly link press-release rewrites, original publications, same-company/repo events and downstream reporting; prevent false independent corroboration | Prefer standard-library offline graph keyed by verified original ID/URL, publisher and provenance. Does not require another API or a vector DB; extends, not duplicates, existing URL/root dedup |
| B10 | MEDIUM / CONDITIONAL | Change-point and seasonality falsification | Detect regime breaks vs one-time spikes only for fully comparable historical series; reduce false trends | Start with existing pandas/statistics; consider optional ruptures/statsmodels only after measurable gain and sufficient observed history; M13 already has conservative lifecycle labels |
| B11 | MEDIUM / RESEARCH-ONLY | Wikimedia new-page discovery | New article creation can generate seedless emerging topics outside developer ecosystems, complementary to M06 existing pageviews | Official MediaWiki recentchanges action query, bounded 30-day recent window; community editorial activity != public interest or paid demand |
| B12 | HIGH / RESEARCH-ONLY | Competitor changelog and release-event extraction | Turn existing locally saved RSSHub/changedetection or GitHub release snapshots into comparisons: feature additions, breaking changes, pricing-page change hints | Reuse existing locally opt-in RSSHub/changedetection; no broad website crawling, license-violating scraping or unattended monitoring |
| B13 | HIGH POTENTIAL / LICENSE-GATED | ecosyste.ms packages/repositories/usage metadata | Very broad cross-registry dependency, release and repository graph could accelerate A01/A03 | Public APIs and data advertise CC BY-SA 4.0 and separate commercial licenses; check precise use/redistribution obligations and operational rate policies before using in a commercial-facing output; no automatic inclusion |

### B01–B13 decision recommendation

First assess **B08 (MCP conformance)** and **B09 (evidence-origin graph)** for inclusion as quality gates rather than new public-facing tools. Next prioritize **B01 (OpenSSF)** and **B02 (software EOL)** for uniquely actionable context. Assess B03/B04/B05 where source-backed user scenarios justify them. B13 remains gated on explicit licensing review. Do **not** automatically turn thirteen candidates into thirteen providers.

### Researched but deliberately not in the implementation backlog

- **GH Archive BigQuery / full bulk GitHub events:** public data exists, but arbitrary scans/downloads could incur nontrivial compute/bytes or exceed a resource-constrained local machine; official privacy-safe GitHub star-history is preferable for A02.
- **Common Crawl wide web index:** free archive but high querying/index/load complexity and poor directly comparable topical denominators. Not a general-market trend estimate.
- **Reddit commercial API, paid Similarweb/keyword volume tools, Google Trends unofficial quota-bypass scraping, Bluesky firehose, paid data brokers:** excluded from this free-only project.
- **TrendRadar / WorldMonitor code copying:** study architecture only. TrendRadar is GPL-3.0; WorldMonitor core is AGPL-3.0-only. Both have obligations incompatible with casually pasting sections into TrendPulse's MIT codebase without a deliberate licensing decision. Their public dashboards do not grant rights to reuse their hosted API outputs.
- **New full framework/vector DB/LLM embedding model:** not justified by current source sizes or demonstrated query errors; avoid unless offline A05 measurements demand it.
- **Competitor ratings, raw estimated users, revenue and global searches from popularity metadata:** unavailable as validated data in the proposed free sources.

## 5. Highest-value integration concept: intelligence report rather than tool sprawl

A v2 research answer should contain six sections with exact evidence classes and explicit missingness:

1. **Discovery:** newly observed term or source-backed entity; source-level first-seen date and geo/language limitations.
2. **Attention/adoption:** distinct search-interest, news, repository stars, package events, AI-Hub metadata and other source units, never a combined fictitious volume.
3. **Competition:** named alternatives, MCP/package/extension/project source links, released versions, maintenance context and unresolved coverage.
4. **Problem/possible buyer:** only originally supported pain/problem descriptions, named purchase or procurement evidence when independently available; no inferred willingness to pay.
5. **Contradictions/quality:** source outages, duplicate origins, missing sampling denominator, promotional/low-evidence material, unverified entity joins and historical gaps.
6. **Action:** a cheap falsifiable next research step, sources to inspect and optional source-aware user workflow; never a fabricated revenue probability.

Expose reusable **evidence objects** before adding new top-level tool names. Return concise text, deterministic JSON and provenance. A01+A02+A03+A04+A05 are the highest-leverage integrated core; others should improve the same existing report, not create a parallel recommendation engine to compete with M14.

## 6. Isolation and sequencing

1. **Research/planning only now.** File resides exclusively on research/mjau-v2-plan-20261121. Do not touch .planning/mjau-plan.md, draft PR #328 or child PRs #370–#374, active Windows Codexify worktree, worker processes, settings, tunnel, CI workflows, releases or secrets.
2. **Finish original MJAU M14 and integration gates independently.** If M04 remains 429 blocked, keep it blocked without forced retries. Respect M08 ACL blocker and do not bypass locks.
3. **Freeze v1 contracts after review.** Compare existing source adapters, CLI options, optional MCP tool names, tests and available local resources to avoid duplicated code.
4. **V2 Stage 0:** A05 evaluation harness/baseline and A01 competitor taxonomy prototype, offline. Capture metrics before adding providers.
5. **V2 Stage 1:** A02 GitHub history, A03 deps.dev, A04 Wikidata; one provider/feature per independent, reviewable PR with strictly bounded source requests. A06 pilot separately.
6. **V2 Stage 2:** A07 AI Hub and A10 OSV; keep as specialist opt-ins. A08 Mastodon/Bluesky and A09 Apple only after account/terms/access pilots pass.
7. **V2 Stage 3:** A11 evaluate BM25 on a representative existing agent task suite; only enable in optional intelligence MCP where it empirically helps.
8. **V2 Stage 4:** Integrate source-attributed reports, real research task comparison, API budgets, licensing, production-compatibility checks. Do not enable new monitoring or permanent background tasks by default.
9. **B backlog:** choose only after A improvements are benchmarked, clear user benefit is documented, and explicit scope approval is given. Conformance/evidence-origin checks may be judged higher-value than another data source.

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

## 7. Verified public references (research on 2026-11-21)

**Approved A references**
- MCP official Registry API: https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/api/official-registry-api.md
- GitHub privacy-safe star history: https://docs.github.com/en/rest/activity/starring ; GitHub announcement: https://github.blog/changelog/2026-09-04-new-api-endpoint-provides-privacy-safe-star-history-data/
- Google deps.dev: https://docs.deps.dev/api/v3/
- Wikidata access: https://www.wikidata.org/wiki/Wikidata:Data_access
- GDELT DOC 2.0: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
- Hugging Face public APIs and rate tiers: https://huggingface.co/docs/hub/api and https://huggingface.co/docs/hub/rate-limits
- Mastodon source-bounded public trends: https://docs.joinmastodon.org/methods/trends/
- Bluesky AppView: https://endpoints.bsky.app/ ; known post-search auth inconsistency: https://github.com/bluesky-social/bsky-docs/issues/332
- Apple iTunes/App Store search: https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/
- OSV public API: https://google.github.io/osv.dev/api/
- FastMCP BM25 tool-search transform: https://github.com/PrefectHQ/fastmcp/blob/main/docs/v3/servers/transforms/tool-search.mdx

**Newly researched B references**
- OpenSSF Scorecard and public REST results: https://github.com/ossf/scorecard ; https://api.securityscorecards.dev/
- endoflife.date v1: https://endoflife.date/docs/api/v1/
- Eclipse Open VSX: https://github.com/eclipse-openvsx/openvsx ; https://open-vsx.org/
- APIs.guru OpenAPI directory: https://github.com/APIs-guru/openapi-directory ; https://apis.guru/
- arXiv metadata API: https://info.arxiv.org/help/api/index.html ; https://info.arxiv.org/help/api/tou.html
- Crossref public REST: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- GitHub Discussions: https://docs.github.com/en/graphql/guides/using-the-graphql-api-for-discussions
- Official MCP Conformance: https://github.com/modelcontextprotocol/conformance ; Inspector: https://github.com/modelcontextprotocol/inspector
- MediaWiki recent changes: https://www.mediawiki.org/wiki/API:RecentChanges
- Existing RSSHub and changedetection.io: https://github.com/DIYgod/RSSHub and https://github.com/dgtlmoon/changedetection.io
- ecosyste.ms public API and usage/license notices: https://ecosyste.ms/api and https://ecosyste.ms/
- GH Archive and Common Crawl excluded reference: https://www.gharchive.org/ and https://index.commoncrawl.org/

## 8. Current decision checkpoint

**Approved for planning:** A01–A11, with explicit pilot/benchmark gates for A06/A08/A09/A11.  
**Researched but pending decision:** B01–B13, especially B08/B09 quality improvements and B01/B02 sources.  
**Not authorized:** code implementation, new automatic jobs, cloud spend, secret installation, merges, deployments, CI churn, MJAU v1 changes or releases.

**Stop rule:** When successive additions do not significantly improve verified usefulness or only raise maintenance/false positives, stop adding APIs. Focus on source-quality reliability, end-to-end usefulness, correctly bounded costs and release.
