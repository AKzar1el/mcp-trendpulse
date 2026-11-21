# MJAU v2 A06 — GDELT DOC 2.0 topic timeline feasibility gate

**Decision: BLOCKED (2026-11-21). No implementation and no repeated provider calls.**

**Plan owner:** MJAU v2 discovery track; A06 is selected-for-proof, not a commitment to ship.
**Pinned base:** `b88b0a974b5dcdb480e4fd8c4da5f7bbca68e98e`, original v1 MJAU draft PR #328.
**Work isolation:** documentation only in this branch; no v1/v3 source, schedule, worker, quota or production change.

## Unique possible value

DOC 2.0 offers topic-queryable volume timelines, distinct from MJAU v1's latest raw GDELT feed manifest. A timeline would be **news coverage within GDELT's monitored corpus**, not an absolute global audience, search volume, independent article originals, user intent or business demand. Its article-list horizon and historical timeline horizon differ; normalize only within the same mode and original source.

Official documentation: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/

## Single non-disruptive free source pilot

On November 21, 2026, the Windows machine made **one** keyless, bounded HTTP GET:

`https://api.gdeltproject.org/api/v2/doc/doc?query=open%20source%20security&mode=timelinevol&format=json&timespan=7d`

**Observed:** HTTP 429 Too Many Requests; the provider supplied no successfully validated timeline data. No second request, retry, proxy, different IP, different query, rate-limit workaround or automatic background task was attempted.

A contemporary independent source (<https://gdeltcloud.com/gdelt-api>, updated Nov 13, 2026) also reports multiple 429 responses from the DOC API. This is supporting risk context, not a substitute for our one real source observation.

## Correct failure handling

- `status=provider_rate_limited` / **BLOCKED**, never an empty timeline or proof of zero news.
- **Do not install adapter or advertise a working feature** until a new explicitly authorized narrow live attempt legally passes, its original denominator/units are understood, the source terms/commercial rights reviewed and utility demonstrated against v1.
- V1's raw 15-minute GDELT manifest remains available; it is not equivalent to topic-queryable DOC and should not be relabeled as this feature.
- No scheduler or repeated checks. Never retry a 429 automatically, change identity or pressure shared provider quotas. Owner can reconsider only with new independent availability evidence and an explicit approval.
- If continued unavailability makes a sustainable legal free integration infeasible, mark **REJECTED/DISCARDED** and omit A06 from the product. This blocked record can remain for project knowledge without shipping code.

**No tests can be counted as real-source success** because the only bounded live query returned 429.
