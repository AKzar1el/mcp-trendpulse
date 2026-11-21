"""Security regression: main PR #381 dependency pins inherited by V2."""
from __future__ import annotations

import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _metadata():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    lock = tomllib.loads((ROOT / "uv.lock").read_text("utf-8"))
    versions = {package["name"]: package["version"] for package in lock["package"]}
    return project, lock, versions


def test_prior_dependabot_alerts_have_patched_pins():
    _, _, packages = _metadata()
    assert packages["soupsieve"] == "4.1.3"
    assert packages["opentelemetry-api"] == "1.45.2"
    assert packages["beautifulsoup4"] == "4.13.4"


def test_python_311_patch_compatibility_is_explicit():
    project, lock, _ = _metadata()
    assert project["project"]["requires-python"] == ">=3.11.5"
    assert lock["requires-python"] == ">=3.11.5"


def test_direct_deps_keep_source_security_boundaries():
    project, _, _ = _metadata()
    deps = project["project"]["dependencies"]
    assert "soupsieve>=4.0.0" in deps
    assert "opentelemetry-api>=1.45.2" in deps
