# MJAU M08 — GitHub Issues developer-problem evidence

M08 reuses the existing **intelligence_foundation GitHub Issues source**:
plan_source("github_issues") builds one approved API request;
intelligence_core.collect provides its original transport, cache,
request lock and daily budget; intelligence_issue_quality performs the
existing conservative quality screen. M08 is a thin normalization layer
in src/mcp_trendpulse/intelligence_github_issues.py. There is no second
GitHub API client, credential, proxy, crawler or paid provider.

GitHub REST documentation:
https://docs.github.com/en/rest/search/search
https://docs.github.com/en/rest/issues/issues

GitHub Search matches are not an unbiased census of technical problems,
unique developers, independent customers or buying intent. Search
results can include pull requests; this module both searches with
is:issue and rejects any returned pull_request marker.

## CLI: offline preview, then explicit opt-in

Preview (does not open SQLite or issue a network request):

    uv run --locked mcp-trendpulse-cli intelligence github-problems --query "timeout" --repository microsoft/playwright --days 30 --limit 10 --format json

Explicit one-source-request path (or a validated original cache hit):

    uv run --locked mcp-trendpulse-cli intelligence github-problems --query "timeout" --repository microsoft/playwright --days 30 --limit 10 --execute --format json

The optional public owner/repo filter is intentionally exposed in the
output as repository bias. With no filter, GitHub Search's ranking and
available repository population are still nonrepresentative. The query
is a printable literal phrase (3–80 characters), not arbitrary GitHub
search syntax, a URL or a user profile selector. The query uses issues
CREATED in the last 7–90 UTC days, not old issues only recently updated.
At most ten first-page issue records are examined, with no hidden paging.

## Validation and honest semantics

Each source record must have a positive stable global issue ID, a valid
issue number, a canonical matching github.com/owner/repo/issues/number
link, a matching api.github.com/repos/owner/repo identity, state=open,
source-created and updated UTC timestamps, and no pull request marker.
Duplicated global IDs and duplicate repository/number pairs count once.
Source URL, title and the existing coarse issue_evidence_type label
are retained; bodies, author identities, labels, email addresses
and arbitrary external links are not emitted in M08 output.

The GitHub API exposes total_count and incomplete_results. M08 clearly
separates those source-reported values from the actually returned first
page and reports rejected/duplicate rows, distinct repositories,
distinct owners, and the most represented owner's fraction.
The title_contains_exact_phrase flag is purely a lexical check;
the coarse issue_evidence_type classifier is not a verified bug report,
customer problem, market opportunity or individual buyer.
Daily github_issue_mentions TrendSignals count only unique issues
on this bounded page; coverage_status=partial even for a fully valid
first page, because the full GitHub population is not sampled.

No result in the selected filter means no indexed matching issue
observed, NOT zero technical demand. Missing, malformed or incomplete
metadata must not imply full coverage or fabricated zero counts.

The existing core formerly retained a bounded copy of raw GitHub search
JSON which could contain user-pasted issue bodies and identifying
information. For NEW GitHub issue fetches, the M08 change persists only
source aggregate metadata and the existing allowlisted issue projection.
The original body is used transiently for the conservative classifier
and is never persisted by newly created M08 source snapshots. Previous
cached records are not deleted or retroactively rewritten; no quota
or cache history is reset.

Existing GitHub quota: 12 operations per UTC day, original SQLite store,
one-hour cache, per-request file lock, 429/503 cooldown, no redirects or
automatic retries. No new quota database, lock directory or bypass.

## Evidence and remaining live gate (2026-11-21 UTC)

A single independent, read-only authenticated GitHub API check
(NOT the M08 collector) for this literal search:

    "timeout" is:issue is:open created:>=2026-10-22 repo:microsoft/playwright

returned total_count=8, incomplete_results=false, and canonical source
metadata for issue IDs:

| Public issue | Global issue ID | Created UTC | State |
| --- | ---: | --- | --- |
| microsoft/playwright#44096 | 6370513287 | 2026-11-13T11:42:16Z | open |
| microsoft/playwright#44180 | 6449982165 | 2026-11-11T14:16:07Z | open |
| microsoft/playwright#43842 | 6154854553 | 2026-11-02T02:06:34Z | open |

This verifies that the official source provides the required fields,
NOT that the M08 adapter completed a live query, and not three buyers.
The new M08 CLI returned status=local_budget_unavailable,
requests_attempted=0, network_performed=false. The original daily
GitHub source budget stayed 0/12 for UTC 2026-11-21.

Read-only ACL inspection found the pre-existing Windows directory
C:\Users\Tomi\.mcp-trendpulse\intelligence\.request_locks is inaccessible
to the unelevated Codexify process, while the parent SQLite store is
readable. One narrow non-elevated attempt to grant Modify on this
EXISTING child returned Access denied, exit code 5. We did not delete
or reset the directory, replace the lock path, change the quota
database, copy credentials or override protection.

The independent elevated Windows directory owner can apply an
ADDITIVE ACL grant, without modifying quota history:

    $path = 'C:\Users\Tomi\.mcp-trendpulse\intelligence\.request_locks'
    & "$env:WINDIR\System32\icacls.exe" $path /grant 'DESKTOP-6AL4RUA\Tomi:(OI)(CI)M'

Only after the original lock is accessible should the live M08 command
be rerun once, followed by an identical zero-network cache repeat.
M08 remains UNCHECKED pending this genuine acceptance. The M04
verification runs in another chat; no M04 code, state or quota was
changed. M09 and later milestones remain untouched.
