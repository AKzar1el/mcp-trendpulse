# Predeclared five-case usefulness protocol (b01)

Fixed **before further source sampling**, 2026-11-21. Real-source pass alone does not equal product acceptance. No changes to MJAU v1/v3 or user account.

## Tasks

1. Positive 1: `ossf/scorecard` yields dated per-check security observations; v1 issue/download evidence does not explain the checks.

2. Positive 2: `pallets/flask` yields a published scorecard or explicitly reports no coverage; do not invent a score.

3. Negative 1: `AKzar1el/mcp-trendpulse` returned 404 previously and must remain `not_covered`, not a negative security score.

4. Negative 2: a source check with -1 is inconclusive; missing `CI-Tests`, Contributors or other unscanned checks must never be silently asserted as passing.

5. Adversarial 3: repository assessment is never a security audit or a verified vulnerability/customer-demand assessment; stale/invalid data must be labeled, not ranked as safe.

## Outcome threshold

Two named scored repo positives with primary links if available, otherwise label coverage honestly; both negative cases and adverse safety case must pass; compare to actual v1 source coverage. No more than 2 new HTTP GETs.

Record exact source URL/response category, observed-at, named correct answers, no-signal decisions, false positives, cache calls and any contradiction against original provider/v1. A 429/403/unavailable finding is BLOCKED, never zero. An irrelevant answer is DISCARD unless a demonstrably better source can be validated without paying or circumventing protections.

## Evaluated outcome — 2026-11-21

**Positive A:** original native adapter `ossf/scorecard` returned 18 named checks and 8.8/10 source aggregate on a dated scan (2026-11-21). The v1 download and GitHub-issue signals cannot provide this public per-check evidence.
**Positive B:** independently fetched public source `pallets/flask` -> HTTP 200, **7.1/10**, 14 checks, scan 2026-11-09; `psf/requests` -> HTTP 200, **7.9/10**, 14 checks, scan 2026-11-16. Source fields were read only; these extra cases were feasibility reads, **not extra native adapter acceptance**.
**Negative missing:** own repo `AKzar1el/mcp-trendpulse` returned HTTP 404 in prior native adapter test -> `not_covered`, `aggregate_score=null`. Score absence does not mean insecure.
**Negative missing checks:** OpenSSF's own README confirms public scans omit some checks due to scale/API costs. Absence is **unscored/unknown**, not passed. Scanned individual -1 scores are mapped to inconclusive `null` in actual focused tests.
**Adversarial:** no security audit, no exploit verification, no buyer demand or blanket secure/insecure rank. Do not compare scores without scan date, check coverage, and same Scorecard version.

**5-case result:** 2/2 named scored positives observed with primary URLs, explicit missing-repo negative covered, other negative gates verified by official docs/focused tests. Distinct incremental evidence **YES**. **Decision:** *provisionally retain B01 as source-backed repository due diligence*, not accepted to public MCP. Full release still needs resource/terms/review and final v1+v3 integration regression.

Primary sources: https://api.scorecard.dev/projects/github.com/pallets/flask ; https://api.scorecard.dev/projects/github.com/psf/requests ; https://github.com/ossf/scorecard/blob/main/README.md . Official README licenses published REST results under **CDLA Permissive 2.0** and warns heuristics can have false positives/negatives.
