# V3 startup and warm-dispatch diagnosis (2026-11-23)

**Scope:** source-only local 35-tool unified V1/V2/V3 MCP after QA-only PR #429. No public release, no paid API, no user-owned long-running source restart, no worker configuration changes. All measurements are on the user's Windows development machine (Python 3.13.5). They are engineering observations, not buyer productivity or latency guarantees.

## Reproducible 10-round cold import benchmark

New bounded diagnostic: `python scripts/measure_unified_cold_start.py --rounds 10`. It alternates the order of 10 fresh subprocess starts for the **full 35-tool unified module** and the separate **two-tool V3-only module**, imports only module registration code, never calls tools or sources, and exits every child. It reports process+import wall time separately from each import phase. Both modes are valid, but **not feature equivalent**: the unified mode includes all V1 and V2 capabilities; V3-only excludes them.

| Python import/process measure | Full 35-tool unified | Two-tool V3 only |
| --- | ---: | ---: |
| Median new process plus imports | **5,910.69 ms** | **3,652.60 ms** |
| Observed range across 10 alternating cold starts | 5,033.13-9,264.03 ms | 2,772.58-6,508.29 ms |
| FastMCP import median | 1,633.41 ms | 1,600.69 ms |
| Existing V1 community server module import | **3,456.78 ms** | Not imported |
| V2 intelligence MCP registration | 56.47 ms | Not imported |
| V3 source tool registration after V1/V2 imports | **13.92 ms** | V3-only initial import 1,445.08 ms (includes its source budget/cache dependency imports) |
| Parent unified wiring module | **1.91 ms** | Not used |

**Attribution:** the new V3 tool registration and unified parent are under 20ms of the typical unified import path; shared FastMCP and pre-existing community V1 are the dominant contributors. An earlier independent run saw 10.5-34.5s four-launch unified cold startup and a single 58s outlier under different host load. Both results are real for their windows. The variance points to the broad dependency/import stack and host process/IO scheduling, but does **not prove** Windows Defender, disk, CPU throttling or one third-party package is the unique cause.

A separate `python -X importtime` inspection found heavy original V1 imports: `newspaper.text`, `nltk`, `pandas` and their dependencies. Removing or lazy-loading these would require changing shared V1 news/article/Trends operations and annotation/provider imports. It is **not justified** in this narrowly scoped source-only V3 phase without a new cross-service performance regression and security review. We did not rewrite public V1 or make an unmeasured startup claim.

## Matched warm 33-vs-35-tool dispatch (same original V1/V2)

A separate in-process FastMCP A/B, reproducible with `python scripts/measure_unified_warm_dispatch.py`, mounted the **exact same original V1 community and V2 intelligence server objects** as the 33-tool baseline and compared them to the true source-only 35-tool unified server. The order alternated for five rounds. In each arm/round: 14 valid `intelligence_source_catalog(wave=1)` calls, seven rejected invalid V1 news calls, and 14 `tools/list` checks. In the unified arm also five valid plan-only V3 OSV metadata requests. No remote sources or daily budgets were spent. All source-catalog outputs matched exactly across rounds and arms; all expected errors remained errors; all 33 existing tool names remained available.

| Measured warm in-process catalog RPC median across 5 rounds | Result |
| --- | ---: |
| Baseline 33-tool V1/V2 | **5.686 ms** |
| Unified 35-tool V1/V2/V3 | **5.912 ms** |
| Observed difference | **+0.226 ms**, unified slower |

This is a tiny measured warm call overhead, **not** a guaranteed bound, statistically significant regression, full HTTP network measurement or proof of human productivity. It confirms that extra registration did not break existing V1/V2 catalog results in the tested same-process setup. The broader 3,213+ tests and independent source-oracle source-backed trial remain separate evidence.

A **second independent execution** of the same script (five more alternating rounds on the same machine under a different load) also preserved exact 33/35-tool catalog parity. It reported **11.816 ms** for the 33-tool baseline versus **11.562 ms** for the 35-tool unified server: **-0.254 ms**, this time with unified slightly faster. The change of sign and larger absolute times reinforce the limited conclusion: no meaningful warm-call performance regression observed, but **no reproducible speed advantage** and no statistically significant human productivity claim. They are two small engineering repetitions, not controlled human trials.

The prior nine exact public Wikidata/OSV source cases had a direct original-API first lookup median **438.23 ms** versus V3 MCP **999.15 ms**; repeated V3 cached lookups took **81-98 ms**. Those source tasks are different from a no-network catalog RPC and are not directly interchangeable. **V3 is not claimed to be faster than a knowledgeable engineer making one direct API request.**

## Production-safe operating choice

- For **explicit supervised local use** needing all 35 tools, create **one** client-managed stdio connection from the source checkout (`python -m mcp_trendpulse.mjau_v3.unified_mcp`), then keep it open for repeated tasks; avoid repeated process startup. No extra daemon or unsafe public listener is necessary.
- For a user needing **only** the two exact V3 source functions, `python -m mcp_trendpulse.mjau_v3.mcp` is an existing optional narrower entrypoint, typically faster to import, but it does **not** provide V1/V2 and must not be substituted silently.
- V3 source calls remain plan-only unless `execute=True` is explicitly sent; official providers' quotas, cache, attribution and source rights remain enforced. Never bypass Google Trends normal upstream throttles.
- Do not expose unauthenticated HTTP outside localhost or hot-reload the existing live 33-tool connector; public packaging still excludes V3 until external source-rights and independent-human gates are accepted.

## Decision / external blockers

**Cold-start investigation: completed; no proven V3-specific code defect to fix.** Because the startup costs are mainly inherited from V1/FastMCP, changing shared production/news dependency loading would be a cross-service change with safety and compatibility implications. The conservative solution for the V3 evaluation phase is a persistent MCP session and optional V3-only mode for its narrower task. The profiler and opt-in regression check preserve a repeatable record if host or library upgrades change this. Do not report a code speedup that was not implemented.

The separate [independent human review #426](https://github.com/AKzar1el/mcp-trendpulse/issues/426) and [original OSV feed rights review #427](https://github.com/AKzar1el/mcp-trendpulse/issues/427) remain **unapproved external gates for a public/commercial release**. Official all-fixture MCP requirement conformance is also not certified; the existing read-only 35-tool server passes applicable initialize/list/ping/error + Host/Origin protection but does not implement arbitrary image/audio/prompt/elicitation fixture tools. Do not add fake features merely to game a fixture-specific pass rate.

**Final user value:** existing 33-tool users experience no runtime config changes. Owner-authorized 35-tool supervised local source research is technically ready with stable warm calls and accurate public-source output; public/hosted release and human-level productivity uplift are not claimed.
