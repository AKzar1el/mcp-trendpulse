# Remote deployment notes

This directory documents the containerized **remote Streamable HTTP transport**. It is a deployment foundation, not a public production service yet. Until DigestSEO authentication/OAuth is wired, keep this endpoint on localhost, a private network, or behind another controlled access layer.

## Build

```bash
docker build -t mcp-trendpulse:local .
```

The image is based on Python 3.12.14 Bookworm, installs the locked non-development dependency set with `uv`, installs the Playwright Chromium build matching the locked Python package, and preloads NLTK `punkt` plus `punkt_tab` so summarization does not download tokenizer data during requests.

The runtime process uses a non-root UID/GID (`10001`) and sets `TRENDPULSE_BROWSER_SANDBOX=true`. The application itself remains at `/app`; writable runtime state is expected under `/tmp` and the non-root home directory.

## Chromium sandbox profile

TrendPulse may visit untrusted article URLs through its Playwright fallback. Playwright recommends a non-root browser user plus its Docker seccomp profile for crawling/scraping. Use the profile that matches the locked Playwright version (`1.53.0`):

```bash
curl -fsSL \
  https://raw.githubusercontent.com/microsoft/playwright/v1.53.0/utils/docker/seccomp_profile.json \
  -o /tmp/trendpulse-playwright-seccomp.json
```

Do not replace the production sandbox with `--cap-add=SYS_ADMIN`; Playwright documents that only as a local debugging fallback.

## Local/private smoke run

```bash
docker run --rm \
  --init \
  --ipc=host \
  --security-opt seccomp=/tmp/trendpulse-playwright-seccomp.json \
  -p 127.0.0.1:8000:8000 \
  mcp-trendpulse:local
```

Then verify:

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/ready
```

The MCP endpoint is `http://127.0.0.1:8000/mcp` by default.

`/health` is a process liveness endpoint. `/ready` confirms the ASGI/MCP process is ready to accept requests; it intentionally does not make live Google News/Trends calls, so upstream provider health is not part of readiness.

## Public hostname configuration

The remote transport rejects unexpected Host and Origin headers. For a real reverse-proxy hostname, configure it explicitly:

```bash
-e TRENDPULSE_HTTP_ALLOWED_HOSTS=trendpulse.example.com \
-e TRENDPULSE_HTTP_ALLOWED_ORIGINS=https://trendpulse.example.com
```

`Origin` may be absent for server-to-server MCP clients. If a browser-based client is introduced later, list only the exact trusted browser origins.

The MCP path can be changed with:

```bash
-e TRENDPULSE_HTTP_PATH=/mcp
```

## Reverse proxy / orchestrator requirements

- Terminate TLS at the ingress or reverse proxy and preserve the intended public `Host` header.
- Keep one Uvicorn worker per container. Scale horizontally with additional container replicas; the remote MCP transport is stateless.
- Provide sufficient shared memory for Chromium. Docker's recommended local setting is `--ipc=host`; Kubernetes-style deployments should provision an appropriately sized `/dev/shm` (for example a memory-backed volume) rather than relying on Docker's tiny default.
- Preserve a Chromium-compatible sandbox/user-namespace policy. The exact mechanism depends on the runtime, so validate it on the target platform before exposing article/browser tools.
- The container includes no temporary authentication layer. Do not publish it directly to the open internet before the planned DigestSEO identity integration.

## Runtime variables

Relevant remote/container settings:

```text
TRENDPULSE_HTTP_PATH
TRENDPULSE_HTTP_ALLOWED_HOSTS
TRENDPULSE_HTTP_ALLOWED_ORIGINS
TRENDPULSE_BROWSER_SANDBOX
GOOGLE_TRENDS_DELAY
HTTP_PROXY
HTTPS_PROXY
```

The image sets `TRENDPULSE_BROWSER_SANDBOX=true`; overriding it to false weakens the browser isolation model and should not be used for the hosted service.
