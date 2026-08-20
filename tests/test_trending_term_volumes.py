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
