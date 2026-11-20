# MJAU M04: Google Trends Explore evidence (no cloud login)

This is an **optional**, quota-limited Google Trends Explore research
operation built on TrendPulse's *existing* paced, unofficial TrendSpy
provider. It is **not** the official Google Trends API, BigQuery, Google
Search Console, an SEO property report, Keyword Planner, or a measurement
of search volume or paying customers. It uses no Google Cloud account.

The command does nothing on the network without explicit `--execute`:

```powershell
uv run --locked mcp-trendpulse-cli intelligence explore-evidence --term "AI agents" --country SI --format json
uv run --locked mcp-trendpulse-cli intelligence explore-evidence --term "AI agents" --country SI --execute --format json
```

A source-backed seed can instead come from a locally saved, **observed**
M01 Trending Now RSS report or an **observed** M03 BigQuery result.
Only one vetted source term is selected; it is not relabeled as an
observed literal Google query (Trending Now labels may group multiple
searches; BigQuery is a curated ranking):

```powershell
uv run --locked mcp-trendpulse-cli intelligence explore-evidence --source-file .\observed-m01-rss.json --execute --timeframe "today 3-m" --format json
```

Source-file input is capped at 128 KiB; accepted M01 reports are at most
seven days old and M03 at most 30 days old. An unsupported, stale, or
inconsistent market/source is refused. Only `today 3-m` and
`today 12-m` windows are accepted. No automatic topic harvesting,
keyword expansion, proxies, or background jobs are added.

## Source and metric meanings

- **Top related queries:** a relative, within-query score (0-100)
  within the specified country, time window and search properties. Not
  global rankings or absolute searches.
- **Rising related queries:** percentage change versus the previous
  comparable period. **Breakout** means greater than 5,000% growth,
  commonly from a low baseline. It is not 5,000 searches, an exact
  percentage, a sales metric, or independently proven demand.
- **Interest time series:** observed 0-100 normalized *single-term*
  Google Trends Explore sample, attributed to exact provider dates,
  country, time window and the community provider. At most 16 original
  points are emitted; `points_truncated` flags omitted historical
  samples. A value of 0 means zero in the normalized result, not
  zero actual searches. Never compare the indices of separate
  requests as if they share a calibrated denominator.
- Search geography is **not** language identification. `language` is
  unknown unless source metadata actually provides it.
- Malformed/missing values, provider failures, cooldown, and quota
  exhaustion are explicitly distinguished from a valid empty result.
  Related-query rows that are rejected, duplicated or excluded by the
  three-per-series output cap produce an explicit **observed_partial**
  status (when other usable rows remain), with source/omission counts.
  A nonempty result where every row is invalid is **not** observed_empty.

References: [Google Trends Find related searches](https://support.google.com/trends/answer/4355000),
[Google Trends FAQ](https://support.google.com/trends/answer/4365533).

## Safety and quota contract

The Explore command shares the exact
`google_trends_idea_related_queries` local `BudgetCache` source ID
and **two provider operations per UTC day** with the existing
`intelligence_keyword_probe` feature, avoiding quota bypasses.
An Explore attempt uses at most one related-query provider operation
and one interest-over-time provider operation, and the persistent cache
holds successful responses for six hours. The existing process-wide
Trends request pacing and 429 cooldown remain active, with an additional
durable local cooldown. **An operation may involve multiple HTTP
requests inside TrendSpy; physical request count is not measured.**
Cached source rows are structurally revalidated, and only whitelisted,
source-labeled evidence metadata is returned; malformed or unexpected
local SQLite JSON must never be emitted verbatim or trigger an unbudgeted
refetch.
The existing related-query wrapper can make one retry on a transient
unavailability; there is no unbounded retry, alternative endpoint, or
proxy rotation. Source failure and quota exhaustion do not trigger
paid fallback or create credentials.

Only a genuinely observed live provider response can satisfy the M04
live acceptance gate. When Google rate limits or the provider fails,
report M04 as live blocked even if all deterministic tests pass.

## M03 is independent and verified

M03's optional official public BigQuery sandbox was verified on
2026-11-20 with a **billing-unattached** Google Cloud project, a
61,072,200-byte dry run under the 100 MiB maximum, and five US
2026-11-18 source-ranked observations. It is **not** a Google Trends
Explore API and does not verify M04. See bigquery-trends.md.
M04's own live source acceptance remains independent of the M03 result.
