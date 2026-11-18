"""Seed a disposable *paused* watch in an ephemeral local changedetection.io.

This script refuses to touch a server other than 127.0.0.1:5000 and requires
a dedicated CI opt-in environment gate. Never use against a real user service.
No API tokens or watch details are printed.
"""

from __future__ import annotations

import json
import os
import sys
from urllib.request import Request, build_opener, ProxyHandler

BASE = "http://127.0.0.1:5000/api/v1/watch"


def main() -> None:
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get(
        "TRENDPULSE_E2E_DISPOSABLE_INSTANCE"
    ) != "YES":
        raise RuntimeError("Refusing to alter any non-ephemeral change monitor")
    key = os.environ.get("TRENDPULSE_INTEL_CHANGEDETECTION_KEY", "")
    if not key:
        raise RuntimeError("Ephemeral test service key is absent")
    opener = build_opener(ProxyHandler({}))
    payload = json.dumps({
        "url": "https://example.com/",
        "title": "TrendPulse disposable MCP read-only smoke",
        "paused": True,
    }).encode("utf-8")
    request = Request(
        BASE, method="POST", data=payload, headers={
            "x-api-key": key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    )
    with opener.open(request, timeout=12) as res:
        if res.status not in (200, 201):
            raise AssertionError("Ephemeral API refused paused watch fixture")
        item = json.loads(res.read(4096))
    watch_id = item.get("uuid") if isinstance(item, dict) else None
    if not isinstance(watch_id, str) or len(watch_id) < 8:
        raise AssertionError("Ephemeral API did not create a valid watch")
    listing = Request(BASE, headers={"x-api-key": key, "Accept": "application/json"})
    with opener.open(listing, timeout=10) as res:
        if res.status != 200:
            raise AssertionError("Ephemeral watch-list GET returned non-200")
        body = json.loads(res.read(128 * 1024))
    if not isinstance(body, dict) or watch_id not in body:
        raise AssertionError("Ephemeral watch not visible through the read-only API")
    print("Disposable paused watch seeded and API listing verified; no secrets output")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Disposable change-monitor fixture failed: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1) from None
