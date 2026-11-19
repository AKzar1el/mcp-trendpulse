"""Offline acceptance tests for comparing two saved RSS headline captures."""

import json
from unittest.mock import patch

from click.testing import CliRunner

from mcp_trendpulse.cli import cli


def _item(name, slug, **overrides):
    item = {"title": name, "url": f"https://news.google.com/rss/articles/{slug}",
            "publisher": "Example", "publish_date": "2026-11-19T10:00:00Z"}
    return {**item, **overrides}


def _capture(*items):
    return {"schema_version": 1, "source": "google_news_rss",
            "content_level": "rss_headline_only", "count": len(items),
            "headlines": list(items)}


def _compare(tmp_path, older, newer, *args):
    old_file = tmp_path / "older.json"
    new_file = tmp_path / "newer.json"
    old_file.write_text(json.dumps(older), encoding="utf-8")
    new_file.write_text(json.dumps(newer), encoding="utf-8")
    with patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("No provider calls")):
        return CliRunner().invoke(cli, ["rss-compare", "--older", str(old_file),
                                        "--newer", str(new_file), *args])


def test_rss_compare_exact_url_delta_is_not_a_demand_claim(tmp_path):
    result = _compare(tmp_path, _capture(_item("Old", "a"), _item("Shared", "b")),
                      _capture(_item("Updated headline", "b"), _item("New", "c")),
                      "--format", "json")
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["comparison_method"] == "exact_url_membership"
    assert report["summary"]["newly_seen"] == 1
    assert report["summary"]["still_seen"] == 1
    assert report["summary"]["not_seen_in_newer"] == 1
    assert report["summary"]["retitled_same_url"] == 1
    assert report["source_authenticated"] is False
    assert [row["url"] for row in report["newly_seen"]] == ["https://news.google.com/rss/articles/c"]
    assert [row["url"] for row in report["not_seen_in_newer"]] == ["https://news.google.com/rss/articles/a"]
    assert "not evidence of demand growth" in " ".join(report["caveats"]).lower()


def test_rss_compare_empty_newer_is_not_article_disappearance(tmp_path):
    result = _compare(tmp_path, _capture(_item("Old", "a")), _capture(), "--format", "json")
    assert result.exit_code == 2, result.output
    report = json.loads(result.output)
    assert report["summary"]["newer_empty"] is True
    assert "feed window" in " ".join(report["caveats"]).lower()


def test_rss_compare_duplicate_capture_marks_review_needed(tmp_path):
    result = _compare(tmp_path, _capture(_item("First", "a"), _item("Duplicate", "a")),
                      _capture(_item("First", "a")), "--format", "json")
    assert result.exit_code == 2, result.output
    report = json.loads(result.output)
    assert report["summary"]["older_duplicate_urls"] == 1
    assert report["summary"]["still_seen"] == 1


def test_rss_compare_rejects_invalid_capture_without_partial_report(tmp_path):
    result = _compare(tmp_path, _capture(_item("Valid", "a")),
                      _capture(_item("Unsafe", "c", url="javascript:alert(1)")),
                      "--format", "json")
    assert result.exit_code == 1
    assert "comparison failed" in result.output.lower()
    assert '"newly_seen"' not in result.output


def test_rss_compare_markdown_escapes_untrusted_content(tmp_path):
    result = _compare(tmp_path, _capture(),
                      _capture(_item("x | [link](https://evil.test)", "new", publisher="*P*")))
    assert result.exit_code == 2, result.output
    assert "x \\|" in result.output
    assert "\\[link\\]" in result.output
    assert "\\*P\\*" in result.output


def test_rss_compare_never_overwrites_destination(tmp_path):
    destination = tmp_path / "out.md"
    destination.write_text("PRESERVE", encoding="utf-8")
    result = _compare(tmp_path, _capture(_item("Old", "a")),
                      _capture(_item("New", "b")), "--output-file", str(destination))
    assert result.exit_code != 0
    assert destination.read_text(encoding="utf-8") == "PRESERVE"


def test_rss_compare_saved_report_is_offline_and_valid(tmp_path):
    destination = tmp_path / "new-report.json"
    result = _compare(tmp_path, _capture(_item("Old", "a")),
                      _capture(_item("New", "b")), "--format", "json",
                      "--output-file", str(destination))
    assert result.exit_code == 0, result.output
    assert json.loads(destination.read_text(encoding="utf-8"))["summary"]["newly_seen"] == 1
