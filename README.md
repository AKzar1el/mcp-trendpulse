# mcp-trendpulse

[![MCP](https://img.shields.io/badge/Model%20Context%20Protocol-MCP-blue.svg)](https://modelcontextprotocol.io)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**TrendPulse** is a Python Model Context Protocol (MCP) server for researching current news and search-interest trends. It combines Google News discovery and article extraction with Google Trends analysis so MCP clients can inspect what is trending, compare keyword momentum, explore related demand, and add current-news context to research workflows.

The project currently ships as a **community/self-hosted MCP server** and also contains the implementation for a separate **hosted TrendPulse by DigestSEO** surface for remote MCP clients such as ChatGPT and Codex. The hosted layer uses a smaller, goal-oriented tool surface while the community server keeps the full low-level research toolkit available to developers.

> **Project status:** the local/community server is usable today. The DigestSEO-hosted MCP and public OpenAI plugin are not released yet and should not be treated as available endpoints.

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

### Run directly from GitHub with `uvx` (recommended)

The package is not yet published to PyPI, so the most direct installation path is:

```bash
uvx --from git+https://github.com/AKzar1el/mcp-trendpulse.git mcp-trendpulse
```

After a PyPI release exists, the shorter form will be:

```bash
uvx mcp-trendpulse
```

### Install with pip from a checkout

```bash
git clone https://github.com/AKzar1el/mcp-trendpulse.git
cd mcp-trendpulse
python -m pip install .
python -m mcp_trendpulse
```

## Browser fallback

News/article tools can fall back to Playwright when ordinary retrieval cannot extract a usable article. Installing the Python `playwright` package does not install Chromium automatically.

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

### Claude Desktop

Using `uvx` directly from GitHub:

```json
{
  "mcpServers": {
    "mcp-trendpulse": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/AKzar1el/mcp-trendpulse.git",
        "mcp-trendpulse"
      ]
    }
  }
}
```

### VS Code

```json
{
  "mcp": {
    "servers": {
      "mcp-trendpulse": {
        "command": "uvx",
        "args": [
          "--from",
          "git+https://github.com/AKzar1el/mcp-trendpulse.git",
          "mcp-trendpulse"
        ]
      }
    }
  }
}
```

### Cursor

Cursor supports global and project MCP configuration. Add the server to the relevant `mcp.json` configuration:

```json
{
  "mcpServers": {
    "mcp-trendpulse": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/AKzar1el/mcp-trendpulse.git",
        "mcp-trendpulse"
      ]
    }
  }
}
```

### ChatGPT and other cloud MCP clients

The repository now includes a dedicated stateless Streamable HTTP ASGI entry point at `mcp_trendpulse.asgi:app`. This is separate from the Community stdio entry point, which remains unchanged.

For controlled local/private testing you can run the ASGI app with Uvicorn or use the provided container. See [`deploy/README.md`](deploy/README.md) for the hardened container, Host/Origin allowlists, Chromium sandbox requirements, health/readiness endpoints, and reverse-proxy notes.

The DigestSEO-hosted endpoint and public ChatGPT app are still **not released**. Hosted deployments now support fail-closed Clerk OAuth authentication; do not expose the remote transport publicly unless Clerk issuer/JWKS/audience settings, the public base URL, and the Host/Origin allowlists are configured for that deployment.

## Configuration

TrendPulse loads environment variables from the process environment and from a local `.env` file when present.

Useful variables include:

```env
HTTP_PROXY=http://your-proxy-address:port
HTTPS_PROXY=http://your-proxy-address:port
GOOGLE_TRENDS_DELAY=2.0
```

`GOOGLE_TRENDS_DELAY` controls the request delay used by the current Trends provider. Proxy variables can be useful when the upstream service rate-limits or blocks a particular network.

Remote deployments also support `TRENDPULSE_HTTP_PATH`, `TRENDPULSE_HTTP_ALLOWED_HOSTS`, `TRENDPULSE_HTTP_ALLOWED_ORIGINS`, and `TRENDPULSE_BROWSER_SANDBOX`. The container enables Chromium sandboxing explicitly; local Community runs retain the Playwright-compatible default unless you opt in.

Do not commit secrets, private proxy credentials, or machine-specific `.env` files.

## MCP tools

The community MCP server currently exposes **16 tools**.

### News tools

| Tool | Purpose |
| --- | --- |
| `get_news_by_keyword` | Find recent news articles matching a keyword. |
| `get_news_by_location` | Find recent news associated with a location. |
| `get_news_by_topic` | Find recent news for a supported Google News topic. |
| `get_top_news` | Retrieve top Google News stories. |
| `get_news_by_site` | Find recent news from a specific publisher domain. |
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
| `get_categories` | Retrieve Google Trends category IDs and names. |

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

The separate Click CLI exposes a smaller news-oriented command set than the MCP server:

```bash
uv run mcp-trendpulse-cli --help
```

Current CLI commands:

```text
keyword
location
top
topic
trending
```

The CLI and MCP surfaces are intentionally documented separately because they do not expose the same command set.

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

A GitHub Actions workflow is already present for building and publishing Python distributions through PyPI Trusted Publishing when a GitHub release is published. Until the first package release exists, use the GitHub `uvx --from ...` command shown above.

## Security notes

Article retrieval is an outbound network feature and is treated as untrusted input. The implementation validates HTTP(S) targets, rejects private and non-routable destinations, checks redirect targets, enforces response-size limits, and applies browser-route validation when Playwright is used.

If you deploy TrendPulse remotely, retain these controls and add deployment-level rate limiting, request timeouts, observability, and resource limits rather than relying only on application defaults.

## Roadmap

Current production-readiness work is focused on:

1. Keeping documentation, packaging metadata, and generated MCP manifests coherent with the live tool surface.
2. Adding continuous integration for unit tests and static checks.
3. Separating provider access from TrendPulse's domain logic so providers can be changed without rewriting the MCP layer.
4. Adding a production remote HTTP transport while preserving local stdio operation.
5. Designing a smaller high-level hosted tool surface for ChatGPT/Codex.
6. Integrating the hosted service with the DigestSEO application and operational stack.
7. Packaging and testing the hosted MCP as an OpenAI plugin only after the service is production-ready.

## License

MIT. See [LICENSE](LICENSE).
