# Free intelligence: three opt-in source waves

This module supports **opportunity discovery now and validated product development
later**. It is not an additional research-only agent, not a background scheduler,
and not a production/hosted MCP deployment.

Default behavior is offline; all network requests require explicit opt-in and
are strictly limited to approved public providers. No paid subscriptions,
commercial vendor APIs, external language-model APIs, proxies, or cloud
compute are required.

## Commands

Use the existing TrendPulse installation and Python 3.11+:

    mcp-trendpulse-cli intelligence sources
    mcp-trendpulse-cli intelligence sources --wave 2
    mcp-trendpulse-cli intelligence query --source gdelt --keyword "AI purchase approval"
    mcp-trendpulse-cli intelligence query --source greenhouse --company public-board-slug
    mcp-trendpulse-cli intelligence query --source eurostat --dataset nama_10_gdp --country SI
    mcp-trendpulse-cli intelligence query --source ecb --identifier EXR/D.USD.EUR.SP00.A

The preceding commands only print request plans. They do not contact providers.
Add the explicit flag to make one bounded request:

    mcp-trendpulse-cli intelligence query --source gleif --keyword "Example AG" --execute

Analyzing an existing public job-board export is fully offline:

    mcp-trendpulse-cli intelligence jobs-analyze --source greenhouse --company example \
      --input-json board-export.json

The job-board file must be UTF-8 JSON of at most 512 KiB. Data is not uploaded
or used for marketing outreach. It identifies source-backed *possible* tasks
and frustrations, not verified buying intent.

## Optional dedicated local MCP

You can run a separate, strictly local, stdio MCP entry point:

    python -m mcp_trendpulse.intelligence_mcp

A client can configure that module with executable 'python' and arguments
'-m', 'mcp_trendpulse.intelligence_mcp'. It offers read-only catalogue, plan,
explicit collection and job-posting-analysis tools. The existing 16-tool
TrendPulse community surface and hosted surface are intentionally unchanged.
Do not expose the standalone MCP as an unauthenticated public HTTP server.

## Status: catalog vs. actual request adapters

| Wave | Source IDs | Status | Signal |
|---|---|---|---|
| 1 | gdelt, eurostat, ted, cellar, github_issues, worldbank | Bounded adapters | Attention, demographics, procurement, laws, issues, indicators |
| 2 | greenhouse, lever, ashby, smartrecruiters | Bounded public-board adapters | Employer work and inferred workflow friction |
| 2 | sec_companyfacts | Bounded, requires SEC descriptive contact User-Agent | Company-reported financial facts |
| 2 | openalex | Bounded, no paid fallback and 5 calls/day local cap | Scientific momentum |
| 2 | companies_house | Requires a free Companies House API key | UK business filings |
| 2 | cfpb, cordis, usaspending | Catalog only; deliberately not auto-fetch-enabled | Complaints, research funding, U.S. awards |
| 3 | gleif, ecb | Bounded public adapters | Legal entities and official financial time series |
| 3 | entsoe | Requires approved **free** ENTSO-E token | Electricity load by EIC |
| 3 | rsshub_local | Local RSSHub on 127.0.0.1:1200 | Public website feeds |
| 3 | copernicus, epo, opsi_slovenia, changedetection_local | Catalog only; deliberately not auto-fetch-enabled | Climate, patents, Slovenia, official-site diffs |

Catalog-only means *not implemented as a live fetcher*. Free availability,
data licenses, endpoint version, response size and auth must be validated
before claiming a source operational. Some adapters can also fail on large
public datasets because the collector refuses responses over 256 KiB.

## Why reverse-engineer job openings?

Published postings expose responsibilities that employers are already
assigning and sometimes paying salaries to perform. That is a useful pain
signal but **does not demonstrate willingness to buy an external product**.
A firm recruiting an internal developer might prefer to build in-house.

A disciplined process:

1. Define the narrow buyer group, geographic coverage, time window and
   sampling method *before* collecting postings.
2. Read actual job responsibilities (not only role titles). Extract specific
   recurring manual work, integration tasks, compliance, incident response,
   cost management and customer operations.
3. Attribute each example to its employer, posting URL and posting date.
4. Check recurrence across **independent companies** and source vendors;
   one duplicated vacancy is not multiple votes.
5. Compare the implied workflow against existing commercial alternatives.
   Explicitly test build-versus-buy and who controls purchasing decisions.
6. Triangulate with customer discussions, current vendor pricing, contracts,
   disclosed spending, procurement, or observed paid pilots.
7. Interview potential buyers about **the last actual occurrence**, cost,
   frequency, workaround and purchase process, not a hypothetical wish list.
8. Choose the smallest experiment that can **disprove** the proposition.
   Never substitute endless reports for a real-world behavioral test.
9. For forecasts, preserve the publication and discovery dates to avoid
   hindsight leakage when backtesting.

The analyzer keeps excerpts and posting URLs; each category is a heuristic
*problem hypothesis*, never an automatically validated business.

Y Combinator's customer-interview guidance emphasizes asking about actual
past behavior: https://www.ycombinator.com/library/6g-how-to-talk-to-users
Strategyzer's evidence scale distinguishes statements, low-stakes action,
and meaningful commitments:
https://www.strategyzer.com/library/business-project-succcess

## Eight independent lenses

| Lane | Source combination | Most important falsification |
|---|---|---|
| 01 Autonomous authority | GitHub incident reports + hiring + regulation | Do buyers pay for independent safeguards beyond their platform? |
| 02 Machine-to-machine commerce | SEC filings + hiring + merchant news | Are ordinary merchants changing budgets because agents purchase? |
| 03 SME profitability | Eurostat + hiring + TED + competitors | Which specific sector has accessible budgets and measurable pain? |
| 04 Regulation-created demand | CELLAR + official regulator updates + TED | Are deadlines firm and is existing compliance supply inadequate? |
| 05 Fraud and identity | CFPB + incidents + NVD + procurement | Is the underserved buyer reachable without regulated incumbency? |
| 06 Household finances | Eurostat + ECB + complaints | Can savings be verified, and who pays for the service? |
| 07 Longevity and care | Eurostat + CORDIS + hiring | Are solutions reimbursed or directly purchased? |
| 08 Climate and energy | ENTSO-E + Copernicus + TED | Is there a software-addressable problem, not a capital project? |

These are discovery directions. Agents doing the eventual work should get
specific, verifiable *deliverables* (experiments, apps, sales validation,
reports or implementation), not an indefinite research-only schedule.
Two available slots may be used for independent opportunity falsification
and bounded commercial experiments when the evidence warrants them.

## The research and decision discipline

Use a hypothesis-first, evidence-first approach:

- **Observe:** Establish what changed and when: employer responsibilities,
  real customer complaints, procurement, regulation or behavior.
- **Triangulate:** Require at least two independent *evidence classes*. Two
  articles quoting the same press release are one original source.
- **Buyer:** Name the organization/person with purchasing authority and
  the current cost of the problem. An affected user is not necessarily
  the paying customer.
- **Timing:** Explain why demand increases within a specific 2027–2030
  horizon; distinguish proposals from adopted and effective laws.
- **Alternatives:** Identify how the job is solved now, including internal
  staff, spreadsheets, consultants, general-purpose software, and incumbents.
- **Disprove:** Record an alternative explanation and the cheapest
  experiment that would show the idea is wrong.
- **Behavior:** Treat actual user/financial commitment as stronger evidence
  than survey opinions or normalized search-interest scores.
- **Reachability:** Market size must be calculated from reachable buyers
  and reasonable adoption assumptions, not a population headline.

A tool returning a record is evidence *of that record*, not evidence of
causality or successful market prediction. No source-mix accuracy has been
independently backtested yet.

## Free-only operational guardrails

- No paid tiers, credits, billable compute, hosted services or proxy services.
- Request plans use fixed host allowlists, exact typed parameters, short
  timeouts, 256-KiB response ceilings, no redirects/proxies and no automatic
  retries. Raw source URLs are not user-configurable arbitrary fetch targets.
- Explicit --execute or execute=true is needed to contact a provider.
- Optional free credentials live in environment variables (never in URL or
  returned logs): TRENDPULSE_INTEL_SEC_USER_AGENT,
  TRENDPULSE_INTEL_COMPANIES_HOUSE_KEY,
  TRENDPULSE_INTEL_ENTSOE_TOKEN.
- SQLite budgets and a 60-minute cache reside under
  ~/.mcp-trendpulse/intelligence (or TRENDPULSE_INTEL_CACHE_DIR).
  Deleting state can reset local budgets; do not use that to evade rate limits.
- Use one owner for shared cache management and avoid concurrent canonical
  repository writers. Logs and source records may include personal details
  present in public sources; retain and share only what is necessary.
- Do not infer demand or revenue from normalized Google Trends scores,
  press mentions, patents, vacancies or legislation alone.
- Publication, customer contact, payment, deployment and production changes
  all require separate authorized workflows.

## Known follow-up tasks

Before production rollout: exercise adapters against real public endpoints,
test provider-specific error and pagination variants, check jurisdictional
data licenses, benchmark memory/network demand, and verify no live worker
or scheduler behavior changed. Only then consider promoting this optional
module into an agreed long-term architecture.
