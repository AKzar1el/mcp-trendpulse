# MJAU v3 A04/A10 — fourth adversarial engineering pass (2026-11-22)

**Target:** AKzar1el/mcp-trendpulse [draft PR #382](https://github.com/AKzar1el/mcp-trendpulse/pull/382), frozen base `a7fcd7bf8c258344906064058755040d6311c1bf`.

**Reviewer:** automated engineering self-review, a fourth method/sample, **not** a fourth independent human reviewer. Tested a separate managed Windows worktree; never registered a live connector or used real OSV/Wikidata provider quota. Existing V1 and V2 worktrees were not edited.

## New falsification findings, independently reproduced red

| Priority | Production path | Pre-fix behavior | Correction |
| --- | --- | --- | --- |
| P2 outbound request boundary | `mjau_v3/budgeted_sources.py::_request_json` | A URL with nonnumeric explicit port raised raw `ValueError` instead of uniformly rejecting the source request | Catch invalid parsed host/port as `IntelligenceError`; malformed IPv6 also denied |
| P2 upstream content-type acceptance | `mjau_v3/budgeted_sources.py::_request_json` | Successful JSON payload with fake `application/jsonp` or `text/plain; comment=json` passed naive substring MIME check | Accept exact `application/json` and `application/*+json` media types only; keep valid charset parameters and problem+json working |
| P2 misleading source completeness | `mjau_v3/wikidata.py::parse_qid_lookup` and `budgeted_sources.py::wikidata_identity` | A returned but explicitly `missing` QID occupied the entire entity map and was reported `source_coverage_complete=True`, and high-level status said `source_entities_observed` | Derive coverage from actually observed source item statuses; missing QIDs now remain `unknown_missing_entity` and report `source_entities_partially_observed` |

All failures were reproduced in fresh test cases **before** changing production code. The initial new red suite: **4 failed / 31 previously passing**; two additional direct/indirect missing-coverage assertions failed red before correcting the parser. After the first changes, 38/38 targeted cases passed; after the parser-level follow-up, both focused new completeness cases passed. No identity auto-confirmation, package safety assertion, automatic retries, new permissions, or API scope was added.

## Fresh execution evidence

- Reusable venv: `C:\Users\Tomi\Desktop\lol\mcp-trendpulse\.venv\Scripts\python.exe` (Python 3.13.5; pytest 9.1.1; FastMCP 3.4.11). This was used only as a test interpreter pointed at the isolated worktree through `PYTHONPATH=src`; no installs into the live service.
- Pre-change targeted baseline: **31/31 passed**.
- Initial red after adding negative cases: **4 failed, 31 passed** (expected).
- Targeted after first fixes: **38/38 passed**.
- Expanded V3 and selected shared V1 regular regressions after first fixes: **320 passed, 3 marked integration deselected**.
- Real separate stdio / protected HTTP MCP subprocess integrations after first fixes: **3 passed**. No live API requests.
- Additional source-completeness red reproduction: **2 failed**; after parser fix: **2 passed**.

### Final post-parser reruns

- **321 passed**, 3 integration tests deselected, in the final regular v3 + selected shared-v1 suite (exit 0).
- **3 real local MCP subprocess integration checks passed** together on the final code and test revision in 78.07s (exit 0): real stdio child, guarded HTTP security, and source-fixture HTTP e2e. No external provider calls, no live MCP installation.
- **Ruff, compileall, and git diff --check** passed on the final source and test files; no runtime dependencies added.

### Guarded HTTP startup diagnostic (environment reliability, not a source logic fix)

An intermediate combined integration rerun passed 2/3 but the third disposable HTTP child failed to become socket-ready inside its existing **50-second** startup deadline. The same test had passed earlier. A focused retry with captured child stderr then **passed in 36.98 seconds** without changing the source code; there was no reproduced protocol or validation bug. We retained the child-stderr error capture for future failures and aligned the guarded HTTP *test harness* bounded startup deadline to **90 seconds**, matching the existing Windows real-stdio test allowance. The combined three-transport rerun subsequently passed in full. This is an observed flaky cold-start test under a shared Windows environment; it is **not** a proven latency or capacity benchmark for a dedicated machine.

The GitHub CI status for the new commit is checked separately after publication; local green results never imply remote CI passed.

## Release boundary

Continue to allow **supervised, opt-in owner-local tests only**; `execute=False` remains the default. `execute=True` remains capped at **8 Wikidata and 10 OSV** requests per UTC day through the existing persistent budget. The original 16-tool TrendPulse MCP, CLI, V1/V2, scheduled workers, and public production registry are unchanged.

**Still NO-GO for automatic merge, deployment or public/commercial source-data redistribution** without outside-human workflow review, per-original-source attribution/permission checks, and explicit deployment-owner approval. OSV API use does not grant blanket upstream data rights. This fourth assistant-led pass does not substitute for those approvals.
