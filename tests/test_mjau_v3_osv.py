"""A10 deterministic source contract tests only, NOT real vulnerability observations."""
import pytest
from mcp_trendpulse.mjau_v3.osv import (
    plan_package_query, plan_advisory_lookup, parse_package_query,
    parse_advisory_lookup, parse_http_result,
)

ID = "OSV-2020-744"


def advisory():
    # Shape modeled on public OSV documentation, NOT live record contents.
    return {"id": ID, "published": "2020-07-03T10:00:00Z", "modified": "2020-08-03T10:00:00Z",
            "references": [{"url": "https://github.com/google/osv.dev"}]}


def query(data):
    return parse_package_query(data, ecosystem="PyPI", package="jinja2", version="3.1.4")


def test_plan_only_one_fixed_origin_package_version():
    p = plan_package_query("PyPI", "jinja2", "3.1.4")
    assert p["method"] == "POST" and p["url"] == "https://api.osv.dev/v1/query"
    assert p["json_body"]["version"] == "3.1.4" and p["zero_network_calls"]
    assert p["max_requests_if_approved"] == 1


def test_exact_advisory_id_lookup_url_is_fixed_origin():
    p = plan_advisory_lookup(ID)
    assert p["method"] == "GET" and p["url"].endswith("/v1/vulns/" + ID)
    assert p["execution"] == "PLAN_ONLY"


@pytest.mark.parametrize("package", ["../../etc/passwd", "@", "", "https://example.com", " foo", "a" * 121])
def test_invalid_package_path_rejected(package):
    with pytest.raises(ValueError):
        plan_package_query("PyPI", package, "1.0")


@pytest.mark.parametrize("version", ["", "1.0/../../", "v 1.0", "1.0?token=foo", "x" * 100])
def test_bad_version_fails_closed(version):
    with pytest.raises(ValueError):
        plan_package_query("npm", "@scope/pkg", version)


def test_unsupported_ecosystem_blocked():
    with pytest.raises(ValueError):
        plan_package_query("GIT", "https://github.com/a/b", "1.0")


@pytest.mark.parametrize("ident", ["CVE-2024", "GHSA-", "OSV-abc", "../etc/passwd", "abc", "OSV-2020-744?x=y"])
def test_invalid_advisory_id_rejected(ident):
    with pytest.raises(ValueError):
        plan_advisory_lookup(ident)


def test_dated_valid_advisory_not_demand_or_exploitation():
    result = query({"vulns": [advisory()]})
    assert result["status"] == "source_advisories_returned"
    assert result["advisory_count_in_this_response"] == 1
    assert result["records"][0]["advisory_id"] == ID
    assert result["records"][0]["is_not_exploitation_evidence"]
    assert result["records"][0]["copyright_review_required_per_original_feed"]


def test_explicit_empty_vulns_not_safe_package():
    result = query({"vulns": []})
    assert result["status"] == "no_returned_advisories"
    assert result["no_advisory_not_equivalent_to_safe_package"]


def test_paged_result_must_not_claim_complete():
    result = query({"vulns": [advisory()], "next_page_token": "opaque123"})
    assert result["status"] == "incomplete_paged_response"
    assert not result["source_population_complete"]


def test_empty_paged_page_is_unknown_not_zero():
    result = query({"next_page_token": "opaque123"})
    assert result["advisory_count_in_this_response"] == 0
    assert result["status"] == "incomplete_paged_response"


@pytest.mark.parametrize("payload", [None, [], {}, {"error": {"code": "rate_limited"}}, {"vulns": None}, {"vulns": {}}])
def test_invalid_api_shapes_rejected(payload):
    with pytest.raises(ValueError):
        query(payload)


def test_reject_duplicate_advisory_ids():
    with pytest.raises(ValueError, match="Duplicate"):
        query({"vulns": [advisory(), advisory()]})


def test_reject_wrong_advisory_identity():
    with pytest.raises(ValueError, match="Wrong advisory"):
        parse_advisory_lookup(advisory(), "OSV-2020-745")


def test_reject_missing_modified_or_published_dates_as_incomplete():
    sample = advisory()
    sample.pop("modified")
    r = query({"vulns": [sample]})
    assert r["records"][0]["status"] == "incomplete_advisory_dates"


def test_withdrawn_is_not_active():
    sample = advisory()
    sample["withdrawn"] = "2020-09-02T00:00:00Z"
    assert query({"vulns": [sample]})["records"][0]["status"] == "withdrawn"


def test_non_utc_dates_and_wrong_order_rejected():
    item = advisory()
    item["modified"] = "2020-01-01T00:00:00Z"
    with pytest.raises(ValueError, match="before publication"):
        query({"vulns": [item]})
    item["modified"] = "2020-07-10T12:00:00"
    with pytest.raises(ValueError, match="Timezone"):
        query({"vulns": [item]})


def test_secret_and_private_links_are_not_redistributed():
    item = advisory()
    item["references"] += [
        {"url": "http://localhost:8000/key"},
        {"url": "https://example.com/view?token=dont_echo"},
    ]
    result = query({"vulns": [item]})
    assert len(result["records"][0]["advisory_links"]) == 1
    assert "dont_echo" not in str(result)


def test_no_unbounded_records_or_payloads():
    with pytest.raises(ValueError, match="oversized"):
        query({"vulns": [advisory()] * 13})
    huge = {"vulns": [advisory()], "details": "x" * 193000}
    with pytest.raises(ValueError, match="cap"):
        query(huge)


@pytest.mark.parametrize("status,expected", [(401, "permission_denied"), (403, "permission_denied"),
                                             (429, "rate_limited"), (503, "transport_failed"),
                                             (302, "transport_failed")])
def test_transport_failure_visible_not_empty(status, expected):
    out = parse_http_result(status, {"error": "secret123"}, ecosystem="PyPI", package="jinja2", version="3.1.4")
    assert out["cause"] == expected and out["observations"] is None
    assert out["retry"] is False and out["not_a_zero_result"]
    assert "secret123" not in str(out)


def test_http_200_success_parses_only_source_evidence():
    out = parse_http_result(200, {"vulns": [advisory()]}, ecosystem="PyPI", package="jinja2", version="3.1.4")
    assert out["records"][0]["advisory_id"] == ID


def test_no_auto_remediation_and_demand_gates():
    out = query({"vulns": [advisory()]})
    assert out["no_auto_remediation"] and out["records"][0]["is_not_commercial_demand_evidence"]


def test_real_official_osv_page_dates_are_preserved_not_reforecast():
    """Small manually reviewed original-page metadata, not live JSON fetch.

    https://osv.dev/vulnerability/OSV-2020-744 (reviewed 2026-11-21)
    """
    original_page_metadata = {"id": ID, "published": "2020-07-04T00:00:01Z",
                              "modified": "2022-04-13T03:04:39Z", "references": [
                                  {"url": "https://github.com/google/oss-fuzz-vulns/blob/main/vulns/mruby/OSV-2020-744.yaml"},
                              ]}
    out = parse_advisory_lookup(original_page_metadata, ID)
    assert out["record"]["published_at"] == "2020-07-04T00:00:01Z"
    assert out["record"]["modified_at"] == "2022-04-13T03:04:39Z"
    assert out["record"]["status"] == "dated_advisory"
