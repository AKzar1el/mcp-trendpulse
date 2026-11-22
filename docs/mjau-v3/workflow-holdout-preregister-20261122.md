# MJAU v3 independent-of-adapter workflow evaluation — preregistration (2026-11-22)

This frozen test plan is recorded **before** the new source requests. It uses real original-provider responses as an **external source of ground truth**, and scores with a scorer that does not import the A04/A10 parser functions. It is *independent of the adapter logic*, **NOT an independent human reviewer**. A separate human assessor is still required to sign off actual end-user productivity and attribution suitability. No user/person-identifying data is collected.

## Source tasks (preselected before observing results)

**Wikidata:** four bounded official `wbgetentities` HTTP requests, never more than three QIDs per request, six supported languages maximum. Evaluate candidate lookup decisions and recorded source identity for:

1. `Q90/Q60/Q64` in `en,de,sl`; exact English candidate tasks: `Paris`, `New York City`, `Berlin`, `An invented place name not in Wikidata`.
2. `Q89/Q312/Q30` in `en,sl`; tasks: `apple` (fruit), `Apple Inc.` (company), `United States` (country), `Some non-existent organization`.
3. `Q308/Q1150/Q42` in `en,de,sl`; tasks: `Mercury` (two possible items), `Merkur` in German (two possible items), `Douglas Adams` (unknown if original Q42 localized label absent), `Fictional QID name`.
4. `Q9999999999/Q89` in `en`; tasks: `apple`, `One missing source entity name`.

**OSV:** exactly eight official **one-item** `POST https://api.osv.dev/v1/querybatch` requests, matching version and ecosystem, with only ID/`modified` records:

1. PyPI Django 2.2.0; 2. PyPI requests 2.31.0; 3. PyPI Jinja2 2.10.1; 4. PyPI six 1.16.0;
5. npm lodash 4.17.11; 6. npm minimist 0.0.8; 7. npm react 18.2.0; 8. npm express 4.16.0.

**Control:** exact merged v1 `intelligence_core.plan_source()` on `wikidata_action_api` and `osv_public_api` — these are not v1 sources. No fake v1 source aliases or invented performance measurements.

## Data collection and frozen scoring protocol

- A separate **data-only score path** reads minimal original-provider source responses (Wikidata CC0 QID/label/alias, OSV ID+modified) rather than importing v3 parsers to create gold references. Provider JSON is decoded independently with bounded byte limits. Avoid persistence of raw full advisories: only OSV's official ID-only responses are held.
- Compare each v3 tool response against the independently extracted original source identity, status and subset consistency. Exact source ID and language; no invented QID when the source omitted an item, no false entity auto-confirmation, no false security verdict for an empty OSV result, no arbitrary names or credential-like text leaking, no raw OSV content redistribution.
- Report *opportunity to answer*, not venture-market value: coverage count for source-specific questions where v1 cannot query those official sources, correct matches when the provider source contains an exact label, abstention/ambiguity on underdetermined questions, OSV exact ID overlap/count and source completeness, bytes and per-request time. No exploitation/patch recommendation based solely on OSV.
- Predeclared quality gate: **0 false confirmed identities, 0 false 'secure package' claims, 0 false OSV advisory IDs, 0 unreported incomplete source inputs, 0 budget-bypass requests, 0 unreviewed raw advisory body reuse**. If original source is unavailable, exceeded 192,000 source bytes, timed out, rate-limited or was malformed, report `unavailable` and do not score the case as a clean negative.
- **Budget:** 4 Wikidata calls under fixed 8 UTC/day cap, 8 OSV calls under fixed 10 UTC/day cap. One call per unique query, 8-second timeout, no redirects, retries, added paging or hidden fetches, public origins only; isolate the SQLite budget store inside a disposable test workspace; no changes to the user's configured production budget/cache or worker state.
- **Reference risk:** This is one engineer and an automated independent extraction/scoring path. Because source values are compared with the same original providers the features consume, this demonstrates *technical factual fidelity*, not an unbiased user-benefit panel or external source reliability. A human independent of implementation should assess usability, attribution presentation, usefulness and ranking before release.

**Decision rule:** only retain new official data-source tools if factual-match and conservative-abstention measures pass; retain OSV as provisional factual metadata only until original source rights/attribution review. Any failure is recorded before repair. Keep PR #382 draft and no live registration or publication.
