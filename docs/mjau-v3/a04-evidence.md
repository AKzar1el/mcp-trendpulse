# MJAU v3 A04 — Wikidata identity pilot (isolated)

**Decision: BLOCKED — keep experimental, do not integrate or release.**

## Baseline and question

Does an exact, publicly sourced Wikidata QID plus multilingual labels prevent a false name merge that v1's language-scoped lexical phrase handling cannot independently disambiguate? The v1 M02 phrase grouping is lexical, not Wikidata-identity based. A04 must establish QID-specific incremental value, not add a redundant name normalization wrapper.

**Pinned staging ancestor:** `b88b0a974b5dcdb480e4fd8c4da5f7bbca68e98e` from draft v1 PR #328. A04 has its own branch and reviewable PR. It does not depend on or modify Stage 0, v2, or shared v1 code.

## What was observed versus simulated

Official Wikidata item pages reviewed on 2026-11-21:
- [Q89](https://www.wikidata.org/wiki/Q89): English label `apple`, fruit.
- [Q312](https://www.wikidata.org/wiki/Q312): English label `Apple Inc.`, technology company.

This confirms the items are **distinct QIDs** and exact labels. It does **not** validate the real Action API response for six languages or the `wbgetentities` parser; a constructed response using these observed labels checks only the local logic. All six-language samples and ambiguous alias collisions in unit tests are marked **synthetic**. They must not be cited as independent live data.

No authenticated account, paid resource, proxy, scraper, SPARQL query, credentials, API invocation, or production connection was used. Wikimedia's official [Data access](https://www.wikidata.org/wiki/Help:Data_access), [API access policy](https://www.mediawiki.org/wiki/Wikimedia_APIs/Access_policy), [2026 rate limits](https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits), and [Wikidata licensing](https://www.wikidata.org/wiki/Wikidata:Licensing) were reviewed. Wikidata structured entity data is CC0. Calls must identify a contactable app User-Agent and respect HTTP 429/503, retry-after, global concurrent request limits, terms, and controlled caching. The plan specifies one bounded read-only API query but never executes it. The existing v1 budgeted collector must own any future transport; this pilot cannot bypass per-source quotas.

## Implemented, test-only

- `plan_qid_lookup([QIDs], [languages])`: fixed-origin official Action API `wbgetentities` request plan; maximum three explicitly supplied QIDs, six supported languages (`en`, `de`, `fr`, `es`, `sl`, `it`), 1 planned call, max 192000 response bytes, 8-second proposed timeout, **zero actual calls**.
- `parse_qid_lookup(payload, ...)`: bounded validated external response projection. Missing/partial/not-authorized source is **unknown**, not zero. No automatic redirects, ID changes, wrong-language aliases or unexpected items.
- `candidates_for_name(...)`: exact NFC/casefold name match only, yields ambiguous/candidate-requires-confirmation/unknown. It **never returns identity_confirmed=true** and does not infer geographic presence, buying demand or corporate status.
- `parse_transport_result(...)`: offline handling of already-received HTTP 401/403/429/503/504/302; no retries, errors not mistaken for zero evidence, no echoed error bodies or credentials.

## Tests, resources and measured benefit

From isolated sandbox Python 3.13.5:

    PYTHONPATH=src python -m pytest -q tests/test_mjau_v3_wikidata.py
    PYTHONPATH=src python -m compileall -q src/mcp_trendpulse/mjau_v3 tests/test_mjau_v3_*.py

**A04: 45 deterministic targeted cases passed; Stage 0+A04: 76 passed.** (All cases must be rerun against the **published** commit and the repository's Python 3.11–3.14 CI/Ruff before considering a proof.)

300-run single-process offline sample with `tracemalloc`, on constructed two-item, six-language fixture: p50 **0.2274 ms**, p95 **0.3362 ms**, peak traced **25793 B**, JSON output **1552 B**. This is a tiny local microbenchmark, not production latency, memory or measured time saved. Requests = 0, API cost = $0.

**Observed utility:** Two official page labels + QIDs show a meaningful *hypothesis*: potential distinction between fruit and company despite similar English names, and six-language exact-identity mapping. However the **full v1 code path has not been run on live matching source records**, multilingual labels are synthetic, and no independent human audit across real samples has been completed. **Measured live uplift: unavailable.** No source acceptance or release claim.

## Decision, missing evidence, rollback

**BLOCKED** because mandatory real official Action API bounded request, zero-network cache replay, six-language source validation, real v1-versus-A04 comparative tasks (including adversarial false-merge cases), full suite and official license/terms regression on the target host are incomplete. The separate TrendPulse Codexify bridge still reports tunnel-client unseen for 300 seconds. No bypass attempted.

Once the connection is healthy, an independently configured reviewer may run **one** planned official source query through an existing approved budgeted collector, store only small evidence metadata in a test-only cache, compare with actual v1 behavior, and decide **ACCEPT or DISCARD**. Do not create public MCP registration, modify shared manifests/CI, or publish until explicitly authorized. Roll back by removing only the A04 module/test/doc commits from this draft branch. No production state changed.
