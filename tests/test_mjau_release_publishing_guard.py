"""MJAU merge safety: main pushes must not publish GHCR accidentally."""
from __future__ import annotations

from pathlib import Path

def test_container_publication_requires_explicit_manual_dispatch():
    workflow = (
        Path(__file__).resolve().parent.parent
        / ".github/workflows/publish-container.yml"
    ).read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "push:" in workflow  # Main builds may still be tested.
    assert workflow.count("if: github.event_name == 'workflow_dispatch'") == 3
    assert "if: github.event_name != 'pull_request'" not in workflow
    for step in ("Log in to GHCR", "Preserve immutable version tag", "Push image tags"):
        section = workflow.split(f"- name: {step}", 1)[1]
        section = section.split("\n      - name: ", 1)[0]
        assert "if: github.event_name == 'workflow_dispatch'" in section


def test_public_container_context_excludes_unreleased_v3_pilot():
    root = Path(__file__).resolve().parent.parent
    exclusions = {
        line.strip()
        for line in (root / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert "src/mcp_trendpulse/mjau_v3/" in exclusions
    assert "docs/mjau-v3/" in exclusions
    assert "COPY . /app" in (root / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY . /app" in (root / "Dockerfile.mcp-registry").read_text(encoding="utf-8")

    for workflow_name in ("container.yml", "publish-container.yml"):
        workflow = (
            root / ".github" / "workflows" / workflow_name
        ).read_text(encoding="utf-8")
        assert "Verify unreleased V3 pilot excluded from image" in workflow
        assert "find_spec('mcp_trendpulse.mjau_v3') is None" in workflow
        assert "Path('/app/src/mcp_trendpulse/mjau_v3').exists()" in workflow
