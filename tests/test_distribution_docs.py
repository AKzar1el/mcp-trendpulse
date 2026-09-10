from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_install_docs_use_published_pypi_package():
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    agent_guide = (PROJECT_ROOT / "llms-install.md").read_text(encoding="utf-8")

    assert "The package is not yet published to PyPI" not in readme
    assert "Until the first package release exists" not in readme
    assert "uvx mcp-trendpulse" in readme

    assert "The package is not yet published to PyPI" not in agent_guide
    assert '"args": ["mcp-trendpulse"]' in agent_guide
