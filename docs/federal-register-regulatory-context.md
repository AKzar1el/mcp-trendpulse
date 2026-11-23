# Federal Register regulatory context (optional, keyless)

TrendPulse has an **opt-in** U.S. Federal Register source, identified as
`federal_register`. It reuses the existing read-only intelligence planning,
fixed-host enforcement, SQLite request budgets, one-hour source cache and
MCP/CLI entry points. It does not affect the default 16 Community MCP tools,
normal Google News/Trends behavior, scheduled workers or the separately gated
MJAU v3 code.

## Access and limits

- Official API: https://www.federalregister.gov/developers/documentation/api/v1
- Authentication/payment: **none**. No account, API key, credits or billing.
- TrendPulse **local safety cap**: 20 attempted source requests per UTC day.
  This is our own limit, **not** a claimed Federal Register upstream quota.
- Each query: one HTTPS GET, no redirect or retry, at most 20 results on one
  page, 7-90 day publication-date lookback, fixed safe fields only.
- A 256-KiB HTTP body ceiling and bounded record projection apply. No article
  full text or complaint submissions are stored in the response cache.
- HTTP 429/503 and schema failures use the existing unavailability/cooldown
  path. No zero-demand claims can be inferred from empty/failed results.

## Use

Print a safe read-only plan first (no provider request):

```sh
mcp-trendpulse-cli intelligence query --source federal_register --keyword "artificial intelligence" --limit 8
```

Explicitly execute one official query:

```sh
mcp-trendpulse-cli intelligence query --source federal_register --keyword "artificial intelligence" --limit 8 --execute
```

The optional existing discovery workflow can derive a topical query from
previously observed candidate labels/research topics (if suitable) and request
**at most one** additional bounded Federal Register page:

```sh
mcp-trendpulse-cli intelligence discover --regulatory-context
mcp-trendpulse-cli intelligence discover --regulatory-context --execute
```

Or provide an explicit, bounded topical term:

```sh
mcp-trendpulse-cli intelligence discover --regulatory-context --regulatory-term "data privacy" --execute
```

The separate, opt-in intelligence MCP accepts `regulatory_context: true`
and optionally `regulatory_term` on its existing
`intelligence_discover_current` tool. These are not new public Community
tools. With `execute: false`, this produces only a plan, not a network call.

If no source-derived topic is suitable, the optional workflow returns
`no_supported_topic` and performs zero Federal Register requests. Existing
OpenAlex/CFPB/TED sample counts and candidates are unchanged. Regulatory
documents are reported separately and never increment buyer votes.

## Interpretation and legal status

A search match is evidence of a **publication**, not of an enacted
regulation, an effective date, legal advice, a compliance deadline, a new
market, or a specific paying buyer. Proposed rules, rules and notices are
distinct. Review the original document and the official govinfo edition,
then verify current legal effect in eCFR and relevant authoritative sources.
The federalregister.gov XML site also warns that its own presentation is not
the official legal edition.

Returned document fields are intentionally limited to original document
number, title, publication date, type and canonical link, plus explicit
`legal_effect_verified=false` / proposal flags. Full text and abstract are
not cached or exported as product intelligence.

## Test and rollout gates

Deterministic regression tests:

```sh
python -m pytest -q tests/test_intelligence_federal_register.py
```

Hypothesis property/fuzz tests run against local builders and source-shape
projections **without any API calls**. Install the free test-only library in
your development environment, not into production:

```sh
python -m pip install "hypothesis>=6.170.17,<7"
python -m pytest -q tests/test_intelligence_federal_register_properties.py
```

CI/build gate: run Ruff, regular test suite, packaging guard, preexisting
separate intelligence MCP stdio tests and a bounded independent live source
smoke. Live success requires nonempty, source-confirmed data with canonical
document links and correct publication dates. A 200 status with a malformed
payload is not success; nor is an empty dataset evidence of no regulation.

**2026-11-23:** This feature is introduced on a feature branch for review.
The Codexify/TrendPulse tunnel and direct provider network are currently
unreachable from this execution environment. Therefore no live Federal
Register probe or full-suite acceptance is claimed. Do not merge/deploy
or change worker schedules before those gates pass.

No Bluesky source, SDK, login, authentication or crawler is included.
