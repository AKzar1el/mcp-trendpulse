# Bounded hunter research controls (2026-11-25)

A practical research session found that the current hunter's five-record,
recency-first samples missed useful niche evidence. This change adds opt-in
depth and provider-native relevance ordering to the existing tool, not a new
crawler or MCP tool. The default remains five requested records per source
and existing recency ordering. The lexical quality screen is unchanged.

Example plan (zero network requests):

```json
{
  "topics": ["embedded software testing"],
  "sources": ["openalex", "github_issues"],
  "lookback_days": 60,
  "sample_limit": 10,
  "relevance_first": true,
  "execute": false
}
```

Use explicit execute=true only for a bounded public-source query. A topic
allows up to 40 requested records; each source requests 1-10. One provider
request per topic/source is unchanged; existing local quotas and caches
still apply. Native relevance ordering applies only to OpenAlex and GitHub
issue searches; the response lists those sources and requested depth.
A returned sample can be smaller than requested. If a provider overreturns
valid records, the hunter limits the sample without rewriting the source
count. Local quota exhaustion is reported separately from generic collection
failure. Historical telemetry distinguishes non-default configurations.

References: OpenAlex's documented relevance sort requires an active search
(https://help.openalex.org/api/sorting/); GitHub issue search defaults to
best match without a sort parameter
(https://docs.github.com/en/rest/search/search).

## Bounded live comparison and provider availability

On 2026-11-25, six keyless OpenAlex requests compared the original five-record
recency-first sample with the opt-in ten-record relevance-first sample:

| Query | Original title matches | Opt-in title matches |
| --- | --- | --- |
| battery recycling | 0/5 | 10/10 |
| browser agent prompt injection | 0/5 | 7/10 |
| embedded software testing | 0/5 | 1/10 |

The last query also returned one separate metadata-label-only context match.
These are lexical sample counts, not a blinded precision/recall or decision-quality
benchmark. Provider-assigned labels do not establish current market activity.

The existing CORDIS endpoint returned an authentication redirect; its official
SPARQL page notes maintenance affecting federated queries. Do not follow login
redirects or infer that the endpoint is repaired from the maintenance notice.
The Publications Office CELLAR endpoint remains documented and timed out on
bounded 12.7-second and 26.0-second live observations. No matching official
maintenance notice was established. USAspending returned two records and a
successful cache replay. Keep the strict live coverage gate separate from local
regression success; unavailable providers must not become empty evidence or
fabricated successful responses. Do not retry automatically.

## Adaptive research and sessions

The existing `intelligence_hunt_current` tool accepts optional `adaptive_passes`
(1-3), `request_budget` (up to 15 request slots), up to two `alternate_queries`,
up to five `exclude_terms`, and an opaque `session_id`. Adaptive research accepts
one explicit topic. Example zero-request plan:

```json
{
  "topics": ["browser agent prompt injection"],
  "sources": ["openalex", "github_issues"],
  "adaptive_passes": 2,
  "request_budget": 4,
  "alternate_queries": ["agent injection defense"],
  "session_id": "research-20261125-01",
  "execute": false
}
```

With explicit execution, subsequent passes target only weakly covered healthy
sources, use distinct strategies, and stop on insufficient new preview evidence
or the configured limits. Request slots include cache hits and unavailable
calls; existing provider quotas still apply. Exclusions filter the evidence
preview, not provider-level coverage metrics. Duplicate identities and conflicting
metadata are distinguished; fingerprint counts are not population coverage.
Completed passes can resume using `resume: true` with the same date, session ID
and configuration. SQLite retains up to ten versions per session, storing only
hashes, counts and typed pass status. Request slots are charged before a pass;
an interrupted in-flight pass is unconfirmed and is never repeated using the
same reserved slots. Plan-only calls do not write session state.

## Exact bibliographic verification

Use the existing source collector with `source: "crossref"` and `identifier`
set to one DOI; execution is opt-in. This source returns factual title, DOI,
publication date, type, venue and reference only, not authors or abstracts.
The public list endpoint has a conservative local quota of five calls per day,
one concurrent call and at least one second between distinct network calls.
The exact DOI 10.1002/adma.201404892 returned matching metadata and a successful
cache replay on 2026-11-25. Missing or mismatched records are not verification;
neither is a metadata match proof of retraction status. The official Crossref
status service reported a Retraction Watch incident on the observation date.
See https://www.crossref.org/documentation/retrieve-metadata/rest-api/ and
https://status.crossref.org/ for provider terms and availability.

No paid tier, automatic retry, new dependency, worker, public publishing, or
Google Trends workaround is added. Live provider recovery, independent
decision-quality validation and deployment remain separate gates.

Existing draft PR #432 covers concept validation, GitHub repository
discovery, HN/Stack Exchange and hybrid retrieval; #433 covers Devpost
evidence review. Do not duplicate or activate those changes here.
