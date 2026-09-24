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
