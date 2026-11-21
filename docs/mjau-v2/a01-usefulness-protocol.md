# Predeclared five-case usefulness protocol: A01 official MCP Registry

Recorded 2026-11-21 **before** evaluating these cases. Only legal, free sources. Source-observed facts and uncertainty only; no invented demand measurements. Not approval to merge.

## Cases

1. Positive: search `filesystem` latest+limit=3. Name and version of at least one real active registry entry with primary link; v1 competition is `not_measured`.

2. Positive: search `github` latest+limit=3. Record named entries and primary links, not inferred semantic equivalence.

3. Positive: search `postgres` latest+limit=3. Record exact registry matches with version/source, without user-count claims.

4. Negative: search `nonexistent-zzxy-invalid-named-server-2026` latest+limit=3. Must return no catalog matches, not assert zero competitors or zero demand.

5. Adversarial: name-substring evidence cannot verify functionality, downloads, paying users or authenticity of publisher-supplied GitHub repo links.

## Success gate

At least two of three positive tasks supply new verified catalog records unavailable in v1; both abstention safeguards pass; at most four real queries.

Record exact response status, primary source link, unit/coverage, real answerability relative to v1, abstentions and failures. A legal, operational, source, or measured-usefulness failure means BLOCK or DISCARD, not quiet retention.

## Observed evaluation (2026-11-21)

**Live requests:** 3 new one-page HTTP reads (name substring `github`, `postgres`, and `nonexistent-zzxy-invalid-named-server-2026`), all successful with source-shaped JSON. Every identical second call was a zero-network validated-cache replay. Earlier `filesystem` proof returned active catalog name `com.pulsemcp/remote-filesystem`, but its version was not retained in the earlier report; therefore it is **not** counted as a newly completed positive case in this prospective protocol.

| Case | Evidence | Assessment |
| --- | --- | --- |
| Filesystem | Earlier live source: active `com.pulsemcp/remote-filesystem` name; exact version not logged | PARTIAL, not a prospective complete positive |
| GitHub | Three latest-active name matches; examples `ai.agentapigate/github-huggingface-arxiv-papers-repos-search-api-mcp@1.3.0` and `ai.agentapihub/github-huggingface-arxiv-papers-repos-search-api-mcp@1.3.0` | PASS as named source-discovery only |
| Postgres | Three latest-active name matches; examples `ai.getvda/kafka-and-postgres-monitoring-stack@1.0.0` and `ai.getvda/minio-postgres-redis-stack-generator@1.0.0` | PASS as names, **NOT proven Postgres MCP functional competitors** |
| Deliberately nonexistent | `status=no_data`, zero catalog matches, no demand claim | PASS guardrail; not evidence no competitors exist elsewhere |
| Semantic/market certainty | `customer_demand_verified=false`, `competition_verified=false`; publisher URL unverified, name substring only | PASS safety labeling |

**Measured incremental utility:** 2/3 predeclared positive prompts gave verifiable **named Registry leads** with exact version/primary metadata where v1 only returned `competition:not_measured`; 2/2 guardrails upheld. This **does not validate semantic relevance**, competitive comparability, popularity, source originality, buyer traction or revenue. Examples include bundled monitoring stacks and possible mirrors, illustrating why label-only discovery must not be presented as proven rivals.

**Decision:** useful **source-discovery subcomponent**, **A01 full competitor intelligence not yet accepted**. Before merging, assess precision on human-labeled true alternative questions and complete full tests/license review. If it cannot beat v1 decisions beyond noisy name matches, discard the subcomponent rather than advertise a competitor oracle.
