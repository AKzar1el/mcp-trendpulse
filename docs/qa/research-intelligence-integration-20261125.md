# Research intelligence integration review — 2026-11-25

Integration branch: `integration/research-intelligence-20261125`.
Pinned inputs: #445 `888a0776f3ba114ee831a83de7d799475171bd7d`, #432
`0d78b6de49b2dc0015534b2999764c749f7f0712`, #433
`7fe55ca671ba0a1c4f722164ac45f837cbd98204`. Work is confined to the
existing isolated research worktree. Other draft branches and workers are
not edited. This is not a production release.

## Integration changes

- Preserve the adaptive hunter, Crossref metadata verification and provider
  cooldown diagnostics from #445 while adding concept and Devpost review.
- GitHub search requests carry `is:public`; authenticated responses must
  establish public repository visibility before projection or caching.
  Ambiguous visibility fails closed. Previous GitHub cache keys are not
  replayed by the new collector. This can reduce hybrid coverage when the
  provider does not include repository visibility. Do not bypass this check.
- Devpost observations use note-independent identity; different dates and
  contradictory statuses remain distinct observations, not independent sources.
  Bounded citation trails preserve exact source references, dates and caller
  provenance, with omission counts and links from gates to evidence IDs.
- All 16 community tools stay unchanged; the opt-in intelligence surface has
  19 tools and 28 source adapters. The isolated unified V1/V2/V3 surface has
  37 tools. Public V3 package exclusions remain in place.
- A frozen tool-discovery regression identified the concept tool competing
  with model discovery. Clarify that it verifies one dataset identifier; keep
  original evaluation tasks and accuracy thresholds unchanged.

## Provider and reuse boundaries

GitHub search documentation supports `is:public`; API access does not grant
repository reuse rights. Stack Exchange API terms require source attribution
and public contributions carry revision-specific CC BY-SA licenses. HN API
access is not a blanket license to redistribute discussions. Hugging Face
metadata is not permission to download gated data or redistribute samples.
Keep source-linked factual metadata and verify applicable attribution/rights
before distribution. No gated content or private repository data was used
for these offline regressions.

- https://docs.github.com/en/search-github/searching-on-github/searching-issues-and-pull-requests
- https://docs.github.com/en/rest/search
- https://github.blog/changelog/2026-04-02-improved-search-for-github-issues-is-now-generally-available/
- https://stackoverflow.com/legal/api-terms-of-use
- https://stackoverflow.com/help/licensing
- https://hn.algolia.com/api
- https://huggingface.co/docs/hub/datasets-gated

## Remaining release gate: independent blinded decision-quality assessment

Freeze the following tasks and use equal request-slot caps, source windows and
time limits for both arms; record provider unavailability and actual calls.
Use the original hunter and the combined concept/hunter workflow. Do not retry
unavailable sources or relax quotas. Use no CORDIS calls during its outage.

1. Browser-agent prompt-injection regression testing: identify alternatives
   and whether a replay harness addresses a documented gap.
2. Embedded software testing: identify a specific recurring failure and
   distinguish active tooling from stale repositories.
3. Invoice-fraud review automation: identify an actual recurring workflow and
   distinguish problem observations from purchase evidence.
4. Municipal electrical permits: identify comparable incumbent workflows,
   identify missing geographic and buyer evidence, and abstain if unavailable.

Prepare two bounded source-linked packets per task, anonymizing arm labels and
randomizing order before giving them to an independent reviewer. Keep the
mapping separate until scoring is recorded. On each packet grade source
relevance, independent corroboration, actual feature equivalence, useful
decision changes, and unsupported claims; score each 0-2 and record a reason
and references. Measure unsupported claims separately; no arm may turn an
unavailable observation into zero demand or infer buyer validation. Compare
paired scores, denominators and disagreements, not only returned record counts.
The developer's own review is not an independent blinded assessment. The
existing live lexical-match comparison and offline tool-selection proxy do
not satisfy this release gate. No independent reviewer was available in this
execution; do not mark the gate passed.

CORDIS is an upstream outage and is excluded from additional live probes by
owner direction. Existing strict live-provider gates are not weakened.

## Executed blinded AI assessment — 2026-11-25

Evaluated code: `7b51e7b8a970b88412924c6e7690c099bb35c9e7`.
Original hunter logic: `d513d4fb00ca2f4c7dcd244986945228fb03139a`.
Both arms used the current hardened public-only transport, evidence projection,
and existing quota/cache controls. This isolates a workflow comparison rather
than reproducing all historical version behavior. The original arm used a
primary and fixed alternate query; the integrated arm used concept validation
and relevance-first academic retrieval. Eight randomized, arm-anonymous
packets were given to a fresh AI reviewer in a separate anonymous conversation.
The reviewer received public metadata, not the arm mapping or code. The raw
scoring response was recorded before deriving the unblinded summary. Source
identities remained visible; the reviewer did not independently open links.

The planned cap was five request slots per task and arm, five sampled records
per source and a 30-day window where supported. Actual reservations were 27
of 40 planned slots; no budget reset, paid API, or CORDIS request was used.
Provider exhaustion and unavailability were retained, not replaced by zero
demand. At most 12 observations were displayed per packet.

| Task | Original score /10 | Integrated score /10 | Original requests | Integrated requests | Original displayed | Integrated displayed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Browser-agent prompt injection | 3 | 7 | 5 | 5 | 0 | 12 |
| Embedded software testing | 3 | 6 | 5 | 4 | 0 | 11 |
| Invoice-fraud automation | 3 | 7 | 2 | 3 | 0 | 6 |
| Municipal electrical permits | 3 | 3 | 1 | 2 | 0 | 0 |
| Total | 12/40 | 23/40 | 13 | 14 | 0 | 29 |

| Dimension (maximum 8 per arm) | Original | Integrated |
| --- | ---: | ---: |
| Relevance | 0 | 5 |
| Independent corroboration | 0 | 3 |
| Concrete feature/workflow evidence | 0 | 3 |
| Decision usefulness | 4 | 4 |
| Unsupported-claim control | 8 | 8 |

The reviewer preferred the integrated packet in three pairs; the fourth was
inconclusive. No unsupported claims were flagged, and no buyer validation or
working feature equivalence was established. The raw score improved from 30%
to 57.5% (+27.5 percentage points). Conservative sensitivity: the invoice-fraud
packet's corroboration score of 1 may be too generous because its relevant
evidence is repository-only. Scoring that dimension 0 gives 22/40 (55%).
Preserve the original reviewer score rather than silently altering it.

### Verification and limits

- Reviewer input SHA-256: `cc882669ef8b24b8d59305dec23bfaf7588e86cbeab86f2e15ac479d633d87ee`.
- Reviewer result SHA-256: `be8ea073e96cc71760352122329991ee578bff08b31708caf9f7e271a254d172`.
- All eight score IDs, five integer dimensions, four paired preferences, and
  citation membership in the supplied packets were checked programmatically.
- The raw packets, mapping and reviewer response remain local QA artifacts.
  This repository receipt intentionally excludes raw third-party metadata
  and private filesystem paths; redistribution rights have not been cleared.
- Review receipt: https://github.com/AKzar1el/mcp-trendpulse/pull/446#issuecomment-7172069253

This completes the initial separate-context blinded AI assessment, not an
independent human or source-verification audit. The sample has four tasks,
one AI reviewer, different source choices, unequal realized provider coverage,
and a common transport layer. Repository metadata and update dates do not
establish actual functionality, adoption or purchase intent. The equal
decision-usefulness scores do not support a claim of improved commercial
decisions. No release gate is cleared by this receipt alone. Preserve the
strict live-provider checks and outstanding source-verification and applicable
redistribution/attribution requirements before production promotion.

The evaluated code previously passed 3,342 offline tests, with one skipped and
17 deselected, independent MCP stdio 14/14, offline cross-source 7/7, Ruff,
package build and V3 public-wheel exclusion checks. Consolidated CI recorded
22 successful checks, two live-provider failures and two publication skips.
These results apply to the pinned code, not to an untested runtime deployment.
