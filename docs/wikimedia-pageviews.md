# MJAU M06 — Wikimedia daily article pageviews

Wikimedia Analytics API is a **free, official source of Wikipedia article attention**. This optional adapter does not measure Google/Bing keyword search volume, unique readers, visitors by country, potential buyers or commercial demand. The initial M06 scope deliberately supports language-specific `*.wikipedia.org` projects; other Wikimedia projects and automatically discovered article candidates are not silently assumed to work.

The official Analytics API has open access and CC0 1.0 data licensing. It requires an identifying User-Agent with contact information and asks clients to limit traffic and respect 429 responses. TrendPulse identifies itself using its public repository URL, does not send tokens, and issues requests sequentially. Wikimedia also cautions that **HTTP 404 can mean zero pageviews or data not yet loaded**, and date gaps can reflect unavailable counts; neither is silently converted to measured zero.

Sources: [Wikimedia Analytics API access policy](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/access-policy.html), [page metrics examples](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/examples/page-metrics.html), [troubleshooting and missing values](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/troubleshooting.html), and [pageview definition](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/concepts/page-views.html).

## One exact article, two comparable windows

By default the command is **offline planning only**; it does not access the network or open the local SQLite quota store:

```powershell
uv run --locked mcp-trendpulse-cli intelligence wikimedia-pageviews --article "Python (programming language)" --project en.wikipedia.org --days 7 --end-date 2026-11-17 --format json
```

To explicitly fetch the selected article (or use a previously verified cache hit):

```powershell
uv run --locked mcp-trendpulse-cli intelligence wikimedia-pageviews --article "Python (programming language)" --project en.wikipedia.org --days 7 --end-date 2026-11-17 --execute --format json
```

The `--article` argument is an **exact wiki page title**, not a URL, search phrase, pageview redirect, disambiguation label, article search, or unverified topic-to-page mapping. A site does not need to be owned by the user. Specify the language/project explicitly: `en.wikipedia.org` and `sl.wikipedia.org` are distinct data sources. The wiki language is **not** the geographic location of readers. The CLI does not infer readers' countries from the language or site project.

An executed call first performs a read-only MediaWiki Action API `action=query&prop=pageprops&redirects=1` check. Missing pages, disambiguation pages, namespace mismatches, redirects and differing canonical titles are **refused** rather than automatically followed. Supply an existing, canonical, non-ambiguous article title if a title is refused. The validation verifies the page's canonical title and simple disambiguation property; it is not a guarantee that the source article is semantically the exact topic the researcher intended.

When verified, one official Wikimedia Analytics API request obtains **daily user-agent / all-access pageview counts** for the complete union of two adjacent, equal-length periods (a total of 2–60 days, with 1–30 days per period):

```text
https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia.org/all-access/user/Python_%28programming_language%29/daily/20261104/20261117
```

The default end date is at least **two completed UTC days in the past** to reduce not-yet-loaded data. Every requested day and source timestamp is validated; samples are independently represented as `TrendSignal` records with original project, language, exact title, date, access/agent category and provenance.

The comparison emits a sum and percentage change **only when both periods contain all their daily observations** and the previous window total is greater than zero. If any days are missing, totals for the affected window are `null` and percentage change is not reported. A legitimate explicit zero-view observation, when returned by the provider, stays zero. The API's missing dates and 404 responses **must not** be interpreted as measured zero.

## Network, budgets and failure behavior

- Strictly explicit `--execute`; never fetches data during CLI help or preview.
- A maximum of **two** sequential outbound operations per uncached call: one read-only canonical-title verification and one read-only pageview data request. **Both are reserved atomically** before contacting any provider, using TrendPulse's original durable `BudgetCache` SQLite store and a dedicated `wikimedia_pageviews` source cap of **four reserved operations per UTC day**. A failed first request does not release its conservative two-reservation batch, preventing quota reuse.
- Valid observed, partial or no-data reports are cached for **six hours**. An identical cached query consumes **zero** provider operations. The cache reconstructs only validated records, never arbitrary SQLite JSON or unknown metadata fields.
- API requests use a fixed HTTPS host and a language-Wikipedia-host allowlist, descriptive contact User-Agent, 5-second connect and 12-second read timeouts, <=96 KiB response body, no proxies, redirects, retries, browser scraping, paid accounts, API keys, scheduled jobs or new dependencies.
- HTTP 429/503 opens a local short cooldown; a malformed/non-JSON source, schema mismatch, redirect or disambiguation is a distinct error state. HTTP 404 from the Pageviews API returns `zero_or_not_loaded_unknown`, not fabricated zero or an invented pageview trend.
- The project title and language are source-level metadata; do not interpret them as verified country-level interest. All views are page requests, not distinct individuals. Redirects are not aggregated to a canonical page, and potential bot detection changes can affect longitudinal comparisons.

## Verified bounded live observation — 2026-11-20 UTC

The source article **Python (programming language)** on `en.wikipedia.org` was verified canonical via the read-only Action API. The Analytics API then returned 14 days of measured, daily *all-access/user* pageviews (no rejected or missing days).

| Inclusive window | Days observed | Article views |
| --- | ---: | ---: |
| 2026-11-04 through 2026-11-10 | 7/7 | 26,965 |
| 2026-11-11 through 2026-11-17 | 7/7 | 25,846 |

The change between the two equal-length source periods was **−4.15%** (a difference of −1,119 article views), not proof of declining general demand, search intent, spending, customers or a cross-language search trend. The first recorded day, 2026-11-04, had 4,132 views. All 14 source points were mapped to provenance-attributed, daily `wikimedia_pageviews` signals. A second identical CLI call returned `cache_hit=true`, `requests_attempted=0` and `network_performed=false`. The original daily local Wikimedia source quota was **2/4** after live acceptance; the original M04 Google Trends and M05 Bing quotas were unchanged, and SQLite `quick_check=ok`.

Only M06 was implemented and accepted. M04 is **still unchecked** pending the user's separate reminder. M07+ remain untouched; the PR remains draft and unmerged.
