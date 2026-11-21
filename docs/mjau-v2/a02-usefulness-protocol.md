# Predeclared five-case usefulness protocol: A02 GitHub privacy-safe star history

Recorded 2026-11-21 **before** evaluating these cases. Only legal, free sources. Source-observed facts and uncertainty only; no invented demand measurements. Not approval to merge.

## Cases

1. Positive: `fastapi/fastapi` ten newest weekly cohorts. Can it provide provider cohorts and a conditional two-window comparison?

2. Positive: `AKzar1el/mcp-trendpulse` ten newest weekly cohorts. Correctly handle zero or sparse weeks, without inferring population size.

3. Negative: provider week/day slots do not guarantee UTC; cannot assert precise UTC dates.

4. Negative: surviving stars do not include removed stars, customers, users, revenue or installations.

5. Adversarial: 403/429, malformed response or insufficient weeks must mean unavailable/inconclusive rather than growth or zero users.

## Success gate

Both real public repositories return grounded weekly observations (or clearly unavailable), the two-window comparison is conditional and all three negative gates hold; at most two live queries.

Record exact response status, primary source link, unit/coverage, real answerability relative to v1, abstentions and failures. A legal, operational, source, or measured-usefulness failure means BLOCK or DISCARD, not quiet retention.

## Observed evaluation (2026-11-21)

**New live public sample:** `fastapi/fastapi` first 10 newest weekly privacy-safe historical cohorts, one provider GET and one validated zero-network cache replay. First-page status `observed_partial`, not entire GitHub history. Provider current-snapshot surviving-star counts in two four-week windows after excluding the newest two provider weeks: recent **1,737**, prior **801**, computed **+116.85%** descriptive cohort comparison. This is **NOT historical net star growth** because unstar events and deleted stars are absent; cannot imply paid users, installs or commercial momentum. <https://api.github.com/repos/fastapi/fastapi/stargazers/history>

The earlier live `AKzar1el/mcp-trendpulse` one-page sample returned 10 weekly cohorts and a descriptive comparison; exact cohort counts were not retained in its proof log. Do not treat that earlier observation as newly verified numerical growth.

**Negative gates:** implementation explicitly marks provider timezone not guaranteed UTC and individual stargazer data absent; 403/429, malformed pages and insufficient history were exercised in focused unit cases. No intentional live 403 or forced 429 was generated. Original v1 GitHub issue and package-download sources do not include this star-history cohort measurement.

**Score:** 1/2 positive prompts fully documented with numeric observations, 1/2 previously observed but not numerically replicated under this prospective protocol; 3/3 guardrails modeled and/or asserted in focused tests. **Incremental value shown, but full acceptance remains OPEN** pending full repository regression, licensing review and an independently reviewed five-case outcome.
