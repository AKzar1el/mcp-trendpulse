import logging
import os
from collections.abc import Mapping

from dotenv import load_dotenv


logger = logging.getLogger(__name__)
DEFAULT_GOOGLE_TRENDS_DELAY = 2.0


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
