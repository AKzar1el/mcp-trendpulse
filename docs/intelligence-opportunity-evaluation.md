# Opportunity triage and temporal evaluation (optional, free-only)

The intelligence extension supports **12 evidence-combination recipes**. It is
an *investigation triage tool*, not a probability that a startup will succeed
and not a source of verified paying customers. The original 16 community MCP
tools and all scheduled agents remain unchanged.

## Exact scope and interfaces

The separate opt-in stdio MCP exposes nine read-only tools, including:
- `intelligence_opportunity_lanes`: inspect each combination and its question;
- `intelligence_evaluate_opportunities`: evaluate caller-supplied, dated evidence;
- `intelligence_walk_forward_backtest`: grade historical triage only when later customer outcomes exist.

CLI equivalents:

\`\`\`bash
mcp-trendpulse-cli intelligence opportunities lanes
mcp-trendpulse-cli intelligence opportunities evaluate --input-json research.json
mcp-trendpulse-cli intelligence opportunities backtest --input-json outcomes.json --k 3
\`\`\`

Default source queries remain plan-only. The evaluator never accesses a
network, visits an arbitrary website, contacts buyers, sends mail, uses an LLM
or writes to external systems.

### Twelve combinations

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

The combination recipes are **supported source types**, not verified
relationships among individual records. Eurostat macro statistics, EPO
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

\`\`\`json
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
\`\`\`

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
- **Provider failures**: rate-limited, stale, unavailable or unconfigured
  sources make the lane partial. Unavailable is not interpreted as zero demand.
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
each provider. Each row must identify source, geography, day, unit
`daily_events`, value and confirmed coverage. Sparse series, missing
days, differing units/geographies, future samples or contradictory signals
return unknown/conflicted rather than manufactured momentum. The evaluator
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
