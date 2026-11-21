"""End-to-end smoke against an ACTUAL self-hosted RSSHub instance.

Use only loopback:180? No, the adapter is fixed to 127.0.0.1:1200.
The built-in /test/1 RSSHub feed is independent of remote scraping failures.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

from mcp_trendpulse.intelligence_core import BudgetCache, collect, plan_source


def main() -> int:
    output = Path(os.environ.get("TRENDPULSE_INTEL_RSSHUB_REPORT", "intelligence-rsshub.json"))
    root = Path(os.environ.get(
        "TRENDPULSE_INTEL_CACHE_DIR", "/tmp/trendpulse-rsshub-smoke"))
    report: dict = {"checked_at": datetime.now(timezone.utc).isoformat(),
                    "local_server": "127.0.0.1:1200",
                    "mandatory": {}, "external_feed_optional": {}}
    try:
        opener = build_opener(ProxyHandler({}))
        with opener.open("http://127.0.0.1:1200/healthz", timeout=5) as response:
            if response.status != 200:
                raise AssertionError("RSSHub healthz refused request")
        plan = plan_source("rsshub_local", identifier="test/1", limit=5)
        result = collect(plan, cache=BudgetCache(root), fetch=True, timeout=18)
        evidence = result.get("observations") or {}
        raw = result.get("data") or {}
        values = [x.get("text") for x in raw.get("observations", [])
                  if isinstance(x, dict)]
        passed = (
            result.get("status") == "observed"
            and raw.get("root") in ("rss", "feed")
            and evidence.get("record_count", 0) >= 5
            and "Test 1" in values
            and "Title1" in values
        )
        report["mandatory"] = {
            "status": "passed" if passed else "failed",
            "provider_status": result.get("status"),
            "xml_root": raw.get("root"),
            "observations": evidence.get("record_count"),
            "saw_test_title": "Test 1" in values,
            "saw_test_item": "Title1" in values,
            "source_url": plan.url,
        }
        if not passed:
            raise AssertionError("RSSHub /test/1 did not contain validated XML feed entries")
        # This route requires third-party GitHub access; report but do not
        # mark it as a local-service regression if GitHub blocks a runner.
        try:
            external = plan_source(
                "rsshub_local", identifier="github/issue/DIYgod/RSSHub", limit=5
            )
            result = collect(external, cache=BudgetCache(root), fetch=True, timeout=15)
            report["external_feed_optional"] = {
                "status": result.get("status"),
                "source_url": external.url,
                "observations": (result.get("observations") or {}).get("record_count"),
            }
        except (OSError, ValueError) as exc:
            report["external_feed_optional"] = {
                "status": "unavailable", "reason": type(exc).__name__,
            }
        return 0
    except (OSError, ValueError, AssertionError) as exc:
        if report["mandatory"].get("status") != "passed":
            report["mandatory"] = {
                **report["mandatory"], "status": "failed",
                "error_type": type(exc).__name__,
            }
        return 1
    finally:
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
