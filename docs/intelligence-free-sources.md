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
    mcp-trendpulse-cli intelligence query --source gdelt_latest
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

## Secure provider setup and RSSHub self-hosting

See [Optional intelligence provider settings](intelligence-provider-settings.md)
for the Windows Credential Manager wizard, cross-platform secrets injection,
read-only MCP settings tools, ChatGPT connection boundaries and the pinned
loopback-only RSSHub Compose service. Credentials are added only by the human
user, not by tool calls or chat prompts.

## Optional dedicated local MCP

You can run a separate, strictly local, stdio MCP entry point:

    python -m mcp_trendpulse.intelligence_mcp

A client can configure that module with executable 'python' and arguments
'-m', 'mcp_trendpulse.intelligence_mcp'. It offers read-only catalogue, plan,
explicit collection and job-posting-analysis tools. The existing 16-tool
TrendPulse community surface and hosted surface are intentionally unchanged.
Do not expose the standalone MCP as an unauthenticated public HTTP server.

## Source status and measured reality

There are 25 distinct source families, including a dedicated one-job detail
adapter. A request builder alone is **not** proof of live provider support.
Only the current GitHub Actions "Free intelligence live contract smoke" run
can establish which representative public requests returned valid data.

| Wave | Source IDs | Free access and behavior |
|---|---|---|
| 1 | gdelt_latest | Keyless GDELT raw 15-minute event manifest; **not** DOC keyword search or news article data |
| 1 | eurostat, ted, cellar, github_issues, worldbank | Keyless official indicators, notices, laws, public issues |
| 2 | greenhouse, greenhouse_job, lever, ashby, smartrecruiters | Public job indices; `greenhouse_job` fetches one detailed description by ID |
| 2 | sec_companyfacts, sec_companyconcept | Public, requires an attributable descriptive SEC User-Agent |
| 2 | openalex | **Requires registered free API key** ($1/day allowance); 300 local searches/day maximum, no paid fallback |
| 2 | companies_house | **Requires free UK Companies House key** (600 requests per 5 minutes upstream) |
| 2 | usaspending, cfpb, cordis | Keyless public contract awards, structured complaint records, EU project titles |
| 3 | gleif, ecb | Keyless legal entities and official economic time series |
| 3 | entsoe | Requires freely approved transparency API token (upstream policy applies) |
| 3 | rsshub_local, changedetection_local | Your **own self-hosted** services only; no hosted subscriptions |
| 3 | copernicus | Keyless **satellite collection metadata**; not climate projections or ERA5 reanalysis |
| 3 | epo | Registered free EPO OPS OAuth key/secret; 4 GB/week free data allowance |

No data source requires a credit-card trial or a paid vendor contract. The
public research key sources only become available after **you** configure
the free credentials locally. Sensitive environment variables are described
below; do not paste them into chat or commit them to GitHub.

The latest live smoke verifies global and cross-border public sources. Provider outages and empty results are preserved as evidence limitations rather than counted as demand.

Responses exceeding 256 KiB fail rather than silently download or truncate.
A job-index listing may omit descriptions; fetch one individual job with
`greenhouse_job` and then use the offline analysis tool.

### Real provider smoke workflow

The repository includes
.github/workflows/intelligence-live-smoke.yml and
scripts/intelligence_live_smoke.py. On changes to this feature,
GitHub Actions invokes bounded, read-only public source requests without
secrets and uploads a JSON diagnostic report. One failure fails the smoke
check; "200 OK but empty" is not treated as verified market demand.
Credential-only sources are covered by offline contract tests until real
free keys are provided. Check the *latest* PR run, not an older passing run.

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


## Free credentials (configure only after provider validation)

Use local environment variables, not chat, GitHub issues, PR descriptions,
source files or command-line arguments:

- `TRENDPULSE_INTEL_COMPANIES_HOUSE_KEY`: free Companies House key, 600 requests per five minutes upstream.
- `TRENDPULSE_INTEL_OPENALEX_KEY`: free account key. Keyless research remains possible at a smaller budget. Authorization uses a header, not a query-string key.
- `TRENDPULSE_INTEL_EPO_CONSUMER_KEY` and `TRENDPULSE_INTEL_EPO_CONSUMER_SECRET`: registered EPO OPS OAuth credentials, automatically exchanged for short-lived Bearer token when a read-only search executes.
- `TRENDPULSE_INTEL_ENTSOE_TOKEN`: free approved ENTSO-E transparency token.
- `TRENDPULSE_INTEL_CHANGEDETECTION_KEY`: API key of your **self-hosted, local** change monitor only.

No paid trial credentials, payment information or premium plans are needed.
The EPO free threshold is 4 GB per calendar week, but far lower request
budgets are enforced by this module. You must not provision a paid OPS tier.
