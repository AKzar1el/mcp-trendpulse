# MJAU v3 lean release acceptance — original-source evidence and rights (2026-11-21)

**Scope:** ONLY A04 Wikidata and A10 OSV, against merged v1 commit `691846684f28652ed5d67973641596d9aaa93849`. This is a **source-backed engineer validation**, not a blinded independent end-user study, legal opinion, security guarantee, or production release.

**Preregistered before observations:** `docs/mjau-v3/acceptance-preregistered-20261121.md`, Git commit `a5e5d2db09b645760c937019575cc87637ff3e30`. Fixed nine requests (one Wikidata QID batch, eight OSV exact package/version). Real bug forensics after those nine requests used one compact four-item batch and two separate explicit, bounded, opt-in corrective checks. **Total: 12 free original-provider HTTP requests**, no retry, no paid compute, no change to worker budgets or installed services.

## A04 — validated but identity confirmation still manual

One official Wikidata `wbgetentities` request for **Q42, Q64, Q30** across `en,de,fr,es,sl,it` returned HTTP200 in **742.5ms**, **5,863 source bytes**, SHA-256 `79994a13f1c0028fceef3012e4c4c09ecc110ce71b62369f04bb6048041c45ae`.

- Q64 (Berlin) and Q30 (United States) returned label records for **6/6** requested languages. Q42 returned **no labels** in this scoped source response. The adapter correctly returns an unconfirmed/unknown label rather than manufacturing a famous person's name. Do **not** interpret the empty field as proof the entity or language doesn't exist.
- Source returned **9 German aliases** for Q64; Q30 had **20 English, 15 German, 19 French aliases**. Projection remains capped to 8 per entity per language; `aliases_truncated` and `source_alias_count` are exposed. An unmatched name after truncation is `unknown_incomplete_aliases`, never an asserted non-entity or auto-merge.
- Real Q89 fruit/Q312 company and Q308 planet/Q1150 Roman deity snapshots continue to pass; deliberate ambiguity across six languages is **never** treated as confirmed identity.
- Exact merged v1 `plan_source("wikidata_action_api")` still rejects unknown source. A04 thus adds an **official source-backed answer absent from v1**, but the source itself was used to check outputs, not independent human labels; no claimed precision@K/customer productivity increase.

**Source license:** Wikidata's official [licensing policy](https://www.wikidata.org/wiki/Wikidata:Licensing) says structured item/property data is **CC0**. No nonstructured wiki prose, media, biographies, or third-party asset licenses are being copied. Cite the exact QID link on any downstream output. Identity is only a source-listed candidate, not a corporate registry determination.

## A10 — real package/version triage and the corrected compact path

All **8 preregistered OSV `/v1/query` calls returned HTTP200**; initial adapter and source outcomes:

| Exact version | Source IDs returned | Initial bounded adapter |
| --- | ---: | --- |
| PyPI Jinja2 2.10.1 | 10 | 10 IDs projected |
| PyPI six 1.16.0 | 0 | **No indexed advisory in this response, NOT safe** |
| PyPI requests 2.19.1 | 10 | 10 IDs projected |
| PyPI Django 2.2.0 | Full response >192,000 B | **Explicit oversized unknown**, not zero |
| PyPI PyYAML 5.1 | 6 | 6 IDs projected |
| npm lodash 4.17.11 | 6 | **Source reference overflow detected**, never zero |
| npm minimist 0.0.8 | 2 | 2 IDs projected |
| npm react 18.2.0 | 0 | **No indexed advisory in this response, NOT safe** |

**Source-backed corrective improvement 1 — compact querybatch:** official `POST /v1/querybatch` returns **advisory IDs and modified times only**; the single four-query verification response (Django, lodash, Jinja2, react) was HTTP200, **6,211 bytes**, SHA-256 `c06f2360f56d7f99107b177bf630900a1912938ac3239c3450ff9accbade5e63`, and yielded **75, 6, 10, 0 source IDs** respectively. A subsequent single Django-only compact query completed with **75/75 IDs in 5,086 bytes** and SHA-256 `19d2191ff0de4edfaf12af148a0acc91012e9770001557562d08429006627010`, compared to a full-details response exceeding the 192KB cap. New `plan_compact_package_query()` emits **one fixed-origin request**; new `parse_compact_package_query()` accepts precisely one response, records source ID, modified time and source-specific attribution, outputs at most **100 records**, flags truncation/pagination explicitly, and never embeds advisory descriptions.

**Source-backed corrective improvement 2 — full-details references:** in a single follow-up `lodash@4.17.11` full query, six advisories arrived; one GHSA advisory supplied **93 source references**. The previous 30-reference rejection hid all six. Updated `_advisory()` projects at most 30 references to a bounded 4-link output and marks `references_truncated`, while retaining **6/6 advisory IDs**. Source SHA-256 of the live full response was `30fdd2293c40fea8a5383fde2d80af4bdecb13e4d63b4300ad382fa14665b928`. No original advisory bodies or reference text are committed; source-derived count fixtures plus constructed safe URL test records reproduce the edge case.

**Source terms and attribution:** OSV.dev is an aggregator; its official [source-license table](https://google.github.io/osv.dev/data/) lists GitHub Advisory Database (GHSA) and PyPI Advisory Database (PYSEC) as **CC BY 4.0**, and other feeds under other licenses, including potentially noncommercial/no-derivatives. The output contains factual IDs, modified timestamps, OSV source links, and non-authoritative origin-license hints; **no raw summaries, descriptions, reference pages, unlicensed text or bulk advisories are copied.** The existing `source_specific_license_review_required=true` and `raw_advisory_redistribution_authorized=false` fields apply to every record. Any future UI must link to its original database, surface appropriate CC BY attribution and changes notices when using protected content, and separately review uncommon/unknown feed licenses. An OSV match is neither exploitation evidence nor a buyer/revenue prediction; an empty response is neither proof of safety nor complete security assurance.

## Measured value vs merged v1, cost and remaining limits

- **New factual answer coverage:** merged v1 has neither `wikidata_action_api` nor `osv_public_api`; the two retained adapters return source-scoped answers or unknowns where v1 cannot offer the same official-source lookup. This meets a *source-coverage* distinctness test, **not** a generalized customer productivity uplift.
- **Known false assurance:** **0** observed incorrect auto-confirmed identities or claims of safe packages. Missing Q42 labels, no indexed OSV match, oversized full Django response, and incomplete projections remain explicitly unknown or bounded.
- **Corrected completeness:** previously lost Django and lodash cases now yield **75/75 ID-only** and **6/6 full-source IDs** respectively, with no additional paid dependency and no unbounded download.
- **Engineered limits:** one request per approved plan, <=8s timeout, response cap 192,000 bytes, max 100 compact IDs, max 12 detailed advisories, max 30 inspected references and max 4 source URLs per record; no background fetch, paging loop, shared cache mutation or rate-limit evasion. ID-only batch response does **not** establish independent vulnerability counts because GHSA/PYSEC aliases may describe the same underlying issue; no auto-dedup across IDs.
- **Human review limit:** these are official-source and deterministic negative checks performed by the implementing engineer, **not an independent blinded labeling panel**. Broader researcher workflows and release attribution/permissions remain an owner-review requirement.
- **Tool integration limit:** all plans/parsers are still offline-only; they are not registered into a production MCP tool or collection worker. The owner must approve use through the existing v1 budget/cache and a reviewed MCP/CLI adapter before release. This report does not authorize merging.

## Verification

The combined local **207 ordinary tests** and **1 real guarded-HTTP integration test** passed on Windows Python 3.13.5. Ruff and compileall passed. Source samples are stored only as CC0 Wikidata structured data or minimized OSV ID/modified/count projections, with original-source SHA-256 receipts.

**Release verdict:** **A04 and A10 remain the only justified v3 source candidates** with improved source coverage and safe missingness. They are technically validated against the merged v1 APIs but remain **DRAFT until a reviewed budgeted integration, independent workflow verification and source-specific distribution policy are accepted**.
