# MJAU v3 — preregistered focused real-source acceptance, 2026-11-21

**Decision under test:** Retain only A04 Wikidata and A10 OSV if they answer actual source-attributed questions absent from merged v1 **without misleading negative results, false identity/security claims, or unapproved data copying**. This is an engineer-run source-contract validation, not an independent blinded user study or release license opinion.

**Frozen before new external calls:** use the exact merged v1 `691846684f28652ed5d67973641596d9aaa93849` and lean candidate `019a8ff564a7d6e9102e9a8e63b2b2e863231757`. Do not expand to discarded IDs. Both adapters are pure plan-only modules and **do not add provider registration or network transport**.

## Fixed representative source tasks

### A04 exact QID / name / language (one new original-source request)

Request official `wbgetentities` with **three fixed QIDs `Q42`, `Q64`, `Q30`** across supported `en,de,fr,es,sl,it`. No fuzzy search and no auto-QID assignment. Measure:

- Distinct entity identity, label and description per requested language where present.
- For each item, the English label is a **candidate requiring confirmation**, never confirmed from mere text match.
- For a deliberately nonexistent name, no wrong QID; if an alias list is truncated, return `unknown_incomplete_aliases` rather than unqualified source absence.
- Six-language scope, unrequested language rejection, QID collisions, and real source alias length handling.
- Compare with v1's actual `plan_source("wikidata_action_api")` (should reject unknown source): **new answer coverage**, not percentage market-performance gain.

Use source data SHA-256, bounded JSON/metadata output, source QID URLs, original/source-observed date and CC0 license reference; never claim legal/corporate registry identity or full-language completeness.

### A10 exact package/version factual advisory lookup (eight new official queries)

Fixed `(ecosystem, package, version)` pairs:
1. `PyPI/Jinja2/2.10.1`
2. `PyPI/six/1.16.0`
3. `PyPI/requests/2.19.1`
4. `PyPI/Django/2.2.0`
5. `PyPI/PyYAML/5.1`
6. `npm/lodash/4.17.11`
7. `npm/minimist/0.0.8`
8. `npm/react/18.2.0`

For each, use **one official `POST https://api.osv.dev/v1/query`**, JSON body from the existing plan, timeout 8s, read **at most 192,001 bytes**, no paging or repeat on failure. Compare adapter's advisory IDs/count/status with source envelope; no advisory must mean *no indexed advisory in response*, not secure. An unexpected response, >12 advisories, page token, or >192KiB size is a **source-shape / incomplete-coverage finding, not a zero count**. Require exact input identity and source timestamps; no automatic vulnerability remediation, exploitation claim, or buyer intent inference.

**Rights:** the OSV API aggregates several source databases with different licenses. Retain only small IDs, timestamps, advisory source URLs, SHA-256 of source bytes, projected counts and provider identity; **do not commit full OSV advisory bodies or unreviewed descriptive text**. GHSA/PYSEC prefix license hints are not a universal grant. Cite the relevant source database and [OSV source rights index](https://google.github.io/osv.dev/data/).

Compare against merged v1 actual `plan_source("osv_public_api")` (not available). New source coverage is useful, but **do not claim measured security outcomes**.

## Protective predeclared outcomes

- **Technical acceptance:** no false positives on entity identity, no false safety from missing advisories, no misattribution across raw OSV license families, no leaked query tokens/personal data, bounded 8s requests/192KiB response, zero retries or shared worker/cache writes. Preserve complete source identity and signal unknown for partial/missing data.
- **Real-source shape:** all 1+8 requests permitted only if public/free original endpoints respond; HTTP failures remain explicit `unavailable`. One unexpected source shape is a repair candidate **only when reproducible** and can be fixed in isolation without new API scopes or dependencies. Retest locally and judge incremental usefulness.
- **Cost/performance:** 9 opt-in free public requests maximum; fixed-origin, no concurrent collection, no paid compute; record per-request elapsed wall time and projected JSON sizes, no fabricated demand or forecast.
- **Independent reviewer:** not available in this run; source consistency and exact-ID assertions are engineer-verified against original provider output. This limitation remains visible and bars claiming an independently validated user-success uplift.
- **Release approval:** positive source tests and lint/CI are necessary but do **not** approve merge or commercially licensed redistribution. An owner reviews source rights, final MCP/CLI wiring and additional human use cases before deployment.

Raw body scope and task ordering are frozen before the first new request. See the post-execution report for observed pass/unknown/fail counts.
