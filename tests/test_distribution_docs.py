import json
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


def test_cli_docs_include_brief_pack_fulfillment_command():
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    cli_section = readme.split("## CLI", 1)[1].split("## Development", 1)[0]

    assert "brief-pack" in cli_section
    assert "human-produced brief" in cli_section


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


def test_pages_visual_examples_are_not_presented_as_live_evidence():
    page = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")

    assert "illustrative preview - not live data" in page.lower()
    assert "last updated 4m ago" not in page
    assert "+340%" not in page
    assert "+412%" not in page
    assert "+287%" not in page
    assert "+196%" not in page


def test_pages_publish_agentic_resource_discovery_metadata():
    page = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")
    marker = '<script id="ard-discovery" type="application/ld+json">'

    assert marker in page
    ard_json = page.split(marker, 1)[1].split("</script>", 1)[0]
    entry = json.loads(ard_json)

    assert entry["@context"] == "https://agenticresourcediscovery.org/context/v1"
    assert entry["identifier"] == "urn:air:github.com:AKzar1el:mcp-trendpulse"
    assert entry["type"] == "application/mcp-server-card+json"
    assert entry["url"] == "https://raw.githubusercontent.com/AKzar1el/mcp-trendpulse/main/server.json"
    assert 2 <= len(entry["representativeQueries"]) <= 5
    assert entry["capabilities"]


def test_pages_publish_canonical_and_social_preview_metadata():
    page = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")

    assert '<link rel="canonical" href="https://akzar1el.github.io/mcp-trendpulse/">' in page
    assert (
        '<link rel="icon" type="image/png" '
        'href="https://raw.githubusercontent.com/AKzar1el/mcp-trendpulse/main/assets/logo-400.png">'
        in page
    )
    assert '<meta property="og:title" content="TrendPulse — Google Trends + Google News MCP">' in page
    assert '<meta property="og:url" content="https://akzar1el.github.io/mcp-trendpulse/">' in page
    assert (
        '<meta property="og:image" content="https://raw.githubusercontent.com/AKzar1el/mcp-trendpulse/main/assets/logo-400.png">'
        in page
    )
    assert '<meta name="twitter:card" content="summary">' in page


def test_pages_publish_current_mcpvault_verification_badge():
    page = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")

    assert 'https://mcpvault.io/badge/mcp-trendpulse.svg?theme=dark' in page
    assert (
        'https://mcpvault.io/servers/mcp-trendpulse/health?utm_source=external_badge&utm_medium=referral&utm_campaign=mcp_health_report'
        in page
    )
    assert 'alt="MCPVault: verified"' in page


def test_pages_top_trends_copy_matches_current_provider_paths():
    page = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")

    assert "realtime RSS feed or the 24-hour Trending Now feed" in page
    assert "Real-time spike feed from Google Trends RSS" not in page
