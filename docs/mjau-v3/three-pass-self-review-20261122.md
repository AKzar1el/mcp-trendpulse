# MJAU v3 A04/A10 — THREE-PASS ENGINEERING SELF-REVIEW

**Date:** 22 November 2026. **PR:** [AKzar1el/mcp-trendpulse#382](https://github.com/AKzar1el/mcp-trendpulse/pull/382). **Initial frozen review commit:** `93d9a147cde19e1f715ad3cc24a3fa1d00fd0e0c`. **Reviewer:** automated/assistant engineering evaluation, NOT three outside people or independent counsel. This is an opt-in two-tool MCP, not the shared production MCP/worker registry.

## Verdict

| Independent-method pass | Score | Gate |
| --- | ---: | --- |
| **1. Realistic user tasks / source-fidelity** | **26/28** (14 tasks) | PASS for supervised local use |
| **2. Adversarial security / runtime** | **28/28** (14 checks) | PASS for supervised local use |
| **3. Original source-rights and operator review** | **21/28 before latest-head CI**; becomes **22/28 if exact-head CI passes** | Engineering safeguards met; **public/commercial rights and external human signoff NOT APPROVED** |

**PRIVATE SUPERVISED OPT-IN TESTING:** TECHNICALLY ACCEPTABLE once changes are checked out independently, launched explicitly and limited to the existing 8 Wikidata/10 OSV per UTC-day budget. The user does not need to manually repeat 285+ Python tests. **PUBLIC COMMERCIAL RELEASE:** NO-GO until source-specific attribution/permission and operator/independent evaluator approval for the actual product use case. This is a risk and license boundary, not a request for three further technical passes.

### Pass 1 — actual user outcomes: 26/28

Automated scorer ran 14 scenarios through the real budgeted source functions with **only retained minimal original provider snapshots**; truth was separately extracted from source JSON without the v3 match parser. All tests completed without an erroneous answer or false security declaration. No new external provider calls.

- Q89 apple fruit and Q312 Apple company were distinct in English and Slovenian; Mercury Q308 planet vs Q1150 deity was correctly ambiguous in both English and German; Q64 Berlin source labels matched in three languages.
- Missing Q42 English label, entirely unreturned QID, and truncated alias lists preserved source uncertainty instead of inventing matches.
- Original OSV ID lists for Django 2.2.0 (**75**), Jinja2 2.10.1 (**10**), lodash 4.17.11 (**6**), and no returned advisories for react 18.2.0 matched the official saved ID-only source envelopes; no details/severity or verified exploit claims copied.
- **W09 scored 1/2**: a user cannot search arbitrary names until they supply exact QIDs; intentional safe scope, but needs a separate discovery workflow. **W14 scored 1/2**: OSV ID-only evidence cannot independently recommend a patch or severity; it abstains safely, but requires a separate advisory verification workflow.
- The first run after improving the attribution notice temporarily caused a **false-positive test**: a string search flagged the word "severity" in a sentence saying that severity had **not** been included. The assessor now checks actual advisory field keys, not explanatory safety text. Re-run completed **26/28 with zero failed cases**.

Evidence: `docs/mjau-v3/three-pass-user-review-20261122.json`; exact reproducible offline scorer `tests/mjau_v3_three_pass_user_review.py`. Earlier preregistered live-original-source trial measured **12/12 scored Wikidata + 8/8 OSV**, two unscored due unavailable source, no query replay; see `workflow-holdout-results-20261122.json`.

### Pass 2 — adversarial + real MCP: 28/28

Baseline **61** adversarial/SQLite tests passed, plus **3 actual local MCP subprocess and guarded HTTP tests** passed. Post-attribution changes passed another **31** focused budgeting and transport checks. The combined current source-v3+existing-v1 regular regression suite passed **289/289** (three transport scenarios tested separately); Ruff and compileall green. Legacy local pytest prints a single `asyncio_mode` configuration warning with optional plugin autoload disabled; it is not an assertion failure.

During this round, the first review pass uncovered an actual user-facing discrepancy: `wikidata_identity(execute=True)` returned `OFFLINE_PARSED_UPSTREAM_PAYLOAD` while `network_performed=True`. Reproduced before patch, then fixed wrapper status to `source_entities_observed` or `source_entities_partially_observed`, preserving `source_payload_validated_offline=True`.

The security pass found two more *reproducible* validation gaps directly inside the internal HTTP helper: `_request_json` accepted a malicious alternate Wikidata Action API query at the allowed host, and an OSV `/v1/querybatch` body containing multiple version/package queries. The high-level plan builders already generated safe requests, but a lower-level internal caller could bypass the **one bounded original query** contract. Both tests failed red before patch; transport now verifies the canonical Wikidata QID query and canonical OSV single-query body **again** at the network boundary. 29 focused tests passed directly after the fix; expanded regression and integration tests remain green.

Additional verified controls: plan-only no cache/network; typed `execute`; strict source host/paths, MIME and 192,000-byte limits; eight-second timeout; no redirect/auto retries; Wikidata 8/day and OSV 10/day persisted caps across new SQLite instances; 429/503 no-repeat cooldown; eight-way singleflight requests reserve one quota; only safe projected OSV ID/date/link data cached; caller-specific Wikidata name matches never leak via QID cache; stdio real child and guarded HTTP tests clean up.

Evidence: `docs/mjau-v3/three-pass-security-review-20261122.json`; `tests/test_mjau_v3_budgeted_transport.py`, `tests/test_mjau_v3_budgeted_mcp.py`, `tests/test_mjau_v3_budgeted_stdio.py`, and the existing guarded HTTP tests.

### Pass 3 — primary-source licensing and operator checks

**Wikidata** explicitly dedicates structured labels, descriptions and aliases to CC0: https://www.wikidata.org/wiki/Wikidata:Licensing . Every entity output includes a QID source URL; no identity is auto-confirmed.

**OSV** explicitly returns ID and modified timestamp only in the one-query `/v1/querybatch`: https://google.github.io/osv.dev/post-v1-querybatch/ . The source list (https://google.github.io/osv.dev/data/) shows GHSA and PyPI advisories under CC BY 4.0, but the wider aggregator includes different original publisher rights.

**New official maintainer clarification:** https://github.com/google/osv.dev/issues/6264#issuecomment-6595561725 explicitly allows **commercial OSV API use and caching operationally**. The maintainer says Chainguard/Wolfi feeds are not expected in the `npm`/`PyPI` ecosystems we restrict to, but that the project has **no blanket aggregated bulk-data license** and cannot certify that any particular downstream attribution complies with original CC BY requirements. A second contributor explains the special scanner license for Chainguard. Both concerns are narrower for our ID/date-only use, but a formal public commercial rights grant cannot be inferred.

The user-facing OSV output now explicitly names the aggregator, includes a source-list link and CC BY link, documents the transformation to factual IDs/modified timestamps/links only, discloses that the user's package coordinates are sent to a third party only on `execute=True`, and says original per-record feed is **not verified**. It retains `commercial_bulk_redistribution_approved=False`. There is no raw vulnerability prose or severity copied.

**Outstanding scored failures not solvable by another assistant pass:** L07 original *per-record* source identity/rights is not independently proven by the compact API (0/2); L13 no external human independently signed unfamiliar-user tasks (0/2); L14 no owner/legal permission for *public commercial distribution* under every upstream source (0/2). L12 exact new-head CI is pending at report preparation (1/2; upgrade to 2/2 only after GitHub success). The opt-in sandbox is documented as fully reversible without affecting the original 16-tool connector or any workers.

Evidence: `docs/mjau-v3/three-pass-license-ops-review-20261122.json`, `a04-a10-source-rights-review-20261122.md`, `opt-in-budgeted-mcp-review-20261122.md`.

## Exact operational next step

1. Commit this **isolated draft** to GitHub, run exact-head CI/Container/Publish stdio checks, keep separate tool uninstalled from production.
2. For owner-supervised local testing, explicitly launch `python -m mcp_trendpulse.mjau_v3.mcp`; default calls are **plan-only**, and only `execute=True` makes original source requests inside daily quota. No user secrets and no automatic schedule.
3. For public/commercial use, have a responsible person examine exact original-source attribution and your specific service's permissions, and separately authorize any merge/deployment. A fourth identical assistant pass would not replace these facts.

**Reviewer limitations:** This is one AI assistant using three **different methodologies**, not three independent humans. Metadata snapshots were originally acquired and documented by the same project, while the direct field extractor for pass 1 was independent of parser functions; no evidence about external user satisfaction or financial return was produced. The scored technical sample cannot establish a formal legal right or universal official MCP conformance certification.
