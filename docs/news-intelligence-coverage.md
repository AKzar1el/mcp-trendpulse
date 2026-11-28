# V4.06 news coverage normalization

Experimental offline internal APIs, no registration, new dependencies, network calls or persistence.

- `summarize_news_snapshot(batches, as_of=..., hints=())` validates up to 16 typed batches and 80 supplied observations. Keeps provider-specific article keys, unique observations, URL strings, discovery providers, and event candidates separate. Counts repeated observation IDs once but keeps separate revisions. Does not sum overlapping provider source counts, count independent sources, or claim that a feed or capped article list represents all news. Missing/unavailable captures never imply zero; a successful empty capture describes only the supplied sample.
- Publisher-label and reported-publisher-host distributions count one label per provider-scoped article key. Missing labels and conflicting labels across revisions are disclosed. Exact casefolded publisher labels are not verified identities. Google News RSS aggregator hosts are excluded from publisher-host metrics. HHI = 10,000 times sum of squared shares among known labels only; top-one and top-three shares and known-label coverage accompany it. This is descriptive concentration of the sample, not market concentration, ownership or independent reporting. No regulatory HHI thresholds are used.
- `summarize_gdelt_coverage(report, expected_interval_seconds=None)` accepts an existing GDELT raw-timeline collector receipt, not unscoped counts. Revalidates query, fixed URL and unsmoothed raw mode; rejects out-of-window points, inconsistent counts, unknown status with measurements and capture before cutoff. Each interval share is 100 * matched / monitored. Overall share is 100 * sum(matched) / sum(monitored) for returned intervals, not the unweighted mean of percentages. Zero denominators and empty/unavailable outcomes give unknown shares. Optional caller-declared aligned 15-minute/hour/day grid diagnoses missing bins and endpoint/off-grid points; this is not a provider completeness guarantee. No silent zero imputation or cross-provider substitution.
- Keep article coverage, event occurrence, source independence, adoption and commercial demand separate. Caller receipts are structurally validated, not authenticated provider responses. Both APIs are experimental and deterministic.

References:
- GDELT DOC mode, raw counts and unsmoothed norm: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
- https://blog.gdeltproject.org/gdelt-2-0-api-now-supports-raw-result-counts/
- HHI arithmetic: https://www.justice.gov/atr/herfindahl-hirschman-index (formula only, not market or antitrust interpretation).

Evaluation: offline synthetic regressions, not a successful live GDELT timeline. Real-world sample/coverage calibration remains a release gate.
