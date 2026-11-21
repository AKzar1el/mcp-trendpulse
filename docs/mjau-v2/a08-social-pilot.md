# MJAU v2 A08 — bounded social-source feasibility

**Status on 2026-11-21: PARTIALLY FEASIBLE; NOT ACCEPTED AND NO ADAPTER IMPLEMENTED.**

**Scope:** Free public Mastodon trends, keyless Bluesky AppView search. Separate documentation-only branch from pinned original MJAU v1 staging commit `b88b0a974b5dcdb480e4fd8c4da5f7bbca68e98e`; no v1/v3/production source change, browser firehose, data archive, authorization bypass or scheduled polling.

## Official permitted sources

- Mastodon public trends API: https://docs.joinmastodon.org/methods/trends/ . `GET /api/v1/trends/tags` on a **specific instance**, returning tags and local weekly use/account histories. Its ranking is instance/provider-specific and changes on recalculation; not a complete Mastodon federation or global market trend.
- Bluesky official HTTP API: https://endpoints.bsky.app/ . Most public GETs are documented as keyless on public AppView, but searchPosts is not guaranteed available to this unauthenticated client. Previous independent reports note public-search 403: https://github.com/bluesky-social/bsky-docs/issues/332 .

## One-shot real-source results

Two distinct sources, **one keyless bounded GET per source**, no retry or service-account token:

| Source | Tested request | Observed | Appropriate interpretation |
| --- | --- | --- | --- |
| Mastodon | `https://mastodon.social/api/v1/trends/tags?limit=3` | **HTTP 200**, JSON ~1353 bytes, **3** public trending tags, first tag `FensterFreitag`, **7** reported day-history rows | Supports local-to-`mastodon.social` current/tag-week evidence only. Does not measure every Mastodon server or buyers |
| Bluesky | `https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?q=open%20source&limit=2&sort=latest` | **HTTP 403 Forbidden** | BLOCKED for this unauthenticated endpoint. Never classify as no social activity; do not retry/switch identity/host to evade provider policy |

Only source metadata sizes/names/statuses were examined. No public user profiles, post bodies, images, followers, private content, accounts or firehose were copied to this repository.

## Mandatory proof-or-discard decision

**A08 combined social pilot: BLOCKED FOR ACCEPTANCE.** Mastodon alone is technically reachable but its additive decision usefulness over existing MJAU HN/community sources remains **NOT PROVEN**. Bluesky anonymous post search is provider-blocked. Do not create a half-working endpoint simply to increase tool count.

To reconsider, demand an independent, legal, free first-party access path and exact terms, a real end-to-end bounded adapter test (not a source HTTP ping), deterministic failure and privacy tests, instance attribution, cache/cooldown, and a recorded improvement in 5 representative opportunity decisions compared with v1. Without meaningful source coverage and measured value, **DISCARD A08** and keep this evidence ledger only.

**No automatic retry, proxy workaround, paid token, integration PR, release, v1/v3 file edit, or production task was performed.**
