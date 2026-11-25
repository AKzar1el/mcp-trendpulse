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
