# MJAU v3 — lean release scope and deletion decisions
**Decided: 21 November 2026. User direction: cut features that are low priority or not demonstrated useful.**

## The only active v3 work

**ACTIVE FEATURE CANDIDATES (2):** `A04` Wikidata QID multilingual identity and `A10` OSV factual vulnerability evidence. Continue strictly opt-in, budgeted, limited-result, source-traceable validation. Their two independent draft PRs are not release-accepted; they need a real user-workflow benefit, appropriate source licensing and an integration review against settled v1.

**ACTIVE TEST/QUALITY GATE (1):** `B08` official version-pinned MCP conformance. This is a **quality assurance task, not a new MCP data feature or permanent tool**. Keep the already-proven real Python SDK stdio+HTTP checks. The full official `@modelcontextprotocol/conformance@0.1.16` requirements run still has **not** executed because test-only dependency installation failed; do not mislabel it green, spend more time retrying the same stuck npm/Bun/Yarn commands, or add a production dependency to compensate.

This makes **3 active IDs out of the original 21**, of which **only 2 are user-visible feature candidates**. Do not register, merge, deploy, or expand them without the existing per-feature proof gates and explicit owner approval. Current normal production behavior and 16-tool community MCP are unchanged.

## Keep the evidence, not the feature backlog

| ID | Decision | Specific reason and reactivation condition |
|---|---|---|
| **A05** | **KEEP AS OFFLINE RESEARCH ONLY**, not a release blocker | Deterministic historical replay is valuable *for future evaluation*, but currently has **0/20** independently attested historical outcome labels, so it cannot prove any uplift. Keep its isolated research module/tests in draft Stage0 evidence only, do not register as MCP/CLI or include it in the release deliverable; revisit only if independently audited as-of-safe examples are supplied |
| **A09** | **DEFER / NO IMPLEMENTATION** | Two-storefront Apple official API works, but commercial non-promotional competitor-metadata reuse is **not clearly licensed** and ranking/order cannot establish popularity. No adapter, metadata crawler, cache or worker. If rights cannot be established for the exact use, discard rather than ship |
| **B18** | **DEFER ONLY AS A POSSIBLE A10 FOLLOW-ON**, removed from active roadmap | CISA KEV confirmation and FIRST EPSS statistical probability are genuinely different source measures that *might* improve actionable OSV security triage. But no A10 integrated workflow value is established yet, and B18 itself was not live-tested. Require accepted A10 usage and a separately measured precision/safety benefit before **new explicit user approval**; no collector or implementation now |

## Rejected from the v3 release; no dormant implementation

| ID | Decision | Grounded rationale |
|---|---|---|
| **B09** | **REJECT / REMOVE CODE** | Preregistered real `github_issues` benchmark on SDK #3551 original, #3596 explicit duplicate and #3100 distinct source: actual v1 produced **2 correct origins, 1 duplicate; B09 exactly 2/1**. **0 added correct decisions**; it requires the same manually supplied origin identity v1 already consumes. The experimental `origin_graph.py` and B09-only tests/fixtures are removed from the active Stage0 draft. Evidence is preserved in an earlier immutable Git commit and `b09-last-chance-*.md` docs |
| **A11** | **REJECT / PERMANENTLY EXCLUDE** | Preregistered BM25 live-MCP trial: **16/24 first-tool**, **23/24 top-5**, **0/4 no-tool abstentions**, tiny two-search context saving. Failed core protective gates, no integration. Keep its historical isolated benchmark branch *only as evidence*, not as a feature or tool, no reactivation without a new explicit owner request |

## Remove the untested, lower-return B proposals from the active roadmap

**These 13 items were not independently performance-tested; dropping them is a priority/complexity decision, not a claim that their official APIs are useless.** They are archived as prior research ideas in the immutable original `.planning/mjau-v3-plan.md` on the planning branch, **not implementation-authorized**. Do not keep to-do tickets or hidden MCP registrations for them.

| ID | Idea | Why remove from active v3 |
|---|---|---|
| B05 | arXiv research metadata | High overlap with existing OpenAlex research stream; no demonstrated additional decision |
| B06 | Crossref DOI metadata | OpenAlex already supplies much of the attribution/reference layer; duplicate-maintenance risk |
| B10 | Change-point/seasonality algorithm | Existing M13 lifecycle labels cover broad need; no measured reduction in false trends |
| B19 | ClinicalTrials.gov | Health-specific claims and compliance burden for a domain-general tool; no validated recurring user task |
| B20 | NIH RePORTER grants | Niche US biomed funding; added cost to maintain and interpret against existing CORDIS/OpenAlex |
| B22 | ROR institution identity | Specialized research-affiliation joins; A04 already provides a general exact-identity workflow; separate institution utility untested |
| B23 | NASA EONET | Niche environment events; curated events don't measure general market demand |
| B24 | US EIA | Energy-specific metrics, account/API key, frequency/geo interpretation beyond current scope |
| B26 | Open Food Facts | Specialized food products, ODbL/database reuse constraints and uneven crowdsourced data |
| B27 | openFDA recalls | Niche product-safety compliance data, reporting lag and medical/safety interpretation risks |
| B28 | FRED/ALFRED vintages | Potentially useful only for a **later** A05 evaluation with real dated labels; free account/key and no current baseline cases |
| B29 | IETF drafts/RFC transitions | Niche standards tracking, drafts do not prove adoption or demand; no direct decision demonstrated |
| B30 | OpenCitations | Overlaps OpenAlex citation network; no measured independent added value |

**Not within this agent's authority:** the 20 different v2-track IDs and ongoing v1 merge work; report potential overlap but do not touch the other agent's branches, plan, workers or installed tools. This pruning is **only for v3's 21 IDs**.

## Release proof checklist for only A04 + A10 + B08

- **A04:** six-language original-source smoke already passed; parser real alias overflow and unknown negative handling fixed in PR #377. Next: 12-20 independently reviewed, real QID-scoped user naming tasks including ordinary and deliberately ambiguous cases; compare honest v1 exact-source coverage, human correctness/abstention, wrong merges, response size/latency. Existing official CC0 data license/attribution confirmed for factual Wikidata structured data, not third-party entity endorsements. Must still independently review integration requirements.
- **A10:** official positive/negative source observations and cache replay passed; malformed reference crash fixed in PR #378. Next: 8-15 real package/version research tasks spanning actual vulnerability, no indexed advisory, multiple license families, unknown upstream source, and one independent citation-level reviewer; report advisories not false safety/buyer demand. No raw text redistributions; GHSA/PYSEC CC BY 4.0 hints are not universal OSV grants.
- **B08:** no official CLI passed yet, even though Python MCP SDK stdio+Streamable HTTP sessions worked. Treat runner provisioning as an **external test prerequisite** until a trustworthy, isolated dependency-resolved official bundle is available; don't modify global npm or service. Distinguish per-protocol scored scenarios from optional tests. No conformance tier claim.

**Owner integration sequence:** finish/settle v1 (currently draft PR #328) first, then rebase only accepted A04/A10 into a single owner-reviewed branch; rerun exact tests plus source-rights, permissions, quotas, privacy and official conformance; deploy only after explicit authorization. A05 stays research-only, all other v3 proposed features absent. A dropped prototype can be audited by its frozen parent commit without shipping dormant code.

**Removal and rollback:** code deletions occur only on the isolated Stage0 research PR branch. Original proofs and feature branch histories remain reachable. No production migration or worker restart is required. This is not a claim that any cut API could never be useful in a different niche product.
