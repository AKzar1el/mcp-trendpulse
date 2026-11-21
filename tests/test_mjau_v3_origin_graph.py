"""B09 deterministic attack cases and a documented, source-backed release pair."""

import copy

import pytest
from mcp_trendpulse.mjau_v3.origin_graph import audit_origin_evidence

RELEASE = "https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.3.0"
PYPI = "https://pypi.org/project/mcp/2.3.0/"


def original():
    return {
        "source_id": "github_releases", "source_record_id": "402184404",
        "publisher": "modelcontextprotocol", "source_url": RELEASE,
        "published_at": "2026-10-02", "observed_at": "2026-11-21",
        "origin_url": RELEASE, "origin_relation": "original",
        "reviewed_origin": True,
    }


def package_record():
    # Two public sites attest the same *software version event*; this is not
    # independent evidence of buyer adoption or distinct market demand.
    return {
        "source_id": "pypi_catalog", "source_record_id": "mcp:2.3.0",
        "publisher": "pypi", "source_url": PYPI,
        "published_at": "2026-10-02", "observed_at": "2026-11-21",
        "origin_url": RELEASE, "origin_relation": "same_event",
        "lineage_reference_url": PYPI, "reviewed_origin": True,
    }


def audit(rows):
    return audit_origin_evidence(rows, as_of="2026-11-21")


def test_official_release_and_pypi_are_one_release_event():
    output = audit([original(), package_record()])
    assert output["verified_original_event_count"] == 1
    assert output["verified_independent_original_publishers"] == 1
    assert output["dependent_or_same_event_records"] == 1
    assert output["v1_independent_publisher_proxy_before_lineage"] == 2
    assert output["no_market_demand_inference"]


def test_unreviewed_link_does_not_auto_merge():
    derived = package_record()
    derived["reviewed_origin"] = False
    output = audit([original(), derived])
    assert output["verified_original_event_count"] == 1
    assert output["unresolved_origin_records"] == 1
    assert output["dependent_or_same_event_records"] == 0


def test_distinct_originals_remain_distinct():
    second = copy.deepcopy(original())
    second.update({
        "source_record_id": "384197183", "published_at": "2026-09-07",
        "source_url": "https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.2.0",
        "origin_url": "https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.2.0",
    })
    output = audit([original(), second])
    assert output["verified_original_event_count"] == 2
    assert output["verified_independent_original_publishers"] == 1


def test_future_row_cannot_support_historical_claim():
    delayed = copy.deepcopy(package_record())
    delayed["observed_at"] = "2026-12-01"
    output = audit([original(), delayed])
    assert output["records_in_window"] == 1
    assert output["ignored"]["future_or_unobserved"] == 1


def test_tracking_only_urls_match_original():
    row = original()
    row["source_url"] += "?utm_source=rss&fbclid=abc"
    output = audit([row])
    assert output["verified_original_event_count"] == 1


def test_meaningful_query_parameters_are_preserved():
    row = original()
    row["source_url"] += "?version=older"
    with pytest.raises(ValueError, match="own URL"):
        audit([row])


def test_inconsistent_two_original_publishers_flagged():
    other = copy.deepcopy(original())
    other["source_record_id"] = "mirror-2"
    other["publisher"] = "another_publication"
    output = audit([original(), other])
    assert output["verified_original_event_count"] == 0
    assert output["contradictory_original_claims"] == 1
    assert output["unresolved_origin_records"] == 2


def test_same_source_id_repeated_does_not_double_count():
    output = audit([original(), original()])
    assert output["verified_original_event_count"] == 1
    assert output["ignored"]["duplicate_source_record"] == 1


def test_unknown_is_not_zero_or_proven_independent():
    row = original()
    row["origin_relation"] = "unknown"
    row.pop("origin_url")
    output = audit([row])
    assert output["unresolved_origin_records"] == 1
    assert output["verified_original_event_count"] == 0


def test_credentials_rejected_without_echo():
    row = original()
    row["source_url"] += "?access_token=dont_print"
    with pytest.raises(ValueError, match="Credential") as exc:
        audit([row])
    assert "dont_print" not in str(exc.value)


def test_non_public_origin_ref_rejected():
    row = original()
    row["origin_url"] = "http://localhost:8080/admin"
    with pytest.raises(ValueError, match="HTTPS"):
        audit([row])


def test_oversized_input_rejected():
    with pytest.raises(ValueError, match="At most"):
        audit([original()] * 121)


def test_source_observed_before_publication_rejected():
    row = original()
    row["observed_at"] = "2026-09-30"
    with pytest.raises(ValueError, match="Publication"):
        audit([row])


def test_conflicting_duplicate_source_id_fails_closed():
    second = copy.deepcopy(original())
    second["source_url"] += "?unrelated=yes"
    with pytest.raises(ValueError, match="Conflicting duplicate"):
        audit([original(), second])


def test_invalid_publisher_identity_is_rejected():
    row = original()
    row["publisher"] = "Not Verified News"
    with pytest.raises(ValueError, match="lowercase stable"):
        audit([row])


def test_future_asof_cutoff_is_prohibited():
    with pytest.raises(ValueError, match="Future as_of"):
        audit_origin_evidence([original()], as_of="2030-01-01")
