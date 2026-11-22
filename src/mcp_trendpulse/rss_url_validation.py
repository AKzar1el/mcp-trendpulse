"""Strict, provider-shaped URL validation for Google News RSS evidence."""

from urllib.parse import urlsplit


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
        and parsed.path.startswith("/rss/articles/")
        and parsed.path != "/rss/articles/"
        and not parsed.fragment
    )
