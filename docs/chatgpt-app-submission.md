# ChatGPT Apps submission runbook

This document tracks the release gates for **TrendPulse by DigestSEO** as a public ChatGPT Apps / MCP integration.

The repository package can be prepared and validated before the hosted service is publicly submitted. Do not treat package readiness as public-submission approval.

## Repository package

The repository contains:

- `.codex-plugin/plugin.json` — universal plugin metadata and starter prompts.
- `chatgpt-app-submission.json` — app review metadata, tool-hint justifications, five positive review cases, and three negative cases.
- `assets/digestseo-mark.svg` and `assets/digestseo-wordmark.svg` — DigestSEO brand assets reused from the DigestSEO site repository.
- `src/mcp_trendpulse/hosted.py` — the six-tool hosted MCP surface.
- `tests/test_hosted_facade.py` — hosted catalog, schema, annotation, and selection-boundary tests.
- `tests/test_chatgpt_plugin_package.py` — package-manifest and submission-file drift checks.

There is intentionally no `.app.json` yet. That file is only appropriate after a real registered MCP connection ID exists. Do not invent or preallocate a `plugin_asdk_app...` identifier.

## Public listing metadata

Use these existing public surfaces when preparing the submission:

- Display name: **TrendPulse by DigestSEO**
- Category: **Business**
- Website: `https://digestseo.com/`
- Support: `https://digestseo.com/support/`
- Privacy policy: `https://digestseo.com/privacy/`
- Terms of service: `https://digestseo.com/terms/`
- Repository / public issue tracker: `https://github.com/AKzar1el/mcp-trendpulse`
- Logo source: `assets/digestseo-mark.svg`

The DigestSEO Privacy, Terms, and Support pages must disclose the hosted TrendPulse behavior before public submission.

## Hosted MCP deployment requirements

Before connecting ChatGPT Developer Mode or submitting publicly, deploy a stable public HTTPS Streamable HTTP endpoint and configure at minimum:

- `TRENDPULSE_AUTH_MODE=clerk`
- `TRENDPULSE_CLERK_ISSUER`
- `TRENDPULSE_CLERK_JWKS_URI` when the issuer default is not used
- `TRENDPULSE_CLERK_AUDIENCE`
- `TRENDPULSE_PUBLIC_BASE_URL`
- `TRENDPULSE_HTTP_ALLOWED_HOSTS`
- `TRENDPULSE_HTTP_ALLOWED_ORIGINS`
- `TRENDPULSE_DIGESTSEO_CONTEXT_URL`
- `TRENDPULSE_BROWSER_SANDBOX=true`

The production endpoint must expose the configured `/mcp` path, protected-resource OAuth metadata, `/health`, and `/ready`. Keep one Uvicorn worker per container and scale by replicas.

## Blocking provider-authorization gate

**Do not submit the current hosted provider implementation for public ChatGPT review until its third-party data-access path is clearly authorized for this use.**

The current Community adapters use libraries that access Google Trends / Google News data without an official Google API credential. The provider boundary is intentionally separate from the hosted MCP surface, so this can be changed for hosted deployments without breaking Community clients.

Before public submission, satisfy one of these gates:

1. replace the hosted trends/news adapters with an authorized or licensed provider whose terms permit the hosted integration; or
2. obtain explicit authorization for the current upstream access pattern and retain evidence suitable for review.

Do not rely on the open-source library license alone as evidence that the upstream Google access itself is authorized.

The Community MCP may continue to expose its existing provider adapters under the user's/self-hoster's own responsibility while the hosted provider path is resolved.

## OAuth / reviewer account

For an authenticated public submission:

- use the existing DigestSEO Clerk authorization server;
- support the authorization-code flow and refresh tokens used by the ChatGPT connection;
- configure the actual ChatGPT OAuth client identifier as the hosted MCP audience;
- create a dedicated reviewer account that can sign in without MFA or inaccessible manual steps;
- do not require a Google Search Console connection for the core five review cases — `project_id` enrichment is optional;
- if a Search Console review case is later added, provide a dedicated reviewer project/account with non-sensitive sample data.

Never put reviewer credentials, OAuth tokens, client secrets, or Google credentials in this repository.

## Developer Mode validation

After the real hosted endpoint exists:

1. Connect the HTTPS MCP URL in ChatGPT Developer Mode.
2. Complete the Clerk OAuth flow and reconnect after token refresh.
3. Confirm ChatGPT imports exactly these six tools:
   - `discover_trends`
   - `analyze_keyword_trend`
   - `compare_keyword_trends`
   - `discover_related_demand`
   - `get_trend_context`
   - `find_seo_opportunities`
4. Run every case in `chatgpt-app-submission.json`.
5. Add additional direct, indirect, edge, and out-of-scope prompts to verify tool selection.
6. Confirm out-of-scope requests do not invoke TrendPulse.
7. Confirm no tool asks for confirmation or implies a write operation because the hosted surface is read-only.
8. Record a reviewer demo showing authentication, a representative successful tool call, returned sources/context, and error handling.

## Portal submission gates

Do not submit until all of the following are true:

- public production MCP URL is stable and reachable over HTTPS;
- provider-authorization gate above is resolved;
- DigestSEO domain ownership can be verified in the submission flow;
- OpenAI account/business identity requirements are satisfied;
- the submitter has the required Apps Management permission;
- reviewer OAuth credentials are prepared outside the repository;
- logo, category, website, support, Privacy, and Terms URLs are live;
- all six tool descriptors match production behavior and expose all three tool hints;
- exactly five positive and three negative review cases are ready;
- Developer Mode end-to-end tests are green;
- the demo recording and release notes are prepared;
- geographic availability is deliberately selected.

## Release-note draft

> TrendPulse by DigestSEO adds a focused six-tool research surface for discovering search trends, analyzing and comparing keyword momentum, expanding related demand, adding recent-news context, and finding trend-driven SEO opportunities. Optional DigestSEO project context can add read-only Search Console evidence without transferring Google OAuth credentials into TrendPulse.

Keep this release note aligned with the deployed provider and authentication behavior at submission time.
