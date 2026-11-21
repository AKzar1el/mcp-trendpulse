# MJAU v3 A11 — Tool-discovery efficiency: REJECTED/DISCARDED

**Final decision on 2026-11-21: REJECTED/DISCARDED for the existing 12-tool catalog.** No transform added and no new proxy MCP tool exposed. The original preregistration below remains useful historical context; the scored findings at the end supersede its initial blocked status.

## What v1 already provides

The pinned v1 stage `b88b0a974b5dcdb480e4fd8c4da5f7bbca68e98e` defines **12** read-only optional intelligence MCP tools in `src/mcp_trendpulse/intelligence_mcp.py`. These are distinct from the production community MCP (16 tools), which is explicitly out of scope. Existing optional tool names include `intelligence_source_catalog`, `intelligence_plan`, `intelligence_collect`, `intelligence_analyze_job_postings`, `intelligence_provider_settings`, `intelligence_provider_setup`, `intelligence_observe_source_snapshots`, `intelligence_discover_current`, `intelligence_hunt_current`, `intelligence_opportunity_lanes`, `intelligence_evaluate_opportunities`, `intelligence_walk_forward_backtest`. This count is from source inspection, not a fresh real MCP `tools/list` observation.

The official [FastMCP tool-search documentation](https://github.com/PrefectHQ/fastmcp/blob/main/docs/v3/servers/transforms/tool-search.mdx) describes `BM25SearchTransform` as an optimization for **hundreds or thousands of tools**. It transforms the advertised catalog into synthetic `search_tools` and `call_tool` proxy tools; the original tools stay callable but hidden in discovery. For a 12-tool catalog that adds an additional search action and a proxy invocation, and may raise latency and wrong-tool risk without enough context saved to justify it. This is a reason to **benchmark**, not a measured regression or an authorization to change the server.

## Prespecified, repeatable real-agent proof protocol

Use the existing optional MCP process on its own ephemeral local test-only connection; do not modify shared `intelligence_mcp.py`, default community MCP, v1 schedules, root dependencies, credentials, cache or worker.

1. Pin the optional tool catalog schema, exact tested FastMCP version and protocol revision; record the exact 12 `tools/list` definitions, token counts and server process baseline. Validate baseline invocation and permissions with an official stdio MCP client.
2. Define at least **24 blinded representative questions** before running either arm: source availability/settings, catalog browsing, planning, single-source collection (plan-only), seedless discovery, multi-source hunt, historic snapshots, buyer-evidence evaluation, retrospective evaluation, unsupported/out-of-scope requests and prompt-injection attempts. Use the same input set, runtime conditions and allowed tools for both arms; include negative/no-tool cases and ambiguous requests.
3. Run arm A without BM25, then arm B with a **test-only isolated wrapper** applying `BM25SearchTransform`. Check that exposed tool-list differences are expected, direct access controls are unchanged, and unauthorized invocation is still denied.
4. On each case independently score first-tool correctness, success of actual read-only invocation, wrong-tool rate, refusal/no-tool correctness, per-task p50/p95 latency, context tokens sent, peak RAM, CPU, result provenance and API calls. Repeat runs with interleaved arm order where feasible. A correct search suggestion alone is not a successful invocation.
5. **ACCEPT only** if the blinded scored data demonstrate a meaningful net gain without material latency, reliability, security or permission regression. If inferior or no useful uplift, **DISCARD** the transform. Missing real-agent trial, unavailable FastMCP version or failed source access is **BLOCKED**, not a pass.

## Original preregistration checkpoint (superseded)

**No actual real-MCP discovery baseline or arm comparison has been executed.** The dedicated TrendPulse Codexify tunnel still responds `Tunnel-client has not been seen for 300 seconds`; this sandbox does not have the full local TrendPulse FastMCP runtime installed. No test counts, percent uplift, token or latency savings are claimed for A11. No package, source or production settings have changed.

The official [MCP conformance framework](https://github.com/modelcontextprotocol/conformance) requires a running reachable HTTP MCP endpoint for its server suite; this is separately **B08 BLOCKED**. A successful stdio unit or synthetic ranking simulation cannot stand in for that official protocol test.

**Rollback:** no A11 implementation exists to revert. This documentation records the gate; adding it never constitutes authorization to implement, deploy or merge a transform. Review only after the current branch's own CI completes and full user approval to integrate an ACCEPTed feature.

## 2026-11-21 scored A11 outcome — REJECTED/DISCARDED

The source-backed Windows God v5 integration has since executed the actual optional 12-tool FastMCP 3.4.11 in-memory catalog and the opt-in `BM25SearchTransform`. Frozen test-task definitions were committed **before the full 28-query benchmark** at `b3d5932384ba8507bb45cd62087a80a6972171a7` on the independent A11 research branch. In **three repeat runs** the first-tool score was only **16/24 (66.7%)**, the expected tool appeared in the top five for **23/24**, and safe abstentions were **0/4** on unrelated requests. All eight wrong first-choice task IDs repeated identically across runs. The proxy correctly rejected an unknown tool and an invalid provider; no access-control bypass was observed. Search p95 was 20.1–38.2 ms; estimated two-search schema-plus-results savings were only **913 UTF-8 JSON bytes** relative to directly advertising the existing 12 tools, with an extra search step and proxy invocation.

The frozen protective gates (first-tool accuracy at least 22/24, unrelated-request abstention at least 3/4) **failed**. This is a lexical search experiment with authored prompts, **not** a randomized real LLM-agent study or measured end-user productivity improvement. There is nevertheless enough negative evidence to **discard** the proposed transform for this small optional catalog; do not integrate, merge or release A11 or modify the default community MCP.

[Exact A11 benchmark script, frozen prompts and measured decision](https://github.com/AKzar1el/mcp-trendpulse/blob/feat/mjau-v3-evidence-a11-20261121/docs/mjau-v3/a11-bm25-results.md). The dedicated A11 branch is research evidence only, with **no release PR**, no shared-file edits and no production changes. Retest only if the catalog grows materially and independent model-agent comparisons justify a new decision.
