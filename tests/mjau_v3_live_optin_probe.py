"""Explicit/manual source smoke for the optional MJAU v3 MCP backends.

Never imported by pytest. Makes at most ONE free public Wikidata request and
ONE free public OSV query to widely known nonprivate coordinates. Creates an
isolated budget/cache directory. Does not touch the live TrendPulse connector.
"""
from __future__ import annotations

from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter
import json

from mcp_trendpulse.intelligence_core import BudgetCache
from mcp_trendpulse.mjau_v3.budgeted_sources import osv_package_ids, wikidata_identity


def main() -> None:
    receipts: dict[str, object] = {
        "mode": "explicit_single_request_per_source",
        "public_only": True,
        "installed_mcp_modified": False,
    }
    with TemporaryDirectory(prefix="mjau-v3-pass5-", ignore_cleanup_errors=True) as root:
        cache = BudgetCache(Path(root))
        plans = []
        for _ in range(20):
            begin = perf_counter()
            plan = wikidata_identity(["Q64"], ["en", "de", "sl"], execute=False, cache=cache)
            plans.append(round((perf_counter() - begin) * 1000, 3))
            assert plan["status"] == "planned"
            assert plan["network_performed"] is False
        receipts["plan_only_median_ms"] = median(plans)
        receipts["plan_only_max_ms"] = max(plans)

        start = perf_counter()
        wiki = wikidata_identity(
            ["Q64"], ["en", "de", "sl"], name="Berlin", execute=True, cache=cache,
        )
        receipts["wikidata"] = {
            "status": wiki["status"],
            "reason": wiki.get("reason"),
            "network_performed": wiki["network_performed"],
            "time_ms": round((perf_counter() - start) * 1000, 2),
            "candidate_qids": wiki.get("name_candidates", {}).get("candidate_qids"),
            "identity_verified": wiki.get("identity_verified"),
        }
        if wiki["status"].startswith("source_entities_"):
            assert wiki["identity_verified"] is False
            assert wiki["name_candidates"]["candidate_qids"] == ["Q64"]
            cached = wikidata_identity(
                ["Q64"], ["en", "de", "sl"], name="Berlin", execute=True, cache=cache,
            )
            assert cached["cache_hit"] is True
            assert cached["network_performed"] is False
            receipts["wikidata"]["cached_answer_consistent"] = (
                cached["name_candidates"]["candidate_qids"] == ["Q64"]
            )

        start = perf_counter()
        osv = osv_package_ids(
            "npm", "lodash", "4.17.11", execute=True, cache=cache,
        )
        receipts["osv"] = {
            "status": osv["status"],
            "reason": osv.get("reason"),
            "network_performed": osv["network_performed"],
            "time_ms": round((perf_counter() - start) * 1000, 2),
            "advisory_count_projected": osv.get("advisory_count_projected"),
            "no_auto_remediation": osv.get("no_auto_remediation"),
            "no_advisory_not_equivalent_to_safe_package": osv.get(
                "no_advisory_not_equivalent_to_safe_package"
            ),
            "commercial_bulk_redistribution_approved": osv.get(
                "commercial_bulk_redistribution_approved"
            ),
        }
        if osv["status"] != "source_unavailable":
            assert osv["no_advisory_not_equivalent_to_safe_package"] is True
            assert osv["commercial_bulk_redistribution_approved"] is False
            cached = osv_package_ids(
                "npm", "lodash", "4.17.11", execute=True, cache=cache,
            )
            assert cached["cache_hit"] is True
            assert cached["network_performed"] is False
            receipts["osv"]["cached_answer_consistent"] = (
                cached["advisory_count_projected"] == osv["advisory_count_projected"]
            )
    print(json.dumps(receipts, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
