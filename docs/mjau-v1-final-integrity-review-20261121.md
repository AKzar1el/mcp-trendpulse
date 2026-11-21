# MJAU V1 final evidence-integrity review (2026-11-21)

Scope: surgical release correction to optional M14 research reporting and GHCR publishing. No production MCP tool registration, worker schedule, credential, paid source, model integration or v3 file was changed.

## Four defects reproduced in independent PR #328 review

1. **Chronology:** Rising queries were possible when a measurement period ended after its recorded observation time. Source-attested query reports now refuse incomplete/future-dated batches, for both Google and Bing.
2. **Source-reference safety:** A literal LF in a source URL could break text reporting; legacy hex/octal/dword IPv4 host notations could be mistaken for safe DNS names. The shared typed source contract now rejects controls, unsafe ports, numeric IP disguises, private/reserved IP addresses and local suffixes *without any DNS or outbound HTTP*. Both report ingestion and direct typed signal parsing share this rule.
3. **Batch isolation:** One unrelated historic observation batch could suppress a complete valid Google batch. Complete, internally consistent fourteen-day windows are now assessed *within* exact UTC observation batches, then the most recent complete window is selected. Two partial batches, even if their dates combine into 14 days, are never merged. Conflicting duplicate daily values invalidate that batch.
4. **Text visibility:** The human report now shows up to four source-specific rising query examples with the original metric unit, both date windows, percentage change and two hashed evidence IDs. The complete structured output remains available; no absolute search volume or demand is inferred.

## No automatic production publication

The legacy publish-container.yml workflow published to GHCR on any main push that touched src/**. Its login, tag-preservation and push steps are now **manual-dispatch-only**. Main pushes may still build and smoke-test the image, but cannot automatically publish SHA, latest or semantic version GHCR tags. A guarded offline regression test checks those three explicit publication conditions. Deliberate future publication requires a separate manual workflow dispatch.

The separate PyPI workflow already publishes only on a GitHub Release event; no release is created or authorized in this pass.

## Verification receipt

- Original independent review: https://github.com/AKzar1el/mcp-trendpulse/pull/328#issuecomment-7064276309
- Staged in one detached temporary worktree on **V1 head 876957a874e4bc81c0470095254b5a6b0b189397**, leaving the original checkout and active workers unchanged.
- Focused source-contract and research-report tests: **105 passed**; Ruff clean.
- Full local offline v1 suite using existing Python environment: **2,236 passed, 10 deselected, 3 warnings**, ~98 seconds; Ruff clean.
- No live provider requests, auth tokens, GitHub Actions reruns or production deployment were needed for local verification.

**Release gates still pending at this document's creation:** safe virtual merge with newer main, latest-head protected CI checks after a reviewed push, draft-to-ready approval and server-side merge enforcement. None of the local results alone constitute a successful production merge, and the separate MJAU v3 research remains untouched.
