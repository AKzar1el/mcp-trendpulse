import logging
import re

import pytest
from starlette.testclient import TestClient

from mcp_trendpulse.asgi import REMOTE_SERVICE_NAME, create_app
from mcp_trendpulse.config import (
    DEFAULT_HTTP_ALLOWED_HOSTS,
    DEFAULT_HTTP_ALLOWED_ORIGINS,
    DEFAULT_HTTP_PATH,
    RemoteAuthSettings,
    RemoteHttpSettings,
    get_remote_http_settings,
)


REQUEST_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


def remote_settings() -> RemoteHttpSettings:
    return RemoteHttpSettings(
        path="/mcp",
        allowed_hosts=("allowed.test",),
        allowed_origins=("https://allowed.test",),
    )


def disabled_auth_settings() -> RemoteAuthSettings:
    return RemoteAuthSettings(mode="disabled")


def test_remote_http_settings_are_fail_closed_and_normalized():
    defaults = get_remote_http_settings({})
    assert defaults.path == DEFAULT_HTTP_PATH
    assert defaults.allowed_hosts == DEFAULT_HTTP_ALLOWED_HOSTS
    assert defaults.allowed_origins == DEFAULT_HTTP_ALLOWED_ORIGINS

    custom = get_remote_http_settings(
        {
            "TRENDPULSE_HTTP_PATH": "/remote/mcp/",
            "TRENDPULSE_HTTP_ALLOWED_HOSTS": "trendpulse.example.com, trendpulse.example.com:*",
            "TRENDPULSE_HTTP_ALLOWED_ORIGINS": "https://digestseo.com, https://app.digestseo.com",
        }
    )
    assert custom.path == "/remote/mcp"
    assert custom.allowed_hosts == (
        "trendpulse.example.com",
        "trendpulse.example.com:*",
    )
    assert custom.allowed_origins == (
        "https://digestseo.com",
        "https://app.digestseo.com",
    )

    with pytest.raises(ValueError, match="must start"):
        get_remote_http_settings({"TRENDPULSE_HTTP_PATH": "mcp"})

    with pytest.raises(ValueError, match="at least one host"):
        get_remote_http_settings({"TRENDPULSE_HTTP_ALLOWED_HOSTS": " , "})


def test_health_and_readiness_endpoints_have_unique_server_request_ids():
    app = create_app(remote_settings(), disabled_auth_settings())
    with TestClient(app, base_url="http://allowed.test") as client:
        health = client.get("/health")
        ready = client.get("/ready")

    assert health.status_code == 200
    assert health.json() == {"status": "ok", "service": REMOTE_SERVICE_NAME}
    assert ready.status_code == 200
    assert ready.json() == {
        "status": "ready",
        "service": REMOTE_SERVICE_NAME,
        "transport": "streamable-http",
        "stateless": True,
        "auth": "disabled",
    }

    health_request_id = health.headers["x-request-id"]
    ready_request_id = ready.headers["x-request-id"]
    assert REQUEST_ID_PATTERN.fullmatch(health_request_id)
    assert REQUEST_ID_PATTERN.fullmatch(ready_request_id)
    assert health_request_id != ready_request_id


def test_remote_mcp_rejects_invalid_host_origin_and_content_type():
    app = create_app(remote_settings(), disabled_auth_settings())
    with TestClient(app, base_url="http://allowed.test") as client:
        invalid_host = client.post(
            "/mcp",
            content="{}",
            headers={"host": "evil.test", "content-type": "application/json"},
        )
        invalid_origin = client.post(
            "/mcp",
            content="{}",
            headers={
                "host": "allowed.test",
                "origin": "https://evil.test",
                "content-type": "application/json",
            },
        )
        invalid_content_type = client.post(
            "/mcp",
            content="{}",
            headers={"host": "allowed.test", "content-type": "text/plain"},
        )

    assert invalid_host.status_code == 421
    assert invalid_origin.status_code == 403
    assert invalid_content_type.status_code == 400
    assert REQUEST_ID_PATTERN.fullmatch(invalid_host.headers["x-request-id"])
    assert REQUEST_ID_PATTERN.fullmatch(invalid_origin.headers["x-request-id"])
    assert REQUEST_ID_PATTERN.fullmatch(invalid_content_type.headers["x-request-id"])


def test_mcp_http_log_is_bounded_and_does_not_log_request_body(caplog):
    app = create_app(remote_settings(), disabled_auth_settings())
    secret = "do-not-log-this-keyword-or-token"

    with caplog.at_level(logging.INFO, logger="mcp_trendpulse.asgi"):
        with TestClient(app, base_url="http://allowed.test") as client:
            response = client.post(
                "/mcp",
                content=secret,
                headers={"host": "allowed.test", "content-type": "text/plain"},
            )

    assert response.status_code == 400
    records = [record.getMessage() for record in caplog.records if "mcp_http_request" in record.getMessage()]
    assert len(records) == 1
    log_line = records[0]
    assert f"request_id={response.headers['x-request-id']}" in log_line
    assert "method=POST" in log_line
    assert "status=400" in log_line
    assert "auth=disabled" in log_line
    assert "duration_ms=" in log_line
    assert secret not in log_line


def test_remote_mcp_is_stateless_and_sampling_disabled():
    app = create_app(remote_settings(), disabled_auth_settings())
    mcp_route = next(
        route
        for route in app.inner_app.routes
        if getattr(route, "path", None) == "/mcp"
    )

    assert mcp_route.methods == {"POST", "DELETE"}
    assert app.inner_app.state.trendpulse_sampling_enabled is False
    assert app.inner_app.state.trendpulse_auth_settings.mode == "disabled"
