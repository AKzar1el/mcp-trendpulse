# Official Google Trends public dataset: operator-only SQL workflow

This is an **opt-in, no-network SQL generator** for Google's first-party
BigQuery public dataset. It does not execute queries, acquire credentials,
enable a hosted provider, or create a Google Cloud billing account.

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

Copy the SQL into the **Google Cloud BigQuery Console** and run a **dry run**
first. Confirm the exact table schema, snapshot availability, and estimated
bytes scanned with the provider. The generator cannot validate the live
table or guarantee that the selected country's snapshot exists.

## Zero automatic paid usage

- No code in this repository sends BigQuery jobs or uses a Google credential.
- The BigQuery sandbox has no required payment method and provides the
  documented free query allowance, subject to platform constraints.
- For any account with billing enabled, set a **maximum bytes billed**
  threshold (for example 100 MB) *in the BigQuery query settings* before
  executing; use a custom daily query quota for stricter project control.
  Google warns that `LIMIT` alone does not limit bytes scanned or charges.
- Any manually run query can use quota or incur a charge if the free allowance
  is exhausted. The generator does not and cannot guarantee zero spend.
- Official BigQuery public-data access does **not** resolve issue #22's
  separate authorization review for a public hosted ChatGPT app; redistribution
  and public-service terms must still be reviewed before integration.

Official references:

- https://support.google.com/trends/answer/12764470
- https://codelabs.developers.google.com/ca-in-bigquery
- https://docs.cloud.google.com/bigquery/docs/sandbox
- https://docs.cloud.google.com/bigquery/docs/best-practices-costs
