# MJAU v2 — A03+B01 non-shipping integration preview

**Milestone:** isolated source-level + real stdio MCP smoke proof, **2026-11-21**. **Not production, not merged, not a global tool registration.**

**Preview branch:** `feat/mjau-v2-discovery-integration-preview-20261121` (base original v1 PR #328 commit `876957a874e4bc81c0470095254b5a6b0b189397`). The v1 PR is still draft and v3 owns independent A04/A10 code; the preview is not an integration PR.

**Included by design:** just `src/mcp_trendpulse/mjau_v2/__init__.py`, `depsdev_graph.py`, `openssf_scorecard.py`, corresponding `tests/test_mjau_v2_*.py`, and this report. No `cli.py`, `intelligence_mcp.py`, `intelligence_core.py`, `pyproject.toml`, `uv.lock`, workers, CI, v3 source, or production config is changed.

## Why A03 and B01 were selected ahead of the others

- **A03 deps.dev:** one-version resolved dependency graphs answer exact package dependency relationships that v1 npm/PyPI download counts cannot answer. Source scopes to provider-resolved *generic 64-bit Linux* installations; never infer installed customers or users. Generated deps.dev data is CC BY 4.0 with caching expressly permitted (https://docs.deps.dev/api/v3/).
- **B01 OpenSSF:** dated public Scorecard check observations answer a different source-backed software health question; never a security audit or proof of safety or purchasing demand. Published REST results are CDLA Permissive 2.0. REST datasets omit some checks and may use a bare `YYYY-MM-DD` date; the new parser preserves source precision. The official OpenSSF also offers an experimental first-party read-only stdio MCP; evaluate overlap and Windows binary/memory impact before registering any new public tool (https://github.com/ossf/scorecard/blob/main/docs/mcp.md).
- A01/A02/A07 remain useful but conditional source experiments; B02 has a documented contradictory provider support flag; A06 (429) and A08 (403+single-instance limitations) remain blocked. None has been silently promoted or discarded from research.

## Actual verification receipts

| Gate | Result | Notes |
| --- | --- | --- |
| A03+B01 preview unit tests | **124/124 authentic pytest PASS**, Ruff PASS | Real v1 imports, temporary files from exact GitHub preview branch; no checkout mutations |
| Combined targeted v1+preview regression | **383/383 authentic pytest PASS**, exit 0 | 11 selected original v1 MJAU/evidence modules + both preview test modules, pytest-asyncio enabled, `-m not integration`; **168.55 seconds pytest** (about 171.93 seconds wrapper) |
| v1 checkout stability | **PASS** | HEAD identical before/after full regression, working tree clean, no agents/workers restarted |
| B01 original-source completeness | **59/59 pytest PASS**, Ruff PASS + two native adapter GETs | `pallets/flask` source 7.1/10 14 checks, scan day 2026-11-09; `psf/requests` source 7.9/10 14 checks, scan day 2026-11-16; both real SQLite zero-network cache replays |
| A03 original-source evidence | **65/65 focused tests PASS** and prior native npm/PyPI proof with cache replay | Source original-success claims are on A03 feature branch; this preview intentionally made **no new A03 live call** |
| Real local stdio MCP session | **PASS, test-only** | FastMCP 3.4.11 on Windows. A manually staged temporary server initialized, advertised exactly `preview_depsdev` and `preview_scorecard`, both returned plan-only `status=planned` and 0 network attempts. An `execute=True` attempt was rejected by the preview wrapper. No new tools were registered in shared public/community MCP |
| Stdio startup | **One initial timeout / then PASS** | Initial 20-second client initialization deadline was too short for cold FastMCP startup on this Windows machine; increasing the test-only deadline to 90s allowed a normal handshake. This is a startup-latency concern to measure before deployment, **not** permission to change running services |

## Offline operational fit — 60-sample microbenchmark per mode

These numbers are from deterministic injected provider fixtures and the **original v1 SQLite BudgetCache**, with independent temporary cache root. They are not provider-network latency measurements and are not a forecast of production performance.

| Mode | p50 (ms) | p95 (ms) |
| --- | ---: | ---: |
| A03 plan-only, no I/O | 0.062 | 0.093 |
| A03 warm validated SQLite cache | 4.121 | 5.383 |
| B01 plan-only, no I/O | 0.048 | 0.087 |
| B01 warm validated SQLite cache | 3.833 | 4.567 |

The offline benchmark process peaked at **41.49 MiB Windows working set**, including Python runtime; **0 external provider requests**, two simulated source reservations and 60 cache replays per adapter. The **two actual Scorecard network samples** were **8.603s** and **2.640s**, with warm replay 0.110s/0.066s in that separate native test. Two live observations are not enough to claim network p50/p95. Larger real dependency graphs and simultaneous v3 jobs need independent peak-RAM/load assessment.

## Remaining mandatory gates

1. **Hold integration:** v1 #328 remains draft/moving; v3 agent is active. Only a single designated integration owner should rebase this preview onto the final approved v1 merge commit and add shared MCP/CLI wiring *after* v1 and v3 contracts settle. No merge, release or tool count increase now.
2. **A03 canonicalization:** official deps.dev says returned canonical package and version keys may differ from queried forms. Current adapter intentionally rejects unverified root-version mismatch to prevent false attribution. Before shipping, test actual canonicalization examples and implement only demonstrably safe equivalence or an explicit inconclusive status. Never disable root identity checks.
3. **B01 source coverage & duplication:** retain day-only scan dates and `unreported_checks_are_unknown`, source Scorecard version/commit, and partial check coverage. Compare the light Python adapter with OpenSSF's official experimental MCP; do not install a second heavy service merely to increase advertised tools.
4. **Decision usefulness:** independently review ≥5 actual research cases with a v1 baseline (including no-signal and wrong-identity cases), licensed attribution, precision/recall of relevant conclusions, source uncertainty and operational decision delta. Passing technical tests is not acceptance.
5. **True combined release QA:** rerun the **entire** v1+v2+v3 suite and a real stdio session on the **final integrated commit**; measure realistic fresh-provider p50/p95, 8-GB-machine peak RAM, cold startup, source quotas/rate limits and cleanup. No GitHub Actions charges are required—prefer existing local venv.
6. **Rollback:** preview branch can simply be abandoned. No live config was modified and no worker/tunnel needs restart.

**Conclusion:** A03+B01 has a clean **non-shipping integration preview** with real MCP transport and strong focused compatibility evidence. It is not authorized for production until the remaining gates pass. Candidate policies remain *prove useful or discard*, not “keep just because implemented.”

## Follow-up milestone: canonicalization, official MCP comparison, v1+v2+v3 compatibility — 2026-11-21

**Supersedes the earlier focused A03 count and 383-case cross-v1 test result above.** Earlier receipts were accurate at their original commits; later changes are tested below.

### 1. A03 root canonicalization: RESOLVED WITH GUARDED SCOPE

- Official deps.dev v3 says returned root package/version identifiers may be normalized. Real source `PYPI Colorama@0.04.6` returned `PYPI colorama@0.4.6`.
- Source commits `637c168e780a1c85817aa21fa16fe4e8b9b59bb9` and `8c81d541070625e2f20cf731c85b608c06c461bf`, tests `3a0023db1c99fef21293baf833ce9fe886de36ae`, copied into this preview.
- **77/77 authentic pytest PASS**, Ruff clean; native real adapter with original v1 SQLite BudgetCache PASS: 1 real GET (4.60s), second exact replay 0 network, temp cleanup successful.
- Only provably equivalent simple numeric PyPI release aliases use PEP 440 component-zero padding (and PEP 503 package-name normalization). Unverified root version => `identity_unverified`, no dependencies, no cache; unrelated root => invalid. No dependency upgrade or generalized SemVer parser.
- Official references: https://docs.deps.dev/api/v3/ ; https://packaging.python.org/en/latest/specifications/version-specifiers/ .

### 2. B01 first-party OpenSSF MCP overlap: DESIGN DECISION RECORDED

- Official experimental `scorecard mcp` exposes five read-only tools and two check resources via an independent Go binary; this is **broader and more informative than B01** and uses the same underlying REST API.
- Retain B01 **only as a narrow, budgeted score/heuristic observation embedded within TrendPulse**. Do not copy/reimplement the official `get_check_result`, `compare_repos`, `list_checks`, `explain_check` features. Full Scorecard research should use the official MCP separately when supported; if future integration makes its basic score cheaper/reliably available, re-evaluate B01 as redundant and discard.
- Official Windows x64 v5.7.0 asset is 29,007,450 bytes, but the temp first-party download did **not** complete checksum validation; no binary was executed/installed and no Go binary RSS/startup comparison is claimed. This missing optional binary benchmark must **not** be represented as a first-party performance failure.
- Official references: https://github.com/ossf/scorecard/blob/main/docs/mcp.md and https://github.com/ossf/scorecard/releases/tag/v5.7.0 .

### 3. Cross-track code compatibility: PASS, release readiness: NOT YET

- **541/541 targeted authentic pytest tests passed** with `pytest_asyncio.plugin` explicitly loaded, **Ruff passed** for staged v2/v3 source/tests. Execution included **11 original v1 modules + two v2 preview modules + seven v3 experimental test modules** and their fixture files. Temporary isolated Python environment imports from the local original v1 checkout.
- Pinned test versions: v1 `876957a874e4bc81c0470095254b5a6b0b189397`, v2 preview `cab95cb2a7c86e299c88176406c338e37ae23eb7`, v3 Stage0 `55e8cd7ffb4e4038a9ae591d4a45a2871098d45f`, v3 A04 `4460540c4aa2adea296e47185852634d3ccb65e8`, v3 A10 `a47bc5b71d051bb72978dfae3eff1f72b0949d53`.
- Total test runtime **95.21s pytest** / **163.18s overall wrapper including collection/startup**. Local original v1 HEAD stayed fixed and worktree clean. **No shared source, main merge, schedule, v3 branch, production registry, or GitHub Actions run was modified for this test.**
- GitHub PR #328 current v1 SHA has **14/14 associated PR workflow runs completed successfully** and shows `mergeable=true`, but remains **OPEN/DRAFT**, not owner-approved/merged. It is not valid to claim that all v1/v3 business gates are complete merely because CI is green.
- V3 Stage0, A04, A10 pilots continue to mark source usefulness/independent evidence gates **BLOCKED** even though they have passing unit tests. The combined 541 tests prove import/code compatibility, **not independent v3 decision uplift or integration approval**.

### Remaining release-level decisions

**Code interoperability and A03 canonicalization are resolved for the tested scope.** The official MCP overlap has a conservative, non-duplicative deployment decision. Still pending: v1 owner to mark PR #328 ready/merge when satisfied; separate v3 owner to finish its genuine source-evidence, rights and decision-quality gates; one authorized integration owner to merge only accepted features, run the **full** combined repository suite (541 was targeted, not full), real registered stdio MCP/production-shaped requests and p95 load/RSS tests on the merged commit. Do **not** approve or merge unproven v3 pilots, or GDELT A06 / social A08.
