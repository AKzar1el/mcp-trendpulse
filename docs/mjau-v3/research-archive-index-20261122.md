# MJAU v3 research archive - preserved before branch cleanup

**Archived:** 2026-11-22, for the user-directed cleanup of superseded MJAU v3 branches and closed PRs.

This index records immutable evidence originally stored on four historical research branches. The contents below are **historical experiments**, not current release guidance and not instructions to register extra tools. Current scope is still only two opt-in sources, A04 Wikidata and A10 OSV, as described in `docs/mjau-v3/merge-containment-20261122.md`.

| Historical source | Repository files preserved | Disposition |
| --- | --- | --- |
| `feat/mjau-v3-evidence-a04-20261121` (`e6c14d5`, closed PR #377) | `a04-evidence.md` | Original Wikidata feasibility evidence; A04 is included only as the separately started, restricted two-tool MCP |
| `feat/mjau-v3-evidence-a10-20261121` (`484a48c`, closed PR #378) | `a10-evidence.md` | Original OSV source evidence; no blanket commercial content-reuse grant |
| `feat/mjau-v3-evidence-a11-20261121` (`1461519`) | `a11-bm25-results.md`, `a11-preregistered-bm25-benchmark.md`, `tests/fixtures/mjau_v3/a11_preregistered_tool_tasks_20261121.json` | A11 BM25 discovery rejected; **no A11 runtime module or benchmark test reintroduced** |
| `feat/mjau-v3-evidence-stage0-20261121` (`868a5fb`, closed PR #376) | `stage0-evidence.md`, `lean-release-scope-20261121.md`, `release-gates-20261121.md`, `a09-license-gate.md`, `a11-tool-search-benchmark-gate.md`, `b09-last-chance-preregistered.md`, `b09-last-chance-results.md`, `connection-and-real-mcp-20261121.md` | Preserves prune rationale and rejection decisions, **not** the historical A05 prototype or its runtime |

All listed files were copied from the specified frozen branch commits into their original repository paths. The A11 benchmark note had one trailing space removed to pass Git whitespace checks; its meaning is unchanged. This keeps source records reachable on `main` when the superseded GitHub branches are deleted. Earlier branch-specific links in old reports are historical; these `main` files are the durable archival locations.

**Release controls remain separate:** The independent human review packet is unsigned; source-specific public/commercial OSV rights and deployment owner approval are not fabricated by archiving this research. No historical source-collector code, extra CLI commands, worker schedules, dependencies or public MCP registrations were added by this archival step.
