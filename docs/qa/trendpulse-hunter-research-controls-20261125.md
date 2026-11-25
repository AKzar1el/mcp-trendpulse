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

This is a retrieval-control improvement, not measured relevance lift.
Offline tests cover the plan, bounds, late-match fixtures, quota degradation,
history separation and real MCP schema. Live relevance benchmarking and
deployment remain separate gates. No paid tier, automatic retry, new
dependency, worker, public publishing, or Google Trends workaround is added.

Existing draft PR #432 covers concept validation, GitHub repository
discovery, HN/Stack Exchange and hybrid retrieval; #433 covers Devpost
evidence review. Do not duplicate or activate those changes here.
