"""Explicit original-provider holdout evaluation (NOT run by pytest).

Run from repo root:
  PYTHONPATH=src python tests/mjau_v3_workflow_holdout_runner.py --live

Original-source labels are extracted by this standalone code path without
calling the v3 parsing functions. It still is NOT an independent human review.
No raw OSV advisory bodies; OSV querybatch returns only id+modified.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
from pathlib import Path
import tempfile
from time import monotonic

from mcp_trendpulse.intelligence_core import BudgetCache, IntelligenceError, plan_source
from mcp_trendpulse.mjau_v3 import budgeted_sources as api

WIKIDATA_CASES = [
    (["Q90", "Q60", "Q64"], ["en", "de", "sl"],
     [("Paris", "en"), ("New York City", "en"), ("Berlin", "en"),
      ("An invented place name not in Wikidata", "en")]),
    (["Q89", "Q312", "Q30"], ["en", "sl"],
     [("apple", "en"), ("Apple Inc.", "en"), ("United States", "en"),
      ("Some non-existent organization", "en")]),
    (["Q308", "Q1150", "Q42"], ["en", "de", "sl"],
     [("Mercury", "en"), ("Merkur", "de"), ("Douglas Adams", "en"),
      ("Fictional QID name", "en")]),
    (["Q9999999999", "Q89"], ["en"],
     [("apple", "en"), ("One missing source entity name", "en")]),
]

OSV_CASES = [
    ("PyPI", "Django", "2.2.0"),
    ("PyPI", "requests", "2.31.0"),
    ("PyPI", "Jinja2", "2.10.1"),
    ("PyPI", "six", "1.16.0"),
    ("npm", "lodash", "4.17.11"),
    ("npm", "minimist", "0.0.8"),
    ("npm", "react", "18.2.0"),
    ("npm", "express", "4.16.0"),
]

OUTPUT = Path("docs/mjau-v3/workflow-holdout-results-20261122.json")


def _gold_wikidata(raw, qids, lang, query):
    """Independent source-field extraction: intentionally no A04 parsing imports."""
    original = raw.get("entities", {})
    expected = []
    incomplete = False
    for qid in qids:
        item = original.get(qid)
        if not isinstance(item, dict) or "missing" in item:
            incomplete = True
            continue
        label = item.get("labels", {}).get(lang, {}).get("value")
        if not isinstance(label, str):
            incomplete = True
        aliases = item.get("aliases", {}).get(lang, [])
        if len(aliases) > 8:
            incomplete = True
        bounded = [
            a["value"] for a in aliases[:8] if isinstance(a, dict)
            and isinstance(a.get("value"), str)
        ]
        if any(x.casefold() == query.casefold() for x in [label, *bounded]
               if isinstance(x, str)):
            expected.append(qid)
    return sorted(expected), incomplete


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Execute bounded original-source calls")
    args = parser.parse_args()
    if not args.live:
        raise SystemExit("No provider calls without explicit --live")
    expected = len(WIKIDATA_CASES) + len(OSV_CASES)
    assert expected == 12
    assert len(WIKIDATA_CASES) <= api.WIKIDATA_DAILY_CAP
    assert len(OSV_CASES) <= api.OSV_DAILY_CAP

    # Spied data are held only in process memory, never cached unprojected.
    original_fetch = api._request_json
    raw_by_key = {}
    attempted = []
    def spy(**kwargs):
        identity = (
            kwargs["url"], kwargs["method"],
            json.dumps(kwargs["body"], sort_keys=True) if kwargs["body"] else "",
        )
        attempted.append(identity)
        body = original_fetch(**kwargs)
        raw_by_key[identity] = body
        return body

    api._request_json = spy
    report = {
        "original_preregister": "docs/mjau-v3/workflow-holdout-preregister-20261122.md",
        "independent_human_reviewer": False,
        "original_source_truth_extraction_independent_of_adapter": True,
        "no_original_osv_advisory_bodies_stored": True,
        "network_limit": 12,
        "wikidata": [],
        "osv": [],
        "failures": [],
    }
    # v1 actual source-contract control, not a simulated fake ranking.
    for source in ("wikidata_action_api", "osv_public_api"):
        try:
            plan_source(source)
            report["failures"].append("Unexpected baseline v1 source: " + source)
        except IntelligenceError:
            pass
    report["v1_official_source_task_coverage"] = 0

    # SQLite context-managed commits are not guaranteed to release file
    # handles immediately on Windows. Ignore only temp cleanup failures so
    # the completed holdout receipt is not lost after all tests have run.
    with tempfile.TemporaryDirectory(
        prefix="mjau-v3-holdout-cache-", ignore_cleanup_errors=True,
    ) as d:
        cache = BudgetCache(Path(d))
        for qids, langs, queries in WIKIDATA_CASES:
            started = monotonic()
            observed = api.wikidata_identity(qids, langs, execute=True, cache=cache)
            elapsed = round((monotonic() - started) * 1000, 1)
            key = (api.wikidata_identity(qids, langs)["url"], "GET", "")
            raw = raw_by_key.get(key)
            group = {
                "qids": qids, "languages": langs,
                "source_status": observed.get("status"),
                "first_request_ms": elapsed,
                "source_received": raw is not None,
                "case_results": [],
            }
            if raw is not None and observed.get("status") == "OFFLINE_PARSED_UPSTREAM_PAYLOAD":
                identity = json.dumps(raw, ensure_ascii=True, sort_keys=True).encode()
                group["original_json_sha256"] = hashlib.sha256(identity).hexdigest()
                projected_by_qid = {r["qid"]: r for r in observed["results"]}
                for qid in qids:
                    ref = raw.get("entities", {}).get(qid)
                    reported = projected_by_qid.get(qid)
                    if not isinstance(ref, dict) or "missing" in ref:
                        correct = reported and reported["status"] in (
                            "unknown_missing_entity", "unknown_partial_response"
                        )
                    else:
                        correct = bool(reported and reported["status"] == "source_item_observed")
                        if correct:
                            for lang in langs:
                                origin = ref.get("labels", {}).get(lang, {}).get("value")
                                projected = reported["names"][lang]["label"]
                                if origin != projected:
                                    correct = False
                    if not correct:
                        report["failures"].append("A04 wrong QID/label projection " + qid)
                for name, lang in queries:
                    expected_candidates, incomplete = _gold_wikidata(raw, qids, lang, name)
                    candidate = api.wikidata_identity(
                        qids, langs, name=name, match_language=lang,
                        execute=True, cache=cache,
                    )
                    actual = candidate.get("name_candidates", {})
                    correct = (
                        actual.get("candidate_qids") == expected_candidates
                        and actual.get("identity_confirmed") is False
                        and (not incomplete or not actual.get("searched_name_coverage_complete"))
                    )
                    group["case_results"].append({
                        "query": name, "language": lang,
                        "expected_source_candidates": expected_candidates,
                        "observed_source_candidates": actual.get("candidate_qids"),
                        "source_coverage_incomplete": incomplete,
                        "status": actual.get("status"),
                        "pass": correct,
                    })
                    if not correct:
                        report["failures"].append("A04 source match error " + name)
            report["wikidata"].append(group)
            print("A04_HOLDOUT=" + json.dumps({
                "qids": qids, "observed": group["source_status"],
                "cases": len(group["case_results"]),
                "pass": sum(bool(x["pass"]) for x in group["case_results"]),
            }), flush=True)

        for ecosystem, package, version in OSV_CASES:
            started = monotonic()
            observed = api.osv_package_ids(
                ecosystem, package, version, execute=True, cache=cache,
            )
            elapsed = round((monotonic() - started) * 1000, 1)
            plan = api.osv_package_ids(ecosystem, package, version)
            key = (
                plan["url"], "POST", json.dumps(plan["body"], sort_keys=True)
            )
            raw = raw_by_key.get(key)
            entry = {
                "ecosystem": ecosystem, "package": package, "version": version,
                "status": observed.get("status"),
                "request_elapsed_ms": elapsed,
                "source_received": raw is not None,
            }
            if raw is not None and observed.get("status") in (
                "source_advisories_returned", "no_returned_advisories",
                "incomplete_truncated_response", "incomplete_paged_response",
            ):
                data = raw.get("results", [{}])[0]
                original_ids = [x["id"] for x in data.get("vulns", [])]
                projected_ids = [x["id"] for x in observed.get("advisories", [])]
                expected_subset = original_ids[:100]
                pass_source = (
                    projected_ids == expected_subset and
                    observed.get("provider_ids_in_this_page") == len(original_ids)
                    and observed.get("no_advisory_not_equivalent_to_safe_package") is True
                    and observed.get("commercial_bulk_redistribution_approved") is False
                    and observed.get("raw_advisory_redistribution_authorized") is False
                )
                if not pass_source:
                    report["failures"].append(
                        "A10 original ID projection mismatch " + package
                    )
                entry["expected_original_count"] = len(original_ids)
                entry["projected_count"] = len(projected_ids)
                entry["source_complete"] = observed.get("source_population_complete")
                entry["pass"] = pass_source
                entry["original_metadata_sha256"] = hashlib.sha256(
                    json.dumps(raw, sort_keys=True).encode()
                ).hexdigest()
            report["osv"].append(entry)
            print("A10_HOLDOUT=" + json.dumps({
                "package": package, "source_status": entry["status"],
                "count": entry.get("projected_count"),
                "pass": entry.get("pass"),
            }), flush=True)

        report["source_requests_attempted"] = len(attempted)
        report["max_requests_preserved"] = len(attempted) <= expected
        report["wikidata_budget_spent"] = sum(x["method"] == "GET" for x in (
            {"method": kind[1]} for kind in attempted
        ))
        report["osv_budget_spent"] = sum(kind[1] == "POST" for kind in attempted)
        report["wikidata_cases_scored"] = sum(
            len(x["case_results"]) for x in report["wikidata"]
        )
        report["wikidata_cases_passed"] = sum(
            bool(y["pass"]) for x in report["wikidata"] for y in x["case_results"]
        )
        report["osv_cases_scored"] = sum("pass" in x for x in report["osv"])
        report["osv_cases_passed"] = sum(
            bool(x.get("pass")) for x in report["osv"]
        )
        if not report["max_requests_preserved"]:
            report["failures"].append("Exceeded preregistered request budget")
        del cache
        gc.collect()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n")
    print("HOLDOUT_FINAL=" + json.dumps({
        "wikidata": [report["wikidata_cases_passed"], report["wikidata_cases_scored"]],
        "osv": [report["osv_cases_passed"], report["osv_cases_scored"]],
        "requests": report["source_requests_attempted"],
        "failures": report["failures"],
        "reviewer_human_independent": False,
    }), flush=True)


if __name__ == "__main__":
    main()
