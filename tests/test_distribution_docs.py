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


def test_vscode_mcp_json_uses_current_top_level_servers_shape():
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    vscode_section = readme.split("### VS Code", 1)[1].split("### Cursor", 1)[0]

    assert "`.vscode/mcp.json`" in vscode_section
    assert '  "servers": {' in vscode_section
    assert '  "mcp": {' not in vscode_section


def test_vscode_one_click_install_uses_stable_pypi_package():
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    vscode_section = readme.split("### VS Code", 1)[1].split("### Cursor", 1)[0]

    assert "https://vscode.dev/redirect?url=vscode%3Amcp%2Finstall%3F" in vscode_section
    assert "%2522command%2522%253A%2522uvx%2522" in vscode_section
    assert "%2522args%2522%253A%255B%2522mcp-trendpulse%2522%255D" in vscode_section
    assert "git%2Bhttps%3A%2F%2Fgithub.com%2FAKzar1el%2Fmcp-trendpulse.git" not in vscode_section


def test_kiro_docs_link_community_privacy_notice_and_support():
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    privacy = (PROJECT_ROOT / "PRIVACY.md").read_text(encoding="utf-8")
    kiro_section = readme.split("### Kiro", 1)[1].split("### ChatGPT", 1)[0]

    assert "[TrendPulse Community MCP Privacy Notice](PRIVACY.md)" in kiro_section
    assert "info@tomiseregi.si" in kiro_section
    assert "local `stdio` execution path" in privacy
    assert "does not add hidden analytics" in privacy
    assert "unreleased hosted TrendPulse service" in privacy


def test_client_install_docs_use_stable_pypi_package():
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    claude_section = readme.split("### Claude Desktop", 1)[1].split("### VS Code", 1)[0]
    vscode_section = readme.split("### VS Code", 1)[1].split("### Cursor", 1)[0]
    cursor_section = readme.split("### Cursor", 1)[1].split("### Kiro", 1)[0]
    kiro_section = readme.split("### Kiro", 1)[1].split("### ChatGPT", 1)[0]

    for section in (claude_section, vscode_section, cursor_section):
        assert "git+https://github.com/AKzar1el/mcp-trendpulse.git" not in section
        assert '"command": "uvx"' in section
        assert '"mcp-trendpulse"' in section

    assert "git%2Bhttps%3A%2F%2Fgithub.com%2FAKzar1el%2Fmcp-trendpulse.git" not in kiro_section
    assert "%22args%22%3A%5B%22mcp-trendpulse%22%5D" in kiro_section


def test_lm_studio_one_click_install_uses_stable_pypi_package():
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    lm_studio_section = readme.split("### LM Studio", 1)[1].split("### ChatGPT", 1)[0]

    assert "https://lmstudio.ai/install-mcp?" in lm_studio_section
    assert "name=mcp-trendpulse" in lm_studio_section
    assert "eyJjb21tYW5kIjoidXZ4IiwiYXJncyI6WyJtY3AtdHJlbmRwdWxzZSJdfQ%3D%3D" in lm_studio_section
    assert "git+https://github.com/AKzar1el/mcp-trendpulse.git" not in lm_studio_section
