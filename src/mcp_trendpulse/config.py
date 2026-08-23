import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import load_dotenv


logger = logging.getLogger(__name__)
DEFAULT_GOOGLE_TRENDS_DELAY = 2.0
DEFAULT_HTTP_PATH = "/mcp"
DEFAULT_HTTP_ALLOWED_HOSTS = ("127.0.0.1:*", "localhost:*", "[::1]:*")
DEFAULT_HTTP_ALLOWED_ORIGINS = (
    "http://127.0.0.1:*",
    "http://localhost:*",
    "http://[::1]:*",
)


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
