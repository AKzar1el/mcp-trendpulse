# Opportunity triage and temporal evaluation (optional, free-only)

The intelligence extension supports **18 evidence-combination recipes**. It is
an *investigation triage tool*, not a probability that a startup will succeed
and not a source of verified paying customers. The original 16 community MCP
tools and all scheduled agents remain unchanged.

## Exact scope and interfaces

The separate opt-in stdio MCP exposes eleven read-only tools, including:
- `intelligence_opportunity_lanes`: inspect each combination and its question;
- `intelligence_evaluate_opportunities`: evaluate caller-supplied, dated evidence;
- `intelligence_walk_forward_backtest`: grade historical triage only when later customer outcomes exist.
- `intelligence_observe_source_snapshots`: convert bounded public collector snapshots into dated evidence trails, provider coverage diagnostics and exact corporate-registry links.
- `intelligence_hunt_current`: query recent public evidence with bounded topical seeds; rank present-day research activity without requiring historic records.

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
