"""Offline regression tests for malformed Google Trends numeric observations."""

import json
from math import isfinite
from unittest.mock import patch

import pandas as pd

from mcp_trendpulse import news


async def test_trends_drop_nonfinite_points_without_discarding_valid_observations():
    frame = pd.DataFrame(
        {"python": [20.0, float("nan"), float("inf"), 40.0]},
        index=pd.date_range("2026-09-01", periods=4, freq="W"),
    )
    with patch.object(news.tr, "interest_over_time", return_value=frame):
        points = await news.get_trends("python", timeframe="today 12-m")

    assert [point["value"] for point in points] == [20.0, 40.0]
    json.dumps(points, allow_nan=False)


async def test_trends_reject_boolean_provider_values_instead_of_reporting_zero_or_one():
    dates = pd.date_range("2026-09-01", periods=3, freq="W")
    frame = pd.DataFrame({"python": pd.Series([True, 42.0, False], index=dates, dtype=object)})
    with patch.object(news.tr, "interest_over_time", return_value=frame):
        points = await news.get_trends("python", timeframe="today 12-m")

    assert [point["value"] for point in points] == [42.0]
    assert news._finite_trend_number(pd.Series([True]).iloc[0]) is None
    assert news._finite_trend_number(False) is None
    assert news._finite_trend_number(0) == 0.0


async def test_trends_omit_interest_scores_outside_provider_zero_to_hundred_scale():
    frame = pd.DataFrame(
        {"python": [-0.5, 0.0, 42.0, 100.0, 101.0]},
        index=pd.date_range("2026-09-01", periods=5, freq="W"),
    )
    with patch.object(news.tr, "interest_over_time", return_value=frame):
        points = await news.get_trends("python", timeframe="today 12-m")

    assert [point["value"] for point in points] == [0.0, 42.0, 100.0]
    json.dumps(points, allow_nan=False)


async def test_growth_ignores_nonfinite_samples_and_has_no_invalid_percentages():
    frame = pd.DataFrame(
        {"python": [20.0] * 16 + [40.0, float("nan"), float("inf"), 40.0]},
        index=pd.date_range("2026-05-03", periods=20, freq="W"),
    )
    with patch.object(news.tr, "interest_over_time", return_value=frame):
        growth = await news.get_growth("python", percent_growth=["3M"])

    value = growth[0]["growth"]["3M"]
    assert value is not None and isfinite(value)
    json.dumps(growth, allow_nan=False)


def test_growth_does_not_serialize_overflowed_calculated_percentage():
    points = [
        {"keyword": "example", "date": date.date().isoformat(), "value": 1e-300}
        for date in pd.date_range("2025-01-05", periods=16, freq="W")
    ] + [
        {"keyword": "example", "date": date.date().isoformat(), "value": 1e300}
        for date in pd.date_range("2025-04-27", periods=4, freq="W")
    ]

    growth = news._growth_from_trend_points(points, ["example"], ["3M"])
    assert growth == [{"keyword": "example", "growth": {"3M": None}}]
    json.dumps(growth, allow_nan=False)


async def test_region_discards_unusable_measurements_and_coordinates():
    frame = pd.DataFrame(
        {
            "geoName": ["California", "Texas", "Oregon"],
            "geoCode": ["US-CA", "US-TX", "US-OR"],
            "python": [float("nan"), 55.0, float("inf")],
            "lat": [36.0, float("nan"), 44.0],
            "lng": [-119.0, float("-inf"), -120.0],
        }
    )
    with patch.object(news.tr, "interest_by_region", return_value=frame):
        regions = await news.get_interest_by_region("python")

    assert regions == [{"geoName": "Texas", "geoCode": "US-TX", "values": {"python": 55.0}}]
    json.dumps(regions, allow_nan=False)


async def test_region_omits_out_of_range_interest_without_losing_valid_keywords():
    frame = pd.DataFrame(
        {
            "geoName": ["Alabama", "Alaska", "Arizona", "Arkansas"],
            "python": [-0.5, 0.0, 100.0, 101.0],
            "rust": [-1.0, 101.0, 37.0, 41.0],
        }
    )
    with patch.object(news.tr, "interest_by_region", return_value=frame):
        regions = await news.get_interest_by_region(["python", "rust"])

    assert regions == [
        {"geoName": "Alaska", "values": {"python": 0.0}},
        {"geoName": "Arizona", "values": {"python": 100.0, "rust": 37.0}},
        {"geoName": "Arkansas", "values": {"rust": 41.0}},
    ]
    json.dumps(regions, allow_nan=False)


async def test_region_skips_missing_or_invalid_names_without_losing_valid_geodata():
    frame = pd.DataFrame(
        {
            "geoName": [None, float("nan"), "  ", 123, "  California  ", "New York"],
            "geoCode": ["US-XX", "US-XX", "US-XX", "US-XX", "US-CA", "US-NY"],
            "python": [10, 20, 30, 40, 50, 60],
            "lat": [0.0, 0.0, 0.0, 0.0, 36.0, 43.0],
            "lng": [0.0, 0.0, 0.0, 0.0, -119.0, -75.0],
        }
    )
    with patch.object(news.tr, "interest_by_region", return_value=frame):
        regions = await news.get_interest_by_region("python")

    assert regions == [
        {"geoName": "California", "values": {"python": 50.0}, "geoCode": "US-CA", "lat": 36.0, "lng": -119.0},
        {"geoName": "New York", "values": {"python": 60.0}, "geoCode": "US-NY", "lat": 43.0, "lng": -75.0},
    ]
    json.dumps(regions, allow_nan=False)


async def test_region_omits_malformed_optional_geo_codes_without_losing_valid_regions():
    frame = pd.DataFrame(
        {
            "geoName": ["Alabama", "Alaska", "Arizona", "Arkansas", "California"],
            "geoCode": ["  ", 123, float("nan"), None, " US-CA "],
            "python": [10, 20, 30, 40, 50],
            "lat": [32.0, 64.0, 34.0, 35.0, 36.0],
        }
    )
    with patch.object(news.tr, "interest_by_region", return_value=frame):
        regions = await news.get_interest_by_region("python")

    assert [region["geoName"] for region in regions] == frame["geoName"].tolist()
    assert [region.get("geoCode") for region in regions] == [None, None, None, None, "US-CA"]
    assert [region["values"]["python"] for region in regions] == [10, 20, 30, 40, 50]
    assert [region["lat"] for region in regions] == [32, 64, 34, 35, 36]
    json.dumps(regions, allow_nan=False)


async def test_region_omits_out_of_range_coordinates_without_losing_interest():
    frame = pd.DataFrame(
        {
            "geoName": ["Alpine", "Pacific", "Boundary"],
            "python": [10, 20, 30],
            "lat": [91.0, -44.0, -90.0],
            "lng": [12.0, -181.0, 180.0],
        }
    )
    with patch.object(news.tr, "interest_by_region", return_value=frame):
        regions = await news.get_interest_by_region("python")

    assert regions == [
        {"geoName": "Alpine", "values": {"python": 10.0}, "lng": 12.0},
        {"geoName": "Pacific", "values": {"python": 20.0}, "lat": -44.0},
        {"geoName": "Boundary", "values": {"python": 30.0}, "lat": -90.0, "lng": 180.0},
    ]


async def test_related_queries_skip_invalid_provider_values_only():
    related = {
        "top": pd.DataFrame({"query": ["valid", "bad", "infinite"], "value": [80, float("nan"), float("inf")]}),
        "rising": pd.DataFrame({"query": ["growing", "missing"], "value": [120, None]}),
    }
    with patch.object(news, "_call_related_queries_with_unavailable_retry", return_value=related):
        rows = await news.get_related_queries("python")

    assert rows == {"top": [{"query": "valid", "value": 80.0}], "rising": [{"query": "growing", "value": 120.0}]}
    json.dumps(rows, allow_nan=False)


async def test_related_queries_preserve_breakout_as_labeled_non_numeric_signal():
    related = {
        "top": pd.DataFrame({"query": ["stable"], "value": [95]}),
        "rising": pd.DataFrame({"query": ["surging", "ordinary"], "value": ["Breakout", "350"]}),
    }
    with patch.object(news, "_call_related_queries_with_unavailable_retry", return_value=related):
        rows = await news.get_related_queries("python")

    assert rows["rising"] == [
        {"query": "surging", "value": None, "is_breakout": True},
        {"query": "ordinary", "value": 350.0},
    ]
    json.dumps(rows, allow_nan=False)


async def test_related_topics_skip_invalid_provider_values_only():
    related = {
        "top": pd.DataFrame(
            {
                "mid": ["/m/good", "/m/bad"],
                "title": ["Good", "Bad"],
                "type": ["Topic", "Topic"],
                "value": [90, float("nan")],
            }
        ),
        "rising": pd.DataFrame(
            {
                "mid": ["/m/new", "/m/invalid"],
                "title": ["New", "Invalid"],
                "type": ["Topic", "Topic"],
                "value": [250, float("-inf")],
            }
        ),
    }
    with patch.object(news.tr, "related_topics", return_value=related):
        rows = await news.get_related_topics("python")

    assert rows == {
        "top": [{"mid": "/m/good", "title": "Good", "type": "Topic", "value": 90.0}],
        "rising": [{"mid": "/m/new", "title": "New", "type": "Topic", "value": 250.0}],
    }
    json.dumps(rows, allow_nan=False)


async def test_related_topics_preserve_breakout_with_its_entity_metadata():
    related = {
        "top": pd.DataFrame(columns=["mid", "title", "type", "value"]),
        "rising": pd.DataFrame({"mid": ["/m/surge"], "title": ["Surge"],
                                "type": ["Topic"], "value": ["Breakout"]}),
    }
    with patch.object(news.tr, "related_topics", return_value=related):
        rows = await news.get_related_topics("python")

    assert rows["rising"] == [
        {"mid": "/m/surge", "title": "Surge", "type": "Topic",
         "value": None, "is_breakout": True}
    ]
    json.dumps(rows, allow_nan=False)


async def test_related_queries_skip_missing_or_invalid_query_identity():
    related = {
        "top": pd.DataFrame({
            "query": ["  real query  ", None, float("nan"), "   ", 123],
            "value": [70, 60, 50, 40, 30],
        }),
        "rising": pd.DataFrame(columns=["query", "value"]),
    }
    with patch.object(news, "_call_related_queries_with_unavailable_retry", return_value=related):
        rows = await news.get_related_queries("python")

    assert rows == {"top": [{"query": "real query", "value": 70.0}], "rising": []}


async def test_related_topics_skip_missing_or_invalid_entity_identity():
    related = {
        "top": pd.DataFrame({
            "mid": ["/m/valid", None, "/m/missing-title", "/m/blank-type"],
            "title": ["  Real topic  ", "Ignored", float("nan"), "Ignored"],
            "type": ["Topic", "Topic", "Topic", "   "],
            "value": [70, 60, 50, 40],
        }),
        "rising": pd.DataFrame(columns=["mid", "title", "type", "value"]),
    }
    with patch.object(news.tr, "related_topics", return_value=related):
        rows = await news.get_related_topics("python")

    assert rows == {"top": [{"mid": "/m/valid", "title": "Real topic", "type": "Topic", "value": 70.0}], "rising": []}


async def test_suggestions_skip_invalid_provider_entity_fields():
    frame = pd.DataFrame(
        {
            "mid": [" /m/valid ", None, "/m/no-title", "/m/no-type", 123],
            "title": [" Valid suggestion ", "Missing ID", float("nan"), "Blank type", "Numeric ID"],
            "type": [" Topic ", "Topic", "Topic", "  ", "Topic"],
        }
    )
    with patch.object(news.tr, "suggestions", return_value=frame):
        suggestions = await news.get_suggestions("python")

    assert suggestions == [{"mid": "/m/valid", "title": "Valid suggestion", "type": "Topic"}]
    json.dumps(suggestions, allow_nan=False)
