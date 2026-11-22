# Independent human reviewer packet — A04/A10 on PR #382 (2026-11-22)

**Reviewer needed:** someone *other than the implementer*, with no prior access to the expected outputs, to complete this check before any public/commercial release. This form is currently **UNSIGNED**; automated source-fidelity tests do not constitute this signoff.

## Scope and artifacts

- Review **only** the two additional opt-in tools in draft [PR #382](https://github.com/AKzar1el/mcp-trendpulse/pull/382): `mjau_v3_wikidata_names` and `mjau_v3_osv_advisory_ids`.
- Source-fidelity evidence: `docs/mjau-v3/workflow-holdout-preregister-20261122.md` and `docs/mjau-v3/workflow-holdout-results-20261122.json`. Automated original-provider comparison: 12/12 scored Wikidata tasks and 8/8 OSV tasks passed; two QID tasks were unscored because their batch was unavailable. **A Windows SQLite temp-cleanup error occurred only after those comparisons; results were recovered from console and SQLite receipts, without repeating provider calls.** This is NOT a claimed human-review pass.
- Source-policy evidence: `docs/mjau-v3/a04-a10-source-rights-review-20261122.md`. Official OSV source table contains CC BY, CC0, CC BY-SA, MIT/Apache and restrictive CC BY-NC-ND original licenses. No blanket commercial reuse approval.
- Technical test report: `docs/mjau-v3/stress-qa-round2-20261121.md`. Additional source integration tests run against disposable SQLite, never production.

## Blinded workflow prompts

**A04 Wikidata (no automatic merging):** Ask the reviewer to describe expected decisions *before* opening the actual tool output. Compare with original Wikidata entity records, not only the implementer's tests.

1. Is `Q89` (apple fruit) the same identity as `Q312` (Apple Inc.)? Review English and Slovenian names/aliases.
2. How should exact English name `Mercury` be handled across `Q308` and `Q1150`? Check ambiguity and absence of auto-confirmation.
3. Can `Q64` be labeled in English, German and Slovenian? If one label is absent, must the status be unknown?
4. If QID `Q42` has no English label in the returned exact scoped snapshot, does the tool invent 'Douglas Adams' or abstain?
5. What happens when an entire requested QID is absent, missing, or rejects parsing? No definitive 'not found' based on absent source coverage.
6. Does a 20-alias source with only 8 projected aliases label an unobserved name as 'not found' or as incomplete?

**A10 OSV (no false safety claim):**

7. Given PyPI `Django==2.2.0`, does the response return all available official per-response IDs (75 in the original snapshot) without downloading full advisory descriptions?
8. Given PyPI `six==1.16.0`, is 'no indexed advisories in this response' correctly distinguished from 'secure package'?
9. Given npm `lodash==4.17.11`, are advisory IDs preserved despite long/unsafe references and are raw bodies omitted?
10. Does the output clearly distinguish advisory IDs from independent vulnerabilities, exploitation proofs and guaranteed fixes?
11. Can the reviewer find source attribution, upstream license caveats, a CC BY license link and a clear commercial-redistribution **not approved** warning? Check that GHSA/PYSEC prefixes are only origin hints.
12. If an original source is HTTP 429/503, malformed, oversized or paginated, does the tool show source unavailable/incomplete rather than fake zero?
13. Does `execute=False` make no network call and create no cache? Does `execute=True` spend at most one local daily quota reservation per unique request?
14. Does the optional MCP start separately without changing the existing community/hosted v1 services and without exposing arbitrary URLs or credentials?

## Scoring rubric and required signoff

For each prompt, mark **Correct**, **Incorrect**, **Abstained appropriately** or **Unreviewed**, along with original-source citation and any misleading content. **Fail the release gate for any falsely confirmed identity, falsely secure package, unknown source presented as clean evidence, unauthorized original-feed content reuse, source-origin mismatch, or daily-quota bypass.**

Independent assessor should also conduct one unfamiliar genuine use case in their own workflow and rate usefulness (task completion yes/no, time to source-verified answer, answer clarity, warnings/attribution usability). Recorded results should be reviewed before a PR is converted from draft; do not infer success from code tests or asserted benchmarks alone.

**Reviewer name:** [not assigned]
**Reviewer independence / affiliation:** [not verified]
**Review date:** [pending]
**Reviewed original references and any follow-up license permissions:** [pending]
**False positives / false safety claims:** [pending]
**Usefulness score and real-task notes:** [pending]
**Signoff:** [PENDING — no independent human decision has been recorded]

**Reviewer must not edit production tool config, merge PR, deploy or request credentials.** Only review recorded source snapshots or the isolated opt-in test server.
