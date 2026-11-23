# V3 release gate: 2026-11-23 fixed real-source comparison protocol

The user authorized further research and conservative implementation. This protocol was frozen **before** executing the new 9-scenario source-comparison run. The previous November 21-23 tests influenced the choice of categories and included some of the same software packages; this is **not a novel hidden holdout**, independent human study or randomized human productivity study.

## Release question

Does the opt-in, source-only unified 35-tool V1/V2/V3 MCP return the exact source-backed facts needed to make **unambiguous technical decisions**, as accurately as direct official provider lookup, without false safety/identity claims, and with acceptable time and third-party data exposure?

These are **machine-checkable facts from original source HTTP responses**. An independently performed human-labeling and real usability study remains a separate outside-person approval gate.

## Locked task matrix

Four Wikidata scenarios: explicit QID sets Q89/Q312 (apple fruit vs company), Q308/Q1150 (two Mercury meanings), Q64/Q30 (Berlin vs country), Q42/Q95 (unknown/missing text vs Google), selected English/Slovenian/German; each has one exact name-candidate prompt. No name-to-QID search is allowed. Five exact OSV scenarios: npm minimist 0.0.8, PyPI six 1.16.0, PyPI Django 2.2.0, npm lodash 4.17.11 and PyPI Jinja2 2.10.1. These are public, old packages with known historical advisory variation; none implies a current customer, compromise or safe status. Budget: <=4 Wikidata and <=5 OSV primary V3 calls plus <=9 direct source checks; no automatic retries.

## Objective scoring and comparators

For each scenario, **A** is the result from the actual unified stdio MCP (V3 source-only tool, execute=True) with a new isolated temporary cache. **B** is a separate, straightforward HTTP call directly to the official original provider URL using standard library, independent parser and original response. The direct truth extractor must not import TrendPulse code.

- Wikidata: compare every returned requested QID and requested-language label to the official Action API response; check any surfaced name matches against labels + projected aliases only. identity_verified=false, no auto merge. Missing names must remain unknown.
- OSV: compare *sets of factual advisory IDs* from official /v1/querybatch for the same exact ecosystem/package/version, with bounded count; verify no texts, no safety certification, no auto-remediation and source/attribution links.
- Failure: an upstream HTTP failure or mismatched current response receives **not verifiable**, never a silent zero. A dangerous false identity/safety claim is a **hard failure**.
- Output: task-level pass/abstain/fail, **no invented percentage** if provider fails. Capture first-use response time (including source call), direct original provider round-trip, MCP startup, repeated cached query time, returned bytes as serialization proxy, source side-effects, and complete tool metadata.
- The direct call is a realistic baseline for an engineer who already knows the source APIs. It may be faster than MCP for one source; explicitly disclose any such result. Any end-to-end decision or human time saved is **unmeasured** unless actual human testers record it.
- **Do not save full OSV raw advisories** or reproduce snippets, severity, exploit data or private metadata; only original ID sets and original-source HTTP result hashes/counts may be recorded as evidence. Keep ephemeral raw bytes solely in memory and delete temporary cache on exit. No external credentials or new provider billing.

## Independent human follow-up acceptance

A human who is not the implementer must receive **unlabeled** A/B output sheets and a fresh unfamiliar task they choose themselves. They must be blind to which arm is TrendPulse, assess source accuracy, friction, comprehension of caveats and time, and sign the review. A script or language model scoring its own cases may **not** sign in their place.

## Separate release gates

- Official MCP conformance: inspect which per-revision scenarios genuinely apply to a read-only tool server; if runner is unavailable do not replace official scoring with a fake green. Prefer the pinned non-alpha CLI or an audited requirement-scored version, run on localhost with Host/Origin protection, no public bind, and record inactive fixture scenarios separately.
- Wikimedia: structured data CC0; identifiable User-Agent with project contact URL; 2026 per-client rate limits (official Wikimedia API Access policy); no credential or paid access.
- OSV: heterogeneous original-feed rights, GHSA/PYSEC CC BY, CC0 and restrictive sources; minimal IDs/date/link only; no blanket commercial bulk grant, per-record true origin not established by ID prefix. Public/commercial redistribution remains a **NO-GO** pending rights/owner approval and actual independent human usability review.
- Live change: a second **optional, local** 35-tool runner may be approved only with explicit control over start/stop, verified isolation from production 33-tool source, private loopback/stdio binding, no credentials and tested rollback. Never hot-reload or silently change the existing 33-tool production source.

## Results

### Publisher terms reverified directly (2026-11-23)

- [Official Wikidata licensing](https://www.wikidata.org/wiki/Wikidata:Licensing): structured item/property data, including the bounded explicit-QID labels/aliases used here, is CC0. This is **not** a legal verification of corporate ownership/endorsement; nonstructured wiki prose and media have different rights.
- [Official Wikimedia API access policy](https://www.mediawiki.org/wiki/Wikimedia_APIs/Access_policy) and [2026 rate limits](https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits): real contact-bearing User-Agent, bounded public-source access, respect 429/Retry-After. The existing client identifies itself with a link to public GitHub issues, uses one exact GET per source batch, 8/day local quota, 1h metadata cache, no retries, no account/proxy rotation.
- [OSV original feed license table](https://google.github.io/osv.dev/data/) and [original feed policy](https://google.github.io/osv.dev/data/new): GHSA and PyPI advisory feeds are listed as CC BY 4.0, but the aggregator also has CC0, CC BY-SA, MIT/Apache and restricted sources (including Chainguard/Wolfi NC-ND terms). An OSV API response is **not** a universal original-source rights grant. The optional V3 only supports npm/PyPI exact versions, one `/v1/querybatch` request, factual IDs/modified dates and OSV links, explicit CC BY license/source index/transformation notice and **no public/commercial bulk distribution approval**.
- Per-record original feed cannot be legally certified from advisory ID prefix or the minimal querybatch response. **No legal opinion or binding rights-holder permission was obtained.** No paid access, secret package lists or raw OSV advisory texts were copied.

### Nine-source independent parser validation (observed, not a human review)

One newly isolated 35-tool stdio MCP server was queried for each fixed task, then a **different standard-library-only, original-provider HTTP client and parser** independently queried the same explicit IDs and versions. No import or reuse of TrendPulse's parsing logic occurs in that oracle. Original raw payloads existed only in memory, while the receipt stores bounded ID/count/label projections and SHA-256 hashes. Both direct-source and MCP requests made at most **four Wikidata plus five OSV calls each**, no automatic retry or paid API.

| Fixed case | Source-verifiable outcome | Interpretation |
| --- | --- | --- |
| W01 Q89 vs Q312, English/Slovenian Apple | **PASS** | Original source labels/first eight aliases, counts and exact candidate QIDs matched; no identity confirmation |
| W02 Q308 vs Q1150, Mercury | **PASS** | Both distinct original source entities preserved as possible candidates, never silently merged |
| W03 Q64 vs Q30, Berlin | **PASS** | Three-language original source labels and aliases matched; country not mislabeled as city |
| W04 Q42 vs Q95, Google | **PASS** | Missing source text not invented; Google exact QID candidate attribution preserved |
| O01 npm minimist 0.0.8 | **PASS — 2 IDs** | Exact official OSV /v1/querybatch advisory ID set |
| O02 PyPI six 1.16.0 | **PASS — 0 IDs** | Clearly `no_returned_advisories`, never a security certification |
| O03 PyPI Django 2.2.0 | **PASS — 75 IDs** | Bounded projection retained every ID from original compact source page |
| O04 npm lodash 4.17.11 | **PASS — 6 IDs** | No raw advisory descriptions, original URLs + rights warnings intact |
| O05 PyPI Jinja2 2.10.1 | **PASS — 10 IDs** | Exact source ID set and attribution/caveat contract |

**9/9 verifiable passes, 0 incorrect, 0 unverifiable in this selected test set.** This is an assistant-operated independently *coded original-source oracle*, not a random held-out human evaluation, no real paid-buyer data, and not a percentage prediction of future correctness. A negative/unknown result means precisely what the source returned, not that the underlying real-world fact is absent.

The inspectable [nine-case original-source receipt](v3-source-oracle-9task-receipt-20261123.json) records the original-response SHA-256 and byte count, source status, advisory ID sets or matched candidate QIDs, MCP/direct-call timings, and explicitly **false** human-review/public-release flags. It contains **no original advisory prose**, security severity or full third-party source-body dumps. The original provider responses can change over time, so their hashes are provenance for this observed run rather than immutable future truth.

### Actual timings: first source calls and recurring sessions

**First-call median across 9 tasks:** direct original HTTP **438.23 ms**; MCP **999.15 ms**. Direct official lookup was *faster* for single uncached queries in this run. Two repeated MCP requests from a warm source cache took **98.07 ms** (Wikidata) and **81.27 ms** (OSV), with no second upstream requests.

The first unified subprocess startup in the 9-task benchmark was a **57,987.97 ms outlier**. A separate seven-launch, zero-provider-call process check included **four** unified cold starts of **14,022.63 ms, 23,223.58 ms, 10,522.67 ms, 34,499.63 ms** (median **18,623.10 ms**), plus separate reference servers: V1 **9,090.55 ms**, V2 **4,805.57 ms**, V3 **11,170.85 ms**. This Windows host runs other workers; no causal CPU/AV source was proven. Cold start is a meaningful cost, and a persistent MCP connection avoids repeating it for every task. These small-N measurements do **not** establish human research time savings, long-term memory stability, or a service-level latency guarantee.

The earlier separate 3-round fixed plan-only A/B showed a **5.62s/41.7% median *startup-and-plan* advantage** to one combined server over three concurrently started separate servers. That advantage and these single-source disadvantages describe **different baselines**, not contradictions; neither is a valid claim of 41.7% human productivity uplift.

### Official MCP conformance and bounded local HTTP security

- The pinned, official **@modelcontextprotocol/conformance@0.1.16** CLI was installed with `npm --ignore-scripts` into a disposable QA directory; no global package mutation or service change. On a separately launched guarded `127.0.0.1` unified server, **server-initialize, tools-list, ping and tools-call-error each passed 1/1** as real official scenario checks.
- Direct guarded HTTP initialize probes returned **200** for valid local Host, **421** for malicious Host, **403** for malicious Origin, **421** when both were forged. The owned child process was verified stopped after tests. No public/remote bind, credentials or publishing.
- The v0.1.16 full active suite exited **1**: **12 check passes / 20 check failures**, mainly because this domain-specific 35-tool server does not provide the conformance harness's test-fixture image/audio/elicitation/resources/prompts examples. The unsupported operations are **not silently upgraded into green results**.
- A separate, isolated pinned **@modelcontextprotocol/conformance@0.2.0-alpha.12** runner exposed the frozen `2025-11-25` requirement set and was run against a fresh guarded local server. It exited **1** with **46 passes / 22 failures overall**; three non-scored scenarios contributed **4 passes and 2 failures**, giving **42 required check passes and 20 required check failures**. Most required scenario failures likewise expect unadvertised everything-fixture features, and this server implements neither their fixtures nor public OAuth resource-server semantics. Both runners are real official code; **NO formal revision/tier conformance certificate has been achieved.**
- Scope: supported stdio/localhost MCP interoperability and DNS-rebinding protection are confirmed. Do not add arbitrary image/audio/resource or test-only fake tools just to make a fixture-specific suite pass; do not claim conformance tier or public HTTP deployment readiness.

### Outstanding independent external approvals

The engineering source and safety checks passed **for supervised local use only**. Public commercial/bulk data redistribution remains **NO-GO** until intended-use, original-feed provenance and CC BY/other source conditions are independently reviewed and approved by an appropriate rights holder/specialist. Independent outside-human accuracy/usability grading remains **UNSIGNED**; no automated scorer can certify this in the implementer's place. The prepared reviewer packet is [v3-independent-human-review-request-20261123.md](v3-independent-human-review-request-20261123.md), and the historical older packet remains in docs/mjau-v3.

The existing 33-tool live MCP has not been changed or hot-reloaded; any eventual rollout requires separate explicit release/operations approval, matching source permissions and tested rollback. These receipts cannot override those gates.

**Final local source/package verification:** the exact 0.3.1 checkout built an offline wheel and sdist successfully. The public distribution guard passed with **75 public Python modules**, **V3 excluded** and security dependency floors intact. Installing that exact wheel into a disposable isolated target (not changing the user/worker venv) yielded **3,213 default tests passed, 1 intentionally excluded exhaustive-stress skip, 16 integration tests deselected, 3 nonfatal warnings, 0 failures**. Repo-wide Ruff passed after fixing two lint warnings in a disposable, uncommitted benchmark helper. The new guarded localhost integration was separately invoked with `-m integration` and passed **1/1**, with real subprocess startup/Host/Origin/MCP tool calls and bounded teardown. No public release or live 33-tool source registration occurred.

### Local 35-tool operating test and rollback validation

A fresh, **explicitly owned local** unified HTTP subprocess was started with the repository's guarded loopback helper, without any public bind or production credential/config changes. An original false alarm in the shutdown probe was traced to checking the socket **immediately** after terminating the venv launcher: Windows socket teardown was asynchronous. We changed only the disposable probe to poll the precise ephemeral localhost port, without killing unrelated processes.

The verified repeat passed: startup **8,116.36 ms**; valid Host HTTP 200, forged Host 421, forged Origin 403; all **35** tools visible; **30** successful read-only/catalog/plan calls plus **3** rejected invalid V1 calls; median per-call **20.33 ms**, range **18.30-29.32 ms**; **zero** provider requests, no V3 budget/cache file created. The actual serving process, PID 10416, was a child of the launched venv PID 29516. Its Windows working set was **158,736,384** before vs **162,381,824** bytes after the 30 calls (delta **3,645,440 bytes**, around 3.5 MiB). This short window is **not a memory leak or soak-test assessment**; the venv launcher itself used only ~3.5 MB and is not the correct process to measure. Server port closure completed in **753.82 ms** with two bounded polls, and neither owned PID remained running. No changes to worker browser/processes.

To retain this check for later iterations, a separate **opt-in** integration test was added at `tests/test_mjau_v3_unified_guarded_localhost.py`. It runs the same guarded actual 35-tool HTTP server, checks four-version routes and plan-only safety, malformed parameters, Host/Origin protection and bounded shutdown; it does not contact providers or allocate paid quota. It is excluded from routine `pytest` unless `-m integration` is explicitly selected. One local invocation **passed**, Ruff clean.

### Real external review tracking and final gate decisions

Two explicit, open GitHub tasks now track requirements that the implementing assistant **cannot ethically or legally self-certify**:

- [#426 — outside-human independent V3 user-accuracy and usability review](https://github.com/AKzar1el/mcp-trendpulse/issues/426): fresh tasks, blinded/alternating direct API vs MCP, verified sources, user-understood attribution/abstention, observed time-to-verified-answer, independent signature. **Reviewer not yet assigned, no signed review**.
- [#427 — determine original OSV feed provenance and distribution rights](https://github.com/AKzar1el/mcp-trendpulse/issues/427): precise intended public/commercial use; source-by-source attribution, original rights/permissions and review; do not infer license permission from GHSA/PYSEC ID prefixes. **No bulk/commercial reuse approval**.
- [#428 — diagnose highly variable unified MCP cold startup](https://github.com/AKzar1el/mcp-trendpulse/issues/428): measure a larger controlled sample and distinguish Windows process/import costs before optimizing; a persistent session already avoids paying that setup cost on every request.

**Gate verdict as of 2026-11-23:**

| Deployment/use | Decision | Grounded reason |
| --- | --- | --- |
| Explicit, supervised **local source checkout** use, with stdout/stdio and daily budgets | **Technically GO for private evaluation** | Actual 35-tool source check, direct original-source parity 9/9, guarded loopback RPC and rollback all passed; no private credentials required |
| General claim of measurable *human* productivity advantage | **NOT PROVEN** | Plan-only connection A/B benefits were observed, but direct API faster on first-use queries and no outside-human tasks were graded |
| Official frozen MCP requirement certification | **NOT CERTIFIED** | Real official runner scored 42 required checks passing and 20 failing; the server does not advertise the everything-fixture feature set |
| Hosted/public remote 35-tool service | **NO-GO** | Authentication/exposure/release review and independent owner acceptance still required; no public bind or registration performed |
| Commercial/bulk redistribution of heterogeneous OSV-derived source records | **NO-GO** | Original per-record feed rights and intended-use approvals outstanding; minimal facts alone do not create blanket permission |

These statuses are **scope-specific**, not a hidden request to automatically enable a different MCP connection. The working live 33-tool V1/V2 source must remain unchanged while unresolved external gates are open.
