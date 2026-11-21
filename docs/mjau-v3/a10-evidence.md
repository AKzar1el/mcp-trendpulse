# MJAU v3 A10 — OSV advisory evidence pilot

**Decision: BLOCKED; not an accepted capability or release.**

**Pinned v1 staging ancestor:** `b88b0a974b5dcdb480e4fd8c4da5f7bbca68e98e` (draft v1 PR #328). Independent A10 branch with no shared edits and no dependency on the A04 or Stage 0 PRs. No protected, production or central registration changed.

## Distinct decision value versus v1

V1 exposes npm/PyPI package download histories and public GitHub issue text, but not authoritative package/version-linked vulnerability advisories. A10 could answer *“Has the official OSV aggregator indexed an advisory for this exact package/version?”* without mistaking popularity, discussion or downloads for a security finding. This does **not** establish vulnerability exploitation, urgency, remediation correctness, buyer demand or safety when no advisory is returned.

## Official source policy and limits

- [OSV official API](https://google.github.io/osv.dev/api/): free public API and currently no global rate limit; an open public service does **not** authorize high-volume probing. Proposed local plan is **one query**, explicit execution through existing v1 budgets/caching, 8-second timeout, max 192 KB response, no retry/paging by default.
- [POST v1/query](https://google.github.io/osv.dev/post-v1-query/): exact `package.name`, `package.ecosystem`, `version`. OSV notes version matching may be fuzzy for some registries; do not compute or assert precise dependency version ranges locally. The API can return `next_page_token`; results must be labeled incomplete until reviewed.
- [GET v1/vulns/{id}](https://google.github.io/osv.dev/api/): exact original advisory ID. One known public example from the official [OSV-2020-744 advisory page](https://osv.dev/vulnerability/OSV-2020-744), last inspected 2026-11-21, has **published** `2020-07-04T00:00:01Z`, **modified** `2022-04-13T03:04:39Z`, and reports OSS-Fuzz mruby evidence.
- [OSV source license guidance](https://google.github.io/osv.dev/data/new/rest-api): original feeds supply their own license links (e.g., CC BY or CC0); do not treat all aggregated advisory bodies as globally CC0 or unrestricted for commercial redistribution. This pilot stores only IDs, dates, a few public URL references and status labels, not advisory details or full feeds. Licensing for broad distribution remains **blocked pending per-source audit**.

## Implemented in isolated A10-only files

- `plan_package_query(PyPI|npm, exact_name, exact_version)` constructs one fixed-origin JSON POST body, no transport invocation.
- `plan_advisory_lookup(known_id)` constructs a single fixed-origin GET URL.
- `parse_package_query(...)` validates response envelope, duplicates, size, ID, dates, paging, withdrawals and source attribution. Empty `vulns` is *no indexed advisory returned for this specific query*, never *safe software*.
- `parse_advisory_lookup(...)` validates identity match for an already fetched advisory object.
- `parse_http_result(...)` fails closed for 401/403/429/503/302 without automatic retries or leaking returned error bodies.
- No direct HTTP client, automatic remediation, purl/version range arithmetic, new dependency, auto polling, production security reports, or extra public MCP tools.

## Test results and measured observations

On Python 3.13.5 sandbox:

    PYTHONPATH=src python -m pytest -q tests/test_mjau_v3_osv.py
    PYTHONPATH=src python -m compileall -q src/mcp_trendpulse/mjau_v3 tests/test_mjau_v3_*.py

**A10 45 deterministic tests passed; total v3 sandbox 121/121 tests passed.** Negative cases cover malformed/empty/error envelopes, duplicate IDs, missing/wrong dates, withdrawn advisories, HTTP errors, pagination without silent completeness, oversized payloads, and private/credential-looking links. The OSV-2020-744 test includes **manually reviewed public page timestamps**; the rest of the response payload is synthetic. **No real OSV JSON API call or real MCP process was executed.**

300-run single-process offline microbenchmark (one plan+response parsing+ID lookup each): median **0.1305 ms**, p95 **0.2038 ms**, peak traced allocation **22,521 bytes**, JSON result **808 bytes**, requests **0**, API cost **$0**. This is not an 8-GB-Windows operational benchmark or measured improvement over v1.

## Decision, outstanding proof gates, rollback

**BLOCKED** pending one genuinely free, bounded OSV package/version request and one known advisory-ID request through approved existing v1 cache/budget, validated zero-network replay, a side-by-side real v1 vs A10 security research task with independent ground truth (including adversarial non-vulnerable/no-result examples), provider-missingness review, actual upstream feed license decisions, and full repository regression/official MCP checks. No claim of **ACCEPT** or utility uplift is warranted.

When connectivity returns, use the existing v1 staging test environment, avoid shared mutable cache/quotas, and do not add an auto worker. Revert only A10 module, test and doc in this draft branch to roll back; no production state or old workers are affected. If real incremental value fails, **DISCARD** rather than ship.
