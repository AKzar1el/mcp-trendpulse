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
- **B08 updated 2026-11-21:** the previous package-manager blockage was bypassed with a **disposable, SHA-512-verified 111-package installer-free runner**. The actual official `@modelcontextprotocol/conformance@0.1.16 server --suite active` ran: **11/32 checks passed, 21 failed** on the unguarded 12-tool app, mostly because SDK reference-fixture-only media/resource/prompt/elicitation capabilities are absent. Its DNS-rebinding failure was independently confirmed and **fixed in a separate guarded, loopback-only HTTP helper**, then **5 targeted official scenarios / 6 checks passed**, including DNS **2/2**. See `docs/mjau-v3/b08-official-security-results-20261121.md`. Neither this active suite nor targeted subset is a complete frozen 2025-11-25 requirement-scored certification, and this PR does **not** modify production stdio startup.
- **Measured uplift gap:** this branch proves **distinct source answers not exposed by v1**, but not broader human-reviewed workflow throughput, vendor demand, remediation safety or independent release approval. No claim of “production ready.”

**Rollback:** close this isolated draft PR and discard only its A04/A10 files; existing merged v1 and the v2 companion remain byte-for-byte unchanged. Do not merge until full review and explicit authorization.

## Latest bounded acceptance and safety checkpoint (2026-11-21)

The original 171/171 test result above remains the historical first integration check. A follow-up **preregistered nine-call real-source comparison** (one Wikidata QID batch; eight OSV exact package/version queries) found A04's Q42 label missing in the scoped upstream response, correctly left unknown; confirmed official Q64 and Q30 six-language output, with bounded aliases. Six of eight original full OSV queries parsed normally; Django 2.2.0 exceeded the strict full-body 192KB cap and npm lodash 4.17.11 contained one GHSA advisory with **93 references**, exceeding the former per-advisory 30-reference rejection.

An independently documented small official `/v1/querybatch` proof returned ID/modified-only data: **Django 2.2.0 yielded 75/75 advisory IDs in 5,086 bytes**, within the same source cap. A narrowly scoped one-request compact query plan and strict parser were added under A10, alongside source-license hints, pagination/truncation abstention and a 100-ID projection cap. The prior lodash full-detail rejection was repaired to project up to 30 references / four safe links and report truncation while retaining **6/6 advisory IDs**. No original advisory bodies or unlicensed article text were stored.

**Current Windows local verification:** **207/207 regular tests**, plus **1/1 real guarded HTTP integration test**, Ruff and compileall green. A04 and A10 are still **plan-only** until the single integration owner reviews a budgeted source adapter, commercial source attribution and independent user workflows. Complete evidence: `docs/mjau-v3/source-acceptance-and-licenses-20261121.md` and `docs/mjau-v3/b08-official-security-results-20261121.md`. **This is not a production merge or user-facing release authorization.**

## Additional adversarial and real MCP E2E round (same day)

The 207+1 result above is an earlier validated checkpoint. Follow-up adversarial trials reproduced and fixed incomplete-QID/language false negatives; leaked credential-like OSV source-reference query links and encoded CR/LF/NUL; nonstring ecosystem inputs causing uncaught `TypeError`; malformed `null` Wikidata aliases; and pathological nesting leaking `RecursionError` instead of a controlled validation error. Added deterministic **550-payload malformed-shape fuzz** and real-source regression tests. A dedicated **test-only** FastMCP catalog verified 30 sequential real client calls plus a second **guarded HTTP client-server E2E** across separate processes, with no live-source registrations.

The existing A10 internal 75-ID Django projection remains audit-detailed at **50,590 JSON bytes**. An optional compact **MCP-facing projection** retains all 75 IDs/source links/modified dates/attribution warnings in **14,848 bytes (70.65% less)** without pretending the sample is a full security verdict. It is not a newly registered production tool. Local regression result: **242 regular tests + 2 separate guarded-real-HTTP integration tests passed**, Ruff/compileall clean; see `docs/mjau-v3/stress-qa-round2-20261121.md`. The release gate remains owner-reviewed source rights, budgeted MCP integration, independently adjudicated user workflows and explicit merge approval.

## 2026-11-22: opt-in two-source MCP and source-rights/holdout review

The earlier 'plan-only/unregistered' descriptions above are historical checkpoints. A **separately launched, opt-in two-tool stdio MCP** is now implemented **in this draft branch only**, without altering the installed community/hosted or v1 intelligence MCP tool catalogs. The two new modules `mjau_v3/budgeted_sources.py` and `mjau_v3/mcp.py` reuse the **existing v1 `BudgetCache` SQLite daily quotas, cooldowns and request locks**, with fixed origins, one request each, explicit `execute=True`, 8s timeout and 192KB response cap. Daily caps are 8 Wikimedia queries and 10 OSV one-item ID-only queries. Only validated source projections are cached; no original full OSV advisories or summaries. The original v1 generic market collector is **not** given additional source permissions or allowed to cache security advisory bodies.

Preregistered original-source technical holdout: **12/12 Wikidata name tasks**, **8/8 OSV package/version ID tasks**, with **2 extra Wikidata tasks unscored** after the source returned an invalid/unavailable response; **4+8** source operations, no extra retries. Source truth was extracted via a separate data-only scorer, *not* an independent human. An unrelated Windows SQLite temporary-directory cleanup error occurred after scoring; the summary was recovered from the printed comparisons and read-only budget/cache receipts without requerying. See `docs/mjau-v3/workflow-holdout-results-20261122.json`, the frozen preregistration, and `docs/mjau-v3/independent-review-packet-20261122.md`.

Rights: Wikidata structured records CC0; OSV has **heterogeneous upstream licenses**. The optional A10 tool returns factual ID/date/link metadata only, marks commercial bulk redistribution **not approved**, includes source-license references and never infers license grants from advisory prefixes. Engineering review, policy and exact validation instructions: `docs/mjau-v3/a04-a10-source-rights-review-20261122.md` and `docs/mjau-v3/opt-in-budgeted-mcp-review-20261122.md`. **Human independent workflow signoff, final public/commercial licensing and operator deployment approval are still pending.** No production merge, installation or automatic worker restart.

**Latest local suite:** 285/285 regular v3+v1 budget/source regressions, plus separately tested subprocess stdio initialization and 18/18 outbound transport threat-model cases; full three-case guarded HTTP/stdio integration matrix run separately. These are implementation checks and do not replace human reviewer signoff.
