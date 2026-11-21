# MJAU V2 A01 - competitor-equivalence feature rejected

2026-11-21. No A01 source, tool or dependency included in the next integration. The research prototype stays on isolated branch feat/mjau-v2-discovery-a01-registry-20261121.

The official MCP Registry v0.1 API supports substring **server-name** searches, not capability or functional-semantic matches. The original predeclared five-case evidence:
- Filesystem: one plausible source name, but no complete version record was preserved for that first experiment.
- GitHub: three latest active name matches with original name/version links.
- Postgres: three name matches, including bundled stacks with services unrelated to a PostgreSQL competitor question.
- Deliberately nonexistent phrase: no catalog rows, correctly NOT "no competing products" or "no demand".
- Adversarial: names and publisher-supplied repo URLs cannot prove comparable functionality, customers, market share, pricing or traction.

**Observed marginal value:** 2/3 positive prompts generated versioned directory leads unavailable in V1, but **0/3 verified a genuine functional competitor**. Under the original prove-useful-or-discard rule, that is not enough to ship a product with the promised competitor/substitute intelligence. This is a conservative decision based on the reported original samples, not a statistical assertion about all registered servers.

**Decision: DISCARD A01 as an automatic competitor-equivalence engine.** Do not ship or quietly rename name-only records to validated rivals. A separate future, explicitly scoped MCP directory lookup remains research-eligible only if meaningful lookup value, licensing, false-positive checks and a distinct user decision are independently proven. Do not spend more requests on the four-per-UTC-day A01 source budget in this pass; the original pilot already documented four bounded source reads. V3 was untouched.

Primary API docs: https://github.com/modelcontextprotocol/registry/blob/main/docs/reference/api/official-registry-api.md
Original research/proof: docs/mjau-v2/a01-usefulness-protocol.md on the isolated A01 proof branch.
