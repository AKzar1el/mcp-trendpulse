# Hosted TrendPulse rollback procedure

This procedure is for the remote **TrendPulse by DigestSEO** service. The preferred rollback unit is the previously validated container image, not ad-hoc edits on a running instance.

## Before every production deployment

Record:

- candidate Git commit SHA;
- immutable container image digest/tag;
- previously stable image digest/tag;
- deployment timestamp;
- runtime configuration version or secure configuration snapshot reference;
- expected Clerk issuer/audience/public base URL;
- expected Host/Origin allowlists;
- expected hosted provider selection.

Do not copy secret values into the deployment record.

## Rollback triggers

Rollback is preferred over live debugging when a new deploy is followed by any of these conditions and the previous image was healthy:

- `/health` or `/ready` regression;
- MCP initialize/authentication regression;
- sustained new 5xx responses;
- Chromium can no longer launch under the sandbox/seccomp profile;
- tool catalog/schema drift;
- new provider adapter causes widespread failures;
- privacy/security regression such as sensitive log content;
- material latency/resource regression attributable to the new image.

An external provider outage with the same behavior on the previous image is not, by itself, a reason to roll back TrendPulse.

## Image-first rollback

1. Stop new rollout/progressive traffic shifts.
2. Select the last image that passed the repository CI + hardened container smoke and was known healthy in the target environment.
3. Restore the runtime configuration version that was paired with that image when configuration changed with the deploy.
4. Redeploy that immutable image digest without rebuilding it.
5. Wait for the new replica(s) to pass `/health` and `/ready`.
6. Confirm the expected auth mode is `clerk` on a public deployment.
7. Perform an authenticated MCP initialize and list the six hosted tools.
8. Confirm a sandboxed Chromium smoke check if the incident involved browser behavior.
9. Inspect `mcp_http_request` and `provider_failure` logs for new errors after traffic is restored.
10. Remove or drain the failed replica(s) only after the rollback replica(s) are ready.

## Configuration-only rollback

If the image is unchanged and the incident follows a configuration change:

1. identify the exact changed setting;
2. restore the previous secure configuration version;
3. restart/redeploy replicas so the process reloads configuration;
4. verify `/ready`, OAuth discovery, authenticated MCP initialize, and Host/Origin behavior.

High-risk settings include:

- `TRENDPULSE_AUTH_MODE`;
- `TRENDPULSE_CLERK_ISSUER` / JWKS URI / audience;
- `TRENDPULSE_PUBLIC_BASE_URL`;
- HTTP Host/Origin allowlists;
- DigestSEO context URL;
- future hosted-provider credentials/configuration.

Never work around an OAuth incident by switching a public deployment to `TRENDPULSE_AUTH_MODE=disabled`.

## DigestSEO integration boundary

TrendPulse does not own DigestSEO's D1 project database or the user's Google OAuth credentials. An MCP application rollback therefore should not mutate or roll back DigestSEO D1 data.

If only optional `project_id` / Search Console enrichment is failing:

- verify the DigestSEO control-plane endpoint independently;
- compare the failing TrendPulse image/configuration with the last known good version;
- roll back the TrendPulse image when the regression is on the client/integration side;
- follow DigestSEO's own deployment rollback process if the control-plane service itself regressed.

Do not delete user projects or disconnect Google accounts as a TrendPulse rollback mechanism.

## Provider rollback

When a hosted provider adapter changes:

1. retain the previous adapter configuration/image until the new provider is validated;
2. roll back the image/configuration rather than falling back silently to an authorization-ambiguous provider;
3. confirm the restored provider is still authorized for public hosted use;
4. rerun representative hosted tools after rollback.

Issue #22 is the authorization gate for the initial public Trends/news provider path. Do not use the Community unofficial provider as an emergency public fallback unless its hosted authorization basis has been explicitly resolved.

## Verification after rollback

Minimum acceptance checks:

- correct image digest is running;
- non-root UID 10001;
- `/health` 200;
- `/ready` 200 with `auth=clerk` for public service;
- OAuth protected-resource metadata reachable;
- valid authenticated initialize succeeds;
- invalid/missing token receives 401;
- exactly six hosted tools are listed;
- sandboxed Chromium launches;
- NLTK resources are packaged;
- no new 5xx/provider-failure burst;
- request logs contain correlation metadata but no request bodies/tokens.

## After the incident

Create a short incident record containing the failed and restored image digests, timestamps, request IDs, sanitized error categories, root cause, and the regression test or guardrail added afterward.

Do not promote the failed image again until the original failure is reproducible or otherwise understood and the fix has passed normal CI plus the hardened container workflow.
