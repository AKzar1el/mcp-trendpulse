"""M09 npm / M10 PyPI Stats: free, source-scoped, cache-safe tests."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from io import BytesIO

import pytest
from click.testing import CliRunner

from mcp_trendpulse import intelligence_package_downloads as packages
from mcp_trendpulse.cli import cli
from mcp_trendpulse.intelligence_core import BudgetCache

NOW = datetime(2026, 11, 21, 1, tzinfo=timezone.utc)
END = date(2026, 11, 19)


def npm_data(package="zod", *, days=7, removed=(), first=3):
    start = END-timedelta(days=days-1)
    return {
        "start": start.isoformat(), "end": END.isoformat(),
        "package": package,
        "downloads": [
            {
                "day": (start+timedelta(days=i)).isoformat(),
                "downloads": 0 if i == 0 else first+i,
            }
            for i in range(days) if i not in removed
        ],
    }


def pypi_data(package="pydantic", *, days=14, missing=(), lag=2,
              category="without_mirrors"):
    end = NOW.date()-timedelta(days=lag)
    start = end-timedelta(days=days-1)
    return {
        "type": "overall_downloads", "package": package,
        "data": [
            {
                "category": category,
                "date": (start+timedelta(days=i)).isoformat(),
                "downloads": 0 if i == 0 else 10+i,
            }
            for i in range(days) if i not in missing
        ],
    }


class Client:
    def __init__(self, payload, *, http=200, error=None):
        self.payload = payload
        self.http = http
        self.error = error
        self.calls = []

    def __call__(self, url, ecosystem):
        self.calls.append((url, ecosystem))
        if self.error:
            raise self.error
        return self.http, self.payload


def run(tmp_path, client, *, ecosystem="npm", package=None,
        days=7):
    return packages.discover_package_downloads(
        ecosystem=ecosystem, package=package or (
            "zod" if ecosystem == "npm" else "pydantic"
        ),
        days=days, observed_at=NOW,
        execute=True, cache=BudgetCache(tmp_path), fetcher=client,
    )


@pytest.mark.parametrize("ecosystem,package", [
    ("npm", "zod"), ("pypi", "Pydantic"),
])
def test_offline_preview_never_opens_sqlite_or_fetches(
    monkeypatch, ecosystem, package,
):
    monkeypatch.setattr(packages, "BudgetCache", lambda *_args: (
        (_ for _ in ()).throw(AssertionError("Preview must not open SQLite"))
    ))
    monkeypatch.setattr(packages, "_http_get", lambda *_args: (
        (_ for _ in ()).throw(AssertionError("Preview must not fetch"))
    ))
    preview = packages.discover_package_downloads(
        ecosystem=ecosystem, package=package, observed_at=NOW,
    )
    assert preview["status"] == "planned"
    assert preview["requests_attempted"] == 0
    assert preview["network_performed"] is False
    assert preview["signals"] == []
    assert preview["window"] is None
    assert preview["country"] is None and preview["language"] is None
    assert preview["cross_ecosystem_counts_additive"] is False
    assert preview["customer_demand_verified"] is False


@pytest.mark.parametrize(("ecosystem", "package"), [
    ("npm", "https://registry.npmjs.org/zod"),
    ("npm", "foo,bar"),
    ("npm", "foo/other"),
    ("npm", "ZOD"),
    ("npm", "../foo"),
    ("npm", "@someone"),
    ("npm", "@scope/../../other"),
    ("npm", "zod\nkey"),
    ("npm", " zod"),
    ("npm", ""),
    ("npm", "a"*121),
    ("pypi", "https://pypi.org/project/pydantic"),
    ("pypi", "x/y"),
    ("pypi", "%2F"),
    ("pypi", "some\nbad"),
    ("pypi", "pydantic."),
    ("pypi", "pydantic-"),
    ("pypi", "pydantic_"),
    ("pypi", ""),
    ("unknown", "zod"),
])
def test_invalid_names_rejected_before_any_source(ecosystem, package):
    with pytest.raises(ValueError):
        packages.discover_package_downloads(
            ecosystem=ecosystem, package=package, observed_at=NOW,
        )


@pytest.mark.parametrize("days", [0, 1, 14, 31, True, "7", None])
def test_unsupported_day_windows_refused(days):
    with pytest.raises(ValueError):
        packages.discover_package_downloads(
            ecosystem="npm", package="zod", days=days, observed_at=NOW,
        )


def test_scoped_npm_package_path_and_pypi_pep503_identity():
    assert packages._package("a", "pypi") == "a"
    assert packages._package("@babel/core", "npm") == "@babel/core"
    assert packages._url("@babel/core", "npm", 7) == (
        "https://api.npmjs.org/downloads/range/last-week/@babel%2Fcore"
    )
    assert packages._package("My_Package.Name", "pypi") == "my-package-name"
    assert packages._url("my-package-name", "pypi", 30) == (
        "https://pypistats.org/api/packages/my-package-name/overall?mirrors=false"
    )


def test_npm_realistic_7day_complete_zero_and_cache_repeat(tmp_path):
    client = Client(npm_data())
    out = run(tmp_path, client)
    assert out["status"] == "observed"
    assert out["ecosystem"] == "npm"
    assert out["window"] == {
        "start": "2026-11-13", "end": "2026-11-19",
        "days_expected": 7,
    }
    assert out["source_lag_days"] == 2
    assert len(out["rows"]) == 7 and out["rows"][0]["downloads"] == 0
    assert out["missing_dates"] == []
    assert out["source_rows_received"] == 7
    assert out["source_rows_rejected"] == 0
    assert out["downloads_sum_if_full_coverage"] == sum(
        row["downloads"] for row in npm_data()["downloads"]
    )
    assert out["requests_attempted"] == 1 and out["network_performed"]
    assert client.calls == [(
        "https://api.npmjs.org/downloads/range/last-week/zod", "npm",
    )]
    assert out["source"] == "npm_package_downloads"
    assert len(out["signals"]) == 7
    assert all(s["source_id"] == "npm_package_downloads" for s in out["signals"])
    assert all(s["metric_type"] == "npm_package_downloads" for s in out["signals"])
    assert all(s["metric_unit"] == "downloads" for s in out["signals"])
    assert all(s["provenance"]["method"] == "official_api" for s in out["signals"])
    assert all(not s["provenance"]["is_observed_search_query"] for s in out["signals"])
    assert all(s["country"] is None and s["language"] is None for s in out["signals"])
    assert out["unique_users_verified"] is False
    assert out["paid_services_used"] is False

    repeat = run(tmp_path, client)
    assert repeat["status"] == "observed" and repeat["cache_hit"] is True
    assert repeat["requests_attempted"] == 0
    assert repeat["network_performed"] is False
    assert repeat["signals"] == out["signals"]
    assert repeat["downloads_sum_if_full_coverage"] == (
        out["downloads_sum_if_full_coverage"]
    )
    assert len(client.calls) == 1


def test_npm_last_month_and_source_gaps_not_measured_zero(tmp_path):
    client = Client(npm_data(days=30, removed=(2, 9)))
    out = run(tmp_path, client, days=30)
    assert out["status"] == "observed_partial"
    assert out["window"]["days_expected"] == 30
    assert out["missing_dates"] == ["2026-10-23", "2026-10-30"]
    assert out["downloads_sum_if_full_coverage"] is None
    assert len(out["signals"]) == 28
    assert client.calls[0][0].endswith("/last-month/zod")


def test_npm_duplicate_daily_record_never_pretends_complete(tmp_path):
    payload = npm_data()
    payload["downloads"][0] = payload["downloads"][1].copy()
    out = run(tmp_path, Client(payload))
    assert out["status"] == "observed_partial"
    assert out["source_rows_rejected"] == 1
    assert out["missing_dates"] == ["2026-11-13"]
    assert out["downloads_sum_if_full_coverage"] is None


@pytest.mark.parametrize("mutation,expected", [
    (lambda p: p.update(package="other"), "invalid_source_scope"),
    (lambda p: p.update(start="2026-11-12"), "invalid_source_window"),
    (lambda p: p.update(end="2026-11-21"), "invalid_source_window"),
    (lambda p: p.update(downloads="not a list"), "invalid_source_shape"),
    (lambda p: p.update(downloads=[{"day": "bad", "downloads": 1}]),
     "invalid_source_shape"),
    (lambda p: p["downloads"][0].update(downloads=-1), "observed_partial"),
    (lambda p: p["downloads"][0].update(downloads=True), "observed_partial"),
])
def test_npm_scope_window_shape_and_invalid_counts_fail_closed(
    tmp_path, mutation, expected,
):
    payload = npm_data()
    mutation(payload)
    out = run(tmp_path, Client(payload))
    assert out["status"] == expected
    if expected.startswith("invalid_"):
        assert out["signals"] == []


def test_npm_empty_series_is_no_data_not_verifiable_zero(tmp_path):
    payload = npm_data()
    payload["downloads"] = []
    out = run(tmp_path, Client(payload))
    assert out["status"] == "no_data"
    assert out["signals"] == []
    assert out["downloads_sum_if_full_coverage"] is None


def test_npm_empty_series_repeat_stays_no_data_and_uses_cache(tmp_path):
    client = Client(npm_data())
    client.payload["downloads"] = []
    first = run(tmp_path, client)
    assert first["status"] == "no_data"
    second = run(tmp_path, Client({}, error=RuntimeError("no_network")))
    assert second["status"] == "no_data"
    assert second["cache_hit"] is True
    assert second["requests_attempted"] == 0
    assert second["window"] == first["window"]


def test_pypi_last_observed_data_window_and_known_mirror_exclusion(tmp_path):
    client = Client(pypi_data(days=14))
    out = run(tmp_path, client, ecosystem="pypi")
    assert out["status"] == "observed"
    assert out["ecosystem"] == "pypi"
    assert out["window"] == {
        "start": "2026-11-13", "end": "2026-11-19", "days_expected": 7,
    }
    assert len(out["rows"]) == 7
    assert out["rows"][0]["date"] == "2026-11-13"
    assert out["source_rows_all_history"] == 14
    assert out["source_rows_received"] == 7
    assert out["source_lag_days"] == 2
    assert out["downloads_sum_if_full_coverage"] is not None
    assert out["mirror_handling"] == "pypi_stats_excludes_known_mirrors"
    assert all(s["metric_type"] == "pypi_package_downloads" for s in out["signals"])
    assert all(s["metric_unit"] == "downloads" for s in out["signals"])
    assert all(s["provenance"]["method"] == "public_api" for s in out["signals"])
    assert client.calls[0] == (
        "https://pypistats.org/api/packages/pydantic/overall?mirrors=false", "pypi",
    )
    cached = run(tmp_path, client, ecosystem="pypi")
    assert cached["cache_hit"] and cached["requests_attempted"] == 0
    assert len(client.calls) == 1
    assert cached["rows"] == out["rows"]
    assert cached["source_rows_all_history"] == 14


def test_pypi_pep503_normalized_response_identity(tmp_path):
    data = pypi_data(package="My_Package.Name")
    out = run(tmp_path, Client(data), ecosystem="pypi", package="My_Package.Name")
    assert out["status"] == "observed"
    assert out["package"] == "my-package-name"


def test_pypi_30day_coverage_with_missing_history_not_invented(tmp_path):
    data = pypi_data(days=35, missing=(32,))
    out = run(tmp_path, Client(data), ecosystem="pypi", days=30)
    assert out["status"] == "observed_partial"
    assert out["missing_dates"] == ["2026-11-17"]
    assert out["downloads_sum_if_full_coverage"] is None


def test_pypi_late_source_not_marked_complete(tmp_path):
    out = run(tmp_path, Client(pypi_data(lag=9)), ecosystem="pypi")
    assert out["status"] == "observed_partial"
    assert out["source_lag_days"] == 9
    assert out["downloads_sum_if_full_coverage"] is None


def test_pypi_no_data_not_a_measured_zero(tmp_path):
    out = run(tmp_path, Client(pypi_data(days=0)), ecosystem="pypi")
    assert out["status"] == "no_data"
    assert out["signals"] == []
    assert out["downloads_sum_if_full_coverage"] is None
    again = run(tmp_path, Client({}, error=Exception("should never fetch")), ecosystem="pypi")
    assert again["cache_hit"] and again["requests_attempted"] == 0


@pytest.mark.parametrize("bad,expected", [
    ({"error": "PRIVATE_SECRET"}, "invalid_source_shape"),
    ({"type": "overall_downloads", "package": "wrong", "data": []},
     "invalid_source_scope"),
    ({"type": "recent_downloads", "package": "pydantic", "data": []},
     "invalid_source_shape"),
    (pypi_data(category="with_mirrors"), "invalid_source_scope"),
    (pypi_data(category="unknown"), "invalid_source_scope"),
])
def test_pypi_invalid_source_shapes_and_mirror_contamination(
    tmp_path, bad, expected,
):
    out = run(tmp_path, Client(bad), ecosystem="pypi")
    assert out["status"] == expected
    assert out["signals"] == []
    assert "PRIVATE_SECRET" not in repr(out)


@pytest.mark.parametrize("ecosystem", ["npm", "pypi"])
def test_source_404_is_not_zero_market_usage(tmp_path, ecosystem):
    out = run(
        tmp_path,
        Client({"error": "Sensitive API info"}, http=404),
        ecosystem=ecosystem,
    )
    assert out["status"] == "package_not_found_or_data_unavailable"
    assert out["downloads_sum_if_full_coverage"] is None
    assert out["rows"] == []


@pytest.mark.parametrize("ecosystem,code", [
    ("npm", 429), ("npm", 503), ("pypi", 429), ("pypi", 503),
])
def test_rate_limit_short_circuit_provider_cooldown(
    tmp_path, ecosystem, code,
):
    client = Client({}, http=code)
    out = run(tmp_path, client, ecosystem=ecosystem)
    assert out["status"] == "provider_rate_limited"
    assert out["requests_attempted"] == 1
    other = Client({})
    later = run(tmp_path, other, ecosystem=ecosystem, package=(
        "react" if ecosystem == "npm" else "requests"
    ))
    assert later["status"] == "provider_cooldown"
    assert later["requests_attempted"] == 0 and other.calls == []


def test_provider_exception_redacts_sensitive_body(tmp_path):
    client = Client({}, error=RuntimeError("Bearer SECRET_ABC"))
    out = run(tmp_path, client)
    assert out["status"] == "provider_unavailable"
    assert "SECRET_ABC" not in repr(out)


@pytest.mark.parametrize("ecosystem,cap", [("npm", 5), ("pypi", 3)])
def test_daily_budget_limits_source_specific_same_original_sqlite(
    tmp_path, ecosystem, cap,
):
    store = BudgetCache(tmp_path)
    for _ in range(cap):
        store.reserve(packages.SOURCE[ecosystem]["source_id"], cap)
    client = Client(npm_data() if ecosystem == "npm" else pypi_data())
    out = run(tmp_path, client, ecosystem=ecosystem)
    assert out["status"] == "local_daily_budget_exhausted"
    assert out["network_performed"] is False
    assert out["requests_attempted"] == 0 and client.calls == []


def test_poisoned_cache_fields_are_not_echoed_or_accepted(tmp_path):
    store = BudgetCache(tmp_path)
    client = Client(npm_data())
    good = run(tmp_path, client)
    assert good["status"] == "observed"
    key = packages._cache_key("zod", "npm", 7, NOW)
    original = store.cached(key)
    assert isinstance(original, dict)
    store.save(
        key, {**original, "private_key": "DO_NOT_ECHO"},
        packages.CACHE_TTL_SECONDS,
    )
    cached = run(tmp_path, client)
    assert cached["cache_hit"]
    assert "DO_NOT_ECHO" not in json.dumps(cached)
    bad = {**original, "rows": [
        {"date": "2026-11-19", "downloads": 1, "secret": "TOKEN_BAD"},
    ]}
    store.save(key, bad, packages.CACHE_TTL_SECONDS)
    for _ in range(packages.SOURCE["npm"]["daily_cap"]-1):
        store.reserve("npm_package_downloads", 5)
    blocked = run(tmp_path, Client(npm_data()))
    assert blocked["status"] == "local_daily_budget_exhausted"
    assert "TOKEN_BAD" not in repr(blocked)


def test_unavailable_store_never_falls_back_to_new_quota_db():
    class Broken:
        def cached(self, _key):
            raise PermissionError("locked SOURCE SECRET")
    client = Client(npm_data())
    out = packages.discover_package_downloads(
        ecosystem="npm", package="zod", days=7,
        execute=True, observed_at=NOW, cache=Broken(), fetcher=client,
    )
    assert out["status"] == "local_budget_unavailable"
    assert client.calls == [] and out["requests_attempted"] == 0
    assert "SECRET" not in repr(out)


def test_http_enforces_fixed_host_no_redirects_or_proxies(monkeypatch):
    import requests

    class Stream:
        def __init__(self, body: bytes):
            self.raw = BytesIO(body)
        def read(self, cap, decode_content=False):
            assert cap == packages.SOURCE["npm"]["max_response_bytes"]+1
            return self.raw.read(cap)

    class Response:
        status_code = 200
        headers = {"Content-Type": "application/json"}
        raw = Stream(b'{"example":"yes"}')
        def __enter__(self): return self
        def __exit__(self, *_args): return None

    sessions = []

    class Session:
        trust_env = True
        def __init__(self):
            sessions.append(self)
        def get(self, url, *, stream, allow_redirects, timeout, headers):
            assert url == packages._url("zod", "npm", 7)
            assert stream and not allow_redirects and timeout == (5, 12)
            assert self.trust_env is False
            assert "github.com/AKzar1el/mcp-trendpulse" in headers["User-Agent"]
            return Response()
        def close(self): self.closed = True

    monkeypatch.setattr(requests, "Session", Session)
    result = packages._http_get(packages._url("zod", "npm", 7), "npm")
    assert result == (200, {"example": "yes"})
    assert sessions[-1].closed
    Response.raw = Stream(b"x"*(packages.SOURCE["npm"]["max_response_bytes"]+1))
    with pytest.raises(packages.ResponseTooLarge):
        packages._http_get(packages._url("zod", "npm", 7), "npm")
    with pytest.raises(ValueError):
        packages._http_get(
            "https://api.npmjs.org.evil.test/downloads/range/last-week/zod", "npm",
        )


def test_cli_two_preview_commands_json_and_invalid_input():
    runner = CliRunner()
    for cmd, package in (("npm-downloads", "zod"), ("pypi-downloads", "pydantic")):
        result = runner.invoke(cli, [
            "intelligence", cmd, "--package", package, "--days", "7",
            "--format", "json",
        ])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["status"] == "planned"
        assert data["requests_attempted"] == 0
        bad = runner.invoke(cli, [
            "intelligence", cmd, "--package", "https://evil.test/abc",
            "--format", "json",
        ])
        assert bad.exit_code != 0 and "invalid" in bad.output.lower()
