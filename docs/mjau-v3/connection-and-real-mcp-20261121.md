# MJAU v3 — Windows Codexify connectivity and real-MCP test checkpoint

**Date:** 2026-11-21. **Decision:** existing God v5 Codexify path WORKING; dedicated Codexify TrendPulse v2 tunnel still DISCONNECTED; official B08 conformance BLOCKED. No feature accepted, merged or deployed.

## Connection topology and investigation

- The dedicated `Codexify_TrendPulse_v2` connector repeatedly returned `Tunnel-client has not been seen for 300 seconds`. Merely enabling the connector in the ChatGPT UI does not establish the tunnel client on the user's machine.
- The existing, **separately connected** `God_v5` Codexify bridge works. Its source-project catalog contains one unambiguous `mcp-trendpulse` checkout. The current conversation was bound to a new **managed detached worktree** with `createWorktree=true`; `cloned=false`. No other agent's checkout, branch, process or mutable index was selected.
- Codexify 2.4.0 local doctor: 13 checks passed, zero failures, one warning, two skipped. The background service and loopback health endpoint respond; the already-configured primary OpenAI tunnel credential and runtime checks passed. A separate warning concerned unrelated `cua_repl` and `node_repl` command paths. These were **not altered**.
- Only one running `tunnel-client-runtime` process was observed, while multiple historical credential-reference files exist. This **does not prove** which historical tunnel ID is associated with the stale dedicated connector. No extra tunnel was started, no key file read, no service restarted and no connector settings changed.
- `God_v5.mcp_list_sources(query=trendpulse)` reported the upstream **community** `mcp_trendpulse` as `connected`, with 16 tools and no recent failures. The actual `get_categories(query="Software",limit=3)` tool call succeeded, returning three published Google Trends category names/IDs. This proves an end-to-end God v5 -> configured upstream MCP call; it is **not** evidence that the separate v3 opt-in server has been registered as an upstream.

## Exact v3 commits retested on Windows in the isolated worktree

| Track | Exact SHA | Command (with PYTHONPATH=src) | Local result |
| --- | --- | --- | --- |
| Stage 0 A05 + B09 | `67a43f88330ddca2212722b76ddad10a3943b989` | `python -m pytest -q tests/test_mjau_v3_historical.py tests/test_mjau_v3_origin_graph.py` | 31 passed |
| A04 Wikidata | `96ee759e422076b33cf3e0bfc814011f63ea499d` | `python -m pytest -q tests/test_mjau_v3_wikidata.py` | 45 passed |
| A10 OSV (Ruff fix included) | `b9b0053f64ed2f4da7aa79a3d10877e1842cbfb1` | `python -m pytest -q tests/test_mjau_v3_osv.py` | 45 passed |

**Total: 121/121 targeted deterministic tests passed** across separate pinned branches; this is not a single integrated release. The global Python 3.13 pytest run emitted an `asyncio_mode` configuration warning because the global environment lacked pytest-asyncio. This warning did not cause failures. Existing GitHub Python CI on the individual PRs had passed across Python 3.11–3.14 and Ruff.

## Actual optional intelligence MCP process proof

Using the existing source project's virtual environment **read-only** (FastMCP 3.4.11 and official MCP Python SDK) and the managed v3 worktree's `src` on `PYTHONPATH`, an independent MCP client subprocess:
- started `python -m mcp_trendpulse.intelligence_mcp` using stdio;
- completed initialize/negotiation at `2025-11-25`;
- listed exactly **12** optional read-only intelligence tools;
- successfully invoked `intelligence_source_catalog` with no live provider call; and
- confirmed `intelligence_plan` rejects an unapproved source (`isError=true`).

This is a **real MCP stdio integration** pass and makes the configured God v5 + Windows workspace usable for continued independent v3 work.

## Official B08 conformance track — NOT PASSED

Source: https://github.com/modelcontextprotocol/conformance (official README and frozen requirement-set semantics checked on 2026-11-21). The public conformance CLI expects a live HTTP MCP URL for server tests; the official revision requirement set and extensions must be distinguished. The system under test speaks `2025-11-25` via the real stdio smoke.

Two attempts to start a *temporary, loopback-only* FastMCP HTTP adapter within the independent Windows test session did not reach TCP readiness (initial short window, then 75-second bounded deadline). The child process was terminated and confirmed cleaned in both attempts. The longer attempt produced no diagnostic stderr, so the cause is **unknown** rather than a diagnosed FastMCP defect.

The machine's direct `npm view @modelcontextprotocol/conformance` request stalled and was interrupted; no `@modelcontextprotocol/conformance` package was found in its local `npx` cache. **The official runner was not executed.** Do not claim a conformance pass, compliance tier or HTTP compatibility from the successful stdio smoke alone.

Reproduction next time: first identify why the ephemeral HTTP process does not bind, then run a pinned official `@modelcontextprotocol/conformance` release against `127.0.0.1` using the `2025-11-25` requirement set and store its required/extension/not-scored results. Never expand local service exposure, automate retries, or alter shared CLI/MCP wiring just to satisfy a test runner.

## Safety, integration and rollback

- No new permanent workers, cloud resources, tunnels, credentials, provider calls, purchases, deployments, merges, or edits to v1/v2/shared files.
- Existing God v5 is the **working route** for future v3 agent sessions. Do not depend on the stale dedicated TrendPulse connector until its original tunnel is separately re-established. Rebinding it must not change or stop the live general service.
- Full v1-v3 empirical usefulness uplift, audited historical outcomes, bounded live A04/A10 source observations, cache replay, and B08 official conformance remain **BLOCKED**. These pilots must stay isolated and unreleased under PROVE OR DISCARD.
- No production rollback necessary; only this documentation commit is new. All local test server children were cleaned. The managed worktree remains detached from reviewed commits.

## 2026-11-21 additional diagnostic results (later checkpoint)

- **Temporary HTTP server now demonstrated:** a later isolated, loopback-only FastMCP 3.4.11 process bound to `127.0.0.1:<ephemeral_port>/mcp` in **19.3 seconds**, with Uvicorn confirming successful startup. The short/75-second failures in the earlier test were **intermittent**, not evidence of a reproducible HTTP transport incompatibility. Test process terminated and verified cleaned. The same optional stdio MCP still passed protocol 2025-11-25 initialization and tool listing.
- **Official runner package metadata:** a bounded GET of `https://registry.npmjs.org/@modelcontextprotocol%2fconformance/latest` returned HTTP 200, current published package `@modelcontextprotocol/conformance@0.1.16`. This verifies package existence, **not successful runner execution**.
- **Installation obstacle:** isolated, temporary `npm install --no-save --ignore-scripts --no-package-lock @modelcontextprotocol/conformance@0.1.16` with a private npm cache exceeded its **85-second** bound; a separate temporary Bun `bun x @modelcontextprotocol/conformance@0.1.16 --help` also timed out (55-second child timeout, about 100 seconds observed including process teardown). Both disposable directories were cleaned. No global packages, root manifests, lockfiles or processes left installed by these attempts.
- **B08 remains BLOCKED:** no official conformance command, revision-specific requirement scoring or Inspector CLI test actually ran. A real stdio client pass and an HTTP bind smoke test are distinct from an official conformance suite verdict. Do not infer server Tier 1 or full HTTP protocol compliance. A future isolated conformance runner must be provisioned safely before claiming acceptance.
- **A04/A10 follow-up:** the actual Wikidata Q89/Q312 and OSV Jinja2 2.10.1 / OSV-2020-744 requests have since returned HTTP 200 and passed their adapter parsers. Isolated reuse of the v1 `BudgetCache` with zero-network second lookups and quota guards passed; precise source hashes, timestamps and limitations are in the independent A04/A10 PR ledgers. None of these source checks resolves the missing official B08 verdict or independent utility/rights review.

**No changes to the connected Codexify service, either tunnel, existing workers, shared files, dependencies or deployments.**

## 2026-11-21 independent HTTP SDK acceptance — passed, not official conformance

After resolving the intermittent loopback bind delay, the isolated Windows managed worktree launched the **actual optional `intelligence_mcp` FastMCP 3.4.11 server** over an ephemeral `http://127.0.0.1:<port>/mcp` Streamable HTTP transport. Using the **official Python MCP SDK** (`mcp.client.streamable_http.streamablehttp_client` plus `ClientSession`), the client independently completed the `initialize` handshake negotiating **2025-11-25**, listed **12** optional intelligence tools, successfully invoked `intelligence_source_catalog` and verified that `intelligence_plan` rejects an unapproved source. Final clean execution: loopback readiness **3.32 seconds**, **HTTP_MCP_INDEPENDENT_SDK_PASS=True**, child process terminated and verified cleaned. No provider query, user data, root/shared MCP registration or production service was involved. An earlier successful invocation had an unrelated Windows temporary log-file cleanup lock; that file was subsequently removed and the final run used no temporary log file.

**B08 still BLOCKED:** this is a genuine independent MCP **HTTP protocol smoke pass**, not a result from `@modelcontextprotocol/conformance`. The pinned official npm CLI version `0.1.16` was successfully invoked once with `list --server` using a disposable Windows package directory, but isolated npm/Bun installation repeatedly failed to finish reliably and no official scenario or frozen `2025-11-25` requirement suite was run. **Do not claim full conformance, Tier 1, or absence of extensions failures.** No dependency, workflow, permanent service or production tool registration was changed.

## 2026-11-21 final dependency-installer diagnostics — official runner still unavailable

Pinned official conformance package: `@modelcontextprotocol/conformance@0.1.16`. Its registry metadata and official `npm` tarball can be read individually over HTTPS from both Python and Node 22 on the Windows host (e.g. a bounded `zod@4.3.6` tarball GET returned HTTP 200 through both transports). The **actual multi-dependency installation**, rather than basic DNS/TLS access to registry metadata, is failing to complete reliably. This cannot honestly be categorized as a protocol test failure.

Additional test-only provisioning methods after the first npm/Bun experiments: an official **Yarn v1.22.22** standalone bundled script extracted from its npm package and verified against the registry's SHA-512 `dist.integrity`, used strictly inside a disposable project folder with its own cache, no project lockfile and no script execution. Its dependency fetch displayed `There appears to be trouble with your network connection. Retrying...` and was terminated after the prescribed bound. A second Yarn attempt with `--network-concurrency 1 --network-timeout 22000` (serial fetch) stopped after **95 seconds** while displaying `[2/4] Fetching packages...`; no executable official runner was available. Both disposable directories and package caches were cleaned. A final Windows process/temp scan showed no leaked conformance/yarn helpers or residual test directories; Codexify service remained **running**. The already independently tested localhost FastMCP HTTP MCP server itself still starts and speaks negotiated `2025-11-25`.

**B08 decision remains BLOCKED.** No scored `--requirements 2025-11-25` run happened. Before retrying, obtain a different demonstrably working, authorized isolated dependency provisioning route (or a trustworthy pre-provisioned official runner in a separate environment) rather than repeating unchanged installers. No user-facing requirement score, conformance tier or spec-wide compliance can be claimed.
