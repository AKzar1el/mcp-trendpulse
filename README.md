# mcp-trendpulse

[![MCP Version](https://img.shields.io/badge/MCP-Protocol-blue.svg)](https://modelcontextprotocol.io)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A powerful, robust Model Context Protocol (MCP) server that connects AI models to Google News RSS feeds and Google Trends. Easily pull historical weekly interest curves, calculate keyword growth rates, fetch trending queries, and analyze/summarize related articles using LLMs and NLP.

## Features

- **Google News Integration**: Trawl feeds for articles by keyword, location, or topic, and fetch top news stories.
- **Advanced Trends Analysis**: Pull interest history for explicit Google Trends windows (such as 12 months, five years, or an exact date range), calculate growth velocities over custom windows, and retrieve real-time trending keywords.
- **NLP & LLM Summarization**: Summarize article payloads and extract key concepts using client-side LLM sampling or local NLP.
- **Windows-Safe & Robust**: Fully handles local session state, rates limits, and includes a fallback mechanism for sites that are difficult to scrape.

## Installation

### Using uv/uvx (recommended)

When using [`uv`](https://docs.astral.sh/uv/) no specific installation is needed. The
project is currently run directly from GitHub because it is not yet published to PyPI:

```bash
uvx --from git+https://github.com/AKzar1el/mcp-trendpulse.git mcp-trendpulse
```

Once a release is published to PyPI, the shorter command will also work:

```bash
uvx mcp-trendpulse
```

#### Publishing to PyPI

The included GitHub Actions workflow uses PyPI Trusted Publishing, so no API token
is stored in GitHub. Before the first release, the PyPI project owner must add a
pending publisher at [PyPI publishing settings](https://pypi.org/manage/account/publishing/):

- Owner: `AKzar1el`
- Repository: `mcp-trendpulse`
- Workflow: `publish.yml`
- Environment: leave blank

After that one-time setup, create and publish a GitHub release. The workflow builds
and publishes the package automatically. If the owner cannot use PyPI Trusted
Publishing, a PyPI API token can be stored as the `PYPI_API_TOKEN` repository secret
and passed to the publishing action instead.

### Using PIP

```bash
pip install mcp-trendpulse
```
After installation, you can run it as a script using:

```bash
python -m mcp_trendpulse
```

## Configuration

### Configure for Claude.app

Add to your Claude settings:

<details>
<summary>Using uvx</summary>

```json
{
  "mcpServers": {
    "mcp-trendpulse": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/AKzar1el/mcp-trendpulse.git", "mcp-trendpulse"]
    }
  }
}
```
</details>

<details>
<summary>Using pip installation</summary>

```json
{
  "mcpServers": {
    "mcp-trendpulse": {
      "command": "python",
      "args": ["-m", "mcp_trendpulse"]
    }
  }
}
```
</details>

### Configure for VS Code

<details>
<summary>Using uvx</summary>

```json
{
  "mcp": {
    "servers": {
      "mcp-trendpulse": {
        "command": "uvx",
        "args": ["--from", "git+https://github.com/AKzar1el/mcp-trendpulse.git", "mcp-trendpulse"]
      }
    }
  }
}
```
</details>

<details>
<summary>Using pip installation</summary>

```json
{
  "mcp": {
    "servers": {
      "mcp-trendpulse": {
        "command": "python",
        "args": ["-m", "mcp_trendpulse"]
      }
    }
  }
}
```
</details>

### Configure for Cursor Editor

Cursor supports MCP configuration globally or per-project:

- **Global Config**: Edit `%USERPROFILE%\.cursor\mcp.json` (Windows) or `~/.cursor/mcp.json` (macOS/Linux).
- **Project Config**: Create a `.cursor/mcp.json` file inside your project root.

Add the following to the `mcpServers` object:

```json
{
  "mcpServers": {
    "mcp-trendpulse": {
      "command": "python",
      "args": ["-m", "mcp_trendpulse"]
    }
  }
}
```
*(Alternatively, you can open Cursor Settings -> Features -> MCP, and click "Add New Global MCP Server" to set it up via the UI).*


### Configure for Gemini / Antigravity IDE

If you are pair programming with Gemini in Antigravity IDE, add the server to your settings file at `%APPDATA%\.gemini\antigravity-ide\mcp_config.json`:

```json
{
  "mcpServers": {
    "mcp-trendpulse": {
      "command": "python",
      "args": ["-m", "mcp_trendpulse"]
    }
  }
}
```


### Configure for ChatGPT (OpenAI)

Because ChatGPT resides in the cloud, it requires your local MCP server to be exposed via a secure HTTPS tunnel (e.g., using `ngrok` or similar):

1. **Expose Server via Tunnel**:
   Start your local MCP server using an HTTP/SSE bridge or expose its stdio endpoint using a secure tunnel tool.
2. **Enable Developer Mode in ChatGPT**:
   Open the ChatGPT desktop app, go to **Settings → Apps & Connectors**, and toggle on **Developer Mode**.
3. **Register the Connector**:
   Click **+ New Server** (or "Create Connector") and paste the public HTTPS URL where your tunnel is hosted.

### Environment Variables and Proxies

If you experience rate limits (`429 Client Error`) from Google Trends, or if your server is running in an environment without direct internet access, you can configure environment variables and proxies in one of two ways:

#### Option A: Using a `.env` file (Recommended)
You can create a `.env` file in the workspace directory (where the server is executed) and define the variables there. The server will automatically load them at startup:

```env
HTTP_PROXY=http://your-proxy-address:port
HTTPS_PROXY=http://your-proxy-address:port
GOOGLE_TRENDS_DELAY=2.0
```

#### Option B: Injecting via the client configuration
You can add environment variables directly to the `"env"` object in your Claude Desktop or VS Code JSON configuration:

```json
      "env": {
        "HTTP_PROXY": "http://your-proxy-address:port",
        "HTTPS_PROXY": "http://your-proxy-address:port",
        "GOOGLE_TRENDS_DELAY": "2.0"
      }
```

On Windows, it is also recommended to pass system environment variables like `PATH`, `USERPROFILE`, `LOCALAPPDATA`, and `APPDATA` under the `"env"` block to ensure that internal Chromium browsers (used by Playwright) resolve and execute correctly:

```json
      "env": {
        "PATH": "C:\\Windows\\system32;C:\\Windows;C:\\Windows\\System32\\Wbem;C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\;C:\\Users\\<Username>\\AppData\\Local\\Microsoft\\WindowsApps;C:\\Users\\<Username>\\AppData\\Local\\Programs\\uv",
        "USERPROFILE": "C:\\Users\\<Username>",
        "LOCALAPPDATA": "C:\\Users\\<Username>\\AppData\\Local",
        "APPDATA": "C:\\Users\\<Username>\\AppData\\Roaming"
      }
```


## Tools

The following MCP tools are available:

| Tool Name            | Description                                                                                          |
|----------------------|------------------------------------------------------------------------------------------------------|
| **get_news_by_keyword**| Search for news using specific keywords.                                                             |
| **get_news_by_location**| Retrieve news relevant to a particular location.                                                   |
| **get_news_by_topic**| Get news based on a chosen topic.                                                                    |
| **get_top_news**     | Fetch the top news stories from Google News.                                                         |
| **get_trending_terms**| Return trending keywords from Google Trends for a specified location.                                |
| **get_trends**       | Pull Google Search interest over an explicit window to inspect growth and seasonality curves.   |
| **get_growth**       | Measure how much search interest changed over custom periods (e.g. 3M, 1Y) and compare growth side-by-side.|
| **get_ranked_trends**| Get a ranked list of the highest-volume or fastest-growing keywords on Google Search right now.      |
| **get_top_trends**   | Discover top trending topics on Google Trends right now without requiring a keyword query.           |

All of the news related tools have an option to summarize the text of the article using LLM Sampling (if supported) or NLP

### Choosing a useful Trends window

`get_trends` accepts an explicit `timeframe` and an optional Google Trends category ID (`cat`). Use `get_categories` to discover category IDs. An explicit `timeframe` overrides the legacy `data_mode` hint.

```json
{
  "keyword": ["technical SEO audit", "AI SEO audit"],
  "geo": "US",
  "source": "google search",
  "timeframe": "today 12-m",
  "cat": 0
}
```

Supported ranges include standard windows such as `today 12-m` and `today 5-y`, custom intervals such as `today 90-d`, `all`, and exact date ranges such as `2021-01-01 2026-01-01`. Use an explicit range whenever you need reproducible comparisons; do not infer absolute search volume from normalized 0–100 values.


## CLI
MCP tools are exposed through the MCP server. The separate Click CLI currently exposes only the commands shown below, which can be run from the command line using `uv`.

```bash
uv run mcp-trendpulse-cli
Usage: mcp-trendpulse-cli [OPTIONS] COMMAND [ARGS]...

  Find and download news articles using Google News.

Options:
  --help  Show this message and exit.

Commands:
  keyword   Find articles by keyword using Google News.
  location  Find articles by location using Google News.
  top       Get top news stories from Google News.
  topic     Find articles by topic using Google News.
  trending  Returns google trends for a specific geo location.
```

## Debugging

```bash
npx @modelcontextprotocol/inspector uvx --from git+https://github.com/AKzar1el/mcp-trendpulse.git mcp-trendpulse
```

To run from within locally installed project:

```bash
cd path/to/mcp-trendpulse
npx @modelcontextprotocol/inspector uv run mcp-trendpulse
```

## Testing

```bash
cd path/to/mcp-trendpulse
python -m pytest
```
