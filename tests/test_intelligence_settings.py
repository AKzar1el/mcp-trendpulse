"""No-network tests for optional free-provider settings and Windows-native store."""

import pytest

from mcp_trendpulse import intelligence_settings as settings
from mcp_trendpulse.intelligence_core import plan_source


def test_settings_are_read_only_and_redact_key_material():
    key = "SECRET_DO_NOT_LEAK_456"
    values = {"TRENDPULSE_INTEL_OPENALEX_KEY": key}
    rows = settings.provider_status(env=values)
    text = repr(rows)
    assert key not in text
    assert len(rows) == len(settings.PROVIDERS)
    assert next(row for row in rows if row["provider"] == "openalex")[
        "ready_for_live_auth_test"
    ]
    assert not next(row for row in rows if row["provider"] == "epo")[
        "ready_for_live_auth_test"
    ]
    guidance = settings.setup_instructions("openalex")
    assert "set-key openalex" in guidance["windows_command"]
    assert key not in repr(guidance)
    assert guidance["credential_optional_for_basic_queries"] is True
    assert next(row for row in rows if row["provider"] == "openalex")[
        "keyless_basic_queries_available"
    ] is True


def test_explicit_env_disables_native_key_lookup(monkeypatch):
    monkeypatch.setattr(settings, "_supports_native_store", lambda: True)
    def forbidden(_):
        raise AssertionError("Explicit env override must not read native secrets")
    monkeypatch.setattr(settings, "_read_secret", forbidden)
    assert settings.resolved_environment({}) == {}
    no_key = plan_source("openalex", keyword="aeronautics", env={})
    assert no_key.headers == {}
    assert no_key.budget_per_day == 20


def test_native_credentials_are_a_fallback_to_env(monkeypatch):
    monkeypatch.setattr(settings, "_supports_native_store", lambda: True)
    monkeypatch.setattr(settings, "_read_secret", lambda _: "NATIVE_ONLY_TEST_VALUE")
    monkeypatch.setenv("TRENDPULSE_INTEL_OPENALEX_KEY", "ENV_WINS_TEST")
    result = settings.resolved_environment()
    assert result["TRENDPULSE_INTEL_OPENALEX_KEY"] == "ENV_WINS_TEST"


def test_secure_provider_save_remove_without_real_windows_api(monkeypatch):
    store = {}
    monkeypatch.setattr(settings, "_supports_native_store", lambda: True)
    monkeypatch.setattr(settings, "_read_secret", lambda name: store.get(name))
    monkeypatch.setattr(settings, "_write_secret", lambda name, value: store.__setitem__(name, value))
    monkeypatch.setattr(settings, "_delete_secret", lambda name: store.pop(name, None))
    values = {
        "TRENDPULSE_INTEL_EPO_CONSUMER_KEY": "test-key",
        "TRENDPULSE_INTEL_EPO_CONSUMER_SECRET": "test-secret",
    }
    settings.save_provider_credentials("epo", values)
    assert store == values
    settings.clear_provider_credentials("epo")
    assert store == {}


def test_native_key_save_rolls_back_after_partial_write(monkeypatch):
    store = {"TRENDPULSE_INTEL_EPO_CONSUMER_KEY": "prior-key"}
    monkeypatch.setattr(settings, "_supports_native_store", lambda: True)
    monkeypatch.setattr(settings, "_read_secret", lambda name: store.get(name))
    def write(name, value):
        if name == "TRENDPULSE_INTEL_EPO_CONSUMER_SECRET":
            raise OSError("Simulated OS credential refusal")
        store[name] = value
    monkeypatch.setattr(settings, "_write_secret", write)
    monkeypatch.setattr(settings, "_delete_secret", lambda name: store.pop(name, None))
    with pytest.raises(OSError, match="refusal"):
        settings.save_provider_credentials("epo", {
            "TRENDPULSE_INTEL_EPO_CONSUMER_KEY": "new-key",
            "TRENDPULSE_INTEL_EPO_CONSUMER_SECRET": "new-secret",
        })
    assert store == {"TRENDPULSE_INTEL_EPO_CONSUMER_KEY": "prior-key"}


@pytest.mark.parametrize("field", ["UNKNOWN_KEY", "../.secret", ""])
def test_unknown_credential_field_rejected(field):
    with pytest.raises(ValueError):
        settings._field(field)


def test_non_windows_storage_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "_supports_native_store", lambda: False)
    with pytest.raises(settings.SecureStoreUnavailable):
        settings.save_provider_credentials(
            "openalex", {"TRENDPULSE_INTEL_OPENALEX_KEY": "test"}
        )
