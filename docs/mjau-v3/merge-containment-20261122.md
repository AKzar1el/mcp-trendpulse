# MJAU v3 A04/A10 - repository integration and release containment

**Date:** 2026-11-22. **PR:** https://github.com/AKzar1el/mcp-trendpulse/pull/382

## Authorization and exact scope

The repository owner explicitly requested that the technical work be integrated into `main`, reviewed for coherence, and that the completed PR branch and task-owned local worktrees be cleaned up. This **authorizes a source-code merge**, not automatic production registration, third-party licensing signoff, or public/commercial bulk-data redistribution.

The integration combines the existing V1/V2 `main` work, based on remote commit `db3d9abf1a0bacc4c08a5e06d8bb60ebd56b1c19`, with the standalone opt-in V3 A04/A10 work through PR head `8a55a10a8f71c43fd9ed1382d428f9672eb65a1a`. The merge was conflict-free; it preserves `src/mcp_trendpulse/mjau_v2` and adds `src/mcp_trendpulse/mjau_v3`. Relative to current `main`, the proposed combined tree does **not** change the existing CLI, default/hosted MCP entrypoint, schedule, dependencies, V1/V2 code, or worker registry. The 16 live TrendPulse tools must remain unchanged until explicitly authorized for release.

### Technical acceptance

- Mainline-merged V1/V2/V3 + relevant docs test matrix: **1,320 passed, 3 integration tests separated**, using the existing Python 3.13.5 environment without installing packages.
- All **3/3** real separate-process stdio and guarded HTTP MCP integration tests **passed** in 83.46 seconds on the combined V1/V2/V3 tree (nine unrelated test cases deselected).
- Previous fifth-pass source-contract QA: **16/16** passed; official Wikidata Q64 and OSV lodash 4.17.11 one-request live-source probes returned expected, explicitly qualified answers. Temporary cache replays were hits with no second network request. All fifth-pass evidence is at `docs/mjau-v3/fifth-pass-wide-qa-20261122.md`.
- The PR must pass its *new exact-head* GitHub Python and container smoke workflows after integration; previous-head CI alone does not prove current-main compatibility.

## External-source rights and safety boundary

- Wikidata main namespace structured data is **CC0**, confirmed by https://www.wikidata.org/wiki/Wikidata:Licensing . Bounded entity labels/aliases, explicit QIDs and source links only; never automatically establish identity.
- OSV's project maintainer said hosted OSV API requests by commercial services are operationally acceptable, but explicitly warned that underlying source-data licensing remains determined by the original publishers: https://github.com/google/osv.dev/issues/6264 . The original feed tables (https://google.github.io/osv.dev/data/) are heterogeneous. Therefore, **no blanket commercial redistribution permission is claimed**.
- The only supported OSV output in this module remains **factual ID/modified date/source URL**, from exactly one npm or PyPI package/version via official `/v1/querybatch`. There is no full advisory prose, detailed exploit material, arbitrary original links, default auto-fix, automatic retries, or claim that absence of indexed records means a package is secure. Explicit license-source references, CC BY caveat, transformation notice, and `commercial_bulk_redistribution_approved=False` remain in the results.
- No upstream legal advice, per-record original-feed verification or independent human end-user review has been obtained. The packet `docs/mjau-v3/independent-review-packet-20261122.md` remains unsigned. **Do not claim or record such approval as completed.**

## Deployment and rollout boundary

A repository code merge **is not** a production launch. The only executable V3 tools are the separate, manually started `python -m mcp_trendpulse.mjau_v3.mcp` adjunct with **`execute=False` by default**, one fixed-origin opt-in request only when `execute=True`, persistent UTC daily budgets **8 Wikidata / 10 OSV**, 8-second source timeouts, 192,000-byte maximum responses, and validated projected-metadata-only caches.

**Do not register, publish, enable, schedule or expose V3 through the existing hosted/live MCP service or claim public/commercial source-data distribution approved based on this merge.** Require distinct external-human workflow review, source-specific rights assessment for the intended use, and explicit deployment approval before that later rollout.

This document records the exact narrower repository-integration decision and does not retrospectively convert earlier assistant self-reviews into independent approvals.
