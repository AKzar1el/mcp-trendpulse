"""Offline validation tests for supported get_growth comparison windows."""

from unittest.mock import patch

import pandas as pd
import pytest

from mcp_trendpulse import news


@pytest.mark.parametrize(
    ("window", "expected_days"),
    [("3M", 90), ("1Y", 365)],
)
def test_parse_growth_window_accepts_supported_windows(window, expected_days):
    assert news.parse_growth_window(window) == (window, expected_days)


def test_parse_growth_window_accepts_five_year_window():
    assert news.parse_growth_window("5Y") == ("5Y", 5 * 365)


@pytest.mark.parametrize("windows", [["10Y"], ["invalid"], [""], []])
async def test_get_growth_rejects_unsupported_windows_before_requesting_trends(windows):
    with patch.object(news.tr, "interest_over_time") as request:
        with pytest.raises(ValueError):
            await news.get_growth("example", percent_growth=windows)

    request.assert_not_called()


async def test_get_growth_requests_a_five_year_timeframe_for_a_five_year_window():
    dates = pd.date_range(start="2021-01-03", periods=262, freq="W")
    frame = pd.DataFrame(
        {"example": list(range(262))},
        index=pd.DatetimeIndex(dates, name="time [UTC]"),
    )

    with patch.object(news.tr, "interest_over_time", return_value=frame) as request:
        result = await news.get_growth("example", percent_growth=["5Y"])

    request.assert_called_once_with(
        ["example"], timeframe="today 5-y", geo="US", gprop=""
    )
    assert "5Y" in result[0]["growth"]
