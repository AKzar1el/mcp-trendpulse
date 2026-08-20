"""Live Google Trends provider smoke tests.

Run explicitly with: ``uv run pytest tests/integration -m integration``.
"""

import pytest

from mcp_trendpulse.news import (
    get_growth,
    get_ranked_trends,
    get_top_trends,
    get_trends,
)


pytestmark = pytest.mark.integration


async def test_get_trends_returns_historical_data() -> None:
    trends = await get_trends(
        keyword="artificial intelligence",
        source="google search",
        data_mode="weekly",
    )

    assert isinstance(trends, list)
    assert all({"date", "value", "keyword"} <= point.keys() for point in trends)


async def test_get_growth_returns_metrics() -> None:
    growth = await get_growth(
        keyword="electric vehicles",
        source="google search",
        percent_growth=["3M", "1Y"],
    )

    assert isinstance(growth, list)
    assert all({"keyword", "growth"} <= item.keys() for item in growth)


async def test_get_ranked_trends_returns_rankings() -> None:
    ranked = await get_ranked_trends(source="google search", sort="wow_pct_change", limit=5)

    assert isinstance(ranked, list)
    assert len(ranked) <= 5
    assert all({"keyword", "volume", "growth_pct", "started", "news"} <= item.keys() for item in ranked)


async def test_get_top_trends_returns_top_trends() -> None:
    top_trends = await get_top_trends(type="Google Trends", limit=5)

    assert isinstance(top_trends, list)
    assert len(top_trends) <= 5
    assert all({"keyword", "volume", "link", "started", "picture", "news"} <= item.keys() for item in top_trends)
