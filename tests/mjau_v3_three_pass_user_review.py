"""Automated reviewer pass 1: user outcomes on retained original-source metadata.

This is an ENGINEER/ASSISTANT review, NOT an independent human assessor.
No external provider calls: source metadata comes from scoped official snapshots.
Execute directly: PYTHONPATH=src python tests/mjau_v3_three_pass_user_review.py
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

from mcp_trendpulse.intelligence_core import BudgetCache
from mcp_trendpulse.mjau_v3 import budgeted_sources as api

ROOT = Path(__file__).parent / "fixtures" / "mjau_v3"
REPORT = Path("docs/mjau-v3/three-pass-user-review-20261122.json")
LANGS = ["en", "de", "fr", "es", "sl", "it"]
cases: list[dict[str, Any]] = []


def load(name: str) -> dict[str, Any]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


APPLE = load("wikidata_q89_q312_20261121.json")
MERCURY = load("wikidata_mercury_planet_god_six_languages_20261121.json")
CITIES = load("wikidata_q42_q64_q30_20261121.json")
OSV_SOURCE = load("osv_querybatch_source_20261121.json")
DJANGO = load("osv_django_compact_20261121.json")["one_query_envelope"]


def call_wikidata(source: Any, qids: list[str], *,
                  name: str, language: str = "en") -> dict[str, Any]:
    with TemporaryDirectory(prefix="triple-review-w-", ignore_cleanup_errors=True) as path:
        with patch.object(api, "_request_json", return_value=copy.deepcopy(source)):
            return api.wikidata_identity(
                qids, LANGS, name=name, match_language=language,
                execute=True, cache=BudgetCache(Path(path)),
            )


def call_osv(source: Any, ecosystem: str, package: str,
             version: str) -> dict[str, Any]:
    with TemporaryDirectory(prefix="triple-review-o-", ignore_cleanup_errors=True) as path:
        with patch.object(api, "_request_json", return_value=copy.deepcopy(source)):
            return api.osv_package_ids(
                ecosystem, package, version, execute=True, cache=BudgetCache(Path(path)),
            )


def expected_entities_from_original(source: dict[str, Any], query: str,
                                    language: str) -> list[str]:
    """Independent direct JSON extraction: no v3 parser/matcher import."""
    found = []
    for qid, record in source["entities"].items():
        labels = record.get("labels", {})
        aliases = record.get("aliases", {}).get(language, [])[:8]
        original_names = [
            labels.get(language, {}).get("value"),
            *(r.get("value") for r in aliases if isinstance(r, dict)),
        ]
        if any(isinstance(v, str) and v.casefold() == query.casefold()
               for v in original_names):
            found.append(qid)
    return sorted(found)


def record(code: str, task: str, score: int, passed: bool, evidence: str) -> None:
    if score not in (0, 1, 2):
        raise ValueError("Invalid bounded assessor score")
    final = score if passed else 0
    item = {
        "id": code, "user_task": task, "score": final,
        "decision": "passed" if passed else "failed",
        "evidence": evidence,
    }
    cases.append(item)
    print(f"{code} SCORE={final}/2 {task} | {evidence[:100]}", flush=True)


def original_osv(ecosystem: str, package: str, version: str) -> tuple[dict, int]:
    if package == "Django":
        raw = DJANGO
        expected = 75
    else:
        sample = next(x for x in OSV_SOURCE["samples"] if (
            x["ecosystem"], x["package"], x["version"]
        ) == (ecosystem, package, version))
        raw = {"results": [{"vulns": sample["advisory_stubs"]}]}
        expected = sample["count"]
    return raw, expected


def main() -> None:
    # W01 — same English name does not collapse different identities.
    en_apple = call_wikidata(APPLE, ["Q89", "Q312"], name="apple")
    en_company = call_wikidata(APPLE, ["Q89", "Q312"], name="Apple Inc.")
    okay = (
        en_apple["name_candidates"]["candidate_qids"]
        == expected_entities_from_original(APPLE, "apple", "en") == ["Q89"]
        and en_company["name_candidates"]["candidate_qids"]
        == expected_entities_from_original(APPLE, "Apple Inc.", "en") == ["Q312"]
        and not en_apple["name_candidates"]["identity_confirmed"]
    )
    record("W01", "Fruit vs company in English", 2, okay, "Original Q89 and Q312 labels, no confirmed identity")

    # W02 — language-specific source coverage for the same two entities.
    sl_apple = call_wikidata(APPLE, ["Q89", "Q312"], name="jabolko", language="sl")
    sl_company = call_wikidata(APPLE, ["Q89", "Q312"], name="Apple Inc.", language="sl")
    okay = (
        sl_apple["name_candidates"]["candidate_qids"]
        == expected_entities_from_original(APPLE, "jabolko", "sl") == ["Q89"]
        and sl_company["name_candidates"]["candidate_qids"]
        == expected_entities_from_original(APPLE, "Apple Inc.", "sl") == ["Q312"]
    )
    record("W02", "Fruit vs company in Slovenian", 2, okay, "Original Slovenian labels retained separately")

    # W03/W04 — exactly the same surface string for two different original QIDs.
    for code, label, lang in [
        ("W03", "Mercury", "en"), ("W04", "Merkur", "de"),
    ]:
        result = call_wikidata(
            MERCURY, ["Q308", "Q1150"], name=label, language=lang,
        )["name_candidates"]
        truth = expected_entities_from_original(MERCURY, label, lang)
        okay = (
            result["candidate_qids"] == truth == ["Q1150", "Q308"]
            and result["status"] == "ambiguous"
            and result["identity_confirmed"] is False
        )
        record(code, "Ambiguous Mercury entity (" + lang + ")", 2, okay,
               "Both original Q308/Q1150 present, explicitly ambiguous")

    # W05 — language coverage and truthful *live* source status.
    city = call_wikidata(CITIES, ["Q42", "Q64", "Q30"], name="Berlin")
    city_item = next(x for x in city["results"] if x["qid"] == "Q64")
    okay = (
        city["status"] == "source_entities_observed"
        and city["source_payload_validated_offline"] is True
        and city["network_performed"] is True
        and city["name_candidates"]["candidate_qids"] == ["Q64"]
        and all(city_item["names"][k]["label"]
                == CITIES["entities"]["Q64"]["labels"][k]["value"]
                for k in ("en", "de", "sl"))
    )
    record("W05", "Berlin source in three languages; honest live status", 2, okay,
           "Q64 original de/en/sl labels; no contradictory OFFLINE user status")

    # W06 — unknown Q42 localized label must never hallucinate Douglas Adams.
    unknown = call_wikidata(CITIES, ["Q42", "Q64", "Q30"], name="Douglas Adams")
    row_q42 = next(x for x in unknown["results"] if x["qid"] == "Q42")
    okay = (
        row_q42["names"]["en"]["label"] is None
        and unknown["name_candidates"]["candidate_qids"] == []
        and unknown["name_candidates"]["searched_name_coverage_complete"] is False
        and unknown["name_candidates"]["identity_confirmed"] is False
    )
    record("W06", "Missing Q42 label: abstain instead of inventing", 2, okay,
           "Original Q42 en label missing and search coverage incomplete")

    # W07 — source returns only one of two requested QIDs.
    source_partial = copy.deepcopy(APPLE)
    del source_partial["entities"]["Q312"]
    partial = call_wikidata(source_partial, ["Q89", "Q312"], name="Apple Inc.")
    okay = (
        partial["status"] == "source_entities_partially_observed"
        and any(x["status"] == "unknown_partial_response"
                for x in partial["results"] if x["qid"] == "Q312")
        and not partial["name_candidates"]["searched_name_coverage_complete"]
        and not partial["name_candidates"]["identity_confirmed"]
    )
    record("W07", "Absent QID: unknown, never definitive negative", 2, okay,
           "Simulated incomplete official envelope with Q312 absent")

    # W08 — source aliases exceed cap; no false negative from unprojected aliases.
    alias = call_wikidata(CITIES, ["Q42", "Q64", "Q30"],
                          name="unobserved-name-that-is-not-in-top-eight")
    okay = (
        alias["name_candidates"]["candidate_qids"] == []
        and alias["name_candidates"]["searched_aliases_incomplete"]
        and alias["name_candidates"]["status"] == "unknown_incomplete_aliases"
        and any(row["names"]["en"]["aliases_truncated"] for row in alias["results"]
                if row["status"] == "source_item_observed")
    )
    record("W08", "Unseen aliases after bounded top eight: incomplete", 2, okay,
           "Original Q30 has 20 English aliases; only 8 safely projected")

    # W09 — intentionally limited QID-only user experience is a *partial*.
    try:
        api.wikidata_identity([], ["en"], name="Berlin")
        direct_query_supported = True
    except ValueError:
        direct_query_supported = False
    record("W09", "Answer a name-only user without a supplied QID", 1,
           not direct_query_supported,
           "Safe but requires user-provided QID; natural-language discovery absent")

    # W10/W11/W13 — original OSV ID lists, no full bodies.
    for code, ecosystem, package, version in [
        ("W10", "PyPI", "Django", "2.2.0"),
        ("W11", "PyPI", "Jinja2", "2.10.1"),
        ("W13", "npm", "lodash", "4.17.11"),
    ]:
        raw, expected = original_osv(ecosystem, package, version)
        output = call_osv(raw, ecosystem, package, version)
        source_ids = [x["id"] for x in raw["results"][0]["vulns"]]
        actual_ids = [x["id"] for x in output.get("advisories", [])]
        okay = (
            actual_ids == source_ids and len(actual_ids) == expected
            and all(x["source_url"].startswith("https://osv.dev/vulnerability/")
                    for x in output["advisories"])
            and output["commercial_bulk_redistribution_approved"] is False
            and output["raw_advisory_redistribution_authorized"] is False
            and "details" not in json.dumps(output)
        )
        record(code, f"Exact factual OSV IDs: {package}=={version}", 2, okay,
               f"Original source ID-only sample {expected} records, descriptions omitted")

    # W12 — zero findings is not a claim of security.
    empty, original_count = original_osv("npm", "react", "18.2.0")
    response = call_osv(empty, "npm", "react", "18.2.0")
    okay = (
        original_count == 0 and response["advisories"] == []
        and response["status"] == "no_returned_advisories"
        and response["no_advisory_not_equivalent_to_safe_package"] is True
        and response["source_population_complete"] is True
        and response["commercial_bulk_redistribution_approved"] is False
    )
    record("W12", "Empty OSV result must NOT mean safe package", 2, okay,
           "Official npm/react source result has 0 IDs; safety warning retained")

    # W14 — this deliberately ID-only feature cannot recommend patches.
    output = call_osv(*original_osv("npm", "lodash", "4.17.11")[:1],
                      "npm", "lodash", "4.17.11")
    # Inspect actual advisory *record fields*, not prose explaining which
    # content was deliberately omitted. An attribution notice mentioning
    # "no severity reproduced" is not a leaked severity score.
    forbidden = {"severity", "fixed", "summary", "details", "exploit",
                 "affected", "vulnerable_versions"}
    okay = (
        output["no_auto_remediation"] is True
        and all(not forbidden.intersection(record)
                for record in output["advisories"])
        and output["source_attribution"]["original_per_record_feed_verified"] is False
    )
    record("W14", "User asks for a specific patch recommendation", 1, okay,
           "Correct abstention: no fix/severity in ID-only API; extra workflow required")

    report = {
        "reviewer_type": "assistant_self_review_not_independent_human",
        "method": "original-source snapshot replay through budgeted callable; independent direct field extractor",
        "no_external_provider_calls": True,
        "run_count": 14,
        "points": sum(x["score"] for x in cases),
        "max_points": 28,
        "passed_decisions": sum(x["decision"] == "passed" for x in cases),
        "cases": cases,
        "critical_failure": any(x["decision"] == "failed" for x in cases),
        "supervised_opt_in_technical_threshold": 24,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    print("USER_PASS_FINAL=" + json.dumps({
        "score": report["points"], "max": 28, "cases": len(cases),
        "failed": [x["id"] for x in cases if x["score"] == 0],
        "clear_limitations": ["W09", "W14"],
    }), flush=True)
    if report["critical_failure"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
