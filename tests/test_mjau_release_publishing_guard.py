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
