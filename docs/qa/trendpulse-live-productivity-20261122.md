# TrendPulse live MCP QA and productivity evaluation - 2026-11-22

**Evaluated:** The actually connected Codexify private MCP source `mcp_trendpulse`, reporting implementation `trendpulse-standard-plus-intelligence-v2` version `3.4.11`, 33 tools, connection healthy. This is a live product evaluation, not merely a code review, independent human study, or benchmark across other MCP providers.

**Source branch:** `qa/trendpulse-live-productivity-20261122` based on merged `origin/main` commit `8e2229158bfe5fff8ad2bd915154bf3167d54946`. Changes and tests are isolated and **not yet installed into the connected MCP**. The separate opt-in MJAU v3 tools are not registered or deployed by this review. No paid services, credentials, model downloads, or private package inventories were used.

## Preregistered practical pass/fail interpretation

For each case, test **real task completion** (a source-backed, useful answer rather than only valid JSON), source/link provenance, bounded fetches, explicit unknowns, false-confirmation guardrails, repeat/caching behavior, and end-to-end tool latency. This is an assistant-created exploratory battery with a small selected sample, not a blinded independent user evaluation. The `mcp_search_tools` discovery test measures local BM25 retrieval only, not an LLM's actual tool-selection success.

## Actual live tool outcomes

| User workflow and input | Observed output | Utility/effectiveness verdict |
| --- | --- | --- |
| Google News: "artificial intelligence", last 3 days, headlines-only, 5 | Five dated publisher/title/Google News RSS links; no fetched publisher prose | **Works** for rapid headline monitoring, but some Google-ranked matches are weakly topical; relevance is not guaranteed |
| Google Trends: top five queries for `SI` | Five current provider terms and provider-attached news metadata | **Works with geography caveat**: a Croatia and Hawaii weather story was attached to a Slovenia-feed weather query; the attached news is not verified to be geographically Slovenian |
| Google Trends: ChatGPT vs Claude AI, United States, last 3 months | 184 normalized date/keyword interest observations | **Works** for time-series comparisons, not exact search volumes |
| deps.dev: npm React `18.2.0` | Verified root, `loose-envify@1.4.0` as direct dependency; 2 resolved dependency versions; repeat was cache hit/no network | **Works** for version-specific dependency investigation, not install counts |
| endoflife.date: Python `3.12` | `unavailable`, `storage_or_network_unavailable`, one source attempt | **Blocked by real TLS issue**: independent HTTPS requests from the same Windows host fail `SSLError` with and without proxy environment. Do not bypass TLS. No support date was fabricated |
| OpenSSF: `astral-sh/ruff` | `not_covered`, no published Scorecard | **Correct abstention**; not equivalent to an insecure project |
| OpenSSF: `ossf/scorecard` | 8.8/10, 18 checks, scan timestamp 2026-11-21, source links, no audit guarantee | **Works** for bounded published-score inspection |
| Hugging Face models: `text embedding`, limit 5 | Live installed MCP: provider returned 5 rows, rejected all 5, `invalid_source_shape` | **Reproduced real defect**, detailed below |
| Seedless trend/opportunity discovery, 14-day, limit 5 | Three public providers (OpenAlex/CFPB/EU TED) all responded; 15 recent observations; **1 single-source weak candidate**, no confirmed buyer, growth or commercial demand | **Useful context** but not a validated customer/opportunity shortlist |
| Targeted hunt: `MCP server reliability`, public GitHub issues + OpenAlex | One relevant issue, `anthropics/claude-cookbooks#974` dated 2026-11-18; no cross-source buyer corroboration | **Useful research lead** with explicitly incomplete demand verification |
| GitHub retained-star cohorts: `vercel/next.js`, limit 8 | 8 weekly cohorts, `insufficient_eligible_history`, no artificial percent estimate | **Correct abstention** |
| Same repository, limit 12 | 12 cohorts, recent eligible 4wk 722 vs prior 4wk 1073 = -32.71% descriptive comparison | **Works** as a retained-star cohort comparison; **not** historic absolute growth, users, traffic, or revenue |

No external-source output was treated as authoritatively establishing commercial value, security guarantees, or identity confirmation.

## Real bug: overstrict Hugging Face multi-term model search

**Initial installed behavior:** Query `kind=models,search="text embedding",limit=5,execute=True` returned `received_rows=5`, `rejected_rows=5`, `status=invalid_source_shape`. Independent official `GET https://huggingface.co/api/models` with the same bounded query returned HTTP 200 and five real public model metadata rows. Examples: `jinaai/jina-embeddings-v5-text-nano`, `litert-community/embeddinggemma-2-text-270m-litert-lm`, and `DiffSynth-Studio/MiniMax-H3-Text-Embeddings`. These names contain the two query tokens in different positions, but the local parser erroneously required the literal phrase `text embedding` to appear contiguously.

**Before correction:** Two new regression tests **failed red**. **Minimal isolated correction:** split safe search phrase into casefolded whitespace-delimited tokens; require **all tokens** in the public repository ID regardless of adjacency or order. Preserve strict ID syntax, requested model-ID equality, `private=False`, gating rules, metric bounds, duplicate checks, no text body copying, no buyer/model-quality assertions, and no caches of partially rejected pages.

**After correction:** New + preexisting Hugging Face suite **64 passed**. The patched isolated adapter actually queried the public Hugging Face API: `status=observed_partial`, `received_rows=5`, `rejected_rows=0`, **5 valid model IDs available**. Repeated identical call was `cache_hit=True, network_performed=False`. First call including local adapter execution was approximately 6.4 seconds. Source bodies, weights, credentials and private records were not downloaded or committed.

**Changed files:** `src/mcp_trendpulse/mjau_v2/hf_catalog.py`; `tests/test_mjau_v2_hf_live_search_regression.py`.

## Agent-tool discoverability check

Twelve distinct natural-language user questions were passed to Codexify's private `mcp_search_tools` with a frozen expected correct TrendPulse tool. **8/12 expected tools ranked first, 10/12 in top three.** The two misses beyond rank three were a request for Python 3.12 end-of-life and an AI regulation headline search. Several Google Trends queries ranked another geographic/trend tool above the historical/now-specific tool.

This is a concrete **retrieval-description quality gap**, not evidence that an actual LLM called the wrong tool 4/12 times. Future improvement: tune tool descriptions around natural phrases and run a separate paired coding/research-agent test with equivalent models and budgets.

## Resilience and source correctness checks

- Outbound-free `execute=False` plans for lifecycle, HF models, seedless discovery, and two-topic hunt returned bounded request descriptions and no network.
- Negative inputs were rejected before network: HF limit 99, npm package-version path traversal, blank news keyword. The blank headline validation error was surfaced as `UNAVAILABLE` by the connector wrapper rather than an invalid-request category; it remains a minor diagnostic consistency gap, not an executed unsafe query.
- Real source lookup and cached repeated `react@18.2.0` showed the same root and no repeat network; the patched HF catalog showed the same cache behavior in a separate temporary store.
- Endoflife.date certificate validation failed independently. The current generic `storage_or_network_unavailable` reason is safe but insufficiently actionable; **do not disable certificate verification** to make this test green.
- Google Trends results and unrelated upstream news links should not be treated as geographic news verification or objective search demand without source-provenance checks.

## Test receipts and release boundary

- **All regular repository tests:** 3,079 passed, 13 process-level integration tests deselected, 3 nonfatal warnings in 421.18s. Warnings: two upstream Starlette/AnyIO deprecations and one tempfile cleanup warning in a test.
- **Focused Hugging Face parser:** 64 passed after the verified red tests.
- **Static checks:** Ruff, Python compileall and `git diff --check` passed.
- **Real MCP and live provider:** 33-tool Codexify source connected; actual Google News, Google Trends, deps.dev, OpenSSF, OpenAlex, CFPB, TED, GitHub issues and GitHub star-history calls executed. Patched Hugging Face official direct call succeeded; installed live HF tool remains unpatched until code is separately reviewed and deployed.
- **Real isolated MCP stdio/HTTP process integrations:** **3/3 passed** in 125.39s; nine unrelated test cases deselected during that specific invocation.
- **Historical external Google News/Trends/article integrations before test repairs:** **3 passed, 7 failed** in 154.36s; *not* a product acceptance pass. Two failures were outdated tests (Playwright intentionally disabled pending pinned browser egress; unsupported news topic `CATS` should raise a validation error). The remaining five failures were upstream Google Trends RSS/HTTP 429/rate-limit errors handled as retryable provider errors rather than fabricated trend data. Some were subsequently blocked by intentional provider cooldown. No Google rate-limit bypass attempted.
- **External integration test hardening:** corrected both obsolete expectations without enabling unsafe browsing. A test-only provider availability fixture skips only known retryable `google_trends` timeout/rate-limit/unavailable receipts, with the skip reason clearly stating that source availability was **not verified**. Validation mistakes, unexpected tool errors and nonretryable responses are still failures. The five provider-dependent scenarios were not rerun against Google during active cooldown; these should **not** be counted as passed. Four offline negative classifier/skip-behavior tests passed.
- **Remaining validation:** rerun provider-dependent smoke cases only after provider availability normalizes and free quota allows, separately reporting **pass/fail/skip**. GitHub exact-head CI and container checks must pass on the updated PR commit, not only on the original HF patch commit.

This is **not a production restart, live tool update or deployment authorization**. Existing mainline V1/V2/V3, worker schedules and other Codexify agents stay untouched. Publish any code change as a reviewable branch/PR and require exact-head CI before merge. The optional V3 source rights and independent external human release review remain unchanged.
