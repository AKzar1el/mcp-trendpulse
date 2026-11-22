# MJAU v2 A03/B01 integration and security hardening

Prepared on 2026-11-21 under approved Option 1 after V1 PR #328 merged at 691846684f28652ed5d67973641596d9aaa93849, then rebased onto independently merged security PR #381 at 60ca71278f9f348c7948250661a113c5fa5d7743.

## Scope and expected behavior

Only the separately launched optional TrendPulse intelligence MCP gains two read-only functions:

- intelligence_dependency_graph(ecosystem, package, version, execute=False): source-scoped versioned dependency graph from the free deps.dev v3 API. Supports npm, PyPI, Cargo, Maven; bounded request size and source quota; safe PyPI numeric version canonicalization; no claimed customer counts or market demand.
- intelligence_repository_scorecard(owner, repo, execute=False): one official OpenSSF Scorecard heuristic assessment for a public GitHub repo, with source date precision, reported check scores, uncertainty and missing coverage. Never a security guarantee.

Plan-only default does not read SQLite or contact any source. Explicit execute=True makes one bounded keyless request on a cache miss, subject to separate daily source caps, cooldown and validated 12h/24h cache. Only fixed trusted provider hosts are accessed, never arbitrary user URLs. Cache root is distinct from the existing V1 cache. No user API keys, paid data, worker polling, unrelated third-party MCP process or V3 code.

The regular community 16-tool MCP and hosted six-tool MCP retain their original tool catalogs. V3 experimentation is independent; A06 (GDELT) and A08 (social sources) remain blocked. OpenSSF's first-party five-tool MCP is broader but is NOT duplicated: B01 is only a narrow embedded evidence signal.

## Main-branch security fixes already merged before V2

At integration planning time the protected main lockfile had Soup Sieve 2.9.2 (four alerts: two HIGH, two MODERATE) and OpenTelemetry Python API 1.45.1 (one MODERATE). Those alerts predated V2.

Separate main-branch security PR #381 already refreshed the lockfile. This V2 integration intentionally reuses the exact checked-in versions without duplicating dependency metadata changes:
- soupsieve 4.1.3 (patched high and moderate selector ReDoS reports)
- opentelemetry-api 1.45.2 (patched traceparent length processing)

Soup Sieve 4.x requires Python 3.11.5 or newer. The declared minimum Python version is correspondingly raised from 3.11 to 3.11.5. Existing supported modern Python 3.11 patch releases and Python 3.12-3.14 remain compatible. Any consumer pinned to Python 3.11.0-3.11.4 must upgrade its interpreter patch or stay on the previous release. This is an explicit compatibility change, not hidden by a permissive dependency constraint.

Beautiful Soup 4.13.4 remains pinned; verified on a fresh isolated Windows Python 3.12 venv with Soup Sieve 4.1.3 and OpenTelemetry API 1.45.2. Both nested CSS selector behavior and oversized traceparent processing passed. The corrected lockfile is already merged via PR #381. Confirm remaining Dependabot alerts separately; V2's test results alone do not establish that every security alert is closed.

## Release verification gates

1. All V2 source tests plus integration tests pass authentic pytest and Ruff. V1 complete tests remain passing with the new optional tool registration and no changes to default surfaces.
2. Run an actual stdio MCP handshake, read-only tool discovery and plan-only calls. For explicit execution, use bounded source probes and the separated local quota/cache with no network bypass.
3. Verify new dependency constraints with uv lock plus a real installed updated-dependency environment; run Python 3.11 and 3.12+ GitHub checks on the actual candidate PR.
4. Protected main branch required checks and author review remain mandatory. No force push, release, automatic GHCR or PyPI publication. The merged V1 guard leaves GHCR login/tag/push manual-dispatch-only.
5. Keep changes isolated to opt-in intelligence_mcp, two V2 adapters, focused tests, SQLite-handle cleanup and clear documentation; reuse PR #381 dependency metadata without changes. Do not touch V3 branches or running agents.

Useful source documentation:
https://docs.deps.dev/api/v3/
https://github.com/ossf/scorecard/blob/main/docs/mcp.md
https://github.com/ossf/scorecard/blob/main/README.md
https://pypi.org/project/soupsieve/4.1.3/
https://github.com/open-telemetry/opentelemetry-python/releases

## Windows SQLite handle lifecycle fix

Live one-request-per-source acceptance for A03 and B01 observed valid original provider records and SQLite cache replay without another network request. The test found Windows cannot delete the disposable cache database while the original BudgetCache leaves sqlite3 connections to be closed by GC. Python's connection context manager only commits/rolls back; it does not close the connection. The existing seven BudgetCache calls now explicitly wrap each connection in contextlib.closing, while retaining the original inner context manager for commit/rollback semantics. A Windows regression creates, queries, reserves and saves a cache then deletes the directory immediately with no garbage-collection or retry dependence. No cache schema, source budget, scheduler, worker, user credential or provider behavior was changed.
