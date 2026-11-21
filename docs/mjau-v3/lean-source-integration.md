# MJAU v3 lean two-source compatibility branch — merged v1 baseline

**Date:** 2026-11-21. **Status:** REVIEW-ONLY / NO RELEASE, NO CLI OR MCP REGISTRATION.

## Scope exactly

This branch starts at the actual merged v1 commit `691846684f28652ed5d67973641596d9aaa93849` (PR [#328](https://github.com/AKzar1el/mcp-trendpulse/pull/328), merged 2026-11-21 15:47:23Z). It imports only the approved **A04 Wikidata multilingual QID identity** and **A10 OSV package/version vulnerability metadata** offline plan/parser pilots from their individually tested heads:

- A04 source `e6c14d5c9a9bc3351e0004190f9e8432f41b5f4a`, [draft PR #377](https://github.com/AKzar1el/mcp-trendpulse/pull/377).
- A10 source `484a48cb0c6b1430af2c9736e850e639f7de3551`, [draft PR #378](https://github.com/AKzar1el/mcp-trendpulse/pull/378).

Only `src/mcp_trendpulse/mjau_v3/{__init__,wikidata,osv}.py`, their four source-specific test modules, five small original-source/metadata fixtures and this new focused test/doc are included. **No A05, A09, A11, B09, B18 or additional niche proposals**; no package/dependency/lockfile changes; no changes to `intelligence_core.py`, `intelligence_mcp.py`, CLI, worker schedules or normal 16-tool community MCP. The omitted candidates are prioritized in the [archival Stage0 scope ledger](https://github.com/AKzar1el/mcp-trendpulse/blob/feat/mjau-v3-evidence-stage0-20261121/docs/mjau-v3/lean-release-scope-20261121.md).

## Distinct user questions that merged v1 cannot answer from its own sources

1. Given an exact Wikidata QID and scope, **which source-backed six-language names/aliases exist, and is a particular name ambiguous across supplied QIDs?** The real official Q308 planet Mercury versus Q1150 Roman deity snapshot demonstrates a shared candidate in six language scopes, with no automatic identity confirmation. The Q89 fruit/Q312 Apple company snapshot preserves separate entities. The official Q30 USA response has English 20, German 15, French 19 aliases; output caps eight and correctly declares negative alias matching incomplete. In v1, `plan_source("wikidata_action_api")` raises unknown source, **a source-coverage improvement, not measured independent user productivity**.
2. For an explicitly provided PyPI/npm exact package/version, **which OSV advisory IDs did the official public source return, and which factual dates/links are available?** An official PyPI Jinja2 2.10.1 OSV sample returned 10 advisory IDs. Real `six==1.16.0` returned an empty `{}` HTTP200 source result; this means **no indexed match in that response, not security assurance**. Individual full advisory bodies are **never** redistributed. In v1, `plan_source("osv_public_api")` raises unknown source, a distinct verified source capability, not a buyer/revenue/exploitation claim.

The source fixtures were obtained with bounded zero-cost public requests earlier on 2026-11-21. Full credits, exact SHA-256 identities, privacy, unknowns and licensing caveats remain in the original [A04 evidence](https://github.com/AKzar1el/mcp-trendpulse/blob/feat/mjau-v3-evidence-a04-20261121/docs/mjau-v3/a04-evidence.md) and [A10 evidence](https://github.com/AKzar1el/mcp-trendpulse/blob/feat/mjau-v3-evidence-a10-20261121/docs/mjau-v3/a10-evidence.md).

## Reproducible Windows verification

Run in this branch with the **existing repo venv**, with `PYTHONPATH=src`:

```text
python -m pytest -q tests/test_mjau_v3_lean_workflows.py tests/test_mjau_v3_wikidata.py tests/test_mjau_v3_wikidata_snapshot.py tests/test_mjau_v3_osv.py tests/test_mjau_v3_osv_snapshot.py tests/test_intelligence_opportunities.py
python -m ruff check src/mcp_trendpulse/mjau_v3 tests/test_mjau_v3_*.py
python -m compileall -q src/mcp_trendpulse/mjau_v3
```

**Actual result on Windows Python 3.13.5 against merged v1:** **171/171 passed**, lint/compile clean. Pytest with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` emitted one warning about `asyncio_mode` (expected: asynchronous plugin auto-load disabled for this bounded synchronous suite). The five new source-backed workflow tests verify separate Apple fruit/company identities, ambiguous Mercury naming across six languages, bounded Q30 alias missingness, real OSV positive/negative source semantics and the explicit v1 unknown-source baseline. The test suite is **not** a blind human judge, a full security scan or MCP specification conformance.

A separate **200-iteration offline, same-process, tracemalloc-enabled microbenchmark** on this resource-limited Windows machine measured:

| Code path | Median parse time | p95 parse time | Peak traced Python memory | JSON projected output |
| --- | ---: | ---: | ---: | ---: |
| A04 six-language original Q30 response | 10.9484 ms | 31.6255 ms | 28,964 B | 2,121 B |
| A10 original-source Jinja2 metadata projection (10 advisories) | 4.9207 ms | 7.9091 ms | 32,232 B | 8,321 B |

These are small in-process parse observations **with allocation tracing overhead**, not API latency or promised production user-response times. No network, temporary SQLite, model inferencing or paid resource used during those replays. They demonstrate bounded output and modest memory, not business usefulness scores.

## Explicit open gate and no-misrepresentation policy

- **Both remain plan-only/unregistered.** An approved v1-budgeted collector and a single reviewed MCP/CLI owner must integrate the plan and response projections before any end-user tool can invoke them; this branch does not quietly wire new functionality into production.
- **A04 review:** Wikidata source data CC0; verify the response's actual entity identity, bounded language scope, matching abstentions and real representative user success before release. No global automatic name-to-entity merge.
- **A10 review:** official OSV is aggregated from **heterogeneously licensed** upstream feeds; GHSA and PYSEC attribution hints reflect generally CC BY 4.0 upstream databases but individual source terms must be checked. Unknown `OSV-`/`CVE-` prefixes remain rights-unknown. No raw advisory descriptions, automatic remediation, claim of security, or unapproved downstream commercial reuse. Verify source attribution/citations in any future UI.
- **B08:** real stdio and Streamable HTTP MCP SDK client sessions already passed on v1, but independent [official conformance suite](https://github.com/modelcontextprotocol/conformance) `@modelcontextprotocol/conformance@0.1.16 --requirements 2025-11-25` has **not run**: isolated npm/Bun/Yarn installs could not finish fetching the dependency graph on this Windows host. A passing SDK smoke **is not** full conformance. No retry of unchanged stalled installers, test-only package in runtime, or claim of Tier 1.
- **Measured uplift gap:** this branch proves **distinct source answers not exposed by v1**, but not broader human-reviewed workflow throughput, vendor demand, remediation safety or independent release approval. No claim of “production ready.”

**Rollback:** close this isolated draft PR and discard only its A04/A10 files; existing merged v1 and the v2 companion remain byte-for-byte unchanged. Do not merge until full review and explicit authorization.
