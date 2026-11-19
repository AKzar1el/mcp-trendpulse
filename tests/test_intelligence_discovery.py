"""Synthetic, deterministic falsification tests for keyword-free trend discovery.

Invented records are only fixtures. A successful collector is not customer
validation, trend growth, population prevalence or proof of buyer budgets.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest

from mcp_trendpulse import intelligence_discovery as discovery
from mcp_trendpulse.intelligence_core import IntelligenceError, plan_source

ASOF = "2026-11-19"


def observed(source, items, *, cached=False):
    return {
        "source": source, "status": "observed", "cache_hit": cached,
        "observations": {"record_count": len(items), "sample": items},
    }


def work(id="W2741809807", day="2026-11-18",
         title="New battery recycling lifecycle data"):
    return {
        "id": "https://openalex.org/" + id,
        "display_name": title, "publication_date": day,
        "primary_topic": {"display_name": "Battery recycling systems"},
    }


def complaint(id="101", day="2026-11-18", issue="Incorrect information"):
    return {
        "public_complaint_id": id, "product": "Credit card",
        "issue": issue, "date_received": day,
        "narrative": "NEVER_LEAK_THIS_PRIVATE_STRING",
        "company": "TEST COMPANY",
    }


def notice(id="2026-1234", day="2026-11-18",
           title="Battery recycling lifecycle equipment procurement"):
    return {
        "publication-number": id, "publication-date": day,
        "notice-title": title, "buyer-name": "Test government",
    }


def report(*snapshots, days=30):
    return discovery.summarize_discovery(list(snapshots), as_of=ASOF, lookback_days=days)


def test_seedless_independent_source_title_overlap_is_research_candidate():
    output = report(
        observed("openalex", [work()]),
        observed("ted", [notice()]),
        observed("cfpb", [complaint()]),
    )
    assert output["discovery_query_mode"] == "no_seed_topics_or_sector_keywords"
    assert output["recent_observations"] == 3
    matches = [x for x in output["candidates"] if x["label"] == "battery recycling"]
    assert matches, output["candidates"]
    x = matches[0]
    assert x["investigation_priority"] == 2
    assert x["distinct_source_classes"] == 2
    assert x["unique_recent_records_in_sample"] == 2
    assert set(x["sources"]) == {"ted", "openalex"}
    assert x["same_buyer_verified"] is False
    assert x["commercial_budget_verified"] is False
    assert x["growth_direction"] == "unknown_without_comparable_population_history"
    assert output["growth_rate_verified"] is False
    assert output["paid_buyers_verified"] is False


def test_independent_cfpb_complaints_repeat_same_public_category():
    output = report(observed("cfpb", [
        complaint("101"), complaint("102"), complaint("103"),
    ]))
    assert output["candidate_count"] >= 1
    matches = [x for x in output["candidates"] if x["basis"] ==
               "cfpb_public_product_issue_categories"]
    assert len(matches) == 1
    candidate = matches[0]
    assert "Credit card" in candidate["label"]
    assert candidate["unique_recent_records_in_sample"] == 3
    assert candidate["investigation_priority"] == 1
    assert candidate["distinct_source_classes"] == 1
    assert candidate["commercial_budget_verified"] is False
    assert "NEVER_LEAK_THIS_PRIVATE_STRING" not in repr(output)


def test_openalex_primary_topic_groups_two_different_recent_publications():
    output = report(observed("openalex", [
        work(), work("W2741809808", "2026-11-17", "Biological battery recycling"),
    ]))
    one = next(x for x in output["candidates"]
               if x["basis"] == "openalex_assigned_primary_topic")
    assert one["unique_recent_records_in_sample"] == 2
    assert one["investigation_priority"] == 1
    assert one["label"] == "Battery recycling systems"
    assert all(x["source"] == "openalex" for x in one["examples"])


def test_openalex_without_primary_topic_keeps_observation_but_no_fake_theme():
    work_without_topic = work()
    work_without_topic.pop("primary_topic")
    output = report(observed("openalex", [work_without_topic]))
    assert output["candidate_count"] == 0
    assert output["recent_observations"] == 1
    assert output["sample_examples_by_source"]["openalex"][0]["theme"] == ""


def test_future_and_stale_records_not_recent_just_because_queried():
    result = report(observed("openalex", [
        work("W2741809807", "2026-11-20"),
        work("W2741809808", "2025-10-05"),
        work("W2741809809", "2026-11-19"),
    ]))
    assert result["recent_observations"] == 1
    assert result["candidate_count"] == 0


def test_duplicate_source_ids_are_deduplicated_before_candidate_count():
    a = complaint()
    result = report(observed("cfpb", [a, a]))
    assert result["recent_observations"] == 1
    assert result["candidate_count"] == 0


def test_provider_failure_is_degraded_coverage_not_zero_market():
    x = report(
        {"source": "openalex", "status": "unavailable", "http_status": 429,
         "reason": {"token": "DO_NOT_ECHO"}},
        observed("cfpb", [complaint(), complaint("102")]),
    )
    assert x["source_health_degraded"] is True
    assert x["source_coverage"][0]["http_status"] == 429
    assert x["candidate_count"] == 1
    assert x["source_coverage"][0]["status"] == "unavailable"
    assert "DO_NOT_ECHO" not in repr(x)
    assert x["growth_rate_verified"] is False


def test_single_latest_publication_is_not_fake_market_trend():
    x = report(observed("openalex", [work()]))
    assert x["candidate_count"] == 0
    assert x["recent_observations"] == 1


def test_source_projected_record_shape_errors_are_inconclusive():
    x = report({
        "source": "openalex", "status": "observed",
        "observations": {"record_count": 2, "sample": {"oops": True}},
    })
    assert x["source_coverage"][0]["status"] == "invalid_source_shape"
    assert x["candidate_count"] == 0


def test_twenty_record_bulky_provider_snapshots_keep_all_bounded_evidence(monkeypatch):
    # Reproduces the exact --limit 20 failure without live APIs, credentials,
    # or reliance on current wall-clock date. Unused provider metadata is
    # deliberately large, but the normalized 60 public records are small.
    day = date.today().isoformat()
    bulky = "PRIVATE_UNUSED_PROVIDER_CONTENT_" + ("X" * 2900)
    snapshots = [
        observed("openalex", [
            {**work(f"W{2741809807 + i}", day), "authorships": bulky}
            for i in range(20)
        ]),
        observed("cfpb", [
            {**complaint(str(100 + i), day), "unused_provider_metadata": bulky}
            for i in range(20)
        ]),
        observed("ted", [
            {**notice(f"{805001 + i}-2026", day),
             "unused_provider_metadata": bulky}
            for i in range(20)
        ]),
    ]
    raw_bytes = len(json.dumps(snapshots, ensure_ascii=False).encode("utf-8"))
    assert discovery.MAX_SNAPSHOT_BYTES < raw_bytes < discovery.MAX_SOURCE_INPUT_BYTES
    direct = discovery.summarize_discovery(snapshots, as_of=day)
    assert direct["recent_observations"] == 60
    assert [x["recent_valid_records"] for x in direct["source_coverage"]] == [20, 20, 20]
    assert "PRIVATE_UNUSED_PROVIDER_CONTENT_" not in repr(direct)
    assert "NEVER_LEAK_THIS_PRIVATE_STRING" not in repr(direct)

    calls = []
    by_source = {x["source"]: x for x in snapshots}

    def fake_collect(plan, **kwargs):
        assert kwargs.get("fetch") is True
        calls.append(plan.source)
        return by_source[plan.source]

    monkeypatch.setattr(discovery, "collect", fake_collect)
    executed = discovery.discover_current(execute=True, limit=20, env={})
    assert calls == ["openalex", "cfpb", "ted"]  # No additional requests.
    assert executed["recent_observations"] == 60
    assert executed["queries_budgeted"] == 3
    assert "PRIVATE_UNUSED_PROVIDER_CONTENT_" not in repr(executed)


def test_oversized_untrusted_discovery_input_still_refused():
    huge = observed("cfpb", [
        {**complaint(), "unused_provider_metadata":
         "X" * (discovery.MAX_SOURCE_INPUT_BYTES + 1)}
    ])
    with pytest.raises(ValueError, match="bounded three-provider budget"):
        report(huge)


@pytest.mark.parametrize("invalid", [
    [], [None], [123], [
        {"source": "unknown", "status": "observed"}],
    [{"source": "cfpb", "status": "observed"}] * 2,
])
def test_untrusted_snapshot_input_is_bounded_and_validated(invalid):
    with pytest.raises(ValueError):
        report(*invalid)


@pytest.mark.parametrize("days", [0, 6, 91, True, "30"])
def test_unbounded_lookback_refused(days):
    with pytest.raises(ValueError):
        discovery.summarize_discovery(
            [observed("cfpb", [complaint()])], as_of=ASOF, lookback_days=days,
        )


def test_openalex_seedless_plan_has_freshness_filter_not_paid_sync():
    now = date.today()
    cutoff = now - timedelta(days=29)
    plan = plan_source("openalex", discover=True,
                       lookback_days=30, limit=12, env={})
    query = parse_qs(urlsplit(plan.url).query)
    assert "search" not in query
    assert query["filter"] == [
        f"from_publication_date:{cutoff.isoformat()},"
        f"to_publication_date:{now.isoformat()}"
    ]
    assert query["sort"] == ["publication_date:desc"]
    assert "primary_topic" in query["select"][0]
    assert "from_updated_date" not in plan.url
    assert "from_created_date" not in plan.url
    assert "api_key=" not in plan.url


@pytest.mark.parametrize("source", ["cfpb", "ted", "github_issues", "epo"])
def test_discovery_flag_not_available_to_other_providers(source):
    with pytest.raises(IntelligenceError):
        plan_source(source, discover=True, lookback_days=30, env={})


def test_openalex_discovery_plan_remains_key_private():
    plan = plan_source("openalex", discover=True, lookback_days=30,
                       limit=12, env={"TRENDPULSE_INTEL_OPENALEX_KEY": "SECRETPASS"})
    assert plan.headers["Authorization"] == "Bearer SECRETPASS"
    assert "SECRETPASS" not in json.dumps(plan.public())
    assert "SECRETPASS" not in plan.url


def test_seedless_plan_is_network_free(monkeypatch):
    def deny(*_args, **_kwargs):
        raise AssertionError("Plan-only must not access public APIs")

    monkeypatch.setattr(discovery, "collect", deny)
    plan = discovery.discover_current(execute=False, env={})
    assert plan["status"] == "planned"
    assert plan["network_performed"] is False
    assert len(plan["plans"]) == 3
    assert {p["source"] for p in plan["plans"]} == {"openalex", "cfpb", "ted"}
    assert all(p["network_performed"] is False for p in plan["plans"])


def test_explicit_execution_produces_clean_summary(monkeypatch):
    fixtures = {
        "openalex": observed("openalex", [work(), work("W2741809808")]),
        "cfpb": observed("cfpb", [complaint(), complaint("102")]),
        "ted": observed("ted", [notice(), notice("2026-4321")]),
    }
    def fake_collect(plan, **kwargs):
        if not kwargs.get("fetch"):
            raise AssertionError("Execution must be explicitly opted in")
        return {**fixtures[plan.source], "data": {
            "private_narrative": "UNTRUSTED_RAW_PROVIDER_FIELDS",
        }}

    monkeypatch.setattr(discovery, "collect", fake_collect)
    result = discovery.discover_current(execute=True, env={})
    assert result["queries_budgeted"] == 3
    assert result["recent_observations"] == 6
    assert result["network_performed"] is True
    assert result["candidate_count"] > 0
    assert result["user_credentials_exposed"] is False
    assert "UNTRUSTED_RAW_PROVIDER_FIELDS" not in repr(result)
    assert "NEVER_LEAK_THIS_PRIVATE_STRING" not in repr(result)


def test_stratified_ted_plan_is_disjoint_bounded_and_network_free(monkeypatch):
    def forbid(*_a, **_kw):
        raise AssertionError("Planning may not fetch source data")
    monkeypatch.setattr(discovery, "collect", forbid)
    planned = discovery.discover_current(
        limit=20, lookback_days=30, execute=False,
        ted_date_slices=3, env={},
    )
    assert planned["request_count"] == 5
    assert planned["source_count"] == 3
    assert [p["source"] for p in planned["plans"]] == [
        "openalex", "cfpb", "ted", "ted", "ted"
    ]
    windows = planned["ted_windows"]
    assert [w["requested_limit"] for w in windows] == [7, 7, 6]
    assert windows[0]["through"] == date.today().isoformat()
    assert windows[-1]["from"] == (date.today() - timedelta(days=29)).isoformat()
    for older, newer in zip(windows[::-1], windows[-2::-1]):
        assert date.fromisoformat(older["through"]) + timedelta(days=1) == date.fromisoformat(newer["from"])
    for plan, window in zip(planned["plans"][2:], windows):
        start = window["from"].replace("-", "")
        end = window["through"].replace("-", "")
        assert f"PD = ({start} <> {end})" in plan["body"]["query"]
        assert plan["body"]["limit"] == window["requested_limit"]
        assert "notice-type IN (cn-standard cn-social cn-desg)" in plan["body"]["query"]
        assert "classification-cpv" not in plan["body"]["query"]


@pytest.mark.parametrize("bad,limit", [(0, 20), (2, 20), (4, 20),
                                        (True, 20), ("3", 20), (3, 2)])
def test_stratification_invalid_modes_and_too_small_limits_rejected(bad, limit):
    with pytest.raises(ValueError):
        discovery.discover_current(
            execute=False, ted_date_slices=bad, limit=limit, env={},
        )


def test_stratified_live_path_bounded_three_ted_windows_and_private_history(
    monkeypatch, tmp_path,
):
    calls = []
    def fake_collect(plan, **kwargs):
        assert kwargs["fetch"] is True
        calls.append(plan.source)
        if plan.source == "openalex":
            return observed("openalex", [work(day=date.today().isoformat())])
        if plan.source == "cfpb":
            return observed("cfpb", [complaint(day=date.today().isoformat())])
        match = re.search(r"PD = \((\d{8}) <> (\d{8})\)", plan.body["query"])
        assert match
        source_day = date.fromisoformat(
            f"{match.group(2)[:4]}-{match.group(2)[4:6]}-{match.group(2)[6:]}"
        ).isoformat()
        idx = calls.count("ted")
        rows = []
        for i in range(plan.body["limit"]):
            n = 800000 + 25 * idx + i
            raw = _rich_ted(f"{n}-2026", f"Buyer {n}", "72222300")
            raw["publication-date"] = source_day
            raw["unneeded_personal_vendor_metadata"] = "NEVER_LEAK_VENDOR"
            rows.append(raw)
        return observed("ted", rows)

    monkeypatch.setattr(discovery, "collect", fake_collect)
    result = discovery.discover_current(
        execute=True, limit=20, lookback_days=30,
        ted_date_slices=3, env={},
    )
    assert calls == ["openalex", "cfpb", "ted", "ted", "ted"]
    assert result["queries_budgeted"] == 5
    assert len(result["source_coverage"]) == 3
    assert result["recent_observations"] == 22
    assert result["source_health_degraded"] is False
    assert result["ted_sampling_audit"]["observed_notice_count"] == 20
    assert result["ted_sampling_audit"]["publication_days_represented"] == 3
    assert result["ted_sampling_audit"]["observed_date_windows"] == 3
    assert result["ted_sampling_audit"]["failed_date_windows"] == 0
    review = result["procurement_review"]
    assert review["selection_strategy"] == (
        "round_robin_qualified_notices_across_ted_date_windows"
    )
    assert [w["review_selected"] for w in review["per_date_window"]] == [2, 2, 2]
    assert [w["displayed_notices"] for w in review["per_date_window"]] == [3, 3, 2]
    assert [w["sampled_notices"] for w in review["per_date_window"]] == [7, 7, 6]
    assert review["software_it_not_review_qualified"] == 0
    assert result["ted_sampling_audit"]["sector_share_or_growth_estimable"] is False
    assert result["ted_sampling_audit"]["any_date_window_hit_record_cap"] is True
    assert result["growth_rate_verified"] is False
    assert "NEVER_LEAK_VENDOR" not in repr(result)
    text = discovery.format_discovery_report(result)
    assert "TED OPT-IN TIME-STRATIFIED SAMPLING" in text
    assert "3/3 date windows observed" in text
    assert "At least one TED date-window page hit" in text
    stored = discovery.record_discovery_history(result, tmp_path / "test_history.sqlite")
    assert stored["raw_records_saved"] is False
    contents = (tmp_path / "test_history.sqlite").read_bytes().decode("latin1")
    assert "Buyer" not in contents and "NEVER_LEAK_VENDOR" not in contents


def test_date_balanced_review_and_unqualified_software_notice_visible():
    today = date(2026, 11, 19)
    windows = discovery._ted_date_windows(today, 30, 20)
    notices = []
    for i, (_, end, _) in enumerate(windows):
        for j in range(4):
            row = _rich_ted(
                f"{810000 + i * 10 + j}-2026",
                f"Window Buyer {i} {j}", "90510000",
            )
            row["publication-date"] = end.isoformat()
            notices.append(row)
    software = _rich_ted(
        "812000-2026", "IT Buyer With Missing Projection Date", "72222300",
    )
    software["publication-date"] = windows[2][1].isoformat()
    software.pop("deadline-receipt-tender-date-lot")
    notices.append(software)
    result = discovery.summarize_discovery(
        [observed("ted", notices)], as_of=today.isoformat(),
        ted_date_windows=windows,
    )
    review = result["procurement_review"]
    assert review["qualified_notices_in_bounded_sample"] == 12
    assert review["selected_for_review"] == 6
    assert [x["review_selected"] for x in review["per_date_window"]] == [2, 2, 2]
    assert review["software_it_not_review_qualified"] == 1
    assert review["software_it_exclusion_reason_counts"] == {
        "no_lot_deadline_in_sample_projection": 1,
    }
    shown = result["procurement_observations"]
    assert len(shown) == 8
    assert sum(x["buyer_side_review_selected"] for x in shown) == 6
    it_context = [n for n in shown if n["main_cpv_software_it_category"]]
    assert len(it_context) == 1
    assert it_context[0]["buyer_side_review_selected"] is False
    assert it_context[0]["buyer_side_review_qualified"] is False
    assert it_context[0]["review_exclusion_reasons"] == [
        "no_lot_deadline_in_sample_projection"
    ]
    assert not it_context[0]["still_open_tender_verified"]
    output = discovery.format_discovery_report(result)
    assert "Software/IT primary CPV notices not review-qualified: 1" in output
    assert "lot deadline missing in projection: 1" in output
    assert "review criteria unmet: no_lot_deadline_in_sample_projection" in output


def test_time_window_review_does_not_claim_empty_window_is_zero_market():
    today = date(2026, 11, 19)
    windows = discovery._ted_date_windows(today, 30, 20)
    ted = []
    for i in (0, 2):
        for j in range(4):
            row = _rich_ted(
                f"{813000 + i * 10 + j}-2026",
                f"Buyer {i}-{j}", "90510000",
            )
            row["publication-date"] = windows[i][1].isoformat()
            ted.append(row)
    x = discovery.summarize_discovery(
        [observed("ted", ted)], as_of=today.isoformat(),
        ted_date_windows=windows,
    )
    assert [d["review_qualified"] for d in x["procurement_review"]["per_date_window"]] == [
        4, 0, 4
    ]
    assert [d["review_selected"] for d in x["procurement_review"]["per_date_window"]] == [
        3, 0, 3
    ]
    assert x["growth_rate_verified"] is False
    assert x["ted_sampling_audit"]["sector_share_or_growth_estimable"] is False
    assert all(not n["still_open_tender_verified"]
               for n in x["procurement_observations"])


def test_stratified_partial_failures_and_out_of_window_records(monkeypatch):
    calls = 0
    def fake_collect(plan, **kwargs):
        nonlocal calls
        if plan.source == "openalex":
            return observed("openalex", [])
        if plan.source == "cfpb":
            return observed("cfpb", [])
        calls += 1
        if calls == 2:
            return {"source": "ted", "status": "unavailable", "http_status": 429}
        match = re.search(r"PD = \((\d{8}) <> (\d{8})\)", plan.body["query"])
        day = date.fromisoformat(
            f"{match.group(2)[:4]}-{match.group(2)[4:6]}-{match.group(2)[6:]}"
        ).isoformat()
        good = _rich_ted(f"{804000+calls}-2026", f"Buyer {calls}", "72222300")
        good["publication-date"] = day
        wrong = _rich_ted(f"{805000+calls}-2026", "Wrong Window", "72222300")
        wrong["publication-date"] = "2020-01-01"
        return observed("ted", [good, wrong])

    monkeypatch.setattr(discovery, "collect", fake_collect)
    x = discovery.discover_current(
        execute=True, limit=12, ted_date_slices=3, env={},
    )
    audit = x["ted_sampling_audit"]
    assert audit["observed_date_windows"] == 2
    assert audit["failed_date_windows"] == 1
    assert x["source_health_degraded"] is True
    assert next(c for c in x["source_coverage"] if c["source"] == "ted")["partial_date_window_coverage"] is True
    assert audit["observed_notice_count"] == 2
    assert audit["date_window_results"][0]["dropped_outside_window"] == 1
    assert audit["date_window_results"][1]["status"] == "unavailable"
    assert audit["date_window_results"][2]["dropped_outside_window"] == 1
    assert "PARTIAL COVERAGE" in discovery.format_discovery_report(x)


def test_opt_in_hashed_history_never_stores_titles_or_urls(tmp_path):
    x = report(observed("cfpb", [complaint(), complaint("102")]))
    path = tmp_path / "discovery.sqlite"
    y = discovery.record_discovery_history(x, path)
    again = discovery.record_discovery_history(x, path)
    assert y["raw_records_saved"] is False
    assert again["candidate_count"] == y["candidate_count"]
    with sqlite3.connect(path) as con:
        rows = con.execute("SELECT day,candidate_hash,sample_records "
                           "FROM discovery_candidates").fetchall()
    assert len(rows) == 1
    assert len(rows[0][1]) == 14
    assert rows[0][2] == 2
    contents = path.read_bytes().decode("latin1")
    assert "Credit card" not in contents
    assert "consumerfinance.gov" not in contents
    assert "NEVER_LEAK" not in contents


def test_no_history_accepted_from_unexecuted_plan(tmp_path):
    plan = discovery.discover_current(execute=False, env={})
    with pytest.raises(ValueError):
        discovery.record_discovery_history(plan, tmp_path / "bad.sqlite")


def test_text_output_is_useful_even_with_zero_candidates():
    x = report(observed("openalex", [work()]))
    output = discovery.format_discovery_report(x)
    assert "No recurring current themes" in output
    assert "openalex: observed" in output
    assert "New battery recycling" in output
    assert "Growth, buyer budgets and market size: NOT VERIFIED." in output


def test_future_publication_date_is_rejected_with_explainable_coverage():
    report = discovery.summarize_discovery([
        observed("openalex", [
            work("W2741809807", "2026-11-20"),
            work("W2741809808", "2026-11-18"),
        ]),
    ], as_of=ASOF)
    assert report["source_coverage"][0]["future_dated_records_rejected"] == 1
    assert report["source_coverage"][0]["recent_valid_records"] == 1
    assert "future-dated rejected:1" in discovery.format_discovery_report(report)



def test_multilingual_ted_notice_becomes_source_attributed_procurement_example():
    from mcp_trendpulse.intelligence_observations import _entry

    actual_shape = {
        "publication-number": "683567-2026",
        "publication-date": "2026-11-18+01:00",
        "notice-title": {
            "deu": ["Batterie-Recycling Anlage"],
            "eng": ["Battery recycling facility services"],
        },
        "buyer-name": {"deu": ["Stadt Beispiel"], "eng": ["Example Municipality"]},
        "official-language": ["DEU"],
        "notice-type": "cn-standard",
    }
    parsed = _entry("ted", actual_shape, date(2026, 11, 19))
    assert parsed is not None
    assert parsed["title"] == "Battery recycling facility services"
    assert parsed["title_language"] == "eng"
    assert parsed["buyer_name"] == "Example Municipality"
    assert parsed["buyer_language"] == "eng"
    assert parsed["reference"] == "https://ted.europa.eu/en/notice/-/detail/683567-2026"
    assert parsed["event_date"] == "2026-11-18"
    r = report(observed("ted", [actual_shape]))
    assert r["recent_observations"] == 1
    assert r["candidate_count"] == 0
    notice = r["procurement_observations"][0]
    assert notice["title"] == "Battery recycling facility services"
    assert notice["buyer_name"] == "Example Municipality"
    assert notice["procurement_stage"] == "contract_notice_not_award"
    assert notice["buying_intent_verified"] is False
    assert notice["contract_value_verified"] is False
    output = discovery.format_discovery_report(r)
    assert "Recent EU procurement notices" in output
    assert "buyer published: Example Municipality" in output
    assert "title language: eng" in output
    assert "683567-2026" in output


def test_ted_official_language_fallback_is_not_invented_translation():
    from mcp_trendpulse.intelligence_observations import _entry

    x = notice("777777-2026", "2026-11-19", "placeholder")
    x["notice-title"] = {
        "fra": ["Prestation sanitaire"],
        "deu": ["Gesundheitssysteme"],
    }
    x["buyer-name"] = {"fra": ["Ville Exemple"]}
    x["official-language"] = ["FRA"]
    result = _entry("ted", x, date(2026, 11, 19))
    assert result is not None
    assert result["title"] == "Prestation sanitaire"
    assert result["title_language"] == "fra"
    assert result["buyer_name"] == "Ville Exemple"
    assert result["buyer_language"] == "fra"
    assert result["reference"].endswith("777777-2026")


def test_unusable_ted_title_does_not_count_as_quality_procurement_observation():
    x = notice("777777-2026")
    x["notice-title"] = {"deu": [{"untrusted_text": "DO_NOT_EMIT_THIS"}]}
    r = report(observed("ted", [x]))
    assert r["recent_observations"] == 0
    assert r["procurement_observations"] == []
    assert r["source_coverage"][0]["recent_valid_records"] == 0
    assert "DO_NOT_EMIT_THIS" not in repr(r)


def test_source_balanced_report_does_not_erase_nonrepeat_procurement_and_research():
    r = report(
        observed("cfpb", [
            complaint("101"), complaint("102"), complaint("103"),
        ]),
        observed("ted", [{
            "publication-number": "572118-2026",
            "publication-date": "2026-11-18",
            "notice-title": {"eng": ["Clinical equipment maintenance"]},
            "buyer-name": {"eng": ["Public hospital"]},
            "notice-type": "cn-standard",
        }]),
        observed("openalex", [work()]),
    )
    assert r["candidate_count"] == 1
    assert r["source_balanced_examples_not_additional_trend_candidates"] is True
    assert len(r["procurement_observations"]) == 1
    assert len(r["research_observations"]) == 1
    out = discovery.format_discovery_report(r)
    assert "distinct source records" in out
    assert "not independent buyers or verified market growth" in out
    assert "Clinical equipment maintenance" in out
    assert "Recent scholarly work" in out
    assert "Provider topic (algorithmic)" in out
    assert "Research activity" not in out or "research activity" in out


def test_ted_award_notice_is_not_published_as_new_open_tender():
    x = notice("683567-2026")
    x["notice-type"] = "can-standard"
    result = report(observed("ted", [x]))
    assert result["procurement_observations"][0]["procurement_stage"] == (
        "contract_award_notice_not_open_tender"
    )
    assert result["candidate_count"] == 0


def test_discover_uses_recent_first_published_notice_sort():
    plan = discovery.discover_current(execute=False, env={})
    ted = next(p for p in plan["plans"] if p["source"] == "ted")
    assert "SORT BY publication-date DESC" in ted["body"]["query"]
    assert "PD = (" in ted["body"]["query"]
    assert ted["body"]["limit"] == 12



def test_seedless_ted_competition_only_query_is_sector_agnostic():
    plan = discovery.discover_current(execute=False, env={})
    ted = next(p for p in plan["plans"] if p["source"] == "ted")
    query = ted["body"]["query"]
    assert "PD = (" in query
    assert "notice-type IN (cn-standard cn-social cn-desg)" in query
    assert query.count("notice-type IN (") == 1
    assert query.endswith("SORT BY publication-date DESC")
    # No predefined industry, product, buyer or CPV keywords: only notice stage.
    assert "classification-cpv" not in query
    assert " FT " not in query
    assert "can-standard" not in query and "pin-only" not in query


def _rich_ted(id, buyer, cpv, *, kind="cn-standard",
              deadline="2026-12-11", estimated="65000.00", currency="EUR"):
    return {
        "publication-number": id,
        "publication-date": "2026-11-19",
        "notice-title": {"eng": [f"Procurement of specialist services {id}"]},
        "buyer-name": {"eng": [buyer]},
        "buyer-country": ["DEU"],
        "notice-type": kind,
        "main-classification-proc": cpv,
        "classification-cpv": [cpv, cpv, "72222300"],
        "deadline-receipt-tender-date-lot": [deadline],
        "estimated-value-proc": estimated,
        "estimated-value-cur-proc": currency,
    }


def test_seedless_ted_enrichment_preserves_only_published_source_values():
    from mcp_trendpulse.intelligence_observations import _entry

    notice = _rich_ted("804511-2026", "City Data Office", "72000000")
    normal = _entry("ted", notice, date(2026, 11, 19))
    assert normal["buyer_country_code"] == "DEU"
    assert normal["main_cpv_code"] == "72000000"
    assert normal["cpv_codes"] == ["72000000", "72222300"]
    assert normal["lot_deadline_dates"] == ["2026-12-11"]
    assert normal["estimated_value_as_published"] == "65000.00"
    assert normal["estimated_value_currency"] == "EUR"
    assert normal["estimated_value_not_verified_spending"] is True

    x = report(observed("ted", [notice]))
    lead = x["procurement_observations"][0]
    assert lead["main_cpv_code"] == "72000000"
    assert lead["deadline_assessment"] == "published_lot_dates_on_or_after_asof"
    assert lead["latest_lot_deadline_date"] == "2026-12-11"
    assert lead["estimated_value_as_published"] == "65000.00"
    assert lead["contract_value_verified"] is False
    output = discovery.format_discovery_report(x)
    assert "main CPV: 72000000" in output
    assert "buyer country: DEU" in output
    assert "last published lot date: 2026-12-11" in output
    assert "estimated (not spent): 65000.00 EUR" in output


def test_buyer_side_review_separates_inspectable_procurement_from_theme_count():
    ted = [
        _rich_ted("804742-2026", "Greek Employment Authority", "72000000",
                  deadline="2026-12-21", estimated="10588350"),
        _rich_ted("804842-2026", "Croatian Waste Authority", "90510000",
                  deadline="2026-12-04", estimated="1075000"),
        _rich_ted("804823-2026", "German Building Buyer", "45000000",
                  deadline="2027-01-11", estimated="567000"),
        _rich_ted("804817-2026", "French Fuel Buyer", "09134000",
                  deadline="2026-12-18", estimated="25000"),
        _rich_ted("804901-2026", "Old Date Buyer", "41000000",
                  deadline="2026-11-01"),
        _rich_ted("804902-2026", "Already Awarded", "72000000",
                  kind="can-standard"),
    ]
    x = report(observed("ted", ted))
    review = x["procurement_review"]
    assert review["qualified_notices_in_bounded_sample"] == 4
    assert review["qualified_main_cpv_software_it"] == 1
    assert review["qualified_other_main_cpv_sectors"] == 3
    assert review["selected_for_review"] == 4
    assert review["open_bid_status_verified"] is False
    assert review["estimated_value_is_not_spending_or_software_only_budget"] is True
    assert x["candidate_count"] == 0
    selected = [
        notice for notice in x["procurement_observations"]
        if notice["buyer_side_review_qualified"]
    ]
    assert len(selected) == 4
    assert selected[0]["reference"].endswith("804742-2026")
    assert selected[0]["main_cpv_software_it_category"] is True
    assert selected[0]["estimated_value_as_published"] == "10588350"
    assert selected[0]["software_only_estimate_verified"] is False
    assert all(not n["buyer_entity_identity_verified"] and
               not n["still_open_tender_verified"] for n in selected)
    text = discovery.format_discovery_report(x)
    assert "BUYER-SIDE PROCUREMENT REVIEW" in text
    assert "software/IT main CPV: 1; other: 3" in text
    assert "other published CPVs: 72222300" in text
    assert "Growth, buyer budgets and market size: NOT VERIFIED." in text


def test_published_procedure_estimate_evidence_is_not_budget_or_market_rank():
    # Three different sectors, currencies and estimate sizes. Recency and
    # source-date representation—not money—choose the inspection examples.
    today = date(2026, 11, 19)
    windows = discovery._ted_date_windows(today, 30, 20)
    rows = []
    for i, (_, end, _) in enumerate(windows):
        record = _rich_ted(
            f"{820000 + i}-2026", f"Public Buyer {i}",
            ["90510000", "71000000", "72222300"][i],
            estimated=["1000.00", "7000000", "200"][i],
            currency=["EUR", "CZK", "SEK"][i],
        )
        record["publication-date"] = end.isoformat()
        rows.append(record)
    unpriced = _rich_ted(
        "820010-2026", "Unpriced Public Buyer", "45000000",
        estimated="unknown",
    )
    unpriced["publication-date"] = windows[0][1].isoformat()
    rows.append(unpriced)
    expired_money = _rich_ted(
        "820011-2026", "Past Bid Buyer", "72222300",
        deadline="2026-11-02", estimated="400000", currency="EUR",
    )
    expired_money["publication-date"] = windows[1][1].isoformat()
    rows.append(expired_money)
    x = discovery.summarize_discovery(
        [observed("ted", rows)],
        as_of=today.isoformat(), ted_date_windows=windows,
    )
    p = x["procurement_review"]
    assert p["qualified_notices_in_bounded_sample"] == 4
    assert p["qualified_with_published_procedure_estimate"] == 3
    assert p["qualified_without_published_procedure_estimate"] == 1
    assert p["procedure_estimate_examples_selected"] == 3
    assert p["estimate_review_is_not_value_or_sector_ranking"] is True
    examples = x["procurement_estimate_examples"]
    assert [e["published_currency"] for e in examples] == [
        "EUR", "CZK", "SEK"
    ]
    assert [e["published_procedure_estimate"] for e in examples] == [
        "1000.00", "7000000", "200"
    ]
    assert [e["date"] for e in examples] == [
        w[1].isoformat() for w in windows
    ]
    assert all(e["procedure_estimate_not_software_lot_amount"]
               and not e["confirmed_buyer_budget"]
               and not e["awarded_contract_value"]
               and not e["still_open_tender_verified"]
               and not e["product_market_fit_verified"] for e in examples)
    assert "820011-2026" not in repr(examples)
    assert "Unpriced Public Buyer" not in repr(examples)
    output = discovery.format_discovery_report(x)
    assert "PUBLISHED PROCEDURE ESTIMATES: 3" in output
    assert "1 have no usable procedure estimate" in output
    assert "not ranked by currency or amount" in output
    assert "procedure estimate (not spent): 7000000 CZK" in output
    assert "software-only value" in output


def test_unpriced_qualified_notice_remains_visible_but_not_monetary_evidence():
    x = report(observed("ted", [
        _rich_ted("820021-2026", "Town A", "90510000",
                  estimated="unknown"),
        _rich_ted("820022-2026", "Town B", "48000000",
                  estimated="12000", currency="NOTISO!"),
    ]))
    p = x["procurement_review"]
    assert p["qualified_notices_in_bounded_sample"] == 2
    assert p["qualified_with_published_procedure_estimate"] == 0
    assert p["qualified_without_published_procedure_estimate"] == 2
    assert p["procedure_estimate_examples_selected"] == 0
    assert x["procurement_estimate_examples"] == []
    assert len([r for r in x["procurement_observations"]
                if r["buyer_side_review_qualified"]]) == 2
    assert "PUBLISHED PROCEDURE ESTIMATES: 0" in discovery.format_discovery_report(x)


def test_buyer_review_requires_original_reference_named_buyer_primary_cpv_and_lot_date():
    valid = _rich_ted("804742-2026", "Government", "72000000")
    no_buyer = _rich_ted("804743-2026", "Government", "72000000")
    no_buyer.pop("buyer-name")
    no_cpv = _rich_ted("804744-2026", "Government", "72000000")
    no_cpv.pop("main-classification-proc")
    old = _rich_ted("804745-2026", "Government", "72000000",
                    deadline="2026-10-11")
    no_deadline = _rich_ted("804746-2026", "Government", "72000000")
    no_deadline.pop("deadline-receipt-tender-date-lot")
    invalid_identity = _rich_ted("BAD_NOTICE", "Government", "72000000")
    x = report(observed("ted", [
        valid, no_buyer, no_cpv, old, no_deadline, invalid_identity,
    ]))
    assert x["procurement_review"]["qualified_notices_in_bounded_sample"] == 1
    selected = [n for n in x["procurement_observations"]
                if n["buyer_side_review_qualified"]]
    assert len(selected) == 1
    assert selected[0]["reference"].endswith("804742-2026")


def test_review_qualification_distinct_from_six_review_slots():
    notices = [
        _rich_ted(f"{805101 + i}-2026", f"Published Buyer {i}",
                  "90510000", deadline="2026-12-15")
        for i in range(8)
    ]
    x = report(observed("ted", notices))
    review = x["procurement_review"]
    assert review["qualified_notices_in_bounded_sample"] == 8
    assert review["selected_for_review"] == 6
    assert len(x["procurement_observations"]) == 8
    assert sum(n["buyer_side_review_qualified"]
               for n in x["procurement_observations"]) == 8
    assert sum(n["buyer_side_review_selected"]
               for n in x["procurement_observations"]) == 6
    assert all(not n["still_open_tender_verified"]
               for n in x["procurement_observations"])


def test_buyer_review_is_not_exclusive_to_software_or_estimated_contracts():
    tenders = [
        _rich_ted("804800-2026", "Town One", "90510000",
                  estimated="unknown"),
        _rich_ted("804801-2026", "Town Two", "45000000",
                  estimated="unknown"),
    ]
    x = report(observed("ted", tenders))
    assert x["procurement_review"]["qualified_notices_in_bounded_sample"] == 2
    assert x["procurement_review"]["qualified_main_cpv_software_it"] == 0
    assert x["procurement_review"]["qualified_other_main_cpv_sectors"] == 2
    assert all(n["estimated_value_as_published"] == "" for n in
               x["procurement_observations"] if n["buyer_side_review_qualified"])


def test_two_distinct_published_buyers_same_primary_cpv_are_research_candidate():
    x = report(observed("ted", [
        _rich_ted("805001-2026", "Municipality East", "72222300"),
        _rich_ted("805002-2026", "Municipality West", "72222300"),
        _rich_ted("805003-2026", "Municipality East", "72222300"),
    ]))
    clusters = [c for c in x["candidates"]
                if c["basis"] ==
                "ted_distinct_published_buyer_labels_shared_primary_cpv"]
    assert len(clusters) == 1
    c = clusters[0]
    assert c["label"] == "TED CPV 72222300"
    assert c["cpv_hierarchy_level"] == "category_or_finer"
    assert c["unique_recent_records_in_sample"] == 3
    assert c["distinct_source_classes"] == 1
    assert c["distinct_published_buyer_labels_in_sample"] == 2
    assert c["investigation_priority"] == 1
    assert c["same_buyer_verified"] is False
    assert c["commercial_budget_verified"] is False
    output = discovery.format_discovery_report(x)
    assert "Buyer-side repeat: 2 distinct published buyer labels" in output
    assert "shared workflows, legal-entity identities, awards" in output


def test_broad_cpv_division_repeats_do_not_fake_same_workflow():
    # Real field failure: flood-protection works and fibre expansion both
    # declare division-level 45000000, but are not the same buyer workflow.
    one = _rich_ted("805715-2026", "Polish Water Agency", "45000000")
    one["notice-title"] = {"eng": ["Flood protection civil works"]}
    two = _rich_ted("805721-2026", "Swedish Energy Buyer", "45000000")
    two["notice-title"] = {"eng": ["Fibre network expansion"]}
    x = report(observed("ted", [one, two]))
    assert not any(c["basis"] ==
        "ted_distinct_published_buyer_labels_shared_primary_cpv"
        for c in x["candidates"])
    assert x["candidate_count"] == 0
    assert len(x["procurement_observations"]) == 2
    assert all(n["buyer_side_review_qualified"] for n in x["procurement_observations"])
    coarse = x["coarse_cpv_repeats_not_candidates"]
    assert len(coarse) == 1
    assert coarse[0]["main_cpv_code"] == "45000000"
    assert coarse[0]["hierarchy_level"] == "division"
    assert coarse[0]["notice_count_in_sample"] == 2
    assert coarse[0]["shared_workflow_verified"] is False
    output = discovery.format_discovery_report(x)
    assert "BROAD CPV REPEATS" in output
    assert "CPV 45000000 (division)" in output
    assert "shared workflow NOT verified" in output


@pytest.mark.parametrize("cpv,level", [
    ("45000000", "division"),
    ("72000000", "division"),
    ("45100000", "group"),
    ("45210000", "class"),
    ("72222300", "category_or_finer"),
    ("80500112", "category_or_finer"),
    ("garbage", "invalid"),
    ("00000000", "invalid"),
])
def test_cpv_granularity_matches_official_hierarchy(cpv, level):
    assert discovery._cpv_granularity(cpv) == level


def test_one_publication_day_cannot_impersonate_thirty_day_sector_sample():
    day = "2026-11-19"
    records = [
        _rich_ted(f"{805100 + i}-2026", f"Buyer {i}", "45000000")
        for i in range(20)
    ]
    result = report(observed("ted", records))
    audit = result["ted_sampling_audit"]
    assert audit["status"] == "observed"
    assert audit["observed_notice_count"] == 20
    assert audit["publication_days_represented"] == 1
    assert audit["earliest_sampled_publication"] == day
    assert audit["latest_sampled_publication"] == day
    assert audit["requested_lookback_days"] == 30
    assert audit["first_page_hit_record_cap"] is True
    assert audit["main_cpv_48_or_72_observed"] == 0
    assert audit["main_cpv_divisions_in_sample"] == {"45": 20}
    assert audit["sector_share_or_growth_estimable"] is False
    output = discovery.format_discovery_report(result)
    assert "TED SAMPLING AUDIT" in output
    assert "1 publication date(s)" in output
    assert "20-record first-page cap" in output
    assert "not a market-wide frequency" in output


def test_unavailable_ted_is_not_misreported_as_zero_market():
    result = report({
        "source": "ted", "status": "unavailable", "http_status": 429
    })
    audit = result["ted_sampling_audit"]
    assert audit["status"] == "unavailable"
    assert audit["main_cpv_48_or_72_observed"] == 0
    assert audit["sector_share_or_growth_estimable"] is False
    assert "TED SAMPLING AUDIT" not in discovery.format_discovery_report(result)


def test_repeat_notices_from_same_buyer_cannot_fake_cross_buyer_demand():
    x = report(observed("ted", [
        _rich_ted("805001-2026", "Municipality East", "72000000"),
        _rich_ted("805002-2026", "municipality east ", "72000000"),
    ]))
    assert not any(c["basis"] ==
                   "ted_distinct_published_buyer_labels_shared_primary_cpv"
                   for c in x["candidates"])


def test_awards_and_prior_information_not_grouped_as_new_procurement():
    x = report(observed("ted", [
        _rich_ted("805001-2026", "Municipality East", "72000000", kind="can-standard"),
        _rich_ted("805002-2026", "Municipality West", "72000000", kind="pin-only"),
    ]))
    assert not any(c["basis"] ==
                   "ted_distinct_published_buyer_labels_shared_primary_cpv"
                   for c in x["candidates"])
    assert all(z["buying_intent_verified"] is False
               for z in x["procurement_observations"])


def test_no_unverified_primary_cpv_from_only_additional_lot_codes():
    x = _rich_ted("805010-2026", "Town A", "72000000")
    x.pop("main-classification-proc")
    y = _rich_ted("805011-2026", "Town B", "72000000")
    y.pop("main-classification-proc")
    output = report(observed("ted", [x, y]))
    assert not any(c["basis"] ==
                   "ted_distinct_published_buyer_labels_shared_primary_cpv"
                   for c in output["candidates"])


def test_prioritize_competition_notices_with_future_lot_dates_over_awards():
    x = report(observed("ted", [
        _rich_ted("805002-2026", "Town B", "72000000",
                  kind="can-standard"),
        _rich_ted("805001-2026", "Town A", "72000000",
                  deadline="2026-12-30", kind="cn-standard"),
        _rich_ted("805003-2026", "Town C", "72000000",
                  deadline="2026-10-01", kind="cn-standard"),
    ]))
    assert x["procurement_observations"][0]["notice_type"] == "cn-standard"
    assert x["procurement_observations"][0]["deadline_assessment"] == (
        "published_lot_dates_on_or_after_asof"
    )
    assert any(
        item["deadline_assessment"] == "all_published_lot_dates_past"
        for item in x["procurement_observations"]
    )


def test_no_false_budget_from_invalid_or_unpaired_estimate():
    from mcp_trendpulse.intelligence_observations import _entry

    bad = _rich_ted(
        "805010-2026", "Town A", "72000000",
        estimated="999999999999999999999999999999999.123",
        currency="EUR",
    )
    raw = _entry("ted", bad, date(2026, 11, 19))
    assert raw["estimated_value_as_published"] == ""
    invalid_currency = {**bad, "estimated-value-proc": "12345",
                        "estimated-value-cur-proc": "NOTISO!"}
    raw = _entry("ted", invalid_currency, date(2026, 11, 19))
    assert raw["estimated_value_currency"] == ""


def test_seedless_ted_field_contract_requests_verified_source_fields():
    plan = discovery.discover_current(execute=False, env={})
    ted = next(p for p in plan["plans"] if p["source"] == "ted")
    fields = set(ted["body"]["fields"])
    assert {
        "classification-cpv", "main-classification-proc", "title-proc",
        "estimated-value-proc", "estimated-value-cur-proc",
        "deadline-receipt-tender-date-lot", "buyer-country",
    } <= fields


def test_cfpb_cannot_consume_all_discovery_candidate_slots():
    complaints = [
        complaint(str(i), issue=f"Complaint category {i // 2}")
        for i in range(16)
    ]
    publications = [
        work("W2741809807"), work("W2741809808"),
    ]
    x = report(
        observed("cfpb", complaints),
        observed("openalex", publications),
    )
    cfpb = [c for c in x["candidates"]
            if c["basis"] == "cfpb_public_product_issue_categories"]
    assert len(cfpb) <= 4
    assert any(c["basis"] == "openalex_assigned_primary_topic"
               for c in x["candidates"])
