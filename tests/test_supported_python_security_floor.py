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
