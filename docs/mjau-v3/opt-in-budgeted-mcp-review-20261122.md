# MJAU v3 optional budgeted MCP integration — owner review (2026-11-22)

**Status: draft only; NOT installed, released, merged into main or connected to live Codexify.** The existing 16-tool community TrendPulse connector and v1 intelligence MCP source set remain unchanged. This is a new, separately launched two-tool source adjunct based on the current v1 `BudgetCache` infrastructure.

## Exact command for later owner-approved sandbox activation

```powershell
# Run from the checkout or an installed package with dependencies already present.
# Default requests are read-only PLAN-ONLY; no network until execute=True.
$env:PYTHONPATH = "src"
python -m mcp_trendpulse.mjau_v3.mcp
```

The standalone stdio MCP exposes only `mjau_v3_wikidata_names` and `mjau_v3_osv_advisory_ids`. No network, file-system budget setup, API keys or user credential access occurs on import, initialization or an ordinary `execute=False` call. Inputs are strict: 1–3 explicit QIDs, 1–6 approved languages, optional exact name; PyPI/npm exact package/version.

## Approved-by-code request boundaries (NOT a deployment approval)

| Control | Wikidata | OSV |
| --- | --- | --- |
| Upstream | HTTPS `www.wikidata.org/w/api.php` exact QID lookup | HTTPS `api.osv.dev/v1/querybatch` one exact versioned package |
| Request | GET | POST JSON with exactly one query |
| Per-execution network budget | max 1 request | max 1 request |
| Persistent UTC/day cap | **8** | **10** |
| Timeout | **8 seconds** | **8 seconds** |
| Response ceiling | **192,000 bytes** | **192,000 bytes** |
| Redirects / user URLs | no redirects, fixed origin/path | no redirects, fixed origin/path |
| Cache | v1 `BudgetCache`, independent key, 1h validated CC0 metadata | v1 `BudgetCache`, independent key, 1h only projected ID/modified/source URLs |
| Per-source HTTP 429 | 24h local no-retry circuit, no automatic calls | 24h local no-retry circuit, no automatic calls |
| Source rights | CC0 structured data with Wikidata links | heterogeneous original licenses; all commercial bulk reuse marked **NOT APPROVED** |
| Interpretation | name candidate **never** confirmed identity | advisory ID **never** independently validated exploit, customer demand, package safety or patch |

`BudgetCache` is the **same existing v1 SQLite budget/cache class**, but with separate `mjau_v3_` source identifiers. Request-level file locks prevent duplicate identical provider calls across workers/processes; atomic SQLite `reserve(..., guard_cooldown=True)` prevents quota bypass; repeated name queries over one Wikidata QID payload recompute name candidates **after** source-cache lookup to prevent cross-caller false matches. Errors are projected as `source_unavailable`, never an empty result.

We intentionally do **not** call the generic `intelligence_core.collect()` projector: it is built to retain market-source data and would not satisfy the requirement to avoid OSV raw advisory bodies. The new `budgeted_sources.py` reuses the official v1's budget, cooldown, cache and FileLock facilities and keeps a distinct fixed-origin, validated minimal response path.

User-Agent: `mcp-trendpulse-mjau-v3/0.1` identifies the original repo issue-tracker contact URL for Wikimedia access policy. No custom redirect, certificate bypass, proxy use, user-provided token, account credential, scheduled work, commercial endpoint or paid service is introduced.

## Evidence, operational readiness and rollback

- Source-fidelity **separate original-response scorer**: preregistered 4 Wikidata queries + 8 OSV queries, **12/12** scored Wikidata name decisions and **8/8** OSV package/version ID projections matched original provider data. A fourth Wikidata group was unavailable; its 2 name questions are **unscored**. Test crashed during a Windows SQLite temporary-directory cleanup, not during source scoring. Report reconstructed from printed score and SQLite receipts *without repeating provider requests*; see `workflow-holdout-results-20261122.json`. This is **not** an independent human trial.
- FastMCP in-process two-tool tests run with mocked original-source responses; 9 budgeting/source integration unit tests passed in the first run, including parallel singleflight, budget cap, cache isolation, 429 cooldown and no raw OSV blob retained. A real separate **stdio MCP subprocess** initialized and responded to both plan-only tools, with no cache created and invalid inputs correctly rejected. This test needed a 90-second bounded initialization allowance on the resource-limited Windows computer; its second run passed in ~45 seconds. No unapproved network call.
- HTTP transport threat model: 18 mock tests passing for URL/path/scheme/credentials, MIME, source-size, malformed JSON and User-Agent. Previous selected official B08 MCP protocol tests against guarded HTTP passed; the broad SDK everything-server suite is not fully applicable to this focused source adjunct and is not being relabeled as certified.
- Scope rollback: closing draft PR #382 leaves existing users/agents unchanged. No schema migration or production data directory changed by this work. On a later explicitly approved deployment, remove this optional source from MCP configuration and discard only the opt-in cache namespace if desired; production v1 remains untouched.

### Additional full local compatibility check

After consolidating the two-source integration and v1 budget-regression tests, a no-network regular suite across **14 MJAU v3 test modules plus four existing v1 budget/source modules passed 285/285 assertions** (3 real-transport tests were explicitly deselected for separate execution), with Ruff and Python compileall green. The real subprocess stdio server was individually confirmed to initialize and respond to both plan-only tool calls, using no cache and no network, after increasing the local Windows cold-start timeout to 90 seconds; initial 30-second startup allowance was too low on this machine. The transport threat-model suite passed **18/18** cases. The remaining three guarded HTTP/stdio tests are run separately to avoid silently counting skipped integration scenarios as passed.

## Required external approvals before production

1. **Independent human user-workflow reviewer** of unfamiliar source tasks (see `independent-review-packet-20261122.md`) with explicit correctness, false-assurance and usability signoff. Currently **PENDING**.
2. **Source-specific OSV legal/owner review** before public/commercial redistribution or aggregation; source family differences and CC BY attribution must be acceptable and shown. Preliminary engineering review documented but **NO legal signoff**.
3. **Deployment/operator approval** for installing/enabling optional MCP in Codexify, any public service, or merging. Require baseline tests on the final merged revision, exact target cost/quotas, authorization model for public HTTP, and rollback test. Currently **PENDING**.

**Verdict:** isolated two-source MCP is functionally implemented for optional testing and has conservative caps. It is not a permission to ship, nor evidence that full reference-tool MCP conformance or independent human user-benefit evaluation has passed.
