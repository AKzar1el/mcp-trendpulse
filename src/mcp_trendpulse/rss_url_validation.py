"""Strict, provider-shaped URL validation for Google News RSS evidence."""

import re
from urllib.parse import urlsplit


_ARTICLE_PATH = re.compile(r"/rss/articles/[A-Za-z0-9_-]{1,4096}={0,2}/?")


def is_google_news_rss_url(value: object) -> bool:
    """Return whether value has the canonical Google News RSS article URL shape."""
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    if any(
        character.isspace() or ord(character) < 32 or ord(character) == 127
        for character in value
    ):
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname == "news.google.com"
        and parsed.username is None
        and parsed.password is None
        and port in (None, 443)
        and _ARTICLE_PATH.fullmatch(parsed.path) is not None
        and not parsed.fragment
    )
