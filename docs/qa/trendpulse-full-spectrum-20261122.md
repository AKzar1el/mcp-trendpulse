# TrendPulse V2 - full-spectrum live MCP QA (2026-11-22)

**Scope:** User-authorized real Codexify God v5 TrendPulse Standard+Intelligence V2, 33 read-only tools. Code fix is based on exact main commit 313fd3bf59f440d398eb6342543092bc2030197c. This is an exploratory product/effectiveness review and deterministic fault-injection suite, not a randomized human user study, source-uptime SLA, or forecast. The optional MJAU V3 module remains separate and off.

## How cases were judged

A live task counts as a source success only when the actual connected MCP returned usable, attributable evidence. A bounded, explicit no-evidence outcome is a safe abstention, not a provider pass. Synthetic records and mocked provider responses are exclusively for deterministic correctness, safety and historical leakage tests; they are never called real customers. No paid API purchases, bypassed rate limits, extra worker schedules, private model downloads, changes to other MCP processes or unsafe browser egress.

## Complete 33-tool catalog

All **33** tool contracts were enumerated through the live Codexify schema discovery and checked for requested fields and response scope. Standard 16: get_article_content, get_categories, get_growth, get_interest_by_region, get_news_by_keyword, get_news_by_location, get_news_by_site, get_news_by_topic, get_ranked_trends, get_related_queries, get_related_topics, get_suggestions, get_top_news, get_top_trends, get_trending_terms, get_trends. Intelligence 17: intelligence_analyze_job_postings, intelligence_collect, intelligence_dependency_graph, intelligence_discover_current, intelligence_evaluate_opportunities, intelligence_hf_catalog, intelligence_hunt_current, intelligence_observe_source_snapshots, intelligence_opportunity_lanes, intelligence_plan, intelligence_provider_settings, intelligence_provider_setup, intelligence_release_lifecycle, intelligence_repository_scorecard, intelligence_repository_star_history, intelligence_source_catalog, intelligence_walk_forward_backtest. Catalog advertised **25** source definitions in three waves plus **18** investigation lanes; a catalog entry is not evidence a live endpoint worked.

## Real free-source observations

| Source | Scope | Actual result | Accuracy note |
| --- | --- | --- | --- |
| World Bank | Slovenia SP.POP.TOTL, last 3 | **3:** 2025 2,130,986; 2024 2,127,400; 2023 2,120,461 | Official population data, not software demand |
| OpenAlex | software testing works, limit 3 | **3** bibliographic records | One older 1979 work illustrates query relevance does not imply recency |
| CFPB | mortgage, limit 2 | **2** public structured complaint records | No narratives copied, not population prevalence |
| GLEIF | Microsoft legal-name query, limit 2 | **2** LEI records | Name similarity alone does not prove same legal entity or buyer |
| USAspending | software keyword, limit 2 | **2** federal award records | Broad match can include unrelated large awards; amounts are not software opportunity estimates |
| CORDIS | software public grants, limit 2 | **2** EU project records | Funded titles do not establish product adoption |
| Eurostat | SI demo_pjan, limit 3 | Source unavailable (URLError) | No observations fabricated |
| TED | EU software procurement, limit 2 | Source unavailable (HTTPError) | No tender invented |
| Greenhouse | Stripe board, limit 2 | Download exceeded fixed 256 KiB cap | Public board API returns entire list; safety limit preserved |
| Greenhouse | Sentry board, limit 2 | Source unavailable (HTTPError) | No jobs invented |

Nine fixed-origin query plans were inspected for safety without network; invalid World Bank/ECB identifier forms and missing SEC descriptive User-Agent were blocked before network. OpenAlex reported USD 0.001 query accounting against its published daily free allowance, with no prepaid purchase. Official references: https://help.openalex.org/access/pricing/ and https://help.openalex.org/access/example-costs/. The public Greenhouse Job Board jobs-list endpoint documents no paging parameters: https://docs.greenhouse.io/job-board.html.

## End-to-end source-to-decision workflows

**Five-source chained evidence:** Reused cached CORDIS (2), CFPB (2), GLEIF (2), OpenAlex (3) and USAspending (2) outputs, eleven bounded records total. The live observation tool accepted all five supported source snapshots; it identified two recent dated records, no verified paid buyer, no exact legal-registry join, and insufficient data to estimate 28-day market momentum. World Bank input was explicitly rejected by the nine-source observer allowlist rather than interpreted incorrectly.

**ATS work extraction:** Three synthetic Greenhouse-like posts, including a duplicate job ID and an irrelevant instruction, resulted in two deduplicated descriptions and manual-work, compliance and reliability categories. It did not follow the embedded instruction or claim the job duties establish external purchasing budgets.

**Historical ranking with leakage probes:** Eight deliberately synthetic outcome labels across two as-of cutoffs produced descriptive-only precision@2 of 1 on easy fixture data, not calibrated success probability. Injecting future-dated evidence did not affect earlier folds or scores; invalid localhost outcome URL was rejected and insufficient three-label data abstained. Four separate scenarios were run via the connected walk-forward tool.

**Existing research chain:** A GitHub-issues + OpenAlex reliability research hunt produced a dated public issue; the downstream opportunity reviewer correctly rated the single-source hypothesis monitor, without claiming customer demand or success probability.

## Actual standard/news/trend tool coverage

- Reuters publisher-only headlines: three source-attributed, dated records with distinct HTTPS RSS URLs.
- TECHNOLOGY category: three records; top-news feed: three; London location: three. Slovenia narrow location query returned zero without invented articles.
- Slovenia trending RSS: four terms and bounded related news metadata. Software-related Google Trends category lookup returned eight named category IDs.
- One publisher-article extraction from a Slovenia trend story returned HTTPS source, a parsed title, and metadata; with summarization disabled the tool did not invent a body or summary.
- Risk tests: get_article_content rejected a loopback URL before HTTP, unsupported user input and zero limits were rejected by other standard trend/search tools. Outer FastMCP/Codexify schema errors can be labeled UNAVAILABLE even when rejected locally; this is a separate diagnostic issue.
- Unavailable Google Trends endpoints were not repeatedly hammered; input-validation and injected-worker correctness, rather than provider uptime, were tested for those families.

## Confirmed new correctness defect: ranked Trends provider exceptions

**Live reproduction:** A valid get_ranked_trends request with geo=US, sort=recent_growth_pct and limit=4 returned an unsafe raw upstream TypeError: JSON loads(None). Source tracing found shared _call_trends_async catches asyncio TimeoutError, but lets other exceptions raised inside the TrendSpy worker leak as generic caller errors. get_ranked_trends also did not normalize/validate geography before calling that worker.

**RED:** Three new no-network fake-provider tests failed on unmodified main: provider JSON NoneType error, HTTP 429-like worker exception, and invalid geo reaching source. Two original positive/input tests passed.

**Minimal GREEN fix:** Validate ranked geo with existing normalize_trending_geo before the provider call. Preserve pre-classified ProviderError values; classify any other ordinary worker exception using existing classify_provider_exception, preserving operation/provider context and pre-existing timeout cancellation behavior. No new retries, network origin, source entitlement, quota expansion, or optional V3 registration.

**Test proof:** 214 targeted existing + new trend-input/result/worker tests passed immediately after patch. Extended dedicated fake-provider battery to **23/23 passed**, including five malicious geo forms, lowercase normalization, direct ProviderError identity, semaphore recovery after sequential upstream failures, and nine other TrendSpy-backed tool functions. Full regular repository suite **3,126 passed, 13 process/provider integration tests deselected, 3 nonfatal dependency/test-resource warnings** in 182.91 seconds. A separate isolated real FastMCP stdio child deliberately injected broken upstream JSON and verified sanitized error, valid plan-only follow-on and all 33 tools. Combined with three existing stdio/guarded HTTP integration cases: **4/4 passed** in 73.11 seconds.

## Quality assessment

| Dimension | Verdict | Why |
| --- | --- | --- |
| Discovery/contract breadth | Pass | 33/33 schemas reviewed; standard and intelligence code paths covered |
| Live source retrieval | Useful on tested sources | Six independently named public source families yielded grounded data, with honest upstream abstentions |
| Market-research evidence quality | Pass for tested cases | No fabricated buyer, market growth, exact legal entity or forecast |
| Adversarial/data leakage | Pass | Historical time split, invalid outcomes, ATS duplicate injection, source allowlist |
| Remote protocol/stdio continuity | Pass on isolated tests | 4/4 real subprocess/HTTP process integrations |
| Provider error correctness | Fixed and independently tested | 3 confirmed RED failures turned GREEN, 23/23 extended fault tests |
| Cache and limit safety | Pass on selected repeats | Bounded sources, cached five-source replay and provider quota guards intact |
| Universal upstream availability | Not established | Multiple independently operated source endpoints; no uptime guarantee claimed |

**Release boundary:** The installed Codexify runtime remains on its previous verified pinned wheel until this branch receives exact-head GitHub CI/containers and an independent combined V2 33-tool stdio preflight. Only then use the existing transactional source-only reload, with private config backup and rollback, while preserving all other workers and the separately gated V3 module. The live status after any future reload must be recorded separately; this document does not claim deployment before it occurs.
