# Sample TrendPulse Demand Brief

This is a public example of the **EUR 49 TrendPulse Demand Brief**. It demonstrates the format and level of interpretation a buyer receives. It is not a client deliverable and does not contain private customer data.

Data captured: **2026-09-10**

## Decision

An AI/devtools company has one near-term content and integration sprint. Which assistant ecosystems should it prioritize for the **US and UK** based on current search-interest momentum plus recent product-news context?

## Inputs

Keywords/phrases:

1. `ChatGPT`
2. `Claude`
3. `Gemini`
4. `Perplexity`
5. `Microsoft Copilot`

Markets: **United States (`US`)** and **United Kingdom (`GB`)**.

Trend window: trailing 12 months, Google Search.

## Search-interest snapshot

TrendPulse queried the five terms together in each market. Google Trends values are normalized relative-interest indices, not absolute search volume. Values from the US query and UK query should **not** be compared directly across markets.

### United States

| Term | Latest weekly index (2026-09-06) | 3-month growth estimate | 1-year growth estimate |
| --- | ---: | ---: | ---: |
| ChatGPT | 80 | +5.35% | -20.85% |
| Gemini | 31 | +2.48% | +31.91% |
| Claude | 19 | -34.43% | +300.00% |
| Perplexity | 1 | -66.67% | -80.00% |
| Microsoft Copilot | 1 | 0.00% | 0.00% |

### United Kingdom

| Term | Latest weekly index (2026-09-06) | 3-month growth estimate | 1-year growth estimate |
| --- | ---: | ---: | ---: |
| ChatGPT | 97 | +5.00% | -1.18% |
| Gemini | 29 | -7.08% | +38.16% |
| Claude | 25 | -15.93% | +493.75% |
| Perplexity | 1 | -50.00% | -50.00% |
| Microsoft Copilot | 1 | -20.00% | 0.00% |

The growth figures are TrendPulse estimates based on normalized Google Trends series. They are directional signals rather than market-size estimates.

## What the signal suggests

### 1. ChatGPT remains the reach-first choice

ChatGPT is still the dominant exact search term in both market comparisons. Its latest index is materially above every other term, and the 3-month estimate is slightly positive in both markets.

For a single near-term content or integration sprint, ChatGPT therefore has the strongest evidence for **immediate audience reach** among these exact terms.

### 2. Gemini is the strongest second priority

Gemini is the clear second-largest exact term in both markets in the latest weekly snapshot. Its US 3-month estimate is slightly positive and its 1-year estimate is positive in both markets.

That combination makes Gemini a better second priority than simply chasing the highest percentage-growth term.

### 3. Claude is the interesting challenger, not the first reach bet

Claude shows very strong 1-year relative growth in both markets, but its 3-month estimate is negative. That is a useful distinction: **large year-over-year expansion does not automatically mean current acceleration**.

For a buyer deciding where to place one sprint, this argues for keeping Claude in the test/watch set rather than displacing ChatGPT or Gemini for broad-reach work.

### 4. Exact-term interpretation matters

`Microsoft Copilot` scores very low in this exact comparison, but many users search simply for `Copilot`. A real buyer brief would test the buyer's actual query variants rather than treat this phrase as a complete measure of Microsoft demand.

Likewise, `Claude` and `Gemini` are plain-language names as well as AI brands. Search-term analysis should be paired with topic/entity variants or additional context when ambiguity materially affects the decision.

## Current-news context

Recent official product activity shows that all three leading ecosystems are still moving quickly:

- OpenAI announced **GPT-6 Astra** in early September 2026 and continued ChatGPT product updates during the same week: https://openai.com/products/release-notes/
- Google announced **Gemini 3.8 Flash and 3.8 Flash Cyber** on 2026-09-02: https://blog.google/innovation-and-ai/models-and-research/gemini-models/3-8-flash-and-3-8-flash-cyber/
- Anthropic announced **Claude Fable 5.1** on 2026-09-01: https://www.anthropic.com/news
- Perplexity's recent changelog continued expanding its Computer/product surface in August 2026: https://www.perplexity.ai/changelog

The news layer matters because a short-lived launch or product announcement can move search interest without implying durable demand. The brief therefore uses news as context, not as a substitute for trend data.

## Three concrete implications

1. **Prioritize ChatGPT first and Gemini second** for the next broad-reach content/integration sprint in both markets.
2. **Run a smaller Claude-specific test** rather than ignoring it: its year-over-year expansion is strong enough to justify monitoring, but the recent 3-month softness argues against making it the primary reach bet today.
3. **Do not spend the remaining sprint on Perplexity or the exact phrase `Microsoft Copilot` without a narrower buyer reason.** If Microsoft is strategically important, rerun the analysis with variants such as `Copilot` and the specific Microsoft product context before deciding.

## Missing signal handled explicitly

TrendPulse's related-query provider returned a **retryable temporary upstream error** during this sample run, so related-query data is intentionally omitted rather than fabricated.

For a paid brief, that enrichment would be retried within the delivery window and supplemented with current public-source research when useful. The offer promises related queries/topics **where available**, not invented completeness.

## Method and caveats

- Google Trends indices are normalized relative-interest values, not absolute search volumes.
- Comparing five terms in one request changes the normalization scale versus querying each term separately.
- The latest weekly point can move as Google updates or resamples Trends data.
- Search terms may be ambiguous; topic/entity comparisons can be more appropriate for some brands.
- The growth estimates are directional and should not be interpreted as revenue, market share, or user-count growth.
- This sample is a decision aid, not a claim that search interest alone determines product strategy.

## Want this for your own decision?

The launch offer is **EUR 49 for one brief**, covering up to five keywords/phrases and two geographic markets, with a target turnaround within 24 hours after payment and inputs are confirmed.

See [DEMAND_BRIEF.md](DEMAND_BRIEF.md) or email **info@tomiseregi.si** with the subject **`TrendPulse Demand Brief [TP-RS1]`**.
