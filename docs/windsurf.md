# Devin Desktop / Devin Local and legacy Windsurf

**Devin Desktop (Devin Local) and older Windsurf Cascade use different MCP configuration locations.** Do not put Devin Local server settings in Windsurf's legacy `~/.codeium` directory.

## Devin Desktop / Devin Local (current)

In Devin Desktop, open **Agents > Customize > MCPs** and select the desired installation scope. For a user-wide local stdio server, merge the entry below into `~/.config/devin/mcp_config.json`. Project configuration instead belongs in `.devin/mcp_config.json`; `.devin/mcp_config.local.json` is the private project override.

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

This runs the published free Community MCP from PyPI over local stdio. Install `uv`/`uvx` first and use Python 3.11 or newer. Keep other existing `mcpServers` entries when merging the configuration. Alternatively, use the [Devin CLI plugin installation](../README.md#devin-cli-and-devin-desktop) described in the README.

Confirm the server appears under **Customize > MCPs**, refresh the list if necessary, and inspect the available tools before making a low-impact read-only news or trend request.

## Legacy Windsurf Cascade

For an *existing legacy Windsurf configuration* that still uses the older Cascade settings directory, merge this entry into `~/.codeium/windsurf/mcp_config.json`:

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

Do not assume this legacy path configures current Devin Desktop. Follow the local client's MCP settings if its configuration has been migrated.

## Verify

For legacy Windsurf, reload the client after changing the config, open Cascade's MCP settings, confirm `mcp-trendpulse` starts, then inspect its tool list. A safe first check is a read-only Google News or Google Trends query.

- PyPI: https://pypi.org/project/mcp-trendpulse/
- Repository: https://github.com/AKzar1el/mcp-trendpulse
- Official MCP Registry ID: `io.github.AKzar1el/mcp-trendpulse`
- Current Devin Local MCP configuration and scopes: https://docs.devin.ai/desktop/devin-local/customizations#configuration
