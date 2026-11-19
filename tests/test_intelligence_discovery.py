"""Synthetic, deterministic falsification tests for keyword-free trend discovery.

Invented records are only fixtures. A successful collector is not customer
validation, trend growth, population prevalence or proof of buyer budgets.
"""
from __future__ import annotations

import json
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


def test_two_distinct_published_buyers_same_primary_cpv_are_research_candidate():
    x = report(observed("ted", [
        _rich_ted("805001-2026", "Municipality East", "72000000"),
        _rich_ted("805002-2026", "Municipality West", "72000000"),
        _rich_ted("805003-2026", "Municipality East", "72000000"),
    ]))
    clusters = [c for c in x["candidates"]
                if c["basis"] ==
                "ted_distinct_published_buyer_labels_shared_primary_cpv"]
    assert len(clusters) == 1
    c = clusters[0]
    assert c["label"] == "TED CPV 72000000"
    assert c["unique_recent_records_in_sample"] == 3
    assert c["distinct_source_classes"] == 1
    assert c["distinct_published_buyer_labels_in_sample"] == 2
    assert c["investigation_priority"] == 1
    assert c["same_buyer_verified"] is False
    assert c["commercial_budget_verified"] is False
    output = discovery.format_discovery_report(x)
    assert "Buyer-side repeat: 2 distinct published buyer labels" in output
    assert "legal-entity identities, awards" in output


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
