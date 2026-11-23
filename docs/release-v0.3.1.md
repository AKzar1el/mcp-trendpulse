# TrendPulse v0.3.1 - RSS integrity and cache safety patch

This patch release batches four protected-main fixes merged after v0.3.0
(PRs #413, #414, #416, and #417) and includes the already merged
container V3-exclusion safeguard from PR #412.

## Fixes

- Google News article URLs must contain a valid article identifier; reject
  missing identifiers and nested/noncanonical path suffixes.
- Reject empty URL-fragment delimiters as well as nonempty fragments instead
  of treating them as canonical evidence URLs.
- Treat inconsistent cached RSS status/row combinations as invalid cache
  entries, rather than returning potentially misleading cached evidence.
- Keep V3 experimental code and review documents out of both public Docker
  build contexts, with built-image verification in the hosted and stdio
  container workflows.

## Compatibility and security

- Python >=3.11.5 remains required (patched Soup Sieve 4.x dependency).
- Preserve the existing 16 public Community tools, plus the separately
  opt-in read-only V2 intelligence tools. No change to external source
  budgets, consent requirements, or default network behavior.
- The V3 Wikidata/OSV pilot is **not released**, not in the public PyPI
  wheel/sdist, not in Docker image contexts, not registered as a hosted or
  default MCP tool, and still requires separate rights and independent
  human-workflow review before any later release.
- This patch does not activate a public hosted endpoint or remove its
  Clerk OAuth, Host/Origin allowlist, TLS and browser sandbox gates.

## Release validation

The release must pass exact-head Python CI, Ruff, package build and
installed-wheel smoke, both Docker image smokes including V3 exclusion,
and the fail-closed `scripts/check_public_distribution.py` artifact gate.
The tag must match the synchronized package, registry and plugin versions.
PyPI and MCP Registry publication are separately confirmed after the
GitHub release pipeline. No GHCR image push is automatically authorized
by this Python patch release.

Previous release notes: `docs/release-v0.3.0.md`.
