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


async def test_get_trends_excludes_partial_provider_rows():
    dates = pd.date_range(start="2026-08-30", periods=3, freq="W")
    frame = pd.DataFrame(
        {
            "ChatGPT": [70.0, 78.0, 76.0],
            "isPartial": [False, False, True],
        },
        index=pd.DatetimeIndex(dates, name="time [UTC]"),
    )

    with patch.object(news.tr, "interest_over_time", return_value=frame):
        result = await news.get_trends("ChatGPT", geo="US", timeframe="today 12-m")

    assert [point["value"] for point in result] == [70.0, 78.0]
    assert result[-1]["date"] == "2026-09-06"


async def test_get_growth_excludes_partial_provider_rows():
    dates = pd.date_range(start="2025-09-14", periods=53, freq="W")
    values = [20.0] * 4 + [40.0] * 45 + [80.0, 80.0, 80.0, 1.0]
    frame = pd.DataFrame(
        {
            "keyword": values,
            "isPartial": [False] * 52 + [True],
        },
        index=pd.DatetimeIndex(dates, name="time [UTC]"),
    )

    with patch.object(news.tr, "interest_over_time", return_value=frame):
        result = await news.get_growth("keyword", percent_growth=["1Y"], geo="US")

    assert result[0]["growth"]["1Y"] == 250.0
