"""Validate V3's versioned SQLite cache before exposing results to MCP callers.

This is an integrity *contract*, not a signature. A process with authority to
rewrite both local files and source code cannot be authenticated by this check.
No network request is ever made as a recovery strategy for a bad cache entry.
"""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .osv import ADVISORY, MAX_COMPACT_IDS, OSV_LICENSE_SOURCES, _date
from .wikidata import MAX_ALIASES, _clean_text

_COMMON = {
    "source", "status", "retrieved_at", "network_performed", "cache_hit",
    "daily_request_cap", "retry_automatically", "source_terms_review_required",
}
_WIKIDATA_KEYS = {
    "qids_requested", "languages_requested", "results", "source_coverage_complete",
    "raw_payload_reused_not_fetched", "no_auto_entity_merging",
    "source_payload_validated_offline", "license", "license_url",
    "identity_verified",
}
_OSV_KEYS = {
    "ecosystem", "package", "version", "source_population_complete",
    "provider_ids_in_this_page", "advisory_count_projected", "advisories",
    "source_license_reference", "source_licenses_are_heterogeneous",
    "source_specific_license_review_required",
    "raw_advisory_redistribution_authorized",
    "no_advisory_not_equivalent_to_safe_package",
    "not_exploitation_or_buyer_demand_evidence", "no_auto_remediation",
    "source_rights_review_status", "commercial_bulk_redistribution_approved",
    "cc_by_license_url", "source_attribution", "third_party_request_notice",
    "source_licensing_comment",
}
_FAILURE_KEYS = {
    "source", "status", "reason", "not_a_zero_result",
    "retry_automatically", "network_performed", "cache_hit",
}
_FAILURE_REASONS = {
    "source_transport_or_encoding_error", "invalid_or_oversized_source_shape",
}


def _is_clean_text(value: Any) -> bool:
    if value is None:
        return True
    try:
        return _clean_text(value) == value
    except ValueError:
        return False


def _valid_wikidata(item: dict[str, Any], url: str) -> bool:
    expected = parse_qs(urlsplit(url).query)
    qids = expected["ids"][0].split("|")
    languages = expected["languages"][0].split("|")
    if (set(item) != _COMMON | _WIKIDATA_KEYS
            or item["qids_requested"] != qids
            or item["languages_requested"] != languages
            or item["identity_verified"] is not False
            or item["source_payload_validated_offline"] is not True
            or item["no_auto_entity_merging"] is not True
            or item["raw_payload_reused_not_fetched"] is not True
            or item["license"] != "CC0-1.0"
            or item["license_url"] != "https://www.wikidata.org/wiki/Wikidata:Licensing"
            or type(item["source_coverage_complete"]) is not bool):
        return False
    results = item["results"]
    if not isinstance(results, list) or len(results) != len(qids):
        return False
    complete = True
    for result, qid in zip(results, qids):
        if not isinstance(result, dict) or result.get("qid") != qid:
            return False
        status = result.get("status")
        if status in {"unknown_partial_response", "unknown_missing_entity"}:
            if set(result) != {"qid", "status"}:
                return False
            complete = False
            continue
        if (status != "source_item_observed" or set(result) != {
                "qid", "status", "entity_url", "names", "source_id",
                "source_licenses_data_as_cc0",
                "original_source_identity_not_corporate_registry_confirmation",
        } or result["entity_url"] != f"https://www.wikidata.org/wiki/{qid}"
                or result["source_id"] != "wikidata_action_api"
                or result["source_licenses_data_as_cc0"] is not True
                or result["original_source_identity_not_corporate_registry_confirmation"] is not True):
            return False
        names = result["names"]
        if not isinstance(names, dict) or set(names) != set(languages):
            return False
        for lang in languages:
            name = names[lang]
            if not isinstance(name, dict) or set(name) != {
                "label", "description", "aliases",
                "source_alias_count", "aliases_truncated",
            }:
                return False
            aliases = name["aliases"]
            count = name["source_alias_count"]
            if (not _is_clean_text(name["label"])
                    or not _is_clean_text(name["description"])
                    or not isinstance(aliases, list) or len(aliases) > MAX_ALIASES
                    or type(count) is not int or count < len(aliases) or count > 10000
                    or name["aliases_truncated"] is not (count > MAX_ALIASES)):
                return False
            if any(not isinstance(v, str) or not _is_clean_text(v) for v in aliases):
                return False
    return (
        item["source_coverage_complete"] is complete
        and item["status"] == (
            "source_entities_observed" if complete else "source_entities_partially_observed"
        )
    )


def _valid_osv(item: dict[str, Any], body: dict[str, Any]) -> bool:
    original = body["queries"][0]
    package = original["package"]
    if (set(item) != _COMMON | _OSV_KEYS
            or (item["ecosystem"], item["package"], item["version"]) != (
                package["ecosystem"], package["name"], original["version"],
            )
            or item["commercial_bulk_redistribution_approved"] is not False
            or item["raw_advisory_redistribution_authorized"] is not False
            or item["source_specific_license_review_required"] is not True
            or item["no_advisory_not_equivalent_to_safe_package"] is not True
            or item["source_licenses_are_heterogeneous"] is not True
            or item["no_auto_remediation"] is not True
            or item["not_exploitation_or_buyer_demand_evidence"] is not True
            or item["source_license_reference"] != OSV_LICENSE_SOURCES
            or item["source_rights_review_status"] != "pending_final_original_feed_review"
            or item["cc_by_license_url"] != "https://creativecommons.org/licenses/by/4.0/"
            or type(item["source_population_complete"]) is not bool):
        return False
    attribution = item["source_attribution"]
    if (not isinstance(attribution, dict)
            or set(attribution) != {
                "aggregator", "aggregator_url", "upstream_license_index",
                "cc_by_4_license", "transformation_notice", "original_per_record_feed_verified",
            }
            or attribution["aggregator"] != "OSV.dev"
            or attribution["aggregator_url"] != "https://osv.dev/"
            or attribution["upstream_license_index"] != OSV_LICENSE_SOURCES
            or attribution["cc_by_4_license"] != "https://creativecommons.org/licenses/by/4.0/"
            or attribution["original_per_record_feed_verified"] is not False
            or attribution["transformation_notice"] != (
                "Filtered original OSV querybatch response to factual "
                "advisory IDs, modified timestamps and OSV record links; "
                "no original advisory prose or severity was reproduced."
            )
            or item["third_party_request_notice"] != (
                "execute=True sends ecosystem, package and exact version to "
                "the OSV.dev API; no private package lists or secrets."
            )
            or item["source_licensing_comment"] != (
                "GHSA/PYSEC prefix indicates attribution hint, not permission; "
                "check original OSV source; no raw advisories are redistributed."
            )):
        return False
    advisories = item["advisories"]
    count = item["advisory_count_projected"]
    source_count = item["provider_ids_in_this_page"]
    if (not isinstance(advisories, list) or type(count) is not int
            or type(source_count) is not int or len(advisories) != count
            or not 0 <= count <= MAX_COMPACT_IDS or source_count < count
            or source_count > 10000):
        return False
    for record in advisories:
        if (not isinstance(record, dict)
                or set(record) != {"id", "modified_at", "source_url", "source_database_hint"}):
            return False
        ident = record["id"]
        if not isinstance(ident, str) or not ADVISORY.fullmatch(ident):
            return False
        if record["source_url"] != f"https://osv.dev/vulnerability/{ident}":
            return False
        try:
            if _date(record["modified_at"], "modified") is None:
                return False
        except ValueError:
            return False
        hint = (
            "GitHub Advisory Database" if ident.startswith("GHSA-")
            else "PyPI Advisory Database" if ident.startswith("PYSEC-")
            else None
        )
        if record["source_database_hint"] != hint:
            return False
    if item["status"] == "no_returned_advisories":
        return source_count == 0 and item["source_population_complete"] is True
    if item["status"] == "source_advisories_returned":
        return source_count > 0 and item["source_population_complete"] is True
    if item["status"] in {"incomplete_paged_response", "incomplete_truncated_response"}:
        return item["source_population_complete"] is False
    return False


def valid_cached_result(item: Any, source: str, url: str,
                        body: dict[str, Any] | None, cap: int) -> bool:
    """Reject unexpected cache shapes, scopes and unsafe assurance fields."""
    try:
        if not isinstance(item, dict) or item.get("source") != source:
            return False
        if item.get("status") == "source_unavailable":
            reason = item.get("reason")
            valid_reason = isinstance(reason, str) and (
                reason in _FAILURE_REASONS
                or re.fullmatch(r"provider_http_[1-5][0-9]{2}", reason) is not None
            )
            return (
                set(item) == _FAILURE_KEYS
                and valid_reason
                and item.get("not_a_zero_result") is True
                and item.get("network_performed") is True
                and item.get("cache_hit") is False
                and item.get("retry_automatically") is False
            )
        if (item.get("network_performed") is not True
                or item.get("cache_hit") is not False
                or item.get("retry_automatically") is not False
                or item.get("daily_request_cap") != cap
                or item.get("source_terms_review_required") is not (
                    source == "osv_public_api"
                )
                or not isinstance(item.get("retrieved_at"), str)):
            return False
        datetime.fromisoformat(item["retrieved_at"])
        if source == "wikidata_action_api":
            return _valid_wikidata(item, url)
        if source == "osv_public_api" and body is not None:
            return _valid_osv(item, body)
        return False
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
