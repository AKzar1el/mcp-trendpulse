"""Provider-capped optional related keyword traces with no market hallucination."""
from __future__ import annotations

import asyncio

import pytest

from mcp_trendpulse import intelligence_keyword_probe as probes
from mcp_trendpulse.errors import ProviderRateLimitError
from mcp_trendpulse.intelligence_core import BudgetCache

def idea(i, kind, market, words):
    return {
        "id": i, "kind": kind,
        "geography": {"country_code": market},
        "keyword_hypotheses": [
            {"keyword": v, "basis": "published_ted_scope_original_language"}
            for v in words
        ],
    }


def source():
    return {"mode": "source_grounded_project_idea_and_keyword_research_queue",
            "ideas": [
                idea("abc123abc123ab", "procurement_derived_software_hypothesis",
                     "DE", ["finanzsoftware", "haussoftware"]),
                idea("def234def234de", "consumer_problem_derived_software_hypothesis",
                     "US", ["incorrect information on your report"]),
                idea("fedcba98765432", "consumer_problem_derived_software_hypothesis",
                     "US", ["debt collection"]),
            ]}


class Cache:
    def __init__(self):
        self.stored = {}
        self.used = 0
        self.cap = 2

    def cached(self, key):
        return self.stored.get(key)

    def reserve(self, source, cap, *, guard_cooldown=False):
        assert source == probes.PROVIDER_BUDGET_ID and cap == 2
        assert guard_cooldown is True
        if self.used >= cap:
            from mcp_trendpulse.intelligence_core import DailyBudgetExceeded

            raise DailyBudgetExceeded(source, "2026-11-20", cap, self.used)
        self.used += 1

    def save(self, key, body, ttl):
        assert ttl == probes.CACHE_TTL_SECONDS
        self.stored[key] = body


class Provider:
    def __init__(self):
        self.calls = []

    async def get_related_queries(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["geo"] == "DE":
            return {"top": [{"query": "software für liegenschaftsmanagement",
                             "value": 89}],
                    "rising": [{"query": "c a f m software", "value": 150}]}
        return {"top": [{"query": "credit report dispute", "value": 100}],
                "rising": [{"query": "credit reporting software",
                            "is_breakout": True, "value": None}]}


def test_two_market_source_selection_provider_calls_and_cache_reuse():
    selected = probes.select_related_query_seeds(source())
    assert len(selected) == 2
    assert [(x["keyword"], x["market"]) for x in selected] == [
        ("finanzsoftware", "DE"),
        ("incorrect information on your report", "US"),
    ]
    cache = Cache()
    provider = Provider()
    result = asyncio.run(probes.probe_idea_keywords_async(
        source(), provider=provider, cache=cache,
    ))
    assert len(provider.calls) == 2
    assert cache.used == 2
    assert all(r["status"] == "observed_related_queries" for r in result["results"])
    assert result["results"][0]["top"][0]["provider_value"] == 89
    assert result["results"][1]["rising"][0]["is_breakout"] is True
    assert result["results"][0]["top"][0]["keyword_demand_verified"] is False
    assert result["physical_http_requests_not_measured"] is True
    assert "absolute keyword volume" in "\n".join(probes.format_keyword_probe(result)).lower()
    cached = asyncio.run(probes.probe_idea_keywords_async(
        source(), provider=provider, cache=cache,
    ))
    assert len(provider.calls) == 2
    assert all(r["cache_hit"] for r in cached["results"])


def test_failures_do_not_leak_secrets_or_count_as_observed_zeros():
    class BadProvider:
        async def get_related_queries(self, **_kwargs):
            raise RuntimeError("token=PRIVATE_VALUE https://internal.invalid")
    out = asyncio.run(probes.probe_idea_keywords_async(
        source(), provider=BadProvider(), cache=Cache(),
    ))
    assert out["status"] == "partial_or_unavailable_related_query_sources"
    assert all(r["status"] == "unavailable" for r in out["results"])
    assert "PRIVATE_VALUE" not in repr(out)
    assert "internal.invalid" not in repr(out)


def test_invalid_payload_not_promoted_to_measured_keyword_volume():
    class EvilProvider:
        async def get_related_queries(self, **_kw):
            return {"top": [{"query": "https://evil.example/SECRET",
                             "value": 100}, {"query": "bad", "value": float("inf")},
                            {"query": "valid software", "value": 200}],
                    "rising": [{"query": "good related query", "value": 2100}]}
    out = asyncio.run(probes.probe_idea_keywords_async(
        source(), provider=EvilProvider(), cache=Cache(),
    ))
    assert "evil.example" not in repr(out)
    assert "SECRET" not in repr(out)
    assert out["results"][0]["top"] == []
    assert out["results"][0]["rising"][0]["provider_value"] == 2100


def test_daily_quota_refusal_skips_network_and_reports_partial():
    cache = Cache()
    cache.used = 2
    class NoCalls:
        async def get_related_queries(self, **_kw):
            raise AssertionError("No calls should occur after local cap")
    out = asyncio.run(probes.probe_idea_keywords_async(
        source(), provider=NoCalls(), cache=cache,
    ))
    assert out["provider_operations_attempted"] == 0
    assert all(r["status"] == "local_daily_budget_exhausted"
               for r in out["results"])
    assert all(r["local_quota_used"] == 2
               and r["local_quota_limit"] == 2 for r in out["results"])
    assert "already reserved" in "\n".join(probes.format_keyword_probe(out))


def test_429_in_legacy_probe_stops_second_seed_and_m04_across_store_reopen(tmp_path):
    from mcp_trendpulse import intelligence_explore as explore

    class RateLimited:
        calls = 0

        async def get_related_queries(self, **_kw):
            self.calls += 1
            raise ProviderRateLimitError("google_trends", "related_queries")

    provider = RateLimited()
    first = asyncio.run(probes.probe_idea_keywords_async(
        source(), provider=provider, cache=BudgetCache(tmp_path),
    ))
    assert first["provider_operations_attempted"] == 1
    assert first["results"][0]["status"] == "provider_rate_limited"
    assert first["results"][1]["status"] == "provider_cooldown"

    class NoCalls:
        async def get_related_queries(self, **_kw):
            raise AssertionError("Never retry after 429")

        async def get_trends(self, **_kw):
            raise AssertionError("Never fetch interest after 429")

    reopened = BudgetCache(tmp_path)
    repeated = asyncio.run(probes.probe_idea_keywords_async(
        source(), provider=NoCalls(), cache=reopened,
    ))
    assert repeated["provider_operations_attempted"] == 0
    assert all(r["status"] == "provider_cooldown" for r in repeated["results"])
    m04 = asyncio.run(explore.discover_explore(
        explore.select_seed(term="AI agents", country="US"),
        provider=NoCalls(), cache=BudgetCache(tmp_path), execute=True,
    ))
    assert m04["provider_operations_attempted"] == 0
    assert m04["related"]["status"] == "provider_cooldown"
    assert m04["interest"]["status"] == "provider_cooldown"
    assert provider.calls == 1


def test_m04_rate_limit_blocks_legacy_probe_even_with_daily_budget_left(tmp_path):
    from mcp_trendpulse import intelligence_explore as explore

    class Limited:
        async def get_related_queries(self, **_kw):
            raise ProviderRateLimitError("google_trends", "related_queries")

    first = asyncio.run(explore.discover_explore(
        explore.select_seed(term="AI agents", country="US"),
        provider=Limited(), cache=BudgetCache(tmp_path), execute=True,
    ))
    assert first["provider_operations_attempted"] == 1
    assert first["related"]["status"] == "provider_rate_limited"
    repeated = asyncio.run(probes.probe_idea_keywords_async(
        source(), provider=Limited(), cache=BudgetCache(tmp_path),
    ))
    assert repeated["provider_operations_attempted"] == 0
    assert all(r["status"] == "provider_cooldown" for r in repeated["results"])


def test_storage_errors_are_not_exhausted_quota_and_no_requests_are_sent():
    class BrokenCache(Cache):
        def cached(self, _key):
            raise OSError("CREDENTIAL_MUST_NOT_BE_EXPOSED")
    class NoCalls:
        async def get_related_queries(self, **_kw):
            raise AssertionError("A failed cache must never trigger the provider")
    out = asyncio.run(probes.probe_idea_keywords_async(
        source(), provider=NoCalls(), cache=BrokenCache(),
    ))
    assert all(r["status"] == "local_budget_store_unavailable"
               for r in out["results"])
    assert out["provider_operations_attempted"] == 0
    assert "CREDENTIAL_MUST_NOT_BE_EXPOSED" not in repr(out)
    class UnwriteableCache(Cache):
        def reserve(self, source, cap, *, guard_cooldown=False):
            raise OSError("disk restricted and password")
    out2 = asyncio.run(probes.probe_idea_keywords_async(
        source(), provider=NoCalls(), cache=UnwriteableCache(),
    ))
    assert all(r["status"] == "local_budget_store_unavailable"
               for r in out2["results"])
    assert "password" not in repr(out2)


def test_explicit_opt_in_required_and_execute_false_stays_offline(monkeypatch):
    from mcp_trendpulse import intelligence_discovery as discovery

    monkeypatch.setattr(discovery, "collect", lambda *_a, **_kw: (
        (_ for _ in ()).throw(AssertionError("Plan-only must stay offline"))
    ))
    with pytest.raises(ValueError, match="keyword-probe"):
        discovery.discover_current(execute=False, keyword_probe=True, env={})
    planned = discovery.discover_current(
        execute=False, workflow_briefs=True, idea_map=True,
        keyword_probe=True, env={},
    )
    assert planned["request_count"] == 3
    assert planned["idea_map"]["keyword_probe"]["max_provider_operations"] == 2
    assert planned["idea_map"]["keyword_probe"]["source_requests_performed"] == 0


def test_async_handler_fails_closed_if_sync_cli_adapter_invoked():
    async def running():
        with pytest.raises(ValueError, match="synchronous CLI-only"):
            probes.probe_idea_keywords(source())
    asyncio.run(running())
