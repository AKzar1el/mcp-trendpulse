# TrendPulse desktop extension

This MCPB wrapper targets the published `mcp-trendpulse==0.3.1` PyPI distribution, not the moving main branch. It is packaged using MCPB 0.4's UV runtime with an exact dependency lock. The client must support UV-based MCPB extensions and download locked dependencies from PyPI on first install. The published wheel hash is recorded in uv.lock.

From this directory: `uv sync --locked`, then `uv run --locked src/server.py` for stdio. To pack: `npx --yes @anthropic-ai/mcpb@2.1.2 pack . ../trendpulse-0.3.1.mcpb` in a clean copy containing only manifest.json, icon.png, LICENSE, PRIVACY.md, pyproject.toml, uv.lock and src/server.py. Do not include .venv, credentials or local caches.

Validated on Windows with Python 3.13.5: official manifest validation, extracted archive offline locked installation, published package version, normal UV-launch initialization, exact 16-tool manifest match through the locked virtual environment, read-only annotations and invalid argument rejection. No live provider requests or sampling during this qualification. Claude Desktop GUI and macOS have not been tested.

This wrapper does not change provider behavior. See PRIVACY.md and the upstream README for external requests, local operation and provider limitations. No API key or paid Claude subscription is required by this wrapper; the user's client and any external service have their own requirements.