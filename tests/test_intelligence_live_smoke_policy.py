"""Keep keyless shared-CI-IP source blocks visible but nonfatal.

An optional network check is inconclusive on 403/429; it is not an
observed source, and unit tests still validate GitHub parsing/quality.
"""
from __future__ import annotations

import runpy
from pathlib import Path


def test_github_keyless_ci_check_is_explicit_optional_availability():
    script = Path(__file__).resolve().parents[1] / "scripts" / "intelligence_live_smoke.py"
    settings = runpy.run_path(str(script), run_name="intelligence_live_smoke_policy")
    mandatory = {source for source, _ in settings["CASES"]}
    optional = {source for source, _ in settings["OPTIONAL_CASES"]}
    assert "github_issues" not in mandatory
    assert "github_issues" in optional
    assert "lever" in optional
    assert "cordis" in mandatory
    assert "usaspending" in mandatory
    assert "cfpb" in mandatory
