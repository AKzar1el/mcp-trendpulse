# TrendPulse Monetization Experiment

Status: HISTORICAL LAUNCH RECORD

The original seven-day experiment below is retained as launch history. It no longer defines the current offer expiry or operational runtime authority. Current buyer-facing terms live in `DEMAND_BRIEF.md`: the one-off TrendPulse Demand Brief remains EUR 49 and the Community MCP remains free.

Experiment window: 2026-09-10 18:15 Europe/Ljubljana through 2026-09-17 18:15 Europe/Ljubljana.

Starting canonical main: `52057b39b2e260d18b2c7d038ce85a8c0cc0ba95`.

## Market evidence reviewed at launch

Current evidence supports charging for **decision-ready interpretation**, not for raw Google Trends access alone:

- Exploding Topics currently charges from $39/month for its paid trend product, with higher tiers at $99 and $249/month. Its API is materially more expensive and is sold as a Business-plan add-on. Source: https://explodingtopics.com/pricing and https://explodingtopics.com/feature/et-api (retrieved 2026-09-10).
- Treendly has a free tier and a Pro tier at $99/year, demonstrating a low-price self-serve market for trend discovery. Source: https://www.treendly.com/pricing (retrieved 2026-09-10).
- Trends MCP offers a directly competing MCP/API experience with a free tier and paid plans starting at $19/month, then $49 and $199/month. Source: https://www.trendsmcp.ai/ (retrieved 2026-09-10).
- HasData offers a hosted Google Trends MCP with OAuth/API-key access and usage-based credits, which confirms demand for agent-readable trend data while also making a raw hosted-data subscription a crowded path. Source: https://hasdata.com/mcp/google-trends (retrieved 2026-09-10).
- A low-end custom market-research provider advertises a 30+ page custom report for EUR 99, while higher-end research providers advertise quick scans starting around $500 and broader custom research from thousands of euros. Sources: https://deepinsightnow.com/ and https://elevatedsignal.com/pricing/ (retrieved 2026-09-10).
- A 2026 SaaS discussion describes the founder research problem as a choice between expensive enterprise reports and hours of fragmented manual research. This is anecdotal rather than market-size proof, but it directly matches the value of a small, fast evidence brief. Source: https://www.reddit.com/r/SaaS/comments/1q7tux0/why_is_finding_reliable_market_data_for_a_new/ (retrieved 2026-09-10).
- Google Trends remains awkward for production use in 2026: the official API is application-gated and common unofficial approaches have maintenance/rate-limit problems. This increases the value of a human-operated, bounded research deliverable without requiring TrendPulse to sell an authorization-ambiguous hosted upstream. Sources: https://crawlora.net/blog/how-to-scrape-google-trends and https://scrapebadger.com/blog/does-google-trends-have-an-api-what-to-use-in-2026 (retrieved 2026-09-10).

TrendPulse already exposes the raw capabilities needed for a useful brief: interest-over-time, growth, ranking, related queries/topics, geographic interest, suggestions, current news discovery, and article context. No new hosted product is required.

## Hypotheses considered

Scores use 1-5 where 5 is best. For implementation/risk and external-account dependence, 5 means fast/low-risk and little or no new-account dependency.

| Candidate | Willingness to pay | Existing fit | 7-day cash probability | Fast / low risk | Low external dependence | Provider / legal safety | Distribution leverage | Preserves Community MCP | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **A. EUR 49 TrendPulse Demand Brief** | 4 | 5 | 5 | 5 | 5 | 5 | 3 | 5 | **37** |
| B. EUR 149 MCP setup / integration sprint | 4 | 4 | 3 | 4 | 5 | 5 | 2 | 5 | 32 |
| C. EUR 79 paid TrendPulse troubleshooting session | 3 | 4 | 3 | 5 | 5 | 5 | 3 | 5 | 33 |
| D. EUR 199 white-label trend-research pack for agencies | 4 | 5 | 3 | 4 | 5 | 5 | 2 | 5 | 33 |
| E. GitHub Sponsors support CTA | 3 | 5 | 2 | 5 | 2 | 5 | 3 | 5 | 30 |
| F. Hosted TrendPulse subscription/API | 5 | 4 | 1 | 1 | 1 | 1 | 4 | 5 | 22 |

Candidate F is additionally disqualified for this experiment while issue #22's hosted-provider authorization constraint remains unresolved. Candidate E depends on sponsorship-account readiness that was not independently established at launch. Candidates B-D are legitimate but require a larger trust jump from a small existing audience. Candidate A offers the shortest credible path from an existing public project to a small attributable payment.

## Frozen hypothesis

**Hypothesis:** a small subset of bootstrapped SaaS founders, indie builders, SEO/content operators, and small agencies will pay a low fixed price for a rapid, human-produced TrendPulse demand brief that turns public trend and current-news signals into a concrete go/no-go or prioritization decision.

### Target paying user

A founder, indie builder, SEO/content operator, or small agency that already has a product/topic/keyword decision to make and does not want to buy a larger subscription or spend hours assembling trend evidence manually.

### Offer / value exchange

**TrendPulse Demand Brief — EUR 49 launch price.**

For one topic or decision, Tomi will produce a concise decision-ready brief covering up to five supplied keywords/phrases and up to two geographic markets. The brief will use TrendPulse's Community/self-hosted capabilities plus current public sources to provide:

1. current and historical search-interest direction;
2. relative growth/momentum and meaningful comparison caveats;
3. rising/top related queries or topics where available;
4. relevant current-news context where useful;
5. three concrete implications or next-step recommendations for the buyer's product, content, campaign, or research decision.

Delivery target: within 24 hours after payment is confirmed and the buyer supplies the topic/keywords and geography.

This is a **human-operated research service**, not resale of a hosted Google Trends API and not access to the unreleased hosted TrendPulse surface. The free Community MCP remains unchanged and fully usable.

### Price and payment terms

- Fixed launch price: **EUR 49 per brief** during this seven-day experiment.
- Scope is confirmed by email before payment.
- Payment instructions use Tomi's existing invoicing/bank-transfer arrangement; no new payment account is created for this experiment and no financial details are stored in this repository.
- Work begins after payment is confirmed.

### Attribution path

Primary CTA uses `info@tomiseregi.si` with the deterministic marker **`TP-RS1`** in the email subject or body.

Canonical inbound subject:

`TrendPulse Demand Brief [TP-RS1]`

Every repository-controlled CTA for this experiment should preserve that marker. A qualified inbound without the marker may still be attributed only if the thread contains independently verifiable evidence that the buyer came from this exact experiment.

### Success criterion

**SUCCESS** only when more than EUR 0 is actually received/earned and independently attributable to this frozen TrendPulse Demand Brief experiment before 2026-09-17 18:15 Europe/Ljubljana.

An inquiry, reply, click, star, clone, download, order intent, invoice, promise, or scheduled payment does not count as success.

### Failure criterion

**FAIL** at or after 2026-09-17 18:15 Europe/Ljubljana if no attributable money has been received and the available payment evidence is unambiguous.

Use **UNVERIFIED** instead of FAIL or SUCCESS when a material payment claim exists but actual receipt cannot be independently established.

### Non-terminal diagnostics

These may guide changes but never count as success:

- GitHub views, unique visitors, referrers, clones, stars, forks, or README-path exposure;
- PyPI/MCP Registry installs or downloads;
- Glama or other passive-directory visibility;
- clicks or `mailto:` opens when observable;
- inbound inquiries and qualified replies;
- number of briefs requested, quoted, or invoiced;
- CI/package/product health.

## Frozen fields

The following may **not pivot** during the experiment:

- the hypothesis above;
- target paying-user category;
- offer category: one-off human-produced TrendPulse demand brief;
- fixed EUR 49 experiment price;
- success criterion and failure criterion;
- experiment deadline;
- requirement for actual attributable money.

Implementation, wording, placement, examples, delivery template, reliability, and lawful distribution channels may change based on evidence as long as they remain inside this frozen offer.

## Experiment guardrails

- Do not paywall, degrade, or insert hidden telemetry into the Community MCP.
- Do not expose the authorization-ambiguous hosted TrendPulse path as a paid/public critical path.
- Do not create a new financial account, change banking/tax/payout settings, spend money, buy ads, or accept new legal/affiliate terms.
- Do not use cold-email campaigns, mass DMs/posts, spam, fake testimonials, fake buyers, or fake revenue.
- At most three total warm Gmail messages may be used, and only inside genuinely relevant existing human relationships after reading the full thread and checking for opt-outs.
- Only `AKzar1el/mcp-trendpulse` and its repository-controlled distribution surfaces may be mutated.
