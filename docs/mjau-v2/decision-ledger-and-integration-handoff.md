# MJAU v2 — Integration handoff and strict proof/discard ledger

**Prepared:** 2026-11-21. **Scope owner:** MJAU v2 discovery only, no v3 code or shared edits. **This is not integration/merge approval.**
**Planning authority:** `.planning/mjau-v2-plan.md` on `research/mjau-v2-plan-20261121`, intentionally left unchanged while v3 runs.
**Originally pinned v1 base:** `b88b0a974b5dcdb480e4fd8c4da5f7bbca68e98e`; v1 draft PR #328 is moving independently. During last combined test the local v1 checkout was clean and pinned at `876957a874e4bc81c0470095254b5a6b0b189397`; update this baseline only after a final v1 owner-controlled freeze.

## Final status of eight selected v2 candidates

| ID | Source-backed independent benefit vs v1 | Isolated branch / report | Real source | Focused pytest | Correct current gate |
| --- | --- | --- | --- | --- | --- |
| A01 | Official MCP Registry name/version candidates (not semantic competitor validation) | `feat/mjau-v2-discovery-a01-registry-20261121` / `a01-registry-proof.md` + `a01-usefulness-protocol.md` | Registry 3 case queries + prior `filesystem`; zero-network cache replay | 60 | **PROVISIONAL research source only**; measure candidate relevance / false-positive review |
| A02 | Repo weekly *surviving-star* cohorts, not net popularity/user growth | `feat/mjau-v2-discovery-a02-github-stars-20261121` / `a02-github-stars-proof.md` + `a02-usefulness-protocol.md` | GitHub 10 weeks for FastAPI and own repo; cache replay | 46 | **PROVISIONAL research source only**; preserve timezone/unstar caveats and verify independent research gain |
| A03 | Concrete ecosystem-specific resolved package dependency graphs | `feat/mjau-v2-discovery-a03-depsdev-20261121` / `a03-depsdev-proof.md` + `a03-usefulness-protocol.md` | npm and PyPI real graph cases; cache replay | 65 | **HIGH-PRIORITY integration candidate after remaining gates**, not yet accepted |
| A06 | GDELT DOC topical news timeline, distinct from v1 raw 15-minute feed | `feat/mjau-v2-discovery-a06-gdelt-pilot-20261121` / `a06-gdelt-doc-blocked.md` | 429 on **one** free bounded query, no retry | No adapter | **BLOCKED; exclude from release**, reconsider only with genuinely new allowed availability |
| A07 | Hub public model/dataset catalog IDs, popularity snapshots | `feat/mjau-v2-discovery-a07-hf-20261121` / `a07-hf-proof.md` + `a07-usefulness-protocol.md` | 2 models + 2 datasets native, 2 bounded name/no-data source checks; cache replay | 62 | **PROVISIONAL AI-specialist feature**; no universal time-series/rank and review Hub terms |
| A08 | Mastodon instance-level trending tag histories / Bluesky public search | `feat/mjau-v2-discovery-a08-social-pilot-20261121` / `a08-social-pilot.md` | Mastodon HTTP200, Bluesky HTTP403 | No adapter | **BLOCKED; exclude from release**; one instance cannot represent global social demand |
| B01 | OpenSSF per-repository *dated security heuristics* and explicit noncoverage | `feat/mjau-v2-discovery-b01-openssf-20261121` / `b01-openssf-proof.md` + `b01-usefulness-protocol.md` | Native ossf/scorecard 200, own repo 404; independent Flask/Requests 200 | 52 | **HIGH-PRIORITY source-due-diligence candidate**, not security certification |
| B02 | Community-curated software release support phases and dated EOL deadlines | `feat/mjau-v2-discovery-b02-eol-20261121` / `b02-eol-proof.md` + `b02-usefulness-protocol.md` | Native Node 22, Python 3.12, Node 20 (conflicted), unknown 404 | **57** | **BLOCKED for unconditional support assertions**; Node 20 EOL+maintained source conflict detected and surfaced |

All six functioning adapters have real original-source evidence, explicit bounded opt-in requests, zero-network repeat for valid cached source rows (when applicable), negative/error handling, safe output and existing v1 `BudgetCache` integration with **separate v2 default cache root**. No permanent polling, API tokens, paid compute, CI, shared MCP tool registration or v1/v3 file writes.

## Objective test receipts

1. **Six-module combined test on 2026-11-21:** **342/342 authentic pytest tests passed**; **Ruff clean** for all six source files and their tests. This includes B02's three new provider-contradiction cases. Every source is staged in a clean, unique temporary directory, imported alongside v1, not installed into production.
2. Combined test imported v1 from **`876957a874e4bc81c0470095254b5a6b0b189397`** and recorded **no HEAD movement**, **no working-tree modifications**, and successful QA cleanup.
3. A previous selected **11-file original v1-only regression** (on earlier pinned commit, with `pytest-asyncio`) showed **258 passed, 1 concurrency timing test failed** on a busy Windows machine; that exact test subsequently passed isolated. This is a **known intermittent baseline**, not a fully green overall suite or evidence of a v2-induced regression.
4. Native real-provider adapters ran keyless official sources; safe budget/caching response and cleanup separately checked. Synthetic unit tests do not replace those separate live observations. Not all six were tested together through an actual registered stdio MCP tool; none is registered yet.

## Official source use and uncertainty register

| Source | Source rights confirmed from primary documentation | Remaining integration limit |
| --- | --- | --- |
| Official MCP Registry | Open API v0.1 name substring search, latest-version filter | Publisher-supplied repository links and catalog names are **not** verified functional competitors or user-demand measurements. Confirm registry metadata reuse and publisher license expectations |
| GitHub historical stars | Official privacy-safe aggregate history endpoint, API v2026-03-10 | Removed historical stars absent, week/day boundaries provider-defined; check GitHub API terms/current throttles and no collection of individual profiles |
| Google deps.dev | **Generated data CC BY 4.0**; API caching expressly permitted | Google API Terms plus underlying source terms; must attribute generated resolved graphs and preserve environment-specific resolution |
| Hugging Face Hub | Official public Hub APIs and published 5-minute API rate limits | Public metadata is not blanket permission to reuse model/dataset contents or infer ranking quality; terms review needed for commercial-facing aggregation |
| OpenSSF Scorecard | REST API results **CDLA Permissive 2.0** from primary README | Per-check heuristics have false positives/negatives; missing scan/score not zero, aggregate score is not audit or risk guarantee |
| endoflife.date | Official v1 OpenAPI **MIT**; API remains beta | Independently check consequential dates with upstream vendor; Node 20 EOL+Maintained source inconsistency already demonstrated and marked partial |
| GDELT DOC | Free topic timeline candidate | 429 provider rate-limit blocks proof; no retries/circumvention |
| Mastodon / Bluesky | Public Mastodon instance tag trends; Bluesky source returned 403 | No global Mastodon estimates, Bluesky blocked, no opt-in accepted adapter |

Source references:
- https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/api/official-registry-api.md
- https://docs.github.com/en/rest/activity/starring?apiVersion=2026-03-10
- https://docs.deps.dev/api/v3/
- https://huggingface.co/docs/hub/en/api and https://huggingface.co/docs/hub/rate-limits
- https://github.com/ossf/scorecard/blob/main/README.md
- https://github.com/endoflife-date/endoflife.date/blob/master/api_v1/openapi.yml
- https://github.com/nodejs/Release/blob/main/schedule.json and https://devguide.python.org/versions/

## Clear handoff protocol (one future integration owner)

- **Do not merge these six independent branches into each other now.** All were based on old v1 draft SHA; use a final owner-pinned v1 settled commit once PR #328/M14 and parallel v3 evidence contracts are finished. No second owner touching v3's A04/A10 work.
- Keep A01 limited to **MCP registry name-search candidates** and B01 limited to **source-scored security metadata**; do not advertise verified competitors or secure/insecure grades. Keep user-readable scope and source URLs.
- If vendor/source data conflict (B02) or source is rate-limited (A06) or lacks essential coverage (A08), preserve the conflict/unavailability and **do not turn it into zero, false confidence, or sales recommendations**.
- Evaluate exact **final acceptance gates before merging**: official rights/attribution; correct 5-case utility against current v1 and manual review of false leads; p50/p95 wall latency and peak RAM from bounded true-process tests; local UTC-day request caps and cache isolation; authentic full v1+v2+v3 regression on the candidate combined commit; one real stdio MCP process session; no increase in default worker schedule, paid API or breaking user-visible tool schemas.
- Only candidates clearing **all** gates may be marked ACCEPTED, and only the single designated integration owner should wire shared CLI/intelligence MCP schemas. Candidates failing usefulness or cost/legal/quality gates must be **DISCARDED**, not carried in release. A06 and A08 have documentation-only branches and must not be integrated accidentally.
- **Potential cherry-pick collision:** all six prototypes add the same package marker path `src/mcp_trendpulse/mjau_v2/__init__.py`. That marker has been deliberately normalized to the same UTF-8 bytes across six branches. Import one marker once, then selectively copy only distinct source/tests/docs; inspect diffs before cherry-picking to avoid add/add conflicts.
- User authorization is required for production merge, release or any new default MCP tool registration; current user approved continued **research and proof work**, not unreviewed integration.

**Outcome:** six independently evidence-backed optional building blocks, two blocked pilots, **zero shipped additions**. Prefer quality over a large number of functions. The v3 teammate and original v1 code are unaffected.
