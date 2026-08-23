from mcp_trendpulse.config import get_browser_sandbox_enabled


def test_browser_sandbox_defaults_off_for_community_runtime():
    assert get_browser_sandbox_enabled({}) is False


def test_browser_sandbox_accepts_explicit_true_values():
    for value in ("1", "true", "TRUE", " yes ", "on"):
        assert get_browser_sandbox_enabled({"TRENDPULSE_BROWSER_SANDBOX": value}) is True


def test_browser_sandbox_accepts_explicit_false_values():
    for value in ("0", "false", "FALSE", " no ", "off"):
        assert get_browser_sandbox_enabled({"TRENDPULSE_BROWSER_SANDBOX": value}) is False


def test_browser_sandbox_invalid_value_falls_back_to_community_default(caplog):
    assert get_browser_sandbox_enabled({"TRENDPULSE_BROWSER_SANDBOX": "sometimes"}) is False
    assert "Invalid TRENDPULSE_BROWSER_SANDBOX" in caplog.text
