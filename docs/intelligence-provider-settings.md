# Optional TrendPulse intelligence: provider settings and self-hosted RSSHub

This is a **separate, opt-in, read-only MCP extension**. It does not alter the
existing community/hosted TrendPulse MCP, published 16-tool surface, scheduled
worker, production endpoint, browser session, or merger. Starting the normal
`mcp-trendpulse` process does not enable these optional tools.

## Why the setup works like established MCP servers

The GitHub MCP Server exposes configurable toolsets, individual tool controls
and immutable read-only enforcement; Microsoft Playwright MCP uses a config
file and environment settings; Context7 allows environment-backed credentials.

References:
- https://github.com/github/github-mcp-server/blob/main/docs/server-configuration.md
- https://github.com/microsoft/playwright-mcp/blob/main/README.md
- https://github.com/upstash/context7/blob/master/packages/mcp/README.md

TrendPulse uses the smallest compatible pattern: **opt-in separate server +
read-only provider metadata + non-LLM credential setup**. There is deliberately
no settings-writing MCP tool and no general arbitrary-URL HTTP proxy.

## Quick start

Use the same existing package, no extra Python dependencies:

```bash
mcp-trendpulse-cli intelligence settings status
mcp-trendpulse-cli intelligence settings guide openalex
mcp-trendpulse-cli intelligence sources
```

`settings status` returns entries with required environment-variable names,
whether each is configured, documentation, keyless capability (if supported), and the free allowance. It **never**
prints the value, authentication headers, or secret material. A configured field
means **ready to test**, not "upstream authentication verified".

On Windows, store a free provider key interactively in the current Windows
user's native Credential Manager:

```powershell
mcp-trendpulse-cli intelligence settings set-key openalex
mcp-trendpulse-cli intelligence settings set-key companies_house
mcp-trendpulse-cli intelligence settings set-key epo
mcp-trendpulse-cli intelligence settings set-key entsoe
mcp-trendpulse-cli intelligence settings status
```

The terminal prompts for one or two fields with **hidden input**, without
putting values in CLI arguments or shell history. EPO collects two fields
and rolls back a partial write if one field fails. Use
`mcp-trendpulse-cli intelligence settings remove-key openalex` to revoke a
stored local value after an explicit confirmation. Restart the *optional*
intelligence MCP to refresh the running process when changing credentials.

Windows credentials are OS-user-scoped. The MCP process must run under that
same Windows account; a service using a different identity cannot read your
personal credential vault. On non-Windows machines, this command refuses to
persist secrets: supply values using the MCP client's secure environment
injection or a trusted secrets manager instead. **No plaintext fallback** is
created under the project directory or user profile.

Environment variables override the Windows vault for the same field.
Explicit `env={}` arguments in tests bypass all ambient credentials.

## Available generous-free credential providers

| Provider | Required fields | Verified free access policy |
|---|---|---|
| OpenAlex | `TRENDPULSE_INTEL_OPENALEX_KEY` **optional** | Basic API queries work without a key (local 20/day); free registered key gives a larger allowance (local 300/day), no paid fallback |
| Companies House | `TRENDPULSE_INTEL_COMPANIES_HOUSE_KEY` | Registered free account with 600 calls per 5 minutes upstream |
| EPO OPS | `TRENDPULSE_INTEL_EPO_CONSUMER_KEY` and `TRENDPULSE_INTEL_EPO_CONSUMER_SECRET` | Registered free OPS up to 4 GB per week; no paid-overage support |
| ENTSO-E | `TRENDPULSE_INTEL_ENTSOE_TOKEN` | Freely approved transparency token, subject to provider approval and fair use |
| Local changedetection.io | `TRENDPULSE_INTEL_CHANGEDETECTION_KEY` | Your own self-hosted local instance only |

Current OpenAlex guidance: https://help.openalex.org/api/authentication/ .
The status screen distinguishes *keyless basic queries available* from
*authenticated free-key testing ready*. No key is written by a query.

SEC company data use the non-secret descriptive
`TRENDPULSE_INTEL_SEC_USER_AGENT` (include a real technical contact).
Local RSSHub itself requires no provider key for the built-in test route.

**Never paste or commit these values** into ChatGPT conversation content,
GitHub issues/PRs, screenshots, dotenv templates, commands or MCP tool
arguments. Register **free plans only**, with no payment instrument.

## ChatGPT and other MCP hosts

**Local stdio clients** can launch the separate server:

```json
{
  "mcpServers": {
    "trendpulse-intelligence": {
      "command": "python",
      "args": ["-m", "mcp_trendpulse.intelligence_mcp"]
    }
  }
}
```

The optional server exposes nine read-only tools. Two are intended for
ChatGPT-like clients to show setup instructions and key-readiness in a
settings-like experience: `intelligence_provider_settings` and
`intelligence_provider_setup`. They **cannot** retrieve, accept, modify,
delete or create API keys. A model can explain what to do, but cannot silently
configure credentials on your behalf.

**ChatGPT web custom plugins** require a secure remote MCP endpoint or the
first-party Secure MCP Tunnel. They do **not** connect to this local stdio
command directly. This repository has **not** deployed an independent remote
intelligence endpoint, OAuth authorization service, or multi-user secrets UI.
To use it in a ChatGPT workspace, follow OpenAI's current custom MCP plugin
documentation and only connect via a separately authenticated, authorized
transport. Never expose unauthenticated local stdio over a public HTTP port.

Official documentation:
- https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt
- https://developers.openai.com/plugins/build/auth

**Important shared-server boundary:** the current SQLite request cache and
OS credentials belong to one local user. Multi-user hosting requires
per-tenant secret and cache isolation **before deployment**. The current
single-user module must not be published as a shared, unauthenticated server.

## RSSHub self-hosting (optional, free, isolated)

The repository includes a minimal loopback-only Compose file with the RSSHub
official container pinned to an immutable image digest verified in CI:

```bash
docker compose -f deploy/intelligence-rsshub.compose.yml up -d
curl --fail http://127.0.0.1:1200/healthz
mcp-trendpulse-cli intelligence query --source rsshub_local --identifier test/1 --execute
```

Only localhost port 1200 is accepted by the source adapter. No public port,
redis cluster, paid subscription, Chromium, secondary tunnel or new scheduled
worker is created. Run the optional Compose service on the *same host* as the
optional intelligence server. Existing TrendPulse deployment files remain
unchanged.

The self-host smoke workflow
`.github/workflows/intelligence-rsshub-smoke.yml` boots a **real RSSHub
container**, waits for `/healthz`, fetches the official built-in `/test/1`
feed, validates RSS XML and known entries, then probes a real public
`/github/issue/DIYgod/RSSHub` route. An upstream feed being blocked does
not incorrectly fail local RSSHub core health. Diagnostic JSON and container
digest are recorded; the temporary container is removed after testing.

This proves a real local installation and one representative route; it
cannot guarantee every website route works, especially those requiring login,
browser automation, or bypassing anti-scraping controls.

## Upgrade and maintenance policy

- The existing 16-tool public TrendPulse interface stays unchanged; this
  dedicated extension must be invoked separately.
- The new settings commands write secrets **only** when a human explicitly
  enters them locally. All MCP settings tools remain read-only.
- Public sources remain explicit per-call fetches with bounded limits,
  typed schemas, strict fixed domains, per-source caps and no paid fallbacks.
- Secret values are never returned in provider status, setup guides or
  source URLs.
- This is a private draft until the currently configured sources have been
  tested against their real providers and the PR review passes.
- If a provider changes quotas, fails authentication or introduces fees,
  disable it rather than silently purchasing credits or selecting a paid tier.


## Twelve source-aware opportunity combinations (offline)

The 12 investigation lanes are accessible through:
- `mcp-trendpulse-cli intelligence opportunities lanes`
- optional MCP `intelligence_opportunity_lanes`

Submit bounded JSON evidence using `intelligence opportunities evaluate --input-json opportunity.json`
or the equivalent read-only `intelligence_evaluate_opportunities` MCP tool.
Each candidate requires its narrow buyer, workflow, geographic scope and lane.
Each evidence record requires an identified publisher, original record ID,
publication and observation dates, source URL, and source ID. The evaluator
rejects stale and future material, cross-geography/workflow mixing, repeated
publisher and origin claims, and incomplete input. Missing API coverage
produces partial status; negative evidence blocks priority escalation.
Full source URLs remain source references; no network is contacted by these
offline evaluation tools.

Supported combinations include autonomous safety, agent commerce, SME
profitability, compliance demand, fraud/identity, household finances, care
automation, energy software, developer reliability, research-to-product,
regulation-driven procurement, and corporate identity.

**A result can at most be flagged for buyer interview.** The engine never
returns success probability, validated commercial demand, investment advice
or a market-size forecast from these proxy signals. It provides a next buyer
experiment and an audit trail instead. Optional trend checks require 28
complete comparable daily observations; isolated spikes and missing days
must not be interpreted as growth.

`mcp-trendpulse-cli intelligence opportunities backtest --input-json history.json`
and MCP `intelligence_walk_forward_backtest` use prior-day evidence
and only later, *externally attested* paid-pilot/no-purchase outcomes. Synthetic
fixtures test temporal leakage, NOT real predictive accuracy. Descriptive
metrics are suppressed below 8 labeled examples across 2 independent cutoff
dates. Real buyer outcomes still need to be collected and audited before
any genuine historical benchmark is available.


### ENTSO-E live authentication verification

After ENTSO-E approves the registered account, create a one-time Web API
Security Token under My Account, then run `intelligence settings set-key entsoe`
from the intended Windows account. A safe one-day actual-total-load query is:

```powershell
mcp-trendpulse-cli intelligence query --source entsoe --identifier "10YSI-ELES-----O" --limit 2 --execute
```

The domain code is the published Slovenian bidding-zone EIC, used only as an
illustrative credential verification target; the overall trend hunter remains
global. A successful collector result must contain a `GL_MarketDocument`
with actual measured `quantity` fields. XML acknowledgement documents for
missing data, invalid query parameters or other provider errors are rejected
as **invalid source shape**, never interpreted as successful electricity-load
data. Keep tokens in local OS credentials; no URL token parameters or remote
GitHub Actions secrets. Use fresh read-only queries at most sparingly (local
quota for this adapter: six per day).


### ENTSO-E timeout diagnostics (single bounded request)

The standard `intelligence query --execute` timeout is 12 seconds. Approved
ENTSO-E API queries may take longer during provider load; an elapsed timeout
**does not prove token rejection**. Use `--timeout 30` for one explicit
request, without automatic retries or quota bypass:

```powershell
mcp-trendpulse-cli intelligence query --source entsoe --identifier "10YSI-ELES-----O" --limit 2 --execute --timeout 30
```

This option is limited to 2–30 seconds and does not change any worker's
schedule, provider budgets, or the 45-second temporary transport-failure cache.
On repeated timeouts, inspect HTTPS connectivity and the provider's own
known-issues page instead of regenerating a valid token. Do not paste tokens
in chat or logs; rotate any token accidentally disclosed to others.
Official status: https://transparencyplatform.zendesk.com/hc/en-us/articles/51106751516945
