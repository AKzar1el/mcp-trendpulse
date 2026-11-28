"""M04: opt-in Google Trends Explore evidence, with shared provider limits."""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone

import pytest
from click.testing import CliRunner

from mcp_trendpulse import intelligence_explore as explore
from mcp_trendpulse import intelligence_keyword_probe as legacy
from mcp_trendpulse.cli import cli
from mcp_trendpulse.errors import ProviderRateLimitError, ProviderUnavailableError
from mcp_trendpulse.intelligence_core import BudgetCache
from mcp_trendpulse.intelligence_signal import SignalPeriod, SignalProvenance, TrendSignal

NOW = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)


def source_signal(source_id="google_trending_now_rss", country="SI", term="Umetna inteligenca"):
    rss = source_id == "google_trending_now_rss"
    return TrendSignal(
        source_id=source_id,
        source_url=("https://trends.google.com/trending/rss?geo=SI" if rss else
                    "https://cloud.google.com/blog/products/data-analytics/international-google-trends-datasets-in-bigquery"),
        observed_at=NOW,
        country=country,
        raw_term=term, normalized_term=term.casefold(),
        metric_type="google_trending_traffic_bucket" if rss else "google_bigquery_rank",
        metric_unit="approximate_search_bucket" if rss else "rank",
        period=SignalPeriod(start_date=NOW.date(), end_date=NOW.date(),
                            granularity="point_in_time" if rss else "daily"),
        value=None if rss else 2,
        value_label="500+" if rss else None,
        sampling_scope="Source published small sample, not complete Google queries",
        coverage_status="observed",
        provenance=SignalProvenance(
            method="public_rss" if rss else "public_dataset",
            sampling_basis="source_grouped_label" if rss else "daily_curated_rank",
            is_observed_search_query=False,
        ),
    ).model_dump(mode="json")


class Provider:
    def __init__(self, *, related=None, interest=None):
        self.calls = []
        self.related = related if related is not None else {
            "top": [{"query": "umetna inteligenca novice", "value": 92}],
            "rising": [{"query": "umetna inteligenca video", "value": None,
                        "is_breakout": True},
                       {"query": "AI agenti", "value": 85.0}],
        }
        self.interest = interest if interest is not None else [
            {"date": "2026-11-17", "value": 43.0, "keyword": "Umetna inteligenca"},
            {"date": "2026-11-18", "value": 57.0, "keyword": "Umetna inteligenca"},
            {"date": "2026-11-19", "value": 71.0, "keyword": "Umetna inteligenca"},
        ]

    async def get_related_queries(self, **kw):
        self.calls.append(("related", kw))
        if isinstance(self.related, Exception):
            raise self.related
        return self.related

    async def get_trends(self, **kw):
        self.calls.append(("interest", kw))
        if isinstance(self.interest, Exception):
            raise self.interest
        return self.interest


@pytest.fixture
def fixed_seed_clock(monkeypatch):
    """Keep source freshness tests independent of the CI calendar."""

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW.astimezone(tz) if tz is not None else NOW.replace(tzinfo=None)

    monkeypatch.setattr(explore, "datetime", FixedDateTime)


def test_explicit_manual_seed_and_verified_source_seed_must_keep_market(fixed_seed_clock):
    manual = explore.select_seed(term="AI agents", country="SI")
    assert manual == {"term": "AI agents", "country": "SI", "origin": "operator_supplied",
                      "source_id": None, "language": None}
    with pytest.raises(ValueError):
        explore.select_seed(term="AI agents")
    with pytest.raises(ValueError):
        explore.select_seed(term="https://example.test/?token=SECRET", country="SI")
    with pytest.raises(ValueError):
        explore.select_seed(term="Test", country="WORLD")

    rss = {"mode": "google_trending_now_public_rss_source_attributed",
           "status": "observed", "country": "SI",
           "trends": [{"signal": source_signal(), "related_news": []}]}
    seed = explore.select_seed(source=rss)
    assert seed["term"] == "Umetna inteligenca"
    assert seed["country"] == "SI"
    assert seed["origin"] == "source_observed"
    assert seed["source_id"] == "google_trending_now_rss"

    bq = {"source": "google_trends_bigquery_public", "status": "observed",
          "country": "SI", "signals": [
              source_signal(source_id="google_trends_bigquery"),
          ]}
    assert explore.select_seed(source=bq)["source_id"] == "google_trends_bigquery"
    with pytest.raises(ValueError):
        explore.select_seed(source={**rss, "status": "planned"})
    with pytest.raises(ValueError):
        explore.select_seed(source={**rss, "country": "GB"})
    with pytest.raises(ValueError):
        explore.select_seed(source=rss, term="extra", country="SI")
    stale = {**rss, "trends": [{
        "signal": {**source_signal(), "observed_at": "2026-10-01T12:00:00Z"},
        "related_news": [],
    }]}
    with pytest.raises(ValueError):
        explore.select_seed(source=stale)
    future = {**rss, "trends": [{
        "signal": {**source_signal(), "observed_at": "2026-11-20T12:00:01Z"},
        "related_news": [],
    }]}
    with pytest.raises(ValueError):
        explore.select_seed(source=future)


@pytest.mark.asyncio
async def test_preview_is_pure_no_network_and_no_budget_store(tmp_path, monkeypatch):
    seed = explore.select_seed(term="AI agents", country="US")
    provider = Provider()
    monkeypatch.setattr(explore, "BudgetCache", lambda: (_ for _ in ()).throw(
        AssertionError("Preview cannot open budget database")
    ))
    result = await explore.discover_explore(seed, provider=provider, execute=False)
    assert result["status"] == "planned"
    assert result["network_performed"] is False
    assert result["provider_operations_attempted"] == 0
    assert not result["related"]["top"] and not result["interest"]["signals"]
    assert provider.calls == []


@pytest.mark.asyncio
async def test_related_and_interest_source_evidence_share_legacy_daily_budget(tmp_path):
    store = BudgetCache(tmp_path)
    seed = explore.select_seed(term="Umetna inteligenca", country="SI")
    provider = Provider()
    result = await explore.discover_explore(
        seed, provider=provider, cache=store, observed_at=NOW, execute=True,
    )
    assert result["status"] == "observed"
    assert result["provider_operations_attempted"] == 2
    assert result["provider_budget_id"] == legacy.PROVIDER_BUDGET_ID
    assert result["local_utc_daily_provider_operations_cap"] == 2
    assert [x[0] for x in provider.calls] == ["related", "interest"]
    assert provider.calls[0][1] == {
        "keyword": "Umetna inteligenca", "geo": "SI",
        "timeframe": "today 3-m", "cat": 0, "gprop": "",
    }
    assert provider.calls[1][1] == {
        "keyword": "Umetna inteligenca", "geo": "SI",
        "timeframe": "today 3-m", "data_mode": "daily", "cat": 0,
        "source": "google search",
    }
    assert result["related"]["top"][0]["query"] == "umetna inteligenca novice"
    assert len(result["related"]["top"]) == 1
    assert result["related"]["rising"][0]["is_breakout"] is True
    assert result["related"]["rising"][0]["provider_value"] is None
    assert result["related"]["rising"][0]["breakout_meaning"] == "greater_than_5000_percent"
    assert result["related"]["rising"][1]["provider_value"] == 85.0
    assert result["related"]["rising"][1]["provider_value_semantics"] == "previous_comparable_period_percentage_growth_not_absolute_volume"
    assert len(result["interest"]["signals"]) == 3
    points = result["interest"]["signals"]
    assert points[0]["period"]["start_date"] == "2026-11-17"
    assert points[-1]["value"] == 71
    assert all(x["metric_type"] == "google_trends_normalized_interest" for x in points)
    assert all(x["country"] == "SI" and x["language"] is None for x in points)
    assert all(x["provenance"]["method"] == "community_provider" for x in points)
    assert all(x["provenance"]["is_observed_search_query"] is False for x in points)
    assert result["exact_search_volume_available"] is False
    assert result["site_property_required"] is False
    assert result["paid_services_used"] is False

    cached = await explore.discover_explore(
        seed, provider=provider, cache=BudgetCache(tmp_path),
        observed_at=NOW, execute=True,
    )
    assert cached["status"] == "observed"
    assert cached["related"]["cache_hit"] is True
    assert cached["interest"]["cache_hit"] is True
    assert cached["provider_operations_attempted"] == 0
    assert cached["network_performed"] is False
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_legacy_keyword_probe_uses_same_quota_and_no_unbounded_fallback(tmp_path):
    store = BudgetCache(tmp_path)
    store.reserve(legacy.PROVIDER_BUDGET_ID, legacy.UTC_DAILY_PROVIDER_CAP)
    store.reserve(legacy.PROVIDER_BUDGET_ID, legacy.UTC_DAILY_PROVIDER_CAP)
    provider = Provider()
    out = await explore.discover_explore(
        explore.select_seed(term="Umetna inteligenca", country="SI"),
        provider=provider, cache=store, execute=True,
    )
    assert out["status"] == "local_daily_budget_exhausted"
    assert out["provider_operations_attempted"] == 0
    assert provider.calls == []


@pytest.mark.asyncio
async def test_rate_limit_opens_circuit_and_skips_interest(tmp_path):
    store = BudgetCache(tmp_path)
    provider = Provider(related=ProviderRateLimitError("google_trends", "related_queries"))
    seed = explore.select_seed(term="Umetna inteligenca", country="SI")
    first = await explore.discover_explore(
        seed, provider=provider, cache=store, execute=True,
    )
    assert first["related"]["status"] == "provider_rate_limited"
    assert first["interest"]["status"] == "provider_cooldown"
    assert first["provider_operations_attempted"] == 1
    with sqlite3.connect(store.db) as conn:
        remaining = conn.execute(
            "SELECT until FROM cooldown WHERE source=?",
            (legacy.PROVIDER_BUDGET_ID,),
        ).fetchone()[0] - time.time()
        used = conn.execute(
            "SELECT used FROM budget WHERE source=? AND day=date('now')",
            (legacy.PROVIDER_BUDGET_ID,),
        ).fetchone()[0]
    assert remaining >= 23 * 3600  # 429 is not a five-minute retry signal.
    assert used == 1
    second = await explore.discover_explore(
        seed, provider=provider, cache=BudgetCache(tmp_path), execute=True,
    )
    assert second["provider_operations_attempted"] == 0
    assert second["related"]["status"] == "provider_cooldown"
    assert second["interest"]["status"] == "provider_cooldown"
    assert second["network_performed"] is False
    assert second["exact_search_volume_available"] is False
    assert len(provider.calls) == 1


def test_cli_execute_is_network_free_during_persisted_rate_limit(tmp_path, monkeypatch):
    from mcp_trendpulse import providers

    store = BudgetCache(tmp_path)
    store.stop_after_rate_limit(legacy.PROVIDER_BUDGET_ID)
    monkeypatch.setenv("TRENDPULSE_INTEL_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(providers, "get_provider_set", lambda: (
        (_ for _ in ()).throw(AssertionError("Blocked CLI cannot open provider"))
    ))
    result = CliRunner().invoke(cli, [
        "intelligence", "explore-evidence", "--term", "AI agents",
        "--country", "US", "--execute", "--format", "json",
    ])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["status"] == "unavailable"
    assert report["related"]["status"] == "provider_cooldown"
    assert report["interest"]["status"] == "provider_cooldown"
    assert report["provider_operations_attempted"] == 0
    assert report["network_performed"] is False
    assert report["exact_search_volume_available"] is False
    with sqlite3.connect(store.db) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM budget WHERE source=?",
            (legacy.PROVIDER_BUDGET_ID,),
        ).fetchone()[0] == 0


@pytest.mark.asyncio
async def test_local_provider_cooldown_does_not_claim_a_new_google_429(tmp_path):
    from mcp_trendpulse.trends_rate_control import TrendsCooldownError

    provider = Provider(related=TrendsCooldownError("local pacing guard"))
    result = await explore.discover_explore(
        explore.select_seed(term="AI agents", country="US"),
        provider=provider, cache=BudgetCache(tmp_path), execute=True,
    )
    assert result["status"] == "unavailable"
    assert result["related"]["status"] == "provider_cooldown"
    assert result["interest"]["status"] == "provider_cooldown"
    assert result["provider_operations_attempted"] == 1
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_invalid_source_values_and_partial_observations_not_verified_zero(tmp_path):
    provider = Provider(
        related={"top": [{"query": "bad malicious value", "value": 999},
                         {"query": "normal result", "value": 35}],
                 "rising": [{"query": "odd result", "value": float("inf")}]},
        interest=[{"date": "2026-11-18", "value": float("nan"),
                   "keyword": "Umetna inteligenca"},
                  {"date": "2026-11-19", "value": 42,
                   "keyword": "Umetna inteligenca"},
                  {"date": "2026-11-22", "value": 50,
                   "keyword": "Umetna inteligenca"}],
    )
    out = await explore.discover_explore(
        explore.select_seed(term="Umetna inteligenca", country="SI"),
        provider=provider, cache=BudgetCache(tmp_path), observed_at=NOW,
        execute=True,
    )
    assert out["status"] == "observed_partial"
    assert out["related"]["top"][0]["query"] == "normal result"
    assert out["related"]["rising"] == []
    assert len(out["interest"]["signals"]) == 1
    assert out["interest"]["signals"][0]["value"] == 42.0
    assert "NaN" not in json.dumps(out, allow_nan=False)


@pytest.mark.asyncio
async def test_provider_error_redacted_and_interest_kept_unmeasured(tmp_path):
    provider = Provider(related=RuntimeError("Bearer SUPER_SECRET https://private.test"),
                        interest=ProviderUnavailableError("google_trends", "interest_over_time"))
    out = await explore.discover_explore(
        explore.select_seed(term="Umetna inteligenca", country="SI"),
        provider=provider, cache=BudgetCache(tmp_path), execute=True,
    )
    assert out["status"] == "unavailable"
    assert out["related"]["status"] == "provider_unavailable"
    assert out["interest"]["status"] == "provider_unavailable"
    assert out["interest"]["signals"] == []
    assert "SUPER_SECRET" not in repr(out) and "private.test" not in repr(out)


@pytest.mark.asyncio
async def test_broken_local_budget_store_fails_closed(tmp_path):
    class BrokenCache:
        def cached(self, _key):
            raise OSError("secret cannot be echoed")
    provider = Provider()
    out = await explore.discover_explore(
        explore.select_seed(term="Umetna inteligenca", country="SI"),
        provider=provider, cache=BrokenCache(), execute=True,
    )
    assert out["status"] == "local_budget_store_unavailable"
    assert out["provider_operations_attempted"] == 0
    assert provider.calls == []
    assert "secret" not in repr(out)


@pytest.mark.asyncio
async def test_bad_cached_data_refetched_only_after_budget_guard(tmp_path):
    seed = explore.select_seed(term="Umetna inteligenca", country="SI")
    store = BudgetCache(tmp_path)
    provider = Provider()
    result = await explore.discover_explore(seed, provider=provider,
                                            cache=store, observed_at=NOW, execute=True)
    assert result["status"] == "observed"
    # A cache record with a mismatched country cannot be promoted to evidence.
    for operation in ("related", "interest"):
        key = explore._cache_key(seed, "today 3-m", operation)
        store.save(key, {"seed": {"country": "DE"}, "operation": operation},
                   explore.CACHE_TTL_SECONDS)
    repeated = await explore.discover_explore(
        seed, provider=provider, cache=store, observed_at=NOW, execute=True,
    )
    assert repeated["provider_operations_attempted"] == 0
    assert repeated["status"] == "local_daily_budget_exhausted"
    assert len(provider.calls) == 2
    fake_partial = {
        "operation": "interest", "seed": seed, "timeframe": "today 3-m",
        "result": {"status": "observed_partial", "signals": []},
    }
    assert explore._cached_operation(
        fake_partial, operation="interest", seed=seed,
        timeframe="today 3-m", observed=NOW,
    ) is None


@pytest.mark.asyncio
async def test_bad_related_shape_is_distinct_from_empty_with_no_fake_demand(tmp_path):
    seed = explore.select_seed(term="Umetna inteligenca", country="SI")
    bad = await explore.discover_explore(
        seed, provider=Provider(related={"top": "private", "rising": []}),
        cache=BudgetCache(tmp_path / "bad"), execute=True,
    )
    assert bad["related"]["status"] == "invalid_provider_shape"
    assert bad["related"]["top"] == [] and bad["related"]["rising"] == []
    empty = await explore.discover_explore(
        seed, provider=Provider(related={"top": [], "rising": []}, interest=[]),
        cache=BudgetCache(tmp_path / "empty"), execute=True,
    )
    assert empty["related"]["status"] == "observed_empty"
    assert empty["interest"]["status"] == "observed_empty"
    assert empty["exact_search_volume_available"] is False
    missing = await explore.discover_explore(
        seed, provider=Provider(related={}),
        cache=BudgetCache(tmp_path / "missing"), execute=True,
    )
    assert missing["related"]["status"] == "invalid_provider_shape"


@pytest.mark.asyncio
async def test_nonempty_malformed_related_rows_are_not_reported_as_observed_empty(tmp_path):
    seed = explore.select_seed(term="Umetna inteligenca", country="SI")
    provider = Provider(
        related={"top": [{"query": "out of range", "value": 500}],
                 "rising": [{"query": "secret", "value": float("nan")}]},
        interest=[],
    )
    out = await explore.discover_explore(
        seed, provider=provider, cache=BudgetCache(tmp_path), execute=True,
    )
    assert out["related"]["status"] == "invalid_provider_shape"
    assert out["related"]["source_rows_received"] == 2
    assert out["related"]["source_rows_omitted"] == 2
    assert out["related"]["top"] == [] and out["related"]["rising"] == []
    assert out["status"] == "unavailable"
    assert out["exact_search_volume_available"] is False
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_partial_related_source_is_disclosed_and_cached_without_refetch(tmp_path):
    seed = explore.select_seed(term="Umetna inteligenca", country="SI")
    provider = Provider(
        related={"top": [
            {"query": "valid related keyword", "value": 85},
            {"query": "INVALID VALUE", "value": 700},
            {"query": "valid related keyword", "value": 85},
        ], "rising": [
            {"query": "rapidly rising keyword", "is_breakout": True, "value": None},
        ]},
        interest=[],
    )
    cache = BudgetCache(tmp_path)
    first = await explore.discover_explore(
        seed, provider=provider, cache=cache, execute=True,
    )
    assert first["related"]["status"] == "observed_partial"
    assert first["status"] == "observed_partial"
    assert first["related"]["source_rows_received"] == 4
    assert first["related"]["source_rows_omitted"] == 2
    assert len(first["related"]["top"]) == 1
    assert first["related"]["rising"][0]["breakout_meaning"] == "greater_than_5000_percent"
    assert first["provider_operations_attempted"] == 2
    repeat = await explore.discover_explore(
        seed, provider=provider, cache=BudgetCache(tmp_path), execute=True,
    )
    assert repeat["related"]["status"] == "observed_partial"
    assert repeat["related"]["cache_hit"] is True
    assert repeat["interest"]["cache_hit"] is True
    assert repeat["related"]["source_rows_omitted"] == 2
    assert repeat["provider_operations_attempted"] == 0
    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_related_provider_capped_series_discloses_omitted_candidates(tmp_path):
    seed = explore.select_seed(term="Umetna inteligenca", country="SI")
    provider = Provider(
        related={"top": [
            {"query": f"software interest {i}", "value": i}
            for i in range(12)
        ], "rising": []},
        interest=[],
    )
    first = await explore.discover_explore(
        seed, provider=provider, cache=BudgetCache(tmp_path), execute=True,
    )
    assert first["related"]["status"] == "observed_partial"
    assert len(first["related"]["top"]) == 3
    assert first["related"]["source_rows_received"] == 12
    assert first["related"]["source_rows_omitted"] == 9
    assert first["related"]["rows_truncated"] is True


@pytest.mark.asyncio
async def test_corrupt_cached_related_rows_fail_closed_without_leaking_or_refetch(tmp_path):
    seed = explore.select_seed(term="Umetna inteligenca", country="SI")
    store = BudgetCache(tmp_path)
    for _ in range(legacy.UTC_DAILY_PROVIDER_CAP):
        store.reserve(legacy.PROVIDER_BUDGET_ID, legacy.UTC_DAILY_PROVIDER_CAP)
    store.save(
        explore._cache_key(seed, "today 3-m", "related"),
        {"operation": "related", "seed": seed, "timeframe": "today 3-m",
         "result": {"status": "observed",
                    "top": ["SECRET_INVALID_CACHED_ROW"], "rising": [],
                    "source_rows_received": 1, "source_rows_omitted": 0,
                    "rows_truncated": False}},
        explore.CACHE_TTL_SECONDS,
    )
    provider = Provider()
    out = await explore.discover_explore(
        seed, provider=provider, cache=store, execute=True,
    )
    assert out["related"]["status"] == "local_daily_budget_exhausted"
    assert out["related"]["cache_hit"] is False
    assert out["provider_operations_attempted"] == 0
    assert provider.calls == []
    assert "SECRET_INVALID_CACHED_ROW" not in repr(out)


@pytest.mark.asyncio
async def test_cached_interest_does_not_echo_arbitrary_storage_metadata(tmp_path):
    seed = explore.select_seed(term="Umetna inteligenca", country="SI")
    store = BudgetCache(tmp_path)
    provider = Provider()
    first = await explore.discover_explore(
        seed, provider=provider, cache=store, execute=True,
    )
    assert first["status"] == "observed"
    store.save(
        explore._cache_key(seed, "today 3-m", "interest"),
        {"operation": "interest", "seed": seed, "timeframe": "today 3-m",
         "result": {**first["interest"],
                    "private_access_token": "DANGEROUS_CACHED_SECRET"}},
        explore.CACHE_TTL_SECONDS,
    )
    cached = await explore.discover_explore(
        seed, provider=provider, cache=store, execute=True,
    )
    assert cached["interest"]["status"] == "observed"
    assert cached["interest"]["cache_hit"] is True
    assert len(cached["interest"]["signals"]) == 3
    assert cached["provider_operations_attempted"] == 0
    assert len(provider.calls) == 2
    assert "DANGEROUS_CACHED_SECRET" not in repr(cached)


def test_cli_preview_offline_and_source_file_input(tmp_path, monkeypatch, fixed_seed_clock):
    from mcp_trendpulse import providers
    monkeypatch.setattr(providers, "get_provider_set", lambda: (
        (_ for _ in ()).throw(AssertionError("Preview must be offline"))
    ))
    manual = CliRunner().invoke(cli, [
        "intelligence", "explore-evidence", "--term", "AI agents",
        "--country", "SI", "--format", "json",
    ])
    assert manual.exit_code == 0, manual.output
    out = json.loads(manual.output)
    assert out["status"] == "planned"
    assert out["provider_operations_attempted"] == 0
    assert out["seed"]["origin"] == "operator_supplied"
    rss = {"mode": "google_trending_now_public_rss_source_attributed",
           "status": "observed", "country": "SI",
           "trends": [{"signal": source_signal(), "related_news": []}]}
    path = tmp_path / "rss.json"
    path.write_text(json.dumps(rss), encoding="utf-8")
    out2 = CliRunner().invoke(cli, ["intelligence", "explore-evidence",
                                   "--source-file", str(path), "--format", "json"])
    assert out2.exit_code == 0, out2.output
    assert json.loads(out2.output)["seed"]["origin"] == "source_observed"


def test_cli_live_json_excludes_trendspy_stdout_warning(monkeypatch):
    async def fake_discover(seed, *, execute, timeframe):
        assert execute is True
        print("Warning: Too many rate limit errors (429).")
        return {"mode": explore.MODE, "status": "unavailable", "seed": seed,
                "timeframe": timeframe, "provider_operations_attempted": 1,
                "network_performed": True,
                "related": {"status": "provider_rate_limited"},
                "interest": {"status": "provider_cooldown"}}

    monkeypatch.setattr(explore, "discover_explore", fake_discover)
    result = CliRunner().invoke(cli, [
        "intelligence", "explore-evidence", "--term", "AI agents",
        "--country", "US", "--timeframe", "today 3-m",
        "--execute", "--format", "json",
    ])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["status"] == "unavailable"
    assert report["related"]["status"] == "provider_rate_limited"
    assert report["provider_operations_attempted"] == 1
    assert "Warning:" not in result.output


def test_cli_refuses_bad_source_and_double_seed(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"status":"planned","mode":"wrong"}', encoding="utf-8")
    wrong = CliRunner().invoke(cli, [
        "intelligence", "explore-evidence", "--source-file", str(path),
    ])
    assert wrong.exit_code != 0
    assert "Invalid" in wrong.output
    conflict = CliRunner().invoke(cli, [
        "intelligence", "explore-evidence", "--source-file", str(path),
        "--term", "ignore me", "--country", "SI",
    ])
    assert conflict.exit_code != 0
