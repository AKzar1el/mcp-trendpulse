# MJAU V2 A07 - Hugging Face Hub public catalog integration acceptance

**Decision:** ACCEPT ONLY the bounded, source-attributed public model/dataset
catalog observation as a fifth optional V2 adapter. The data is specialist AI
discovery evidence, not global search demand, model quality, adoption growth,
verified use rights, or buyer intent. No underlying model or dataset content
is retrieved. Production release/publication is NOT part of this decision.

**Source proof:** Existing isolated proof on
`feat/mjau-v2-discovery-a07-hf-20261121`, pinned base `b88b0a9`;
see `a07-hf-proof.md` and `a07-usefulness-protocol.md`. Integrated
against protected main after B02 at `5e31899e9c33e4822b6a599fc756d66e260ed6a4`.
V3 and running services remain separate.

## Five preregistered questions: result

- **Positive model listing (PASS):** one public `/api/models` snapshot
  yielded two source IDs, published likes/downloads and the provider
  `trendingScore`. Examples at the original 2026-11-21 observation:
  `thinkingmachines/Inkling-2-Mini` and `higurashi-ai/Haru-4B`.
- **Positive dataset listing (PASS):** one public `/api/datasets`
  snapshot gave source IDs, provider counters and the gating state.
  Examples: `Vyber07/cyber-security` (`gated=auto`) and
  `nvidia/USDCraft-10K`. Gated metadata is NOT permission to
  download its contents.
- **Positive bounded name search (PASS):** the original `search=security`
  public dataset probe yielded two name-matching catalog IDs; it is
  substring matching, not semantic topic relevance.
- **Impossible query (PASS, negative):** original never-seen name
  returned an empty Hub page, classified `no_data`, never no AI demand.
- **Adversarial (PASS):** a single provider-sorted page supplies no
  historical trajectory or denominator. Metrics are never relabeled
  as market share, paying customers, real users or model quality.

Thus 3/3 source-scoped positive tasks and 2/2 negative/abstention gates
passed from the original preregistered proof; neither task authorship nor
results establish a blinded human usefulness study. A07 is narrowly useful
to identify specific ML assets missing from the general V1 source catalog,
not to rank startups or forecast sales.

## Provider access and rights boundaries (checked 2026-11-22)

- Official Hub public API: https://huggingface.co/docs/hub/api
- Current API request rate-limit policy:
  https://huggingface.co/docs/hub/rate-limits
- Hub Terms: https://huggingface.co/terms-of-service
- Gated repositories, separate access rights:
  https://huggingface.co/docs/hub/models-gated
  and https://huggingface.co/docs/hub/datasets-gated

The provider publishes public listing endpoints, but rate limits and API
availability may change. Hub-hosted repository content can carry its own
licenses and gating requirements; this change does NOT claim blanket
rights to reuse, redistribute, train on or commercialize model weights,
dataset records, dataset cards, previews, README text or any third-party
content. Only public source IDs, links, timestamps, gating labels and
provider-supplied counters are exposed, preserving source attribution.
No access tokens, account features, private repositories or paid APIs
are used. Do not construct bulk catalogs or evade rate limits.

## Integrated behavior

A single, separate opt-in intelligence MCP tool:
`intelligence_hf_catalog(kind, limit=5, search="", execute=False)`.

- `kind` is exactly `models` or `datasets`; `limit` is 1 to 8,
  `search` at most a tightly validated printable name phrase.
- Default `execute=False` does **zero SQLite and zero source requests**.
  `execute=True` can make one public metadata GET per cache miss to an
  immutable approved HTTPS origin. No redirects, proxy, automatic retries,
  file downloads or unbounded pagination; 96 KiB response limit.
- Existing `BudgetCache` retained under separate V2 root, with maximum
  **4 reservations per UTC day** shared across the A07 model/dataset
  adapter, 6-hour validated SQLite cache and a 120-second local cooldown
  for HTTP 429/503.
- Private or malformed rows rejected, invalid type booleans caught, duplicate
  IDs guarded, null metrics stay unknown. Mixed invalid rows are not cached.
  Provider failures, absent rows and empty query results are distinct.
- Outputs label sorted *first-page* coverage, unknown download time
  window, no historical comparison, no independently verified model
  quality or buyer demand. Source strings are untrusted data, never
  executable instructions.
- Main community MCP stays **16** tools, hosted stays **6**. Only separately
  launched intelligence MCP changes **16 to 17** read-only tools. Nothing
  is restarted, scheduled, enabled by default or published.

## Authentic local receipts (fresh integration checkout)

- Original research branch: 62/62 A07 source tests and Ruff passed.
- On current-main integration: **88/88 focused source, integration,
  entrypoint and safety tests PASSED**; targeted Ruff all clean.
- Real independent MCP SDK subprocess via stdio, with a separate Python
  process, actual initialize/list_tools/call_tool, **11/11 checks PASSED**,
  including A07 plan-only and default 17-tool schema; **zero paid or
  source requests in offline mode**. No API credentials exposed.
- Offline benchmark: 40 plan-only calls p50 **0.111 ms**, p95 **0.151 ms**;
  40 warm native SQLite replays p50 **3.617 ms**, p95 **6.106 ms**.
  Only **one injected fake source response**, zero HTTP requests;
  native Windows temporary database directory closed/deleted without
  retries. These are NOT network response latency measurements.
- The original A07 provider proof previously made bounded public GETs
  with HTTP 200 and exact cache replay, all documented by original date.
  On 2026-11-22, the integrated **actual MCP tool function** performed
  exactly **one new public model-catalog GET** under the shared persistent
  local four-per-UTC-day source budget. It returned `observed_partial`
  with two current public IDs, `thinkingmachines/Inkling-2-Mini` and
  `unsloth/Inkling-2-Mini-GGUF`; an identical immediate second invocation
  was a verified validated SQLite cache hit with **zero additional GETs**.
  No paid API, auth, downloads, private content or unsupported inference.
- Full repository pytest, whole-project Ruff, offline lock and protected
  GitHub CI remain mandatory pre-merge gates; this document does not
  assert their success ahead of verification. No PyPI/GHCR release
  or production deployment is authorized by merging.

## V2 end-state decision register

| Candidate | Decision | Reason |
| --- | --- | --- |
| A01 semantic competitor discovery | DISCARD | Name-only catalog results do not demonstrate functional equivalence |
| A02 GitHub star-history cohorts | ACCEPT (merged #384) | Source-specific current surviving star cohorts, no historical net-growth claim |
| A03 deps.dev dependency graph | ACCEPT (merged #383) | Version-specific resolved free package dependency evidence |
| B01 OpenSSF Scorecard | ACCEPT (merged #383) | Dated source security heuristics, not an audit or flaw guarantee |
| B02 endoflife.date lifecycle | ACCEPT (merged #389) | Qualified EOL vs extended/commercial support phases, no entitlement claim |
| A07 Hugging Face public catalogs | ACCEPT subject to exact-head CI | New bounded AI asset research evidence; no content downloading |
| A06 / A08 | BLOCKED / EXCLUDED | Unreliable/unavailable access or insufficient value for current free-only scope |
| Other niche candidates | DEFER / EXCLUDE | No proven incremental user value under current constraints |

Separate MJAU V3 draft work retains its own no-merge gates and is
explicitly **not** part of this V2 integration.
