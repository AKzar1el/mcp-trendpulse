# Opportunity triage and temporal evaluation (optional, free-only)

The intelligence extension supports **18 evidence-combination recipes**. It is
an *investigation triage tool*, not a probability that a startup will succeed
and not a source of verified paying customers. The original 16 community MCP
tools and all scheduled agents remain unchanged.

## Exact scope and interfaces

The separate opt-in stdio MCP exposes eighteen read-only tools, including:
- `intelligence_opportunity_lanes`: inspect each combination and its question;
- `intelligence_evaluate_opportunities`: evaluate caller-supplied, dated evidence;
- `intelligence_walk_forward_backtest`: grade historical triage only when later customer outcomes exist.
- `intelligence_review_devpost_candidates`: offline, bounded due-diligence checks for Devpost software ideas, covering award, repository license, competitor, customer and test evidence. This is not a buyer-demand validator or automated source ingester; see [Devpost opportunity validation](devpost-opportunity-validation.md).
- `intelligence_observe_source_snapshots`: convert bounded public collector snapshots into dated evidence trails, provider coverage diagnostics and exact corporate-registry links.
- `intelligence_hunt_current`: query recent public evidence with bounded topical seeds; rank present-day research activity without requiring historic records.
- `intelligence_discover_current`: no topic seeds; discover candidate themes from recent scholarly publications, public consumer complaints, and European procurement notices.

CLI equivalents:

```bash
mcp-trendpulse-cli intelligence hunt --topic "battery recycling" --topic "agent reliability" --execute
mcp-trendpulse-cli intelligence observe --input-json observations.json
mcp-trendpulse-cli intelligence opportunities lanes
mcp-trendpulse-cli intelligence opportunities evaluate --input-json research.json
mcp-trendpulse-cli intelligence opportunities backtest --input-json outcomes.json --k 3
```

Default source queries remain plan-only. The evaluator never accesses a
network, visits an arbitrary website, contacts buyers, sends mail, uses an LLM
or writes to external systems.

### Eighteen combinations

| Lane | Free-source recipe | Test the alternative explanation |
|---|---|---|
| agent_safety | GitHub issues + hiring + CELLAR + TED | Is the incumbent platform already sufficient? |
| agent_commerce | GitHub issues + hiring + CFPB + USAspending | Is activity actually machine-purchase spending? |
| sme_margin | Eurostat + hiring + TED + World Bank | Is the affected SME reachable with real budget? |
| compliance | CELLAR + TED + hiring + USAspending | Is regulation legally effective rather than proposed? |
| fraud_identity | CFPB + GitHub issues + TED + GLEIF | Is the buyer outside incumbent compliance vendors? |
| household_finance | ECB + Eurostat + CFPB + World Bank | Is saving measurable and does a payer exist? |
| care_automation | CORDIS + hiring + World Bank + TED | Is the service reimbursable or directly purchased? |
| energy_software | ENTSO-E + TED + CELLAR + Copernicus | Is the software problem separable from physical assets? |
| developer_reliability | GitHub issues + Greenhouse details + USAspending | Will a buyer purchase remediation or hire instead? |
| research_to_product | CORDIS + OpenAlex + EPO + hiring | Is research activity becoming actual customer demand? |
| procurement_regulation | CELLAR + TED + USAspending | Are contracts actually awarded to address the rule? |
| corporate_identity | GLEIF + Companies House + CELLAR + TED | Can a real budget-owner justify vendor onboarding spend? |
| privacy_operations | CELLAR + TED + GitHub issues + hiring | Does an actual EU buyer fund the required workflow? |
| vendor_due_diligence | GLEIF + Companies House + TED + hiring + CELLAR | Is counterpart verification being purchased rather than merely required? |
| public_cloud_finops | USAspending + GitHub issues + hiring + SEC company concepts | Is US cloud operations spending addressable by a separate vendor? |
| customer_dispute_ops | CFPB + hiring + GitHub issues + USAspending + SEC company concepts | Does observed consumer friction translate into a buyer budget? |
| industrial_maintenance | TED + hiring + CORDIS + EPO + ENTSO-E | Does a contract cover software rather than physical equipment? |
| research_procurement | CORDIS + OpenAlex + EPO + TED + hiring | Is commercial procurement distinct from research funding? |

The recipes are **investigation hypotheses**, not automatically validated
multi-source joins. **Geographic compatibility is mandatory**: US-only
spending/complaints cannot corroborate EU awards simply because titles match.
Sources from different jurisdictions may be useful contextual evidence but
must not be scored as if they prove one local buyer's budget. The combinations
are **supported source types**, not verified relationships among individual records. Eurostat macro statistics, EPO
patents, Copernicus satellite catalogue metadata and GDELT batch manifests
cannot independently prove commercial demand.

## Evidence contract

Every candidate must identify a narrow workflow, buyer type, jurisdiction,
and selected lane. Evidence must include source, original record identifier,
real publisher, public HTTPS URL, publication date, first-observed date,
geography, specific workflow, and polarity. For a higher *buyer-interview*
priority, the award's exact buyer-entity identifier must also match the
candidate's identifier. A shared keyword or industry is **insufficient**.

This fictional demonstration uses **synthetic observations and buyers**. Do
not cite these records as market intelligence or send them to prospects.

```json
{
  "as_of": "2026-11-18",
  "candidates": [{
    "id": "incident-automation",
    "title": "Incident triage for public agencies",
    "lane": "developer_reliability",
    "workflow": "incident_triage",
    "geography": "US",
    "buyer": "Public agencies",
    "buyer_entity": "agency-example"
  }],
  "evidence": [
    {
      "id": "sample-issue", "candidate": "incident-automation",
      "source": "github_issues", "publisher": "publisher-example-a",
      "origin_id": "record-issue", "geography": "US",
      "workflow": "incident_triage", "polarity": "support",
      "published_at": "2026-11-05", "observed_at": "2026-11-10",
      "url": "https://example.org/records/issue",
      "claim": "Illustrative manual incident-handling example"
    },
    {
      "id": "sample-job", "candidate": "incident-automation",
      "source": "greenhouse_job", "publisher": "publisher-example-b",
      "origin_id": "record-job", "geography": "US",
      "workflow": "incident_triage", "polarity": "support",
      "published_at": "2026-11-06", "observed_at": "2026-11-10",
      "url": "https://example.org/records/job",
      "claim": "Illustrative incident operations vacancy"
    },
    {
      "id": "sample-award", "candidate": "incident-automation",
      "source": "usaspending", "publisher": "publisher-example-c",
      "origin_id": "record-award", "buyer_entity": "agency-example",
      "geography": "US", "workflow": "incident_triage",
      "polarity": "support", "published_at": "2026-11-07",
      "observed_at": "2026-11-10",
      "url": "https://example.org/records/award",
      "claim": "Illustrative agency spend on related operations"
    }
  ]
}
```

A returned status of `buyer_interview_priority` means only that the
caller described multiple distinct original publishers, material work signals,
and a matching award-related buyer. The caller's provenance assertions are
**not independently authenticated by this tool**. It is never proof of a
paid pilot or product-market fit.

The only output ordering is a transparent, ordinal investigation priority.
There is no arbitrary percentage score, population market-size estimate,
automatically recommended product, or success probability.

## Validity and abstention rules

- **Dates**: published and observed must both be on/before the historical
  as-of date; records older than one year are excluded.
- **Identity**: independent evidence means distinct original publishers,
  not repeated summaries; origin IDs and exact URLs are deduplicated.
- **Comparability**: only evidence of the exact submitted workflow and
  geography contributes. "GLOBAL" does not silently mean "any country."
- **Contradictions**: dissenting publishers force contested/conflict-review
  status; they are not hidden by a positive majority.
- **Provider failures**: rate-limited, stale, unavailable, invalid-schema or unconfigured
  sources make the lane partial. Unavailable is not interpreted as zero demand.
  Missing source-health reports are flagged separately; a caller-supplied
  `ok` flag is not an independent provider audit.
- **Buyer gate**: public awards are purchasing proxies, not payment to
  your proposed future software; exact claimed buyer identifier is required
  for buyer-interview priority.
- **Source type**: only documented provider classes count toward evidence
  diversity. A media or patent publication alone cannot prove buying intent.
- **Security**: at most 20 opportunities and 300 evidence records, bounded
  overall payload, fixed known source IDs, public HTTPS evidence links,
  no network from evaluator and no APIs/credentials entered via MCP.

## Trends with actual denominators

Trend detection requires a complete 28-day collection (14 prior + 14
recent days) of daily event counts, **including zero-event days**, for
each supported dated-event provider. Static company registries, GDP indexes,
Copernicus catalogue metadata and GDELT batch manifests **cannot** provide
topical momentum from this source adapter. Each row must identify source, geography, day, unit
`daily_events`, value and confirmed coverage. Sparse series, missing
days, differing units/geographies, non-integer event counts, future samples,
sources outside the selected lane, or contradictory signals return
unknown/conflicted rather than manufactured momentum. Two related applicant
tracking system endpoints count as **one** signal family, not two independent
corroborations. If a submitted trend source is unhealthy, momentum is
`coverage_degraded` rather than "rising". The evaluator
does not add counts across providers with different collection populations.
`rising_multi_source` indicates two comparable provider series
rising independently, not a CAGR, revenue growth or payment forecast.

## Historical validation before investment decisions

Historical examples require prior evidence snapshots plus *later* dated,
caller-attested paid-pilot/no-purchase outcomes with a public HTTPS evidence
URL. Outcomes cannot be in the future, reused across examples, or recorded
inside 30 days of the hypothesis date. Measurements use strict chronological
as-of cutoffs; data observed after the cutoff cannot support past rankings.

The descriptive precision-at-k metric is suppressed until at least eight
labels, two cutoff dates, and two positive and negative outcomes are present.
Even if passed, labels and sample selection have to be independently audited.
**Synthetic fixtures validate the evaluation machinery, never predictive
accuracy.** Truly calibrated commercial predictions require real historical
cohorts and transparent baseline comparisons.

Time-aware validation methodology:
https://stanford-mse-125.github.io/book/lec16-feedback-loops.html

Buyer-validation research:
https://www.ycombinator.com/library/6g-how-to-talk-to-users

## Failure-injection matrix

| Condition | Enforced behavior |
|---|---|
| HTTP 429/503 | Short shared per-source cooldown (bounded 30–300 s), no automatic retries |
| Malformed schema/transport error | Short negative cache, never fake an observed signal |
| HTTP 200 containing malformed record arrays | Invalid source shape, not fabricated zero observed demand |
| HTTP 200 with an error envelope and empty results | Reject as provider error, not zero demand |
| Provider health omitted or incomplete | Explicit unverified-health caveat even for archived evidence |
| Related hiring feeds both rising | One signal family, no false multi-source corroboration |
| Trend from outside the selected lane | Unknown, no unrelated-source ranking |
| Unhealthy trend provider | Coverage degraded, not a rising momentum claim |
| Marketing-query variants of a source URL | Canonicalized for deduplication, original URL retained for audit |
| Rotated free API key | Different request cache identity; cannot reuse prior key's cached data |
| Ten identical agent requests | Per-query single-flight lock: one provider call on success |
| Concurrent different queries | Retain independent requests, within provider daily budgets |
| Corrupt SQLite cache | Fail closed; no invented zero demand |
| Provider missing / not configured | Degraded/partial priority, not a false negative |
| Duplicated articles, URLs, publishers | Deduplication and publisher-independence limits |
| Future-dated or stale records | Excluded from current and past-as-of rankings |
| Contradictory records | Conflict review, suppress investment-like priority |
| Mixed geography/workflow | Excluded, not scored together |
| Sparse/incomplete daily trends | Unknown momentum, no trend claim |
| Missing buyer / unlinked awards | Research-only priority |
| Insufficient or future outcome labels | Backtest abstains |
| Oversized/invalid JSON input | Explicit error, no outbound calls |

The CI tests are deliberately isolated from your existing scheduled agent
fleet. This matrix covers **tested failure modes**, not every conceivable
hardware, OS, provider, security or market failure. Google SRE recommends
controlled failure injection and finite retry budgets precisely because
untested outages can cascade:
https://sre.google/sre-book/addressing-cascading-failures/

The trend series still require independently checked collection completeness:
`coverage_complete` is a caller assertion, not a remotely verified certificate.
Historical outcomes are still externally asserted, not trained or audited.

## Limitations and next gate

The current 17-source live smoke, independent MCP client, RSSHub,
changedetection.io, local Windows credentials and Python checks establish
basic adapter and transport behavior; they do not produce an accuracy
benchmark on real paying buyers. Four generous-free authenticated sources
require owner-provided keys for provider-specific live tests. Public source
titles/dates must be normalized and verified before ranking real cases.
A data ingestion/exporter that automatically and reliably constructs these
attributed evidence objects is not yet provided. No new standing worker,
paid API, hosted MCP endpoint or production deployment is part of this PR.


## One-time keyless multi-lane compatibility matrix

Run `python scripts/intelligence_multi_lane_smoke.py --mode offline` to validate
allowlisted source recipes without a network, or opt into the **one-time**
GitHub Actions workflow `Optional intelligence keyless multi-lane matrix`.
Its six bounded live scenarios exercise research commercialization, procurement
regulation, customer disputes, cloud FinOps, supplier due diligence and SME
margin context. Sources include keyless OpenAlex, CORDIS, CELLAR, TED,
USAspending, CFPB, GitHub issues, GLEIF, Eurostat, World Bank and public
hiring boards. Requests use existing provider budgets, no credentials or
new scheduler. The artifact deliberately contains only status, record count,
source class and non-sensitive diagnostic metadata, **never raw API payloads**.

A real response does NOT mean that the data are safely joinable: different
buyers, jurisdictions, or time windows cannot be combined to claim an
opportunity. The matrix explicitly reports buyer/period/jurisdiction matching
as *unverified* and never generates commercial confidence, TAM, success
probability, or product-market-fit scores. Independently validated paid-buyer
outcomes are required before evaluating commercial predictive accuracy.


## Buyer identity and source observations (no EPO credentials needed)

Pass a bounded JSON object containing `topic`, `as_of` and a `snapshots`
array of previous `intelligence_collect` results to `intelligence observe`, or
call the corresponding isolated MCP tool. This workflow is **offline** and
read-only. It accepts Companies House, GLEIF, OpenAlex, TED, USAspending,
GitHub Issues, CORDIS, CFPB and Greenhouse, with stricter provenance and schema
handling than treating raw search matches as market signals.

- Companies House corporate numbers and GLEIF LEIs are joined **only** when
  GLEIF's `registeredAt.id` is one of RA000585 (England and Wales), RA000586
  (Northern Ireland) or RA000587 (Scotland), and `registeredAs` matches the
  exact Companies House company number. Similar names are **not** identity
  evidence; mismatched legal names on exact-ID matches require review.
- An awarded US federal contract is attached to the **awarding agency** as
  potential buyer, not the recipient supplier; its reported amount is not
  assumed to have been paid, nor to be software spending. Record *Last Modified
  Date* must not be relabeled an award date.
- Dated OpenAlex works, public GitHub issues, TED notices and CFPB complaints
  produce traceable observation samples with publication/receipt semantics.
  Neither research, vacancies, complaints nor notices establish a buyer budget.
- Search results are relevance-ranked, partial and subject to source failure.
  This tool explicitly returns **market momentum not estimable**. It will not
  infer rising demand or fabricate missing zero-event days from top-N results.
  The separate 28-day coverage-gated `daily_trends` evaluator remains the
  only pathway to a source-level direction estimate.
- Each source row can be **caller supplied** and is therefore not independently
  authenticated. Inspect original provider links before contacting or naming
  potential buyers. These are observation records, not verified leads.

The old 16-tool community MCP stays unchanged. The observation tool is available
only on the separate, manually launched optional intelligence server. It has no
scheduled polling, key access, export automation or paid provider dependencies.

Source semantics: [GLEIF registration authorities](https://www.gleif.org/en/lei-data/lei-linking-to-registration-authorities),
[Companies House search schema](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/resources/companysearch),
[OpenAlex works](https://help.openalex.org/data/works/attributes/), and
[USAspending awarded contracts](https://api.usaspending.gov/docs/endpoints/api/search/spending_by_award/).


### Eighteen-lane topical observation coverage

The observation report now evaluates the **partial topical sample coverage of
all 18 recipes**. The `eighteen_lane_coverage` array counts only literal
source-title/company-name matches against the declared topic, plus the number
of present source types. This is intentionally a weak retrieval check, **not**
semantic relevance or a recommendation engine. Every lane reports either
`review_original_sources_and_buyer_workflow` or
`insufficient_topical_cross_source_evidence`, with an explicit
`not_a_validated_market_opportunity` flag. No lane receives a percentage score.

A collector-projected `record_count` describes a **bounded page or sample**, not
the whole searchable source population. Consequently `sample_complete` and
`population_coverage_verified` are always false even if the projected row
count equals the sample length. The narrower `projection_sample_complete`
metadata only checks whether the bounded extractor retained every projected
row. This avoids false trending evidence from sampled denominators.


### Live acceptance without credentials

The optional GitHub Actions workflow `intelligence-observation-smoke.yml`
executes three small real public queries (GLEIF, CORDIS, USAspending),
passes their collector observations through the offline normalization pipeline,
and publishes only source status and bounded count diagnostics. Source
unavailability is explicitly marked inconclusive and blocks a claimed
successful integration; no API keys, company records or raw public responses
are uploaded. Results are **compatibility and provenance tests**, not
validated trend forecasts or winning companies.


### No EPO credential required

Patent publication data are **optional context**, not mandatory buying evidence.
`research_to_product`, `research_procurement` and
`industrial_maintenance` continue to triage based on their other free
sources if EPO OPS is unconfigured. The provider status remains visible and
the report labels missing optional enrichment explicitly, but does not
artificially downgrade the primary buyer/workflow investigation. An actual
failure of a required source still degrades the lane. There is no EPO
registration requirement, paywall, or paid substitute for TrendPulse.


On shared GitHub Actions runner IPs, keyless OpenAlex queries have returned
HTTP 429 under concurrent workflows. We **do not retry or bypass free quotas**.
The separate multi-lane suite continues to test OpenAlex when permitted;
this observation smoke avoids an unnecessary duplicate concurrent API call
and instead checks the GLEIF corporate-identity JSON shape. Authenticated
OpenAlex testing uses locally stored free credentials, never CI secrets.

## Current-activity hunter — no historical database required

Run the new standalone CLI or call the **eleventh isolated MCP tool**:

`mcp-trendpulse-cli intelligence hunt --execute`

Without `--topic`, a transparent deterministic three-topic rotation draws from
18 global research **seeds**. Those seeds are investigation questions, not
automatically detected trends. Use `--topic` up to four times to study specific
themes; use `--source` up to five times to select actual original providers.
Without `--execute`, the command is **plan-only** and never fetches remote data.
The normal community/hosted 16-tool MCP and scheduled workers stay untouched.

The default fixed-origin, free-only providers are GitHub issues, OpenAlex,
CORDIS and USAspending. You can add `--source companies_house` and
`--source gleif` for company identity context (or select CFPB complaints and
TED procurement notices). When the CLI runs under the same Windows account as
the securely configured credentials, its Companies House/OpenAlex requests
read the OS Credential Manager automatically. **No key is returned by hunter
outputs or passed as an LLM tool argument.** If the MCP service uses another
OS identity, configure credentials for that account separately.

The optional `lookback_days` parameter (7–90; 30 by default) uses free,
provider-supported **publication/creation** filters on OpenAlex works,
GitHub issues and CFPB complaints, not OpenAlex's paid synchronization
filters. OpenAlex publication date is not its provider-indexing date.
Incomparable macroeconomic, registry, and award-modification timestamps
are never passed off as recent buyer purchases.

A trend is classified as *current cross-source activity* only when dated
topical records are observed in at least two independent evidence classes,
with sample provenance and original links. This is a **watchlist for
investigation**, not proof of growth: small relevance-ranked API pages
cannot estimate a population rate or growth direction. Single-source
activity, undated context, sparse/no results, outages, and missing credentials
are reported distinctly. Lexical term overlap is an exact/partial keyword
check, not semantic proof that two sources describe the same buyer or
workflow.

Use `mcp-trendpulse-cli intelligence hunt --execute --record-history` to
**opt in** to minimal SQLite metadata history under the current Windows
user's `~/.mcp-trendpulse/intelligence/hunter_history.sqlite`. It stores
hashes of topic/query identity, date, provider coverage and sampled counts,
not raw records, company names, URLs, or credentials; retention is 90 days.
Comparable complete time series can be developed from future evidence,
but the present-day hunter never requires one. No scheduled polling or
new agent is activated by this command.

Recommended initial verification:

`mcp-trendpulse-cli intelligence hunt --topic "battery recycling" --topic "cloud cost management" --execute --record-history`

The one-time test workflow proves that the safe read-only workflow runs from
a fresh GitHub Actions client with publicly accessible data. Authenticated
local tests remain separate and will be possible when the Codexify tunnel is
restored. No patents or EPO registration are necessary.

Current official API references:
https://help.openalex.org/api/filtering/
https://docs.github.com/en/search-github/searching-on-github/searching-issues-and-pull-requests
https://cfpb.github.io/ccdb5-api/


### Human-readable watchlists

Pass `--format text` together with `--execute` for a compact numbered list of ranked current activity, dates, source references, coverage warnings and next steps. Agents retain the default JSON format. Source titles have terminal control characters stripped. CFPB observations combine public product and issue categories, without personal complaint narratives. Topic matching now normalizes simple plurals, but never claims semantic equivalence or verified growth.


### Current hunter: GitHub issue quality gates

A November 19 review of four public GitHub issues revealed that an automotive
battery-recycling market forecast, a hypothetical engineering design proposal,
and a personal profile repository task were being treated as evidence of
fresh market demand. None of these establish a paying customer. The remaining
agent-reliability issue is a legitimate engineering task but does not by itself
verify external buying intent.

The GitHub issues adapter now uses **bounded lexical classification**, reads
only a short in-memory body excerpt, and projects only the public issue title,
ID, creation date, URL and coarse quality label. The raw narrative, author
identity and labels are not exposed through the observations projection.
The hunter screens promotional market forecasts, explicitly hypothetical
proposals, personal-profile repository tasks, and obvious implementation
assignments from *current market activity* counts. Quality-screen diagnostics
preserve original source links and exclusion reasons for audit.

Single-source activity earns at most **1/3 investigation priority**; multiple
current corroborating evidence *classes* at most **2/3** until buyer, budget,
and workflow relationships are independently verified. Priority 3/3 is
intentionally unreachable from source titles alone. These are heuristic
investigation priorities, **not success probabilities**. A genuine novel
proposal or engineering task might be downgraded: the gate does not establish
that a source is spam, fraudulent, or worthless.

Previously cached public query snapshots may lack body-derived classifications
until normal expiry. Title/URL fallback screening still rejects forecast
headlines and personal-profile issues, without deleting caches or bypassing
provider quotas.

### One-hour cached-issue classification gap (2026-11-19 field report)

The second real user watchlist still showed a hypothetical Zion Metric issue.
Root cause: the collector caches provider results for 60 minutes, including
a *bounded* raw `data.items` projection, but its older
`observations.sample` lacks `issue_evidence_type` computed by the newer
GitHub-body filter. Title/URL-only fallback could not see the explicitly
hypothetical language in the issue body.

The offline normalization layer now **reclassifies matching cached public issue
items from their already retrieved, bounded raw bodies, in memory**. It requires
matching GitHub issue ID, title and URL to avoid misattribution; a stricter
prior classification is preserved if a truncated cached body omits context.
The raw body is never returned in normalized observations or the human-facing
watchlist. No network request, cache deletion, quota bypass, or new credential
is needed to update these source-quality labels. If a cached response truly
lacks the original body, its issue remains explicitly **unverified**, not
automatically treated as a validated customer pain report.

The text watchlist also lists each selected provider's actual reported status,
bounded accepted record count, cache usage and allowlisted HTTP failure code
when present. This makes it obvious when all evidence came from GitHub because
OpenAlex, CORDIS or procurement returned no matching records or were rate
limited. Safe source metadata do not reproduce unknown upstream error strings,
tokens, auth headers or private bodies. These are availability diagnostics,
not measured demand volumes. Regression tests cover the exact public-issue
failure mode, source-ID/title mismatch protection and HTTP 429 visibility.

### Source contribution audit: observed rows are not trend evidence

The user's third local run on 2026-11-19 verified the quality-screen repair:
the promotional GitHub market-size post and the hypothetical Zion proposal
were both excluded. Yet OpenAlex reported five valid sampled records for
each seed with no eligible topical dates, while CORDIS/USAspending contributed
undated or non-comparable background. This is not a provider failure and
must not be mistaken for evidence of recent or increasing demand.

The human-facing watchlist now keeps provider status separate from **source
contribution**: for every provider it reports accepted bounded sample rows,
literal-title topic matches, recent eligible matches, contextual-only
matches and filtered noise counts. For a context-only topic, it displays
up to two original context records with the precise date/eligibility reason
(e.g., absent publication date, outside lookback or award Last Modified Date
not being a comparable market-event timestamp). Providers that successfully
returned five unrelated results are explicitly shown as zero topical
matches rather than implicitly credited for five signals.

In this **current-first** priority scale, purely historical or undated
context now has priority 0/3, while source-specific current activity can
receive 1/3 and distinct recent source classes can receive up to 2/3.
None of these numbers estimates a probability of market growth or purchase.
No extra API calls, credential access, background polling or cache reset is
required to produce the new diagnostics. Title overlap remains lexical
and does not substantiate a matching buyer or the same work process.

### Keyless GitHub CI rate limits are external availability, not market inactivity

On the Nov 19 source-contract smoke, GitHub issue search returned HTTP 403
from an unauthenticated shared GitHub Actions runner IP while the other
public data providers returned their normal records. The behavior is a
provider-access limitation, not proof that Github has no issues or that
the hunter failed to match market signals. GitHub documents that
unauthenticated REST calls are rate-limited by originating IP and that
HTTP 403/429 may indicate rate limiting:
https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api

The public-provider smoke now checks GitHub issue search as an **optional
availability probe**, along with Lever, and records failure statuses without
marking them as observed, verified or a passing contract. Core GitHub
JSON projection and issue-quality rules retain deterministic unit regressions.
Production hunting continues to label an unavailable GitHub source as
degraded coverage. We never retry keyless 403/429 in a tight loop or invent
zero activity. Authenticated local testing with an authorized read-only
token can be a separate follow-up once the existing tunnel reconnects.

## Seedless current-theme discovery (no preset business niches)

Run `mcp-trendpulse-cli intelligence discover --execute --format text` for
a source-led watchlist that does **not** begin with the rotating 18-topic
menu. Offline planning without `--execute` makes **zero network requests**.
The corresponding `intelligence_discover_current` MCP tool is isolated and
read-only; it is intentionally absent from the normal 16-tool community MCP.

The three bounded free-provider origins are:

- OpenAlex works with `from_publication_date`, sorted by publication date,
  including their **provider-assigned `primary_topic`** classification. This
  uses free publication-date filtering (never premium created/updated sync).
- CFPB's public consumer complaint categories, including *product* and
  *issue*, using receipt dates and public complaint IDs. It never includes
  personal complaint narratives or company-contact records.
- TED published EU procurement notices, filtered by a bounded published-date
  expert-query window. Notices are buying-related public evidence, but are
  **not proof of an award** or of vendor spending.

The collector accepts 2–20 sample rows per provider (default 12), a 7–90
day window (default 30), fixed HTTPS origins, the existing free-only API
budgets/cache, and no automatic retry. It uses an OpenAlex API token from
Windows Credential Manager only if already configured, without exposing it
to the MCP arguments, PR or CLI output. No new EPO registration is needed.

The offline normalizer validates source IDs and public event dates, strips
nonapproved source payload fields, and groups independently identified
records. **Two or more distinct source records** with the same source
category (CFPB product+issue or OpenAlex assigned primary topic) create a
single-source research theme. Exact distinctive phrases shared between
multiple provider title/category records yield a **cross-source follow-up**.
Both are explicitly *observed current topics in a bounded sample*, not
population trends, growth forecasts or buyer-level commercial validation.
A lone publication is shown as a source observation, not a "winning" trend.

The output includes original provider references, dates and origin-class
semantics; missing API access is explicitly inconclusive. When no candidates
qualify, the watchlist still shows sample recent publications/complaints/
tenders, instead of manufacturing a positive finding. `--record-history`
optionally saves only hashed candidate IDs, source counts and sample sizes
for 90 days locally; it does not store raw record titles, personal info,
tokens, narratives or URLs. It is never scheduled automatically.

OpenAlex free fields/filter/sort guidance:
https://help.openalex.org/api/filtering/
https://help.openalex.org/api/sorting/
https://help.openalex.org/data/works/attributes/
CFPB public category documentation:
https://cfpb.github.io/api/ccdb/fields.html
TED search documentation:
https://docs.ted.europa.eu/api/latest/search.html

### Real discovery feedback: financial complaint skew and missing TED titles

On 2026-11-19 the user's seedless `--limit 20` local output showed 20 CFPB
complaints and three repeated consumer-finance categories, but only 10 TED
and 10 OpenAlex observations and a **blank** TED notice title. These are
pipeline defects/selection biases, not an absence of procurement or emerging
research topics:

- TED's `notice-title` and `buyer-name` fields are multilingual mappings
  of language codes to strings/arrays. Reading a mapping as a plain string
  deleted every notice title. The source-safe parser now prefers published
  English, then official-language text, then a deterministic available
  language fallback. It records the selected language, extracts published
  contracting authority names and notice type, and links to the exact
  published notice **only when** its number matches TED's documented format.
  A notice with no usable title is not counted as an actionable lead.
- The evidence projection quietly truncated otherwise valid TED/OpenAlex
  samples at 10 even for `--limit 20`. These two bounded sources now
  project up to 20 rows (the network response and JSON normalization
  limits remain unchanged). Existing provider budgets and credentials
  remain untouched.
- Discovery's TED date query now sorts `publication-date DESC` to avoid
  giving an old, first-published item pride of place in the result window.
  It still uses only source-published dates, never inferred creation dates.
- The report preserves all repeated CFPB categories, but explicitly says
  that a *distinct public complaint ID* is **not a distinct customer/buyer**
  and a complaint does not demonstrate willingness to purchase SaaS.
  To counterbalance source skew without fabricating a cross-source trend,
  the report also lists up to four actual published EU procurement notices
  (with buyer/notice type/date/link where available) and three recent
  OpenAlex research works (with provider-classified topic labels).
  These standalone observations are **not scored as growth trends**.

These rules are covered by synthetic multilingual-map, non-English fallback,
empty-title, source attribution, notice-type interpretation and 20-row
projection regressions. The optional live discovery CI smoke reports only
source status and counts of usable procurement/research examples, no raw
notice text, personal complaint details or credentials.

Upstream field documentation:
https://docs.ted.europa.eu/ODS/latest/reuse/search-api.html
https://ted.europa.eu/en/help/search-browse

### Shared-runner ECB latency is an availability diagnostic

On 2026-11-19 the broad public live-contract workflow observed 15/16
mandatory source contracts but its keyless ECB CSV request timed out twice
while the new seedless OpenAlex+CFPB+TED discovery smoke observed all 3/3
providers and four usable procurement notices. ECB macroeconomic data are
not an input to the seedless discovery feature. The generic ECB request is
now a **separate, status-visible optional external-availability check**
rather than a required pass from a transient shared-CI-IP probe. A timeout
must remain `unavailable`, never `observed`; the core ECB CSV shape and
origin allowlist remain covered by deterministic tests. No paid fallback,
retry storm, new credential, production route or unattended polling is added.


### Competition-focused TED discovery (November 19 follow-up)

The public, seedless TED query now selects recent **published contract/design
competition notices** using TED's documented expert-query operator:
`notice-type IN (cn-standard cn-social cn-desg)`. This stays sector-agnostic:
it does not constrain CPV, country, industry, purchaser, or keywords. It still
uses exactly one TED request, bounded to the existing 2–20 notice limit,
date window and original budget/cache rules. The 16-tool community MCP,
hourly scheduler and other provider adapters are unchanged.

**Why:** newest-first all-notice sampling could spend most of a tiny
20-record window on results/awards and prior-information announcements,
crowding out prospective buyer-side requests. The competition-only slice
is more useful for an *investigation* watchlist, but excludes valuable
historical awards and PINs; use other existing adapters for those.
A publication is **not proof that the bid window is still open**:
deadline, amendments, cancellation and eligibility must be checked
against the original notice. Missing a repeated primary CPV in a small
non-random slice still means *insufficient sample evidence*, not no
commercial demand or procurement. CI's live source smoke now reports
rendered competition versus non-competition notice counts separately.

Expert query and official notice type definitions:
https://ted.europa.eu/en/help/search-browse
https://docs.ted.europa.eu/eforms/latest/reference/code-lists/notice-type.html

### Discovery size-contract repair for 20 records per source (2026-11-19)

The collector enforces a **256-KiB maximum HTTP response per provider** and
at most 20 observations. The downstream seedless summarizer previously
serialized and checked all three verbose, provider-shaped sample envelopes
against one 180-KB total cap *before* normalization. With `--limit 20`,
unused OpenAlex/TED metadata could trip `Discovery snapshots exceed 180 KB`
even when every provider was otherwise healthy.

Discovery now separates two strict safeguards: (1) raw input must remain
within **three bounded provider responses plus 32 KiB of envelope overhead**
(`3 * 256 KiB + 32 KiB`), and (2) **normalized evidence alone** must fit
the unchanged **180-KB** cap. Only validated IDs, dates, source-backed
titles, topical categories and narrowly scoped buyer/CPV metadata reach the
candidate output. No raw consumer narratives, author lists, upstream
provider extras, free keys or raw URLs are saved in discovery history.
There is no additional network request, per-provider quota increase or
production configuration change.

A deterministic 20+20+20-record regression has deliberately bulky
irrelevant source metadata (over 180 KB in total), verifies all 60
eligible records remain attributable, and tests that the sensitive filler
is excluded. A separate oversized-input test still enforces rejection.
The live discovery workflow now exercises `--limit 20` and remains
explicitly inconclusive when an external provider is unavailable. Its
source-status counters distinguish provider failures from analysis defects.

### Distinguish published buyer-side tenders from topic recurrence (November 19)

The owner's first fully working 20/20/20 run produced five repeated-theme
candidates, none corroborated across independent sources. Two came from
OpenAlex's algorithmic research topics, three from CFPB public complaint
categories. It also surfaced a specific TED digital-services procedure:
notice `804742-2026` for a Greek national employment policy portal, with
a published estimated procedure amount of EUR 10,588,350 and a published
lot deadline date of 2026-12-21. The full procedure includes non-software
communication/publicity work. This is **one buyer-side research lead**, not
evidence of a repeatable SaaS market or a software-only budget.

Discovery now returns `procurement_review` alongside the original
`candidates`. The review count includes only **recent TED contract-notice
records** with a published buyer-name label, published procedure-level
primary 8-digit CPV, validated notice-specific TED URL and at least one
published lot date **on or after** the report's analysis date. These
fields make a notice inspectable but do **not** establish current opening,
legal identity of a buyer, bid eligibility, contract award, spending,
or product-market fit. Notice amendments and cancellations must be checked
in the original TED notice and primary tender documentation.

The display is still sector-agnostic at the query level. From the
already fetched 20 TED records, it selects up to **two main CPV 48/72
software/IT-class notices** and **four notices from other CPV families**,
filling unused review slots by publication recency. This is an explicit
**review visibility mix**, not an estimate of market attractiveness,
software-related spending share or bidder probability. Up to two more
additional recent notice examples remain visible. Unverified estimated values
are never used to rank between currencies or infer a single software
budget. Other published CPVs are listed to expose possible mixed scope.
The `buyer_side_review_qualified` field says whether a displayed notice
meets the source-completeness criteria; `buyer_side_review_selected`
says whether it occupies one of the six prioritized review slots.
Qualified notices shown as additional context are not mislabeled as
unqualified. The ordinary `candidate_count` and all existing research qualification
logic remain unchanged; review notices are **not counted as market
trends**. An offline fixture with 20 TED observations and the official
notice stages tests this independently of live provider availability.

TED official CPV vocabulary:
https://docs.ted.europa.eu/eforms/latest/reference/code-lists/cpv.html
TED notice status and amendment guidance:
https://ted.europa.eu/en/help/search-browse
CFPB complaint sampling limitations:
https://www.consumerfinance.gov/data-research/consumer-complaints/

### Traceable context-only source matches (2026-11-20)

Owner's next Windows run on `fed3f923` proved the six-source path
actually executed: CORDIS returned two sampled rows and two literal
title overlaps, USAspending three sampled rows and two title overlaps;
both reported **zero recent dated evidence rows**. This is not a
provider outage and not independent confirmation of rising demand:
the current hunter intentionally classifies CORDIS funded project
metadata as **undated project context**, and the USAspending
`Last Modified Date` as a **record edit timestamp**, not a new
award or purchasing event. The contextual rows already exist in
the hunter's `context_examples`, but the auto-hunt wrapper previously
read only the `evidence` (recent-only) list and silently dropped
all original context titles, URLs and exclusion reasons. This
made "2 title matches" practically unauditable.

The auto-hunt output now carries at most four bounded
`source_context_examples` **per selected topic** from the
existing contextual evidence, keeping source, sanitized title,
comparable event date when available, and exactly the hunter's
original exclusion reason (`timestamp_not_comparable_recent_market_event`,
`publication_date_unavailable`, `outside_requested_lookback`,
`not_recent_activity`). It labels the entire section
**CONTEXT-ONLY SOURCE RECORDS** and does not change the
`recent_dated_matches_in_sample` value or count context as
recent or independently validated demand.

CORDIS EURIO `eurio:identifier` supplies an official project
identifier; when it is strictly numeric and within bounds, the
observation layer links to the corresponding official
`https://cordis.europa.eu/project/id/{id}` fact sheet (no new
HTTP request). No project URL is invented for nonnumeric IDs.
The existing USAspending "Award ID" is not sufficient to infer
the site's internal award URL identifier, so the unchanged
`https://www.usaspending.gov/search` reference is conspicuously
marked **provider search landing, NOT an exact record permalink**.
Unrecognized external URLs are omitted, rather than accepting
arbitrary untrusted source URLs or query parameters.

These are *source provenance and report usability* changes, not
new adoption estimates, actual award-date verification, or an
additional network query. Real commercial opportunity detection
will require recent dated independent buyer/problem evidence in
comparable source populations, not these historic context matches.

### Source-attributed commercial workflow investigations (2026-11-20)

The optional `--workflow-briefs` switch uses only already normalized
OpenAlex, CFPB and TED discovery observations, with **zero additional
requests**, new providers, keys, LLM calls or predefined topic seeds.
Normal discovery behavior, 25-adapter catalog, 16-tool community MCP
and hourly agents are unchanged.

The offline candidate builder keeps at most six source-auditable briefs:
up to four published TED contract notices with **primary CPV 48/72**
(software/IT-category scope, not software-only work or an awarded
purchase), and two CFPB product/issue categories with at least **two
distinct complaint IDs** in the bounded sample. It explicitly preserves
original published notice links, published buyer-name labels, CPVs,
lot dates, paired procedure estimates (not spending), complaint-provider
landing links (not individual complaint permalinks), evidence dates,
unverified buyer identity and unanswered product-qualification work.
Forward-looking procurement briefs require published buyer labels and
valid lot dates **on/after the analysis date**. Past/missing lot dates
or missing buyer labels are separated into bounded original-notice-linked
**historical/incomplete context** and cannot consume an automated
source-check query slot. A future published lot date is NOT verification
that a bid is still open, unamended, eligible or a software-only budget.
The output does not assert a recurring software product from one tender.

For each brief, research publication context is attached only when the
published OpenAlex primary-topic wording and its source label share a
contiguous **two-to-four word** meaningful phrase. With `--measure-trends`,
already measured rising research watchlist topics can be attached via
the same strict phrase gate, using official OpenAlex topic IDs. A CFPB
category can be attached to a TED notice only as **lexical** operational
problem context. Mere word overlap, research interest and published
tenders cannot prove the same workflow, adoption, paying customers,
independent purchasing organizations, market size or SEO growth.

A second, independently opt-in `--workflow-cross-check` mode
requires `--workflow-briefs`. It derives up to **two distinct plain
multiword source phrases** from actual TED/CFPB workflow clues. Original
CFPB issue-detail wording takes precedence over broad product categories
(e.g. exact published tokens 'incorrect information' or 'collect debt'),
followed by a future-lot-date TED title only if it yields a safe,
source-derived multiword phrase. Non-ASCII-only / single-word / generic
tender titles stay available for manual review, without replacing them
with a past-lot-date vendor-specific licensing notice. If no TED phrase
qualifies, a second original CFPB issue can be investigated instead. No academic topic name is substituted and no synonyms or fixed
sector seed lists are invented. It reuses existing GitHub Issues and
USAspending collectors, local shared cache, quality screen, source
budget and cooldown; **at most four extra free queries** (2 phrases
x 2 providers). An observed zero matching title is different from
provider unavailability. GitHub issues are not paying customers; US
awards' last-modified timestamps cannot become new purchasing events,
and the USAspending landing page is not a record-specific permalink.
Independent source records require explicit workflow and buyer checks
before any product validation claim. The report shows accepted sample sizes
and explicitly distinguishes **all providers observed with zero matching
titles** from partial/unavailable provider coverage. Neither means zero
market demand. No unattended work or new provider.

The seedless discovery smoke additionally executes the opt-in brief
projection with the existing three keyless collector responses, checks
that every reported opportunity remains explicitly unverified, and saves
only provider status and aggregate brief counts to the CI artifact.

A report with zero qualifying briefs means the small capped sample
contained no qualifying observed workflows, NOT that none exist in the
market. Research topics without documented lexical connections remain
unlinked rather than receiving invented synonyms. Output is capped,
read-only, not recorded as raw source history, and preserves provider
reference whitelists. The workflow briefs are explicitly about follow-up
investigations, not validated product ideas.

Example, after installing the latest draft commit:

```powershell
$env:UV_LINK_MODE = "copy"
uvx --from "git+https://github.com/AKzar1el/mcp-trendpulse.git@<tested-commit>" mcp-trendpulse-cli intelligence discover --execute --workflow-briefs --workflow-cross-check --ted-date-slices 3 --limit 20 --lookback-days 30 --format text
```

### Targeted software/IT TED coverage, separate from unbiased discovery (2026-11-20)

Field tests of the three newest-first 30-day TED windows show that a 20-notice
sector-neutral sample may contain software/IT notices in one run and none
in the next. The later 0/20 sample is **not evidence that the software
market disappeared**: the window pages are capped and not representative.
This cannot be fixed by pretending missing records were re-observed.

The opt-in `--ted-software-scan` adds **one** existing keyless official
TED search using `classification-cpv=48*` or `72*` and source-published
contract notice types in the same lookback. The query is bounded to
12 returned notices and processed with the exact same source, date,
buyer, deadline and **primary-CPV** gates. Secondary-only IT-class
CPVs never automatically become primary IT software products.
Qualified official links may supply up to four independent software
briefs, deduplicated with neutral-source briefs within the existing
**six-total/four-procurement** cap. The neutral sampling counts and
trend directions are not mutated; focused evidence is explicitly
marked with a different sampling population.

The focused scan runs only with `--workflow-briefs --execute`.
It is **not** a rotating hardcoded niche/topic list; CPV classes
are explicit procurement categories. Its coverage is still
newest-page limited; no accumulated opportunity history or guarantee
that previously observed tenders appear again. TED date/published
deadline statuses and documents require source revalidation.

The November 20 field test returned **12/12 items from October 22**
despite the 30-day period, because the focused expert query did not
explicitly sort. The updated query uses TED's officially documented
`PC` alias for `classification-cpv` and appends
`SORT BY publication-date DESC` while retaining the 30-day date
bounds, competition notice types and two software/IT CPV branches
inside the source builder's 140-character safety limit. The provider's
returned page is audited for publication order and date span;
a sort clause does not prove the first page is exhaustive or that the
tender remains open.

The previous Idea Map recognized only DEU and GRC buyer codes and
displayed **unknown** for CHE, EST, HUN and LTU. It now uses a bounded
explicit ISO-3166 alpha-3 to alpha-2 map for European country codes,
including CHE→CH, EST→EE, HUN→HU and LTU→LT. Unknown codes remain
unknown rather than silently defaulting to a geography. Buyer location
is source context, not evidence of local keyword popularity.

The same field test showed zero same-procedure notice matches even
for source-exact scope notices. TED can project publication dates as
ISO dates with an offset or timestamp, which the previous ten-character-
only parser rejected. Related-notice screening now accepts strictly
anchored official date or timestamp shapes (still excluding future and
malformed dates) and reports safe counts of returned, unmatched-UUID
and invalid-dated rows. This improves diagnosis without claiming any
amendment exists unless a validated same-procedure notice is found.
Subsequent opt-in TED scope, same-procedure checks and Idea Map
can operate on the newly found focused briefs.

### Same-procedure TED notices and amendment awareness (2026-11-20)

With `--workflow-briefs --ted-scope-details --ted-related-notices`,
TrendPulse preserves the validated **published procedure identifier UUIDv4**
from a source-exact TED notice scope response, then makes at most one
extra keyless official TED Search API request per shortlisted procurement
(max **two additional requests**). Query terms are an exact, source-
published `procedure-identifier`, never fuzzy title/organisation matches.
The response is validated again against the original identifier; only
bounded dated official publication-number references are returned.

When the same procedure has a newer published notice, the Idea Map marks
the prior scope as needing revalidation. It does **not** assume that a
same-procedure notice supersedes the previous version, changes a
specific lot, cancels a competition, constitutes an award or confirms
that a deadline is still active. Competition, change and result notice
types are shown as published; a definitive amendment relationship
requires the appropriate explicit change notice reference and reading
the original official documents. The query is opt-in, cached under
existing TED free-only daily caps, and never scheduled automatically.
A missing/multivalued/unverified procedure UUID results in zero added
requests rather than a guessed join.

### Explicit bounded related-query investigation (2026-11-20)

With `--workflow-briefs --idea-map --keyword-probe --execute`, the
Idea Map selects at most **one published-source procurement phrase and
one original CFPB problem term** with an applicable source-market ISO
country. It checks Google Trends related **Top** and **Rising** searches
using the **existing unofficial community TrendsPy provider**. This is
not Google's limited-access official Trends API. It is fully opt-in,
has no new packages/providers or background polling, and uses the
existing provider pacing and cooldown system.

A separate shared local SQLite guard permits **two related-query
provider operations per UTC day** for this feature. A typed
`DailyBudgetExceeded` error reports the actual UTC day and already
reserved operation count, while a missing/locked/unwritable SQLite
cache reports `local_budget_store_unavailable`. Neither condition
causes an unbudgeted provider retry or resets the quota. If a previous
provider attempt exhausted the allowance, a repeat within the same UTC
day cannot automatically retry until the next UTC day or cache reuse.
Successful responses have safe cached
results (6-hour TTL) so a repeated run normally does not re-query the
provider. A provider-level operation may make multiple HTTP requests;
the code **does not** claim a two-HTTP-request guarantee or count the
community MCP server's unrelated requests against this quota.
Provider 429, unavailable, malformed responses and daily quota exhaustion
remain distinct from an observed empty related-query result. Original
source-derived keywords are not considered real observed searches until
the provider returns those or related terms.

The output retains the original source market; rising query values
represent **provider-reported % growth or Breakout**, while Top scores
are relative interest values. Neither is absolute monthly keyword volume,
CPC, SEO difficulty, customer demand, TAM, product-market fit or
willingness to pay. Never compare these values across countries/terms
without a valid shared normalization.

The no-network preview `--idea-map --keyword-probe` requires
`--workflow-briefs`. Actual requests require explicit `--execute`.
If rate-limited or blocked, prefer the offline `--idea-map` and
manually supplied normalized series over repeated retries.

### Availability-aware Idea Map and focused TED evidence (2026-11-20)

A field run with `uvx` successfully installed 111 packages after
a Windows PyYAML cache cleanup failed on an in-use `.pyd` file.
TrendPulse then ran, but all three baseline TED date windows and the
CPV-filtered focused scan were unavailable due to the shared
**20/20 consumed local TED UTC-day request cap**.

The focused scan previously printed "No eligible ... notices" and
recorded a performed request even when local admission rejected the
query before network I/O. It now detects the typed local cap, reports
zero HTTP requests performed, preserves the safe UTC-day used/cap,
and states **eligibility unknown** on unavailable/error responses.
An observed empty sample remains distinct from an unavailable sample.

The history previously called all prior leads "NOT present in current
sample", including public TED records that were not queried because
the daily allowance had been exhausted. Historical source entries
are now labelled according to source availability: source unavailable
means **current presence unknown**; a retrieved source that did not
make the bounded top Idea Map means **not selected**, not disappeared.
The CLI passes the observed/unavailable source coverage and focused
scan status into history when recording. This does not overwrite prior
entries, invent observations, query more sources or assert a current
tender is open. The legacy history JSON key remains for compatibility,
with a clearer `prior_history_not_selected_in_current_idea_map` alias.

### TED missing-window diagnostics, without unsafe retries (2026-11-20)

A field run on November 20 had **2/3 TED date windows observed**, with
the oldest date window unavailable; the snapshot alone could not show
whether TED had rate-limited the request or the local 20/day budget
had been exhausted. Existing collection correctly treats this as
partial, not zero-source market activity, but stripped the failure
reason before the report.

The TED three-window diagnostics now preserve **only fixed, explicitly
allowlisted reason codes, HTTP status and typed local UTC-day quota
counters**. A real `DailyBudgetExceeded` prints the UTC date,
used/cap limit and that no bypass is attempted. A cooldown, HTTP 429,
storage error or malformed source shape remains distinct and cannot
leak response bodies, provider error strings or credentials. This
change adds **no** API calls or retries, never resets a provider
allowance, does not fill missing windows with fabricated zeros, and
does not merge the separate focused CPV data into the neutral sample.
The status remains unknown until a subsequent permissible source
observation returns valid rows.

### Persistent opportunity source sightings (explicit opt-in, 2026-11-20)

`--record-idea-history` requires `--idea-map --execute` and adds
**zero** source requests. It stores a 90-day, source-safe local SQLite
ledger at `~/.mcp-trendpulse/intelligence/opportunity_history.sqlite3`
by default, distinct from the preexisting hashed research-candidate
history. Only source-validated TED publication URLs, source-published
short notice labels, CFPB public product/issue categories and the
tentative procurement-fit screen are saved. No raw TED payload,
CFPB narratives, complaint IDs, private provider responses or API
credentials are persisted by this feature.

The stable key is SHA-256 over the TED notice URL or the exact published
CFPB category, so repeated invocations on the same date count as
**one observation day**, not a growth measurement. The report explicitly
counts previously recorded same-day sightings; a repeat producing
`0 new` is normal idempotency, not a collection failure. Results distinguish
currently observed source items from up to five older entries
**not present in the current bounded sample**. Older entries require
fresh original-source validation before being treated as a current
bid, viable buyer workflow or keyword opportunity. History provides
continuity of investigation, not a market-growth trajectory, buyer
count, active bid guarantee, reopening of expired tenders or a
sampling correction. It does not inject unseen historical leads back
into the live Idea Map or schedule background polling.

### Procurement-fit screening for candidate product ideas (2026-11-20)

The live newest-first focused software/IT TED search recovered four
notices from November 19 (Slovenian software-license renewal, Lithuanian
electronic messaging repository maintenance, Lithuanian graphics server
purchase, and Polish software license delivery). **These are procurement
leads, not automatically greenfield product opportunities.** The earlier
Idea Map had assigned the same "prototype a small component" direction
to all of them, which could mislead a product entrepreneur.

The Idea Map now uses a **no-network, conservatively source-lexical
contract-type screen**. It reads only the source-published original-language
notice title, the optional bounded TED procedure/lot excerpts, and the
source-published **primary CPV**. It recognizes a *limited* set of
literal original-language license, renewal, maintenance, hardware,
development and support terms (including the terms observed in the
live Slovenian, Lithuanian, Polish, Hungarian and Estonian notices).
Missing or ambiguous source evidence remains **unclassified**, not
"new SaaS verified". It labels:
- license or entitlement purchase;
- hardware or equipment purchase;
- maintenance/support service;
- mixed development and support;
- custom development/implementation; or
- unclassified software/IT procurement.

Each report states matched lexical categories, the source CPV,
the classification's tentative status, and a concrete next research
question appropriate to the procurement type. Commodity purchases
are retained as evidence but are **not promoted** to validated
standalone software product ideas. No buyer willingness, competitor
gap, recurring workflow, customer identity, original specifications
or market-growth claim is established by these screens.
No new source requests, provider libraries, secrets or background jobs
are required.

### Integrated project-idea and SEO keyword investigation map (2026-11-20)

The opt-in `--idea-map` switch requires `--workflow-briefs`, and
synthesizes **bounded, explicitly unverified product hypotheses** from
the same source-backed TED procurement and CFPB consumer-problem
investigations. When `--ted-scope-details` is also set, the published
procedure and unassigned lot excerpts inform project scope. Optional
`--measure-trends` still measures **OpenAlex publication momentum**,
not Google keyword interest or search traffic. No new provider is
queried by `--idea-map`, no automatic polling is enabled, no LLM
generates untraceable industry ideas, and no scheduled fleet is modified.

Each item has its source reference, origin geography and target-buyer
hypothesis, tentative minimal software direction, available scope,
and validation gaps for **repeat buyers, incumbents, budget,
product-market fit and monetization**. Keyword candidates use only
original published source words (or a visibly labeled combination
of published consumer product/issue categories) in the source
language. They are **not** known search queries, Google search volumes,
CPC or SEO difficulty. An original German/Greek term is not silently
translated into English and its source geography is not proof that
Google searches are occurring in that country.

An optional `--keyword-evidence-file` (<=64 KiB) accepts exactly the
existing Trend Watch JSON contract: one `keyword`, one two-letter
uppercase `market`, and a dated `points` series containing 0–100
normalized, complete trend observations. It uses Trend Watch's existing
offline validation and freshness/cadence checks. Results attach only
when the term **and country** exactly match a proposed keyword. The
series is operator-supplied and provider provenance is **not**
independently verified; normalized Google Trends interest is not
absolute keyword search volume and cannot by itself establish a paid
software market. A missing or stale series stays inconclusive rather
than being imputed. There is no Google Trends scraping or alpha-only
API dependency. Google's public Trends API remains restricted to
accepted alpha participants.

Example combined read-only run:

```powershell
$env:UV_LINK_MODE = "copy"
uvx --from "git+https://github.com/AKzar1el/mcp-trendpulse.git@<tested-commit>" mcp-trendpulse-cli intelligence discover --execute --workflow-briefs --ted-scope-details --idea-map --ted-date-slices 3 --lookback-days 30 --limit 20 --format text
```

After reviewing candidate terms in Google Trends Explore for
the appropriate language and country, an operator may supply a
normalized series via `--keyword-evidence-file .\source-series.json`.
Google Search Console gives **site-specific** impressions/clicks,
not market-wide keyword demand. Do not apply keyword-volume, click
or conversion estimates without corresponding direct measurements.

### Opt-in source-published procurement scope excerpts (2026-11-20)

The user field test found two forward-lot-date TED IT/software leads but
neither could safely yield an original two-word phrase for GitHub/USAspending
follow-up. The publication titles hid the actual implementation scopes:
German `Finanzsoftware` relates to an integrated finance/budget plus
building/property management (CAFM) implementation; the Greek employment
digital portal tender contains a separate communications/publicity lot.
A generic original title, broad CPV or overall procedure estimate does
not identify a product niche, lot budget or active bid.

Use the **optional** `--ted-scope-details` flag with `--workflow-briefs`
to inspect up to two official TED publication numbers selected from the
source-backed future-lot-date briefs. Every request is built through the
existing TED adapter with a strict `publication-number = NNNNNN-YYYY`
query, `limit=1`, and adds only official `description-proc`,
`title-lot`, and `description-lot` projection fields. These fields
are documented by the TED Search API; the option consumes **at most
two additional free source requests**, uses the existing UTC-day cap,
cache, no-redirect policy, timeout and 256-KiB per-request limit,
and does not add any provider or automated task.

The result includes up to one procedure description and two source
excerpts each for lot titles and lot descriptions. The text is short,
control/URL/email sanitized, and original-language only. TED Search
projections can flatten multiple lots and languages. The module
**never assigns** a specific description to a lot identifier, budget,
deadline, buyer or award; corresponding official documents remain
necessary before any product concept, bidder eligibility or financial
opportunity can be confirmed. If notice ID verification fails or the
provider is unavailable, the output clearly shows that status without
exposing raw provider content, secrets or redirect URLs. No method
estimates market demand, sales opportunity or keyword search volume.

Example focused field test:

```powershell
$env:UV_LINK_MODE = "copy"
uvx --from "git+https://github.com/AKzar1el/mcp-trendpulse.git@<tested-commit>" mcp-trendpulse-cli intelligence discover --execute --workflow-briefs --ted-scope-details --ted-date-slices 3 --lookback-days 30 --limit 20 --format text
```

### Source availability diagnosis without unsafe error disclosure (2026-11-20)

The complete owner field test returned one exploratory research watchlist
topic, while CORDIS reported unavailable/incomplete and USAspending returned
zero bounded matches. The previous source-follow-up wrapper dropped the
already-sanctioned provider error metadata from its report, making it
impossible to distinguish a timeout, HTTP failure or local cooldown from
an intentionally empty observed sample.

The opt-in cross-source output now preserves only the hunter's normalized
status, valid numeric HTTP status or a strictly allowlisted exception type.
Unknown upstream error text, response bodies and credential-bearing strings
are never copied into user-facing output. The original provider budget,
cache, requests, research classification and candidate ranking are unchanged.
A failed or incomplete source is NOT evidence of zero underlying demand.
The observed CORDIS failure's exact cause remains unverified until a fresh
safe diagnostic is available.

### Independent follow-up must not depend on promotion to the growth watchlist (2026-11-20)

The owner's first Windows run with both
`--corroborate-issues --cross-source-hunt` showed that **both
optional sources were skipped**, although all three baseline sources
returned observed samples. The cause was the strict eligibility gate:
the research `idea_watchlist` was empty, despite a recent XAI
source-count trajectory of **407 → 470 → 503 works**, normalized
**639.106 → 657.282 → 808.180 per million** (two consecutive
increases, +26.5% oldest-to-recent). This did **not** meet the
conservative first-interval 1.03× threshold for
`early_rising_research_watchlist`; the first gain was ~1.028×.
**Advanced Numerical Methods** **185 → 189 → 191** works, but
normalized **290.503 → 264.311 → 306.884** *declined and then
rebounded*, so it should not be treated as an emerging trend
or an automatically corroborated monotonic follow-up.

The original code used ONLY the **promoted idea watchlist** as
the input for both opt-in corroboration features. This conflated
`not enough evidence to assert rising` with `nothing worth
investigating` and silently disabled cross-provider research.

A new pure source-selection step now **preserves** the original
research direction, main product-idea watchlist, classification
thresholds, volatility flags and source budgets. It first selects
actual rising watchlist topics; if there are fewer than two,
it *only* fills remaining slots from **already source-counted**
`inconclusive` or approximately stable research topics with:
- three valid mature-period topic counts and corpus denominators;
- at least eight topic works in each period, with both normalized
  comparisons nondeclining;
- latest share up at least 8%, total share at least 10%;
- **no** indexing, publication-spike or reversal quality flag.

These candidates appear as
`exploratory_monotonic_below_trend_threshold`, not as rising
product opportunities. They are explicitly labeled for
**source follow-up only** in output JSON/text and in the GitHub
and CORDIS/USAspending corroboration sections, including their
original `inconclusive` research direction. Any missing counts,
unstable research direction, reversed period, or absent measured
topics continue to produce **zero** source follow-up calls.
Neither a title/phrase match nor issue count is treated as
independent customers, comparable market growth or SEO demand.
The full max remains **4 GitHub + 4 CORDIS/USAspending** additional
source calls, using the existing source-specific free quotas.

The narrow purpose is to test emerging or near-emerging ideas
with **other evidence sources**, without rewriting the original
trend detector to manufacture confidence.

### Separate intelligence MCP now exposes the same opt-in discovery modes

The original twelve-tool read-only intelligence MCP previously allowed
`intelligence_discover_current(lookback_days, limit, execute)` only:
none of the more recent CLI research flags were reachable through the
MCP client. The **existing tool** now additionally accepts optional
`measure_trends`, `broad_topic_scan`, `corroborate_issues`
and `cross_source_hunt` booleans, defaulting to `False`.
This allows agents to explicitly use the already verified OpenAlex
research measurements, bounded topic scan, GitHub public issue
counts and re-used CORDIS/USAspending hunter without adding any
new MCP tool or altering the original sixteen-tool community
MCP. Each flag remains opt-in and requires `execute=True`
to access the network. Test coverage verifies the complete
FastMCP JSON schema and plan-only zero-network 29-request
upper bound for all four flags with a single TED window.

### Source inventory audit and optional cross-source research follow-up

There are **25 source adapters** across the existing intelligence
foundation/commercial/specialized/extended modules, but **the seedless
`intelligence discover` baseline intentionally fetches only three:
OpenAlex, CFPB and TED**. `--corroborate-issues` separately uses
GitHub issue search counts. The repository also exposes an
**eight-source current-activity hunter**, whose default source
selection is GitHub issues + OpenAlex + CORDIS + USAspending, and
**18 separate offline opportunity evaluation lanes**. The 18 lanes
are *recipes*, not 18 automatically executed API integrations.
Other adapters require country/time-series identifiers, known
company/hiring board slugs, free registered credentials, or
self-hosted RSSHub/changedetection. Querying all 25 indiscriminately
is not a scientifically comparable market-wide trend scan.

To reuse other already implemented datasets with **no manually entered
topic seeds**, add a deliberately separate opt-in
`--cross-source-hunt` (requires `--measure-trends`).
For at most two **auto-measured source-derived research watchlist
topics** from OpenAlex, it invokes the unchanged existing
`intelligence_hunter.hunt_current` with exactly the already
supported **`cordis`** and **`usaspending`** adapters. The
former searches published EU funded project **titles** (SPARQL EURIO);
the latter searches US federal award descriptions under a
bounded public procurement query. These are *contextual corroboration
examples*, not a count of independent buyers, topic demand growth,
adoption or changes in keyword searches. The hunter explicitly
screens source relevance and recency; empty/unavailable results
never imply no demand. Topic labels are derived from already measured
research; if none are usable, no rotating built-in seed topics or
implicit requests are substituted. No newly invented provider,
crawler or user account is required.

The opt-in contribution is **up to four extra free requests**
(two dynamic topics × CORDIS + USAspending), under their existing
source quotas and safe origins, caching, no-redirect limits and
provider failure states. The full explicit maximum with three TED
date windows, OpenAlex broad scan, issue text corroboration and
cross-source hunter is **31 requests** (5 baseline + 9 topic
counts + 9 broad + 4 GitHub issue counts + 4 other source requests).
The OpenAlex portion remains capped at 19 of its locally
budgeted 20/day keyless calls; other sources use independent
provider caps. Plan-only mode never uses the network.

Reports now explicitly state **28 adapters catalogued** (including the opt-in
Crossref bibliographic-context adapter) versus the
three baseline queried sources and include a separate
`ADDITIONAL EXISTING SOURCES` section when this option is used.
No claim of automatic full 25-source coverage is ever made.
The production community MCP, scheduled agents, default
`intelligence discover` behavior and paid-data restrictions are
unchanged.

Example, deliberately avoiding repeated broad OpenAlex queries:

```powershell
mcp-trendpulse-cli intelligence discover --execute --measure-trends --corroborate-issues --cross-source-hunt --lookback-days 30 --limit 20 --format text
```

Original reference APIs:
https://cordis.europa.eu/about/sparql
https://api.usaspending.gov/docs/endpoints
https://docs.github.com/en/rest/search/search

### Independent GitHub issue-text corroboration for product-idea research (2026-11-19)

The owner's latest `95a2c88` local Windows run verified that
OpenAlex XAI research momentum survives the quality gate, while
the two abrupt topic spikes remain only in the audit section.
That completes the narrow *source-count trend* validation milestone.
A rising research topic, however, does **not** establish developers
have a problem, buyers need a product, or keyword traffic is rising.

An additional strictly **opt-in** `--corroborate-issues` flag (requires
`--measure-trends`) reuses the **existing free/no-key GitHub issues**
source rather than introducing an external integration. For up to
**two automatically selected provider-topic labels from the measured
research watchlist**, it searches the exact safe plain-language phrase
in the titles/bodies of GitHub issues *created* during the **two most
recent mature completed windows**, including both open and closed
issues. Parenthetical abbreviations are discarded to avoid
accidentally requiring them; no synonyms are invented. Every exact
GitHub search is independently inspectable from the provided public
search link. It requests `per_page=1` and reads only the source
`total_count` when `incomplete_results=false`.

**Privacy and rate safeguards:** The count-only search goes through
the established fixed GitHub HTTPS origin, same source daily
budget (**12/day**), cache, request coalescing, provider 429 cooldown,
response size cap, and no-redirect settings. Up to **4 extra requests**
are only made after explicit `--execute --corroborate-issues`. A
dedicated source-plan fingerprint is matched before storing results,
and the **only** cached GitHub issue data is the aggregate
`total_count` and `incomplete_results` fields. Not even one
issue body, issue title, username, email, comment or repository
identity from a raw match is persisted by this mode. Malformed or
incomplete source results remain **unknown** rather than fabricated
zero matches; source exact-phrase searches that genuinely return
zero have the narrow meaning `no matches for this phrase/period
in this GitHub index`, not `no customer interest`.

The output is a standalone **INDEPENDENT DEVELOPER DISCUSSION
CHECK** with period-specific observed text-match counts, official
GitHub search links and prominent limits. It does not change
OpenAlex trend classification, the idea watchlist rank, buyer,
market growth, verified demand or SEO-volume flags. GitHub issue
search is a biased and potentially incomplete index, with bots,
multiple issues per person, varying phrase use and pull requests
excluded; issue mentions do not prove *problem severity* or
*product viability*. A subsequent deliberate human review of
the public issues and alternatives is needed before selecting a
product hypothesis. The SEO keyword phase is independent.

Worst-case opt-in source budgets with the full broad scan:
three default sources + nine OpenAlex historical counts +
nine OpenAlex broad/topology requests + **four GitHub issue
checks = at most 25 calls**. OpenAlex remains capped at
**19 of its existing 20/day local free budget**, GitHub at
four of its 12/day source budget. With three TED date windows,
the total maximum is 27. Plan-only invocations remain zero
network requests.

Example:

```powershell
mcp-trendpulse-cli intelligence discover --execute --measure-trends --broad-topic-scan --corroborate-issues --lookback-days 30 --limit 20 --format text
```

Official evidence:
https://docs.github.com/en/rest/search/search#search-issues-and-pull-requests
https://docs.github.com/en/search-github/searching-on-github/searching-issues-and-pull-requests

### Live ranking-gap spikes: measured counts, not sustained trends (2026-11-19)

The owner's successful `d9a5940` Windows field run captured three
top-100 OpenAlex grouped pages (**100 → 100 → 100**), with **76** topic
IDs present in all three windows and **58** unique groups missing
from one or more ranking pages. Of **24** recently ranked topics not
fully present in older rankings, the first **two** passed three
direct historical source-count queries each (0 rate/source failures).

The source-verified counts exhibited *extreme, unstable*
**decline-then-jump** patterns:
- Oral History, Memory, Narrative Analysis, T13590:
  **78 → 69 → 1078** research works, or
  **124.134 → 96.958 → 1725.013** works per million
  (overall +1,289.6% normalized share).
- Glioma Diagnosis and Treatment, T10129:
  **589 → 477 → 1161** works, or
  **937.37 → 670.278 → 1857.829** per million
  (overall +98.2% normalized share).

Those are valid *observed source counts*. They are **not**
independently verified rising product trends: both declined in
the first interval, then rebounded abruptly. OpenAlex replaced its
topic assignment classifier on **2026-10-06** and periodically revises
historical topics; API publication dates also follow metadata from
upstream publishers. These changes are credible *risks* requiring
investigation, **not proven causes of either spike**.

To avoid promoting such noise into the product-ideation shortlist,
the common three-window classifier now labels a large (>4×)
single-completed-period jump as
`abrupt_publication_spike_needs_validation`, and a material
previous-share decline (<=0.97×) followed by >=1.5× rebound as
`volatile_rebound_needs_validation`. The regular
`rising_research_share` branch now requires first-window share
not to decline, and a clean decline requires both periods to fall.
Guarded signals do **not** enter the product-idea watchlist.
A separate bounded `unconfirmed_spikes_for_source_audit`
retains up to six exact source-backed periods, normalized shares
and provider topic URLs in the output for human investigation.
No data is removed, no false-negative zero counts are inserted
and no additional API requests are made. These labels are
conservative quality heuristics, NOT statistical significance
or causal evidence.

The XAI T12026 signal (630.218 → 671.683 → 798.498 works per
million, two consecutive share increases) continues to qualify
as an exploratory early-rising research watchlist lead. For real
product ideas, corroboration with practical workflows, independent
activity and customer problems is necessary. SEO keyword-demand
research remains a separate future milestone.

Official context:
https://blog.openalex.org/same-topics-better-assignments/
https://help.openalex.org/data/works/attributes/
https://help.openalex.org/data/topics/

### Broad topic coverage and verifiable ranking-gap rescue (2026-11-19)

**Latest Windows field evidence on `57c873f`**: the opt-in
`--broad-topic-scan` succeeded and reported only **13 topic groups
present in all three ranked top-20 lists**, with **15** unique topics
omitted from at least one of the lists. None of the 13 fully matched
groups qualified as consistently rising. This is a **coverage/truncation
failure for the user's goal**, not evidence that no emerging or smaller
research-topic trends exist. Independent OpenAlex T12026 still showed
396 → 478 → 499 recent historical counts and +26.7% normalized research
share, correctly placed on the *early-rising* research watchlist.

OpenAlex's live API documentation describes `group_by` as source-
counted with pages. Its supported general `per_page` maximum is
**100** (older grouping docs mention 200). The three fixed, explicit
free grouped queries now request the **top 100 topic groups** in each
equal, completed period, instead of only 20; no additional group
requests or user seed keywords are required. **Important code-level
fix:** the shared collector's generic `_bound_payload` intentionally
truncates arbitrary lists to 20. Simply raising `per_page` would
otherwise hide groups 21–100. Only known, fixed-host
`openalex /works?group_by=primary_topic.id&per_page=100` plans now
receive a dedicated **maximum-100-group compact projection** storing
*only original topic ID, short display name, integer count and
validated meta count*; all other source response caps remain at 20.
Oversized/malformed grouped replies become source-unavailable, never
fabricated zero counts or unbounded history writes.

To avoid silently discarding promising topics absent from one or both
older **ranked** top-100 lists, the opt-in scan takes at most **two**
recently ranked, not-fully-comparable source topic IDs and checks their
actual publication counts in **all three** date periods with the same
fixed free OpenAlex count query and normalized source denominator.
A ranking absence is not interpreted as zero; a **verified API
`meta.count=0`** is allowed, as a statement about matching indexed
OpenAlex works in that period. If the API fails, counts disagree
materially with the recent grouped snapshot, or the source is
rate-limited, the follow-up remains **unavailable** rather than
becoming a rising/declining signal. Real source-counted upward-share
signals can enter the bounded research watchlist with a clear
`history_verified_by_three_direct_counts` provenance annotation.
No buyer demand, paid customer, product fit, general market growth or
SEO keyword volume is inferred.

The maximum opt-in request cost with `--ted-date-slices 3` is:
**5 normal sources + 9 existing OpenAlex historical count requests
+ 3 grouped queries + 6 targeted follow-up counts = 23 source calls**,
with a worst-case **19 OpenAlex calls** under its existing **20/day
local keyless budget**. This explicit allowance includes the initial
seedless OpenAlex work sample; existing same-request cache may save
network calls. Free provider cooldowns, same-query locks, no redirect,
no paid API tiers and all production scheduling remain unchanged.
If today's source quota is already partially consumed, counts become
unavailable, not zero; there is no quota-bypass or automatic retry.

The source type/topic classifier may be revised, and even the top-100
scan is **not exhaustive** across 4,516 topic classes. It is a
larger, economical *research trend scanner*, not yet a market or
Google search demand detector. Actual product concepts require a
subsequent, separately evidenced workflow/problem validation phase.
SEO/keyword source analysis remains a different milestone.

Official OpenAlex references:
https://help.openalex.org/api/grouping/
https://help.openalex.org/api/paging/
https://help.openalex.org/api/authentication/

### Bounded mainstream-topic landscape scan (2026-11-19)

The previous, correctly source-counted `--measure-trends` mode
investigated at most two OpenAlex topics selected from the **newest
twenty published work records**. The result could accurately detect
momentum in those two themes, but the candidate pool was too narrow
to support broader product ideation.

An additional explicit `--broad-topic-scan` opt-in (requires
`--measure-trends`) now requests **three** more free OpenAlex
`group_by=primary_topic.id&per_page=20` grouped-count pages,
one for each completed, equal-length source interval.
These queries use identical source-publication type/date filters
to the current two-topic counter and consume only three additional
requests under the **same** OpenAlex keyless free daily budget,
request coalescing/cache and fixed HTTPS origin. A base three-source
discovery with three TED date windows uses five calls, the optional
two-topic count measurement uses at most nine additional calls,
and the grouped scan adds at most three: **17 fixed requests total**,
of which at most thirteen are OpenAlex calls including the initial
seedless Works request. All require `--execute`; plan-only performs
no network requests.

Each period's group response is strictly validated for source
`meta.count`, topic IDs, original bounded labels, and nonnegative
group counts; at most 20 source groups per period enter analysis.
Only topics present in **all three top-20 lists** can have their
shares compared. An absent topic is **unknown, not zero**, because
the group may still exist outside the first 20; it can never
create a fabricated new or declining trend. Missing, malformed,
rate-limited or inaccessible windows return a clearly unavailable
comparison and no inferred growth.

The broad scan identifies the strongest *rising research-share*
signals among the common high-volume topics, with up to eight
source-backed source-topic links, period counts, and normalized
shares. It enriches the product-idea research watchlist without
inventing product-market fit, search volume, sales or a paying
customer. It is explicitly **not a comprehensive emerging-niche
scanner**: its top-20-by-volume selection still misses the
long-tail 4,516-topic universe. It makes the current workflow
more useful across mainstream research fields, and explicitly
identifies the next coverage limitation.

Example:

```powershell
mcp-trendpulse-cli intelligence discover --execute --measure-trends --broad-topic-scan --lookback-days 30 --limit 20 --ted-date-slices 3 --record-history --format text
```

Official OpenAlex field/grouping references:
https://help.openalex.org/api/grouping/
https://help.openalex.org/data/topics/

### Trend-first product-idea research watchlist, live field verification (2026-11-19)

The owner's Windows execution of `1909e0a` confirms the optional
OpenAlex `--measure-trends` mode works on live count queries. Three
completed comparable 30-day intervals (14 days of indexing lag)
measured Explainable AI (topic T12026): 396 → 478 → 499 provider works,
normalized 630.218 → 671.683 → 798.498 works per million comparable
publications. This is **approximately +26.7%** research-share movement
across the two intervals, with consistent directional gains; the
previous heuristic's `inconclusive` label understated this early
signal because it demanded unusually large consecutive jumps.
The new *early-rising research watchlist* classification requires
at least eight works in **every period**, relative share gain >=3%
then >=8%, and at least >=20% from first to last. Strong rising or
accelerating thresholds remain higher. A mirrored modest two-interval
decline becomes an *early-declining watchlist* direction. Neither is a
statistical significance claim or a forecast.

Advanced Numerical Methods (T10339) measured 181 → 190 → 187
provider works, share 288.054 → 266.987 → 299.237 per million:
approximately stable in comparison. Trend output now prints total and
latest-period percentage changes, orders rising watchlist signals
ahead of neutral topics, and marks the discovery limit explicitly:
**only up to two topics selected from the newest 20 OpenAlex works**
are being measured. The measurement is real; the candidate pool is
*not* comprehensive across industries or a broad market survey.

The opt-in report adds a **product-idea research watchlist** for
measurably rising research shares. It includes up to two
source-published recent paper titles and verifiable OpenAlex links
for each signal, plus a prompt to investigate related real-world
workflows, tools, competition and unmet user needs. These are
**idea seeds only**, not invented customer demand, competitor gaps,
paid users, adoption or keyword search volumes. Default research and
complaint-topic candidate next-steps now emphasize validating
real-world workflows and adoption, not requiring a buyer's published
procurement budget before a product idea can be considered.

**CFPB 2026 limitation:** the public CFPB CCDB service removed
complaint narratives, trend visualizations, and (in API release
1.19.0) trend/geo server functionality during August–September 2026.
Do not implement an earlier advertised CFPB Trends API merely because
historic docs still mention it. A new aggregate/count path would
require verified 2026 endpoint behavior, consistent definitions,
safe data use and bounded requests. This is distinct from the
future SEO-keyword phase, which must seek actual keyword-demand
sources besides Google Trends.

Authorities:
https://blog.openalex.org/same-topics-better-assignments/
https://help.openalex.org/api/grouping/
https://github.com/cfpb/ccdb5-api/releases
https://cfpb.github.io/api/ccdb/release-notes.html

### Real trend direction from OpenAlex source-wide dated counts (2026-11-19)

The owner's latest live `9b48087` test worked at 20/20/20
OpenAlex/CFPB/TED observations, three bounded TED date windows, 16
TED buyer-review-qualified notices, seven with a paired original
procedure amount/currency. That evidence establishes functioning
collection and conservative procurement provenance but **does not
establish whether the scientific or consumer topics are rising**.
Two works tagged with the same OpenAlex topic are not, by themselves,
a measured trend. The product's primary objective is discovering
trends, *not* generating procurement revenue leads or requiring
verified willing-to-pay buyer budgets.

Opt-in `--measure-trends` performs the **first population-counted
direction test** without requiring user-supplied topic keywords:
take up to **two** provider-assigned primary-topic IDs repeated
in the existing latest OpenAlex work sample (two distinct valid,
in-window work IDs minimum), then ask the *same* official OpenAlex
Works API for **full matching counts**, not newest-20 observations.
Compare three prior consecutive, equal-length publication periods.
For a 30-day lookback at 2026-11-19, the completed periods are
Aug 8–Sep 6, Sep 7–Oct 6, and Oct 7–Nov 5, leaving the most recent
**14 days** out of the measurement to reduce incomplete indexing.

For each of those three periods, one bounded list request retrieves
`meta.count` of all OpenAlex `article|review|book|book-chapter`
works, then one additional request per auto-discovered primary-topic
ID retrieves its `meta.count` under the **same publication-type
and date filters**. The result is transparent research-topic
**works per million comparable works**, rather than the absolute
number of works in a twenty-row sample. Up to
`3 * (1 + 2) = 9` **additional** GETs use exactly the same
`openalex` source identity, fixed host, filelock, cache, rate
budget and free/keyless credentials as normal discovery.
The other providers, community MCP tools, workers, production main
and background schedules remain unchanged. No paid sync filters,
hidden subscription fallback, search terms or external scraping.

The report shows exact period counts, normalized shares and
source-limited heuristic directions (newly observed, rising,
accelerating, approximately stable, declining, insufficient
volume or inconclusive). Thresholds intentionally prevent one
or two records from becoming a sensational signal, and a failed
source-count query leaves direction **unavailable**, never zero.
This is **OpenAlex publication share momentum**, not proof that
Google searches, customer spending, product purchases or market
growth accelerated. The recent work sample selects a topic for
measurement; it is **not** used as the denominator or a statistically
representative sample. CFPB and TED topic directions remain
**unmeasured** until equivalent complete, comparable source
counts are implemented. Topic classifiers, category assignments
and indexing change, and older counts can be revised.

OpenAlex updated the topic classifier in October 2026. The
names/IDs are provider-derived, subject to change in meaning,
and the historical-count measurement must not claim a
pre-2026 cross-classifier trend without qualification.
Official API documentation:
https://help.openalex.org/api/
https://help.openalex.org/api/filtering/
https://help.openalex.org/data/topics/
https://help.openalex.org/api/authentication/

Explicit PowerShell example with bounded free evidence:

```powershell
mcp-trendpulse-cli intelligence discover --execute --measure-trends --lookback-days 30 --limit 20 --ted-date-slices 3 --record-history --format text
```

Plan-only invocation without `--execute` performs **zero**
network calls and shows the fixed request maximum. The
normal command remains unchanged and uses three requests or
five with TED date slicing; opt-in measurement uses at most
nine additional OpenAlex requests and stays capped by existing
source-local daily quotas. Measured trends are emitted
separately from the hash-only candidate history; no raw
work IDs, buyer registration numbers, passwords or complaints
are persisted by the discovery history.

### Identity-consistency checks for repeated TED procurement leads (2026-11-19)

The owner's latest `16f32fd` field test confirmed 20/20 dated TED
records across three opt-in date windows, 13 buyer-review-qualified
notices, **four** with paired source-published procedure estimates and
**nine** without. These are early-stage procurement signals, not
independent paying-customer or product demand proof.

A further recurring-CPV data-integrity risk remains: the same public
buyer can publish separate notices with different translated or
departmental labels; a procedure can also produce more than one
publication number. Counting such notices as two independent buying
workflows can fabricate a commercial lead.

TED's official search-fields list includes source-published
`buyer-identifier` (BT-501, national registration **free text entered
by the buyer**) and `procedure-identifier` (BT-04). The existing
fixed keyless TED request now projects those two optional fields
**without making another request**. The three-date-window compact
projection preserves only capped values of these fields, and the
offline normalizer accepts only *single*, bounded, well-shaped IDs
alongside a published ISO-3 buyer country. In-memory matching uses
country-scoped SHA-256 tokens, not raw registration IDs in results or
the SQLite candidate history. Missing/multiple/placeholder IDs remain
unknown and **never silently manufacture an entity join**.

Within one exact specific primary CPV group, if **all** dated
contract notices declare the **same** country-scoped published
buyer-registration token, or all declare the same country-scoped
procedure token, the group is moved to the limited
`same_published_identity_repeats_not_candidates` evidence diagnostic
instead of being counted as multiple independent buyers. Original
TED notices and other buyer-review fields remain visible. Distinct
published registration values only support a conservative
investigation lead; they do not independently verify legal identities,
different workflows, awards, spending or current bid status.

The new TED identity provenance report counts notices with a single
usable published buyer registration and procedure identifier. A
zero count on older cached responses means the optional fields were
not present in those projections, **not** that buyers lack legally
registered identifiers. Tests cover language/dept aliases, repeated
procedure IDs, truly distinct source-published IDs, multi-buyer
ambiguity, invalid or unexpected provider shapes, and no raw ID
leakage. Default discovery still uses one TED request; opt-in
date-stratification still uses three TED calls, capped at 20 total TED
rows; the scheduled worker and production main remain unchanged.

Official TED Search Field List:
https://docs.ted.europa.eu/ODS/latest/reuse/field-list.html
Official advanced search buyer identifier note:
https://ted.europa.eu/en/help/search-browse

### Procedure-estimate evidence separated from market opportunity (2026-11-19)

The owner's latest 20/20/20 source-backed field test confirms three
disjoint TED windows and balanced 2/2/2 buyer-review examples, with the
single 48/72 software notice correctly excluded because its published
lot date (2026-11-12) was before the analysis date (2026-11-19).
The procedure was a Bavaria IBM EntireX/webMethods licence renewal,
not source evidence that an emerging software category is growing.
Later amendments and eventual award outcomes require inspecting the
official TED notice and original buyer procurement platform.

A new **published procedure estimate evidence** section is separate
from the recurring-topic `candidates` and buyer-review completeness
counts. It only includes already reviewed contract notices with an
explicit paired source-published numeric `estimated-value-proc`
and original `estimated-value-cur-proc`. Up to three such notices
are shown for manual verification; with three TED date windows it
picks one from each date bin where available, filling empty slots
newest-first. It does **not** sort by monetary magnitude, convert
currencies or claim any notice offers an addressable startup product.
One procedure may contain multiple lots and mixed software/non-
software deliverables, so a procedure-level estimate is not a
software-only budget or a vendor's attainable contract revenue.

The report now distinguishes a usable published estimate from
missing/unpaired projection data across all buyer-review-qualified
notices. Individual inspection examples carry the original tender
link, published buyer label, primary CPV, amount, currency and latest
published lot date. False claims remain explicitly rejected:
confirmed buyer budget, awards/spending, bid open-now, software-only
amount, legal buyer identity and product-market fit are unverified.
The regular capped buyer-review examples and historic candidate
hashes remain unchanged; no extra network requests, source keys,
pricing, scheduled tasks or production changes.

TED official explanation of estimate `BT-27-Procedure`: it is a
rough estimation by the contracting authority near the launch of
the competition, not an award or settled spend.
https://docs.ted.europa.eu/eforms/1.13/schema/procedure-lot-part-information.html

### Window-balanced buyer review and transparent IT notice exclusions (2026-11-19)

**Owner's real three-window field test:** all five fixed public-source
calls succeeded; TED returned 7/7, 7/7 and 6/6 notices from windows
2026-11-10–19, 2026-10-31–11-09 and 2026-10-21–30.
Twenty TED notices covered just three publication dates and all
window first-page caps were hit. Thirteen had a published buyer,
procedure primary CPV and a lot deadline on/after the analysis day.
One sampled primary CPV belonged to IT/software families 48/72,
but **zero IT records qualified for the buyer review**.

Previously the resulting six featured buyer-side notices were selected
newest-first, so older-date windows largely vanished from text output
even when older source records were safely collected and analyzed.
In the *opt-in* three-window mode only, buyer-review-qualified source
records are now selected by deterministic round-robin through the
three dated pools (up to six in total). If each window has at least
two eligible notices, all contribute two review examples. The
default single-window discovery presentation remains unchanged.
The result also reports sampled, qualified, selected and displayed
counts for every requested date window; incomplete or empty windows
are reported as unknown or zero **sample observations**, not as
zero market demand.

For source-backed IT/software primary CPV notices failing the stricter
buyer-review criteria, the result reports the exact missing evidence
in the projected public notice fields (e.g., missing lot deadline,
missing buyer label or expired *published* lot dates). It also prefers
to show one such unqualified IT notice as **context** within the
existing eight-examples cap, explicitly not as a verified active bid.
Missing field data does not prove the tender itself lacks a deadline;
the original TED notice and amendments must be inspected.
The review's published primary CPV count now reconciles exactly
to qualified plus unqualified IT notices. None of this adds calls,
claiming growth, buyers, awards or software-only budgets.

Official source context: https://docs.ted.europa.eu/api/latest/search.html
and https://docs.ted.europa.eu/eforms/latest/schema/documents-forms-and-notices.html

### Opt-in time-stratified TED notice observation (2026-11-19)

The default keyless discovery samples the **newest 20 TED notices**, which
in owner tests all came from one publication date despite a 30-day lookback.
An explicit \`--ted-date-slices 3\` flag now divides 7–90 requested days
into **three disjoint calendar-date windows**; it never runs by default
or in background schedules. With \`--limit 20\` it requests at most
**7+7+6 TED notices**, one first page in each date range, making
**five requests total** (3 TED, OpenAlex, CFPB) instead of three.
The normal provider-day limits, response-size gates, request locks,
SQLite caching, no-redirect policy and anonymous keyless TED access
remain enforced. \`--execute\` is still required for any fetch;
\`--ted-date-slices 3\` without it only prints a plan.

The three TED results are deduplicated by publication number, records
outside their requested date windows are excluded and counted, and only
a minimal bounded subset of source-published TED fields is preserved
when combining results into the unchanged **single 20-record TED
summary snapshot**. The normal two other source families are retained.
The report includes each date window, result status, sample size,
cap hits and incomplete coverage. A failed window **never** represents
zero demand or zero notices; any successful windows remain visible
with an explicit degraded-health indicator.

This is **deterministic time-stratified convenience sampling**, not a
representative sample or complete count; each partition is itself
newest-first and may truncate observations. No market-share, growth,
buyer eligibility, available tender status or purchasing outcome is
inferred from the distribution. The optional hashed discovery-history
keys are namespaced by strategy, lookback and record limit, so they
cannot silently overwrite the default-mode candidate hashes.

Example (PowerShell, after installing the draft revision):

\`\`\`
mcp-trendpulse-cli intelligence discover --execute --lookback-days 30 --limit 20 --ted-date-slices 3 --record-history --format text
\`\`\`

Official TED sources: https://ted.europa.eu/en/help/search-browse
and https://docs.ted.europa.eu/ODS/latest/reuse/search-api.html .

### Current-first TED quality audit: broad CPV and time-window bias (November 19)

The owner's subsequent local field run used 20 OpenAlex, 20 CFPB and
20 TED notices. Eighteen TED notices had a published buyer, a primary CPV,
and an on/after-as-of lot date, but **none in that sample had a 48/72
software/IT primary CPV**. The headline topic `TED CPV 45000000` referred
to one flood-protection build in Poland and a distinct fibre-infrastructure
construction project in Sweden. Their common CPV is **Construction work,
division 45**, not an independently corroborated narrow buyer workflow.

Per the official TED CPV tree, the first two significant digits are a
division; three are a group, four a class, and five or more a category or
finer. The recurrence candidate gate now requires a *shared exact
primary CPV of category-or-finer specificity* across different published
buyer labels. It retains broad-code repeats in
`coarse_cpv_repeats_not_candidates` with their exact code, hierarchy
level and counts so these legitimate observations remain inspectable,
but cannot masquerade as product demand. Even a category-or-finer
match remains an **unverified single-source investigation lead**, not
proof of a shared workflow, distinct legal buyers, spending or growth.

The report also provides a `ted_sampling_audit`: observed publication
date span, number of distinct publication dates, broad CPV division counts,
the 20-row first-page-cap flag, and number of observed primary CPV 48/72
notices. These are **sample diagnostics only**, never population shares,
market sizes or growth rates. In particular, 20 newest notices on a
single date in a requested 30-day window do not cover older dates
and cannot support an inference of zero software demand. Data absence
and provider unavailability remain explicitly distinct.

This refinement does not add a TED request, broaden source budgets,
select any new industries, change user credentials, enable polling,
alter production, or merge the opt-in PR. Synthetic fixtures check
division/group/class versus category specificity, distinct buyer
labels, contextual preservation, one-day window saturation, partial
provider availability and false market-coverage assertions.

Official source:
https://ted.europa.eu/en/simap/cpv
https://ted.europa.eu/en/help/search-browse

### TED buyer-side repeat signals, CPV and deadline integrity (2026-11-19)

The first real `intelligence discover --limit 20` run showed three repeated
CFPB complaint categories ahead of isolated TED purchases. **A complaint ID
is not a verified distinct buyer.** The new bounded TED projection requests
official procedure/lot data: `main-classification-proc`,
`classification-cpv`, `deadline-receipt-tender-date-lot`,
`buyer-country`, `estimated-value-proc`, `estimated-value-cur-proc`
(and `title-proc` as a multilingual title fallback). All remain free,
read-only, fixed-origin, subject to the same cache and provider-day budget.

For usable TED notices the output now shows published buyer country, main CPV,
last lot-deadline **date** (without inventing an open-now state), published
estimated procedure amount **and original currency**, if present. An estimate
is neither verified vendor revenue nor payment nor addressable software
budget. No currency conversion, values inferred from unrelated lot notices,
or guessed CPV labels are generated. Invalid codes, prices, currencies and
dates are omitted.

An optional recurring buyer-side candidate exists only when **at least two
recent contract-notice records** have the same exact *published primary
category-or-finer CPV* (five or more significant digits) and
**different published buyer-name labels**. Broad division/group/class CPV
repeats are shown as context only. This excludes award
notices, prior-information notices, mismatched CPV codes and multiple notices
from a buyer with the same normalized label. Two name labels are NOT two
independently verified registered legal entities. Such clusters carry a
single-source investigation priority (1/2), not evidence of rising market
volume, awarded contracts or budget execution.

Candidates sort cross-source lexical leads first, then published-buyer CPV
repeats, then research and complaints. CFPB-only repetition cannot consume
more than four of the 12 result slots. Individual procurement notices with
possible remaining lot dates appear before award/historical notice examples
regardless of whether they form a group; this is an inspection order, **not
a guarantee that the tender is still open**. A notice may need its primary
PDF/XML and procurement platform checked before any bid decision.

Official source references: TED API https://docs.ted.europa.eu/api/latest/search.html
and published field list https://docs.ted.europa.eu/ODS/latest/reuse/field-list.html .
