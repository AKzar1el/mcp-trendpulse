import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import load_dotenv


logger = logging.getLogger(__name__)
DEFAULT_GOOGLE_TRENDS_DELAY = 2.0
DEFAULT_BROWSER_SANDBOX = False
DEFAULT_HTTP_PATH = "/mcp"
DEFAULT_HTTP_ALLOWED_HOSTS = ("127.0.0.1:*", "localhost:*", "[::1]:*")
DEFAULT_HTTP_ALLOWED_ORIGINS = (
    "http://127.0.0.1:*",
    "http://localhost:*",
    "http://[::1]:*",
)
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})


@dataclass(frozen=True)
class RemoteHttpSettings:
    """Configuration for the dedicated remote Streamable HTTP entry point."""

    path: str
    allowed_hosts: tuple[str, ...]
    allowed_origins: tuple[str, ...]


def load_environment() -> None:
    """Load local .env values for command-line/server entry points."""
    load_dotenv()


def get_google_trends_delay(env: Mapping[str, str] | None = None) -> float:
    """Read the TrendSpy request delay without caching environment state."""
    source = os.environ if env is None else env
    raw_value = source.get("GOOGLE_TRENDS_DELAY", str(DEFAULT_GOOGLE_TRENDS_DELAY))
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid GOOGLE_TRENDS_DELAY environment variable %r; using default %.1f",
            raw_value,
            DEFAULT_GOOGLE_TRENDS_DELAY,
        )
        return DEFAULT_GOOGLE_TRENDS_DELAY


def get_browser_sandbox_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Return whether Playwright should explicitly enable Chromium sandboxing."""
    source = os.environ if env is None else env
    raw_value = source.get("TRENDPULSE_BROWSER_SANDBOX")
    if raw_value is None:
        return DEFAULT_BROWSER_SANDBOX

    normalized = raw_value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False

    logger.warning(
        "Invalid TRENDPULSE_BROWSER_SANDBOX value %r; using default %s",
        raw_value,
        DEFAULT_BROWSER_SANDBOX,
    )
    return DEFAULT_BROWSER_SANDBOX


def _comma_separated_values(raw_value: str) -> tuple[str, ...]:
    return tuple(value.strip() for value in raw_value.split(",") if value.strip())


def _normalize_http_path(raw_path: str) -> str:
    path = raw_path.strip()
    if not path.startswith("/"):
        raise ValueError("TRENDPULSE_HTTP_PATH must start with '/'.")
    if path != "/":
        path = path.rstrip("/")
    return path


def get_remote_http_settings(env: Mapping[str, str] | None = None) -> RemoteHttpSettings:
    """Read fail-closed settings for the remote Streamable HTTP entry point."""
    source = os.environ if env is None else env
    path = _normalize_http_path(source.get("TRENDPULSE_HTTP_PATH", DEFAULT_HTTP_PATH))

    allowed_hosts = _comma_separated_values(
        source.get("TRENDPULSE_HTTP_ALLOWED_HOSTS", ",".join(DEFAULT_HTTP_ALLOWED_HOSTS))
    )
    if not allowed_hosts:
        raise ValueError("TRENDPULSE_HTTP_ALLOWED_HOSTS must contain at least one host.")

    allowed_origins = _comma_separated_values(
        source.get(
            "TRENDPULSE_HTTP_ALLOWED_ORIGINS",
            ",".join(DEFAULT_HTTP_ALLOWED_ORIGINS),
        )
    )

    return RemoteHttpSettings(
        path=path,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )
