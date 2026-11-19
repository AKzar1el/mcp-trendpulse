"""Static, redacted configuration diagnostics for the local Community CLI.

No provider clients, browser sessions, shared state directories, or network
requests are initialized here. This cannot establish live provider readiness.
"""

import os
import re
from collections.abc import Mapping
from math import isfinite
from pathlib import Path

from mcp_trendpulse.config import (
    DEFAULT_GOOGLE_TRENDS_DELAY,
    get_google_news_country,
    get_google_news_language,
    get_remote_auth_settings,
    get_remote_http_settings,
)


def inspect_local_configuration(env: Mapping[str, str] | None = None) -> dict:
    """Inspect effective settings without returning private values or probing services."""
    source = os.environ if env is None else env
    issues: list[str] = []
    language = get_google_news_language(source)
    country = get_google_news_country(source)
    if not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z]{2})?", language):
        language = "(invalid)"
        issues.append("GOOGLE_NEWS_LANGUAGE must be a language code (for example, en).")
    if not re.fullmatch(r"[A-Z]{2}", country):
        country = "(invalid)"
        issues.append("GOOGLE_NEWS_COUNTRY must be a two-letter country code.")

    raw_delay = source.get("GOOGLE_TRENDS_DELAY", str(DEFAULT_GOOGLE_TRENDS_DELAY))
    try:
        delay = float(raw_delay)
        if not isfinite(delay) or delay < 0:
            raise ValueError("invalid delay")
        delay_status = "configured_unverified"
    except (TypeError, ValueError):
        delay = DEFAULT_GOOGLE_TRENDS_DELAY
        delay_status = "invalid"
        issues.append("GOOGLE_TRENDS_DELAY must be a finite non-negative number.")

    raw_shared = source.get("TRENDPULSE_SHARED_STATE_DIR", "")
    if not raw_shared:
        shared_status = "disabled"
    else:
        try:
            valid_shared_path = Path(raw_shared).expanduser().is_absolute()
        except (OSError, RuntimeError, ValueError):
            valid_shared_path = False
        if valid_shared_path:
            shared_status = "configured_unverified"
        else:
            shared_status = "invalid"
            issues.append("TRENDPULSE_SHARED_STATE_DIR must be an absolute private directory.")

    mode = source.get("TRENDPULSE_AUTH_MODE", "disabled").strip().lower()
    if mode not in ("disabled", "clerk"):
        auth = {"mode": "invalid", "status": "invalid"}
        issues.append("TRENDPULSE_AUTH_MODE must be disabled or clerk.")
    else:
        try:
            get_remote_auth_settings(source)
        except ValueError:
            auth = {"mode": mode, "status": "invalid"}
            issues.append("Hosted Clerk authentication settings are incomplete or invalid.")
        else:
            auth = {
                "mode": mode,
                "status": "local-only" if mode == "disabled" else "configured_unverified",
            }

    try:
        get_remote_http_settings(source)
    except ValueError:
        http_status = "invalid"
        issues.append("Remote HTTP path or allowed-host/origin settings are invalid.")
    else:
        override_names = (
            "TRENDPULSE_HTTP_PATH",
            "TRENDPULSE_HTTP_ALLOWED_HOSTS",
            "TRENDPULSE_HTTP_ALLOWED_ORIGINS",
        )
        http_status = (
            "configured_unverified"
            if any(name in source for name in override_names)
            else "local_loopback_defaults"
        )

    return {
        "schema_version": 1,
        "mode": "offline_configuration_only",
        "provider_reachability": "not_checked",
        "news_edition": {"language": language, "country": country},
        "trends_pacing": {"seconds": delay, "status": delay_status},
        "shared_state": {"status": shared_status},
        "proxies": {
            "http_configured": bool(source.get("HTTP_PROXY") or source.get("http_proxy")),
            "https_configured": bool(source.get("HTTPS_PROXY") or source.get("https_proxy")),
        },
        "remote_auth": auth,
        "remote_http": {"status": http_status},
        "issues": issues,
    }


def format_doctor_text(report: dict) -> str:
    """Render the safe subset of settings in a terminal-friendly report."""
    news = report["news_edition"]
    trends = report["trends_pacing"]
    proxy = report["proxies"]
    lines = [
        "TrendPulse offline configuration check (no provider requests or live checks)",
        "Provider reachability: not checked; settings do not prove a working installation.",
        f"Google News edition: {news['language']} / {news['country']}",
        f"Google Trends pacing: {trends['seconds']:g} seconds ({trends['status']})",
        f"Shared Trends state: {report['shared_state']['status']}",
        f"Proxy environment: HTTP={'set' if proxy['http_configured'] else 'unset'}, "
        f"HTTPS={'set' if proxy['https_configured'] else 'unset'} (values hidden)",
        f"Hosted authentication: {report['remote_auth']['mode']} "
        f"({report['remote_auth']['status']})",
        f"Remote HTTP configuration: {report['remote_http']['status']}",
        "Local-only authentication defaults must never be exposed as a public endpoint.",
    ]
    if report["issues"]:
        lines.append("Configuration issues:")
        lines.extend(f"- {issue}" for issue in report["issues"])
    else:
        lines.append("No static configuration issues detected; no provider availability verified.")
    return "\n".join(lines)
