# TrendPulse agent operating note

## Google Trends availability is normally constrained

Google Trends calls made through the community TrendSpy/unofficial integration are **best-effort and frequently subject to upstream throttling or unavailable responses**. This is a known external limitation, **not by itself a TrendPulse bug or an incident that needs repeated escalation**. Google's effective quotas and reset times are not guaranteed or established by this project.

- Treat `provider_rate_limited`, `provider_cooldown`, `provider_timeout`, and `provider_unavailable` as honest, bounded outcomes when the local error-handling contract works. Do **not** infer zero searches, weak demand, a broken MCP installation, or a guaranteed retry time.
- The Trending Now RSS methods and the separate 24-hour ranked Trends/Explore/interest endpoints can behave differently. RSS success does **not** imply all other Google Trends endpoints are available.
- Respect existing pacing, cache, cooldowns, and daily budgets. Do **not** add aggressive retries, proxy rotation, scraping workarounds, new accounts, quota bypasses, or paid access to hide expected upstream limits.
- Investigate only a **verified local regression** (unexpected tool errors/raw exceptions, bad validation, broken cache, incorrect source attribution, changed behavior on deterministic fixtures, or unexpected tool health). Keep genuine sustained upstream incidents distinguishable from ordinary throttling.
- Where appropriate, use available RSS, existing cached observations, and independent public sources, with their own provenance and comparability caveats. Do not silently substitute one source as equivalent to another.

Canonical details and operational triage: [docs/operations.md](docs/operations.md) ("Standing Google Trends availability expectation"). Existing Explore-specific caps: [docs/google-trends-explore.md](docs/google-trends-explore.md).
