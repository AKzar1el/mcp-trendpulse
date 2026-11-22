# B08 — official MCP conformance runner executed and HTTP security finding fixed (2026-11-21)

**Scope:** original merged v1 optional `intel_mcp` with **12 read-only tools**, tested via isolated HTTP on `127.0.0.1`; also real Python MCP SDK stdio/Streamable HTTP sessions from earlier evidence. **NOT a public service, deployed release or MCP SDK everything-server conformance certification.** No shared listener, worker schedule, installed packages or main-line service configuration changed.

## Pinned official tool provenance, zero install scripts

- Exact official npm package: `@modelcontextprotocol/conformance@0.1.16`, MIT.
- Official tag lockfile: `https://raw.githubusercontent.com/modelcontextprotocol/conformance/v0.1.16/package-lock.json`, pinned SHA-256 `df89d138b91871a7fb041f8d3923a78b9a1e2d5bdf28ba589fe6f944f30814fe`.
- All **110** production dependencies plus the CLI itself, **111 npm tarballs total**, retrieved from `registry.npmjs.org` into a disposable Windows directory; every tarball's original `dist.integrity` SHA-512 checked, archive paths confined to that directory, **no `npm install`, scripts, cloud compute, or global changes**.
- The pinned CLI's `list --server` worked and listed scenarios for MCP protocol `2025-06-18` and `2025-11-25`. Official standalone `server --url ... --scenario server-initialize` and `tools-list` individually returned exit code 0 / **1 of 1 checks passed each** on the real optional intelligence MCP server.

## Full official *active* scenario suite (ungarded baseline)

Exact CLI `node dist/index.js server --url http://127.0.0.1:<ephemeral>/mcp --suite active` **exited 1** after **24.39s**: **30 server scenarios, 11 successful individual checks, 21 failed individual checks** (32 total checks).

**Passing:** initialize 1, logging-set-level 1, ping 1, tools-list 1, tools-call-simple-text 1, tools-call-error 1, server-sse-multiple-streams 2, resources-list 1, prompts-list 1, and one half of DNS rebinding 1.

**Failing:** completion-complete; tool fixture scenarios needing image/audio/embedded resource/mixed content/logging/progress/sampling/elicitation; explicit elicitation SEP variants; resource read/subscribe/template operations; prompt get/argument/image operations; one DNS rebinding check. These checks are designed for an **SDK everything-server test fixture**, while the actual optional TrendPulse server only advertises its bounded domain-specific intelligence tools. Missing optional test-fixture tools should **not** be misrepresented as protocol vulnerabilities or as a tier score, and a passing SDK smoke cannot substitute for the complete suite.

**Important version caveat:** pinned v0.1.16 CLI supports `server --suite active` and `tier-check --spec-version`, but **this run is not a frozen per-revision requirement-scored `--requirements 2025-11-25` tier evaluation**. Current conformance project docs describe frozen requirement sets; do not retroactively claim one was executed here. This report preserves both the failures and the valid narrower interoperability tests.

## Genuine Host/Origin risk in default unguarded localhost HTTP

A four-case direct HTTP initialize probe confirmed that **the test invocation without explicit FastMCP Host/Origin protection** accepted valid and malicious Host/Origin headers with status **200**. FastMCP 3.x documents the guard as opt-in for HTTP reverse-proxy compatibility, independent of stdio:
[official FastMCP HTTP host/origin guide](https://github.com/PrefectHQ/fastmcp/blob/main/docs/v3/deployment/http.mdx).

A scoped new helper `mcp_trendpulse.mjau_v3.http_security.run_guarded_loopback_http()` binds **only** `127.0.0.1`, forces `host_origin_protection=True` and fixed local Host/Origin allowlists, rejects port spoofing, and offers no arbitrary bind address override. Retest statuses:

| HTTP probe | Unprotected test invocation | Guarded helper |
| --- | ---: | ---: |
| Valid 127.0.0.1 Host, no Origin | 200 | 200 |
| Forged `Host: evil.example.com` | 200 | **421** |
| Allowed Host, `Origin: http://evil.example.com` | 200 | **403** |
| Both forged Host and Origin | 200 | **421** |

This is **not** a claim that the production stdio connector is remotely exposed; only the optional localhost HTTP test startup was assessed. Do not expose unauthenticated HTTP beyond loopback. An authenticated remote deployment requires separately reviewed origin policy and credentials.

## Official retest of the guarded helper

The same pinned official CLI was re-provisioned with the same verified 111 SHA-512 packages in a disposable folder, and run against the scoped guarded localhost helper; all child processes and package files cleaned afterward. Exact five targeted official scenarios:

| Scenario | Exit code | Checks |
| --- | ---: | ---: |
| `server-initialize` | 0 | 1/1 |
| `tools-list` | 0 | 1/1 |
| `tools-call-error` | 0 | 1/1 |
| `ping` | 0 | 1/1 |
| **`dns-rebinding-protection`** | **0** | **2/2** |

**All 6/6 app-relevant selected checks passed**. Local regular code tests: 9/9 guard unit tests, and a separate **real isolated HTTP integration test** 1/1 (clean process shutdown), with no changes to shared `intelligence_mcp.py` or the 16-tool community MCP.

**B08 decision:** the official runner was successfully executed, and the directly identified DNS protection risk was fixed in the guarded opt-in test helper. A **universal 30-scenario pass or SDK tier claim remains unavailable / not applicable to the specialized app** because reference-fixture features are intentionally not implemented; any claim of blanket MCP spec certification is rejected. Keep the guarded helper for *future explicitly authorized local HTTP diagnostics*, but production stdio behavior is unchanged. Do not convert it to a public authenticated server without a separate design review.

Supporting machine-readable summary files (short source-derived checks only): `docs/mjau-v3/b08-official-active-suite-20261121.json` and `docs/mjau-v3/b08-guarded-official-targeted-20261121.json`.
