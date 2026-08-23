import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOSTED_TOOL_NAMES = {
    "discover_trends",
    "analyze_keyword_trend",
    "compare_keyword_trends",
    "discover_related_demand",
    "get_trend_context",
    "find_seo_opportunities",
}


def _load_json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def test_universal_plugin_manifest_is_self_contained_and_review_ready():
    manifest = _load_json(".codex-plugin/plugin.json")

    assert manifest["name"] == "trendpulse-by-digestseo"
    assert manifest["version"] == "0.1.0"
    assert manifest["license"] == "MIT"
    assert "apps" not in manifest
    assert "mcpServers" not in manifest

    interface = manifest["interface"]
    assert interface["displayName"] == "TrendPulse by DigestSEO"
    assert interface["shortDescription"] == "Search trends and demand"
    assert interface["capabilities"] == ["Read"]
    assert interface["websiteURL"] == "https://digestseo.com"
    assert interface["privacyPolicyURL"] == "https://digestseo.com/privacy/"
    assert interface["termsOfServiceURL"] == "https://digestseo.com/terms/"

    prompts = interface["defaultPrompt"]
    assert 1 <= len(prompts) <= 3
    assert all("\n" not in prompt and len(prompt) <= 128 for prompt in prompts)

    for field in ("composerIcon", "logo"):
        path = interface[field]
        assert path.startswith("./assets/")
        assert (ROOT / path.removeprefix("./")).is_file()


def test_submission_package_covers_exact_hosted_tool_catalog_and_review_cases():
    submission = _load_json("chatgpt-app-submission.json")

    assert submission["schema_version"] == 1
    assert submission["app_info"]["display_name"] == "TrendPulse by DigestSEO"
    assert set(submission["tools"]) == HOSTED_TOOL_NAMES
    assert len(submission["test_cases"]) == 5
    assert len(submission["negative_test_cases"]) == 3

    for tool_name, tool in submission["tools"].items():
        assert tool_name in HOSTED_TOOL_NAMES
        annotations = tool["annotations"]
        assert annotations == {
            "readOnlyHint": True,
            "openWorldHint": False,
            "destructiveHint": False,
        }
        justifications = tool["justifications"]
        assert set(justifications) == {
            "read_only_justification",
            "open_world_justification",
            "destructive_justification",
        }
        assert all(value.strip() for value in justifications.values())

    positive_tools = {
        name.strip()
        for case in submission["test_cases"]
        for name in case["tools_triggered"].split(",")
    }
    assert positive_tools == HOSTED_TOOL_NAMES
    assert all(case["tools_triggered"] is None for case in submission["negative_test_cases"])
