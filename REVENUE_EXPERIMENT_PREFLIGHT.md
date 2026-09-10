# TrendPulse Revenue Experiment Preflight

Status: PRELAUNCH. The seven-day experiment clock has not started.

## Authority

On 2026-09-10, Tomi Seregi approved a bounded seven-day monetization experiment for `AKzar1el/mcp-trendpulse` with the objective of producing at least one real, attributable monetary event greater than EUR 0 while improving TrendPulse only when those improvements increase the probability of that outcome or protect product/revenue reliability.

This approval supersedes the older free-only/no-monetization instruction in roadmap issue #7 only for this bounded experiment. It does not authorize unrelated products, deceptive monetization, degradation of the free Community MCP, or mutation of other repositories.

The hosted-provider authorization blocker in issue #22 remains binding. The unreleased hosted TrendPulse/ChatGPT surface must not be made a paid/public critical path unless an authorized/licensed upstream Trends and news provider basis is independently established. Community/self-hosted functionality, repo-native distribution, human-operated analysis/services, support/setup, sponsorship, and other lawful adjacent value exchanges remain eligible hypotheses.

## Canonical preflight baseline

- Preflight starting `main`: `7695595736859c49ee641d94a116e58ec9b7dcde`.
- Community package version: `0.2.11`.
- PyPI: `mcp-trendpulse==0.2.11` independently resolved and installed with `uvx`.
- Official MCP Registry: `io.github.AKzar1el/mcp-trendpulse` version `0.2.11`, active.
- GHCR: `ghcr.io/akzar1el/mcp-trendpulse` has `0.2.11`, `latest`, and immutable SHA tags.
- The stale README/agent-install statements saying PyPI was unavailable were repaired during this preflight and protected with a regression test.

## Qualification baseline

On the preflight checkout of canonical `main`:

- `uv sync --locked --dev`: PASS on Python 3.12;
- unit suite: 171 passed, 10 integration-marked tests deselected by the repository default;
- `ruff check .`: PASS;
- `uv build`: PASS;
- `twine check dist/*`: PASS;
- a fresh external `uvx --from mcp-trendpulse==0.2.11 mcp-trendpulse-cli --help`: PASS.

Docker is not installed on the current Windows host. Container correctness therefore remains independently judged by the repository's GitHub Actions container workflow rather than a local Docker invocation. Do not claim a local container pass when Docker is unavailable.

## GitHub execution and observability

Before launch, `main` was changed from unprotected to protected with:

- pull request required before merge;
- strict required status checks for Python 3.10.18, 3.11, 3.12, 3.13, 3.14, and Package validation;
- protections enforced for administrators;
- force pushes disabled;
- branch deletion disabled.

The authenticated local GitHub path can read repository traffic. Preflight 14-day snapshot:

- views: 61 total / 26 unique;
- clones: 692 total / 105 unique;
- most-viewed path: repository Overview, 33 views / 18 unique;
- observed referrers include GitHub and Glama.

PyPI download diagnostics are also reachable; the preflight snapshot reported 5 last-day, 91 last-week, and 331 last-month downloads. These are diagnostics only and must never count as revenue.

## Email and revenue evidence

`info@tomiseregi.si` is confirmed to deliver into the connected Gmail account, so source-marked inbound requests can be monitored without adding a new mailbox system.

No general bank-transaction connector is established by this preflight. Revenue SUCCESS must therefore use the strongest independently available evidence at the time: an accessible payment/provider notification, another connected authoritative payment record, or a direct human confirmation that money was actually received tied to the experiment. An inquiry, order intent, invoice, promise, click, star, clone, download, or projected value is not revenue. If payment cannot be independently established by the deadline, use UNVERIFIED rather than infer success.

## Launch orchestration requirements

The scheduled task must use durable continuation rather than treating hourly wakes as independent attempts.

- Control branch: `experiment/trendpulse-revenue-control`.
- Control state is recovery metadata only; Git, GitHub, PyPI/MCP Registry, Gmail, and other external reality are authoritative.
- Generation is the fencing token. One mutation owner at a time.
- Initial lease target: 50 minutes, with heartbeat during long work.
- A worker that deliberately checkpoints and exits must release its lease immediately instead of leaving an 80-minute lease that suppresses the next hourly wake.
- Every takeover after an expired lease must reconcile actual external state before mutation.
- PR creation, merge, release/publication, outbound email, terminal verdict, and cleanup require a fresh fencing check immediately beforehand.
- Side effects must be idempotent: verify whether they already happened before retrying.

State machine:

`PREFLIGHT -> RESEARCH -> FREEZE -> SHIP -> DISTRIBUTE -> MARKET_LOOP -> SUCCESS | TERMINAL`

`MARKET_LOOP` is active diagnosis, not passive waiting. Each authorized wake should inspect new evidence in this order where available:

1. verified revenue/payment evidence;
2. qualified inbound inquiries or replies;
3. GitHub traffic/referrers/popular paths;
4. PyPI downloads and package/registry availability;
5. Glama/MCP/passive distribution state;
6. offer exposure and conversion friction;
7. product/CI health.

If exposure is weak, improve lawful distribution. If exposure exists but the offer is not seen, improve placement. If the offer is seen but produces no inquiry, improve proposition/friction inside the frozen hypothesis. If qualified inquiries do not convert, investigate trust/scope/pricing presentation without changing the frozen offer category or success criterion. Once money is verified, preserve the proven mechanism and make only reliability/evidence fixes.

Do not stack speculative changes. Prefer one material evidence-backed commercial/conversion change at a time so later observations remain interpretable.

## Research and hypothesis freeze

The first authorized experiment run must research current market evidence and generate multiple candidate monetization hypotheses. It must choose exactly one based on willingness-to-pay evidence, fit to existing TrendPulse capabilities, seven-day revenue probability, implementation risk, external-account dependence, distribution leverage, provider/legal constraints, and preservation of the useful free Community MCP.

The experiment contract created at launch must freeze at least:

- hypothesis;
- target paying user;
- offer category/value exchange;
- price or payment terms when applicable;
- attributable source markers/payment path;
- start time;
- exact seven-day end time;
- success criterion (> EUR 0 actually attributable and received/earned);
- failure criterion;
- diagnostics that do not count as success.

After freeze, implementation/copy/placement/reliability may change based on evidence, but the hypothesis and terminal criteria may not pivot.

## Market authority

Allowed within this experiment:

- `AKzar1el/mcp-trendpulse` code/docs/metadata and isolated work branches/worktrees;
- repo description/topics and repo-native releases/discussions when justified;
- PyPI, official MCP Registry, GHCR, Glama-facing repo metadata, and other existing passive TrendPulse distribution surfaces where the change is controlled from this repository/account and truthful;
- source-marked inbound conversion paths through the existing `info@tomiseregi.si` mailbox;
- at most three total warm Gmail messages during the entire experiment, only to an existing human relationship/thread with clear prior relevance to TrendPulse/MCP/search/trend research and a credible fit for the frozen offer. Read the full thread first, obey prior opt-outs, do not create a new cold-prospect list, and independently verify each send in SENT before counting it as sent.

Not allowed:

- cold-email campaigns, mass DMs, mass posting, spam, bought traffic, fake users/testimonials/revenue, review manipulation, or impersonation;
- creation of financial accounts, changes to bank/tax/payout settings, paid ads, spending money, contracts, or new external legal/affiliate terms;
- exposing the authorization-ambiguous hosted provider path as a paid/public service;
- hidden telemetry in the Community MCP;
- degrading or paywalling the free OSS product;
- touching other repositories or their production surfaces.

## Launch gate

Do not start the seven-day clock until this preflight branch is merged through the protected `main` path, required CI is green, the post-merge `main` SHA is recorded, and the prelaunch control branch is initialized without an active lease. The first scheduled worker then starts the clock, freezes the researched hypothesis, and begins execution immediately.
