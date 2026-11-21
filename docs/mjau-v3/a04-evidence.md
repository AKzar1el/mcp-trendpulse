# MJAU v3 A04 — Wikidata identity pilot (isolated)

**Decision: BLOCKED — live API and temporary v1-cache replay proved; independent utility/ambiguity review incomplete. Do not integrate or release.**

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

## 2026-11-21 live-source and Windows cache-replay follow-up

**Exact code under test:** `96ee759e422076b33cf3e0bfc814011f63ea499d`; independent Windows managed worktree, Python 3.13.5. Original A04 suite: 45/45 passed; GitHub CI matrix for that commit passed. The original "no live request" paragraph above describes the initial pilot, not this follow-up.

- **One authorized live Action API GET** from `plan_qid_lookup(["Q89","Q312"],["en","de","fr","es","sl","it"])`, fixed `https://www.wikidata.org/w/api.php` origin, User-Agent with repository contact, no redirects, 8 s timeout, 192,000-byte maximum, HTTP **200**, 1,666 bytes, observed **2026-11-21T05:07:43Z**, SHA-256 `7e2c2bf65104d1029330d0a752be5a54aa69085b10b13332eeef132d4202ac10`. Parsing yielded Q89 and Q312 as distinct source items; Q89 has labels in 6/6 requested languages, Q312 4/6, with absent languages preserved as unknown. The name "Apple" matched Q89 within **these two QIDs only**; it does **not** establish correct worldwide name disambiguation.
- Repeated an exact request through an **isolated temporary instance of the existing v1 `BudgetCache` class**, with a projected-only cached result: one live fetch, second lookup hit the cache with a network transport that intentionally raises if invoked, and an additional daily reservation raised `DailyBudgetExceeded` at cap 1. **60 cached reads:** p50 **3.508 ms**, p95 **5.545 ms** on this Windows machine. No provider fees or persistent runtime changes. After explicit `gc.collect()`, the isolated SQLite directory was removed. An initial run had a Windows temporary SQLite file lock at teardown despite successful replay; the rerun resolved it without changing shared v1 code.
- Actual **v1 source-planning comparator**: `plan_source("wikidata_action_api")` raises `IntelligenceError: Unknown source ID`. The A04 prototype produces verified QID-scoped identity/labels for this source-backed two-entity task, but the baseline is a capability-coverage comparison, **not** blind precision or business utility uplift. The separate A04 parser and source cache are still not installed into shared `collect` or MCP registration.

**Gate update:** official-source compatibility, bounded fetch, v1-cache reuse and zero-network replay **PASSED**. **A04 remains BLOCKED** for acceptance: independently adjudicated multilingual *ambiguous-name* task set (including at least six languages), security/source licensing review, meaningful real workflow lift and independent integration review are not yet complete. Neither v1 nor v2 changed. Rollback remains this isolated A04 feature branch only.

## Six-language real ambiguity replay (later on 2026-11-21)

The earlier Apple/Q312 snapshot did not demonstrate same-name ambiguity for the requested languages. To test **actual ambiguity**, a bounded official Wikidata Action API lookup of **Q308 (planet Mercury) and Q1150 (Roman deity Mercury)** was performed. Source result: HTTP 200, **2,211 bytes**, SHA-256 `749f037eb5dd47678341f57164b9ac59c9afc43eed073fd35375dd61439b0aad`, with the raw **CC0 structured-data** response preserved at `tests/fixtures/mjau_v3/wikidata_mercury_planet_god_six_languages_20261121.json`.

**Observed source outcome:** `candidates_for_name` correctly returns **both `Q1150` and `Q308`** with `status=ambiguous` and `identity_confirmed=false` in all **six** supported languages: English (Mercury), German (Merkur), French (Mercure), Spanish (Mercurio), Slovenian (Merkur), Italian (Mercurio). In German, the Roman god's label differs, but the official source lists the overlapping name as an alias; the test uses source labels and aliases without inventing any name. As a negative case, a tampered source QID fails closed; offline replay forbids any network access.

The intermediate **Q308/Q925** (planet versus chemical element) query independently demonstrated four languages with ambiguous labels; the Q308/Q1150 pairing completes all six. A preliminary lookup at wrong Q1762 was rejected as unsuitable after source inspection. No data from that discarded pairing was committed. No new parser behavior or shared code was required.

**New targeted regression suite:** `PYTHONPATH=src python -m pytest -q tests/test_mjau_v3_wikidata.py tests/test_mjau_v3_wikidata_snapshot.py`: **58/58 passed** on Python 3.13.5 Windows. Ruff and compileall clean. This proves source-backed candidate abstention in all six language scopes, not authoritative entity disambiguation for all possible names or locales.

**Decision remains BLOCKED**, despite clearing real six-language ambiguity and v1 capability-coverage tests. The source scope comprises only two reviewed objects in each fold; an independently adjudicated broader user-workflow comparison, release rights/attribution review, and separate official MCP conformance remain unproven. No integration, merge or worker changes authorized.
