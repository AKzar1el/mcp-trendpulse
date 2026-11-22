# Predeclared five-case usefulness protocol (a07)

Fixed **before further source sampling**, 2026-11-21. Real-source pass alone does not equal product acceptance. No changes to MJAU v1/v3 or user account.

## Tasks

1. Positive 1: current 2-item public model listing names concrete model IDs and provider-defined likes/downloads/trendingScore with timestamps; v1 has no such model-specific catalog.

2. Positive 2: current 2-item public dataset listing names concrete dataset IDs with the same source-scoped metrics; gated status and source detail link remain preserved.

3. Positive 3: source-side 2-item `search=security` restricted dataset catalog gives name-matched relevant entries or clearly `no_data`, never semantic equivalence without review.

4. Negative 1: an impossibly named catalog query yields `no_data` rather than zero AI demand; private/gated records never trigger file download.

5. Adversarial 2: current likes/downloads/trendingScore lack a universal denominator or historical trajectory; a single snapshot must never become growth, market share or model quality.

## Outcome threshold

At least two source-scoped positives produce distinct real catalog leads unavailable in v1; no fabricated growth or access claims, and all adversarial cases abstain. Maximum 2 new HTTP GETs beyond earlier 2 model and 2 dataset samples.

Record exact source URL/response category, observed-at, named correct answers, no-signal decisions, false positives, cache calls and any contradiction against original provider/v1. A 429/403/unavailable finding is BLOCKED, never zero. An irrelevant answer is DISCARD unless a demonstrably better source can be validated without paying or circumventing protections.

## Evaluated outcome — 2026-11-21

**Positive model catalog:** native adapter retrieved 2 real model IDs on `sort=trendingScore`, with provider downloads/likes/trending scores, including `thinkingmachines/Inkling-2-Mini` and `higurashi-ai/Haru-4B`, exact source links and gating flags. Validated SQLite cache replay zero-network.
**Positive dataset catalog:** native adapter retrieved 2 real dataset IDs, including `Vyber07/cyber-security` (provider `gated=auto`) and `nvidia/USDCraft-10K`; no dataset contents downloaded. Cache replay zero-network.
**Positive name search:** direct bounded source GET for datasets `search=security` returned 2 matching IDs: `Vyber07/cyber-security`, `oi-uae/cyber-security`. New adapter's free text search is **name-substring only**, not model semantic quality or inferred topic equivalence. The real search query was a source feasibility check, not an extra native-adapter acceptance run.
**Negative impossible query:** `search=nonexistent-mjau-20261121` returned HTTP 200 and **zero rows**; this is `no_data` in a scoped Hub catalog, *not zero AI demand*. Private entries and invalid gated flags fail closed in authentic pytest.
**Adversarial:** these are one-page, provider-defined popularity snapshots; no growth rate, sales conversion, downloads normalized by time, global usage or model performance can be claimed.

**5-case result:** 3/3 bounded positive catalog/name-lookup questions answerable with source-attributed IDs and 2/2 adversarial abstention gates supported. **Decision:** A07 is **provisionally useful specialist AI catalog evidence**, still blocked for final integration until Hub data-use/attribution review, p50/p95/resource gate and post-rebase tests.
