"""Provider-dependent tests must distinguish a skip from a genuine bug."""
import importlib.util
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError
from mcp_trendpulse.errors import ProviderRateLimitError, ProviderUnavailableError

path = Path(__file__).parent / "integration" / "conftest.py"
spec = importlib.util.spec_from_file_location("trendpulse_live_source_guard", path)
guard = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(guard)


def test_typed_google_rate_limit_is_classified_but_other_provider_is_not():
    exc = ProviderRateLimitError("google_trends", "interest_over_time")
    assert guard._classified_external_failure(exc, "google_trends") == "provider_rate_limited"
    assert guard._classified_external_failure(exc, "google_news") is None


def test_wrapped_google_provider_downtime_classified_only_when_exact():
    exc = ToolError('Error calling tool: {"code":"provider_unavailable",'
                    '"provider":"google_trends","retryable":true}')
    assert guard._classified_external_failure(exc, "google_trends") == "provider_unavailable"
    assert guard._classified_external_failure(exc, "google_news") is None
    assert guard._classified_external_failure(
        ToolError('Unsupported news topic: CATS'), "google_trends"
    ) is None


def test_does_not_mask_input_errors_or_nonretryable_backend_failures():
    assert guard._classified_external_failure(
        ValueError("invalid source input"), "google_trends"
    ) is None
    assert guard._classified_external_failure(
        ProviderUnavailableError("google_news", "headlines"), "google_trends"
    ) is None
    assert guard._classified_external_failure(
        ToolError('Bad request: {"code":"provider_unavailable",'
                  '"provider":"google_trends","retryable":false}'), "google_trends"
    ) is None
    assert guard._classified_external_failure(
        ToolError('Bad request: {"code":"invalid_params",'
                  '"provider":"google_trends","retryable":true}'), "google_trends"
    ) is None


def test_fixture_explicitly_skips_only_classified_upstream_failure():
    source_guard = guard.external_source_available.__wrapped__()
    with pytest.raises(pytest.skip.Exception, match="availability not proven"):
        with source_guard("google_trends"):
            raise ProviderRateLimitError("google_trends", "interest_over_time")
    with pytest.raises(ToolError, match="Unsupported news topic"):
        with source_guard("google_trends"):
            raise ToolError("Unsupported news topic: CATS")
