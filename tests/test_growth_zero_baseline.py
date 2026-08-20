"""Offline tests for undefined percentage growth from a zero baseline."""

from unittest.mock import patch

import pandas as pd
import pytest
from fastmcp import Client

from mcp_trendpulse import news, server


def _growth_frame(historical_value: float, current_value: float) -> pd.DataFrame:
    dates = pd.date_range(start="2025-01-05", periods=20, freq="W")
    return pd.DataFrame(
        {"example": [historical_value] * 16 + [current_value] * 4},
        index=pd.DatetimeIndex(dates, name="time [UTC]"),
    )


@pytest.mark.parametrize(
    ("historical_value", "current_value", "expected_growth"),
    [(10.0, 20.0, 100.0), (0.0, 0.0, 0.0), (0.0, 20.0, None)],
)
async def test_get_growth_handles_zero_historical_baselines(
    historical_value, current_value, expected_growth
):
    with patch.object(
        news.tr,
        "interest_over_time",
        return_value=_growth_frame(historical_value, current_value),
    ):
        result = await news.get_growth("example", percent_growth=["3M"])

    assert result[0]["growth"]["3M"] == expected_growth


async def test_get_growth_structured_output_serializes_undefined_growth_as_null():
    with patch.object(
        news.tr, "interest_over_time", return_value=_growth_frame(0.0, 20.0)
    ):
        async with Client(server.mcp) as client:
            result = await client.call_tool(
                "get_growth", {"keyword": "example", "percent_growth": ["3M"]}
            )

    assert result.structured_content["result"][0]["growth"]["3M"] is None
    assert '"3M":null' in result.content[0].text.replace(" ", "")
