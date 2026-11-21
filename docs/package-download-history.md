# MJAU M09 + M10 — package registry download histories

These two MJAU adapters provide **software package download events**, not
human users, unique installations, customer conversions, verified buyer
intent or keyword search volume. The ecosystems, source coverage, counted
events and mirror handling differ; **never add or average npm and PyPI raw
download totals into one demand figure**.

Primary source contracts:

- Official npm registry downloads API: https://github.com/npm/registry/blob/main/docs/download-counts.md
- Public PyPI Stats API: https://pypistats.org/api/
- PyPI Stats counting caveats and known mirrors: https://pypistats.org/faqs

Both endpoints are public, keyless, HTTPS and read-only; no GitHub token,
npm login, PyPI account, site ownership, Search Console, Google Ads,
paid service or proxy is needed. The local implementation reuses
requests and the existing original TrendPulse SQLite BudgetCache. No
new dependencies or background schedules are introduced.

## M09 — npm package-download evidence

Source: api.npmjs.org, daily counts from /downloads/range/last-week/{package}
or /downloads/range/last-month/{package}. The source publishes finalized
UTC dates with potential delay, so the most recent day is not assumed to
be today's day or a zero before its batch exists.

Offline preview:

    uv run --locked mcp-trendpulse-cli intelligence npm-downloads --package zod --days 7 --format json

Explicit one-request live check, or cached repeat:

    uv run --locked mcp-trendpulse-cli intelligence npm-downloads --package zod --days 7 --execute --format json

The --package argument is one exact npm package name (including
@scope/name with its slash URL-encoded), never a comma-separated bulk
lookup or arbitrary URL. Allowed periods: 7 or 30 complete source days.
The exact returned package identity, inclusive start/end, date rows and
nonnegative integer download values are checked. Missing source days
are unknown, not silently treated as 0. Explicit source-reported zero
remains a valid zero count. Duplicate dates or rejected rows yield
observed_partial; a full-period total is emitted only with all dates
verified and no rejection. A 404 means package not found OR unavailable
source data, never verified zero adoption.

npm download requests include automation, CI/CD installations, dependency
installs, mirrors and crawlers. The source does not verify unique users
or geographic location. Every daily signal uses the existing typed
npm_package_downloads metric, downloads unit, provenance
official_api and an explicit package/date identity.

## M10 — PyPI Stats daily history

Source: https://pypistats.org/api/packages/{project}/overall?mirrors=false
The project is a PEP 503-normalized Python distribution, not an npm
package identity, user account, verified site or repository selector.

Offline preview:

    uv run --locked mcp-trendpulse-cli intelligence pypi-downloads --package pydantic --days 7 --format json

Explicit one-request live check, or cached repeat:

    uv run --locked mcp-trendpulse-cli intelligence pypi-downloads --package pydantic --days 7 --execute --format json

The official time-series endpoint offers approximately 180 days of
history and updates once per day. The adapter explicitly requests
mirrors=false and only accepts the source category without_mirrors;
known mirror clients are excluded, but CI/CD downloads and other
automation are still included. The requested 7 or 30 daily observations
end at the most recent verified source date, not at an invented
today-based availability date. The source lag in days is returned.
If more than three days behind, the result is observed_partial rather
than falsely current complete coverage; missing dates are unknown.
A verified 0 count remains 0 only where the provider actually reports
it. Only one mirror-excluded daily series is emitted, with the typed
pypi_package_downloads metric and public_api source attribution.

The PyPIStats service asks consumers to cache data rather than
re-querying frequently. A 404, non-JSON body, malformed date, wrong
package, mixed mirror category, response >160 KiB, timeout or rate
limit never leads to a zero-install inference.

## Free-only caps and network boundary

- Offline is default, and CLI help/preview never opens the SQLite store
  or invokes a provider.
- Each uncached --execute call reserves **one** durable provider operation
  before network activity. Distinct source IDs and UTC daily ceilings:
  **npm_package_downloads 5/day** and **pypi_package_downloads 3/day**.
  Each shares the original BudgetCache SQLite file with other MJAU
  sources without resetting their history or quotas.
- Every successful observed, partial or no-data response is stored as
  sanitized date/count rows. An identical request in the UTC day is
  reconstructed through a strict, allowlisted **24-hour validated cache**
  and performs **zero new provider operations**. The exact date source
  scope and input package must match.
- Rate-limit 429/503 triggers a durable five-minute cooldown for its
  source; no retry, failover, proxy rotation, API key or paid bypass.
- Strict host allowlist (api.npmjs.org or pypistats.org), HTTPS only,
  no redirect/proxy, request max 128 KiB npm / 160 KiB PyPI, 5-second
  connection and 12-second read timeout, descriptive User-Agent.
- No interpretation of downloads as unique humans, independent buyers,
  national markets or search volumes. Source-specific metrics remain
  separately queryable and cannot be summed as an adoption score.

## Live source acceptance — 2026-11-21 UTC

One authorized explicit source request **per adapter** and one exact
cached repeat were executed against official free public endpoints.

| Adapter and exact package | Inclusive source dates | Daily records | Total observed downloads | Latest-source lag |
| --- | --- | ---: | ---: | ---: |
| npm: zod | 2026-11-13 to 2026-11-19 | 7/7 | 475,488,459 | 2 days |
| PyPI Stats: pydantic, without_mirrors | 2026-11-13 to 2026-11-19 | 7/7 | 285,184,650 | 2 days |

Both returned status=observed, zero missing/rejected daily source rows,
typed seven-day provenance-attributed TrendSignals and full source
period coverage. The npm service reported zod's first day
2026-11-13 as 72,535,132 events; the PyPI service reported pydantic
2026-11-13 as 42,591,995 events. PyPI provided 181 historical rows;
only the most recent seven were included in M10's output. These are
download events, not distinct humans, sales or geography.

Repeating the identical opt-in npm and PyPI requests returned:
cache_hit=true, requests_attempted=0, network_performed=false
and unchanged daily measurements, with no second source operation.
After acceptance, original SQLite budgets for 2026-11-21 UTC were:
npm 1/5, PyPI 1/3, GitHub Issues 0/12, Google Trends Explore 1/2
(the Google record belongs to the **separate M04 chat**, untouched
here); SQLite PRAGMA quick_check=ok. No new lock folder was required;
the protected GitHub M08 original request-lock ACL remained untouched.

Validation: tests/test_mjau_package_downloads.py exercises preview
and invalid package refusal, identity canonicalization, daily values,
zero vs missing, duplicate dates, late PyPI batches, mirror class
contamination, wrong project/date/provider responses, 404, 429/503
cooldown, durable daily quota enforcement, poisoned cached payloads,
endpoint restrictions, response size and zero-network cache repeat.
M09/M10 are source-complete but remain a **separate draft PR** until
ordinary review/CI acceptance. M04/M08 branch status and M11+ source
tasks are unchanged by these additions.
