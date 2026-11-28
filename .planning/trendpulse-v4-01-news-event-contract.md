# V4.01 — News and Event Intelligence: baseline and shared contract

**Decision:** V4.01 design and inventory completed 2026-11-28; implementation of adapters and runtime schema is not part of this design checkpoint.  
**Roadmap:** [TrendPulse V4–V8](trendpulse-intelligence-v4-v8.md).  
**Inspected source:** protected `main` at `744fa81ff0376ce9bd9d8e6d726dcf924d53ea24`. All code links below are pinned to that revision.  
**Scope:** public source/PR inventory and schema/migration decision; no local runtime inspection, network provider smoke, source-code modifications, release or scheduling. The dedicated TrendPulse Codexify tunnel reported disconnected; local/uncommitted changes are unknown.

## 1. Existing source inventory and reuse decisions

| Existing component (pinned code) | Observed contract and gap | V4 decision |
| --- | --- | --- |
| [news.py L1197–1353](https://github.com/AKzar1el/mcp-trendpulse/blob/744fa81ff0376ce9bd9d8e6d726dcf924d53ea24/src/mcp_trendpulse/news.py#L1197-L1353) | Google RSS rows contain title, Google link, feed date, publisher label and RSS-only marker. Extracted article path returns newspaper.Article, skips failed items, may restore feed title/publisher or assign feed publication date. Exact RSS URL dedup exists. | Reuse ingestion, not the lossy output as an event truth source. New mapping retains date provenance and failed extraction as explicit metadata without changing current list behavior. |
| [server.py L21–82, L209–220](https://github.com/AKzar1el/mcp-trendpulse/blob/744fa81ff0376ce9bd9d8e6d726dcf924d53ea24/src/mcp_trendpulse/server.py#L21-L82) | ArticleOut omits unset/null fields, includes publisher/body/summary/canonical fields when available; TrendingTermArticleOut is a distinct contextual snippet. Output selects minimal/full fields. | Preserve existing MCP input/output and serializer; do not make missing text a new breaking error. |
| [news.py L1586–1650](https://github.com/AKzar1el/mcp-trendpulse/blob/744fa81ff0376ce9bd9d8e6d726dcf924d53ea24/src/mcp_trendpulse/news.py#L1586-L1650) | Legacy JSON export includes original_url as url, canonical_link, source_url, meta_lang, text/summary and other article properties; different from minimal MCP output. | Keep export unchanged; explicitly map with provenance, never copy body/metadata wholesale into shared evidence storage. |
| [providers.py L14–101, L185–345](https://github.com/AKzar1el/mcp-trendpulse/blob/744fa81ff0376ce9bd9d8e6d726dcf924d53ea24/src/mcp_trendpulse/providers.py#L14-L101) | NewsProvider protocol and CommunityNewsProvider distinguish RSS dicts from newspaper.Article. ProviderSet already separates news/trends. | Add an internal adapter/normalization boundary; no duplicate existing provider and no incompatible expansion of mandatory protocol methods. |
| [hosted.py L186–209, L432–449](https://github.com/AKzar1el/mcp-trendpulse/blob/744fa81ff0376ce9bd9d8e6d726dcf924d53ea24/src/mcp_trendpulse/hosted.py#L186-L209) | ContextArticle is explicitly Google News RSS headline metadata with source, URL, optional publication date and fixed link_type; not a body. | Keep six hosted tools and existing link type semantics. New model is not an automatic replacement. |
| [intelligence_rss.py L90–112](https://github.com/AKzar1el/mcp-trendpulse/blob/744fa81ff0376ce9bd9d8e6d726dcf924d53ea24/src/mcp_trendpulse/intelligence_rss.py#L90-L112) | Related news snippets include title, URL and source label only; bounded count. | Map as headline/context evidence with unknown publication date and publisher identity; trend association is not proof of an event. |
| [rss_review.py](https://github.com/AKzar1el/mcp-trendpulse/blob/744fa81ff0376ce9bd9d8e6d726dcf924d53ea24/src/mcp_trendpulse/rss_review.py), [rss_compare.py](https://github.com/AKzar1el/mcp-trendpulse/blob/744fa81ff0376ce9bd9d8e6d726dcf924d53ea24/src/mcp_trendpulse/rss_compare.py), [rss_url_validation.py](https://github.com/AKzar1el/mcp-trendpulse/blob/744fa81ff0376ce9bd9d8e6d726dcf924d53ea24/src/mcp_trendpulse/rss_url_validation.py) | Existing bounded schema-v1 headline audits, exact URL membership diff and strict Google RSS URL shape. | Reuse validation where compatible; retain exact comparison semantics and never infer deletion from feed expiry. |
| [intelligence_foundation.py L12–54](https://github.com/AKzar1el/mcp-trendpulse/blob/744fa81ff0376ce9bd9d8e6d726dcf924d53ea24/src/mcp_trendpulse/intelligence_foundation.py#L12-L54), [intelligence_evidence.py L71–86](https://github.com/AKzar1el/mcp-trendpulse/blob/744fa81ff0376ce9bd9d8e6d726dcf924d53ea24/src/mcp_trendpulse/intelligence_evidence.py#L71-L86) | gdelt_latest reads lastupdate.txt and returns bounded batch filename/byte metadata, not topical articles; notes DOC 429 behavior. | Keep existing source ID and contract. DOC article/timeline access is a separate mode/adapter within the GDELT family, subject to V4.02 live access/rights gate. |
| [intelligence_core.py L56–110, L315–473](https://github.com/AKzar1el/mcp-trendpulse/blob/744fa81ff0376ce9bd9d8e6d726dcf924d53ea24/src/mcp_trendpulse/intelligence_core.py#L315-L473) | Plan, allowlisted origin, explicit fetch, bounded 256 KiB, per-source budget, request locks, cache and cooldown. Success envelope contains retrieved_at and bounded provider projection. | Reuse core safeguards. For news providers, enforce rights-aware minimal projection **before** any persistence; don't automatically cache raw article bodies or third-party metadata just because current generic cache permits them. |
| [intelligence_signal.py L125–259](https://github.com/AKzar1el/mcp-trendpulse/blob/744fa81ff0376ce9bd9d8e6d726dcf924d53ea24/src/mcp_trendpulse/intelligence_signal.py#L125-L259), [intelligence_research.py](https://github.com/AKzar1el/mcp-trendpulse/blob/744fa81ff0376ce9bd9d8e6d726dcf924d53ea24/src/mcp_trendpulse/intelligence_research.py) | Pydantic v2 frozen strict-extra typed signal, source/method/coverage/metric semantics, unknown vs zero, news_mention_count is attention not demand. | Keep TrendSignal unchanged. Article/Event observations are not numeric signals. Later explicitly aggregate comparable coverage into the existing contract only when source/window/counting method is documented. |
| [news.py L633–967, L1871–1890](https://github.com/AKzar1el/mcp-trendpulse/blob/744fa81ff0376ce9bd9d8e6d726dcf924d53ea24/src/mcp_trendpulse/news.py#L633-L967) | Existing article target validation, pinned HTTP, response/deadline limits, browser fallback disabled. Legacy date parser assumes UTC for timezone-naive input. | Reuse hardened fetcher; citation URL validation is not fetch permission. Record date provenance/precision at adapter boundary; never silently treat a timezone assumption as publisher-confirmed. |

**Concurrent work checked:** open PRs #448 (source diagnostics), #446 (research integration including provider core/foundation/evidence/observations and CLI), #437 (keyword whitespace), #436 (CLI escape), #425 (Federal Register). No edits to their files in V4.01. Recheck exact current main and open PR diffs before V4.02. #426 independent human review and #427 rights remain open; #428 cold-start issue is closed (closure alone is not a new performance result). Do not switch the other bound workspace.

## 2. Selected architecture (smallest additive design)

Use existing Pydantic v2 dependency, with frozen, versioned, bounded models and explicit validators, in one future internal module (proposed `news_intelligence_schema.py`). No new dependency, database, MCP tool, scheduler, fetcher or public response change needed for the contract. Keep source payloads outside the models. The field tables below are the implementation specification, not claims that a runtime module exists.

```text
Existing providers / saved imports
  -> explicit source-specific normalizer (no I/O)
  -> bounded NewsBatch + NewsArticle observation(s)
  -> later V4.04 duplicate relations, V4.05 Event candidates
  -> V5 claim/evidence graph (separate)
  -> V6 comparable aggregates -> existing TrendSignal
```

Two entities, not an article/event one-to-one relationship. An article can report more than one event; an event can be described by multiple articles. A discovered link is not an independently verified article; a cluster is not proof an event happened.

### Shared time evidence

Use a small tagged value: `value` (ISO date or explicit-offset ISO timestamp, otherwise null), `precision` (day/minute/second/unknown), `basis` (publisher/feed/provider_seen/local_capture/legacy_normalized/unknown). A date-only value is never promoted to midnight UTC. Timestamp inputs need a real offset; normalize to UTC for comparison while preserving original precision. Use precision matching the original value; if provenance cannot establish a timezone, retain unknown or date-only only if independently justified. Do not infer event time from publication time. Source clock conflicts are warnings/unresolved, not repaired by inventing dates.

### NewsArticle v1 (one source observation, not an entity merge)

| Field | Type / rule |
| --- | --- |
| schema_version | Literal 1. Reject unsupported versions and unknown fields at the typed boundary. |
| article_id | Stable lowercase SHA-256 hex of canonical JSON array [schema identity version, discovery_provider, reported_url]; exact source-level key, not a global claim of same article. |
| observation_id | SHA-256 of version, article_id and normalized material observation fields including source timestamps, capture time and content hash; exclude cache-hit flag and derived presentation text. Same cached observation replays same ID. |
| discovery_provider | Bounded registered source ID (snake_case; max 60). Google News RSS, trend-related news and GDELT DOC are distinguishable; provider not publisher. |
| source_record_id | Optional bounded source ID (120); no secrets or personal identifiers; do not merge solely on it. |
| reported_url | Required safe original discovery result URL (max 8192; Google's RSS token may exceed TrendSignal's 600-char citation limit). |
| discovery_url | Optional safe citation of source endpoint/feed, not raw query with credentials. |
| link_type | google_news_rss / publisher_candidate / other_aggregator. Source-shaped Google RSS links use existing strict validator. Never label a publisher candidate as verified identity. |
| resolved_url | Optional safe final URL from actual pinned retrieval; not guessed from canonical HTML or search snippets. |
| canonical_url | Optional safe publisher-declared canonical candidate; no automatic fetching or equivalence. |
| title | Nonempty bounded printable text, max 512 Unicode chars after explicit control sanitization/rejection; preserve accents and original language; never translate silently. |
| publisher_label | Nullable bounded label (160); provider-reported or publisher-extracted, not verified owner. |
| publisher_basis | feed / provider / publisher_page / unknown. Unknown remains null/unknown. |
| source_country | Nullable ISO alpha-2 when explicitly mapped from provider source-country data; not event location, audience or queried market. |
| query_geo | Nullable bounded original query scope (e.g. US, SI, US-CA); not source or event geography. |
| language | Nullable BCP47 subset consistent with TrendSignal for source-attested original language; unknown if provider language label cannot be confidently mapped. |
| published_at, modified_at | Nullable shared time evidence; keep conflicting source dates as separate observations/warnings, not overwritten as fact. |
| provider_seen_at | Nullable shared time evidence; GDELT seendate is provider observation, not publisher date unless independently supported. |
| captured_at | UTC timestamp of actual collection; required for new live observations; null only for imported legacy data lacking trustworthy capture time. Never replace with replay time. |
| first_seen_at | Nullable earliest observed locally for the exact source record, populated only once supported by tracked local history; not claimed original publication/first reporting. |
| capture_mode | live / legacy_import. Cached replay uses original capture mode and capture time. |
| content_level | headline_only / extracted_text. Extracted means actual accepted publisher extraction, not a headline, snippet or generated summary; still not proof of truth. |
| extraction_status | not_attempted / ok / blocked / unavailable / invalid / unsupported / no_content / unknown. ok requires extraction evidence; headline-only can retain failed attempts. |
| body_sha256 | Nullable SHA-256 of accepted extracted text (UTF-8 exact extracted text, no semantic normalization); no hash invented from summary/headline. For new extraction require hash when retention policy permits; legacy unknown explicitly allowed. |
| retention_scope | metadata_only / permitted_ephemeral_text / restricted. Default metadata_only; never infer redistribution rights from access. No full text/body, image, arbitrary HTML, embedded instructions or unrestricted metadata stored by default. |
| warnings | Up to 12 controlled warning codes; no raw exception bodies or unbounded source payload. |

URL checks: HTTPS references by default; preserve a legitimate HTTP reported link only as a **non-fetching** explicitly marked legacy reference if policy approves; otherwise reject and count the record, never silently upgrade HTTP to HTTPS. Reject private/non-global addresses, numeric IP disguises, credentials, control characters, unsafe scheme/port, secret-bearing URLs and fragments; reuse existing citation and RSS validators rather than duplicating checks (resolve their length/shape differences in tests). Preserve exact reported URL identity; do not strip arbitrary query parameters, normalize case-sensitive paths or accept publisher canonical links as equality. V4.04 handles explicit aliases. Network retrieval still requires existing connection-level SSRF protections and approved origin; data validation alone does not authorize fetches.

No article is synthesized from a GDELT manifest, an empty row, a provider error or a numeric timeline point. A safely retained discovery headline may remain when publisher extraction fails.

### Event v1 (derived grouping candidate)

| Field | Type / rule |
| --- | --- |
| schema_version | Literal 1. |
| event_id | Stable opaque lowercase SHA-256 of algorithm identity version + initial sorted seed observation IDs; preserved across later revisions; no cross-run persistence guarantee before history exists. |
| revision_id | SHA-256 of canonical event state excluding revision_id, with sorted references; deterministic for same inputs/algorithm. |
| algorithm_version | Bounded explicit version; no hidden clustering parameter changes. |
| label | Bounded human-readable event candidate label (512); derived, never presented as a publisher quote. |
| occurrence_status | unknown / reported / disputed. V4 does not assign a verified truth verdict; V5 provides claim-level support. |
| event_start, event_end | Nullable shared time evidence attributed to supporting observation IDs via time_refs; allow uncertain precision and ongoing events. Validate ordering only for comparable exact times. |
| location_labels | Up to 8 bounded event-location candidates with source observation references, not inferred from publisher/source country or query market. |
| entity_candidates | Up to 16 bounded labels/optional existing source IDs and supporting references; candidate only, no automatic identity resolution. |
| article_refs | 1–100 observation IDs, sorted, unique, each with relation reports / followup / context and bounded controlled rationale; at least one reports/followup member. A context-only link is not corroboration. |
| time_refs | Up to 16 observation IDs explaining start/end candidates, empty if time unknown. |
| first_observed_at | Nullable earliest tracked local capture of the supporting observations; not event time or proof of first reporting. |
| as_of | Explicit UTC reference/cutoff for this revision. Reject observations known to have become available after cutoff. |
| warnings | Controlled codes including ambiguous identity, uncertain time, contradictory descriptions, partial coverage, shared-source lineage unknown. |

Event references must resolve within the bounded supplied observation set or an explicitly authorized local snapshot. Do not infer occurrence from a large cluster, article count or publisher diversity. Support future split/merge lineage without rewriting older revisions: preserve old IDs, add explicit successor/parent relationships in a later V4.05 history envelope; no hidden reassignments. Deterministic hash inputs use UTF-8 canonical JSON with sorted object keys, stable array ordering defined above and no NaN/Infinity; hashes identify records, not authenticity.

### NewsBatch v1 (necessary outcome envelope)

A bounded source query result with schema_version, provider_id, query scope/window, captured_at or null, status (planned/observed/partial/empty/unavailable/invalid), cache_hit, source count if actually supplied, accepted/invalid/dropped/truncated counts, sanitized reason codes, observations (max 100, with lower provider-specific caps), coverage notes and permitted source attribution. A successful empty query is explicitly empty **within sampled scope**, not zero real-world events. Unavailable has no fabricated zero counts; partial may retain valid rows. Planned has no observations/no fetch. Old cache data must retain original capture time; expose staleness separately. For normalized timelines, separate raw count, monitored-universe denominator, ratio, interval and source coverage; never create article observations from them.

## 3. Migration and compatibility plan

1. **V4.02**: implement the minimal Pydantic models and pure source adapters alongside existing code (or an equivalent module name selected after rechecking baseline). Map a small fixture of each existing source before adding GDELT DOC. Keep schema validation and fetch boundary separate. Query only explicitly authorized free providers and enforce source budget and rights before caching.
2. Google News RSS: `title -> title`, `url -> reported_url`, `meta_site_name -> publisher_label`, `publish_date -> published_at` with feed basis; preserve RSS content_level. The legacy parser converts naive dates to UTC; when original timezone/precision is unavailable, mark legacy_normalized/warning rather than claiming publisher-confirmed time. No publisher body/canonical URL from RSS.
3. newspaper.Article: map original discovery URL separately from final resolved URL when actually observed. Treat canonical_link as a candidate. Use original feed and article date attribution only when available before fallback restoration. For existing exports without provenance, leave unknown fields null; a supplied body/summary is legacy evidence, not a fresh successful download. Only compute hash from known extracted text, if permitted.
4. Hosted ContextArticle / TrendingTermArticleOut / intelligence_rss: map headline/context only. Related trend association and date precision are separate metadata; never upgrade snippet or summary to extracted body.
5. GDELT DOC article list: map title, URL, language and source-country labels only after real provider contract validation. Preserve provider seendate independently; no direct mapping to publisher publication date. DOC timelines have independent typed aggregate representation, not NewsArticle/Event. Existing gdelt_latest untouched.
6. Do not migrate old RSS audit files in place. Offer explicit versioned offline conversion later; preserve original files and distinguish imported capture-time unknown. Do not make a mandatory new NewsProvider method or change ArticleOut/ContextArticle/TrendSignal serialization, CLI defaults or tool counts. New functionality opt-in/internal until reviewed.
7. V4.03 onward: retain failures and provenance, then implement deduplication, reversible event clusters and report projection. Persist only rights-approved minimal fields. V5 adds claim graph, V6 adds measured news attention only when comparison is valid.

## 4. Concrete mapping examples (synthetic, not live evidence)

| Fixture | Required projection |
| --- | --- |
| Google RSS title + news.google.com/rss/articles/... + dated feed | RSS headline_only; publisher label feed-attributed; resolved_url/canonical_url/body_sha256 null; event time unknown. |
| Extracted publisher article with feed date conflicting with publisher date | Two attributed observations or explicit conflict; actual extraction hash only if permitted; no silently overwritten publisher date. |
| GDELT row with seendate and sourcecountry | provider_seen_at populated; source_country mapped if recognized; published_at and event location unknown. |
| Trending term with related news snippet but no date | headline_only; no fabricated date or event. |
| HTTP 429 / blocked extraction | unavailable batch or retained headline with extraction_status blocked/unavailable; no fake zero or retry loop. |
| Legacy RSS capture imported without collection date | captured_at/first_seen_at null, capture_mode legacy_import; no false freshness. |
| Two outlets reproduce same press release | distinct observations remain separate; no independent corroboration claim, later V4.04 marks lineage candidate. |
| Article covers two separate events | two event candidates may reference same observation; no forced merge. |

## 5. Verification and handoff gates

Design-stage evidence:
- Exact protected-main SHA and relevant source functions inspected; open PR overlap and review issues checked.
- Existing Pydantic dependency and source-specific schemas/validators confirmed; no new dependency needed.
- Architecture and field/mapping decisions recorded, including explicit failure and rights semantics.
- No runtime implementation or live source acceptance performed; no fabricated tests. This completes **only** V4.01's inventory/contract selection, not V4 release acceptance.

Implementation-stage test matrix (required in V4.02–V4.03, not yet run):

| Test | Expected result |
| --- | --- |
| Valid RSS / full article / related snippet / DOC / old import / mixed batch | Correct source-specific mapping, no evidence promotion, round-trip of schema-v1 IDs. |
| Unsupported schema, extra fields, malformed URL, control text, excessive size/count | Deterministic bounded rejection; no network or persistence. |
| Date-only, offset timestamp, naive/legacy date, conflicting dates, future observation cutoff | Preserve original precision, avoid invented timezone/event date; report uncertainty/reject invalid ordering. |
| Cache repeat versus genuinely changed content | Stable observation ID for replay; new revision for actual changed captured evidence; original timestamps unchanged. |
| Unavailable / partial / empty / malformed provider | Explicit statuses and unknown counts; no fake article/events, no quota bypass. |
| Multiple reports/context references, duplicates, unresolved IDs, event/source-country collision | Reject unresolved/invalid references, no automatic identity or independence claims. |
| Existing community/hosted/RSS output snapshots and registry | Unchanged defaults, existing tool counts and semantics. |
| Privacy/rights boundaries, injection, article retrieval | Minimal allowed metadata; no secrets or raw arbitrary payload; existing pinned egress unchanged. |

Existing regression entry points to rerun when code changes: test_news_rss_headlines.py, test_article_json_export.py, test_rss_review.py, test_rss_compare.py, test_rss_url_validation.py, test_article_url_validation.py, test_article_egress_pinning.py, test_google_news_safe_decode.py, test_provider_boundary.py, test_provider_errors.py, test_intelligence_extended_contracts.py, test_intelligence_signal_contract.py, test_intelligence_rss.py, test_mjau_research_report.py, test_hosted_facade.py and registry/entrypoint tests, followed by full offline suite and exact-commit CI. Live source validation only after source terms and access checks.

## 6. External standards (reviewed; no provider calls or permission grants)

- [IPTC NewsCodes guidelines](https://www.iptc.org/std/NewsCodes/guidelines/): event-date confirmation and occurrence-status vocabularies support distinct event time and uncertainty; use as design reference, not a claim of full standards conformance.
- [IPTC NewsML-G2](https://iptc.org/standards/newsml-g2/): separate news-item and event metadata, no one-to-one requirement; no need for XML dependency.
- [GDELT DOC 2.0 API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/), [DOC search-window update](https://blog.gdeltproject.org/doc-2-0-updates-1-5-year-searching-and-updated-mobile-interface/): article lists and normalized/raw coverage timelines are distinct, and time windows/mode limits differ. Historical documentation is not current live access, completeness, rate or rights evidence.

**Next action:** V4.02 — recheck branch/PR ownership and exact source, validate free access and permitted intended use for GDELT DOC and direct feeds, implement the internal schema/adapters with offline tests first, then a bounded live smoke. Stop at a real provider/rights gate; continue independent authorized tests instead of evading limits. No changes to existing production tools, local installation or scheduler.
