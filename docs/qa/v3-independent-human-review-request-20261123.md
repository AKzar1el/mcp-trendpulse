# V3 independent end-user review packet (PENDING, not a release approval)

**Repository:** AKzar1el/mcp-trendpulse. **Date prepared:** 2026-11-23.
**Status:** **UNSIGNED. NO independent human approval is claimed.** The authoring assistant and the tool developer cannot sign as an independent reviewer.

## What is being reviewed

Only two explicit optional read-only local source tools: MJAU V3 Wikidata names for 1-3 known QIDs and MJAU V3 OSV exact npm/PyPI package/version advisory IDs. They are available within the checkout-only combined 35-tool MCP; they are not in the public distributed 0.3.1 wheel or live hosted connector. No credentials are needed. The previous original-source automated matrix and 9-case source oracle were conducted by an assistant, **not by a human**.

**Reviewer needs to be someone other than the implementer** who has not received the scoring key or previous expected outcome list before selecting tasks. The reviewer should choose **at least six fresh public, non-sensitive tasks unknown to the implementer**: three Wikidata identity/name cases, three exact package/version advisory cases, including deliberately ambiguous and no-indexed-result possibilities, plus one unfamiliar end-to-end research task of their own choosing when possible. Do not request secret package lists or paid/private data.

## Fair paired task protocol (record before looking at outputs)

1. Independently select and freeze a task, required geography/language and timeframe, QIDs or exact package/version, and expected decision. Record a timestamp and links to official original data policies before use.
2. Randomly assign first interface for each task: **A = direct original API** or **B = source-only unified TrendPulse MCP**. Alternate order across tasks. Do not present the interface labels as proof that either one is correct.
3. Start a stopwatch before each condition. Include any cold-start time only once per *new* session; separately record tool-call time and answer reading/validation time. Reuse a persistent MCP session for repeated tasks so the comparison isn't dominated by deliberate restarts.
4. For direct API, use only the public original Wikidata Action API or OSV /v1/querybatch and document the URL/query. For TrendPulse, use the local checkout-only V3 MCP with execute=True under its original daily budgets (8 Wikidata, 10 OSV), zero retries and only public queries. Never bypass provider throttles or cache budgets.
5. Do not count an answer correct just because it is returned quickly. Verify **exact QID/label/alias**, or **all per-response OSV IDs for that exact ecosystem/package/version** against original data. Note source time and any partial/unknown results, including missing language fields, truncated aliases and paging.
6. For each task, record: answered correctly / appropriately abstained / incorrect / not observed; seconds to first response; seconds to source-verified decision; number of queries and manual steps; clarity of source attribution; and whether any misleading assertion of confirmed corporate identity, safe package, vendor demand or license approval occurred.
7. Review only minimal factual advisory ID, modified date, OSV URL and rights notice; do not redistribute full advisory bodies. Check Wikidata CC0 source URL and OSV's heterogeneous license index/CC BY attribution with links. **Prefix-only GHSA/PYSEC hints are not legally authoritative provenance.** Mark legal conclusions separately for a rights specialist.
8. Record the reviewer’s own unfamiliar workflow without having read the team's expected answer; provide your original-source citation and explanation of what is useful/unusable.
9. Sign the completed form below and link to the evidence. You may **fail or request changes**; a green engineering CI does not override a human rejection.

## Mandatory negative and uncertainty probes

- Can an ambiguous name or truncated alias result be mistaken for an identity confirmation?
- Does one absent requested Wikidata language/QID result produce unknown, never invented entity name or false nonexistence?
- Does an OSV zero-result response mean *no returned advisory in that snapshot*, **not** secure code?
- If OSV is incomplete, paginated, rate-limited or source-unavailable, can the tool say so without false zero?
- Are the original source URLs, attribution, licensing and commercial-redistribution warnings prominent and understandable?
- Does an invalid input or a transient provider outage leave other V1/V2 and V3 tools working?
- Does the source-only local startup stay bound to stdio or guarded loopback; can it be shut down without affecting the 33-tool service?

## Signoff template (leave unsigned until a real independent reviewer does the work)

**Reviewer GitHub identity:** [UNASSIGNED]

**Independent of implementing contributors?** [UNVERIFIED]

**Date and methodology:** [PENDING]

**Public original-source case links:** [PENDING]

**Tasks attempted / source-verified correct / appropriate abstentions / failures:** [PENDING]

**Time-to-verified-answer results by arm with cold/warm timing:** [PENDING]

**Original source rights and attribution observations (not legal advice):** [PENDING]

**Safety false positives or misleading output observed:** [PENDING]

**Unfamiliar task chosen by reviewer, outcome and usefulness score:** [PENDING]

**Decision:** [PENDING — Approve for narrowly defined supervised local use / Request fixes / Reject]

**Signed by and date:** [PENDING]

A participant’s signature supports only the reviewed **scope**, not blanket public/commercial redistribution of mixed-license original OSV records. Separate appropriate rights-owner/legal approval is required for any commercial bulk publication. **Do not activate new public tools, release packages or silently replace existing live MCP sources from this packet alone.**

## Existing material to consult **after** initial task selection

- Original combined 35-tool technical acceptance: docs/qa/trendpulse-unified-v123-acceptance-20261123.md
- Existing older engineering review packet: docs/mjau-v3/independent-review-packet-20261122.md
- Current source policy: https://www.wikidata.org/wiki/Wikidata:Licensing ; https://www.mediawiki.org/wiki/Wikimedia_APIs/Access_policy ; https://google.github.io/osv.dev/data/
- Prior automatic 9-task oracle: docs/qa/v3-release-gate-and-real-source-benchmark-20261123.md

**Do not mistake this prepared form for completed independent review.**
