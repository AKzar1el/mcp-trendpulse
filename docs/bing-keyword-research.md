# MJAU M05 — Bing Webmaster market-wide keyword research

This module uses Bing Webmaster Tools' **official JSON/HTTP REST** keyword
research API for arbitrary keywords, countries and languages. The keyword
research endpoints have **no siteUrl** argument and do not return impressions
of a particular website. A verified Bing Webmaster site/account may be
required to **obtain an API key**, but the keyword methods are not scoped to
that website.

Only these two Microsoft-documented endpoints are allowed:

- `GetKeywordStats(q, country, language)`: historic **weekly** Bing
  keyword-research impressions and broad-match impressions. No request
  date-range parameters exist for this method.
- `GetRelatedKeywords(q, country, language, startDate, endDate)`: related
  keyword phrases with exact- and broad-match Bing impressions **aggregated
  over the requested date window**. The source does not provide individual
  weekly buckets for this operation; TrendPulse does not invent them.

The 2026-08-31 retirement affects **SOAP and POX**, not REST/JSON. Do not
switch to SOAP, POX, scraped Keyword Research UI, GSC, Bing site-performance
endpoints or paid keyword-data providers.

## Usage

Dry-run/preview (never accesses credentials, SQLite or the network):

```powershell
uv run --locked mcp-trendpulse-cli intelligence bing-keywords --term "crochet patterns" --country US --language en-US --kind stats --format json
```

Explicitly opt in to **one** live read-only REST call, or a validated cache hit:

```powershell
uv run --locked mcp-trendpulse-cli intelligence bing-keywords --term "crochet patterns" --country US --language en-US --kind stats --limit 6 --execute --format json
uv run --locked mcp-trendpulse-cli intelligence bing-keywords --term "crochet patterns" --country US --language en-US --kind related --start-date 2026-10-20 --end-date 2026-11-19 --limit 10 --execute --format json
```

Each query is explicitly limited to 20 emitted source rows. For related
keywords, the selected window is at most 90 days; without dates, the last
30 calendar days are requested. Country is an uppercase ISO alpha-2 code
in the CLI (Bing receives lowercase); language is an IETF language tag
such as `en-US` or `sl-SI`. These are two independent dimensions.
Data availability is Bing-dependent; a syntactically valid market is not
a guarantee of provider coverage.

The `BING_WEBMASTER_API_KEY` is supplied through the operator's secure
process environment or through TrendPulse's existing native Windows
Credential Manager settings profile `bing_webmaster`; a key is already
configured on the verified Windows operator profile. No key needs to be
passed through CLI flags, prompts, screenshots or project files.
The credential is never emitted by TrendPulse reports, errors or cache
records. Microsoft's GET protocol does require an `apikey` parameter:
TrendPulse supplies it **only** to the fixed HTTPS Bing endpoint on the
actual request, never follows redirects, never uses a system proxy, and
never serializes the authenticated URL into reports or logs.

## Quotas, cache and errors

- At most **three** Bing keyword-research operations per UTC calendar
  day **in total across both methods**, reserved in the existing durable
  `BudgetCache` under `bing_webmaster_keyword_research`.
- One request per opt-in invocation; request timeout 5-second connect /
  12-second read, maximum 128 KiB decoded JSON, no automatic retries,
  no redirect, no proxy rotation, and no billable alternative.
- Valid `observed`, `observed_partial` and `no_data` responses cache
  for **three hours**, differentiated by method, keyword, country,
  language, date range, row limit and a one-way fingerprint of the
  operator's API key. A cached repeat consumes **zero** calls.
- Unknown or malformed SQLite/cache rows are not returned verbatim;
  only validated, explicitly allowlisted metadata and source-derived
  keyword rows are reconstructed.
- HTTP 401/403 produces `authentication_required`, 429/503 opens an
  additional local cooldown, other failures are safe unavailability
  states with no raw request URL or credential in the error message.
  `no_data` means the upstream provided no keyword records, not zero
  search demand, and `invalid_source_shape` is not a valid empty source.

## Evidence and measurement

`Impressions` and `BroadImpressions` are Bing's keyword-research
exact-match and broad-match impression counts. They are not unique
searchers, click counts, customers, Google search volume, or total volume
across search engines. A zero count *in a returned source record* is
different from an absent record.

For weekly stats, TrendPulse emits separate `TrendSignal` measurements
for exact and broad impressions, preserving the original Bing date (from
Microsoft JSON `/Date(ms±HHMM)/` format), keyword, market, language,
source and match-basis. For related queries, it emits bounded aggregate
records and an explicit requested period without fabricating a weekly
series. Truncation, malformed source rows, duplicates and source coverage
are distinguished from fully observed results.

### Real bounded acceptance on 2026-11-20 UTC

An operator-owned already-configured Bing Webmaster API key was used
without regenerating or revealing it. The test keyword **crochet patterns**
is unrelated to the operator's verified websites. Read-only
`GetKeywordStats` returned HTTP 200 and **24 historical weekly rows**
for US/en-US, with both exact and broad impressions; the TrendPulse
command emitted the last **six** and their **12 sourced weekly signals**.
Selected source records:

| Bing-reported week date | Exact impressions | Broad impressions |
| --- | ---: | ---: |
| 2026-10-31 | 661 | 3,048 |
| 2026-11-07 | 760 | 3,312 |
| 2026-11-14 | 742 | 3,475 |

`GetRelatedKeywords` for the same keyword and US/en-US,
**2026-10-20 through 2026-11-19**, returned HTTP 200 and **100**
source records; TrendPulse emitted the ten highest exact-impression
phrases. Source examples:

| Related keyword | Exact impressions | Broad impressions |
| --- | ---: | ---: |
| crochet | 5,367 | 72,888 |
| free crochet patterns | 1,990 | 4,420 |
| crocheting | 1,232 | 1,894 |

Both responses were marked `observed_partial` because the emitted
row caps omitted other valid source rows, **not** because the 100 Bing
results imply all possible keywords have been covered. A subsequent
cache hit for each exact request returned `requests_attempted=0`
and `network_performed=false`. The persistent Bing budget ended at
**3/3 on 2026-11-20 UTC**, including the initial schema-probe call.
SQLite quick_check=ok. No website property argument, paid plan, new
credential, scheduled job or browser scraping was used.

The live API response shape, data basis and market independence were
verified directly. A separate Bing Webmaster UI side-by-side comparison
was *not* performed; no such check is claimed. M04's separate unofficial
Google Trends Explore live test remains pending its legitimate local
daily cap reset and is unaffected by M05.

Official Microsoft references:

- https://learn.microsoft.com/en-us/bingwebmaster/getting-access
- https://learn.microsoft.com/en-us/bingwebmaster/api-protocols
- https://learn.microsoft.com/en-us/dotnet/api/microsoft.bing.webmaster.api.interfaces.iwebmasterapi.getkeywordstats?view=bing-webmaster-dotnet
- https://learn.microsoft.com/en-us/dotnet/api/microsoft.bing.webmaster.api.interfaces.iwebmasterapi.getrelatedkeywords?view=bing-webmaster-dotnet
- https://learn.microsoft.com/en-us/dotnet/api/microsoft.bing.webmaster.api.interfaces.keywordstats?view=bing-webmaster-dotnet
- https://learn.microsoft.com/en-us/dotnet/api/microsoft.bing.webmaster.api.interfaces.keyword?view=bing-webmaster-dotnet
