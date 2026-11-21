# MJAU v3 A09 — Apple App Store competitor catalog pilot: license gate

**Decision: LICENSE-BLOCKED / no implementation / no accepted capability.**
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
