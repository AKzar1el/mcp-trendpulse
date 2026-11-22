# TrendPulse v0.3.0 - security and research release

This release updates the **public default/community MCP** while preserving
the existing 16 default TrendPulse tools. It also ships the opt-in, read-only
V2 intelligence modules for advanced source-scoped research. V3's standalone
pilot (Wikidata/OSV) is deliberately **NOT** included in the published wheel
or source distribution, registered in the default MCP, or released in the
hosted service. Its separate rights and independent-human review gate remains
open.

## Compatibility / security upgrade

**Action required:** Python **3.11.5 or newer** is needed. Users of
3.11.0-3.11.4 and 3.10 must upgrade Python before installing this release.
The secure Soup Sieve 4.x line needs the updated interpreter; the resolved
build uses Soup Sieve 4.1.3 and OpenTelemetry API 1.45.2. This is a
compatibility-floor change from the previous public release.

## Changes

- Additional read-only research adapters with source and quota protections:
  software EOL/lifecycle, package dependency graphs, repository history,
  published OpenSSF Scorecard, and Hugging Face public model metadata.
- Preserved the original 16 default tools and improved Google Trends
  geography validation and provider error reporting.
- Repaired Google News RSS URL validation, rejecting noncanonical or
  off-origin links rather than treating them as trustworthy evidence.
- Fixed zero-width separator keyword collisions, potential duplicate
  free-provider reservations under concurrent calls, and source-evidence
  disclosure/consistency defects.
- Improved standalone CLI, hosted facade tests, source-neutral tool discovery,
  source-coverage documentation and reproducible MCP acceptance checks.

## Explicit limitations

- Google Trends may rate-limit external requests. Some live source tests were
  skipped rather than misreported as successful; no source bypass is used.
- Source evidence, GitHub stars and Hugging Face scores are not proof of
  product demand, vulnerability absence, or model fitness.
- The web/hosted MCP is independently deployed; a PyPI release does NOT
  automatically update its production hosting configuration.
- V3 remains blocked pending source-specific rights, independent external
  workflow review, and explicit rollout approval.

## Release safeguards

The release pipeline must enforce: lock resolution; full Python tests on
3.11-3.14; Ruff; wheel+sdist validation; standalone installed-wheel smoke;
release tag exactly matching `pyproject.toml` and `server.json`; and
`scripts/check_public_distribution.py` which refuses public V3 files.
PyPI is published through GitHub's OIDC Trusted Publishing; MCP Registry
publication follows a successful PyPI job. This file alone does not imply
either publication occurred.

Source repository: https://github.com/AKzar1el/mcp-trendpulse
