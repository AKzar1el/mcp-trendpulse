# MJAU M11 — Stack Exchange public question evidence

M11 adds one bounded, **keyless and read-only Stack Exchange API v2.3**
source, limited to public Stack Overflow technology questions. It is a
community discussion signal, **not** search query popularity, market
size, a new product opportunity, verified technical failures or
counted paying customers. A question can be answered without having
an accepted answer, and a lack of accepted answers does not mean the
underlying technical problem is unsolved in the real world.

Official endpoint and policy:

- https://api.stackexchange.com/docs/advanced-search
- https://api.stackexchange.com/docs/throttle
- https://api.stackexchange.com/docs/paging
- https://api.stackexchange.com/docs/error-handling

## Safe CLI

Without --execute, this is a pure preview: no network or quota store
is accessed.

    uv run --locked mcp-trendpulse-cli intelligence stackexchange-questions --tag python --term timeout --days 14 --limit 10 --format json

Exactly one keyless API read-only search, or validated cache repeat:

    uv run --locked mcp-trendpulse-cli intelligence stackexchange-questions --tag python --term timeout --days 14 --limit 10 --execute --format json

Use one exact lowercase Stack Overflow tag (e.g., python, typescript,
c#) and optionally a literal user-selected search phrase. The phrase
is explicitly attributed as a **manual query**, not a source-observed
keyword, measured buyer intent or semantic topic. Stack Exchange
documents that its q parameter uses an undocumented search matching
algorithm and can match question properties other than the title.
No inference of title relevance or a verified code defect is made.

The request is always to:
https://api.stackexchange.com/2.3/search/advanced

with site=stackoverflow, one tagged value, optional q, creation-date
fromdate/todate Unix seconds, order=desc, sort=creation, page=1 and
pagesize=1..10. The 7..30-day lookback has a six-hour UTC anchor, and
the source window is exposed exactly as the closed-open range. Only
one first page is fetched; even a valid page is not a census of all
questions ever posted or independently confirmed affected users.

## Source validation and ethical data handling

Every retained source record must have:

- A stable positive question_id and a matching canonical
  https://stackoverflow.com/questions/{id} provenance URL.
- A creation_date Unix timestamp inside the requested inclusive
  source-created UTC window, and the requested tag among the returned
  tags.
- Valid nonnegative answer_count; Boolean is_answered; optional
  accepted_answer_id must be positive and cannot exist without
  any answers. An answer is **not automatically an accepted answer**.
- Bounded printable decoded title and safe optional score and
  view_count. Null optionals remain unknown instead of fabricated zero.

Repeated question IDs, invalid site/link tags or out-of-window rows
are excluded and counted as rejected. The provider has_more flag
remains explicit; one page with has_more=true is observed_partial.
Even with has_more=false, the source is only the selected search
filter at that UTC snapshot. A true source empty result becomes
no_data, **not zero demand**. First-page daily
stackexchange_question_mentions TrendSignals use unit=questions,
coverage_status=partial, original API URL and source day. They are
not summed with Hacker News stories, GitHub issues or search traffic.

Raw question body, owners, user IDs, profile information, HTML
fragments, unknown provider metadata and untrusted external links are
not included in the output or validated cache. Titles are HTML
entity-decoded for readability, not executed as markup.
The report distinguishes source first-page questioned count,
distinct created days, source has_more and counts of answered,
unanswered and accepted-answer questions. Counts are examples of
public community engagement, not independent users or likely buyers.

## Free-only quotas and mandatory backoff

- Default preview never accesses the network; --execute opts into
  **one** provider operation at most, or zero for a verified cache hit.
- Uses the original SQLite BudgetCache with the dedicated source ID
  stackexchange_question_mentions and a strict local cap of
  **3 requests per UTC day**, well under the API's externally shared
  quota. No alternate cache database, quota reset, token or API key.
- An exact same query is served from a strict six-hour source-scoped
  cache with zero outbound requests. The original provider wrapper's
  quota_remaining and quota_max are retained when present.
- The Stack Exchange documentation requires clients to respect
  per-method backoff. Every valid API-provided backoff value is stored
  durably as at least its exact number of seconds, not clipped to the
  shorter generic 300-second helper. If quota_remaining is zero,
  the source is paused until the following UTC day. A 429/503 causes
  a conservative five-minute cooldown; no retry/failover/bypass.
- A malformed or error provider response is not accepted as no_data
  or measured zero. Local budget/cooldown storage failures stop
  collection. This is public API use, not HTML scraping.
- HTTPS to fixed api.stackexchange.com origin, <=128 KiB decoded
  response, 5-second connection/12-second read timeout, no redirects,
  proxies, retries, credentials, payment, or background scheduled tasks.

## Live official source acceptance — 2026-11-21 UTC

One explicit source request searched the python tag with the manual
phrase timeout, 14-day UTC lookback (snapshot window
2026-11-07T00:00:00Z through before 2026-11-21T00:00:00Z),
pagesize=10, page 1:

- Provider status observed; **1** real source question ID **80015847**.
- Exact source creation time **2026-11-10T16:22:45Z**; public link
  https://stackoverflow.com/questions/80015847 .
- Title: "Asyncio Unhandled Exception in atexit".
  The title does not contain the literal search phrase timeout;
  source free-form q may have matched other question properties.
- The question had **3** reported answers, is_answered=true,
  but **no accepted_answer_id**. This is not an unverified claim
  that the technical issue remains unresolved.
- Source wrapper: has_more=false, quota_remaining **299** of
  quota_max **300**, no backoff; there is no proof that these
  figures will stay constant or match a future IP/shared quota.
- One typed source-attributed daily stackexchange_question_mentions
  signal; zero rejected rows, one created-day observation, no
  author/body processing in the saved report.

The same exact opt-in CLI invocation immediately repeated:
cache_hit=true, requests_attempted=0, network_performed=false,
identical question ID/answer state and the preserved provider quota
metadata. Original local Stack Exchange daily budget: **1/3**
for 2026-11-21 UTC. npm remains 1/5, PyPI Stats 1/3; separate
parallel Google Trends Explore activity had reached 2/2 in its
own original quota record and was **not touched by M11**.
Original SQLite PRAGMA quick_check=ok.

The source is a single public search observation, not a recurring
problem, source-independent adoption evidence, or a commercialization
recommendation. More verification should be done cautiously through
other source families before any product idea is inferred.

Offline tests in tests/test_mjau_stackexchange.py cover tag/phrase
validation, request bounds, source IDs, duplicate/malformed questions,
distinction between answered and accepted, empty results, API errors,
source quota, full provider backoff, provider quota exhaustion,
cache integrity and HTTP transport. All work is in an independent
draft PR targeting the main MJAU staging branch; M04/M08/M09/M10
draft branches are preserved and no M12+ code is started.
