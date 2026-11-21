# MJAU M14 — Final source-attributed cross-source research report

M14 is the **final bounded, offline, source-attributed research surface**.
It synthesizes previously collected, fully typed M00 `TrendSignal` records,
without contacting providers, refreshing caches, using privileged site
properties, changing SQLite budgets or calculating fabricated cross-source
market-demand scores.

It provides both a human-readable and JSON CLI report, plus one read-only
hosted MCP prompt. Source adapters (M01–M11), conservative lexical clustering
(M02/M12) and source-scoped historical classification (M13) remain
**independent and separately reviewable**. M14 consumes their shared M00
signal contract and existing M02 clustering function; it does not silently
merge the outstanding milestone draft PRs or invoke any unmerged source
module at runtime.

The report is a structured way to **inspect evidence and its limits**, not an
automated founder, SEO opportunity ranking, forecast, conversion predictor,
search-query log, demand estimator, customer count or sales strategy.

## Run with genuine previously verified source evidence

The example contains 42 fully validated typed signals from **seven** public
source families, reconstructed from their previously verified local SQLite
cache entries in **read-only** mode (`file:...?...mode=ro`). The export did
not make any provider calls or reserve new quotas.

    uv run --locked mcp-trendpulse-cli intelligence research-report --input docs/examples/mjau-m14-real-multisource-signals.json --format text

Full structured report with every source's metrics and first/last periods:

    uv run --locked mcp-trendpulse-cli intelligence research-report --input docs/examples/mjau-m14-real-multisource-signals.json --format json

The example reuses actual verified public data:

| Primary-source family | Source evidence in example | Metric caveat |
| --- | --- | --- |
| Bing Keyword Research `GetKeywordStats` | 6 weekly exact-match source observations of the query-research seed `crochet patterns`, US/en-US | Keyword research is not site search performance and does not prove actual individually observed search queries |
| Google public Trends BigQuery | 5 dated source-rank observations | Rank ≠ search volume or absolute market size |
| Wikimedia Analytics | 14 dated pageview-request observations for the verified canonical article `Python (programming language)` | Pageviews ≠ independent people or demand |
| Hacker News Algolia/public items | 2 source-linked public story observations, each from a bounded, partial search page | Discussion ≠ validated problem or independent users |
| npm registry | 7 dated daily `zod` tarball request observations | Downloads include repeated requests, CI, bots and dependency installation |
| PyPI Stats | 7 dated daily `pydantic` download observations excluding known mirrors | No unique-user attribution; different ecosystem from npm |
| Stack Overflow | 1 public question with canonical source link and ID `80015847` | A question is not proof of unresolved pain, buyer intent or a verified defect |

Every record is validated again against the original typed M00
`TrendSignal` contract, retaining original source URL, period,
observed time, metric unit, source record ID and country/language
scope. No additional source call was made to generate the example,
and no original cache value or budget was modified.

**Actual report result:** 42 records from seven sources, six source/term
search-interest groups, one public-attention group, three
developer-discussion groups, two separate package-adoption groups and
eleven conservative M02 lexical families. There are **zero**
source-attested individually observed search-query candidates, zero
safely verified rising queries and zero inferred product hypotheses.
That is a correct abstention, not a bug: Bing's seed term is provided
to the official keyword research API, HN is a discussion search,
Google BigQuery gives relative rank, and package downloads and
pageviews are not search query logs. The recommended next step is to
validate genuine query-level demand with an authorized, free,
quota-compliant primary source **only when available**. M04 Google
Trends service limits must not be bypassed or aggressively retried.

## Stable input contract

Root JSON is either an array of 1–120 full M00 typed source signals or
`{"signals":[...]}` with no extra keys. Input must be at most **128 KiB**
and is processed in memory with **no provider or local database calls**.

- The full `TrendSignal` Pydantic model is revalidated. Incorrect
  source metric unit, bad date or timezone, observed false-zero,
  numeric source rank/bucket mistakes, non-source candidate
  provenance, malformed country/language and unsupported enums fail
  closed with a generic error.
- Source URL must be public HTTPS without credentials, private/local
  targets, forbidden port or suspicious API tokens. Titles, terms,
  source-record IDs and scope are also screened for obvious credential
  and email patterns. Unexpected root fields fail closed.
- Exact duplicate source records are collapsed deterministically;
  no source metric is summed across providers, countries, language
  scopes or even unrelated original samples. Source-count values
  describe the bounded input only, not whole-platform counts.
- Every source-reference summary remains tied to exact
  source URL/record ID, UTC observed time, source status and unit.
  At most twelve individual references per grouped source summary are
  printed; a truncation flag and total *input source record count*
  remain visible.
- Null country means source market unspecified, **not worldwide**.
  A source's `partial`, `unavailable` or `no_data` status is never
  silently converted to measured zero. Partial values, if the original
  provider supplies them, stay explicitly labeled `partial_source_value`
  and cannot support a rising-query classification.

## Output fields and evidence levels

The JSON report provides the canonical M14 fields:

- `rising_queries`: only **source-attested literal query** observations
  that pass an unusually strict local two-window gate described below.
  An empty list means no qualified rise *in the supplied sample*.
- `observed_query_candidates`: source-attributed terms only when the
  original typed source explicitly attests the query
  (`is_observed_search_query=true`), with recognized query metric,
  public/official provider method and valid source coverage. A
  manually entered seed is **not** a source-observed query.
- `keyword_families`: optional 95% M02 complete-link RapidFuzz lexical
  families scoped by country, language and evidence level, with source
  links and original metric units preserved. They never prove
  semantic equivalence or combine source values. The default cap is
  eighty families and output indicates truncation when reached.
- `country_language_interest`: individual, original source-unit
  **Google normalized interest, Google BigQuery rank or Bing
  keyword-research impressions** grouped only within their original
  source/term/locale/sampling cohort.
- `independent_attention`: Wikimedia pageview requests and news
  mention proxies. They are *independent source types*, NOT verified
  independent human observers or causal market support.
- `developer_problem_evidence`: bounded Hacker News, GitHub Issues
  and Stack Overflow discussion signals; **problem_unsupported**
  by default until the original source and participants are reviewed.
- `package_adoption_evidence`: official npm and public PyPI Stats
  source download observations, kept completely separate even when
  both report units named “downloads”.
- `product_hypotheses`: only explicitly generated, typed
  `generated_keyword_candidate` source terms become **unverified
  validation questions**, not product recommendations or demand
  estimates. A report without such seed evidence has no hypotheses.
- `data_gaps` and `next_validation_action`: always identify missing
  query evidence, inadequate comparable history, unverified
  source boundaries, missing country market, partial provider
  coverage, unverified user need and lack of business/revenue data.
  Fundamental gaps take precedence over per-source partial warnings.
  The next action is human-directed and never launches a task.
- `source_diversity_exact_term_only` and `source_inventory`:
  distinguish the number of distinct primary-source IDs in a
  supplied sample. Same-phrase overlap is NOT proof of independent
  users, equivalent semantics or buyer demand.

Original source-defined `metric_type` and `metric_unit` are carried
unchanged. Source **ranks** are never interpreted as volume, Google
relative 0–100 values are not absolute searches, and source
`coverage_status=no_data` is not an observed numeric zero.

## Conservative rising-query gate

This M14 query-only gate is deliberately narrower than M13’s separate
historical acceleration/seasonality workflow. It does **not** infer
“rising” from just a current normalized score or source-count spike.

Only a source-attested query with source method
`official_api`/`public_api`/`public_dataset`/`community_provider`
and recognized Google normalized relative interest or Bing keyword
impressions can enter the gate. It requires at least **14 consecutive
fully observed daily records** in one identical source ID/URL,
metric+unit, term, locale, sampling scope and provenance basis.
The previous and recent complete seven-day windows must have a
positive first-window mean and a ≥25% increase in the second mean.
Single explosive outliers are explicitly checked. Google 0–100
values from different source-observation normalization batches
cannot be compared. Bad dates, missing periods, partial values,
conflicting revisions or unknown first-window baseline lead to
**abstention**, not a fabricated rise.

This result is a comparison of source-specific measurements in the
original source unit. It is not proven acceleration, a future forecast,
an aggregate market volume or a cross-source ranking.

## Hosted read-only MCP prompt

The hosted server exposes a prompt, not an additional hosted tool:

`source_evidence_research_report(signals_json="...", output_format="text|json")`

It accepts 1–120 previously acquired full typed M00 source signals
and returns the same structured report. The read-only prompt remains behind the existing hosted MCP
perimeter; it does not call Google Trends, GSC,
GA4, Bing Keyword Research, Algolia, PyPI, npm, GitHub, the browser,
or an external AI model. Its direct runtime call and hosted-prompt
registration are covered by tests. No new background schedules,
deployments, settings changes, site property permissions or paid
credentials are necessary.

The hosted MCP prompt and CLI use the same pure function, ensuring
evidence and caveats do not drift between interfaces. The original
six hosted MCP tools remain unchanged and match the submitted app catalog.

## Acceptance and project integration

`tests/test_mjau_research_report.py` exercises real multi-source
cached public data and synthetic source-specific controlled cases for
source provenance, geographic/linguistic boundaries, duplicate
IDs, search-query attestation, two 7-day rising windows, distinct
Google normalization batches, partial/no-data, missing days,
one-off spikes, rank and download non-comparability, unsafe/private
URLs and secrets, 128 KiB/120-record bounds, 80-family truncation,
M02 exact/fuzzy lexical grouping without observed/generated
conflation, deterministic input permutation, CLI text+JSON and
the hosted read-only MCP prompt registration without altering the tool catalog. All test fixtures are local
and no quotas/providers are consumed.

The existing M04 Google Trends implementation is **closed** per
operator direction: availability is external and source HTTP 429
remains an honest unavailable case. No rate-limit bypass or
additional provider retries are performed. M08’s original Windows
request-lock ACL acceptance remains an unrelated independent
permission gate in draft PR #370. M09–M13 remain isolated draft PRs
#371–#374, and M14 is a separate draft built against the same MJAU
feature staging branch (PR #328), not a merge of any of them.

Integration review should consider applying the separately verified
adapter branches sequentially when expressly authorized, checking
conflicts and running the full source/CLI/MCP suite on the combined
tree. Until then, the M14 report consumes **only the stable M00
typed evidence contract and existing M02 clustering interface**.
Any source-generated M12 phrase should be explicitly converted to
a typed `generated_keyword_candidate` rather than promoted to an
observed user search query.
