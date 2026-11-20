# Official Google Trends BigQuery: SQL preview and opt-in sandbox discovery

The existing **no-network SQL generator** remains available. MJAU M03 adds
one **explicitly opted-in** public-dataset discovery command. It can execute
only after Google's Cloud Billing API independently verifies that the
operator-selected project has **no billing account attached**. A missing
permission, unsupported account, transport error, or ambiguous billing
response blocks execution instead of falling back to a billed project.
No account, project, credential, schedule, or subscription is created.

## What is supported

- US Top 25: `bigquery-public-data.google_trends.top_terms`
- US Top 25 Rising: `bigquery-public-data.google_trends.top_rising_terms`
- International Top 25: `bigquery-public-data.google_trends.international_top_terms`
- International Top 25 Rising: `bigquery-public-data.google_trends.international_top_rising_terms`

These are curated *trending discoveries*, not arbitrary-keyword Trends API
results. International country availability is provider-dependent; a valid
ISO two-letter code does not guarantee that Google publishes that market.
The historical weekly rows repeat terms and ranks; `MIN(rank)` over one
filtered daily snapshot deduplicates a day's leaderboard.

Generate a query without contacting Google:

```powershell
uv run mcp-trendpulse-cli bigquery-sql --country GB --kind rising --limit 10
uv run mcp-trendpulse-cli bigquery-sql --country US --kind top --dma-id 501
uv run mcp-trendpulse-cli bigquery-sql --country SI --kind top --snapshot-date 2026-10-25
```

This prints SQL only; it is useful with **no account or network**. Never
paste and execute it in a billed project to bypass the safeguards below.

## Optional live discovery — billing-free project only

1. Separately create or select a [Google BigQuery sandbox](https://docs.cloud.google.com/bigquery/docs/sandbox)
   project **without linking a Cloud Billing account**. Do not upgrade it.
   The project must have BigQuery and Cloud Billing API permissions needed to
   read data and query its own billing state. Account creation and permissions
   are operator-managed.
2. Install the optional dependency with **uv sync --extra bigquery**, leaving
   the default package untouched. Supply Application Default Credentials
   through Google's official [ADC workflow](https://cloud.google.com/docs/authentication/set-up-adc)
   in your own profile; keep tokens and key files outside the repository.
3. Preview without network; then explicitly opt in to live operation:

~~~powershell
uv run --locked mcp-trendpulse-cli bigquery-discover --country GB --kind rising --limit 5
uv run --extra bigquery --locked mcp-trendpulse-cli bigquery-discover --country GB --kind rising --limit 5 --project-id YOUR_UNBILLED_PROJECT --execute --format json
~~~

The runner validates the allowed table, country, optional subdivision, date
(last 30 days), and limit (1–25). It independently checks the live billing
configuration, **dry-runs first**, refuses estimates exceeding **100 MiB**,
passes BigQuery's server-side maximum_bytes_billed setting, uses the
repository's SQLite local cap of **3 attempted executions per UTC day**,
and avoids automatic job retries. A 15-minute cache can repeat successful
research without issuing additional cloud queries.

Successful JSON includes the source market, selected snapshot, query type,
BigQuery dry-run byte estimate and separate attributed google_bigquery_rank
signals. Their values are **curated ranks from the latest source week**,
not total query counts, search volume, market share, or all country searches.
If a country's snapshot is absent, an empty result is **unknown coverage**,
not zero popularity. Source data can be delayed and country coverage varies.

Results such as no_sandbox_project, bigquery_extra_missing,
no_sandbox_credentials, sandbox_billing_unverified,
billing_account_attached, local_daily_budget_exhausted, and
estimated_bytes_exceeds_limit are refusals, **not** fallback modes.
The CLI deliberately does not print account credentials, tokens, raw
upstream errors, or inferred missing search metrics.

## Zero automatic paid usage

- The original SQL preview is completely offline. Normal TrendPulse flows do
  not load BigQuery credentials or install its optional SDK.
- Only the opt-in BigQuery discovery execution flag can create jobs, and only
  on a project verified as billing-free. A failed billing check refuses work.
- Even a no-billing sandbox can exhaust its free quota. Use explicit byte
  caps and local budgets; LIMIT alone does not restrict bytes scanned.
- If a sandbox's published allowance is exhausted, let the request fail.
  Do not attach billing, route through paid accounts, rotate projects to
  evade quotas, or retry unacknowledged jobs.
- Official BigQuery public-data access does **not** resolve issue #22's
  separate authorization review for a public hosted ChatGPT app; redistribution
  and public-service terms must still be reviewed before integration.

Official references:

- https://support.google.com/trends/answer/12764470
- https://codelabs.developers.google.com/ca-in-bigquery
- https://docs.cloud.google.com/bigquery/docs/sandbox
- https://docs.cloud.google.com/bigquery/docs/best-practices-costs
- https://docs.cloud.google.com/billing/docs/reference/rest/v1/projects/getBillingInfo
- https://docs.cloud.google.com/python/docs/reference/bigquery/latest/google.cloud.bigquery.job.QueryJobConfig
