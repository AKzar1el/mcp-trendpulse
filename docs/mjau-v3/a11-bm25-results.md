# MJAU v3 A11 — scored BM25 discovery proof

**Final pilot decision (2026-11-21): REJECTED / DISCARD the BM25SearchTransform for the 12-tool optional intelligence MCP.** This is a refusal to implement a tool-search feature, **not** a change to any production MCP server.

## Tested source and preregistration

- Pin: v1 staging `b88b0a974b5dcdb480e4fd8c4da5f7bbca68e98e`, 12 actual read-only optional intelligence tools in `src/mcp_trendpulse/intelligence_mcp.py`.
- Runtime: existing Windows local Python environment with **FastMCP 3.4.11**, in-memory `Client(intel_mcp)`, `BM25SearchTransform(max_results=5)` added only inside a disposable Python process.
- Frozen task set: `tests/fixtures/mjau_v3/a11_preregistered_tool_tasks_20261121.json` at preregistration commit `b3d5932384ba8507bb45cd62087a80a6972171a7`, with 24 functional prompts (two expected per tool) and four explicitly out-of-scope negatives.
- Correctness target was fixed in `docs/mjau-v3/a11-preregistered-bm25-benchmark.md` **before the full 28-task run**. Three earlier illustrative example searches had been tried before task-set creation; these prompts are **researcher-authored**, not blinded real-user tasks. No LLM agent was run.

## Actual results: three independent Python processes

| Metric | Run 1 | Run 2 | Run 3 |
| --- | ---: | ---: | ---: |
| Correct first tool, 24 functional queries | **16/24** | **16/24** | **16/24** |
| Expected tool included in top 5 | **23/24** | **23/24** | **23/24** |
| Correct no-tool abstention, four unrelated queries | **0/4** | **0/4** | **0/4** |
| Search p95, milliseconds | 20.132 | 38.178 | 36.963 |
| Two-search total context estimate, JSON bytes | 9,246 | 9,246 | 9,246 |
| Pre-registered protective thresholds passed | **No** | **No** | **No** |

**Same eight first-choice mistakes on all three runs:** `c02`, `c05`, `c08`, `c10`, `c12`, `c14`, `c18`, `c22`. The eight mistakes span source-cataloging, collection, job-pain analysis, provider settings/setup, snapshot observation, public-market hunting, and opportunity evaluation. First-tool correctness was **66.7%**, below the frozen **22/24 = 91.7%** threshold.

All four unrelated requests (`c25` repository deletion, `c26` sales email, `c27` guaranteed revenue forecast, `c28` inaccessible private GSC) returned a plausible-looking **irrelevant tool suggestion**, rather than abstaining. In this pilot the proxy did **not execute** any of those requests; its `call_tool` path explicitly rejected an unknown tool and an unapproved provider source. This measures discovery over-selection, **not** an access-control exploit.

## Actual overhead and savings

- Direct v1 12-tool `tools/list` schema was **10,159 UTF-8 JSON bytes**.
- BM25-only advertised two proxy schemas (`search_tools`, `call_tool`) required **1,226 bytes**.
- Median returned top-5 search result was **4,010 bytes**, so total visible data after one search is approximately **5,236 bytes**; after two searches **9,246 bytes**, only **913 bytes** less than the direct v1 catalog; after three searches **13,256 bytes**, already **3,097 bytes more**.
- First run search p50/p95 **16.688/20.132 ms**; later runs' p95 increased to **38.178/36.963 ms**. For the safe `intelligence_source_catalog` function, direct MCP call p50 **8.956 ms** and via `call_tool` proxy p50 **11.884 ms** in the first process, **before** adding search latency.
- These counts are **serialized JSON bytes, not model tokenizer counts**; in-memory timings are **not end-user response latency**. The model might choose tools differently when reading the full descriptions; no claim of measured baseline model-agent accuracy is made.

## Gate assessment and consequences

| Frozen A11 gate | Result |
| --- | --- |
| First-choice correctness at least 22/24 | **Fail** — 16/24 |
| Safe abstention on at least 3/4 unrelated tasks | **Fail** — 0/4 |
| Meaningful two-search context reduction | **Marginal pass** — 913 bytes (9.0%) |
| Search p95 below 125 ms | Pass — at most 38.2 ms observed |
| Safe catalog proxy, reject unknown tool and invalid source | Pass |

**REJECTED/DISCARDED as a production improvement.** Extra search/proxy calls on a small catalog bring a high top-hit error rate and cannot responsibly claim task-productivity improvement. We will not expose `search_tools`/`call_tool` on the existing default community or optional MCP, edit the tool manifest/registry, add dependencies, or schedule a worker. The experimental harness and this ledger remain on a separate unmerged research branch only; no release PR should merge them.

A future revisit requires a *substantially larger catalog*, representative preregistered real-user tasks, randomized paired LLM-agent runs with actual invocation outcomes and tokenization, security refusal/no-tool behavior, and genuinely favorable accuracy/latency trade-offs. A temporary registry search that merely reduces `tools/list` bytes without improving task outcomes is not enough.

## Exact reproducibility / rollback

From the pinned isolated branch on Windows:

```powershell
$env:PYTHONPATH=(Join-Path (Get-Location) 'src')
python -m pytest -q tests/test_mjau_v3_bm25.py
& 'C:\Users\Tomi\Desktop\lol\mcp-trendpulse\.venv\Scripts\python.exe' -u tests/test_mjau_v3_bm25.py --benchmark
```

The script modifies the FastMCP server object **only in its subprocess** and performs only in-memory search/safe catalog calls. No external source API or account calls, no user credentials, no distributed service changes, no real model charges, no production authorization, and no persistent cache were used. Experimental branch can be closed or deleted without production rollback.
