# Trend Watch — local evidence evaluation (opt in)

This is an intentionally **manual, local-only** alert-rule feature. It never
contacts Google, checks a website, creates a scheduler, sends notifications, or
enables TrendPulse's still-gated public hosted service. Only explicit
`watch evaluate` commands can cause an alert decision.

## Add a rule

```bash
uv run mcp-trendpulse-cli watch create --keyword "AI research" --market US --growth-pct 30 --minimum-interest 20 --window 4 --cooldown-days 7
uv run mcp-trendpulse-cli watch list
```

The returned ID identifies a watch rule. Its keyword is stored in the
current user's local SQLite database (not uploaded to TrendPulse). Override
the default directory `~/.mcp-trendpulse/watches` with the absolute private
`TRENDPULSE_WATCH_DIR` environment variable.

## Provide your own normalized interest evidence

Prepare a UTF-8 JSON file from an **authorized and reviewed** data source,
such as a manually exported trend series. This example is fabricated and
intended only to show the expected shape:

```json
{
  "keyword": "AI research",
  "market": "US",
  "points": [
    {"date": "2026-10-12", "value": 12},
    {"date": "2026-10-13", "value": 15},
    {"date": "2026-10-14", "value": 19},
    {"date": "2026-10-15", "value": 20},
    {"date": "2026-10-16", "value": 28},
    {"date": "2026-10-17", "value": 40},
    {"date": "2026-10-18", "value": 47},
    {"date": "2026-10-19", "value": 55}
  ]
}
```

The data must be one market and one term, chronologically sorted, with valid
ISO dates and normalized scores 0–100. Rows marked `isPartial: true` are
excluded. Maximum size 256 KiB / 520 observations. Never treat interest
scores as absolute keyword volumes. Keep normalization and timeframe
consistent across both comparison windows.

```bash
uv run mcp-trendpulse-cli watch evaluate --id YOUR_RULE_ID --evidence ./trend-series.json
uv run mcp-trendpulse-cli watch remove --id YOUR_RULE_ID
```

The evaluator compares average interest across the latest `window` complete
points with the preceding `window` points. It only triggers if the relative
growth and minimum current interest meet your thresholds. An entirely zero
baseline produces `zero_baseline`, **not** an infinite-growth alert. Repeating
the same evidence cannot trigger again; the configured cooldown also prevents
rapid retriggers on newer observations. SQLite transactions make alert
recording safe when multiple local agents evaluate the same rule concurrently.

The decision is labeled *user-supplied, not independently verified*. It may
be useful for a human decision, but **is not proof of market demand**.
Article/news corroboration and Google Search Console context can be assessed
separately by the operator; this feature does not fabricate those sources.

## Why automated checks are not enabled

Automatic polling would consume upstream provider quota and needs explicit
authorization plus a documented budget. Hosted public integration remains
blocked by repository issue #22 until compliant data access is established.
This foundation is usable manually without increasing upstream traffic.
