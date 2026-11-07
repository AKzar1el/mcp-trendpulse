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


async def test_get_trends_preserves_hourly_timestamps_and_utc_offset():
    times = pd.date_range("2026-11-04", periods=3, freq="h", tz="UTC")
    frame = pd.DataFrame({"python": [10.0, 20.0, 30.0]}, index=times)

    with patch.object(news.tr, "interest_over_time", return_value=frame):
        points = await news.get_trends("python", timeframe="now 1-d")

    assert [point["date"] for point in points] == [timestamp.isoformat() for timestamp in times]
    assert len({point["date"] for point in points}) == 3


async def test_get_trends_preserves_legacy_date_only_daily_labels():
    dates = pd.date_range("2026-10-01", periods=3, freq="D", tz="UTC")
    frame = pd.DataFrame({"python": [10.0, 20.0, 30.0]}, index=dates)

    with patch.object(news.tr, "interest_over_time", return_value=frame):
        points = await news.get_trends("python", timeframe="today 3-m")

    assert [point["date"] for point in points] == [timestamp.strftime("%Y-%m-%d") for timestamp in dates]


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


async def test_get_growth_fetches_enough_history_for_month_window():
    dates = pd.date_range(start="2025-01-05", periods=90, freq="W")
    frame = pd.DataFrame(
        {"keyword": [20.0] * 26 + [40.0] * 60 + [80.0] * 4},
        index=pd.DatetimeIndex(dates, name="time [UTC]"),
    )

    with patch.object(news.tr, "interest_over_time", return_value=frame) as request:
        result = await news.get_growth("keyword", percent_growth=["18M"], geo="US")

    request.assert_called_once_with(
        ["keyword"], timeframe="today 5-y", geo="US", gprop=""
    )
    assert "18M" in result[0]["growth"]


async def test_get_growth_uses_all_history_for_windows_over_five_years():
    dates = pd.date_range(start="2015-01-01", periods=12, freq="YS")
    frame = pd.DataFrame(
        {"keyword": [10.0] * 8 + [20.0] * 4},
        index=pd.DatetimeIndex(dates, name="time [UTC]"),
    )

    with patch.object(news.tr, "interest_over_time", return_value=frame) as request:
        await news.get_growth("keyword", percent_growth=["10Y"], geo="US")

    request.assert_called_once_with(
        ["keyword"], timeframe="all", geo="US", gprop=""
    )


async def test_get_growth_rejects_invalid_window_instead_of_mislabeling_it():
    with patch.object(news.tr, "interest_over_time") as request:
        try:
            await news.get_growth("keyword", percent_growth=["quarter"], geo="US")
        except ValueError as exc:
            assert "Invalid growth window" in str(exc)
        else:
            raise AssertionError("invalid growth window should fail")

    request.assert_not_called()


async def test_get_growth_rejects_short_observed_history():
    """Do not label 21 observed days as 3-month or 1-year growth."""
    dates = pd.date_range(start="2026-09-06", periods=4, freq="W")
    frame = pd.DataFrame(
        {"keyword": [10.0, 20.0, 30.0, 40.0]},
        index=pd.DatetimeIndex(dates, name="time [UTC]"),
    )

    with patch.object(news.tr, "interest_over_time", return_value=frame) as request:
        result = await news.get_growth(
            "keyword", percent_growth=["3M", "1Y"], geo="US"
        )

    request.assert_called_once_with(
        ["keyword"], timeframe="today 12-m", geo="US", gprop=""
    )
    assert result == [{"keyword": "keyword", "growth": {"3M": None, "1Y": None}}]


async def test_get_growth_preserves_short_valid_window_when_year_missing():
    dates = pd.date_range(start="2026-07-05", periods=15, freq="W")
    frame = pd.DataFrame(
        {"keyword": [20.0] * 4 + [40.0] * 11},
        index=pd.DatetimeIndex(dates, name="time [UTC]"),
    )

    with patch.object(news.tr, "interest_over_time", return_value=frame):
        result = await news.get_growth("keyword", percent_growth=["3M", "1Y"])

    assert result[0]["growth"]["3M"] == 100.0
    assert result[0]["growth"]["1Y"] is None


async def test_get_growth_does_not_invent_daily_growth_from_weekly_observations():
    dates = pd.date_range(start="2026-04-05", periods=24, freq="W")
    frame = pd.DataFrame({"keyword": [20.0] * 12 + [40.0] * 12}, index=dates)

    with patch.object(news.tr, "interest_over_time", return_value=frame) as request:
        result = await news.get_growth("keyword", percent_growth=["1D", "3D", "6D", "7D", "1M"])

    request.assert_called_once_with(["keyword"], timeframe="today 12-m", geo="US", gprop="")
    growth = result[0]["growth"]
    assert growth["1D"] is None
    assert growth["3D"] is None
    assert growth["6D"] is None
    assert growth["7D"] is not None
    assert growth["1M"] is not None


def test_growth_respects_monthly_bucket_alignment_and_daily_resolution():
    monthly = [
        {"keyword": "keyword", "date": stamp.date().isoformat(), "value": value}
        for stamp, value in zip(
            pd.date_range("2025-01-01", periods=12, freq="MS"),
            [20.0] * 6 + [40.0] * 6,
        )
    ]
    monthly_growth = news._growth_from_trend_points(monthly, ["keyword"], ["7D", "1M"])[0]["growth"]
    assert monthly_growth["7D"] is None
    assert monthly_growth["1M"] is not None

    daily = [
        {"keyword": "keyword", "date": stamp.date().isoformat(), "value": value}
        for stamp, value in zip(
            pd.date_range("2026-10-01", periods=20, freq="D"),
            [20.0] * 10 + [40.0] * 10,
        )
    ]
    daily_growth = news._growth_from_trend_points(daily, ["keyword"], ["1D", "3D"])[0]["growth"]
    assert daily_growth["1D"] is not None
    assert daily_growth["3D"] is not None


def test_growth_single_timestamp_has_no_observed_change_to_measure():
    points = [{"keyword": "keyword", "date": "2026-11-01", "value": 40.0}]
    growth = news._growth_from_trend_points(points, ["keyword"], ["1D", "1Y"])
    assert growth == [{"keyword": "keyword", "growth": {"1D": None, "1Y": None}}]


def test_growth_deduplicates_timestamps_without_double_counting_samples():
    dates = pd.date_range("2026-07-05", periods=16, freq="W")
    points = [
        {"keyword": "keyword", "date": stamp.isoformat(), "value": 20.0 if idx < 8 else 40.0}
        for idx, stamp in enumerate(dates)
    ]
    duplicate_points = points + [dict(points[8]), dict(points[-1])]

    expected = news._growth_from_trend_points(points, ["keyword"], ["1M", "3M"])
    actual = news._growth_from_trend_points(duplicate_points, ["keyword"], ["1M", "3M"])

    assert actual == expected
