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

## Evaluated outcome — 2026-11-21

**Positive 1 — Node.js 22:** `isEoas=true`, `isEol=false`, `isMaintained=true`, EOL `2027-04-30`. Original Node.js release schedule independently agrees on 2027-04-30 (https://github.com/nodejs/Release/blob/main/schedule.json).
**Positive 2 — Python 3.12:** active support ended, provider EOL `2028-10-31`; primary Python dev guide corroborates **October 2028** (month precision only). Do not present the end-of-month day as independently vendor-certified (https://devguide.python.org/versions/).
**Positive 3 — Node.js 20:** official v1 source returned HTTP 200, `isEol=true`, `isEoas=true`, `isMaintained=true`, EOL `2026-04-30`. Original Node.js release schedule independently corroborates the **EOL date** (https://github.com/nodejs/Release/blob/main/schedule.json), but the provider's EOL+maintained flags **conflict** under its own documented definitions. A native adapter bug could previously have treated that as complete evidence. It has been fixed in source commit `3c3328774a416e250713ad05d659ab37792bac0c`: this is now `status=observed_partial`, with `provider_phase_conflicts=["eol_true_but_maintained_true"]`, uncached as complete. Re-verified with one native live provider GET; exit 0, isolated SQLite cleanup.
**Negative 1 — Unknown:** `nonexistent-mjau-20261121/0` returned **HTTP 404**, not a measured EOL or zero remaining support.
**Adversarial:** do not make purchase/migration/buyer claims from these support dates; report contradictory flags, unknown dates and source beta semantics. The source's official OpenAPI explicitly says `isMaintained` means some level of support; hence concurrent `isEol=true` and `isMaintained=true` is a provider phase contradiction (https://github.com/endoflife-date/endoflife.date/blob/master/api_v1/openapi.yml).

**5-case result:** 2 positives fully source-consistent, **one date corroborated but phase-conflicted**, negative/no-data and uncertainty guards passed. Distinct new release-cycle evidence **YES**; the provider's contradictory flags show a live quality risk. **Decision:** B02 is **PROVISIONAL/BLOCKED FOR FULL ACCEPTANCE** until a policy for conflicting source flags and independent vendor cross-check is formalized for all public answers. Strictly do not ship EOL support recommendations as unequivocal when conflict is present.
