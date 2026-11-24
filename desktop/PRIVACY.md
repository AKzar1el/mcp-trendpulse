# TrendPulse Community MCP Privacy Notice

Last updated: September 19, 2026

This notice applies to the open-source TrendPulse Community MCP package and its local `stdio` execution path, including installation through compatible clients such as Kiro, Cursor, Claude, VS Code, and other MCP clients. It does not describe an unreleased hosted TrendPulse service.

## What TrendPulse processes

TrendPulse processes the inputs you provide to its tools, such as keywords, locations, countries, time ranges, topics, publisher domains, and article URLs. When you request article extraction or summarization, it may also process the downloaded article text and metadata.

TrendPulse does not require a TrendPulse user account for the Community MCP and does not add hidden analytics or maintainer-operated telemetry to the local MCP process.

## Where data goes

TrendPulse is a research client, so some tool calls require outbound requests:

- Google Trends requests send the research inputs needed for the selected Trends query to the upstream Google Trends endpoints used by the packaged provider library.
- Google News requests send the research inputs needed for the selected news query to Google News endpoints used by the packaged news library.
- Article-content requests connect to the article URL or publisher site you selected so the page can be downloaded and parsed locally.
- If you request article summarization and your MCP client supports MCP sampling, extracted article text may be passed to the model provider configured by your MCP client. TrendPulse does not choose or operate that model provider.
- If you configure `HTTP_PROXY` or `HTTPS_PROXY`, outbound provider and article traffic may pass through the proxy you selected.

Those external services may process request metadata under their own terms and privacy notices. TrendPulse does not control their retention or logging practices.

## Storage and retention

The Community MCP does not use a maintainer-operated database and does not upload tool history to TrendPulse or DigestSEO for analytics. Normal Community MCP results are returned to your MCP client and otherwise remain subject to that client's own transcript, logging, and retention settings.

The package also includes CLI functionality that can save article data to a local JSON file when you explicitly invoke that export behavior. Those files stay on the machine and path where you chose to create them.

## Sensitive information

TrendPulse is intended for public trend, news, keyword, and market research. Avoid putting secrets, credentials, or unnecessary personal data into search terms, article URLs, proxy configuration, or other tool inputs. Your MCP client and the external services described above may receive the inputs necessary to complete a request.

## Hosted components

The repository contains code for a separate remote/hosted MCP transport, but the public Kiro/Agent Plugin configuration runs the Community MCP locally through `uvx mcp-trendpulse`. The hosted DigestSEO integration is not part of that Community MCP path and is not currently presented as a released public TrendPulse service.

## Changes and contact

This notice may be updated when the Community MCP's data flows materially change. For privacy or support questions, contact [info@tomiseregi.si](mailto:info@tomiseregi.si).
