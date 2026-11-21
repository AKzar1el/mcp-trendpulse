# MJAU v3 A11 — prespecified BM25 tool discovery experiment

**Status before scoring: NOT YET TESTED. Experiment only, no merge/release authority.**
**Frozen source:** pinned v1 optional intelligence MCP at `b88b0a974b5dcdb480e4fd8c4da5f7bbca68e98e`, FastMCP 3.4.11 observed on Windows. New isolated branch `feat/mjau-v3-evidence-a11-20261121`.

## Question and fairness

For the **same** optional 12-tool catalog, does advertising only `search_tools` and `call_tool` using `BM25SearchTransform` improve useful tool discovery enough to outweigh extra client calls, potential wrong-tool suggestions, context and latency costs? There is **no authority** to change the default 16-tool community MCP or any shared registration.

An *offline lexical ranking test* is not a real agent study. The frozen JSON `tests/fixtures/mjau_v3/a11_preregistered_tool_tasks_20261121.json` contains 24 independently phrased, **agent-authored** functional prompts with two per known tool and four explicit out-of-scope negatives. They are not representative real-user traffic and were written after three separate example searches were explored; that exploratory exposure is a limitation.

Compare to v1's *actual* `Client(intel_mcp).list_tools()` catalog, not a synthetic 1,000-tool baseline. Baseline runtime selection by a model **cannot** be inferred from list size or analyst-assigned labels.

## Prespecified measurements and gates

1. Compare complete `tools/list` JSON schema bytes, transformed proxy tool list size, and sum of each `search_tools` JSON result bytes. Report context break-even for 1, 2 and 3 searches using bytes (not pretend tokenizer counts).
2. Score first-tool correctness and expected-in-top-5 on **24** positive questions, with the original source file frozen before running the full test; report misranks. For the four out-of-scope questions, a safe outcome must avoid confidently recommending a tool merely because the catalog contains one. If the search always offers irrelevant tools, record this explicitly.
3. On the actual FastMCP in-memory client, verify the `search_tools` index and `call_tool` proxy remain read-only: a safe catalog invocation succeeds; an invalid source is rejected; do not run `intelligence_collect(execute=True)` or any live query. Measure warmed search p50/p95, first-query latency, and memory peak if feasible.
4. For a narrow prototype to remain **PILOT-GATED** awaiting a real-agent randomized comparison, require first-tool correctness **at least 22/24**, meaningful savings at two searches, p95 search latency under 125 ms in this Windows test, zero privilege bypasses, and no more than **one of four** unrelated requests receiving a plausible tool as the top hit. These are local engineering thresholds, **not** proof of model-agent usefulness. If the prototype fails any protective threshold, **DISCARD** rather than expose a search proxy.
5. Real acceptance additionally requires repeated paired LLM-agent tasks measuring first-tool correctness, successful *actual* read-only invocation, token counts, p50/p95 task latency, refusal/no-tool behavior and security; independent quality review. A passing synthetic lexical benchmark is still **BLOCKED** for full release.

**Safety:** No network, no writes to shared files, no API key, no secrets, no worker, no CI workflow modification, no permanent new tool registration. Test runs only on an isolated managed worktree; new files live under `tests/test_mjau_v3_*.py`, `tests/fixtures/mjau_v3/`, and `docs/mjau-v3/`. A11 may be discarded with a single revert of this independent pilot branch. 
