# V4.02 — Offline news intelligence foundation receipt

**Date:** 2026-11-28. **State:** IN_PROGRESS, not release-ready. V4.01 remains complete in design scope.

## Changes and observed verification

- Added `src/mcp_trendpulse/news_intelligence_schema.py`: frozen Pydantic models, bounded offline byte projections, explicit source/date provenance, stable source-specific article and observation hashes, exact duplicate/invalid/truncated counts, safe citation links, fixed-origin literal-phrase GDELT request planning and separate raw article coverage counts.
- Added `tests/test_news_intelligence_schema.py`: synthetic regression cases for source identity, dates, stable IDs, output count reconciliation, strict evidence markers, invalid/empty distinction, URL and query rejection, nonfinite JSON, attribution and timeline denominator integrity.
- Ran `PYTHONPATH=<isolated-src> python -m pytest -q <isolated-tests>/test_news_intelligence_schema.py`: **38 passed in 0.10s** with installed Pydantic 2.13.5 and pytest 9.0.2. This isolated environment used local copies of the two inspected baseline citation validators, not a full repository checkout. No live provider calls were executed through the module. The two tested files were transferred losslessly and their Git blob hashes verified: source `d92aef96d34697828abd3f30f5bfb6ff1b6534f5`, tests `fe4a3d839e9ac345f58a3d71b7b05389f61833c3`.
- Existing module/tool/manifest/provider/cache/CLI files were not edited. Protected main was inspected at `744fa81ff0376ce9bd9d8e6d726dcf924d53ea24`; open PRs #448, #446, #437, #436, #425 rechecked. The dedicated local connector remained disconnected, and direct git access from the test container failed DNS resolution; full repo, local uncommitted work and live runtime state are not verified.

## Source gates

GDELT's [official DOC documentation](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) describes the article-list and raw-volume modes; raw count and monitored denominator are separate measurements, not independent readers or event counts. Its [official terms](https://www.gdeltproject.org/about.html) permit reuse of released GDELT datasets with attribution. Third-party publisher text, photos and other rights are not granted automatically. The prototype deliberately projects metadata only, does not fetch linked articles, and includes GDELT attribution. No credential or paid dependency. DOC endpoint retrieval through the web tool was inaccessible; this is not an observed provider HTTP status or proof of current access. Existing provider budgets/cooldown and AGENTS.md remain binding; no new network path or retries. The [NASA official RSS directory](https://www.nasa.gov/rss-feeds/) is one direct-feed candidate; verify exact feed URL, rights, actual XML and allowed-use scope before implementation. [NASA linking/usage guidance](https://www.nasa.gov/nasa-brand-center/) does not grant rights to all third-party assets. No direct feed is registered yet.

## Scope and next actions

This is an initial implementation subset of V4.01's design: headline-only imports, source-reported locale labels (no inferred country/locale), UTC capture metadata explicitly supplied by caller, no body/canonical/resolved article fetch, no Event model or clustering. A supplied saved capture is not authenticated. Exact observation duplicate counts are not cross-provider syndication or source independence. Coverage projection must remain tied to a documented unsmoothed request and retained capture/query scope before live use.

1. Review and tighten schema edge cases, extend tests and contract mapping without changing legacy output.
2. Implement and validate one independent official/publisher RSS route with rights-aware bounded projection and exact source scope; inspect Media Cloud access separately.
3. For GDELT DOC, use the existing source policy, no automatic retries or provider bypass; verify actual permitted bounded responses before adding network execution. Preserve raw manifest mode and unknown/unavailable outcomes.
4. Run full offline suite, lint and exact-commit CI when the full checkout is available; do not mark V4.02 complete before live access/source coverage and required regression gates pass. No deployment, merge, public release, schedule change or tool registration authorized by this checkpoint.
