"""Keep the approved public package/version in sync with the V3 release hold."""
import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_public_version_and_python_floor():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
    assert project["project"]["version"] == "0.3.0"
    assert manifest["version"] == manifest["packages"][0]["version"] == "0.3.0"
    assert project["project"]["requires-python"] == ">=3.11.5"
    for manifest_path in (
        "manifest.json",
        "plugin.json",
        "gemini-extension.json",
        ".claude-plugin/plugin.json",
        ".cursor-plugin/plugin.json",
    ):
        declared = json.loads((ROOT / manifest_path).read_text(encoding="utf-8"))
        assert declared["version"] == project["project"]["version"], manifest_path


def test_public_package_excludes_unreleased_v3_pilot():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    find = project["tool"]["setuptools"]["packages"]["find"]
    assert find["where"] == ["src"]
    assert "mcp_trendpulse.mjau_v3" in find["exclude"]
    assert "mcp_trendpulse.mjau_v3.*" in find["exclude"]
    assert "prune src/mcp_trendpulse/mjau_v3" in (
        ROOT / "MANIFEST.in"
    ).read_text(encoding="utf-8")
    assert "recursive-exclude tests test_mjau_v3*.py" in (
        ROOT / "MANIFEST.in"
    ).read_text(encoding="utf-8")
    assert (ROOT / "src/mcp_trendpulse/mjau_v3/mcp.py").is_file()


def test_public_build_workflows_gate_artifacts_before_publish():
    step = "python scripts/check_public_distribution.py dist"
    for filename in ["ci.yml", "publish.yml"]:
        text = (ROOT / ".github/workflows" / filename).read_text(encoding="utf-8")
        assert step in text
        assert text.index(step) > text.index("uv build")
        assert text.index(step) < text.index("twine check")
