# Concept-validation QA — 2026-11-23

Branch: feat/trendpulse-concept-validation-20261123
Base: origin/main at b383208
Isolation: separate Git worktree; no active TrendPulse service or worker touched.

## Verified execution

- 23 focused concept tests passed after HF metadata field selection.
- 125 cross-family regression tests passed, 1 skipped, 1 deselected (source/evidence/hunter/MCP + optional MJAU V3 registry).
- Independent actual MCP stdio child: 12/12 checks passed with the SDK client. Verified 18 read-only optional intelligence tools, new concept tool, plan-only GitHub/HN/SO/HF coverage, no network in preview, header redaction and other legacy intelligence contracts. Paid requests: 0.
- Ruff targeted changed source, tests, CLI, and stdio script clean.
- GitHub live hybrid requested/returned hybrid mode, with existing local GITHUB_TOKEN (no new key).
- HN source live returned actual recent matching records on the focused "prompt injection" search.
- Stack Exchange source was contacted and returned no_data. It was not silently omitted.
- Live Hugging Face metadata returned rights/freshness for public NotInject and gated BrowseSafe++; the latter required a fixed-field query to respect the established 256 KiB cap.

## Source-backed retrieval comparison (one concept; NOT a calibrated uplift study)

Frozen concept: "browser agent prompt injection" (as observed 2026-11-23).
Old default hunter with GitHub Issues only:
- 5 sampled GitHub issues; 0 exact topical title matches.
- Status: insufficient_topical_observation.

New optional concept validator:
- 5 live public GitHub issue records, provider-reported search_type=hybrid.
- 5 public GitHub repository alternatives (candidate competitors, not equivalent features).
- 5 HN discussion records with shortened focused query "prompt injection".
- Stack Overflow was queried with an inferred JavaScript tag; result: no_data.
- 12 capped source-linked records returned in BM25-ranked display.
- No verified paying buyers, market-size estimate, distinct user-problem census or randomized human productivity comparison.
- Retrieval recall is broader; the quality of the final business decision has not been independently proven.

## Deliberate limits

- Existing generic current-activity hunter defaults unchanged so no worker workflow suddenly adds community API calls.
- New software/hackathon concept-specific tool always considers HN and Stack Overflow on every invocation; 5/day and 3/day source budgets/cooldowns preserved, with explicit status for provider failures.
- GitHub hybrid is actual semantic-plus-keyword search only when source response attests "hybrid"; otherwise output must show effective fallback or unverified.
- No Devpost site scraping/API impersonation. Optional user-supplied Devpost project links are clearly unverified comparators; GitHub repositories are only manual feature-review candidates.
- No FastEmbed model installation: hosted GitHub hybrid + local SQLite FTS5 already remove the most material keyword-recall limitation; extra CPU/model cost has no measured incremental benefit yet.
- Dataset licensing and access audited separately in docs/concept-dataset-readiness-20261123.md. No gated dataset rows downloaded.
- Neither production community MCP nor running unified 35-tool God v5 source was reloaded. The proposed branch would make a separate 18-tool intelligence MCP and 36-tool optional unified evaluation MCP, subject to independent release gate. No merge or deploy claim.

## Future decision gates

1. Independently grade exact same 4-8 ideation questions for source relevance and decision impact versus the original hunter, with frozen queries and denominators.
2. Use an isolated reviewed draft PR and complete GitHub CI before considering a transactional single-source hot reload. Keep V3 existing release gates unchanged.
3. Seek explicit user approval and accept Hugging Face terms before consuming BrowseSafe++ gated training content; test split is evaluation-only.
