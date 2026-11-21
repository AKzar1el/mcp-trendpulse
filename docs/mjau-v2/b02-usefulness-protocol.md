# Predeclared five-case usefulness protocol (b02)

Fixed **before further source sampling**, 2026-11-21. Real-source pass alone does not equal product acceptance. No changes to MJAU v1/v3 or user account.

## Tasks

1. Positive 1: `nodejs` release `22`: distinguish `isEoas=true` from `isEol=false`, and preserve EOL date from both endoflife.date and primary Node.js support schedule.

2. Positive 2: `python` release `3.12`: preserve published end-of-life month with primary Python developer guide as independent corroboration.

3. Positive 3: `nodejs` release `20`: check whether provider reports already EOL and whether that matches primary Node.js schedule.

4. Negative 1: an intentionally missing product or cycle must be `not_found` rather than expired or zero days remaining.

5. Adversarial 2: `isMaintained` and end-of-active-support fields can differ; the adapter cannot invent buyer budgets, migration urgency or vendor legal guarantees.

## Outcome threshold

3/3 positive cases accurate source-supported phase/date semantics; both negative cases correct; 2 new HTTP GETs maximum (nodejs20 and deliberately unknown). Do not translate EOL into sales demand.

Record exact source URL/response category, observed-at, named correct answers, no-signal decisions, false positives, cache calls and any contradiction against original provider/v1. A 429/403/unavailable finding is BLOCKED, never zero. An irrelevant answer is DISCARD unless a demonstrably better source can be validated without paying or circumventing protections.
