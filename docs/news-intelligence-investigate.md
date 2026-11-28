# V4.07 — bounded news investigation

Internal experimental CLI/API; no default MCP registry or installed service change.

```sh
python -m mcp_trendpulse.news_intelligence_investigate "renewable energy"
python -m mcp_trendpulse.news_intelligence_investigate "renewable energy" --source google_news_rss --execute --format markdown
python -m mcp_trendpulse.news_intelligence_investigate "renewable energy" --source nasa_rss --execute
python -m mcp_trendpulse.news_intelligence_investigate "renewable energy" --source gdelt_timeline --execute
python -m mcp_trendpulse.news_intelligence_investigate "renewable energy" --google-capture saved-headlines.json
```

Default is plan-only (no cache or provider I/O); default selected sources are existing Google News keyword headlines and NASA recent-content context. Opt in to GDELT articles or raw timeline individually. Selecting both GDELT modes may return a cooldown outcome on the second; never wait, bypass or retry automatically. GDELT cutoff applies only to GDELT. Recent Google and NASA captures are not historical queries. Saved Google JSON is the existing list of RSS-only rows; imported query scope is unknown. Pass an independently known capture timestamp only with `--capture-time`.

One bounded operation per selected source, max 20 articles per article source, max 80 observations across sources/imports, max four imported typed batches, max two explicit optional topical extraction operations (`--extract-limit`; default zero). Extractor redirects/decoding may use more than one HTTP request, so report operation counts rather than invent exact HTTP counts. No automatic extraction of context/imports or canonical hints. Existing pinned downloader handles egress. Stop extraction after observed rate-limit/access/payment response.

Google uses the existing configured-edition keyword RSS provider and its bounded worker, with added workflow-local durable daily cap 6, pacing, nonblocking source lock, metadata-only cache (five minutes), and no auto-retry. Existing legacy endpoints are unchanged and do not participate in this new local budget. Returned counts describe the legacy filtered projection, not raw upstream response coverage; empty projection is ambiguous and is treated as unavailable. Google operation count is not a wire-level request count. GDELT/NASA reuse existing collector budgets and transport. No new dependencies or paid services.

The result contains source scopes and outcome receipts, original typed observations, separate query-scoped and combined contextual sample summaries, candidate events, dedup evidence, weighted GDELT coverage when available, optional extraction receipts and numbered source citations. JSON is machine-readable and includes a fingerprint of the complete structured result; Markdown escapes untrusted headline and URL text and includes source outcomes, sample concentration, event-candidate citations, duplicate/extraction outcomes and limitations. No full text persisted or claim verification performed. Do not interpret mixed source counts as independent corroboration or worldwide coverage. A supplied capture is not authenticated. This is not a finished production release; live provider smoke and independently labeled real-world duplicate/event accuracy remain separate gates.

MCP compatibility: the existing tool registry and default contracts remain unchanged; the structured result can support a future reviewed tool output schema (https://modelcontextprotocol.io/specification/2025-11-25/server/tools). No production registration is implied by this CLI.
