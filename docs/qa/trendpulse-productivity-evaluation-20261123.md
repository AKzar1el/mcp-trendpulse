# TrendPulse end-to-end usefulness and efficiency trial (2026-11-23)

**Status:** observed workflow trial and surgical optional response-size improvement. The task matrix was written **after initial exploratory tool calls but before this scoring**; these are assistant-selected cases, **not** a blind, independent, preregistered human evaluation. **Scope:** live Codexify V1/V2 33-tool source plus separately launched, isolated repository-only V3, not a hosted/public V3 deployment. Baseline code is source `48f5c64265abba4b0194591158ec82781ca3fcef`; the connected V1/V2 tool source is the published v0.3.1. No paid APIs, synthetic buyer claims, bypassed Google limits, live changes, worker schedule changes or unreviewed public rollout.

## Measures

Each scenario earns **2 = source-backed decision supported**, **1 = useful partial answer/correct abstention with clear next source**, or **0 = misleading, unsupported or unusable**. A *source-backed* score requires checking the actual evidence payload for correct topic, source, date/scope and interpretation. Each trial also records **wall-clock client roundtrip** (not pure backend execution; excludes model reasoning), calls, response size, source hits or fresh network count when reported, cache usefulness, no-fabrication and whether a source-specific verification step is still needed. Never infer total time saved from the stopwatch alone.

The comparison baseline is a manual source query when possible (official data URL/record, no model summary); measure it on the **same facts**, not on synthetic examples or a different query. If no comparable baseline can be run, mark it **unmeasured** rather than invent speedup percentages. Do not interpret tool-plan validation, cached data or mocked fixtures as live-provider uptime.

## Predeclared user tasks

| ID | User decision | Tool workflow | Checkable outcome / pitfalls |
| --- | --- | --- | --- |
| N1 | Could a newsletter cover *passkeys* with recent citations? | `get_news_by_keyword` headlines-only, then independent source/publisher cross-check | Dated, topic-related titles; no fabricated article contents, no assumption syndicated headlines prove adoption |
| N2 | Can a user isolate a publisher's latest security headlines? | `get_news_by_site` headlines-only, then `get_news_by_topic`/article metadata if needed | Source-domain attribution, time bounds, headline-only limits, uniqueness |
| T1 | What are today's main interest topics in Slovenia? | RSS-backed `get_trending_terms` and `get_top_trends` once each | Present ranked terms/volume bands, disclose source not precise actual search volume; do NOT hammer ranked 24-hour/Explore |
| E1 | Is Node.js 20 vs 22 currently within standard support? | V2 `intelligence_release_lifecycle` exact release records, manual official schedule cross-check | Dates, source freshness, extended/commercial support caveat, no automatic migration claim |
| E2 | Which dependencies does `npm:is-odd@3.0.1` resolve, and is a named repo's OSS posture known? | V2 `intelligence_dependency_graph` and `intelligence_repository_scorecard` | Exact version/scope; dependency graph is not downloads, security or purchasing demand |
| O1 | Does a public issue about software supply chain establish a paying market? | V2 `intelligence_hunt_current` bounded to public GitHub issues and `intelligence_evaluate_opportunities` | Explicit abstention on paying customers, no unsupported precision or buyer forecast |
| O2 | Can source discovery and a one-source factual data query reduce manual research steps? | `intelligence_source_catalog`, `intelligence_collect` official World Bank (Slovenia population), source direct comparison | Correct indicator/year, no sales prediction; distinguish useful source list from actual evidence |
| V3-1 | Can an agent disambiguate similar entity names without a false identity merge? | **Isolated** V3 MCP Wikidata explicit QIDs from another public subject, one capped live request, cache repeat | Exact QID labels and aliases; candidate never confirmed identity; no implicit name search |
| V3-2 | Can an agent flag advisory IDs for an exact version without asserting a package is secure? | **Isolated** V3 MCP OSV npm/PyPI exact versions, one capped live request and replay | Matches source ID list; no raw bodies, false safe/remediation claims or bulk-redistribution approval |

## Counterfactual / guardrails

- The *manual baseline* is official provider lookup for exactly the requested entity/package/timeframe; if it succeeds with less work, say so. Never compare against an intentionally slow or incapable baseline.
- Efficiency gains must be **observed** (e.g. fewer HTTP requests on exact cache replay, fewer manual parsing steps), while local and model orchestration overhead remain separated.
- Include at least one empty, one invalid, one weakly related and one partial-source case to measure correct refusal, not just positive demos.
- No claim of independent human acceptance: this is an assistant-operated evaluation. An independent user/workflow reviewer, V3 rights review and official conformance are separate release gates.

## Results

### User-workflow scorecard (assistant-rated, selected cases only)

| Task | Score / 2 | Observed real output | Important limit |
| --- | ---: | --- | --- |
| N1 newsletter topic | 2 | Six passkey-query headlines dated 2026-11-18 to 2026-11-23; five titles explicitly say passkey/passkeys; Google News RSS source and publisher preserved | One weakly related headline; topic shortlisting is not validation of an article's claims or market demand |
| N2 publisher security news | 1 | Six dated publisher-site results, all identified as The Register; another five TECHNOLOGY topic headlines | Site filtering is not an additional security-keyword filter; relevance and recency order need manual curation |
| T1 Slovenia trending context | 2 | Ten SI terms/volume bands; separate RSS trend items linked to original news about Zofka Kveder, Nika Kovac and football. One Slovenian publisher page yielded 3,479 extracted text characters in full-data mode | Volume bands are not exact searches; RSS does not validate separately limited ranked 24-hour/Explore endpoints |
| E1 runtime upgrade triage | 2 | Endoflife.date Node.js 20 EOL 2026-04-30; Node.js 22 EOL 2027-04-30. Both exact dates independently matched the official `nodejs/Release` `schedule.json` | Third-party lifecycle status does not establish each user's commercial/extended support entitlement |
| E2 package/repo due diligence | 2 | deps.dev exact `npm:is-odd@3.0.1` direct dependency `is-number@6.0.0`; OpenSSF Flask scorecard 7.1 with 2026-11-09 scan date | Platform-specific graph is not all deployment dependencies; dated scorecard is neither vulnerability scan nor security guarantee |
| O1 paying-buyer hypothesis | 1 | One bounded GitHub-issues hunt for MCP authentication found no relevant recent source rows. Independent opportunity evaluator returned `insufficient`, no buyer and `success_probability=null` | Safe abstention, **not** proof no demand exists; no buyer identified |
| O2 discovery and official data | 1 | Three sources OpenAlex/CFPB/TED returned 15 recent dated records in one workflow and one CFPB complaint hypothesis. World Bank SI 2022–2025 population values exactly matched separate direct official API response | Single-source CFPB theme is only an investigation lead; no confirmed buyer, sector growth, or market size |
| V3-1 identity candidates | 2 | Separate two-tool V3 MCP returned labels Google (Q95) and Apple Inc. (Q312); independently verified the labels from Wikimedia's original Action API; different-name cache hit picked the correct different QID | Candidate does not confirm organizational identity or legal registry join |
| V3-2 version advisories | 2 | Isolated V3 MCP projected exactly two IDs for `npm:minimist@0.0.8`, independently matched direct official OSV `/v1/querybatch`; returned only minimal IDs/date/link | No full security assessment, fix advice, live release, commercial redistribution permission or independent human signoff |

**Selected-task score: 15/18.** This is an analyst rubric applied to chosen cases, not a randomized evaluation, a probability of user success, or a measured business/productivity uplift. Correct abstention receives a partial score where it avoids a wrong decision but does not solve the user's business question.

### Independently checked originals and additional useful tool outputs

- Official Node.js lifecycle source: `https://raw.githubusercontent.com/nodejs/Release/main/schedule.json`, `v20.end=2026-04-30`, `v22.end=2027-04-30`.
- Official World Bank original query: `https://api.worldbank.org/v2/country/SI/indicator/SP.POP.TOTL?format=json&per_page=4&mrv=4`. Direct API: 2025 **2,130,986**, 2024 **2,127,400**, 2023 **2,120,461**, 2022 **2,112,076**; all four are identical to the TrendPulse projection. Raw PowerShell direct request was 708 ms locally, **not** comparable to the multi-call connector roundtrip.
- Official Wikimedia Q95/Q312 Action API returned `Google` and `Apple Inc.` labels, in agreement with V3. Official OSV `/v1/querybatch` returned exactly the two minimist IDs `GHSA-vh95-rmgr-6w4m` and `GHSA-xvch-5gv4-984h`, matching V3.
- HF Hub models catalog returned four public `text embedding` matches with original URLs and provider counters, while marking model quality, commercial demand and download-window comparability unverified.
- Flask star-history endpoint returned five weekly cohorts and **declined to calculate** a recent-vs-previous four-week growth comparison due insufficient eligible history. This is useful guardrail behavior, not proof of software adoption.
- An Irish IT framework tender carried a large published procedure estimate but was **not** promoted to a qualifying software buyer opportunity: required lot deadline was absent in the sampled projection and neither software-only spend nor award was verified.

### Efficiency actually observed

| Probe | Observation | What it can / cannot prove |
| --- | --- | --- |
| Isolated V3 subprocess MCP cold start | **2,969 ms** | One Windows run; startup overhead is not a production percentile |
| Isolated V3 Wikidata first / cached different name | **520 ms / 9.68 ms** | Same exact source QIDs/language and no second network request; different name correctly re-evaluated |
| Isolated V3 OSV first / cached same package | **635 ms / 10.39 ms** | Exact-repeat local cache avoids provider request; one-shot direct OSV original request itself took **526 ms**, so no first-use speedup is claimed |
| V2 3-source discovery, fresh / exact cached | **about 6.6 s / about 3.5 s** via Codexify bridge; all three source `cache_hit=true` on repeat | Connector roundtrip includes bridge/runtime overhead and variable public network latency; two observations are not an SLA |
| World Bank direct official request | **708 ms** for four data points | Direct client-only provider stopwatch; different transport from Codexify tool timing, cannot claim relative speedup |
| V2 discovery response size | Full observed JSON **14,169 characters** for 15 sampled records / 1 candidate. The **implemented** brief retaining the additional TED sampling audit and explicit detail-omission notice is **4,956 characters**, **65.0% smaller**. An earlier less-auditable prototype reached 3,975 characters / 71.9%, but was **not** chosen. | JSON characters are a payload proxy, **not measured token billing** or a guaranteed latency saving |
| Separate V2 stdio MCP cold startup / plan-only calls | **3,856 ms** startup; normal plan **36 ms** and opt-in compact plan **9 ms** on one run; invalid enrichment rejected in **130 ms** with no cache created | Confirms the real 17-tool V2 server and backwards-compatible plan-only semantics, **not** a statistically reliable per-call speedup |

The measured V3 cache replay is meaningfully faster on the same machine; the three-source discovery does eliminate the need to manually assemble three different schema projections. However **total human time saved, answer quality against blinded reviewers, revenue uplift, token-cost savings, long-run reliability, and cross-account reproducibility were not established**.

### Focused efficiency repair (opt-in V2 response view)

The existing `intelligence_discover_current` default full report is preserved. An opt-in `compact=True` parameter in the separate V2 MCP returns a smaller baseline decision brief containing exact candidate evidence, source coverage, official TED sampling audit, buyer/market-growth caveats, request count and source-health flags. It omits long notice, research and noncandidate samples; `compact=False` is needed for full details and may require another provider request if the shared cache expires. Nonbaseline enrichment flags are rejected in compact mode rather than silently hidden. The baseline plan-only path stays network-free.

Focused FastMCP + discovery regression tests: **106 passed**; the complete local default repository suite on the modified exact source tree: **3,206 passed, 14 integration tests excluded by default, 3 existing nonfatal warnings**. Full Ruff clean. Offline wheel/sdist build guard PASS with **75 V1/V2 public Python modules**, V3 excluded and security floors retained. Separately launched real stdio/guarded HTTP integration cases: **3/3 passed**. A fourth one-off actual standalone V2 stdio smoke listed all **17 V2 tools** and confirmed default/compact plan-only parity, zero provider calls, zero cache initialization and rejection of a compact-plus-enrichment invalid combination. This is a narrow optional response-size convenience, not new evidence or a relaxation of the provider limits. It remains **source-only** until an authorized release/hot reload; the existing connected v0.3.1 tool catalog was not modified.

### Known gaps and interpretation

1. **Strongest practical workflows today:** date/source-qualified news lead discovery, official-software lifecycle triage, public package/scorecard review, SI RSS topic context and versioned advisory ID lookups in supervised isolated V3.
2. **Weakest decision workflow:** finding a *paying customer* from small, biased public feeds. Correct `insufficient`/no-buyer results are safer than invented claims, but not a verified lead pipeline.
3. **Interface gaps, not proven bugs:** site news queries lack a combined publisher+security-topic filter; a default discovery report can be verbose; a few tool calls take multiple seconds through the Codexify bridge even when sources are cached. Do not attribute all bridge latency to TrendPulse core without a controlled trace.
4. **Google Trends warning is already policy:** unofficial Trends endpoints are often restricted. RSS success does not make limited 24-hour ranking/Explore a defect; no extra Google probes or bypasses were used in this pass.
5. **V3 release gates remain:** independent outside-human workflow review, source-specific rights/attribution assessment, scored official MCP conformance, and explicit owner rollout approval; a technically successful two-tool subprocess is not public readiness.
