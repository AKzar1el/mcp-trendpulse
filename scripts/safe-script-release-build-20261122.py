"""Safely verify the versioned public TrendPulse wheel and sdist.

Refuses to reuse an existing build directory and never publishes, overwrites,
or deletes repository files. Windows stderr is captured by Python rather than
PowerShell error redirection. Requires uv available on PATH.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUTPUT = pathlib.Path(tempfile.gettempdir()) / "trendpulse-release-v0.3.0-20261122-safe"
if OUTPUT.exists():
    raise SystemExit(f"Refusing to overwrite existing output: {OUTPUT}")
OUTPUT.mkdir(parents=False)
commands = [
    ["uv", "build", "--offline", "--out-dir", str(OUTPUT)],
    [sys.executable, str(ROOT / "scripts/check_public_distribution.py"), str(OUTPUT)],
    [
        sys.executable, "-m", "pytest", "-q",
        "tests/test_public_release_boundary.py",
        "tests/test_distribution_docs.py",
        "tests/test_supported_python_security_floor.py",
        "--tb=short",
    ],
]
for index, command in enumerate(commands, start=1):
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            timeout=540,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise SystemExit(f"Stage {index} timed out after 540 seconds: {error}") from error
    (OUTPUT / f"stage-{index}.log").write_text(result.stdout, encoding="utf-8")
    print(f"STAGE_{index}_EXIT={result.returncode}")
    print(result.stdout[-1300:])
    if result.returncode:
        raise SystemExit(f"Release candidate stage {index} failed; no publishing occurred.")
print(f"SAFE_RELEASE_OUTPUT={OUTPUT}")
print("PUBLIC_DISTRIBUTION_PREFLIGHT=PASS")
