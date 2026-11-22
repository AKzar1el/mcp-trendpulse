# MJAU v3 A04/A10 — fifth, wider adversarial & usability pass

**Date:** 2026-11-22. **Repository / PR:** [AKzar1el/mcp-trendpulse#382](https://github.com/AKzar1el/mcp-trendpulse/pull/382). **Frozen starting head:** `5ec3b97c67ca619494ff22c31186badce1408678`. **Evaluator:** assistant-led engineering work, **not** a separate human reviewer or a legal/rights determination.

Scope remained the isolated opt-in `mjau_v3` two-tool module. The installed 16-tool TrendPulse connector, V1/V2 code, CLI, workers, production registry and deployment were not modified.

## What was newly tested

1. **Local SQLite cache integrity and provenance:** invalid JSON, JSON null, nonobject/list JSON, duplicate keys, oversized cached body, changed package request identity, false commercial reuse approval, injected vulnerability prose, false Wikidata identity verification, and unreadable SQLite.
2. **Durable free-provider limits:** 20 simultaneous unique OSV requests against one budget, then 20 independent `BudgetCache` instances sharing one SQLite budget. No cap bypass occurred; 10 operations were permitted and 10 denied in each case. No real network traffic from the quota stress tests.
3. **HTTP backoff semantics:** `503 Retry-After` supplied as an HTTP-date instead of just numeric seconds; plus unknown `418` source error caching and previous 429/503 quota behavior.
4. **Source/user outcomes and resilience:** an explicitly missing Wikidata QID remained unknown after cache round-trip; an empty OSV query remained "no returned advisories," **not** "safe"; cache replay preserved source-specific attribution and no-remediation flags.
5. **Real public-source checks:** one explicit live Wikidata Q64 Berlin source query and one explicit live OSV npm lodash 4.17.11 ID-only query, with a temporary isolated cache. Plan-only made no network requests and 20 plan calls had a median 0.2335ms (max 1.416ms). Source metadata, policy flags and repeat-cache behavior were verified independently of mock HTTP.
6. **Real MCP transport:** independent actual stdio and loopback-host-protected HTTP subprocess tests with real JSON-RPC, not just direct Python function calls.

## Reproduced red before fixing

| Severity | Newly reproduced problem | Corrective action |
| --- | --- | --- |
| P2 — cached evidence integrity | Malformed JSON raised user-facing decoder exceptions; cached altered package identities, false license approvals or injected advisory text could be emitted as verified | Added `mjau_v3/cache_integrity.py`: versioned source-specific allowlisted output shapes, strict scope/identity, rights and safety assertions, and advisory/identity record validation |
| P2 — corrupted-row replay | A cached literal `null` was mistaken for a missing entry, causing a further source request; duplicate keys and oversized local rows were accepted | V3 now distinguishes missing SQLite rows from invalid existing rows and performs bounded strict JSON decoding (192,000-byte cap and duplicate-key rejection) before any source request |
| P2 — provider policy compliance | RFC HTTP-date `Retry-After` on 503 was ignored and replaced by a 90-second cooldown even if the provider asked for a longer interval | Parse both numeric and valid HTTP-date forms; retain the conservative existing persisted cooldown / no-repeat treatment for intervals over 300 seconds |
| P3 — new validator compatibility | A legitimate uncommon HTTP error `418` was cached but re-read as "local cache integrity failure" | Preserve bounded `provider_http_100..599` error reasons without treating failed sources as zero results |

Initial fifth-pass red tests: **7 failures / 1 prior-pass safety check passing**. Added three more poisoned-cache shapes and separately reproduced **3 red tests**; the unusual HTTP status was separately reproduced **1 red test**. The patch sequence preserved working empty-result and budget behavior. The finished new suite passed **16/16**.

A bad or unreadable local cache now returns `source_unavailable`, `local_cache_integrity_failure`, `not_a_zero_result=True` and **no fallback provider request**, so it cannot be confused with a verified empty advisory query. The cache validator is a schema/safety-contract check, *not a cryptographic signature*: an actor with complete local filesystem and code control remains out of scope.

## Final execution receipts

| Gate | Observed result |
| --- | --- |
| New fifth-pass focused adversarial suite | **16 passed** |
| Full V3 and selected shared V1 regular regression suite | **337 passed, 3 integration deselected** |
| Actual separately executed stdio + HTTP MCP subprocess suite | **3 passed, 9 deselected**, 114.17s |
| Ruff, Python compileall, git diff --check | **Passed** |
| Live Wikidata Q64 Berlin | `source_entities_observed`, **Q64 candidate**, `identity_verified=False`, **1124.1ms** |
| Live OSV npm lodash 4.17.11 | `source_advisories_returned`, **6 projected IDs**, no safe-package or remediation claim, **965.63ms** |
| Live provider replay | Both repeat calls **cache hits, no second network request** |
| Locally repeated cached Django (75 IDs), 80 samples | Median **7.679ms**, p95 **9.803ms**, 15,989 JSON bytes |
| Locally repeated cached Wikidata 3 QIDs × 6 languages, 80 samples | Median **6.039ms**, p95 **7.826ms**, 5,720 JSON bytes |

Single-request real-source latency and shared Windows timing measurements are **not** formal production performance guarantees. The real-source results were facts observed on this date, not future-proof advisory counts or identity assertions. The tests made one known public request per provider, with no paid API or private package list.

Test/reproduction files: `tests/test_mjau_v3_fifth_pass_qa.py`, `tests/mjau_v3_live_optin_probe.py`. V3-only implementation: `src/mcp_trendpulse/mjau_v3/budgeted_sources.py`, `src/mcp_trendpulse/mjau_v3/cache_integrity.py`.

## Release decision and outstanding gaps

**Engineering:** suitable for supervised private local opt-in tests. Original default `execute=False` remains; only explicit `execute=True` consumes one budgeted free-source request. Existing Wikidata **8/day** and OSV **10/day** UTC quotas, bounded timeouts, no automatic redirects or retries, and minimal OSV ID/date/link source-data policy remain.

**Still NO GO for automatic merge, public deployment or unrestricted commercial redistribution** pending (a) an unfamiliar outside-human user-outcome review, (b) per-original-publisher reuse-rights and attribution assurance for the exact use, and (c) explicit operator approval. Official full MCP conformance is not certified by a subset of tests. No amount of repeated automated self-review fills these external approvals.

The review report and tests themselves do not constitute a deployment or modify the main MCP service. Exact-head GitHub CI/Container/Publish stdio build-and-smoke results should be checked **after** the commit is pushed; never infer remote green from local passing tests.
