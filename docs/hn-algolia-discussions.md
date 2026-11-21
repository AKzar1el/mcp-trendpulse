# MJAU M07 — recent Hacker News stories and comments via Algolia

This is **public developer-community activity**, not search volume, measured customer demand, independently corroborated user problems, or a census of Hacker News. The source is HN Search powered by Algolia; it is a public community-search index, not the official Hacker News Firebase item endpoint. No account, API key, verified website, paid tier or browser scraping is required.

Source documentation: [HN Algolia Search API](https://hn.algolia.com/api). It documents `search_by_date` (most recent first), `tags=story|comment|show_hn|ask_hn`, filters on `created_at_i` (Unix seconds UTC), `hitsPerPage` and `page`. These are indexed *matches*, not a relevance judgment by a human. Query phrases can match title, story text or other indexed attributes; an unexpected article title is not necessarily a provider error. The dataset may index/deindex items over time.

## Usage

Preview only (no SQLite or network):

```powershell
uv run --locked mcp-trendpulse-cli intelligence hn-discussions --query "AI agents" --tag story --days 14 --limit 10 --format json
```

Explicit read-only source access, one **first-page** request at most:

```powershell
uv run --locked mcp-trendpulse-cli intelligence hn-discussions --query "AI agents" --tag story --days 14 --limit 10 --execute --format json
uv run --locked mcp-trendpulse-cli intelligence hn-discussions --query "AI agents" --tag comment --days 14 --limit 10 --execute --format json
uv run --locked mcp-trendpulse-cli intelligence hn-discussions --query "AI agents" --tag show_hn --days 14 --limit 8 --execute --format json
```

Allowed `--tag` values are `story`, `comment`, `show_hn`, `ask_hn`. Comments are **separate HN objects** and have a parent `story_id`; ten comments in eight threads are not ten stories or eight independent customer problems. `show_hn` and `ask_hn` identify subsets of stories, not independent add-on counts. Each record uses an exact numeric HN `objectID` to deduplicate, and only source-generated canonical `https://news.ycombinator.com/item?id=...` links are emitted. Arbitrary external linked URLs, user identities, comment content and raw highlights are **not** persisted or exposed.

The request validates an explicitly supplied printable phrase (3–90 characters), accepts 1–30 previous days, always requests **page 0 only**, with **1–20** results. Its UTC snapshot is anchored to the preceding two-hour boundary; the request's exact closed-open window appears in output. A repeated identical invocation within the anchored window can hit the two-hour validated cache without network. This is a limited recent sample, not a crawl, a complete result set or a timestamped social-media trend index.

## Counting and provenance

- `source_rows_received`: actual first-page rows delivered; `source_rows_rejected`: malformed, wrong-scope or repeated IDs, kept separate from accepted rows.
- `source_total_matches_reported`: Algolia's index-reported total for the filter; it is **not** a verified census of unique conversations, developers or paying customers.
- `matching_hits_not_fetched_reported`: provider-reported matches outside the returned first page. All such responses are **observed_partial**. If no hits returned and the provider reports none, status is `no_data` (no indexed matches in this filter), not zero user interest.
- For `story`, `show_hn`, `ask_hn`: unique stable story IDs and distinct UTC publication days are counted **within the returned page only**. Typed `hacker_news_story_mentions` daily `TrendSignal` records use `coverage_status=partial` and `public_api` provenance; this is not a full-day population count.
- For `comment`: count distinct matching comment IDs and distinct parent story IDs **within the returned page**. No `hacker_news_story_mentions` signals are emitted for comments; otherwise discussion density would be silently inflated.
- HN `points` and `num_comments` are nonnegative, provider-reported engagement metadata, **not** counts of search demand or converted users. If missing, they remain `null`, not zero.
- User-submitted query phrases are labeled `manual_research_phrase`, not silently transformed into source-observed search terms. No sentiment classification, problem validation, competitor analysis, sales forecast or geographic inference is made.

## Transport and access safeguards

Only `GET https://hn.algolia.com/api/v1/search_by_date` is permitted with fixed URL, `tags`, a strict UTC `created_at_i>=START,created_at_i<END` filter, `page=0` and `hitsPerPage<=20`. Maximum 160 KiB response, 5s connect/12s read timeout, identifying User-Agent, **no redirects, proxies, retries, paid services, credentials, browser automation or pagination loops**. Requests are limited to **five** HN Algolia operations per UTC day, reserved in the original shared `BudgetCache` SQLite store under `hacker_news_algolia`; 429/503 activate a durable cooldown. Well-formed reports are cached for two hours using the exact phrase/tag/limit/window hash, with strict record reconstruction to exclude arbitrary cached JSON fields or poisoned results. Local quota/cache errors fail closed and do not trigger a network fetch.

## Real source verification — 2026-11-20 UTC

With user-relevant but *manual* phrase **AI agents**, a 14-day lookback and eight/ten-row first-page caps:

| HN scope | Returned page | Provider-reported matches | Distinct sampled threads | Source status |
| --- | ---: | ---: | ---: | --- |
| Stories | 10 | 550 | 10 | observed_partial |
| Comments | 10 | 1,329 | 8 | observed_partial |
| Show HN launches | 8 | 210 | 8 | observed_partial |

All returned items in these three sampled first pages happened to fall on **2026-11-20 UTC**. That does **not** establish a one-day growth trend or mean the other indexed matches were on that date. An earlier, narrower query `model context protocol` for stories and the same two-week window returned valid **no_data**; no broader market inference followed from that absence.

The source-backed story records included item ID **50582844**, “Show HN: XSquads– Set a mission, agents work on it autonomously in your harness”, and item ID **50580804**, “Concepts to Know for Coding with AI Agents.” The comment source returned ten unique comment IDs over eight parent threads, with **zero** story signals, even though its provider-reported total was larger. Story and comment exact repeat requests were validated cache hits: `requests_attempted=0`, `network_performed=false`. The original daily HN budget used **four of five** operations for those three observed calls plus the narrow no-data probe, SQLite integrity was `ok`, and the separate M04 Google Trends quota was not touched.

M07 does **not** mean these mentions represent novel ideas, product opportunity, market demand, customer pain, or popularity outside the sampled HN index. A later cross-source corroboration phase may use these labeled evidence records as inputs but must not assume independent customers. **M04 remains explicitly deferred and unchecked** at the user's request; M08+ untouched. All changes remain on existing draft PR #328.
