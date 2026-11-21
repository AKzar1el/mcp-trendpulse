# MJAU M13 — Source-scoped historical momentum and lifecycle

M13 is a **strictly offline, deterministic historical classification tool**.
It consumes existing M00 TrendSignal records, never fetches upstream
providers, never writes a history database, changes no rate-limit budget
and does not ask for Google Trends, GSC, GA4, Bing Webmaster, NPM or PyPI
credentials. It uses the installed Python standard-library statistics,
calendar and datetime modules and existing M00 Pydantic types. Neither
pandas resampling nor statsmodels STL is necessary for the conservative
rules implemented here, and **no new dependencies** were added.

These classes describe changes **inside a supplied, comparable source
sample**. They are NOT forecasts, proof of product adoption or demand,
independent unique users, causes, market size, source-global first-seen,
annual seasonality, cross-provider agreement, or an SEO volume estimate.

## Reproduce the source-backed acceptance case

The example JSON is copied from actual previously validated public
M09/npm and M10/PyPI Stats **read-only local source cache** entries
captured on November 21, 2026 UTC. It contains seven correctly dated
M00 daily download signals for each of `zod` (npm) and `pydantic`
(PyPI Stats `without_mirrors`). There are no requests to either
provider in M13 and no new quota reservations.

    uv run --locked mcp-trendpulse-cli intelligence lifecycle --input docs/examples/mjau-m13-observed-package-downloads.json --format json

Or human-readable:

    uv run --locked mcp-trendpulse-cli intelligence lifecycle --input docs/examples/mjau-m13-observed-package-downloads.json --format text

Expected outcome for both independent source groups:

- `status=insufficient_history`, `lifecycle=unknown`
- exactly **seven source-dated daily periods**, November 13–19, 2026
- **14 consecutive observed daily points required** for default
  two-window daily comparison, so `comparison=null`
- `provider_operations=0`, `network_performed=false` and
  `sqlite_or_quota_modified=false`
- no invented relative change or lifecycle

The original public provider counts in that cached example total
475,488,459 npm tarball download events for `zod` and 285,184,650
PyPI Stats (excluding known mirrors) events for `pydantic`. The
numbers are retained as separate typed **source download observations**;
they are never added, normalized together, converted to unique
developers, used to rank search popularity, or compared as one trend.
Most importantly, **seven days are insufficient to assert growth**.

## Strict input and provenance

The local CLI reads up to **128 KiB** of JSON, with one to 500 full
M00 typed TrendSignal records. Supported root shapes are a list or
an object whose only key is `signals`. Malformed, oversized or
unexpected source payloads fail closed with generic secret-safe errors.
The pure analysis function does not open files, SQLite connections,
network services or subprocesses.

A series is only comparable when these values match exactly:

- `source_id` and `source_url`; original `normalized_term`
- `country` and `language`, including null unknown scopes
- `metric_type` and `metric_unit`
- `sampling_scope`, `provenance.method` and
  `provenance.sampling_basis`
- `period.granularity`

An exact series boundary is important: pageviews, Bing impressions,
normalized Google interest, npm downloads, PyPI download counts,
Stack Overflow questions and developer issue mentions **must not
be summed or numerically averaged together**. At most **16** distinct
source/scope series are accepted in one file. Original source URL,
metric unit, sampling scope, bounded source-record IDs, first/last
observed UTC time, recorded-period bounds and term labels are retained.

## Alignment and missingness rules

Only **daily**, **weekly** and **calendar-monthly** typed source
periods are eligible. Minimum observations per complete comparison
window:

| Granularity | Previous window | Recent window | Total minimum |
| --- | ---: | ---: | ---: |
| Daily | 7 contiguous fully observed days | 7 days | 14 |
| Weekly | 4 consistently anchored source weeks | 4 weeks | 8 |
| Monthly | 3 complete calendar source months | 3 months | 6 |

Daily start/end must be the same UTC date. Weekly observations
must consistently use either a single dated provider label separated
by exactly 7 days, or full inclusive seven-day periods; a shifted
weekday anchor is **not** silently resampled. Calendar-monthly
observations must start on the first and have consistent source labels
or complete month-end spans. The tool rejects mixed period shapes,
ambiguous point-in-time records, future measurements and unsafe
integer precision above 2^53−1 for count units.

Every period must be `coverage_status=observed` and carry a valid
source number. A `partial`, `unavailable`, `no_data` or unmeasured
period causes **abstention**, never conversion to zero. Missing
dates **between** supplied source periods are flagged with a bounded
list of up to 24 missing dates; gap counting is constant-time even
for huge calendar gaps. Conflicting repeated source revisions for
one period are blocked, while identical duplicated observations
are collapsed deterministically and counted explicitly.

A genuine source-reported numeric **zero remains zero**.
Important boundary limitation: without an authoritative provider
window declaration in the typed source payload, missing
**leading/trailing** periods cannot be detected. Each result explicitly
reports `provider_declared_window_boundaries_verified=false` and
warns against interpreting internal gap checks as complete provider
history. The first positive source period is only *first within the
supplied sample*, not necessarily the term's creation or first-ever
market appearance.

Relative Google Trends 0–100 values are comparable **only inside
one identical provider normalization batch**. Distinct
`observed_at` timestamps for normalized source samples produce
`incomparable_normalized_batches`. Source ranks, approximate
trending traffic buckets and generated unmeasured keywords are
explicitly excluded from lifecycle arithmetic.

## Transparent classification thresholds

The lifecycle output always carries a `status`, `lifecycle`,
readable explanation, previous/recent source windows and bounded
source-specific numeric diagnostics **only when the history is fully
observed and aligned**. Conservative heuristic classes include:

- **`sustained`:** the two complete observed window means differ
  by ≤15%, with bounded intra-window coefficient of variation
- **`declining`:** the latest complete-window mean is at least
  25% below its previous comparable source mean; explicit zero
  counts remain valid
- **`rising_not_acceleration_verified`:** ≥25% relative increase
  between two source windows, insufficient evidence of acceleration
- **`accelerating`:** at least three complete source windows,
  with two positive consecutive growth steps and the second
  growth ratio more than 0.20 above the first
- **`new_in_observed_window`:** *every older supplied period* is
  explicitly zero, followed by at least three positive recent
  periods. This is not proof of a global first-ever observation
- **`resurfacing_in_observed_window`:** earlier source positives,
  an observed-zero baseline, then multiple recent positives
- **`one_off_spike`:** exactly one recent value ≥4× its prior
  baseline, with the other recent periods close to the baseline
  (no claim about future recurrence)
- **`seasonal_pattern`:** descriptive repeated seven-day shapes
  across at least **four consecutive full seven-day cycles**,
  with stable week means, substantial normalized intraweek
  amplitude and ≥0.85 minimum correlation to the four-week
  profile. This is **not** annual/holiday or causal seasonality
- **`no_activity_observed`:** explicit zeros in all supplied
  complete comparable windows, not global absence
- **`unconfirmed_change`** / **`irregular_or_unclassified`:**
  abstain where there are too few repetitions or too much
  volatility to confidently choose a stricter class

All observed changes are descriptive, source-scoped and historical.
They are not predictions or recommendations. The output's
`forecast_generated` and `buyer_demand_verified` remain false.

## Tests and integration

`tests/test_mjau_lifecycle.py` verifies deterministic synthetic
increasing, accelerating, sustained, declining, new/resurfacing,
one-off spike, weekly-pattern and irregular histories, including
weekly and calendar-monthly alignment, input-order independence,
identical/conflicted source re-observations, exact zeros vs unknown
dates, normalization batches, future-date refusal, extreme date gaps,
uncertain leading boundaries, stale/partial and incompatible units,
secret-safe CLI, and **the genuine prior M09/M10 cached public
source dataset**. The genuine short history is expected to abstain
rather than invent growth.

M04's external provider availability is a **closed implementation
matter** at the user's instruction: when Google Trends is available
the existing feature can use it, and when HTTP 429/other unavailable
it reports unavailable without retry bypass. M13 never contacts M04.
M08's original Windows `.request_locks` ACL verification is a
separate local permission gate and does not affect M13.

This implementation is intentionally in a separate draft PR from
M08 (#370), M09/M10 (#371), M11 (#372), M12 (#373), and original
staging PR #328. M14 cross-source synthesis should be integrated
only after these independent code changes have been reviewed,
without ever treating different metrics or source observers as one
shared unit of market demand.
