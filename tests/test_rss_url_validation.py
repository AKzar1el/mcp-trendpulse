"""Direct, dependency-free checks for saved Google News RSS URL shapes."""

from mcp_trendpulse.rss_url_validation import is_google_news_rss_url


def test_rejects_non_article_google_news_path_suffixes():
    for url in (
        "https://news.google.com/rss/articles/ABC123/extra",
        "https://news.google.com/rss/articles/..",
        "https://news.google.com/rss/articles/%2e%2e",
        "https://news.google.com/rss/articles/ABC123%2Fextra",
    ):
        assert not is_google_news_rss_url(url), url


def test_accepts_google_news_article_token_with_query_and_443():
    assert is_google_news_rss_url("https://news.google.com/rss/articles/CBMiABC_-==?oc=5")
    assert is_google_news_rss_url("https://news.google.com:443/rss/articles/ABC123/")
