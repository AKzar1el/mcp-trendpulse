"""MJAU M11 Stack Exchange / Stack Overflow bounded-source contracts."""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest
from click.testing import CliRunner

from mcp_trendpulse import intelligence_stackexchange as se
from mcp_trendpulse.cli import cli
from mcp_trendpulse.intelligence_core import BudgetCache

NOW = datetime(2026, 11, 21, 2, 15, tzinfo=timezone.utc)
CREATED = datetime(2026, 11, 20, 18, tzinfo=timezone.utc)
TAG = "python"
TERM = "timeout"


def question(qid=120034567, *, day=CREATED, tag=TAG, title="Python API timeout"):
    return {
        "question_id": qid,
        "title": title,
        "tags": [tag, "asyncio"],
        "link": f"https://stackoverflow.com/questions/{qid}/python-api-timeout",
        "creation_date": int(day.timestamp()),
        "last_activity_date": int(day.timestamp())+300,
        "answer_count": 1, "is_answered": True,
        "accepted_answer_id": 120034568,
        "view_count": 42, "score": 1,
        "owner": {"display_name": "DO_NOT_EXPOSE_AUTHOR"},
        "body": "DO_NOT_EXPOSE_COMMENT_SECRET",
    }


def envelope(*items, more=False, remaining=180, backoff=None, maxquota=10000):
    result = {
        "items": list(items), "has_more": more,
        "quota_remaining": remaining, "quota_max": maxquota,
        "untrusted_token": "DO_NOT_EXPOSE_PROVIDER_EXTRA",
    }
    if backoff is not None:
        result["backoff"] = backoff
    return result


class Fetcher:
    def __init__(self, payload=None, *, code=200, error=None):
        self.payload = envelope(question()) if payload is None else payload
        self.code = code
        self.error = error
        self.calls = []

    def __call__(self, url, params):
        self.calls.append((url, dict(params)))
        if self.error:
            raise self.error
        return self.code, self.payload


def run(tmp_path, client, *, tag=TAG, term=TERM, days=14, limit=10):
    return se.discover_stackoverflow_questions(
        tag=tag, term=term, days=days, limit=limit,
        execute=True, cache=BudgetCache(tmp_path), observed_at=NOW,
        fetcher=client,
    )


def test_preview_never_reads_budget_or_api(monkeypatch):
    monkeypatch.setattr(se, "BudgetCache", lambda *_a: (
        (_ for _ in ()).throw(AssertionError("Preview opened original SQLite"))
    ))
    monkeypatch.setattr(se, "_http_get", lambda *_a: (
        (_ for _ in ()).throw(AssertionError("Preview fetched provider"))
    ))
    out = se.discover_stackoverflow_questions(
        tag=TAG, term=TERM, observed_at=NOW,
    )
    assert out["status"] == "planned"
    assert out["network_performed"] is False
    assert out["requests_attempted"] == 0
    assert out["source"] == "stackexchange_question_mentions"
    assert out["source_url"] == se.URL
    assert out["source_rows_received"] == 0
    assert out["questions"] == []
    assert out["signals"] == []
    assert out["paid_services_used"] is False
    assert out["search_volume_verified"] is False


@pytest.mark.parametrize("options", [
    {"tag": ""},
    {"tag": "Python"},
    {"tag": "python;java"},
    {"tag": "http://stackoverflow.com"},
    {"tag": "..python"},
    {"tag": "python\nURL"},
    {"tag": "@developer"},
    {"term": "ab"},
    {"term": "a" * 81},
    {"term": "https://somewhere.tld"},
    {"term": "hello\nTOKEN"},
    {"term": 42},
    {"days": 6},
    {"days": 31},
    {"days": True},
    {"limit": 0},
    {"limit": 11},
    {"limit": True},
    {"execute": "true"},
    {"observed_at": datetime(2026, 11, 20)},
])
def test_invalid_inputs_fail_closed_before_provider(options):
    params = dict(tag=TAG, term=TERM, observed_at=NOW)
    params.update(options)
    with pytest.raises(ValueError):
        se.discover_stackoverflow_questions(**params)


def test_python_question_realistic_api_shape_and_provenance(tmp_path):
    observed = question()
    client = Fetcher(envelope(
        observed,
        question(120034569, day=CREATED+timedelta(minutes=5),
                 title="Python timeout while awaiting task"),
        more=True, remaining=120,
    ))
    out = run(tmp_path, client)
    assert out["status"] == "observed_partial"
    assert out["source"] == "stackexchange_question_mentions"
    assert out["has_more"] is True
    assert out["quota_remaining"] == 120
    assert out["source_rows_received"] == 2
    assert out["source_rows_rejected"] == 0
    assert out["summary"]["distinct_questions_first_page"] == 2
    assert out["summary"]["distinct_utc_creation_days"] == 1
    assert out["summary"]["with_accepted_answer_first_page"] == 2
    assert out["summary"]["with_answer_first_page"] == 2
    assert out["summary"]["without_answer_first_page"] == 0
    assert out["summary"]["unique_developers_verified"] is False
    assert out["summary"]["customer_demand_verified"] is False
    assert out["requests_attempted"] == 1 and out["network_performed"]
    assert len(out["signals"]) == 1
    sig = out["signals"][0]
    assert sig["metric_type"] == "stackexchange_question_mentions"
    assert sig["value"] == 2
    assert sig["metric_unit"] == "questions"
    assert sig["coverage_status"] == "partial"
    assert sig["provenance"]["method"] == "public_api"
    assert sig["provenance"]["is_observed_search_query"] is False
    assert sig["period"]["granularity"] == "daily"
    assert sig["country"] is None and sig["language"] is None
    assert out["questions"][0]["source_url"].startswith(
        "https://stackoverflow.com/questions/"
    )
    assert "DO_NOT_EXPOSE" not in repr(out)
    endpoint, params = client.calls[0]
    assert endpoint == se.URL
    assert params["site"] == "stackoverflow"
    assert params["tagged"] == TAG
    assert params["q"] == TERM
    assert params["sort"] == "creation" and params["order"] == "desc"
    assert params["page"] == "1" and params["pagesize"] == "10"
    assert params["fromdate"] == str(out["window"]["start_epoch_inclusive"])
    assert int(params["todate"]) == out["window"]["end_epoch_exclusive"]-1
    assert "key" not in params and "access_token" not in params
    repeat = run(tmp_path, client)
    assert repeat["status"] == "observed_partial"
    assert repeat["cache_hit"] is True and repeat["requests_attempted"] == 0
    assert repeat["network_performed"] is False
    assert repeat["questions"] == out["questions"]
    assert len(client.calls) == 1


def test_answered_is_distinct_from_accepted_answer(tmp_path):
    a = question()
    a["accepted_answer_id"] = None
    b = question(120034579)
    b["is_answered"] = False
    b["answer_count"] = 0
    del b["accepted_answer_id"]
    out = run(tmp_path, Fetcher(envelope(a, b)))
    assert out["status"] == "observed"
    assert out["summary"]["with_answer_first_page"] == 1
    assert out["summary"]["without_answer_first_page"] == 1
    assert out["summary"]["with_accepted_answer_first_page"] == 0


def test_source_title_is_unescaped_but_not_html_executed(tmp_path):
    a = question(title="How do I fix &lt;async&gt; timeout?")
    out = run(tmp_path, Fetcher(envelope(a)))
    assert out["status"] == "observed"
    assert out["questions"][0]["title"] == "How do I fix <async> timeout?"
    assert "owner" not in repr(out)


def test_duplicate_question_and_bad_tag_never_fake_multiple_topics(tmp_path):
    a, b = question(), question()
    c = question(120034599, tag="javascript")
    out = run(tmp_path, Fetcher(envelope(a, b, c, more=True)))
    assert out["status"] == "observed_partial"
    assert out["source_rows_received"] == 3
    assert out["source_rows_rejected"] == 2
    assert len(out["questions"]) == 1
    assert out["signals"][0]["value"] == 1


@pytest.mark.parametrize("mutate", [
    lambda q: q.update(question_id=True),
    lambda q: q.update(link="https://evil.tld/questions/120034567/a"),
    lambda q: q.update(link="https://stackoverflow.com/q/120034567"),
    lambda q: q.update(link="https://stackoverflow.com:BAD/questions/120034567/a"),
    lambda q: q.update(creation_date=0),
    lambda q: q.update(is_answered="yes"),
    lambda q: q.update(answer_count=-1),
    lambda q: q.update(accepted_answer_id="1200"),
    lambda q: q.update(tags=["java"]),
    lambda q: q.update(title="bad\nSECRET"),
])
def test_corrupt_source_questions_not_treated_as_observed(tmp_path, mutate):
    row = question()
    mutate(row)
    out = run(tmp_path, Fetcher(envelope(row)))
    assert out["status"] == "invalid_source_shape"
    assert out["questions"] == []
    assert out["signals"] == []
    assert "SECRET" not in repr(out)


def test_empty_success_no_data_not_zero_community_interest(tmp_path):
    out = run(tmp_path, Fetcher(envelope()))
    assert out["status"] == "no_data"
    assert out["signals"] == []
    assert out["summary"]["distinct_questions_first_page"] == 0
    assert out["summary"]["search_volume_verified"] is False
    hit = run(tmp_path, Fetcher(error=RuntimeError("MUST_NOT_FETCH")))
    assert hit["status"] == "no_data"
    assert hit["cache_hit"] and hit["requests_attempted"] == 0


@pytest.mark.parametrize("payload", [
    {"items": [], "has_more": True, "quota_remaining": 123},
    {"items": "PRIVATE", "has_more": False, "quota_remaining": 123},
    {"items": [], "has_more": "false", "quota_remaining": 123},
    {"items": [], "has_more": False, "quota_remaining": "123"},
    {"items": [], "has_more": False, "quota_remaining": True},
    {"items": [], "has_more": False, "quota_remaining": 10, "quota_max": 2},
    {"error_id": 502, "error_message": "SECRET_PROVIDER_ERROR"},
])
def test_provider_shape_or_error_envelope_not_no_data(tmp_path, payload):
    out = run(tmp_path, Fetcher(payload))
    assert out["status"] in ("invalid_source_shape", "provider_error")
    assert out["questions"] == []
    assert "SECRET" not in repr(out)


def test_very_long_provider_backoff_is_persisted_not_clamped_to_300(tmp_path):
    seconds = 3900
    client = Fetcher(envelope(question(), backoff=seconds))
    out = run(tmp_path, client)
    assert out["status"] == "observed"
    assert out["backoff_seconds"] == seconds
    store = BudgetCache(tmp_path)
    with store._connect() as conn:
        deadline = conn.execute(
            "SELECT until FROM cooldown WHERE source=?", (se.SOURCE,),
        ).fetchone()[0]
    assert deadline > time.time()+3500
    other = Fetcher()
    blocked = run(tmp_path, other, term="another term")
    assert blocked["status"] == "provider_cooldown"
    assert blocked["requests_attempted"] == 0 and other.calls == []


def test_200_error_with_backoff_honored_without_retry(tmp_path):
    client = Fetcher({
        "error_id": 502, "error_name": "throttle_violation",
        "error_message": "PRIVATE_SECRET", "backoff": 1200,
    })
    out = run(tmp_path, client)
    assert out["status"] == "provider_error"
    assert len(client.calls) == 1
    assert "PRIVATE_SECRET" not in repr(out)
    assert BudgetCache(tmp_path).blocked(se.SOURCE) is True


def test_provider_quota_zero_triggers_durable_hold_until_utc_reset(tmp_path):
    client = Fetcher(envelope(question(), remaining=0, maxquota=100))
    out = run(tmp_path, client)
    assert out["status"] == "observed"
    with BudgetCache(tmp_path)._connect() as conn:
        deadline = conn.execute(
            "SELECT until FROM cooldown WHERE source=?", (se.SOURCE,),
        ).fetchone()[0]
    assert deadline-time.time() > 60
    other = Fetcher()
    blocked = run(tmp_path, other, term="something else")
    assert blocked["status"] == "provider_cooldown"
    assert other.calls == []
    repeated = run(tmp_path, Fetcher(error=RuntimeError("no request")))
    assert repeated["status"] == "observed" and repeated["cache_hit"]


@pytest.mark.parametrize("code", [429, 503])
def test_http_rate_limit_and_no_automatic_retry(tmp_path, code):
    client = Fetcher({}, code=code)
    out = run(tmp_path, client)
    assert out["status"] == "provider_rate_limited"
    assert len(client.calls) == 1
    assert BudgetCache(tmp_path).blocked(se.SOURCE) is True


def test_existing_daily_source_quota_3_requests_then_no_network(tmp_path):
    db = BudgetCache(tmp_path)
    for _ in range(se.UTC_DAILY_CAP):
        db.reserve(se.SOURCE, se.UTC_DAILY_CAP)
    client = Fetcher()
    blocked = run(tmp_path, client)
    assert blocked["status"] == "local_daily_budget_exhausted"
    assert blocked["network_performed"] is False
    assert client.calls == []


def test_corrupted_cache_extras_never_exposed_and_bad_identity_rejected(tmp_path):
    first = run(tmp_path, Fetcher())
    assert first["status"] == "observed"
    key = se._key(TAG, TERM, 10, se._window(14, NOW))
    store = BudgetCache(tmp_path)
    clean = store.cached(key)
    assert isinstance(clean, dict)
    store.save(key, {**clean, "secret": "DONT_ECHO_TOKEN"}, se.CACHE_SECONDS)
    hit = run(tmp_path, Fetcher(error=RuntimeError("none")))
    assert hit["cache_hit"]
    assert "DONT_ECHO_TOKEN" not in repr(hit)
    store.save(key, {**clean, "questions": [{
        "question_id": 1, "sensitive": "RAW_AUTH_TOKEN",
    }]}, se.CACHE_SECONDS)
    for _ in range(se.UTC_DAILY_CAP-1):
        store.reserve(se.SOURCE, se.UTC_DAILY_CAP)
    blocked = run(tmp_path, Fetcher())
    assert blocked["status"] == "local_daily_budget_exhausted"
    assert "RAW_AUTH_TOKEN" not in repr(blocked)


def test_local_storage_error_never_uses_alternative_quota_db():
    class Broken:
        def cached(self, _key):
            raise OSError("PRIVATE_CACHE_PATH")
    client = Fetcher()
    out = se.discover_stackoverflow_questions(
        tag=TAG, term=TERM, execute=True,
        cache=Broken(), fetcher=client, observed_at=NOW,
    )
    assert out["status"] == "local_budget_unavailable"
    assert out["requests_attempted"] == 0 and client.calls == []
    assert "PRIVATE" not in repr(out)


def test_transport_fixed_host_no_proxy_no_redirect_bounded_response(monkeypatch):
    import requests

    class Stream:
        def __init__(self, blob):
            self.buffer = BytesIO(blob)
        def read(self, limit, decode_content=False):
            assert limit == se.MAX_RESPONSE_BYTES+1
            return self.buffer.read(limit)

    class Response:
        status_code = 200
        headers = {"Content-Type": "application/json"}
        raw = Stream(b'{"items":[],"has_more":false,"quota_remaining":100}')
        def __enter__(self): return self
        def __exit__(self, *_a): return None

    sessions = []
    class Session:
        trust_env = True
        def __init__(self): sessions.append(self)
        def get(self, url, *, params, timeout, stream, allow_redirects, headers):
            assert self.trust_env is False
            assert url == se.URL and params["page"] == "1"
            assert timeout == (5,12) and stream and not allow_redirects
            assert "github.com/AKzar1el/mcp-trendpulse" in headers["User-Agent"]
            return Response()
        def close(self): self.closed = True

    monkeypatch.setattr(requests, "Session", Session)
    params = se._params(TAG, TERM, 10, se._window(14, NOW))
    code, obj = se._http_get(se.URL, params)
    assert code == 200 and obj["has_more"] is False
    assert sessions[-1].closed is True
    Response.raw = Stream(b"x"*(se.MAX_RESPONSE_BYTES+1))
    with pytest.raises(se.ResponseTooLarge):
        se._http_get(se.URL, params)
    with pytest.raises(ValueError):
        se._http_get("https://api.stackexchange.com.evil.tld/2.3/search/advanced", params)


def test_cli_offline_preview_is_json_and_no_quota():
    runner = CliRunner()
    good = runner.invoke(cli, [
        "intelligence", "stackexchange-questions",
        "--tag", "python", "--term", "timeout",
        "--days", "14", "--limit", "10", "--format", "json",
    ])
    assert good.exit_code == 0, good.output
    report = json.loads(good.output)
    assert report["status"] == "planned"
    assert not report["network_performed"]
    bad = runner.invoke(cli, [
        "intelligence", "stackexchange-questions",
        "--tag", "https://stack.invalid", "--format", "json",
    ])
    assert bad.exit_code != 0
    assert "invalid" in bad.output.lower()
