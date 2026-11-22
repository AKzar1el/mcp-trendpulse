# TrendPulse V2 - frozen tool discoverability benchmark (2026-11-22)

## Evaluation scope and limitations

These **24 questions and expected tool names were frozen before updating the descriptions**. Twelve reproduce the earlier 33-tool connected Codexify search checks, and twelve are independent phrasings (holdouts). The actual connected Codexify source ranked the intended tool **first for 8/12 and in the top 3 for 10/12** in the original suite. The initial transparent offline BM25 proxy happened to reproduce those aggregate totals; **it is NOT Codexify's ranking implementation**. The numbers after editing are **offline projections only** until the operator refreshes the updated tool manifest and repeats actual connected searches. This is not an LLM-agent completion-rate evaluation or a randomized/blinded benchmark.

## Results

| Frozen scope | Questions | Before top-1 | After top-1 | Before top-3 | After top-3 |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 12 | 8 | **9** | 10 | **12** |
| holdout | 12 | 5 | **12** | 8 | **12** |
| all | 24 | 13 | **21** | 18 | **24** |

## Frozen tasks and rank comparison

Smaller ranks are better. 1 means the expected tool was the first result of the offline BM25 description-only proxy.

| Group | Natural-language user task | Intended tool | Before rank | After rank |
| --- | --- | --- | ---: | ---: |
| baseline | Compare Google Trends interest over time for ChatGPT and Claude | get_trends | 2 | **2** |
| baseline | Find Google News headlines from the last three days about AI regulation | get_news_by_keyword | 5 | **2** |
| baseline | Show what's trending now in Slovenia | get_trending_terms | 3 | **3** |
| baseline | Find when Python 3.12 reaches end of life | intelligence_release_lifecycle | 30 | **1** |
| baseline | Inspect npm React 18.2.0 dependency graph | intelligence_dependency_graph | 1 | **1** |
| baseline | Find trending Hugging Face embedding models | intelligence_hf_catalog | 1 | **1** |
| baseline | Find published OpenSSF Scorecard for ossf/scorecard | intelligence_repository_scorecard | 1 | **1** |
| baseline | Look at GitHub star history for vercel next.js | intelligence_repository_star_history | 1 | **1** |
| baseline | Discover current themes across research, complaints and EU tenders without topics | intelligence_discover_current | 1 | **1** |
| baseline | Hunt current MCP server reliability issues across public research sources | intelligence_hunt_current | 1 | **1** |
| baseline | Evaluate opportunities with dated public buyer evidence | intelligence_evaluate_opportunities | 1 | **1** |
| baseline | List free market intelligence sources and coverage | intelligence_source_catalog | 1 | **1** |
| holdout | Is Python 3.12 still supported or past EOL? | intelligence_release_lifecycle | 2 | **1** |
| holdout | When does Node.js 20 reach end of support? | intelligence_release_lifecycle | 2 | **1** |
| holdout | Check if an old Node.js version is end of life | intelligence_release_lifecycle | 17 | **1** |
| holdout | Read today's breaking AI regulation headlines from Google News without fetching article bodies | get_news_by_keyword | 8 | **1** |
| holdout | Search headlines only for EU artificial intelligence law from the past week | get_news_by_keyword | 29 | **1** |
| holdout | Find Google News story headlines mentioning climate tech across publishers | get_news_by_keyword | 3 | **1** |
| holdout | Which countries search for Python the most? | get_interest_by_region | 17 | **1** |
| holdout | Get the latest Google News TECHNOLOGY category feed | get_news_by_topic | 1 | **1** |
| holdout | List market intelligence sources and free API coverage | intelligence_source_catalog | 1 | **1** |
| holdout | Compare the npm lodash package dependency tree for a specific version | intelligence_dependency_graph | 1 | **1** |
| holdout | Check the published OpenSSF security Scorecard for a GitHub repository | intelligence_repository_scorecard | 1 | **1** |
| holdout | Show terms trending right now in the US | get_trending_terms | 1 | **1** |

## Change and safety boundary

- get_news_by_keyword: advertises free-form Google News subject/headline lookup and headlines_only=True (RSS metadata only, no article fetch).
- intelligence_release_lifecycle: advertises lifecycle/end-of-life support for versioned software such as Python 3.12 and Node.js 20, while keeping vendor-certification and commercial-entitlement caveats.
- get_interest_by_region: clarifies country/region/city relative search interest and removes a misleading inference of verified customer demand.
- No tool added, removed, renamed or made non-read-only. No changes to inputs, network execution, quotas, security checks, production registration or optional MJAU v3 release gates.
- Source-backed provider smoke suite still distinguishes pass, fail and skip; Google 429 errors are not retried or converted to green. Unrelated errors cannot spoof retryable outages by embedding JSON in arbitrary error text.
- Reproduce offline with PYTHONPATH=src python tests/qa_trendpulse_discovery_benchmark.py. It uses local MCP list_tools() and no external provider requests. tests/test_tool_discovery_quality_qa.py enforces metadata and ranking quality.

## Interpretation

This metadata change improves the frozen **offline lexical routing proxy** on all 24 questions, with no previous first-choice hit lost. Real Codexify improvements must be verified after an explicit authorized connector refresh. Further tuning needs additional unseen tasks and direct agent tool-use comparisons, not only this static lexical set.
