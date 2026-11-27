"""Security regression: main PR #381 dependency pins inherited by V2."""
from __future__ import annotations

import tomllib
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent


def _metadata():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    lock = tomllib.loads((ROOT / "uv.lock").read_text("utf-8"))
    return project, lock


def _assert_patched_pins(lock):
    expected = {"soupsieve": "4.1.3", "opentelemetry-api": "1.45.2", "beautifulsoup4": "4.13.4"}
    for name, pin in expected.items():
        # A universal lock can contain multiple entries for one package name.
        versions = [package["version"] for package in lock["package"] if package["name"] == name]
        assert versions, f"{name} missing from lock"
        assert all(version == pin for version in versions), f"{name}: expected {pin}, found {versions}"


def test_prior_dependabot_alerts_have_patched_pins():
    _, lock = _metadata()
    _assert_patched_pins(lock)


@pytest.mark.parametrize("name, vulnerable", [("soupsieve", "2.9.2"), ("opentelemetry-api", "1.45.1")])
@pytest.mark.parametrize("vulnerable_first", [True, False])
def test_patched_pins_reject_shadowed_lock_versions(tmp_path, monkeypatch, name, vulnerable, vulnerable_first):
    monkeypatch.setitem(globals(), "ROOT", tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    rows = [("soupsieve", "4.1.3"), ("opentelemetry-api", "1.45.2"), ("beautifulsoup4", "4.13.4")]
    rows.insert(0 if vulnerable_first else len(rows), (name, vulnerable))
    (tmp_path / "uv.lock").write_text(
        "".join(f'[[package]]\nname = "{n}"\nversion = "{v}"\n' for n, v in rows),
        encoding="utf-8",
    )
    _, lock = _metadata()
    with pytest.raises(AssertionError):
        _assert_patched_pins(lock)


def test_patched_pins_accept_equal_versions_for_multiple_resolver_branches():
    _, lock = _metadata()
    lock["package"].append({"name": "soupsieve", "version": "4.1.3"})
    _assert_patched_pins(lock)


def test_patched_pins_reject_missing_dependency():
    _, lock = _metadata()
    lock["package"] = [package for package in lock["package"] if package["name"] != "soupsieve"]
    with pytest.raises(AssertionError, match="soupsieve missing from lock"):
        _assert_patched_pins(lock)


def test_python_311_patch_compatibility_is_explicit():
    project, lock = _metadata()
    assert project["project"]["requires-python"] == ">=3.11.5"
    assert lock["requires-python"] == ">=3.11.5"


def test_direct_deps_keep_source_security_boundaries():
    project, _ = _metadata()
    deps = project["project"]["dependencies"]
    assert "soupsieve>=4.0.0" in deps
    assert "opentelemetry-api>=1.45.2" in deps
