"""Opt-in real interpreter cold-import diagnostic; never calls providers."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.integration
def test_source_only_unified_cold_import_profiler_is_safe_and_honest():
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join((str(root / "src"), env.get("PYTHONPATH", "")))
    result = subprocess.run(
        [sys.executable, str(root / "scripts/measure_unified_cold_start.py"),
         "--rounds", "1"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-700:]
    lines = result.stdout.splitlines()
    trials = [
        json.loads(line.split("=", 1)[1]) for line in lines
        if line.startswith("COLD_IMPORT_TRIAL=")
    ]
    assert len(trials) == 2
    assert {row["mode"] for row in trials} == {"unified", "v3-only"}
    assert all(row["provider_queries_executed"] == 0 for row in trials)
    assert all(row["research_productivity_measured"] is False for row in trials)
    assert all(row["process_plus_import_ms"] > 0 for row in trials)
    summary = next(
        json.loads(line.split("=", 1)[1]) for line in lines
        if line.startswith("COLD_IMPORT_SUMMARY=")
    )
    assert summary["provider_queries_executed"] == 0
    assert summary["all_processes_exited"] is True
    assert set(summary["results"]) == {"unified", "v3-only"}
    assert all(row["rounds"] == 1 for row in summary["results"].values())
