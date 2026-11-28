# Free concept validation for software and hackathon research

This is a separate, optional tool. It does NOT change the original 16 community
tools, the hosted service, workers, or the generic current-activity hunter.

## Why Hacker News and Stack Exchange were missing

The original intelligence_hunt_current default included GitHub lexical issues,
OpenAlex, CORDIS and USAspending. Its 5-record first-page samples required
near-exact title matches. Hacker News and Stack Exchange were already separate,
quota-limited CLI adapters; the generic hunter never connected them.

The new intelligence_validate_concept MCP tool and intelligence concept-validate
CLI include all four evidence classes by default:
- GitHub hybrid issues (semantic + lexical search) using official REST,
  with existing GITHUB_TOKEN or GH_TOKEN environment auth if available;
  the response must report effective search_type=hybrid before this is
  described as a true hybrid observation. No new key is purchased.
  Both GitHub searches use public-only scope. Authenticated results without
  explicit public repository visibility are rejected before cache/projection.
  Missing visibility is an unavailable observation, not zero demand. Prior
  search cache keys are isolated from this stricter policy.
- GitHub public repositories by name/description as possible alternatives.
- Hacker News via the existing keyless Algolia adapter.
- Stack Overflow via the existing keyless Stack Exchange v2.3 adapter.

HN and Stack Overflow are ALWAYS CONSIDERED. Their no_data, cooldown and local
quota failures stay explicit. This does NOT authorize exceeding daily limits.
A long concept is shortened to its final two terms for community search only.
The full concept remains unchanged for the GitHub hybrid search. The shorter
phrase is an assistant-derived query, not a source-observed search keyword.

The optional Hugging Face dataset owner/name lookup retrieves license,
gating and modification METADATA only. No dataset rows are downloaded or
rights implied. The optional --devpost-url argument takes a canonical
https://devpost.com/software/slug reference from the user and lists it as
NOT YET VERIFIED. There is no undocumented Devpost scraper.

## Commands

Offline preview, without cache initialization or HTTP calls:

    uv run --locked mcp-trendpulse-cli intelligence concept-validate --concept "browser agent prompt injection"

Read-only, bounded real source requests:

    uv run --locked mcp-trendpulse-cli intelligence concept-validate --concept "browser agent prompt injection" --execute

Optional dataset metadata and manual Devpost comparator:

    uv run --locked mcp-trendpulse-cli intelligence concept-validate --concept "browser agent prompt injection" --dataset "leolee99/NotInject" --devpost-url "https://devpost.com/software/example-slug" --execute

## Relevance and truth limits

Results are bounded to public canonical URLs and limited titles, dates,
description and provider-reported metadata. No raw GitHub issue bodies,
authors, HN comments, Stack Overflow profiles, dataset contents, arbitrary
URLs or credentials are stored in the research output.

A transient in-memory SQLite FTS5/BM25 index ranks title and limited
description overlap. It adds no network or model dependencies, and falls
back to simple lexical overlap if FTS5 is unavailable. A low-rank item
can still be relevant semantically: ranking is NOT accuracy or demand proof.
All competitor entries explicitly require human feature-comparison review.

Source quotas and automatic caching reuse existing GitHub issues 12/day,
HN Algolia 5/day and Stack Exchange 3/day with upstream backoff. New
GitHub repo search is capped locally at 12/day and optional Hugging Face
metadata at 6/day. GitHub upstream hybrid search limit is 10/minute.
No paid services, new credentials, proxy retries, Bluesky or schedules.

## Validation / rollback

Compare the same frozen ideas with the old exact-title/5-record hunter
and the new workflow. Grade topical relevance, independent user pain,
actual repo equivalence, false positives and idea decision changes.
More records alone is not proof of better decisions.

The separate optional MCP tool stays off the original public/community
server and is not automatically deployed or hot-reloaded. The isolated
feature branch can be abandoned without affecting live workers.

Official documentation:
- https://github.blog/changelog/2026-04-02-improved-search-for-github-issues-is-now-generally-available/
- https://docs.github.com/en/rest/search/search
- https://hn.algolia.com/api
- https://api.stackexchange.com/docs/advanced-search
- https://huggingface.co/docs/hub/api
