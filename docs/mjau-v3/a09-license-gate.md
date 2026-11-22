# MJAU v3 A09 — Apple App Store competitor catalog pilot: license gate

**Decision: LICENSE-BLOCKED / no implementation / no accepted capability.** A narrow real-source metadata-only US/SI pilot has since passed; see appended dated section.
Reviewed 2026-11-21. This is a source-access and legal-use checkpoint, not a feature proof.

## Proposed distinct question versus MJAU v1

Find narrowly scoped published Apple App Store alternatives for an explicit app term or store ID in two requested country storefronts. V1 packages/GitHub Issues do not contain a consumer iOS app catalog. Store search result ordering cannot be interpreted as app downloads, users, sales, ranking share, buyer willingness or forecast demand.

## Official source and rights

- Apple [iTunes Search API](https://performance-partners.apple.com/search-api) provides fixed-origin `itunes.apple.com/search` and ID-based `/lookup` requests, with `country`, `entity=software`, and a small `limit`. Apple documents an approximate rate limit of **20 calls per minute**, subject to change. A conservative pilot would plan no more than one country-specific request at a time and at most two in total, with local quota/cache managed by existing v1 infrastructure.
- Apple [Search API overview and legal conditions](https://developer.apple.com/library/archive/documentation/AudioVideo/Conceptual/iTuneSearchAPI/) explicitly restrict promotional assets such as app icons, screenshots, artwork and previews to promoting store content, with app-store badges/link placement requirements. Those terms do not by themselves demonstrate unconditional permission for persistent competitor-database redistribution or unrelated commercial research displays.
- Avoid artwork, screenshots, stored promotional text and app reviews. Minimal factual app ID, country, title and canonical App Store link still need a concrete, reviewed legal-use decision for this product context; a public endpoint is not a blanket commercial redistribution license.
- Official result relevance or ordering is *not* verified downloads/revenue; regional stores can show different catalogs and missing results cannot be treated as zero market interest.

## Mandatory proof-gate decision

No code, API requests, tests, external credentials, new scheduled service, or third-party dependency were introduced for A09. **No source observation, license pass, v1 comparator or usefulness uplift was measured.**

A09 fails the **lawful genuinely free reuse/fit** gate pending clear rights for the exact non-promotional competitor-research use case. Therefore **LICENSE-BLOCKED**, not ACCEPT. Do not ship a dormant Apple adapter in the meantime. If a rights-reviewed factual-ID-only use case is approved, restart with a narrow two-storefront original-API test, source dates and IDs, explicit missingness, controlled caching, real v1 comparative tasks, and all pass-or-discard gates. Otherwise **DISCARD**.

**Rollback:** no code or production state exists to revert; removing this decision note alone would not authorize A09 implementation.

## 2026-11-21 15:14 UTC — original Apple API metadata-only observation (source-compatibility PASS, rights BLOCKED)

**Why a live source check is now possible:** Apple explicitly documents `media=software`, `entity=software`, `country` and `limit` for bounded Search API queries, alongside ID-based `/lookup`. A single operator-triggered, test-only run used **four free requests** (two 3-item searches and two exact-ID lookups), all on fixed `itunes.apple.com` HTTPS endpoints, without API keys, assets, payments, cache retention or automated retries. Four manual calls are below Apple's published approximate 20/minute threshold; **they were not routed through the proposed v1 per-source budget/cache**, so any future production collector would still need that integration and review. Each response was bounded to 75 KB and parsed to a minimal set of factual IDs, short names, and canonical-link hosts, with no raw response or artwork retained.

| Requested storefront | Exact bounded search | Observed HTTP | Result count | Factual track IDs (provider ordering, *not a popularity rank*) |
| --- | --- | --- | ---: | --- |
| US | `term=Signal Private Messenger&media=software&entity=software&limit=3` | 200 | 3 | `874139669, 549493839, 310633997` |
| SI | Same term and parameters, separate `country=si` | 200 | 3 | `874139669, 310633997, 447188370` |

The first result in both storefront searches identifies **Signal - Private Messenger**, Apple track ID `874139669`. A separately bounded `/lookup?id=874139669&country=us&entity=software` returned HTTP 200 and one matching app record; the corresponding `country=si` lookup also returned HTTP 200 and one matching record. Both result canonical link hosts were `apps.apple.com`. The lookup envelope did not expose an independent country field, so the **requested** country is known from the URL; do not infer a provider-confirmed address/region field. Original source-response SHA-256 identifiers for audit: US search `83b072c17a75437a028ea9a75ac8b5a79843c3c1fe235ef92031b5c137ea6f98`; SI search `83d5ecfc16593b0908cb8acbe45f79589ec98f2e9505afe91703742e8adc812a`; US lookup `f6c5c907afbc991c2095b7bba12d58fd4d01372a4d96b60fc354f3daa4ff6039`; SI lookup `5b40efba02989a836c4ea5a7888ee36cee626b977572c0277af069d61cb65311`. Hashes are evidence of the original observed bytes, not a persisted replay fixture.

**Distinct observational value:** country-specific search results differed even for the same typed term, and ID lookup can test whether a specific App Store ID is returned for both requested storefronts. V1's 25-source catalog has no Apple app source. This is a small **catalog availability** demonstration, not evidence of downloads, revenue, competitive share, customer intent or independent rank methodology. The term may match unrelated apps; no unreviewed fuzzy name joins are authorized.

**Lawful use remains unresolved:** Apple's [published Search API terms](https://performance-partners.apple.com/search-api) describe promotional-content restrictions and promotional-placement requirements, but they do not clearly grant unrestricted **persistent, commercial competitor research redistribution** of fetched app metadata. No artwork, previews, screenshots, app reviews or third-party marketing text was collected. A bare search result is not permission to republish a new app-market database. Pending a use-case-specific commercial legal-rights decision, **A09 stays LICENSE-BLOCKED** and **no adapter, scheduler, MCP tool, storage or rollout** is authorized. If review does not resolve those rights, **DISCARD**. The earlier no-requests statement describes the initial checkpoint only and is superseded by these four bounded experimental calls.
