"""Read-only live provider smoke with no paid APIs or private keys.

This checks request transport and response contracts, not commercial prediction.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from mcp_trendpulse.intelligence_core import BudgetCache, collect, plan_source

CASES = (
    ("gdelt_latest", {"limit": 2}),
    ("eurostat", {"dataset": "nama_10_gdp", "country": "SI", "limit": 2}),
    ("ted", {"keyword": "PD = (20261001 <> 20261031)", "limit": 2}),
    ("cellar", {"keyword": "battery", "limit": 2}),
    ("github_issues", {"keyword": "webhook", "limit": 2}),
    ("worldbank", {"country": "SI", "identifier": "NY.GDP.MKTP.CD", "limit": 2}),
    ("greenhouse", {"company": "mozilla", "limit": 2}),
    ("smartrecruiters", {"company": "BoschGroup", "limit": 2}),
    ("cfpb", {"keyword": "credit card", "limit": 2}),
    ("cordis", {"keyword": "battery", "limit": 2}),
    ("usaspending", {"keyword": "solar", "limit": 2}),
    ("sec_companyconcept", {"identifier": "320193", "keyword": "Assets", "limit": 2}),
    ("gleif", {"keyword": "Siemens", "limit": 2}),
    ("ecb", {"identifier": "EXR/D.USD.EUR.SP00.A", "limit": 2}),
    ("copernicus", {"limit": 2}),
)

# OPSI currently returns HTTP 500 from GitHub runners. Keep a transparent
# optional probe; do not conflate provider outages with code regressions.
OPTIONAL_CASES = (("opsi_slovenia", {"limit": 2}),)


def main() -> int:
    root = Path(os.environ.get(
        "TRENDPULSE_INTEL_CACHE_DIR", "/tmp/trendpulse-live-contract-cache"))
    cache = BudgetCache(root)
    checks = []
    for source, params in CASES:
        try:
            plan = plan_source(source, **params)
            out = collect(plan, cache=cache, fetch=True,
                          timeout=25 if source in {"worldbank", "ecb"} else 10)
            item = {
                "source": source,
                "status": out.get("status"),
                "reason": out.get("reason"),
                "http_status": out.get("http_status"),
                "records_observed": (out.get("observations") or {}).get("record_count"),
                "source_url": plan.url,
                "source_documentation": plan.docs,
            }
        except (ValueError, OSError) as exc:
            item = {"source": source, "status": "exception", "reason": type(exc).__name__,
                    "detail": str(exc)[:150]}
        checks.append(item)
        print(json.dumps(item, sort_keys=True, ensure_ascii=False), flush=True)
        if source == "greenhouse" and item["status"] == "observed":
            try:
                from mcp_trendpulse.intelligence_jobs import (
                    extract_job_pains, normalize_jobs,
                )
                rows = (out.get("data") or {}).get("jobs", [])
                job = next(x for x in rows if isinstance(x, dict) and x.get("id"))
                detail_plan = plan_source(
                    "greenhouse_job", company=params["company"],
                    identifier=str(job["id"]),
                )
                detail = collect(detail_plan, cache=cache, fetch=True, timeout=10)
                normalized = normalize_jobs("greenhouse", params["company"], detail.get("data"))
                categories = extract_job_pains(normalized)["pain_hypotheses"]
                detail_item = {
                    "source": "greenhouse_job",
                    "status": "observed" if detail["status"] == "observed" and
                              normalized and normalized[0]["description"] else "unavailable",
                    "records_observed": len(normalized),
                    "description_chars": len(normalized[0]["description"]) if normalized else 0,
                    "pain_categories_detected": [c["category"] for c in categories],
                }
            except (ValueError, OSError, KeyError, StopIteration, TypeError) as exc:
                detail_item = {"source": "greenhouse_job", "status": "exception",
                               "reason": type(exc).__name__}
            checks.append(detail_item)
            print(json.dumps(detail_item, sort_keys=True, ensure_ascii=False), flush=True)
    optional = []
    for source, params in OPTIONAL_CASES:
        try:
            plan = plan_source(source, **params)
            outcome = collect(plan, cache=cache, fetch=True, timeout=10)
            item = {"source": source, "status": outcome.get("status"),
                    "http_status": outcome.get("http_status"),
                    "reason": outcome.get("reason"),
                    "optional_external_provider": True}
        except (ValueError, OSError) as exc:
            item = {"source": source, "status": "exception",
                    "reason": type(exc).__name__,
                    "optional_external_provider": True}
        optional.append(item)
        print(json.dumps(item, sort_keys=True, ensure_ascii=False), flush=True)
    report = {
        "optional_external_checks": optional,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "tested": len(checks),
        "passed": sum(x["status"] == "observed" for x in checks),
        "failed": sum(x["status"] != "observed" for x in checks),
        "note": "No secrets/raw records; key-only and local-only services excluded",
    }
    dest = Path(os.environ.get("TRENDPULSE_INTEL_SMOKE_REPORT", "intelligence-live.json"))
    dest.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Summary: {report['passed']}/{report['tested']} sources passed", flush=True)
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
