"""Focused unit tests for useful Google Trends windows and categories."""

from unittest.mock import patch

import pandas as pd

from mcp_trendpulse import news


async def test_get_trends_forwards_explicit_timeframe_and_category():
    dates = pd.date_range(start="2025-08-03", periods=2, freq="W")
    frame = pd.DataFrame(
        {"technical seo audit": [20.0, 40.0]},
        index=pd.DatetimeIndex(dates, name="time [UTC]"),
    )

    with patch.object(news.tr, "interest_over_time", return_value=frame) as request:
        result = await news.get_trends(
            "technical seo audit", geo="US", timeframe="today 12-m", cat=5
        )

    assert result[-1]["value"] == 40.0
    request.assert_called_once_with(
        ["technical seo audit"],
        timeframe="today 12-m",
        geo="US",
        cat=5,
        gprop="",
    )


async def test_get_trends_preserves_legacy_data_mode_when_timeframe_is_omitted():
    dates = pd.date_range(start="2021-01-01", periods=1, freq="YS")
    frame = pd.DataFrame(
        {"python": [10.0]}, index=pd.DatetimeIndex(dates, name="time [UTC]")
    )

    with patch.object(news.tr, "interest_over_time", return_value=frame) as request:
        await news.get_trends("python", data_mode="monthly")

    request.assert_called_once_with(
        ["python"], timeframe="all", geo="US", cat=0, gprop=""
    )
