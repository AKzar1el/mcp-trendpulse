"""M01: two real, bounded, browserless Google Trends RSS source calls in CI.

One explicit, local-quota-gated operation for US and GB; never retry a 429.
Print safe metadata and small public source-label excerpts only.
"""
from __future__ import annotations

import asyncio
import json

from mcp_trendpulse.intelligence_rss import discover_trending_rss
from mcp_trendpulse.intelligence_signal import TrendSignal


async def main() -> None:
    for country in ("US", "GB"):
        report = await discover_trending_rss(country, execute=True)
        sample = []
        for item in report["trends"][:2]:
            signal = TrendSignal.model_validate(item["signal"])
            sample.append({
                "source_term": signal.raw_term[:80],
                "traffic_bucket": signal.value_label,
                "published_at": signal.published_at.isoformat()
                                if signal.published_at is not None else None,
                "news_count": len(item["related_news"]),
            })
        print(json.dumps({
            "country": country, "status": report["status"],
            "count": report["records_observed"],
            "cache_hit": report["cache_hit"],
            "source_requests_performed": report["source_requests_performed"],
            "source_url": report["source_url"],
            "sample": sample,
        }, ensure_ascii=False, sort_keys=True), flush=True)
        if (report["status"] not in {"observed", "observed_partial"}
                or not report["trends"] or report["source_requests_performed"] != 1):
            raise SystemExit("M01 real RSS source verification incomplete for " + country)
    print("M01 bounded live RSS verification PASSED (US and GB)", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
