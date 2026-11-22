# MJAU v3 A10 — OSV advisory evidence pilot

**Decision: BLOCKED; official source and temporary v1-cache replay proved, independent utility/no-signal/license review incomplete. Not accepted for release.**

**Pinned v1 staging ancestor:** `b88b0a974b5dcdb480e4fd8c4da5f7bbca68e98e` (draft v1 PR #328). Independent A10 branch with no shared edits and no dependency on the A04 or Stage 0 PRs. No protected, production or central registration changed.

## Distinct decision value versus v1

V1 exposes npm/PyPI package download histories and public GitHub issue text, but not authoritative package/version-linked vulnerability advisories. A10 could answer *“Has the official OSV aggregator indexed an advisory for this exact package/version?”* without mistaking popularity, discussion or downloads for a security finding. This does **not** establish vulnerability exploitation, urgency, remediation correctness, buyer demand or safety when no advisory is returned.

## Official source policy and limits

- [OSV official API](https://google.github.io/osv.dev/api/): free public API and currently no global rate limit; an open public service does **not** authorize high-volume probing. Proposed local plan is **one query**, explicit execution through existing v1 budgets/caching, 8-second timeout, max 192 KB response, no retry/paging by default.
- [POST v1/query](https://google.github.io/osv.dev/post-v1-query/): exact `package.name`, `package.ecosystem`, `version`. OSV notes version matching may be fuzzy for some registries; do not compute or assert precise dependency version ranges locally. The API can return `next_page_token`; results must be labeled incomplete until reviewed.
- [GET v1/vulns/{id}](https://google.github.io/osv.dev/api/): exact original advisory ID. One known public example from the official [OSV-2020-744 advisory page](https://osv.dev/vulnerability/OSV-2020-744), last inspected 2026-11-21, has **published** `2020-07-04T00:00:01Z`, **modified** `2022-04-13T03:04:39Z`, and reports OSS-Fuzz mruby evidence.
- [OSV source license guidance](https://google.github.io/osv.dev/data/new/rest-api): original feeds supply their own license links (e.g., CC BY or CC0); do not treat all aggregated advisory bodies as globally CC0 or unrestricted for commercial redistribution. This pilot stores only IDs, dates, a few public URL references and status labels, not advisory details or full feeds. Licensing for broad distribution remains **blocked pending per-source audit**.

## Implemented in isolated A10-only files

- `plan_package_query(PyPI|npm, exact_name, exact_version)` constructs one fixed-origin JSON POST body, no transport invocation.
- `plan_advisory_lookup(known_id)` constructs a single fixed-origin GET URL.
- `parse_package_query(...)` validates response envelope, duplicates, size, ID, dates, paging, withdrawals and source attribution. Empty `vulns` is *no indexed advisory returned for this specific query*, never *safe software*.
- `parse_advisory_lookup(...)` validates identity match for an already fetched advisory object.
- `parse_http_result(...)` fails closed for 401/403/429/503/302 without automatic retries or leaking returned error bodies.
- No direct HTTP client, automatic remediation, purl/version range arithmetic, new dependency, auto polling, production security reports, or extra public MCP tools.

## Test results and measured observations

On Python 3.13.5 sandbox:

    PYTHONPATH=src python -m pytest -q tests/test_mjau_v3_osv.py
    PYTHONPATH=src python -m compileall -q src/mcp_trendpulse/mjau_v3 tests/test_mjau_v3_*.py

**A10 45 deterministic tests passed; total v3 sandbox 121/121 tests passed.** Negative cases cover malformed/empty/error envelopes, duplicate IDs, missing/wrong dates, withdrawn advisories, HTTP errors, pagination without silent completeness, oversized payloads, and private/credential-looking links. The OSV-2020-744 test includes **manually reviewed public page timestamps**; the rest of the response payload is synthetic. **No real OSV JSON API call or real MCP process was executed.**

300-run single-process offline microbenchmark (one plan+response parsing+ID lookup each): median **0.1305 ms**, p95 **0.2038 ms**, peak traced allocation **22,521 bytes**, JSON result **808 bytes**, requests **0**, API cost **$0**. This is not an 8-GB-Windows operational benchmark or measured improvement over v1.

## Decision, outstanding proof gates, rollback

**BLOCKED** pending one genuinely free, bounded OSV package/version request and one known advisory-ID request through approved existing v1 cache/budget, validated zero-network replay, a side-by-side real v1 vs A10 security research task with independent ground truth (including adversarial non-vulnerable/no-result examples), provider-missingness review, actual upstream feed license decisions, and full repository regression/official MCP checks. No claim of **ACCEPT** or utility uplift is warranted.

When connectivity returns, use the existing v1 staging test environment, avoid shared mutable cache/quotas, and do not add an auto worker. Revert only A10 module, test and doc in this draft branch to roll back; no production state or old workers are affected. If real incremental value fails, **DISCARD** rather than ship.

## 2026-11-21 live-source and Windows cache-replay follow-up

**Exact code under test:** `b9b0053f64ed2f4da7aa79a3d10877e1842cbfb1` (A10 Ruff fix included). A10 original 45/45 targeted tests and independent GitHub Python 3.11–3.14 CI, Ruff and two container jobs passed. The original "no JSON API request" paragraph above describes the original pilot, **not** this later source test.

- **Official OSV POST** `https://api.osv.dev/v1/query` with `{"package":{"name":"Jinja2","ecosystem":"PyPI"},"version":"2.10.1"}`: HTTP **200**, first response **27,088 bytes**, **10** source-indexed advisory IDs, no next page. First-run SHA-256 `c70dbc02f1ec901f2afb0d3068e352a8e3d2e6ae9d309a9551abafd0ac77e547` at **2026-11-21T05:08:12Z**; a later separately fetched source response also reported ten entries but hashed `7d0f3d92559a617c2e42c1ebce5e89df7ad42399d879bb0c87ea08c8b170b6a5`. Do not treat source bytes as immutable; preserve source time and ID.
- **Official OSV GET** `https://api.osv.dev/v1/vulns/OSV-2020-744`: HTTP **200**, 947 bytes, SHA-256 `e7a2228addd9927419da678e0bc79d12964fe54584f7e00241417a48a8cfee69` at **2026-11-21T05:08:12Z**. Parsed ID `OSV-2020-744`, source-published `2020-07-04T00:00:01.948828Z`, modified `2022-04-13T03:04:39.780694Z`; dates are historical advisory metadata, **not** proof of current exploitation.
- One additional bounded OSV POST for real PyPI `idna==3.10` also returned indexed advisories; **this is NOT a zero-advisory negative case** (the later `six` negative is recorded separately below). Subsequent tests used an independent temporary `BudgetCache` from v1 with cap **3** (two source queries and one advisory lookup), no redirects, 8-second timeout, 192 KB per response, one successful fetch per plan, second invocation with network explicitly denied, and verified cap enforcement. **60 cached reads:** p50 **4.992 ms**, p95 **9.815 ms** on Windows. SQLite temp directory cleaned after `gc.collect()`. Three free requests, $0 API cost, no persistent source storage or worker.
- **v1 comparator:** `plan_source("osv_public_api")` explicitly raises `IntelligenceError: Unknown source ID`; v1's package downloads and GitHub issue counts cannot answer the exact package/version advisory question. A10 returns real OSV advisory identities and dates and never equates them to demand, proof of exploitation, or safe software. This is a source-coverage gain on a small observed task, not blinded predictive or ROI uplift.

**Gate update:** the original live-source and v1 cache-replay blockers are now **PASSED**. **A10 remains BLOCKED** for release acceptance because independently reviewed no-advisory/no-signal cases, source/feed license reuse rights, robust real-workflow utility comparison and official B08 conformance remain unresolved. Raw advisory bodies were neither committed nor bulk persisted; only small IDs/dates/links are projected. No dependency, shared CLI/MCP registration or production state changed. Rollback remains A10-only.

## Real OSV no-advisory case: surgical correctness repair (same day)

**New source-backed negative observation:** the official `POST /v1/query` for real `PyPI six==1.16.0` returned HTTP **200** with the exact JSON bytes `{}` and SHA-256 `44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a` at **2026-11-21T05:28:54Z**. This is a genuine *no indexed advisory returned for the queried version*, **not** independent proof the distribution is safe or that its version exists in every registry mirror.

The prior A10 parser rejected every bare `{}` envelope as malformed. Changed only `src/mcp_trendpulse/mjau_v3/osv.py` to accept **exactly** the empty JSON object as the provider's empty-result shape, while continuing to reject nonempty malformed structures, errors, bad dates, duplicates, oversize responses and non-200 statuses. It emits `status=no_returned_advisories`, `advisory_count_in_this_response=0`, and `no_advisory_not_equivalent_to_safe_package=true`. Verified by a **second** independent real HTTP 200 response after patch, with the same SHA-256 and the corrected output. No retries, vendor authentication or permanent polling.

Retained only the **two-byte original source response** as `tests/fixtures/mjau_v3/osv_six_1_16_0_empty_20261121.json` and updated the A10-only deterministic tests. Windows Python 3.13.5: **52/52 focused tests passed**, Ruff and compileall passed. The positive source-derived fixture remains *projected metadata*, not redistributable full advisory bodies. This repairs a real negative-case false error and reduces no-signal confusion relative to the initial pilot; it is **not** a safety/vulnerability prediction or a blinded business utility win.

**Decision unchanged: BLOCKED for release** pending independent source/feed reuse review, broader evaluated real tasks and official B08 conformance. The experiment can be reverted as an A10-only commit; shared v1/v2 and production remain untouched.

## 2026-11-21 upstream attribution review — narrowed factual IDs only

OSV.dev aggregates *heterogeneously licensed* upstream data, rather than granting a single global license. Its [official data-source list](https://google.github.io/osv.dev/data/) identifies **GitHub Advisory Database** and **PyPI Advisory Database** as **CC BY 4.0** sources; it also includes feeds with different terms, including sources requiring noncommercial or no-derivatives restrictions. Its [new-data-source guidance](https://google.github.io/osv.dev/data/new) distinguishes OSV's public aggregation from each original publisher's terms. An OSV API response is **not** a blanket right to redistribute every vulnerability record or advisory body.

Surgical A10-only change: for `GHSA-` IDs emit an **upstream-database attribution hint** of `GitHub Advisory Database via OSV.dev`; for `PYSEC-` IDs emit `PyPI Advisory Database via OSV.dev`. Each carries the `CC-BY-4.0` **hint**, [license URL](https://creativecommons.org/licenses/by/4.0/) and [official original-source license index](https://google.github.io/osv.dev/data/), plus `source_specific_license_review_required=true` and `raw_advisory_redistribution_authorized=false`. These are **prefix-based suggestions requiring per-record verification**, not a definitive legal determination. Unmapped `CVE-` and `OSV-` IDs retain `null` publisher/license hints and require explicit source review. In particular, the `OSV-2020-744` prefix alone cannot be used to assign every `OSV-` record the OSS-Fuzz license.

Existing source-derived 10-record `Jinja2==2.10.1` sample includes only `GHSA-` and `PYSEC-` IDs. Three new deterministic tests cover both known prefix families and unknown prefixes; the saved real-source metadata fixture checks the recorded families independently. **55/55 targeted Windows pytest tests passed; Ruff and compileall clean.** No original advisory summaries, descriptions, raw feed files, authentication data or license text were redistributed.

**A10 remains BLOCKED for release**, because CC BY requires appropriate source attribution and any modifications notice in downstream presentation, while any other advisory family still needs a per-record original-source license audit. Neither a prefix hint nor this isolated parser establishes the final reuse permission or independent buyer/research workflow uplift. No production registration, service change, permanent cache, deployment or merge. Rollback is this A10-only attribution commit.

## 2026-11-21 adversarial URL parsing repair — drop malformed reference, retain advisory

The unmodified A10 adapter was tested with a syntactically invalid advisory reference URL `https://example.org:notaport/report`. Python's `urlsplit()` accepted the URL string, but accessing `url.port` raised `ValueError: Port could not be cast to integer`. That exception discarded **the entire valid advisory envelope** instead of dropping just one bad reference. This is a genuine parser robustness bug reproduced with a bounded synthetic negative case; it is **not** a claim that the public OSV API returned this malformed URL.

**Surgical A10-only repair:** catch `ValueError` when reading `url.port`, return `None` for that unsafe reference, and continue projecting the original advisory ID/dates/status. The existing HTTPS, public-host, credential-looking-query and allowed-port guards remain in place. A new regression mixes invalid text ports, out-of-range ports, invalid IPv6 and a nonstandard port with one safe HTTPS port 443 reference. The advisory remains visible, and the single safe link survives; malformed links are not redistributed.

**Windows evidence:** `PYTHONPATH=src python -m pytest -q tests/test_mjau_v3_osv.py tests/test_mjau_v3_osv_snapshot.py` yielded **56/56 passed**, Ruff and compileall passed. Neither new provider fetches nor extra services were required. Source-specific upstream license review and independent utility still gate A10 release, and B08 official conformance is separately unproved. This isolated robustness fix is only in the draft A10 PR and carries no main/production migration.
