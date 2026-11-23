# Devpost winner opportunity validation — 23 November 2026

**Decision:** Select one actionable SaaS, software platform or GitHub project for an independently validated prototype. This is a research prioritization, NOT evidence of product-market fit, technical readiness, revenue or market size.

Original entries: [ShadowMCP](https://devpost.com/software/shadowmcp), [Fire Drill](https://devpost.com/software/fire-drill), [AccountableAI](https://devpost.com/software/accountableai), [PermitPike](https://devpost.com/software/permitpike).

## Live TrendPulse evidence

Codexify God v5 reached TrendPulse's 35-tool V3/MJAU source. Its existing free-source hunter ran **8 bounded live GitHub-issues and OpenAlex queries** across four niche seeds over a 90-day lookback.

| Topic | Observed evidence | Interpretation |
| --- | --- | --- |
| MCP security | No relevant latest-title hit in small sample | Unknown, not zero demand |
| Invoice fraud | Only an unrelated internal-implementation issue survived lexical match; excluded from quality evidence | No verified buyer signal |
| Property management | One dated GitHub issue about property/unit/tenant association | Feature work, not proof of paying vendor-audit buyers |
| Electrical permits | No relevant latest-title hit in small sample | Unknown, not zero demand |

The property-operations issue is [fixflow-property-ops #5](https://github.com/Bao992/fixflow-property-ops/issues/5), dated 2026-11-23. It does not substantiate AccountableAI's specific vendor-payment audit market.

Google Trends 12-month US comparisons for agent security and invoice-fraud phrases returned **provider_rate_limited**; no search-volume or growth figure can be reported. The property-management and permitting categories were not successfully measured by Google Trends in this pass.

TrendPulse's 90-day headline-only Google News searches returned up to 12 rows for AI-agent security, up to 12 for invoice/AP fraud, 4 for property-vendor payment audit, and up to 12 for permitting. **These are returned search-result counts under caps, not attention-volume or buyer-demand measurements.** Their original publisher articles were not independently read through this flow.

OpenSSF Scorecard offered no published score for the three requested GitHub repositories (ShadowMCP, Fire Drill, AccountableAI). PermitPike received no network call after the local request budget was exhausted. **No score is unknown, not proof of an insecure repo.**

## ShadowMCP — narrow developer-security testing

Official: [Devpost](https://devpost.com/software/shadowmcp), [GitHub](https://github.com/XaiverTLN/ShadowMCP), [root MIT license](https://github.com/XaiverTLN/ShadowMCP/blob/main/LICENSE) observed.

- Target problem: untrusted AI tool invocation and agent permissions.
- Competitive problem: [MCP Shield](https://github.com/Alex2006boecboec/MCP_Gateway) already offers tool-call filtering, injection detection, approvals and audit logs. [IBM ContextForge](https://github.com/IBM/mcp-context-forge) overlaps; a [third-party index](https://agentsecurityindex.com/category/mcp-security/) enumerated 17 gateway/scanner offerings as of 2026-11-09 (its chosen scope, not entire addressable market).
- **Testable differentiated idea:** a lightweight attack-replay / policy-regression test suite for existing gateways instead of another generic gateway. This is a hypothesis, not a buyer request.
- Next check: in a disposable isolated test environment, benchmark 20 permitted/blocked actions and 20 prompt-injection attempts against at least one incumbent. Record false positives and bypasses. Talk to five real agent/MCP maintainers about recurring pains and actual alternative tooling.

## Fire Drill — specialized agent red-team harness

Official: [Devpost](https://devpost.com/software/fire-drill), [GitHub](https://github.com/shokhabbos-mukhammatov/calhacks13).

- Target problem: invoice-paying AI agents can approve misleading or fraudulent payment instructions.
- Existing market: [AppZen](https://www.appzen.com/) markets AI agent testing and monitoring for accounts payable and expenses; direct overlap needs a feature-by-feature comparison.
- No root conventional LICENSE or LICENSE.md located in our initial GitHub check; **do not copy or commercially reuse code without permission**.
- **Testable idea:** an original open-source red-team harness using only fictional invoices and a test ledger. Execute at least 20 scenarios; measure harmful approvals, false alarms and repeatability. Do not send real money or call live payment accounts.

## AccountableAI — property vendor-payment oversight

Official: [Devpost](https://devpost.com/software/accountableai), [GitHub](https://github.com/ozr0013/AccountableAI), [root MIT license](https://github.com/ozr0013/AccountableAI/blob/main/LICENSE) observed.

- Target problem: owners need evidence that intermediary property managers pay actual contractors and vendors correctly.
- Competitive alternative: [AppFolio](https://www.appfolio.com/pricing) includes property accounting, automated reconciliation and automated invoice processing. Current public Core pricing starts at **USD 1.49 per unit per month**, with minimums. That price is for a **larger full management platform** and does NOT measure willingness to pay for independent vendor auditing.
- **Testable idea:** an independent read-only audit/report with explicit source references and false-positive controls, only using consented anonymized transactions. Interview five property investors/auditors about last actual loss/cost and whether they would pay in addition to existing software.

## PermitPike — one-city contractor permitting

Official: [Devpost](https://devpost.com/software/permitpike), [GitHub](https://github.com/njsaxena/PermitPike), [root MIT license](https://github.com/njsaxena/PermitPike/blob/main/LICENSE) observed.

- Target problem: complex localized electrical permit rules, document requirements and application status.
- Competitive alternative: [Cloudpermit](https://cloudpermit.com/products/building-permitting) provides online building permitting for municipalities/applicants and integrations. This does NOT imply direct parity with a contractor-specific pre-submission checklist.
- **Testable idea:** one-city permit-precheck workflow against published requirements and clearly marked human approval. Test 50 real published forms for completeness and rule-update frequency. Interview five local contractors on current cost and willingness to pay. Don't claim government approval or legal compliance.

## Provisional order for practical investigation

1. ShadowMCP-adjacent open-source testing utility: lowest operational overhead, highly crowded market.
2. Fire Drill-adjacent sandbox test harness: interesting differentiation, enterprise trust and licensing blockers.
3. AccountableAI-adjacent owner-side audit: identifiable B2B buyer hypothesis, but difficult integrations and incumbent overlap.
4. PermitPike-adjacent single-jurisdiction precheck: clear repeatable operational workflow, costly regulatory and dataset upkeep.

This is **not a market or success-probability ranking**. No paid pilot, customer interview, independently run upstream demo or measured operating-cost benchmark was completed. These remain hard build gates.

## Engineering gap and implementation

TrendPulse already has an 18-lane free-source opportunity evaluator; rebuilding it would be redundant. The missing narrow capability was structured **Devpost award, demo, license, competitor-price, functional-test and buyer-commitment evidence review** alongside existing macro evidence.

Added an isolated read-only MCP tool called **intelligence_review_devpost_candidates** to the optional intelligence MCP. It accepts at most 20 Devpost entries and 200 dated evidence records, validates public HTTPS URLs and source shapes, screens secrets, keeps rate-limit and unavailable sources UNKNOWN, warns about conflicting/stale evidence, and provides missing-evidence follow-ups. It never scrapes Devpost or makes network requests. Every caller-supplied citation remains explicitly **unverified by the tool**, including paid-pilot claims. It never predicts revenue, TAM or startup success.

Sample input: docs/examples/devpost-four-candidate-evidence-2026-11-23.json.example (15 sourced/unavailable observations across the four candidates). The sample file contains ordinary JSON; the .example suffix ensures it is not hidden by the repo's blanket *.json gitignore. Evidence kinds and statuses are in src/mcp_trendpulse/intelligence_hackathon.py. No paid API, new credentials, background worker, browser crawler, or changes to the original 16-tool community surface.

All modifications are in the **Codexify managed detached development worktree**, not an automatic release, production deployment or main-branch update.
