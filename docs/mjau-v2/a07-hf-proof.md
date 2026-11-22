# MJAU v2 A07 — Hugging Face public model and dataset intelligence

**Status:** PROOF OF TECHNICAL VALUE, NOT APPROVED FOR INTEGRATION/RELEASE. **Date:** 2026-11-21.

**Repository/branch:** `AKzar1el/mcp-trendpulse` / `feat/mjau-v2-discovery-a07-hf-20261121`.

**Exact pinned v1 base:** `b88b0a974b5dcdb480e4fd8c4da5f7bbca68e98e`. **Module proof commit:** `b7066eafc2c772044a7821fc7a87fbbac7f8ea16`. **Test proof commit:** `38a5180b1b0679b0bf18f6cd06dd98c8bca4f63b`.
**File ownership:** `src/mcp_trendpulse/mjau_v2/hf_catalog.py` and `tests/test_mjau_v2_hf_catalog.py`, one package marker, this report. No v1/v3 CLI/MCP or background worker/config/lockfile changes.

## Distinct value

Hugging Face Hub's public API exposes model/dataset **catalog popularity metadata and provider trending-score order**, not a historical search-time series, general developer adoption, buyer budget or model-quality score. Compared to v1's existing news, macro, research papers, keyword and package download evidence, this is a different source-backed **AI specialist catalog**. It can name specific AI assets for further investigation, including source ID, created/modified dates, provider trendingScore, downloads, likes and gated-access flag. A single snapshot does **not** show growth, predict revenue, verify functionality or establish user count.

Official docs: https://huggingface.co/docs/hub/api ; https://huggingface.co/docs/hub/rate-limits ; https://huggingface.co/docs/huggingface_hub/package_reference/hf_api

## Small real-source proof

The real source adapter was executed on Windows in an **isolated temporary SQLite cache** against public, unauthenticated Hub endpoints:

- `GET https://huggingface.co/api/models?sort=trendingScore&direction=-1&limit=2`: **HTTP 200**, 2 records, 0 rejected. Examples: `thinkingmachines/Inkling-2-Mini` (source trendingScore **600**, downloads **136**, likes **836**) and `higurashi-ai/Haru-4B` (trendingScore **313.5**, downloads **7,323**, likes **5,698**). Source values reflect the instant sampled, not a certified lasting rank.
- `GET https://huggingface.co/api/datasets?sort=trendingScore&direction=-1&limit=2`: **HTTP 200**, 2 records, 0 rejected. Examples: `Vyber07/cyber-security` (trendingScore **183**, downloads **28,056**, likes **1,328**, gated status \`auto\`) and `nvidia/USDCraft-10K` (trendingScore **82**, downloads **55,150**, likes **132**, gated \`false\`).
- Both identical second calls returned **valid source-scoped SQLite cache hits**; second call \`network_performed=false\` and \`requests_attempted=0\`. Native Python exited **0**, temporary cache was removed safely.
- Public listing data only; **no gated model or dataset contents, files, weights, tokens, private profiles, or large asset downloads**.

## Safety and test receipts

- Plan-only default: zero SQLite, zero network. \`execute=True\` required; fixed \`https://huggingface.co/api/models|datasets\` endpoints, first page only, 1–8 public metadata records, optional bounded name search, 96 KiB max body, single GET per miss, no redirects/proxies/retries.
- Existing v1 \`BudgetCache\` reused but default root isolated to \`~/.mcp-trendpulse/mjau-v2-intelligence\`. Maximum 4 API reservations per UTC day, 6-hour scrubbed cache, 429/503 cooldown, no use of Hugging Face tokens. Validate cache against exact kind/name/limit and raw metrics on replay.
- Source records are never executable instructions. Private entries excluded; null metrics treated as unknown not zero. Gated status is preserved, no statement of access rights or quality. Lists are partial first-page catalog samples; model/dataset metrics never summed into general market share.
- First pytest run exposed a **numeric gated-flag type confusion** (\`0 == False\` in Python), resulting in 1 fail and 60 passes. Corrected by exact type validation; added \`gated=1\` regression. Latest **62/62 authentic pytest passed**, **Ruff passed**. Not a shimmed runner.
- Verified two small live-source executions and two cache replays with original v1 SQLite; clean interpreter exit and safe temp cleanup.
- Original v1 targeted eleven-file regression in parallel environment: **258 passed and one timing-sensitive single-flight concurrency assertion failed once**, then that unchanged test passed isolated. This is not a verified fully green full-repo suite. v1 checkout remains at exact pinned SHA and clean.
- Full legal/provider-terms review for commercial-facing reuse, independent real-decision scoring and unified v1+v2+v3 MCP integration are **not complete**. The API's free anonymous rate limits can vary.

## Mandatory pass-or-discard decision

**Technically useful evidence class; provisional KEEP FOR RESEARCH ONLY, not automatic acceptance.** Before integration compare representative AI opportunity decisions against v1 baseline, measure real false positives and unverified claims, review provider API terms/attribution, ensure no stale/misleading popularity rankings, then rerun fully scoped merged tests on the exact integration commit. A feature that does not improve real research decisions must be **DISCARDED**, regardless of 62 passing tests. Do not add new background workers or public MCP functions without explicit integration approval.
