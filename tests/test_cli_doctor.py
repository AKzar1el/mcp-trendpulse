"""Offline configuration diagnostics must be useful without leaking credentials."""

import json
import os
from unittest.mock import patch

from click.testing import CliRunner

from mcp_trendpulse import cli as cli_module


def _doctor(monkeypatch, args, env):
    monkeypatch.setattr(cli_module, "load_environment", lambda: None)
    with (
        patch.dict(os.environ, env, clear=True),
        patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("live provider invoked")),
    ):
        return CliRunner().invoke(cli_module.cli, ["doctor", *args])


def test_doctor_json_reports_defaults_without_contacting_providers(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    result = _doctor(monkeypatch, ["--format", "json"], {})
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["schema_version"] == 1
    assert data["mode"] == "offline_configuration_only"
    assert data["provider_reachability"] == "not_checked"
    assert data["news_edition"] == {"language": "en", "country": "US"}
    assert data["trends_pacing"]["seconds"] == 2.0
    assert data["shared_state"]["status"] == "disabled"
    assert data["remote_auth"]["mode"] == "disabled"
    assert data["issues"] == []
    assert list(tmp_path.iterdir()) == []


def test_doctor_strict_fails_bad_configuration_without_printing_values(monkeypatch):
    secrets = {
        "GOOGLE_TRENDS_DELAY": "private-delay-value",
        "TRENDPULSE_SHARED_STATE_DIR": "private-relative-folder",
        "TRENDPULSE_AUTH_MODE": "private-auth-value",
        "HTTP_PROXY": "http://private-user:private-pass@proxy.example:3128",
    }
    result = _doctor(monkeypatch, ["--format", "json", "--strict"], secrets)
    assert result.exit_code == 2, result.output
    data = json.loads(result.output)
    assert data["trends_pacing"]["status"] == "invalid"
    assert data["shared_state"]["status"] == "invalid"
    assert data["remote_auth"]["status"] == "invalid"
    assert data["proxies"]["http_configured"] is True
    assert len(data["issues"]) >= 3
    assert all(secret not in result.output for secret in secrets.values())
    assert "private-pass" not in result.output


def test_doctor_valid_clerk_configuration_only_is_not_claimed_reachable(monkeypatch):
    env = {
        "GOOGLE_NEWS_LANGUAGE": "de",
        "GOOGLE_NEWS_COUNTRY": "GB",
        "TRENDPULSE_AUTH_MODE": "clerk",
        "TRENDPULSE_CLERK_ISSUER": "https://issuer.example",
        "TRENDPULSE_CLERK_AUDIENCE": "private-client-id",
        "TRENDPULSE_PUBLIC_BASE_URL": "https://app.example",
        "TRENDPULSE_HTTP_ALLOWED_HOSTS": "app.example",
    }
    result = _doctor(monkeypatch, ["--format", "json", "--strict"], env)
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["news_edition"] == {"language": "de", "country": "GB"}
    assert data["remote_auth"] == {"mode": "clerk", "status": "configured_unverified"}
    assert data["provider_reachability"] == "not_checked"
    assert "private-client-id" not in result.output
    assert "issuer.example" not in result.output


def test_doctor_text_explains_local_vs_remote_and_no_live_checks(monkeypatch):
    result = _doctor(monkeypatch, [], {})
    assert result.exit_code == 0, result.output
    assert "offline" in result.output.lower()
    assert "no provider" in result.output.lower()
    assert "local-only" in result.output.lower()
    assert "Google News" in result.output
    assert "Google Trends" in result.output


def test_doctor_shared_state_path_is_redacted_and_not_created(monkeypatch, tmp_path):
    private_dir = tmp_path / "do-not-create-private-state"
    result = _doctor(monkeypatch, ["--format", "json"], {
        "TRENDPULSE_SHARED_STATE_DIR": str(private_dir),
        "HTTPS_PROXY": "https://private:password@proxy.example",
    })
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["shared_state"]["status"] == "configured_unverified"
    assert not private_dir.exists()
    assert str(private_dir) not in result.output
    assert "private:password" not in result.output


def test_doctor_invalid_news_and_hosted_settings_fail_strict_without_leak(monkeypatch):
    result = _doctor(monkeypatch, ["--format", "json", "--strict"], {
        "GOOGLE_NEWS_COUNTRY": "invalid-private-country",
        "GOOGLE_NEWS_LANGUAGE": "private-language-value",
        "TRENDPULSE_AUTH_MODE": "clerk",
        "TRENDPULSE_CLERK_ISSUER": "private-issuer",
        "TRENDPULSE_HTTP_ALLOWED_HOSTS": "",
    })
    assert result.exit_code == 2, result.output
    data = json.loads(result.output)
    assert data["news_edition"] == {"language": "(invalid)", "country": "(invalid)"}
    assert data["remote_auth"]["status"] == "invalid"
    assert data["remote_http"]["status"] == "invalid"
    assert "private-issuer" not in result.output
    assert "private-language-value" not in result.output


def test_doctor_unknown_tilde_user_is_sanitized_not_a_traceback(monkeypatch):
    result = _doctor(monkeypatch, ["--format", "json", "--strict"], {
        "TRENDPULSE_SHARED_STATE_DIR": "~trendpulse_user_does_not_exist_2026/private",
    })
    assert result.exit_code == 2, result.output
    data = json.loads(result.output)
    assert data["shared_state"]["status"] == "invalid"
    assert "trendpulse_user_does_not_exist_2026" not in result.output
