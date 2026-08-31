# Windsurf / Devin Desktop

TrendPulse works with Windsurf / Devin Desktop through Cascade's native MCP support.

## Local stdio setup

Open `~/.codeium/windsurf/mcp_config.json` and merge this server into the existing `mcpServers` object:

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

This uses the published PyPI package. Do not replace existing MCP entries when adding this configuration.

## Verify

Reload Windsurf after changing the config, open Cascade's MCP settings, confirm `mcp-trendpulse` starts, then inspect its tool list. A safe first check is a read-only Google News or Google Trends query.

- PyPI: https://pypi.org/project/mcp-trendpulse/
- Repository: https://github.com/AKzar1el/mcp-trendpulse
- Official MCP Registry ID: `io.github.AKzar1el/mcp-trendpulse`
- Windsurf MCP docs: https://docs.devin.ai/desktop/cascade/mcp
