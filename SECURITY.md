# Security Policy

## Supported versions

Security fixes target the latest published TrendPulse release. If you can reproduce an issue only on an older release, upgrade first and confirm whether the issue still exists.

TrendPulse requires Python 3.11 or newer. Python 3.10 reached end-of-life on October 1, 2026, and Pillow 13 (which fixes critical image-decoder vulnerabilities) does not support Python 3.10. We therefore no longer claim support for Python 3.10 installations or resolve Pillow 12.3.0 for that runtime. Upgrade the Python interpreter before upgrading TrendPulse; the existing published versions may remain installable but are not security-maintained on Python 3.10.

## Reporting a vulnerability

Please do not open a public GitHub issue for an undisclosed security vulnerability.

Report vulnerabilities privately by emailing `info@tomiseregi.si` with `TrendPulse security` in the subject. Include the affected version, a concise impact description, reproduction steps or a proof of concept when safe, and any suggested mitigation.

If GitHub private vulnerability reporting is enabled for the repository, you may instead use the repository's **Security** tab and **Report a vulnerability** form.

Please avoid including live credentials, API keys, private user data, or other unnecessary sensitive material in a report. There is no guaranteed response SLA, but reports will be reviewed as promptly as practical.

## Scope

Good-faith reports about the TrendPulse source code, published Python package, container/runtime configuration, MCP transport, or repository-controlled deployment assets are in scope.

Third-party upstream services, websites, APIs, and client applications are outside TrendPulse's control. Report vulnerabilities in those systems to their respective maintainers unless the issue is caused by TrendPulse's handling of them.
