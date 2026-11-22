# TrendPulse — whole-project functional and effectiveness audit

**Audit date:** 2026-11-22. **Repository:** `AKzar1el/mcp-trendpulse`.
**Reference main at start:** `8e2229158bfe5fff8ad2bd915154bf3167d54946` (includes V3 source-only merge).
**Refreshed main during audit:** `c654c17356f4128921a1ea899edac1ba8046fa17`, incorporating PR #394's V2 Hugging Face fix and stronger external-source QA. **Rebased QA source:** `bdb5febac853bdebaf3534ff382f2b434351ff32`.
**Existing Codexify live runtime (preserved):** pinned wheel at `7cd13cfd1f7c081daab3487120fa34a7e8e89cf6`, standard 16 + optional V2 intelligence 17 = **33 live catalog tools**.

## Scope/immutability boundaries

The audit covers **the entire packaged project**, not only MJAU V2. It distinguishes:
- 16 original standard TrendPulse read-only MCP tools;
- 17 separate V1/V2 intelligence tools available in the existing Codexify combined catalog;
- 6 hosted DigestSEO TrendPulse MCP tools (separate entrypoint);
- 2 newly merged **V3 pilot** Wikidata/OSV tools, which are **separate and NOT REGISTERED/RELEASED** in production;
- the CLI (news/trends, offline research/briefs, source research, diagnostics);
- wheel, source archive, cache/quota/security contracts, platform CI and independent MCP SDK interoperability.

The V3 merge specifically withholds commercialization/production exposure pending **independent-human workflow review and rights-by-source assessment**. See `docs/mjau-v3/merge-containment-20261122.md`. No test report is authorization to expose V3.

## Whole-project packaging integrity

- The existing pinned Codexify wheel covers **74/74 tracked Python source modules** of its exact Git revision; all matched after normalizing Windows CRLF versus Git LF. No source code modules missing.
- Fresh **latest-main** `uv build --offline` produced both a wheel and an sdist. The wheel covers **81/81 Python source modules** at `8e22291`, including default, intelligence, hosted, CLI and V3 source. All matched Git exactly after newline normalization. Wheel SHA-256: `2410dfc515e76b78c77fc06ec2cce2421edda68f0af206f8c6ea24e32b0a0293`.
- Refreshed **rebased whole-project QA wheel + sdist** at `bdb5feb` also built fully offline. All **81/81 tracked Python modules** matched the rebased Git source after Windows newline normalization, including the upstream PR #394 HF fixes and the malformed-geo protection. Wheel SHA-256: `5a63cf4010fa8facad0ebd0dfe38295685f9e5c6280c2d58c47f349a89732f36`. The one later integration-test assertion change is test-only and cannot affect the wheel.
- The package's metadata version is still `0.2.47`. A locally built wheel is **not** a published PyPI/GHCR release. The live source was deliberately **not hot-reloaded** with unreleased V3.
- Existing deployed V2 runtime still reads dependencies from the older tested development venv via a read-only `.pth` bridge. This works but is **not an independently resolved/installed production environment**; changes in that shared venv could affect the live process at the next startup.

## Entire-repo regression and exposed test fragility

- Clean, isolated Windows/Python 3.13 default pytest: **3,077 passed, 13 integration tests intentionally deselected, three warnings**; 460.24 seconds. This is the meaningful full-suite result.
- Two entire suites deliberately competing for CPU/IO on the 8 GB Windows workstation: one returned **3,060 passed / 17 failed** after 918 seconds; the other isolated full suite returned all 3,077 passed. This is **stress/flakiness evidence**; it must not be misreported as 100% stable under concurrency.
- The stressed failures were 16 GitHub Issues fixture metadata assertions: module-import `NOW` became >5 minutes old by test execution, correctly triggering production freshness rejection. Test-only fix refreshes its test clock per case and avoids stale Python default parameter binding. One other scheduler-starved preflight worker fixture waited only 1 second after releasing a blocked thread; the bounded test cleanup allowance was increased to 2 seconds.
- Targeted changed-test proof: **44/44 passed**, Ruff clean, with no changes to source freshness validation or runtime worker safety. Full post-change protected CI remains the final merge gate.

## Real user-facing, source-scoped workflows

All entries below came through actual Codexify MCP tool calls, not a simulated parser:

| Actual question | Surface | Observation | Proven scope |
| --- | --- | --- | --- |
| What is trending in Slovenia? | V1 `get_top_trends` | 5 provider RSS trending terms; ~4.5 s via Codexify bridge | Relative source trends, not search volumes or purchases |
| What happened in AI news in last 3 days? | V1 `get_news_by_keyword` | 4 dated Google News **RSS headline-only** entries; ~6.8 s | Feed provenance; no claims of full article extraction |
| What is 90-day search interest for ChatGPT in Slovenia? | V1 `get_trends` | 90 dated normalized 0–100 daily observations; ~5.5 s | Interest index, **not** absolute queries |
| Which direct dependencies does `is-odd@3.0.1` have? | V2 deps.dev | 1 distinct direct dependency, source root verified | Graph facts, not vulnerability or user count |
| Published `pallets/flask` OpenSSF Scorecard? | V2 OpenSSF | Scan 2026-11-09, published aggregate 7.1, 14 checks | Heuristic upstream score, **not** a security audit |
| Public GitHub stargazer cohorts? | V2 A02 | Ten weekly rows, source-labelled partial observation | Active stars grouped by original dates, **not** true historic net growth |
| Node.js 20 EOL? | V2 B02 | Published EOL Apr 30, 2026; support caveat | Does not claim caller has paid extended-support entitlement |
| Hugging Face public model shortlist? | V2 A07 | Two public IDs, cached response, no downloaded files | Catalog metadata, **not** model quality or adoption |

V2 cache-backed actual calls used **zero new provider requests** where already cached; previous V2 QA found 5/5 source-scoped research responses and fixed concurrent duplicate quota spend across all five V2 adapters. This audit adds genuine V1/CLI/hosted/V3/package checks.

## Matched old-versus-latest protocol benchmark (small offline task)

Six direct MCP-SDK `get_categories(query=finance,limit=3)` calls against the saved original standard MCP and the latest full-source standard MCP returned **identical Finance, Public Finance and Business Finance category IDs**. There were **zero outbound source requests** in both cases. Receipt: `docs/full-project-baseline-receipt-20261122.json`.

| Metric | Older standard runtime | Latest standard source |
| --- | ---: | ---: |
| Cold process initialization + discovery, single run | 27,845 ms | 11,141 ms |
| Warm call median (6 samples) | 20.52 ms | 52.17 ms |
| Warm call p95 (6 samples) | 21.70 ms | 56.74 ms |
| Same answer? | Yes | Yes |

This task does **not** demonstrate broad human productivity uplift; the newest measured warm middleware path was slower by about 32 ms in this small sequence. The cold startup figures came from single sequential runs, so machine contention and import caches can dominate. First request in each case was materially slower (1.88s old, 1.09s latest); do not mistake its exclusion from the warm median for zero first-use cost.

## Cold-start performance limitation

A separate process-local import profile of latest intelligence MCP under Windows recorded **73.11 seconds wall time**, with **42.69 s to import FastMCP** and **18.19 s to register the 17-tool intelligence server** (timed import segments; main process start and other overhead account for the remainder). A fully independent stdio test of this endpoint also exceeded 90 seconds under competing workloads; warm persistent Codexify calls remained usable. Upstream FastMCP has a documented eager-import overhead issue: https://github.com/PrefectHQ/fastmcp/issues/3292 .

**Recommendation:** keep the MCP persistent with source-scoped hot reload, don't spawn a fresh Python server per research question. Do not claim this proves the library is universally defective: Windows antivirus, package cache, resource contention and storage also affect imports. Separate startup/transport latency from API response latency.

## Protocol/integration constraints

The four independently started interfaces have **16 + 17 + 6 + 2 = 41 tools across four separate MCP endpoints** (not one 41-tool production connector). SDK stdio was verified for the default, intelligence, hosted and opt-in V3 surfaces; V3 isolated plan-only checks **2/2 passed**, with zero provider calls and V3 NOT deployed. Additional run receipt: `docs/full-project-v3-stdio-receipt-20261122.json`.

The official MCP conformance runner requires independent HTTP server scenarios and revision-scoped requirements; generic SDK init/list/call smoke is **not** a complete conformance certification: https://github.com/modelcontextprotocol/conformance . Some older V3 conformance experiments and their limitations are documented separately in `docs/mjau-v3`.

### All 13 explicitly marked integration cases — first pass

- **6 passed, 7 failed** in 101.71 seconds, with 3,077 default tests deliberately deselected. This is **not** a green all-integration suite.
- Three separately marked V3 stdio and guarded-loopback-HTTP cases passed. V3 remained unregistered; no production deployment was performed.
- Five Google Trends integration cases raised the typed `ProviderRateLimitError` / tool `provider_rate_limited` receipt. The provider or shared pacer restricted requests; they are **blocked source-verification cases**, not proof of broken normalization logic. We did not disable throttling, reset any source cap or add retries/proxies.
- The live publisher test successfully reached the standard extraction stage, then erroneously expected Playwright article scraping to succeed even though browser egress is intentionally disabled until pinned network controls exist. Test expectation was updated to prove extraction plus the explicit protective rejection.
- The topic test requested `CATS` as if it should yield an empty result. The actual public API intentionally rejects unsupported topic identifiers; the test now expects the typed `ToolError` rather than masking invalid input.
- The tests now **skip explicitly and visibly** only on the typed `provider_rate_limited` condition, while still failing on other provider errors or malformed returned data. A skip is unverified coverage, never a pass.

### Confirmed malformed-geography bug — red/green proof

- During the second integration pass, four rate-limited Google Trends cases correctly skipped and eight integration cases passed, but the remaining `get_trending_terms` test **failed** because `geo='USA'` was sent to the official RSS endpoint `https://trends.google.com/trending/rss?geo=USA`. Its HTTP 400 was surfaced as `provider_unavailable`, misleading callers into thinking the network was broken instead of their input.
- A newly preregistered **no-network regression test was RED before any code change**: the invalid `USA` selector actually called the forbidden provider fixture.
- **Surgical production fix:** `news.normalize_trending_geo` validates just the documented Trending Now selector syntax (empty worldwide, two-letter country, `CC-subdivision`, three-digit DMA), normalizes ASCII case, and raises a local `ValueError` for malformed selectors. Both public MCP entry points `get_trending_terms` and `get_top_trends` validate **before provider selection**; both underlying news helpers also validate before transport, protecting direct CLI/provider use. No Google requests or quota reservations are spent on invalid geo inputs.
- Valid/invalid boundary and existing trending-term, provider-boundary and worker-limit suites: **151/151 targeted tests PASSED**, whole-project Ruff for changed modules clean. The input syntax test does not certify all syntactically well-formed geographic codes are real Google-supported regions.
- The integration test now expects a typed local error for `geo='USA'`, not an empty zero-demand result. Upstream HTTP 400 is never misreported as a valid empty trends feed.

**Final integration rerun on the audit branch:** **9 passed, 4 explicitly skipped, zero failed** (13 cases; 3,103 non-integration tests deselected, two warnings; 347.21 seconds). The four skips mean Google Trends source availability could not be independently proved in those cases; they are never counted as successes. The three local V3 stdio/HTTP compatibility and security checks passed, without live V3 activation.

**Concurrent repository development:** PR #394 advanced `main` to `c654c17356f4128921a1ea899edac1ba8046fa17` during the audit. It independently fixed the old browser/CATS expectations and introduced a stronger shared `external_source_available` fixture for typed upstream failures, plus real V2 Hugging Face and tool-discovery improvements. Our final PR will integrate that current main and avoid duplicate edits to those same integration tests; the only additional integration expectation needed is that malformed `geo='USA'` is rejected locally rather than transmitted. The independent old-vs-new latency receipt remains pinned to the earlier `8e22291` audit baseline, **not** the subsequently merged `c654c17` head.

This is a genuine integration/product-availability limit: provider-restricted workflows are temporarily unavailable even when tests of source validation and caching remain green. A separate live Codexify call had returned genuine Google Trends data earlier, so the restricted integration run does not establish a permanent service outage.

**Release discipline:** No paid APIs, public releases, V3 activation, worker restarts, unrelated MCP reloads or merges unless the new exact-head tests and protected CI pass.

## Still being checked

- Reconcile this QA branch with PR #394's improved upstream provider classifier; preserve all provider-safety semantics and rerun the exact final-head acceptance/CI.
- Whole 4-surface independent MCP harness with long bounded Windows cold-start handling; measure rather than simply masking slow startup.
- Final Ruff, offline dependency lock validation, packaging proof, exact-head protected CI, and safe scoped QA PR/merge if all checks pass.
