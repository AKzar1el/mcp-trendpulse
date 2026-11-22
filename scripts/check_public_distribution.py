"""Fail release builds if gated V3 source leaks into public V1/V2 distributions.

Run after building: python scripts/check_public_distribution.py dist
All checks are offline and use only the Python standard library.
"""
from __future__ import annotations

import argparse
import email
import json
import tarfile
import tomllib
import zipfile
from pathlib import Path


def verify(dist_dir: Path) -> dict[str, object]:
    project_root = Path(__file__).resolve().parent.parent
    project = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))
    version = project["project"]["version"]
    assert project["project"]["requires-python"] == ">=3.11.5"
    assert project["tool"]["setuptools"]["packages"]["find"]["exclude"] == [
        "mcp_trendpulse.mjau_v3",
        "mcp_trendpulse.mjau_v3.*",
    ]

    manifest = json.loads((project_root / "server.json").read_text(encoding="utf-8"))
    assert manifest["version"] == manifest["packages"][0]["version"] == version
    wheels = list(dist_dir.glob("mcp_trendpulse-*.whl"))
    sdists = list(dist_dir.glob("mcp_trendpulse-*.tar.gz"))
    assert len(wheels) == len(sdists) == 1, (wheels, sdists)
    assert wheels[0].name == f"mcp_trendpulse-{version}-py3-none-any.whl"
    assert sdists[0].name == f"mcp_trendpulse-{version}.tar.gz"

    with zipfile.ZipFile(wheels[0]) as wheel:
        wheel_names = set(wheel.namelist())
        metadata_name = next(x for x in wheel_names if x.endswith(".dist-info/METADATA"))
        metadata = email.message_from_bytes(wheel.read(metadata_name))
        assert metadata["Version"] == version
        assert metadata["Requires-Python"] == ">=3.11.5"
        requirements = [r.lower() for r in metadata.get_all("Requires-Dist", [])]
        assert any(r.startswith("soupsieve>=4.0.0") for r in requirements)
        assert any(r.startswith("opentelemetry-api>=1.45.2") for r in requirements)
        must_have = {
            "mcp_trendpulse/server.py",
            "mcp_trendpulse/hosted.py",
            "mcp_trendpulse/cli.py",
            "mcp_trendpulse/intelligence_mcp.py",
            "mcp_trendpulse/intelligence_opportunities.py",
            "mcp_trendpulse/mjau_v2/endoflife_release.py",
        }
        assert must_have <= wheel_names, must_have - wheel_names
        assert not any("/mjau_v3/" in f for f in wheel_names)
        wheel_python_count = sum(n.startswith("mcp_trendpulse/") and n.endswith(".py") for n in wheel_names)

    with tarfile.open(sdists[0], "r:gz") as archive:
        sources = {m.name for m in archive.getmembers() if m.isfile()}
        assert not any("/mjau_v3/" in n for n in sources)
        assert not any("/test_mjau_v3" in n for n in sources)
        assert any(x.endswith("/src/mcp_trendpulse/mjau_v2/endoflife_release.py") for x in sources)
        assert any(x.endswith("/src/mcp_trendpulse/intelligence_mcp.py") for x in sources)

    assert (project_root / "src/mcp_trendpulse/mjau_v3/mcp.py").is_file(), (
        "V3 pilot must remain in the repository for independent source review"
    )
    return {
        "result": "PASS",
        "version": version,
        "public_wheel_python_modules": wheel_python_count,
        "public_sdist_entries": len(sources),
        "v3_in_public_distribution": False,
        "v3_kept_in_repository": True,
        "security_dependency_floors_enforced": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dist", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.dist), sort_keys=True))


if __name__ == "__main__":
    main()
