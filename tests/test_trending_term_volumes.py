import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from mcp_trendpulse import news


@pytest.mark.parametrize(
    ("volume", "expected"),
    [
        (123, 123),
        ("123", 123),
        ("1,200", 1200),
        ("1.2K", 1200),
        ("900K", 900000),
        ("5.2M", 5200000),
        ("1B", 1000000000),
        ("500K+", 500000),
        (" 1.2k ", 1200),
        (None, -1),
        ("", -1),
        ("not a volume", -1),
        ("1.2MM", -1),
    ],
)
def test_parse_trending_volume(volume, expected):
    assert news.parse_trending_volume(volume) == expected


async def test_get_trending_terms_sorts_abbreviated_volumes_without_normalizing_output():
    trends = [
        SimpleNamespace(keyword="1B", volume="1B"),
        SimpleNamespace(keyword="5.2M", volume="5.2M"),
        SimpleNamespace(keyword="900K", volume="900K"),
        SimpleNamespace(keyword="500K+", volume="500K+"),
        SimpleNamespace(keyword="1200", volume="1200"),
    ]

    with patch.object(news.tr, "trending_now_by_rss", return_value=list(reversed(trends))):
        result = await news.get_trending_terms()

    assert [trend["volume"] for trend in result] == ["1B", "5.2M", "900K", "500K+", "1200"]


async def test_get_trending_terms_decodes_provider_keyword_html_entities():
    trends = [SimpleNamespace(keyword="mcdonald&apos;s", volume="2K+")]

    with patch.object(news.tr, "trending_now_by_rss", return_value=trends):
        result = await news.get_trending_terms()

    assert result == [{"keyword": "mcdonald's", "volume": "2K+"}]


async def test_get_trending_terms_full_data_decodes_provider_keyword_html_entities():
    trends = [SimpleNamespace(keyword="arby&apos;s", volume="200+")]

    with patch.object(news.tr, "trending_now_by_rss", return_value=trends):
        result = await news.get_trending_terms(full_data=True)

    assert result[0].keyword == "arby's"
    assert result[0] is not trends[0]
    assert trends[0].keyword == "arby&apos;s"


@pytest.mark.parametrize("full_data", [False, True])
@pytest.mark.parametrize("encoded_blank", ["&nbsp;", "&#32;", " &#x2003; "])
async def test_get_trending_terms_skips_keywords_blank_after_entity_decoding(encoded_blank, full_data):
    valid = SimpleNamespace(keyword="useful &amp; valid", volume="200+")
    malformed = SimpleNamespace(keyword=encoded_blank, volume="900+")
    with patch.object(news.tr, "trending_now_by_rss", return_value=[malformed, valid]):
        result = await news.get_trending_terms(full_data=full_data)

    if full_data:
        assert len(result) == 1
        assert result[0].keyword == "useful & valid"
        assert result[0] is not valid
    else:
        assert result == [{"keyword": "useful & valid", "volume": "200+"}]
    assert valid.keyword == "useful &amp; valid"


async def test_get_trending_terms_full_data_skips_article_titles_blank_after_entity_decoding():
    valid = SimpleNamespace(title="Meaningful &amp; verified", source="Publisher")
    blank = SimpleNamespace(title="&nbsp;", source="Publisher")
    trend = SimpleNamespace(keyword="topic", volume="500+", news=[blank, valid])
    with patch.object(news.tr, "trending_now_by_rss", return_value=[trend]):
        result = await news.get_trending_terms(full_data=True)

    assert len(result[0].news) == 1
    assert result[0].news[0].title == "Meaningful & verified"
    assert result[0].news[0] is not valid
    assert valid.title == "Meaningful &amp; verified"


async def test_get_trending_terms_full_data_decodes_nested_provider_display_text():
    article = SimpleNamespace(
        title="The &apos;90s Arby&apos;s Deal",
        source="What&apos;s on Netflix",
        snippet="Arby&apos;s fans remember it.",
    )
    trend = SimpleNamespace(
        keyword="arby&apos;s",
        volume="200+",
        picture_source="What&apos;s on Netflix",
        news=[article],
    )

    with patch.object(news.tr, "trending_now_by_rss", return_value=[trend]):
        result = await news.get_trending_terms(full_data=True)

    assert result[0].picture_source == "What's on Netflix"
    assert result[0].news[0].title == "The '90s Arby's Deal"
    assert result[0].news[0].source == "What's on Netflix"
    assert result[0].news[0].snippet == "Arby's fans remember it."
    assert article.title == "The &apos;90s Arby&apos;s Deal"
    assert trend.picture_source == "What&apos;s on Netflix"


@pytest.mark.parametrize(
    "unsafe_url",
    [
        "javascript:alert(1)",
        "data:text/html,unsafe",
        "ftp://example.com/story",
        "//example.com/story",
        "https://user:password@example.com/story",
        "https://[invalid/story",
        "https://example.com/has space",
        "https://example.com\\@evil.test/story",
    ],
)
async def test_get_trending_terms_full_data_filters_unsafe_nested_news_urls(unsafe_url):
    unsafe = SimpleNamespace(title="Unsafe story", url=unsafe_url, source="Publisher")
    valid = SimpleNamespace(title="Valid story", url="https://example.com/story", source="Publisher")
    trend = SimpleNamespace(keyword="useful trend", volume="500+", news=[unsafe, valid])

    with patch.object(news.tr, "trending_now_by_rss", return_value=[trend]):
        result = await news.get_trending_terms(full_data=True)

    assert len(result) == 1
    assert [(article.title, article.url) for article in result[0].news] == [
        ("Valid story", "https://example.com/story")
    ]
    assert trend.news == [unsafe, valid]
    assert unsafe.url == unsafe_url


@pytest.mark.parametrize(
    "unsafe_link", ["javascript:alert(1)", "ftp://bad.test", "//bad.test", "https://user:pass@bad.test"]
)
async def test_get_trending_terms_full_data_nulls_unsafe_optional_trend_links(unsafe_link):
    trend = SimpleNamespace(keyword="useful trend", volume="500+", link=unsafe_link)

    with patch.object(news.tr, "trending_now_by_rss", return_value=[trend]):
        result = await news.get_trending_terms(full_data=True)

    assert len(result) == 1
    assert result[0].link is None
    assert trend.link == unsafe_link


@pytest.mark.parametrize(
    ("picture", "expected"),
    [
        ("javascript:alert(1)", None),
        ("data:image/png;base64,AA", None),
        ("//example.com/photo.png", None),
        ("https://user:pass@example.com/photo.png", None),
        ("https://example.com/photo.png", "https://example.com/photo.png"),
    ],
)
async def test_get_trending_terms_full_data_validates_pictures_without_mutating_cache(
    picture, expected
):
    article = SimpleNamespace(title="Story", url="https://example.com/story", picture=picture)
    trend = SimpleNamespace(keyword="topic", volume="500+", picture=picture,
                            picture_source="Publisher &amp; Co", news=[article])

    with patch.object(news.tr, "trending_now_by_rss", return_value=[trend]):
        first = await news.get_trending_terms(full_data=True)
        second = await news.get_trending_terms(full_data=True)

    assert first[0].picture == second[0].picture == expected
    assert first[0].news[0].picture == second[0].news[0].picture == expected
    assert first[0].picture_source == "Publisher & Co"
    assert trend.picture == article.picture == picture


@pytest.mark.parametrize("full_data", [False, True])
async def test_get_trending_terms_does_not_mutate_reused_provider_objects(full_data):
    article = SimpleNamespace(
        title="Weather &amp;nbsp; story",
        source="Publisher &amp; Co",
        snippet="Story &amp;nbsp; summary",
    )
    trend = SimpleNamespace(
        keyword="Weather &amp;nbsp; topic",
        volume="500+",
        picture_source="Publisher &amp; Co",
        news=[article],
    )

    with patch.object(news.tr, "trending_now_by_rss", return_value=[trend]):
        first = await news.get_trending_terms(full_data=full_data)
        second = await news.get_trending_terms(full_data=full_data)

    assert trend.keyword == "Weather &amp;nbsp; topic"
    assert trend.picture_source == "Publisher &amp; Co"
    assert trend.news == [article]
    assert article.title == "Weather &amp;nbsp; story"
    assert article.source == "Publisher &amp; Co"
    assert article.snippet == "Story &amp;nbsp; summary"
    if full_data:
        assert first[0] is not trend
        assert first[0].news[0] is not article
        assert first[0].keyword == second[0].keyword == "Weather &nbsp; topic"
        assert first[0].news[0].title == second[0].news[0].title == "Weather &nbsp; story"
    else:
        assert first == second == [{"keyword": "Weather &nbsp; topic", "volume": "500+"}]


@pytest.mark.parametrize("full_data", [False, True])
async def test_get_trending_terms_ignores_malformed_nested_rss_news(full_data):
    complete = SimpleNamespace(
        title="Valid &amp; relevant", source="News &amp; Analysis", snippet="A &amp; B"
    )
    minimal = SimpleNamespace(title="Still useful")
    trend = SimpleNamespace(
        keyword="reliable topic", volume="200+",
        news=[None, {"title": "unsupported mapping"}, SimpleNamespace(url="missing title"), complete, minimal],
    )

    with patch.object(news.tr, "trending_now_by_rss", return_value=[trend]):
        result = await news.get_trending_terms(full_data=full_data)

    if not full_data:
        assert result == [{"keyword": "reliable topic", "volume": "200+"}]
    else:
        assert len(result[0].news) == 2
        assert result[0].news[0] is not complete
        assert result[0].news[0].title == "Valid & relevant"
        assert result[0].news[0].source == "News & Analysis"
        assert result[0].news[0].snippet == "A & B"
        assert result[0].news[1].source is None
        assert result[0].news[1].snippet is None
        assert complete.title == "Valid &amp; relevant"
        assert not hasattr(minimal, "source")


@pytest.mark.parametrize("news_items", [None, 42, "not a list", {"invalid": True}])
async def test_get_trending_terms_ignores_nonsequence_nested_rss_news(news_items):
    trend = SimpleNamespace(keyword="valid keyword", volume="300+", news=news_items)
    with patch.object(news.tr, "trending_now_by_rss", return_value=[trend]):
        result = await news.get_trending_terms(full_data=True)
    assert result[0].keyword == "valid keyword"
    assert result[0].news == []


@pytest.mark.parametrize("full_data", [False, True])
@pytest.mark.parametrize(
    "invalid_row",
    [
        None,
        SimpleNamespace(volume="900+"),
        SimpleNamespace(keyword=None, volume="900+"),
        SimpleNamespace(keyword=42, volume="900+"),
        SimpleNamespace(keyword="   ", volume="900+"),
        SimpleNamespace(keyword="missing volume"),
        {"keyword": "unsupported mapping", "volume": "900+"},
    ],
)
async def test_get_trending_terms_skips_malformed_root_rss_rows(invalid_row, full_data):
    first = SimpleNamespace(keyword="low", volume="100+")
    second = SimpleNamespace(keyword="high", volume="500+")
    with patch.object(news.tr, "trending_now_by_rss", return_value=[first, invalid_row, second]):
        result = await news.get_trending_terms(full_data=full_data)

    if full_data:
        assert result == [second, first]
    else:
        assert result == [
            {"keyword": "high", "volume": "500+"},
            {"keyword": "low", "volume": "100+"},
        ]


@pytest.mark.parametrize("full_data", [False, True])
@pytest.mark.parametrize(
    "malformed_payload",
    [None, {"keyword": "mapping instead of rows"}, "not RSS rows", 42],
)
async def test_get_trending_terms_handles_malformed_rss_provider_payload(
    malformed_payload, full_data, caplog
):
    with patch.object(news.tr, "trending_now_by_rss", return_value=malformed_payload):
        result = await news.get_trending_terms(full_data=full_data)

    assert result == []
    assert "unexpected" in caplog.text.lower()


@pytest.mark.parametrize("full_data", [False, True])
async def test_get_trending_terms_accepts_tuple_rss_provider_payload(full_data):
    trend = SimpleNamespace(keyword="valid topic", volume="500+")
    with patch.object(news.tr, "trending_now_by_rss", return_value=(trend,)):
        result = await news.get_trending_terms(full_data=full_data)

    assert result == ([trend] if full_data else [{"keyword": "valid topic", "volume": "500+"}])


@pytest.mark.parametrize("full_data", [False, True])
@pytest.mark.parametrize(
    "invalid_volume",
    [None, float("nan"), float("inf"), float("-inf"), 500, True, {}, [], b"500+", "", "   "],
)
async def test_get_trending_terms_skips_malformed_volume_rows(invalid_volume, full_data):
    low = SimpleNamespace(keyword="low", volume="100+")
    invalid = SimpleNamespace(keyword="invalid", volume=invalid_volume)
    high = SimpleNamespace(keyword="high", volume="500+")

    with patch.object(news.tr, "trending_now_by_rss", return_value=[low, invalid, high]):
        result = await news.get_trending_terms(full_data=full_data)

    if full_data:
        assert result == [high, low]
    else:
        assert result == [
            {"keyword": "high", "volume": "500+"},
            {"keyword": "low", "volume": "100+"},
        ]
        json.dumps(result, allow_nan=False)


def test_trending_cli_discloses_approximate_traffic(monkeypatch):
    """Trending RSS CLI must not present provider buckets as precise search counts."""
    from click.testing import CliRunner

    import mcp_trendpulse.cli as cli_module

    async def fake_trending_terms(*, geo, full_data):
        assert geo == "US"
        assert full_data is False
        return [{"keyword": "example topic", "volume": "2000+"}]

    monkeypatch.setattr(cli_module, "get_trending_terms", fake_trending_terms)
    result = CliRunner().invoke(cli_module.cli, ["trending", "--geo", "US"])
    assert result.exit_code == 0, result.output
    assert "Trending terms:" in result.output
    assert "example topic" in result.output
    assert "2000+" in result.output
    assert "approximate" in result.output.lower()
    assert "not exact" in result.output.lower()
