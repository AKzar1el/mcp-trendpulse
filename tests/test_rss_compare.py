"""Offline acceptance tests for comparing two saved RSS headline captures."""

import csv
import io
import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from mcp_trendpulse.cli import cli
from mcp_trendpulse.rss_compare import compare_saved_rss_headlines


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
    assert "filter" not in report
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


@pytest.mark.parametrize("sort_url", [False, True])
def test_rss_compare_opt_in_retitles_respects_topic_and_order(tmp_path, sort_url):
    older = _capture(_item("AI before Z", "z"), _item("Before A", "a"),
                     _item("AI unchanged", "same"), _item("Other", "other"))
    newer = _capture(_item("After Z", "z"), _item("AI after A", "a"),
                     _item("AI unchanged", "same"), _item("Other new", "other"))
    args = ["--format", "json", "--contains", "ai"]
    if sort_url:
        args.append("--sort-url")
    baseline = _compare(tmp_path, older, newer, *args)
    result = _compare(tmp_path, older, newer, *args, "--show-retitles")
    assert result.exit_code == baseline.exit_code == 0, result.output
    report = json.loads(result.output)
    expected = [
        {"url": "https://news.google.com/rss/articles/z", "older_title": "AI before Z", "newer_title": "After Z"},
        {"url": "https://news.google.com/rss/articles/a", "older_title": "Before A", "newer_title": "AI after A"},
    ]
    if sort_url:
        expected.reverse()
    assert report.pop("retitled_urls") == expected
    assert report == json.loads(baseline.output)


def test_rss_compare_retitles_uses_first_record_and_escapes_markdown(tmp_path):
    older = _capture(_item("Old | [link]", "a"), _item("Ignore duplicate", "a"))
    newer = _capture(_item("New *headline*", "a", publisher=None))
    result = _compare(tmp_path, older, newer, "--show-retitles")
    assert result.exit_code == 2, result.output
    assert "## Retitled URLs" in result.output
    assert r"Old \| \[link\]" in result.output
    assert r"New \*headline\*" in result.output
    assert "Ignore duplicate" not in result.output
    assert "not prove editorial" in result.output


@pytest.mark.parametrize("sort_url", [False, True])
def test_rss_compare_show_retitles_leaves_csv_unchanged(tmp_path, sort_url):
    older = _capture(_item("=AI old", "a"))
    newer = _capture(_item("+AI new", "a"))
    args = ["--format", "csv", "--contains", "AI"]
    if sort_url:
        args.append("--sort-url")
    baseline = _compare(tmp_path, older, newer, *args)
    result = _compare(tmp_path, older, newer, *args, "--show-retitles")
    assert result.exit_code == baseline.exit_code == 0, result.output
    assert result.output == baseline.output


def test_rss_compare_opt_in_empty_retitles_and_no_overwrite(tmp_path):
    capture = _capture(_item("Same", "a"))
    result = _compare(tmp_path, capture, capture, "--format", "json", "--show-retitles")
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["retitled_urls"] == []
    destination = tmp_path / "existing.json"
    destination.write_text("preserve", encoding="utf-8")
    result = _compare(tmp_path, capture, capture, "--show-retitles", "--output-file", str(destination))
    assert result.exit_code != 0
    assert destination.read_text(encoding="utf-8") == "preserve"


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


def test_rss_compare_rejects_off_origin_and_malformed_port_without_partial_report(tmp_path):
    for url in (
        "https://example.invalid/rss/articles/z",
        "https://news.google.com:abc/rss/articles/x",
        "https://news.google.com:99999/rss/articles/x",
    ):
        result = _compare(
            tmp_path,
            _capture(_item("Valid", "a")),
            _capture(_item("Untrusted", "b", url=url)),
            "--format",
            "json",
        )
        assert result.exit_code == 1, result.output
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


def test_rss_compare_csv_is_spreadsheet_ready_and_retitles_are_explicit(tmp_path):
    result = _compare(
        tmp_path,
        _capture(_item("Old", "a"), _item("Before", "b", publisher="Old publisher")),
        _capture(_item("After", "b", publisher="New publisher"), _item("New", "c")),
        "--format", "csv",
    )
    assert result.exit_code == 0, result.output
    rows = list(csv.DictReader(io.StringIO(result.output)))
    assert rows[0]["record_type"] == "summary"
    assert rows[0]["comparison_method"] == "exact_url_membership"
    assert rows[0]["source_authenticated"] == "false"
    assert rows[0]["newly_seen"] == "1"
    assert rows[0]["not_seen_in_newer"] == "1"
    assert rows[0]["retitled_same_url"] == "1"
    assert "feed window" in rows[0]["limitations"].lower()
    assert "demand growth" in rows[0]["limitations"].lower()
    headlines = [row for row in rows if row["record_type"] == "headline"]
    assert len(headlines) == 3
    by_slug = {row["url"].rsplit("/", 1)[-1]: row for row in headlines}
    assert by_slug["a"]["status"] == "not_seen_in_newer"
    assert by_slug["c"]["status"] == "newly_seen"
    assert by_slug["b"]["status"] == "still_seen"
    assert by_slug["b"]["old_title"] == "Before"
    assert by_slug["b"]["new_title"] == "After"
    assert by_slug["b"]["title_changed"] == "true"


def test_rss_compare_csv_prevents_spreadsheet_formulas(tmp_path):
    result = _compare(
        tmp_path, _capture(),
        _capture(_item('=HYPERLINK("https://attacker.invalid","open")', "x",
                       publisher="  @SUM(1,2)")),
        "--format", "csv",
    )
    assert result.exit_code == 2, result.output
    rows = list(csv.DictReader(io.StringIO(result.output)))
    assert rows[1]["new_title"].startswith("'=HYPERLINK")
    assert rows[1]["new_publisher"].startswith("'@SUM")
    assert rows[1]["source_authenticated"] == "false"


def test_rss_compare_csv_empty_has_visible_limitations_and_save_new_only(tmp_path):
    result = _compare(tmp_path, _capture(), _capture(), "--format", "csv")
    assert result.exit_code == 2, result.output
    rows = list(csv.DictReader(io.StringIO(result.output)))
    assert len(rows) == 1
    assert rows[0]["record_type"] == "summary"
    assert "not authenticated" in rows[0]["limitations"].lower()
    destination = tmp_path / "comparison.csv"
    saved = _compare(tmp_path, _capture(_item("A", "a")),
                     _capture(_item("B", "b")), "--format", "csv",
                     "--output-file", str(destination))
    assert saved.exit_code == 0, saved.output
    assert destination.read_bytes().startswith(b"record_type,")
    assert len(list(csv.DictReader(io.StringIO(destination.read_text(encoding="utf-8"))))) == 3
    again = _compare(tmp_path, _capture(_item("A", "a")),
                     _capture(_item("B", "b")), "--format", "csv",
                     "--output-file", str(destination))
    assert again.exit_code != 0


def test_topic_comparison_preserves_retitle_membership_and_source_quality(tmp_path):
    older = _capture(_item("AI old", "a"), _item("Energy", "b", publisher=None),
                     _item("AI before", "c"), _item("Unrelated", "c"),
                     _item("Before", "f"))
    newer = _capture(_item("Sports", "d"), _item("Rebranded", "c"),
                     _item("ai new", "e"), _item("AI after", "f"))
    result = _compare(tmp_path, older, newer, "--contains", " aI ", "--format", "json")
    assert result.exit_code == 2, result.output
    report = json.loads(result.output)
    assert report["filter"] == {
        "contains": "aI", "method": "casefold_literal_substring_url_union",
        "older_matched_urls": 2, "newer_matched_urls": 2, "selected_unique_urls": 4,
    }
    assert report["summary"] == {
        "older_unique_urls": 3, "newer_unique_urls": 3, "newly_seen": 1,
        "still_seen": 2, "not_seen_in_newer": 1, "retitled_same_url": 2,
        "older_duplicate_urls": 1, "newer_duplicate_urls": 0,
        "older_missing_metadata": 1, "newer_missing_metadata": 0,
        "older_empty": False, "newer_empty": False,
    }
    assert report["source_capture_quality"]["older"]["unique_urls"] == 4
    assert report["source_capture_quality"]["older"]["missing_publishers"] == 1
    assert report["source_capture_quality"]["newer"]["unique_urls"] == 4
    assert [row["title"] for row in report["still_seen"]] == ["Rebranded", "AI after"]
    assert report["source_authenticated"] is False


def test_topic_comparison_no_matches_requires_review_without_fake_empty_capture(tmp_path):
    result = _compare(tmp_path, _capture(_item("Energy", "a")),
                      _capture(_item("Sports", "b")), "--contains", "AI", "--format", "json")
    assert result.exit_code == 2, result.output
    report = json.loads(result.output)
    assert report["filter"]["selected_unique_urls"] == 0
    assert report["summary"]["older_unique_urls"] == report["summary"]["newer_unique_urls"] == 0
    assert report["summary"]["older_empty"] is report["summary"]["newer_empty"] is False
    assert "not evidence of absent" in " ".join(report["caveats"])


@pytest.mark.parametrize("value", ["", "   ", "a\nb", "x" * 121, 123])
def test_topic_comparison_rejects_invalid_filter(value):
    raw = json.dumps(_capture(_item("AI", "a"))).encode()
    with pytest.raises(ValueError, match="1-120 printable"):
        compare_saved_rss_headlines(raw, raw, contains=value)


def test_topic_comparison_validates_nonmatching_records(tmp_path):
    result = _compare(tmp_path, _capture(_item("AI", "a")),
                      _capture(_item("Sports", "b", url="https://example.invalid/rss/articles/b")),
                      "--contains", "AI", "--format", "json")
    assert result.exit_code == 1, result.output
    assert "comparison failed" in result.output.lower()
    assert '"newly_seen"' not in result.output


def test_topic_comparison_csv_escapes_filter_and_preserves_scope(tmp_path):
    result = _compare(tmp_path, _capture(_item("=AI before", "a"), _item("Energy", "b")),
                      _capture(_item("Rebranded", "a"), _item("Sports", "c")),
                      "--contains", "=AI", "--format", "csv")
    assert result.exit_code == 0, result.output
    rows = list(csv.DictReader(io.StringIO(result.output)))
    assert len(rows) == 2
    assert rows[0]["filter_contains"] == "'=AI"
    assert rows[0]["filter_method"] == "casefold_literal_substring_url_union"
    assert rows[0]["older_source_unique_urls"] == "2"
    assert rows[0]["newer_source_unique_urls"] == "2"
    assert rows[0]["selected_unique_urls"] == "1"
    assert rows[1]["status"] == "still_seen"
    assert rows[1]["old_title"] == "'=AI before"
    assert rows[1]["title_changed"] == "true"


def test_topic_comparison_markdown_and_exclusive_save(tmp_path):
    destination = tmp_path / "topic.md"
    args = ("--contains", "[AI]", "--output-file", str(destination))
    older = _capture(_item("[AI] before", "a"), _item("Energy", "b"))
    newer = _capture(_item("Rebranded", "a"), _item("Sports", "c"))
    result = _compare(tmp_path, older, newer, *args)
    assert result.exit_code == 0, result.output
    report = destination.read_text(encoding="utf-8")
    assert "\\[AI\\]" in report
    assert "source-wide" in report.lower()
    assert "retitled URL:** 1" in report
    assert "Energy" not in report and "Sports" not in report
    assert _compare(tmp_path, older, newer, *args).exit_code == 1
    assert destination.read_text(encoding="utf-8") == report


@pytest.mark.parametrize("format_name", ["json", "csv", "markdown"])
@pytest.mark.parametrize("topic", [False, True])
def test_sort_url_is_opt_in_and_stable_across_permutations(tmp_path, format_name, topic):
    older = [_item("AI old Z", "z"), _item("AI old A", "A"),
             _item("AI before D", "d"), _item("Before B", "b")]
    newer = [_item("AI new Y", "y"), _item("AI new C", "c"),
             _item("Retitled D", "d"), _item("AI after B", "b")]
    args = ["--format", format_name]
    if topic:
        args += ["--contains", "AI"]
    default = _compare(tmp_path, _capture(*older), _capture(*newer), *args)
    reversed_default = _compare(tmp_path, _capture(*reversed(older)),
                                _capture(*reversed(newer)), *args)
    assert default.exit_code == reversed_default.exit_code == 0
    assert default.output != reversed_default.output
    sorted_report = _compare(tmp_path, _capture(*older), _capture(*newer), *args, "--sort-url")
    reversed_sorted = _compare(tmp_path, _capture(*reversed(older)),
                               _capture(*reversed(newer)), *args, "--sort-url")
    assert sorted_report.exit_code == reversed_sorted.exit_code == 0, sorted_report.output
    assert sorted_report.output == reversed_sorted.output
    assert "first" in sorted_report.output.lower()
    assert "chronolog" in sorted_report.output.lower()
    if format_name == "json":
        report = json.loads(sorted_report.output)
        assert report["row_order"] == "exact_url_ascending_within_status"
        assert report["summary"] == json.loads(default.output)["summary"]
        for group, slugs in (("newly_seen", ["c", "y"]), ("still_seen", ["b", "d"]),
                             ("not_seen_in_newer", ["A", "z"])):
            assert [row["url"].rsplit("/", 1)[-1] for row in report[group]] == slugs
        assert "row_order" not in json.loads(default.output)
    elif format_name == "csv":
        rows = list(csv.DictReader(io.StringIO(sorted_report.output)))
        assert all(row["row_order"] == "exact_url_ascending_within_status" for row in rows)
        assert [row["url"].rsplit("/", 1)[-1] for row in rows[1:]] == ["c", "y", "b", "d", "A", "z"]
        assert "row_order" not in next(csv.DictReader(io.StringIO(default.output)))
    else:
        assert "exact URL" in sorted_report.output
        assert "URL order:" not in default.output


def test_sort_url_keeps_first_duplicate_and_csv_safety(tmp_path):
    older = _capture(_item("=AI first", "b"), _item("AI second", "b"),
                     _item("AI other", "a"))
    newer = _capture(_item("AI retitle", "b"), _item("AI other", "a"))
    result = _compare(tmp_path, older, newer, "--contains", "AI", "--sort-url", "--format", "csv")
    assert result.exit_code == 2, result.output
    rows = list(csv.DictReader(io.StringIO(result.output)))
    assert rows[0]["older_duplicate_urls"] == "1"
    assert rows[0]["retitled_same_url"] == "1"
    assert rows[2]["old_title"] == "'=AI first"
    assert rows[2]["title_changed"] == "true"


def test_sort_url_empty_and_exclusive_output(tmp_path):
    destination = tmp_path / "sorted.json"
    args = ("--sort-url", "--format", "json", "--output-file", str(destination))
    result = _compare(tmp_path, _capture(), _capture(), *args)
    assert result.exit_code == 2, result.output
    report = destination.read_bytes()
    data = json.loads(report)
    assert data["row_order"] == "exact_url_ascending_within_status"
    assert data["summary"]["older_empty"] and data["summary"]["newer_empty"]
    assert _compare(tmp_path, _capture(), _capture(), *args).exit_code == 1
    assert destination.read_bytes() == report
