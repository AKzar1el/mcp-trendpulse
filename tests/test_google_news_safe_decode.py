"""Offline tests for bounded, pinned Google News link decoding."""

import json
from urllib.parse import urlsplit

import pytest

from mcp_trendpulse import news
from mcp_trendpulse.google_news_safe_decode import decode_google_news_url_pinned


class _Response:
    def __init__(self, data: str, status: int = 200):
        self.data = data.encode("utf-8")
        self.status_code = status
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True

    def iter_content(self, chunk_size: int):
        assert chunk_size > 0
        for start in range(0, len(self.data), chunk_size):
            yield self.data[start : start + chunk_size]


class _Session:
    def __init__(self, get_responses: list[_Response], post_response: _Response | None = None):
        self.get_responses = iter(get_responses)
        self.post_response = post_response
        self.calls: list[tuple[str, str, dict]] = []

    def get(self, url: str, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return next(self.get_responses)

    def post(self, url: str, **kwargs):
        self.calls.append(("POST", url, kwargs))
        assert self.post_response is not None
        return self.post_response


_HTML = '<c-wiz><div jscontroller="yes" data-n-a-sg="sig-1" data-n-a-ts="123"></div></c-wiz>'
_BATCH = "\n\n" + json.dumps([
    ["wrb.fr", "Fbv4je", json.dumps(["ignored", "https://example.com/article"])],
    None, None,
])


@pytest.mark.parametrize("url", [
    "http://news.google.com/rss/articles/C123",
    "https://127.0.0.1/rss/articles/C123",
    "https://news.google.com.evil.invalid/rss/articles/C123",
    "https://evil@news.google.com/rss/articles/C123",
    "https://news.google.com:8080/rss/articles/C123",
    "https://news.google.com/rss/articles/../C123",
    "https://news.google.com/rss/articles/C123%2Fother",
    "https://news.google.com/rss/articles/C123#fragment",
])
def test_rejects_noncanonical_news_urls_before_any_http(url):
    session = _Session([])
    assert decode_google_news_url_pinned(url, session, timeout=3)["status"] is False
    assert session.calls == []


def test_decodes_using_only_fixed_google_hosts_and_bounded_no_redirect_requests():
    session = _Session([_Response(_HTML)], _Response(_BATCH))
    result = decode_google_news_url_pinned(
        "https://news.google.com/rss/articles/C123?oc=5",
        session,
        timeout=4,
        max_bytes=8192,
    )
    assert result == {"status": True, "decoded_url": "https://example.com/article"}
    assert [method for method, _, _ in session.calls] == ["GET", "POST"]
    assert all(urlsplit(url).hostname == "news.google.com" for _, url, _ in session.calls)
    assert all(kwargs["allow_redirects"] is False for _, _, kwargs in session.calls)
    assert all(kwargs["stream"] is True and kwargs["timeout"] == 4 for _, _, kwargs in session.calls)
    assert "f.req=" in session.calls[-1][2]["data"]


def test_redirects_never_follow_arbitrary_location_and_use_only_fixed_fallback():
    session = _Session([
        _Response("redirect to internal service", status=302),
        _Response(_HTML),
    ], _Response(_BATCH))
    result = decode_google_news_url_pinned(
        "https://news.google.com/rss/articles/C123", session, timeout=4,
    )
    assert result["status"] is True
    assert [method for method, _, _ in session.calls] == ["GET", "GET", "POST"]
    assert all(urlsplit(url).hostname == "news.google.com" for _, url, _ in session.calls)


def test_oversized_or_invalid_metadata_fails_closed_without_posting():
    oversized = _Session([_Response("x" * 500), _Response("x" * 500)])
    result = decode_google_news_url_pinned(
        "https://news.google.com/rss/articles/C123", oversized,
        timeout=2, max_bytes=64,
    )
    assert result["status"] is False
    assert all(method == "GET" for method, _, _ in oversized.calls)

    invalid = _Session([_Response(_HTML.replace("sig-1", "bad!sig"))])
    result = decode_google_news_url_pinned(
        "https://news.google.com/rss/articles/C123", invalid, timeout=2,
    )
    assert result["status"] is False
    assert all(method == "GET" for method, _, _ in invalid.calls)


def test_real_session_configuration_disables_ambient_proxies_and_pins_both_schemes(monkeypatch):
    def inspect(session_url, session, **kwargs):
        assert session_url == "https://news.google.com/rss/articles/C123"
        assert session.trust_env is False
        assert session.proxies == {}
        assert isinstance(session.get_adapter("https://news.google.com"), news.ArticlePinnedHTTPAdapter)
        assert isinstance(session.get_adapter("http://news.google.com"), news.ArticlePinnedHTTPAdapter)
        assert kwargs["max_bytes"] <= news.ARTICLE_MAX_HTML_BYTES
        return {"status": True, "decoded_url": "https://example.com/article"}

    monkeypatch.setattr(news, "decode_google_news_url_pinned", inspect)
    assert news.decode_url("https://news.google.com/rss/articles/C123") == "https://example.com/article"
