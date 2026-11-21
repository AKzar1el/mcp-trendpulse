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
