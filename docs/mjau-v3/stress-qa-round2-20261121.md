# MJAU v3 A04/A10 — adversarial, productivity and MCP E2E test round

**Date:** 21 November 2026. **Scope:** exact preexisting lean draft PR #382; A04 Wikidata entity-name evidence, A10 OSV factual vulnerability IDs; B08 opt-in guarded-localhost helper. **No new production tool/source registrations, dependencies, worker changes, secrets, billable calls, external network provider requests or deployment.** Test source snapshots were previously acquired from their original providers; all new work is deterministic offline replay or localhost transport.

## Pre-fix falsification and surgical repairs

1. **A04 incomplete-source false negatives.** A requested QID missing from an otherwise successful response, a `missing` source item, or a source-observed QID without a language label previously led to `status=unknown_no_match` for an unobserved name. Regression trial reproduced this using original parser output. `candidates_for_name()` now marks `source_items_incomplete=true`, `searched_name_coverage_complete=false`, and uses `unknown_incomplete_source` on otherwise unqualified negatives. Alias overflow retains `unknown_incomplete_aliases` priority. Positive candidates still require confirmation and never auto-identify entities.
2. **A10 untrusted URL credential and control passthrough.** The source reference sanitizer previously echoed HTTPS links with `api_key`, `access_key`, `session_id`, `jwt`, `signature`, percent-encoded sensitive parameter names, literal CR/LF/NUL/whitespace or backslashes. The actual pre-fix deterministic probes returned them. The new sanitizer normalizes query key separators and rejects these links, including percent-encoded control bytes, **without dropping otherwise valid advisory IDs**. Valid public HTTPS reference links remain available.
3. **A10 malformed ecosystem type raised Python TypeError.** Passing an unhashable list or dict for `ecosystem` raised `TypeError: unhashable type`, not a clean validation failure. The fixed plan/query input boundary now requires a string before set membership and responds with controlled `ValueError`. This applies to both full and ID-only OSV plans.
4. **A04 null alias projected.** A malformed alias row `null` previously entered `aliases=[None]`. The parser now fails closed with a source-validation error rather than pretending `null` is a valid multilingual alias.
5. **Unbounded nesting escaped error normalization.** Extremely deep Python JSON-like source objects (6,000 levels) raised `RecursionError` from JSON size calculation rather than a normal invalid-source response. Both A04 and A10 now convert this into a controlled `ValueError`. No recursion limit, global settings or worker processes were modified.

These are reproduced defensive defects, not claims that original official live-source data was malicious. Regression tests exercise the true pre-fix behavior and the repaired invariants, including **550 seeded mutated compact-response envelopes** and source fixture replay.

## Source-backed output efficiency

The existing complete official OSV `Django==2.2.0` ID-only fixture has **75 distinct advisory IDs**. Keeping the full internal A10 projection is useful for audit, but its repeated per-ID terms created disproportionate MCP payloads. Added **`present_compact_query_for_mcp()`** as an opt-in presentation of an already-validated compact projection:

| Same 75-ID source projection | JSON bytes |
| --- | ---: |
| Full internal source record detail | 50,590 |
| Proposed compact MCP-facing source record | **14,848** |
| **Reduction** | **70.65%** |

All 75 IDs, individual modified timestamps, source URLs and database-family hints are preserved. Common warnings are moved to top-level **without dropping** `source_licenses_are_heterogeneous`, `source_specific_license_review_required`, `raw_advisory_redistribution_authorized=false`, `no_advisory_not_equivalent_to_safe_package=true` or `no_auto_remediation=true`. No raw vulnerability descriptions or exploit text included. Detailed source parse remains untouched for audits. This reduction is **deterministic byte measurement, not an inferred model-token cost saving**.

## Real MCP client/server tests (not just direct Python calls)

Two genuine, no-provider-network testing modes ran successfully, isolated from registered MCP systems:

- **In-process FastMCP 3.4.11 `Client(sandbox)`:** a temporary FastMCP instance registered only two **test-only** source-backed tool wrappers, `test_only_wikidata_candidates` and `test_only_osv_package_ids`; validated 2-tool catalog, exact source statuses/QIDs, the complete 75-ID package result, explicit denial of unsupported source versions and malformed tool arguments, and **30 sequential client tool calls** with consistent results. No shared MCP registry/source definitions altered.
- **Real guarded HTTP MCP transport:** a disposable FastMCP HTTP server bound exclusively to `127.0.0.1` through the already reviewed `run_guarded_loopback_http` helper, started as a child process with **no production tools registered**. The actual FastMCP HTTP client listed the same two tools, round-tripped real saved Q64 entity and Django advisory facts over JSON-RPC, rejected wrong package/version fixture bindings, and cleaned up its child on exit. This test exercises HTTP serialization, schema, session and local security rather than the in-memory transport alone.

These are **functional source-workflow tests**, not a blinded external human productivity trial; tools explicitly report that fixtures are not live searches. The official full MCP reference conformance suite remains as documented in `b08-official-security-results-20261121.md`: 11/32 all-feature checks, while 6/6 selected relevant guarded server checks passed in the earlier run. No attempt to fake support for image, audio, prompt fixture or elicitation scenarios.

## Bounded microperformance (diagnostics, not SLA)

Same Windows computer, 160 iterations per source operation, each timed with `perf_counter_ns` **while tracemalloc was enabled**. User session and other agents were not stopped.

| Source-backed operation | Median parse ms | p95 parse ms | Peak traced Python B |
| --- | ---: | ---: | ---: |
| A04 3 QIDs, 6 languages | 22.3521 | 56.5836 | 42,194 |
| A04 source parse + Berlin candidate | 16.2087 | 24.1829 | 35,076 |
| A10 original Django 75-ID compact parse | 28.1495 | 63.0437 | 120,938 |
| A10 lodash six advisories including 93-source-link edge | 77.4725 | 124.6621 | 32,648 |

The last lodash case uses **source-derived 93-link count**, not original publisher text; links are synthetic safe local test strings. Python allocation tracing adds overhead; timings reflect local in-process computation only, not provider fetch latency, live MCP round trip, system RAM ceiling or a user-facing performance promise.

## Final verification and release decision

**Actual Windows test run on this round:** `242 passed, 2 integration tests deselected` for the synchronous core/v1 evaluation suite, followed by the separate real HTTP integration run **`2 passed`**. Ruff checks and compileall succeeded. The local pytest configuration emitted one warning about `asyncio_mode` because the optional asyncio plugin was intentionally disabled; no failing assertions.

**A04/A10 technical quality:** improved source-missingness semantics, parser input safety, reference leak resistance and MCP response efficiency. These remain plan-only/unregistered features in draft PR #382; do not imply completed legal review or universal user benefit. **Release remains NO-GO** pending an owner-reviewed budgeted collector/MCP integration, independent user evaluation, OSV per-original-feed rights and attribution checks for intended public/commercial outputs, and explicit release approval. No live version or main branch was modified by this work.
