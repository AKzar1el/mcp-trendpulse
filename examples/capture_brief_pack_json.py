"""Capture Demand Brief JSON as original UTF-8 bytes across Windows shells.

This is a source-checkout example, not an installed CLI command or a provider retry.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Save brief-pack JSON without shell redirection or overwrites."
    )
    parser.add_argument("--output", required=True, type=Path, help="New JSON evidence file.")
    parser.add_argument("--keyword", action="append", required=True, help="Repeat up to five times.")
    parser.add_argument("--market", action="append", required=True, help="Repeat up to twice.")
    parser.add_argument("--timeframe", help="Optional Google Trends timeframe.")
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Pass through the opt-in flag only if the checked-out CLI supports it.",
    )
    args = parser.parse_args(argv)

    if not 1 <= len(args.keyword) <= 5 or not 1 <= len(args.market) <= 2:
        parser.error("Use one to five keywords and one or two markets.")

    output: Path = args.output
    if output.exists() or output.is_symlink():
        print(f"Refusing to overwrite existing evidence: {output}", file=sys.stderr)
        return 2
    if not output.parent.is_dir():
        print(f"Evidence output directory does not exist: {output.parent}", file=sys.stderr)
        return 2

    command = [sys.executable, "-m", "mcp_trendpulse.cli", "brief-pack"]
    for keyword in args.keyword:
        command.extend(("--keyword", keyword))
    for market in args.market:
        command.extend(("--market", market))
    if args.timeframe:
        command.extend(("--timeframe", args.timeframe))
    command.extend(("--format", "json"))
    if args.allow_partial:
        command.append("--allow-partial")

    child_env = os.environ.copy()
    child_env["PYTHONIOENCODING"] = "utf-8"
    try:
        result = subprocess.run(
            command, stdout=subprocess.PIPE, check=False, timeout=180, env=child_env
        )
    except (OSError, subprocess.TimeoutExpired):
        print("Could not capture brief-pack output; no evidence file was written.", file=sys.stderr)
        return 2

    if not result.stdout:
        print("brief-pack returned no JSON evidence; no file was written.", file=sys.stderr)
        return result.returncode or 2
    try:
        evidence = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        print("brief-pack did not return valid UTF-8 JSON; no file was written.", file=sys.stderr)
        return result.returncode or 2

    if (
        not isinstance(evidence, dict)
        or evidence.get("schema_version") != 1
        or evidence.get("source") != "Google Trends"
        or not isinstance(evidence.get("markets"), list)
    ):
        print("Unexpected brief-pack evidence schema; no file was written.", file=sys.stderr)
        return result.returncode or 2

    try:
        with output.open("xb") as handle:
            handle.write(result.stdout)
    except OSError:
        print("Could not write a new evidence file; no existing file was overwritten.", file=sys.stderr)
        return 2

    if result.returncode != 0 or evidence.get("incomplete") is True:
        print(
            f"Saved evidence to {output}, but the brief is INCOMPLETE. "
            "Inspect the error and do not treat this as finished evidence.",
            file=sys.stderr,
        )
        return result.returncode or 1

    print(f"Saved complete JSON evidence to {output}.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
