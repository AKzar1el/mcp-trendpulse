# Hosted TrendPulse operations runbook

This runbook covers the remote **TrendPulse by DigestSEO** MCP service. It does not change the Community stdio server's operational model.

## Runtime invariants

- Run the hosted service from the hardened container image.
- Keep `TRENDPULSE_BROWSER_SANDBOX=true`.
- Run one Uvicorn worker per container and scale with replicas.
- Public deployments use `TRENDPULSE_AUTH_MODE=clerk`; `disabled` is only for controlled local/private testing.
- Keep Host and Origin allowlists explicit.
- Do not make the current unofficial Trends/news providers public until the provider-authorization gate in issue #22 is resolved.

## Probes

### `/health`

Liveness only. A healthy response means the ASGI process can answer HTTP.

Expected body:

```json
{"status":"ok","service":"trendpulse-by-digestseo"}
```

### `/ready`

Readiness/configuration signal. It reports the service identity, Streamable HTTP transport, stateless mode, and active auth mode.

A public deployment is not considered ready for traffic if the endpoint reports `auth=disabled`, even if it returns HTTP 200.

Both probe responses include an opaque `x-request-id` header for incident correlation.

## Privacy-safe log events

The hosted runtime emits two TrendPulse-specific operational events.

### `mcp_http_request`

Fields:

- `request_id`
- `method`
- `status`
- `duration_ms`
- `auth`

The event must not contain request bodies, keywords, prompts, URLs, user IDs, cookies, bearer tokens, response bodies, or Search Console data.

### `provider_failure`

Fields:

- `request_id`
- `provider`
- `operation`
- `code`
- `retryable`

Expected codes are `provider_timeout`, `provider_rate_limited`, and `provider_unavailable`.

Do not add raw upstream exception text to this event unless it has been explicitly reviewed for credentials, URLs, user data, and third-party response content.

### `provider_metrics`

The Community and Hosted Google Trends provider share bounded, **process-local**
aggregate counters. Every 128 recorded events, the provider logs a JSON snapshot
under `provider_metrics` with only approved counter names and latency buckets
(milliseconds: 250, 1000, 5000, 20000, >20000). These logs never contain
keywords, URLs, user identities, or provider payloads.

- `trends_http_request` and `trends_http_429` count outbound TrendSpy HTTP calls and rejected responses, including batch POST operations.
- `trends_cooldown_open` and `trends_cooldown_block` show throttling pressure.
- `trends_cache_hit`, `trends_cache_miss`, `trends_cache_wait`, and `trends_cache_eviction` show local cache effectiveness.
- `trends_shared_cache_hit`, `trends_shared_cache_miss`, `trends_shared_cache_write`, `trends_shared_queue_reject`, and `trends_shared_state_fallback` describe the optional same-host coordination layer.
- `news_feed_request`, `news_feed_error`, `news_feed_429`, and `news_feed_timeout` describe GNews lookups. **These are logical feed operations**, not a claim to count all HTTP retries or subsequent publisher/article fetches.

Operators can inspect an in-process snapshot without exposing a new public HTTP
endpoint: `from mcp_trendpulse.provider_metrics import provider_metrics; print(provider_metrics.snapshot())`.
The snapshot resets on process restart and is not aggregated across replicas.
Use the configured log collector for cross-instance trends; do not enable
per-request query or URL logging to troubleshoot quotas.

### Optional same-host coordination

Set `TRENDPULSE_SHARED_STATE_DIR` to an **absolute directory on private local storage**
for every TrendPulse process you intend to coordinate. If unset, no SQLite
state or cache files are created. A fresh per-directory 32-byte HMAC key
protects cached query identities against casual dictionary inspection; only
numeric search-interest series and timestamps are stored, never raw keywords,
user IDs, URLs, or publisher content. Restrict the directory and backups to
the account running the MCP. The SQLite cache holds at most 256 series with
freshness bounds of 2 minutes, 30 minutes, 90 minutes, or two hours depending
on the requested Trends window. Request scheduling allows at most 12 seconds
of queueing before failing fast rather than exhausting hosted request timeouts.
Errors in the shared store fall back to local pacing and are counted.

SQLite WAL is designed here for one trusted host on local disk. **Do not**
point independent Kubernetes nodes or containers at an unsafe network
filesystem and assume it is a distributed rate limiter. This feature also
does not authorize provider access for the still-gated public hosted edition.

## Initial monitoring signals

These are starting operational thresholds, not contractual SLOs. Re-baseline them after real production traffic exists.

### Availability

Investigate immediately when:

- `/health` fails for two consecutive probe intervals;
- `/ready` fails or reports an unexpected auth mode;
- container restart/OOM frequency increases; or
- MCP HTTP 5xx responses exceed 2% over a five-minute window with meaningful traffic.

### Authentication

Investigate a sustained increase in 401 responses separately from provider failures. Common causes:

- Clerk issuer/JWKS configuration drift;
- wrong OAuth audience;
- expired or invalid reviewer/client tokens;
- key rotation/JWKS reachability problems.

Do not log or request bearer tokens for diagnosis.

### Provider health

Group `provider_failure` by provider, operation, and code. A spike across many request IDs usually indicates an upstream problem rather than a single user request.

- `provider_rate_limited`: reduce pressure and inspect provider quota/policy before retrying aggressively.
- `provider_timeout`: inspect upstream latency/network conditions.
- `provider_unavailable`: inspect provider status/parser/API compatibility.

TrendPulse currently marks these failures retryable for clients but does not perform an unbounded automatic retry loop.

### Latency

Track `duration_ms` percentiles for `/mcp` requests by status. Do not set an aggressive latency SLO before the final hosted provider is selected.

As a provisional incident signal, investigate sustained p95 latency above 45 seconds because hosted tool timeouts are currently bounded around 60–75 seconds.

## Incident triage

1. Check `/health` and `/ready` from the same network path as the client.
2. Use the reported `x-request-id` to locate the matching `mcp_http_request` event.
3. Classify by HTTP status:
   - 401: OAuth/token configuration.
   - 403/421/400 before MCP handling: Origin/Host/content-type transport protection.
   - 5xx: runtime/infrastructure failure.
   - successful HTTP with tool error: inspect correlated `provider_failure` events.
4. Check container restarts, memory pressure, and Chromium launch failures.
5. Check upstream provider status/quota only after the local runtime is healthy.
6. If the incident began immediately after a deployment or configuration change, use `docs/rollback.md`.

## Deployment smoke checks

A candidate image should pass, in order:

1. container starts as UID 10001;
2. `/health` returns 200;
3. `/ready` returns 200 and the expected auth mode;
4. packaged NLTK data is available without runtime download;
5. sandboxed Chromium launches with the pinned seccomp profile;
6. Streamable HTTP MCP initialize succeeds in the intended auth mode;
7. tool catalog is exactly the six hosted tools;
8. no new warning/error burst appears during smoke traffic.

The repository's `Container` workflow automates the first six checks in controlled private mode.

## Secret/configuration handling

Never write these values to logs, issues, test fixtures, or repository files:

- Clerk secrets or bearer tokens;
- OAuth client secrets;
- Google/Search Console access tokens;
- reviewer credentials;
- future official Google Trends API credentials.

Configuration changes to issuer, audience, public base URL, allowlists, or provider credentials should be treated as deployable changes with a rollback record.

## Escalation information to capture

For an incident report, capture only:

- deployment commit/image digest;
- UTC start/end time;
- affected endpoint/tool name;
- status/error code counts;
- sanitized provider/operation codes;
- request IDs;
- container restart/resource information;
- configuration version/change identifier.

Do not paste user inputs, article content, OAuth tokens, or private Search Console data into the incident report.
