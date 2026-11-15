"""Keep supported runtimes and resolved dependencies above known security floors."""

import re
import tomllib
from pathlib import Path


def test_python_floor_and_pillow_security_floor():
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["requires-python"] == ">=3.11.5"
    assert "pillow>=13.0.0" in project["dependencies"]

    lock = tomllib.loads(Path("uv.lock").read_text(encoding="utf-8"))
    installed = [package["version"] for package in lock["package"] if package["name"] == "pillow"]
    assert installed
    for version in installed:
        parts = re.match(r"^(\d+)\.(\d+)\.(\d+)", version)
        assert parts is not None
        assert tuple(map(int, parts.groups())) >= (13, 0, 0)

def test_agent_install_guide_matches_python_floor():
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
    guide = Path("llms-install.md").read_text(encoding="utf-8")

    assert project["requires-python"] == ">=3.11.5"
    assert "Python 3.11.5 or newer is required" in guide
    assert "Python 3.10.18 remains installable" not in guide
    assert "uvx --python 3.11 mcp-trendpulse" in guide


def test_lock_excludes_vulnerable_soupsieve_and_opentelemetry():
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
    dependencies = project["dependencies"]
    assert "soupsieve>=4.0.0" in dependencies
    assert "opentelemetry-api>=1.45.2" in dependencies

    lock = tomllib.loads(Path("uv.lock").read_text(encoding="utf-8"))
    assert lock["requires-python"] == ">=3.11.5"
    for name, floor in (("soupsieve", (4, 0, 0)), ("opentelemetry-api", (1, 45, 2))):
        versions = [package["version"] for package in lock["package"] if package["name"] == name]
        assert versions, f"{name} missing from locked dependencies"
        for version in versions:
            parsed = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
            assert parsed is not None, f"unexpected {name} version: {version}"
            assert tuple(map(int, parsed.groups())) >= floor
