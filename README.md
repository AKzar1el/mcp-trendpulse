# mcp-trendpulse

[![MCP](https://img.shields.io/badge/Model%20Context%20Protocol-MCP-blue.svg)](https://modelcontextprotocol.io)
[![Python](https://img.shields.io/badge/Python-3.11.5%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![mcp-trendpulse MCP server](https://glama.ai/mcp/servers/AKzar1el/mcp-trendpulse/badges/score.svg)](https://glama.ai/mcp/servers/AKzar1el/mcp-trendpulse)
[![MCPVault: verified](https://mcpvault.io/badge/mcp-trendpulse.svg)](https://mcpvault.io/servers/mcp-trendpulse/health?utm_source=external_badge&utm_medium=referral&utm_campaign=mcp_health_report)

**TrendPulse** is a Python Model Context Protocol (MCP) server for researching current news and search-interest trends. It combines Google News discovery and article extraction with Google Trends analysis so MCP clients can inspect what is trending, compare keyword momentum, explore related demand, and add current-news context to research workflows.

The project currently ships as a **community/self-hosted MCP server** and also contains the implementation for a separate **hosted TrendPulse by DigestSEO** surface for remote MCP clients such as ChatGPT and Codex. The hosted layer uses a smaller, goal-oriented tool surface while the community server keeps the full low-level research toolkit available to developers.

> **Project status:** the local/community server is usable today. The DigestSEO-hosted MCP and public OpenAI plugin are not released yet and should not be treated as available endpoints.

Engineering context: TrendPulse is part of the [DigestSEO](https://digestseo.com/) MCP ecosystem. It complements [mcp-gsc](https://digestseo.com/gsc-mcp/) for Google Search Console data, [mcp-geo](https://digestseo.com/geo-mcp/) for AI visibility, and [mcp-web-validator](https://digestseo.com/validator-mcp/) for technical web validation. The broader architecture is documented in the [DigestSEO MCP Suite engineering case study](https://tomiseregi.si/projects/digestseo-mcp-suite).

## TrendPulse Demand Brief

Need a fast evidence check before choosing a topic, keyword, market, product angle, or content bet? Tomi offers a **human-produced TrendPulse Demand Brief for EUR 49**.

For one decision, the brief covers up to five keywords/phrases and two geographic markets using TrendPulse's open-source research capabilities plus current public sources: search-interest direction, relative momentum, related demand, useful news context, and three concrete implications. Target turnaround is within 24 hours after payment is confirmed and the inputs are supplied.

[See the exact scope and request format](https://github.com/AKzar1el/mcp-trendpulse/blob/main/DEMAND_BRIEF.md), [read a public sample brief](https://github.com/AKzar1el/mcp-trendpulse/blob/main/SAMPLE_DEMAND_BRIEF.md), or email [info@tomiseregi.si](mailto:info@tomiseregi.si?subject=TrendPulse%20Demand%20Brief%20%5BTP-RS1%5D&body=Decision%3A%0AKeywords%20(up%20to%205)%3A%0AMarkets%20(up%20to%202)%3A%0AContext%20%2F%20deadline%3A) with the subject `TrendPulse Demand Brief [TP-RS1]`.

The paid brief is optional. The Community MCP remains free and unchanged, and the `TP-RS1` marker is only an inbound attribution marker; no hidden telemetry is added to the MCP.

## What TrendPulse can do

### News research

- Search Google News by keyword, location, topic, or publisher domain.
- Retrieve top news stories.
- Resolve Google News links and extract article content.
- Fall back from normal HTTP retrieval to Playwright/Chromium for difficult pages.
- Optionally summarize article text with MCP client sampling, with local NLP as a fallback.

### Trend research

- Retrieve current trending terms for a geographic market.
- Pull Google Trends interest-over-time data for one or more keywords.
- Calculate keyword growth over custom windows such as 3M or 1Y.
- Rank live trends by volume or growth.
- Inspect interest by country, region, city, or DMA where supported.
- Explore related queries, related topics, suggestions, and category IDs.
- Compare Google Search, YouTube Search, News Search, Image Search, and Google Shopping trend properties where supported by the underlying provider.

> **Known Google Trends limitation:** The unofficial provider is best-effort and often throttled or temporarily unavailable. A working Trending Now RSS feed does not guarantee that the separate ranked/Explore/interest endpoints will work. Correctly classified provider failures are expected limitations, not automatically product bugs; quotas and reset timing are not guaranteed. See [standing operator guidance](docs/operations.md#standing-google-trends-availability-expectation-community-and-hosted).

## Community and hosted architecture

TrendPulse is being developed with two deliberate surfaces:

| Surface | Purpose | Status |
| --- | --- | --- |
| **Community MCP** | Full Python MCP server for local use, development, self-hosting, and integrations with MCP-compatible clients. | Available in this repository |
| **TrendPulse by DigestSEO** | Managed remote MCP for ChatGPT/Codex and a future public OpenAI plugin with a smaller, task-oriented tool surface. | In development |

The community server remains useful independently. The hosted edition will reuse the same core trend-research concepts while adding the deployment, reliability, authentication, observability, and product integration needed for a managed service.

The implemented hosted tool surface is intentionally higher level than the community API and centers on goals such as:

- `discover_trends`
- `analyze_keyword_trend`
- `compare_keyword_trends`
- `discover_related_demand`
- `get_trend_context`
- `find_seo_opportunities`

These names describe the hosted ChatGPT Apps/MCP interface; they remain separate from the current Community MCP tool names.

## Installation

### Run from PyPI with `uvx` (recommended)

TrendPulse is published on PyPI, so the shortest install path is:

```bash
uvx mcp-trendpulse
```

**TrendPulse v0.3.0 and newer requires Python 3.11.5 or newer.** Python 3.10 reached end-of-life in October 2026 and cannot use Pillow 13, which patches upstream image-decoder vulnerabilities; patched Soup Sieve 4.x also requires Python 3.11.5+. To run TrendPulse on a machine with an older Python default, select a supported interpreter explicitly:

```bash
uvx --python 3.11 mcp-trendpulse
```

See the [security policy](SECURITY.md) for the supported-runtime decision. Python 3.10 and Python 3.11.0-3.11.4 users must upgrade their interpreter before upgrading to v0.3.0.

To run the current repository head instead of the published package:

```bash
uvx --from git+https://github.com/AKzar1el/mcp-trendpulse.git mcp-trendpulse
```

### Install with pip from a checkout

```bash
git clone https://github.com/AKzar1el/mcp-trendpulse.git
cd mcp-trendpulse
python -m pip install .
python -m mcp_trendpulse
```

## Article download safety and optional Chromium

Article downloads use bounded HTTP(S) requests pinned to a validated public IP, while retaining the original hostname for the HTTP Host header and HTTPS certificate verification. System proxies are disabled for this path. The Playwright article fallback is currently disabled because browser URL interception alone cannot guarantee connection-level protection against DNS rebinding; JavaScript-only or challenge-protected articles may therefore return no content. Other Google Trends/News discovery operations are unaffected.

The optional Python `playwright` package does not install Chromium automatically. For separate browser-supported workflows, install Chromium as follows:

For local use:

```bash
playwright install chromium
```

For Linux environments that also require browser system dependencies:

```bash
playwright install --with-deps chromium
```

Trend-only operations do not inherently require Chromium.

## Client configuration

### Claude Desktop and Claude Code

Claude Code plugin packaging is included in `.claude-plugin/plugin.json` with its MCP definition in `.mcp.json`. The Community MCP remains local/stdin-based and runs through `uvx mcp-trendpulse`.

### Claude Desktop

Using the published PyPI package with `uvx`:

```json
{
  "mcpServers": {
    "mcp-trendpulse": {
      "command": "uvx",
      "args": ["mcp-trendpulse"]
    }
  }
}
```

### VS Code

[Install TrendPulse in VS Code](https://vscode.dev/redirect?url=vscode%3Amcp%2Finstall%3F%257B%2522name%2522%253A%2522mcp-trendpulse%2522%252C%2522command%2522%253A%2522uvx%2522%252C%2522args%2522%253A%255B%2522mcp-trendpulse%2522%255D%257D)

Requires `uv`/`uvx`. The install runs the published Community MCP package from PyPI over local stdio.

For workspace-level configuration, put this in `.vscode/mcp.json`. The same top-level `servers` shape is used by the VS Code user-profile `mcp.json` for a global configuration.

```json
{
  "servers": {
    "mcp-trendpulse": {
      "command": "uvx",
      "args": ["mcp-trendpulse"]
    }
  }
}
```

### Codex CLI and Codex IDE extension

Codex CLI and the Codex IDE extension share MCP configuration and support local stdio servers. Register the published TrendPulse Community MCP package with:

```bash
codex mcp add mcp-trendpulse -- uvx mcp-trendpulse
```

This makes TrendPulse available to Codex CLI and its IDE extension; it does **not** automatically install the server in ChatGPT desktop or web. See [OpenAI's Codex MCP guidance](https://developers.openai.com/resources/docs-mcp) for the shared Codex configuration model.

### ChatGPT custom MCP connections

ChatGPT uses a separate plugin connection workflow; it does not import the local Codex MCP registration above. Where permitted by your account and workspace, use **Plugins -> Add custom MCP server** with a reachable HTTPS Streamable HTTP endpoint, or an available Secure MCP Tunnel for a private server. See [OpenAI's connection instructions](https://developers.openai.com/plugins/deploy/connect-chatgpt) for current requirements and access controls.

Local stdio execution through a *desktop-only ChatGPT plugin* is a distinct, partner-allowlisted submission route, not a general **Settings -> MCP Servers** command-entry option. See [OpenAI's desktop-only plugin policy](https://developers.openai.com/plugins/deploy/desktop-only).

TrendPulse's managed HTTPS endpoint and public ChatGPT plugin are **not released**. The current published Community MCP runs locally via `uvx mcp-trendpulse` in supported stdio clients; the Codex command alone does not connect it to ChatGPT.

### Cursor and portable Agent Plugins

This repository includes an [Agent Plugins 1.0](https://agent-plugins.org/) manifest at the repository root. Compatible clients such as Cursor and GitHub Copilot can load the same portable `plugin.json` + `mcp.json` package.

Cursor also supports global and project MCP configuration. Add the server to the relevant `mcp.json` configuration:

```json
{
  "mcpServers": {
    "mcp-trendpulse": {
      "command": "uvx",
      "args": ["mcp-trendpulse"]
    }
  }
}
```

### Devin CLI and Devin Desktop

[Devin CLI plugins](https://docs.devin.ai/cli/extensibility/plugins/overview) can load Claude plugin packages and Agent Plugins 1.0 packages directly from GitHub. TrendPulse already ships both compatible layouts (`.claude-plugin/plugin.json` + `.mcp.json`, and root `plugin.json` + `mcp.json`). Install it with:

```bash
devin plugins install AKzar1el/mcp-trendpulse
```

Devin requires a signed-in CLI session to manage plugins. The installed TrendPulse plugin starts the published Community MCP locally over stdio with `uvx mcp-trendpulse`; it does not use the unreleased hosted TrendPulse endpoint. The same plugin is available in Devin Desktop after installation.

### Kiro

[![Add to Kiro](https://kiro.dev/images/add-to-kiro.svg)](https://kiro.dev/launch/mcp/add?name=mcp-trendpulse&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22mcp-trendpulse%22%5D%2C%22disabled%22%3Afalse%2C%22autoApprove%22%3A%5B%5D%7D)

Requires `uv`/`uvx`. The install runs the published Community MCP package from PyPI; it does not use the unreleased hosted surface.

Privacy: [TrendPulse Community MCP Privacy Notice](PRIVACY.md) · Support: [info@tomiseregi.si](mailto:info@tomiseregi.si)

### LM Studio

[Add TrendPulse to LM Studio](https://lmstudio.ai/install-mcp?name=mcp-trendpulse&config=eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyJtY3AtdHJlbmRwdWxzZSJdfQ%3D%3D)

Requires `uv`/`uvx`. LM Studio runs the published Community MCP package locally over stdio; no hosted TrendPulse service is required.

### ChatGPT web and other cloud MCP clients

The repository now includes a dedicated stateless Streamable HTTP ASGI entry point at `mcp_trendpulse.asgi:app`. This is separate from the Community stdio entry point, which remains unchanged.

For controlled local/private testing you can run the ASGI app with Uvicorn or use the provided container. See [`deploy/README.md`](deploy/README.md) for the hardened container, Host/Origin allowlists, Chromium sandbox requirements, health/readiness endpoints, and reverse-proxy notes.

The DigestSEO-hosted endpoint and public ChatGPT app are still **not released**. Hosted deployments now support fail-closed Clerk OAuth authentication; do not expose the remote transport publicly unless Clerk issuer/JWKS/audience settings, the public base URL, and the Host/Origin allowlists are configured for that deployment.

## Configuration

TrendPulse loads environment variables from the process environment and from a local `.env` file when present.

**Offline configuration check (source checkout):** Run `uv run mcp-trendpulse-cli doctor`
to inspect effective news edition, Trends request pacing, shared-state opt-in,
proxy presence, and hosted authentication/HTTP configuration without contacting
Google, opening a browser, creating shared state, or printing private proxy URLs,
credentials, audience IDs, or local directory paths. Add `--format json` for a
machine-readable, versioned report or `--strict` to exit with code 2 on static
configuration errors. The command intentionally does **not** verify network
reachability, current provider quotas, permissions, OAuth/JWKS availability, or
whether the public hosted endpoint is secure. Local-only authentication is
expected for the Community stdio MCP; never expose an unauthenticated remote
endpoint. This command is on repository HEAD, not necessarily the latest public
PyPI package.

Useful variables include:

```env
HTTP_PROXY=http://your-proxy-address:port
HTTPS_PROXY=http://your-proxy-address:port
GOOGLE_NEWS_LANGUAGE=en
GOOGLE_NEWS_COUNTRY=US
GOOGLE_TRENDS_DELAY=2.0
# Optional, absolute, private directory shared by TrendPulse processes on one host:
# TRENDPULSE_SHARED_STATE_DIR=/home/you/.cache/mcp-trendpulse
```

`GOOGLE_NEWS_LANGUAGE` and `GOOGLE_NEWS_COUNTRY` select the Google News language/edition used by all news-discovery tools; defaults remain `en` and `US`. `GOOGLE_TRENDS_DELAY` (default 2 seconds) paces Google Trends requests **across all TrendSpy worker threads in one process**, including the Trending Now batch endpoint. Identical interest-over-time queries are reused from a bounded, 90-second in-memory cache; concurrent duplicates share one provider request. After an upstream 429 or detected embedded quota rejection, the process pauses new Trends calls with bounded exponential cooldown and honors `Retry-After` when supplied. An already-cached series may still be returned during cooldown. The process also emits privacy-safe aggregate provider counters and latency buckets (see `docs/operations.md`). By default, coordination is process-local; it cannot increase or bypass Google's unpublished quota or throttle Google News article fetching. Proxy variables can be useful for legitimate network configuration but do not guarantee a higher upstream quota.

For **multiple local agents on one computer**, set the optional `TRENDPULSE_SHARED_STATE_DIR` to the same absolute, user-private directory in every TrendPulse process. This adds SQLite-backed inter-process pacing, a maximum 12-second request queue, shared 429 cooldown, and a 256-entry cache of **numeric, indexed Google Trends time series**. Cache keys are HMAC-hashed with a private directory key; query text and news articles are not saved. Long-window series live at most two hours, annual windows 90 minutes, shorter windows 30 minutes, and near-real-time series two minutes. Use a local disk, not a network drive or independent container filesystems. If shared state is unavailable, the existing in-process protections continue operating and emit a sanitized warning. The feature is off by default; it cannot raise Google's provider quotas or provide coordination across separate hosts.

Remote deployments also support `TRENDPULSE_HTTP_PATH`, `TRENDPULSE_HTTP_ALLOWED_HOSTS`, `TRENDPULSE_HTTP_ALLOWED_ORIGINS`, and `TRENDPULSE_BROWSER_SANDBOX`. The container enables Chromium sandboxing explicitly; local Community runs retain the Playwright-compatible default unless you opt in.

Do not commit secrets, private proxy credentials, or machine-specific `.env` files.

## MCP tools

The community MCP server currently exposes **16 tools**.

### News tools

| Tool | Purpose |
| --- | --- |
| `get_news_by_keyword` | Find recent news articles matching a keyword, or set `headlines_only=true` for clearly labeled Google News RSS headline metadata without publisher article extraction or summaries. |
| `get_news_by_location` | Find recent news associated with a location, or set `headlines_only=true` for clearly labeled RSS location headlines without publisher article extraction or summaries. |
| `get_news_by_topic` | Find recent news for a supported Google News topic, or set `headlines_only=true` for explicitly labeled RSS topic headlines without publisher article extraction or summaries. |
| `get_top_news` | Retrieve top Google News stories, or set `headlines_only=true` for explicitly labeled RSS headline metadata without article extraction or summaries. |
| `get_news_by_site` | Find recent news from a specific publisher domain, or set `headlines_only=true` for clearly labeled RSS publisher headlines without publisher article extraction or summaries. |
| `get_article_content` | Download, validate, extract, and optionally summarize one article URL. |

### Trend tools

| Tool | Purpose |
| --- | --- |
| `get_trending_terms` | Retrieve current trending terms for a geographic target. |
| `get_trends` | Retrieve interest-over-time points for one or more keywords. |
| `get_growth` | Calculate search-interest growth over requested windows. |
| `get_ranked_trends` | Rank current trends by growth or volume. |
| `get_top_trends` | Retrieve a top-trends feed without supplying a keyword. |
| `get_interest_by_region` | Compare keyword interest across geographic regions. |
| `get_related_queries` | Retrieve top and rising related search queries. |
| `get_related_topics` | Retrieve top and rising related Google Trends topics. |
| `get_suggestions` | Resolve autocomplete/topic suggestions for a query. |
| `get_categories` | Search or page through Google Trends category IDs and names before using `cat`. |

### Example: explicit trend window

`get_trends` accepts an explicit `timeframe`. Supplying one is preferable when you need reproducible comparisons.

```json
{
  "keyword": ["technical SEO audit", "AI SEO audit"],
  "geo": "US",
  "source": "google search",
  "timeframe": "today 12-m",
  "cat": 0
}
```

Supported provider ranges include standard windows such as `today 12-m` and `today 5-y`, relative windows such as `today 90-d`, `all`, and exact date ranges such as `2021-01-01 2026-01-01`.

Google Trends values are normalized interest scores. Do not interpret a 0-100 interest series as absolute search volume.

## CLI

The separate Click CLI is included in the public PyPI package. Run its published commands without a source checkout:

```bash
uvx --python 3.11 --from mcp-trendpulse mcp-trendpulse-cli --help
```

**Published CLI (v0.2.43+):** The `site` command and the `--headlines-only` options for `keyword`, `location`, `topic`, `top`, and `site` are available in the published PyPI package. Run the stable release rather than repository HEAD:

```bash
uvx --python 3.11 --from mcp-trendpulse mcp-trendpulse-cli keyword "OpenAI" --headlines-only
```

From a local source checkout, `uv run mcp-trendpulse-cli --help` uses that checkout. The opt-in headline-only commands return genuine Google News RSS titles, publishers, dates, and Google News links labeled as metadata, **not** extracted article bodies. Default news commands continue to attempt publisher-article extraction.

**Source checkout (not yet in the published PyPI version):** All five headline-only news commands support `--format json` for scripts and agent workflows, without changing the default human-readable output:

```bash
uv run --no-sync mcp-trendpulse-cli keyword "OpenAI" --headlines-only --format json
```

The JSON response includes a schema version, `google_news_rss` source, `rss_headline_only` evidence level, count, and only title, Google News URL, publisher and publication date for each headline. It never represents RSS metadata as extracted articles or serializes article body/summary fields. An empty result is valid JSON with an empty `headlines` list. `--format json` requires `--headlines-only`, prints no human-readable footer and makes no additional provider requests.

**Source checkout (not yet in the published PyPI version):** All five headline-only commands also support `--format csv` for spreadsheet workflows. CSV contains `source,content_level,title,url,publisher,publish_date` columns, with one header row even for zero results, no human footer, and spreadsheet-formula-safe untrusted metadata. It is RSS headline evidence, **not extracted article content or verified search volume**. Both structured formats can be saved directly to a new UTF-8 file using `--output-file`, which refuses to overwrite an existing file or create missing directories and avoids PowerShell 5.1 redirection encoding issues:

```bash
uv run --no-sync mcp-trendpulse-cli keyword "OpenAI" --headlines-only --format csv --output-file rss-headlines.csv
```

**Source checkout only:** Saved headline-only JSON can be reviewed **offline**, without another Google News fetch: `uv run --no-sync mcp-trendpulse-cli rss-review --evidence rss-headlines.json --format markdown --output-file rss-review.md`. The opt-in JSON or Markdown report validates the saved schema, headline-only source label, safe HTTP(S) links and declared record count; it identifies exact duplicate Google News URLs and missing publisher/date metadata, showing one row per unique URL. A valid complete capture exits 0, duplicate/missing/empty evidence exits 2 for human review, and invalid input exits 1 without creating a report. Files are bounded to 1 MiB/100 headlines, untrusted Markdown fields are escaped and existing reports are never overwritten. Saved dates and source labels are **not authenticated**; this is a headline-metadata quality check, not article extraction, a relevance ranking or a Google Trends demand measurement.

**Source checkout only:** To prepare a narrower offline research reading list from that same captured JSON, add `--contains "AI agents"` to `rss-review`. This opt-in case-insensitive literal substring filter matches saved **titles only** (not publisher or body), returns matching unique URLs in JSON or Markdown, and retains original capture-quality totals. Zero matches exit 2 for human review; they do **not** establish that no articles exist or that demand is absent. Filtering sends no new provider requests and does not rank relevance or verify independent articles.

**Source checkout only:** Add `--publisher-breakdown` to `rss-review` for an opt-in, provider-free summary of **saved publisher labels** across exact-URL-deduplicated headlines. The JSON/Markdown output counts case-insensitive, whitespace-trimmed labels, reports unknown labels separately, and gives the largest named label's share of all unique URLs in scope; with `--contains`, only matching titles contribute to the breakdown while original capture-quality totals remain intact. These labels and the file's source are **not authenticated**: repeated publisher labels are not independent corroboration or proof of demand. Without the flag, report shape, exit codes, and provider usage are unchanged.

**Source checkout only:** `rss-review --evidence rss-headlines.json --format csv --output-file rss-review.csv` exports an offline spreadsheet-ready review. A summary row carries original capture-quality counts, declared filter scope and unauthenticated-source limitations; unique saved headline rows carry their original metadata, with optional publisher-count rows when `--publisher-breakdown` is set. Untrusted spreadsheet-leading formulas are escaped, and existing files are never overwritten. This export does not establish independent corroboration, full-article truth, search growth or buyer demand.

**Source checkout only:** Compare two explicitly saved headline-only captures without refetching Google News: `uv run --no-sync mcp-trendpulse-cli rss-compare --older rss-earlier.json --newer rss-later.json --format markdown --output-file rss-delta.md`. The JSON or Markdown comparison reports newly seen, retained and no-longer-seen **exact Google News URLs**, same-URL headline changes and metadata quality warnings. Each saved file is independently bounded and validated; invalid input exits 1 without creating a report, duplicate/missing/empty records exit 2 for review, and complete captures exit 0 even when membership changes. Saved order/dates and source labels are not authenticated. A link missing from a later feed may merely be outside the feed window; newly seen links are **not evidence of market growth**, verified articles, buyer demand or search-volume changes. Existing report files are never overwritten.

For an offline spreadsheet review, use `rss-compare --older rss-earlier.json --newer rss-later.json --format csv --output-file rss-delta.csv`. The UTF-8 CSV has a summary row with counts and explicit evidence limitations, then one row per exact URL with its feed-window membership, older/newer headline metadata and same-URL title-change flag. Untrusted text is escaped against spreadsheet formula execution. A summary-only CSV when both captures are empty still exits 2 for review; CSV rows are **not** authenticated articles or market-growth observations. The command never overwrites an existing report.

**Source checkout (not yet in the published PyPI version):** Extracted-article CLI commands print results without creating JSON files. To opt into file export, pass `--save-json-dir` with an existing directory, for example `uv run mcp-trendpulse-cli keyword "OpenAI" --save-json-dir ./exports`. Output filenames include a short URL hash to distinguish similarly titled articles; existing files are never overwritten, and duplicate destinations or export failures produce errors. The `--headlines-only` mode only exports RSS metadata, not extracted article JSON.

The operator-only `bigquery-sql` command generates a fixed-table, partition-filtered SQL preview for Google's official public Top 25 / Rising datasets. It never submits a job or incurs API usage automatically. See `docs/bigquery-trends.md` for sandbox, query-cost guardrails, and market-coverage limitations.

`watch` provides opt-in **local manual** threshold rules and idempotent evaluation of user-supplied normalized interest evidence; it does not poll providers, schedule runs, or send external alerts. See `docs/trend-watch.md` before using the commands.

CLI commands available since v0.2.43 (also on GitHub `main`):

```text
brief-pack
keyword
location
site
top
topic
trending
```

`brief-pack` emits the deterministic trend/growth evidence table used for Demand Brief fulfillment. It intentionally leaves the final interpretation and recommendations to the human-produced brief.

For a source-checkout workflow that consumes evidence programmatically, choose JSON instead of the default Markdown:

```bash
uv run mcp-trendpulse-cli brief-pack --keyword "ChatGPT" --keyword "Claude" --market US --format json --output-file evidence.json
```

`--output-file` writes a **new UTF-8 file** without shell redirection and refuses to overwrite existing evidence. It supports JSON, CSV and Markdown; Watch JSON retains its dedicated `--watch-evidence-file` option. The JSON includes source attribution, the shared timeframe, per-market latest observation dates, numeric indices/growth percentages (or `null` when unavailable), and warnings about stale or malformed evidence. Indices are normalized **within each market request**; they are not search volume and should not be directly compared across markets. The command fetches Google Trends data but does not generate recommendations or send a Demand Brief.

**Source checkout only:** To turn an existing saved Demand Brief evidence file into a concrete, provider-free gap checklist, run `uv run --no-sync mcp-trendpulse-cli brief-review --evidence evidence.json --format checklist --output-file evidence-gaps.md`. It lists exact missing-primary-evidence keywords, failed markets with unknown (not zero) coverage, missing growth, saved warning counts, and optional stale/future observations when `--as-of` and `--max-age-days` are provided. It never contacts Google, reveals raw provider failure messages, or automatically retries a rate limit. The new Markdown file is not a verified demand report or permission to bypass quotas; the usual review exit codes 0/2/1 apply.

**Source checkout only:** To review previously saved schema-v1 JSON without contacting Google again, use `uv run mcp-trendpulse-cli brief-review --evidence evidence.json`. This bounded (1 MiB) read-only command checks the stored structure, source labels, per-market primary-evidence coverage, observation dates and failure flags. It prints a human-readable readiness summary; exit code 0 means structurally complete, 2 means incomplete or missing primary evidence, and 1 means the file could not be validated. For an agent or offline reporting workflow, append `--format json` for a machine-readable readiness object, `--format csv` for one spreadsheet-ready row per market, or `--format markdown` for a copyable readiness table with explicit source limitations. For example, `uv run mcp-trendpulse-cli brief-review --evidence evidence.json --format markdown --output-file readiness.md` writes a new BOM-free UTF-8 file without PowerShell redirection or overwriting an existing file; other formats can likewise be saved. Invalid evidence creates no output file, while a review-required result is still saved with exit code 2. Failed-only markets have **unknown** coverage rather than fabricated zeros, CSV escapes formula-like timeframe labels, and Markdown escapes saved labels. All formats retain source-authenticity and comparability caveats and never fetch or rewrite provider evidence. Even a structurally complete file requires human review of warnings, relevance and comparability before buyer-facing use.

**Multi-file readiness audit (source checkout only):** Review up to twelve explicitly supplied schema-v1 Demand Brief evidence files together without contacting Google: `uv run --no-sync mcp-trendpulse-cli brief-audit --evidence january.json --evidence february.json --format csv --output-file brief-audit.csv`. JSON, CSV and Markdown summarize each file's structural readiness, responding-market primary coverage, failed-only markets, growth gaps and saved warnings. Optional `--as-of YYYY-MM-DD --max-age-days N` checks declared stale/future observations. Failed-only market coverage remains unknown, not zero. The command neither compares normalized interest across captures nor searches directories and never overwrites reports. Exit 0 means structurally complete files, 2 means human review, and 1 means invalid inputs without partial output. Saved source provenance is not authenticated and manual relevance review remains essential.

**Saved evidence comparison (source checkout only):** `uv run mcp-trendpulse-cli brief-compare --before earlier.json --after current.json` compares primary-evidence keyword coverage, saved latest-observation labels and provider failure codes **without any live provider call**. Both bounded schema-v1 JSON files must declare the same timeframe, markets and (where recorded on both sides) keywords, otherwise the command refuses an invalid comparison. `--format json` produces a structured coverage-only delta; `--format csv` provides one spreadsheet-ready row per market. The optional `--format keyword-csv` outputs a row per keyword and market, identifying gained, lost, unchanged or unknown primary-evidence availability. It exposes offsetting keyword changes even when the market's total coverage is unchanged; missing provider market records remain unknown, not falsely absent. `--format markdown --output-file comparison.md` produces a copyable, source-caveated review table with dated regression details, safely escaping untrusted saved labels. Spreadsheet-formula-like timeframe and keyword text is escaped in CSV. `--output-file` saves any report format directly as a new BOM-free UTF-8 file, avoiding PowerShell 5.1 redirection encoding issues; existing paths are never overwritten. Default text is readable without extra tooling. Exit 0 means the **after** file is structurally complete, 2 means it needs human review (the report is still saved), and 1 means invalid or incompatible input (no new output is created). File order is user-supplied rather than independently time-verified; these results never compare normalized Google Trends interest indices across captures, establish causation or authenticate provider provenance. Neither input is modified.

To turn that comparison into a concrete, offline follow-up list, add `--format checklist --output-file changes.md`. The new Markdown checklist names exact newly lost, newly gained and still-missing keyword evidence, unknown failed-market coverage, older declared observation dates, saved growth failures, warning counts and optional stale/future after-file observations. It avoids copying sensitive provider error bodies and never turns relative-interest indices into cross-capture demand claims. It does not fetch providers or change the existing comparison formats, exit codes or overwrite protections; saved file order and provenance still need independent verification.

If a keyword has primary observations in both files but its date-only observation becomes **older in the declared after-file**, the comparison highlights the affected keyword and dates in text/JSON, reports the older-keyword count in market CSV and `observation_date_change=older_after` in keyword CSV, and exits 2 for human review even if overall coverage remains complete. Missing market evidence or timestamp-valued observations are reported as unknown rather than implying a chronological regression. This is a comparison of user-ordered saved evidence, **not** an authenticated capture-time or provider-freshness guarantee.

For an optional reproducible **after-file** freshness check, append `--as-of YYYY-MM-DD --max-age-days 7` to `brief-compare`. The same offline validation used by `brief-review` flags primary observations older than the declared threshold or dated in the future, regardless of whether comparison coverage is unchanged, and exits 2 for review. JSON includes per-market after-file freshness exceptions; market CSV adds stale/future counts; keyword CSV adds a per-keyword freshness status; text and Markdown show offending labels and dates. Both flags are required together and omitted by default, so existing comparison output remains unchanged. Unknown primary evidence is never counted as fresh, and saved provider/date labels are not authenticated.

**Source checkout only:** To review or share the human-readable evidence table as a Markdown file without PowerShell redirection or character-encoding surprises, use:

```bash
uv run mcp-trendpulse-cli brief-pack --keyword "ChatGPT" --keyword "Claude" --market US --format markdown --output-file brief-evidence.md
```

The Markdown file matches the normal terminal report, including its source and comparability cautions. For two-market requests, a final **cross-market evidence coverage** table shows the count of keywords with valid primary observations, each market's latest validated date, and whether a market was unavailable, skipped after a rate limit, or had missing growth. It compares evidence availability and freshness, **not** the normalized index values across markets or a keyword ranking. `--allow-partial` saves an explicitly incomplete Markdown report with a nonzero exit status; a strict provider failure does not create a file. This is reviewable evidence for a human-produced brief, not an automatically completed customer report.

**Source checkout only:** For review in spreadsheets, use `--format csv` instead of JSON. The output has one row per requested keyword and market, includes source/timeframe/comparability metadata, latest observation dates, growth basis, missing-value status, and warnings. Text beginning with spreadsheet formula characters is prefixed with an apostrophe to prevent formula execution. For example:

```bash
uv run mcp-trendpulse-cli brief-pack --keyword "ChatGPT" --keyword "Claude" --market US --format csv --output-file evidence.csv
```

With `--allow-partial`, failed and rate-limit-skipped markets remain explicit CSV rows and the process exits nonzero; the `incomplete`, `error_code`, and `error_component` columns must be checked before using the evidence. The `observation_alignment` column distinguishes a keyword whose latest valid observation matches the market's latest (`market_latest`) from one with an older valid observation (`older_than_market_latest`); it is blank when no valid keyword observation exists. This is relative alignment within one market request, not an absolute freshness guarantee. The incomplete file is still saved for review, with a warning on stderr. In strict mode, a provider failure creates no evidence file. PowerShell 5.1's native `>` redirection writes UTF-16LE rather than UTF-8; use `--output-file` for a guaranteed UTF-8 capture. This export is an attributed normalized index table, **not** search volume, autonomous research, or a completed customer brief.

**Source checkout only (not yet a published package feature):** Add `--allow-partial` to retain successfully fetched markets if a provider timeout, rate limit, or outage interrupts a two-market evidence pack. A partial JSON result remains one valid document with `incomplete: true`, usable records in `markets`, and explicit `failed_markets` error codes; Markdown ends with an **INCOMPLETE EVIDENCE** warning. For nondefault timeframes, a failed secondary growth request leaves successful primary Trends observations in `markets` with null growth, a warning, and a `failed_markets` entry marked `component: "growth"`. The command still exits nonzero, so consumers must check the exit status and must not present this as a complete brief. If rate-limited, remaining markets are **not queried**. Without the flag, the original strict behavior and full-success JSON schema remain unchanged. No automatic retries, extra polling, or recommendations are added.

**Windows PowerShell 5.1 evidence capture:** the native `--output-file` option above is the simplest cross-shell choice. The earlier source-checkout Python capture example is still available when a separate schema-v1 validation step is desired:

```powershell
uv run python examples/capture_brief_pack_json.py --output evidence.json --keyword "ChatGPT" --keyword "Claude" --market US
if ($LASTEXITCODE -ne 0) { Write-Warning "Evidence generation failed or is incomplete; inspect before use." }
```

The example executes one local CLI request, validates schema-v1 JSON, writes the original UTF-8 bytes to a **new** file without overwriting existing evidence, and preserves a nonzero CLI exit status. With `--allow-partial`, valid but incomplete JSON is saved for review and returns nonzero; it is **not** considered a complete brief. It performs no retries or provider calls beyond that single requested CLI invocation.

For an explicitly requested one-keyword, one-market Trend Watch series instead of a brief summary, use `brief-pack --format watch-json --watch-evidence-file ./trend-series.json`. The new UTF-8 file can be passed to the offline `watch evaluate --evidence` command without hand-editing; existing files and invalid/hourly evidence are rejected. Use `watch evaluate --dry-run` to preview a decision without consuming the local alert cooldown; a concurrent real evaluation may differ. Use `watch backtest --id ID --evidence ./trend-series.json` for a non-recording, retrospective threshold/cooldown simulation, optionally overriding growth, minimum interest, window, or cooldown in a read-only what-if scenario. Add `--compare-baseline` with an override to compare saved versus proposed hypothetical alert dates/counts directly; different window sizes change the number of eligible evaluations, not predictive accuracy. Add `--format csv --output-file watch-backtest.csv` to export a spreadsheet-ready summary and hypothetical alert-date differences as a new BOM-free UTF-8 file, without overwriting existing files; JSON remains the default. This is a manual Google Trends fetch, not automatic monitoring or proof of historical source availability. See `docs/trend-watch.md`.

**Source checkout only:** For multiple local Watch rules, use `uv run --no-sync mcp-trendpulse-cli watch preview-all --evidence ./us-ai.json --evidence ./gb-cloud.json --format csv` to preview all saved rules against up to 12 distinct declared keyword/market series without running each rule by ID. The offline JSON (default) or spreadsheet-safe CSV reports each rule separately, including `missing_evidence` for unmatched rules; matching rules with different thresholds share the same input series but retain independent decisions. Add `--format markdown` for a human-readable review with manual follow-up candidates, missing-evidence gaps, and other evaluated rules. That review groups decisions but does not rank unrelated keyword/market series or suggest products without independent corroboration. A maximum of 100 saved rules are previewed. No alert or cooldown is recorded and no providers are queried. The user-supplied normalized series, dates and labels are unauthenticated and do not establish demand or real-time market growth.

Add `--output-file ./watch-triage.md` to `watch preview-all --format markdown` (or use `.json`/`.csv` with the matching format) to save the exact offline report as a new UTF-8 file for manual review. Existing files are never overwritten, invalid evidence does not create a partial report, and the saved preview never records alerts or cooldowns.

The CLI and MCP surfaces are intentionally documented separately because they do not expose the same command set.

**Optional offline freshness gate:** `uv run mcp-trendpulse-cli brief-review --evidence evidence.json --as-of 2026-11-19 --max-age-days 7 --format markdown` evaluates each observed keyword's saved primary-observation date against an **explicit, reproducible reference date**. Observations older than seven calendar days or dated after the declared reference date are listed for human review (exit 2), even when every keyword otherwise has primary coverage. This is available in text, JSON, CSV and Markdown, including safe new-file `--output-file` exports; JSON contains the exceptions and CSV reports per-market stale/future counts. Both flags are required together; omitting them preserves existing readiness behavior. Missing primary observations remain unknown, never treated as fresh; saved dates and source labels are unauthenticated, and the check makes no network calls or claims about actual provider publication freshness.

## Development

Install the project with its development dependencies using your preferred Python environment, then run the unit suite:

```bash
python -m pytest
```

The default pytest configuration excludes live integration tests.

Run live provider tests explicitly with:

```bash
python -m pytest tests/integration -m integration
```

Browser-marked integration tests require Playwright Chromium to be installed.

Run Ruff checks with:

```bash
ruff check .
```

## MCP Inspector

Run the published-from-GitHub server through the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector uvx --from git+https://github.com/AKzar1el/mcp-trendpulse.git mcp-trendpulse
```

For a local checkout:

```bash
npx @modelcontextprotocol/inspector uv run mcp-trendpulse
```

## Packaging

A GitHub Actions workflow builds and publishes Python distributions through PyPI Trusted Publishing when a GitHub release is published. The current stable package can be run with `uvx mcp-trendpulse`; use the GitHub `uvx --from ...` form only when you intentionally want repository-head code.

## Security notes

Article retrieval is an outbound network feature and is treated as untrusted input. The implementation validates HTTP(S) targets, rejects private and non-routable destinations, checks redirect targets, enforces response-size limits, and applies browser-route validation when Playwright is used.

If you deploy TrendPulse remotely, retain these controls and add deployment-level rate limiting, request timeouts, observability, and resource limits rather than relying only on application defaults.

For responsible disclosure instructions, see [SECURITY.md](SECURITY.md).

## Optional free market intelligence (separate MCP)

Market-intelligence source adapters are **opt-in only** and do not change the
default TrendPulse tools, hosted MCP, or scheduled workers. Use the existing CLI:

```bash
mcp-trendpulse-cli intelligence sources
mcp-trendpulse-cli intelligence settings status
mcp-trendpulse-cli intelligence settings guide openalex
```

Start the standalone read-only MCP only when explicitly wanted:

```bash
python -m mcp_trendpulse.intelligence_mcp
```

See [source verification and free-tier rules](docs/intelligence-free-sources.md)
and [safe provider settings and self-hosted RSSHub](docs/intelligence-provider-settings.md).
The separate MCP also provides 18 opportunity investigation lanes, deterministic
buyer/evidence triage, bounded trend checks, and a time-aware outcome backtest.
These rank research priorities, **not** startup success probabilities. See
[opportunity evaluation and chaos test matrix](docs/intelligence-opportunity-evaluation.md).
In source checkouts containing this change, baseline `intelligence_discover_current`
accepts `compact=True` for a smaller MCP decision brief containing candidates,
source coverage and buyer/coverage cautions while omitting detailed
research/notice samples. This option does **not** exist in the currently
installed v0.3.1 runtime until a later authorized release and source reload.
The default `compact=False` response remains unchanged; requesting optional
discovery enrichments requires the full view. The compact view does not make
the evidence more conclusive or change provider request quotas.

### Local V1/V2/V3 unified testing (source checkout only)

For **supervised local evaluation** of all 16 community + 17 intelligence +
2 MJAU V3 tools through a **single** stdio MCP client, explicitly run:

```bash
python -m mcp_trendpulse.mjau_v3.unified_mcp
```

This is deliberately **excluded from the public package** and must not be
registered, automatically started, or exposed on a public endpoint. It does
not replace the default 16/33-tool servers or deploy V3. V3 remains plan-only
unless a user explicitly chooses `execute=True`, and source-rights and
independent evaluation gates remain open. See the
[combined MCP acceptance protocol](docs/qa/trendpulse-unified-v123-acceptance-20261123.md).
The [current source-rights, real-source accuracy and conformance review](docs/qa/v3-release-gate-and-real-source-benchmark-20261123.md)
is deliberately **not** a public release certificate. Independent outside-human
[accuracy/usability review (#426)](https://github.com/AKzar1el/mcp-trendpulse/issues/426)
and per-original-feed
[OSV distribution-rights review (#427)](https://github.com/AKzar1el/mcp-trendpulse/issues/427)
remain open; passing automated tests does not satisfy either gate.

For repeated local research, **keep the one client-managed stdio process
connected** rather than launching a new 35-tool Python server for every
question. Cold startup is dominated by shared FastMCP and V1 community
imports, not by registering the two V3 tools. This is a workflow improvement,
not a claim that V3 accelerates a direct first-time provider API lookup.
To reproduce a bounded, network-free import attribution test:

```bash
python scripts/measure_unified_cold_start.py --rounds 3
python scripts/measure_unified_warm_dispatch.py
```

The diagnostic alternates the full 35-tool import with the separate
`python -m mcp_trendpulse.mjau_v3.mcp` **V3-only** two-tool import.
Those modes have different capabilities and must not be called equivalent
A/B research workflows. For actual integrated tasks, continue using the
35-tool entrypoint above. The [startup attribution report](docs/qa/v3-startup-attribution-20261123.md)
records the observed bounds and remaining limits.

ChatGPT web needs a separately authenticated remote MCP connection or secure
tunnel; the local stdio process is **not** a public plugin endpoint.
No API secret should be provided in chat or committed into the repository.

## Roadmap

Current production-readiness priorities are:

1. Keep documentation, packaging metadata, and generated MCP manifests coherent with the live tool surface.
2. Keep CI, package validation, and dependency/runtime coverage aligned with what users actually install.
3. Preserve provider boundaries so upstream sources can be changed without rewriting the MCP layer.
4. Harden and operate the existing stateless Streamable HTTP transport while preserving local stdio operation.
5. Refine the existing smaller hosted tool surface for ChatGPT/Codex against real deployment and buyer evidence.
6. Complete provider authorization and integrate the hosted service with the DigestSEO application and operational stack.
7. Package and test the hosted MCP as an OpenAI plugin only after the managed service is production-ready.

## License

MIT. See [LICENSE](LICENSE).

<!-- mcp-name: io.github.AKzar1el/mcp-trendpulse -->


### Opt-in current activity hunter (free-only)

The optional intelligence extension includes `mcp-trendpulse-cli intelligence hunt --execute`, an evidence-attributed, **current-first** opportunity watchlist. It fetches bounded publicly available signals from fixed source adapters and ranks recent topical observations without requiring historical training data or claiming startup-success probabilities. For reproducible future comparisons, add `--record-history` to store limited local hashed metadata. The separate optional MCP tool is `intelligence_hunt_current`; the community MCP and existing scheduled worker are unchanged. See [opportunity evaluation](docs/intelligence-opportunity-evaluation.md).


### Seedless, free current-theme discovery

The optional intelligence MCP/CLI now offers `intelligence discover --execute --format text`. It collects bounded **recent OpenAlex research, CFPB public complaint categories and TED procurement notices**, and identifies repeated original-source themes without any preset industry keywords. It requires no historical database and never infers growth, verified buyers or revenue from source popularity. To accumulate optional hashed candidate history, add `--record-history`. The normal 16-tool community MCP and scheduled worker are unchanged. See [opportunity evaluation](docs/intelligence-opportunity-evaluation.md).
