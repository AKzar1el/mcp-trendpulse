"""Prevent an end-of-life Python resolver branch from bringing back vulnerable Pillow."""

import re
import tomllib
from pathlib import Path


def test_python_floor_and_pillow_security_floor():
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["requires-python"] == ">=3.11"
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

    assert project["requires-python"] == ">=3.11"
    assert "Python 3.11 or newer is required" in guide
    assert "Python 3.10.18 remains installable" not in guide
    assert "uvx --python 3.11 mcp-trendpulse" in guide
