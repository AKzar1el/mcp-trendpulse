"""Offline tests for the free-only market intelligence core (no outbound network)."""

import json
import pytest
from pathlib import Path
from mcp_trendpulse.intelligence_core import (
    BudgetCache, IntelligenceError, Plan, _bound_payload, collect, plan_source,
)


def test_foundation_registry_and_dry_run():
    # Other waves are available after the complete feature lands.
    p = plan_source("gdelt", keyword="battery passport", limit=4)
    assert p.url.startswith("https://api.gdeltproject.org/")
    result = collect(p)
    assert result["status"] == "planned"
    assert result["network_performed"] is False
    assert result["budget_per_day"] <= 20


def test_fixed_origins_and_encoded_inputs():
    p = plan_source("github_issues", keyword="agent authorization & audit", limit=3)
    assert "%26" in p.url
    assert p.url.startswith("https://api.github.com/")
    with pytest.raises(IntelligenceError):
        plan_source("worldbank", country="US", identifier="https://example.com/")


def test_explicit_dataset_and_ted_expert_query():
    p = plan_source("eurostat", dataset="nama_10_gdp", country="SI", limit=10)
    assert "geo=SI" in p.url
    assert "lastTimePeriod=3" in p.url
    q = plan_source("ted", keyword="publication-date>=20261101", limit=3)
    assert q.method == "POST"
    assert q.body["limit"] == 3
    with pytest.raises(IntelligenceError):
        plan_source("ted", keyword="x}; DROP TABLE test")


def test_invalid_limits_and_no_arbitrary_urls():
    with pytest.raises(IntelligenceError):
        plan_source("gdelt", keyword="a", limit=100000)
    with pytest.raises(IntelligenceError):
        collect(Plan(source="bad", wave=1, method="GET",
                     url="https://evil.example/data", docs="", caution="", budget_per_day=1), fetch=True)


def test_bounded_payload_is_still_valid_json():
    payload = {"items": [{"text": "x" * 9000} for _ in range(40)]}
    trimmed = _bound_payload(payload)
    assert len(trimmed["items"]) == 20
    assert all(len(x["text"]) == 3000 for x in trimmed["items"])
    json.dumps(trimmed)


def test_daily_budget_and_cache(tmp_path: Path):
    store = BudgetCache(tmp_path)
    store.reserve("test", 1)
    with pytest.raises(IntelligenceError, match="cap reached"):
        store.reserve("test", 1)
    store.save("hello", {"status": "observed"}, 60)
    assert store.cached("hello") == {"status": "observed"}
