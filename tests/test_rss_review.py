"""Provider-free acceptance tests for reviewing saved headline-only RSS JSON."""

import csv
import io
import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from mcp_trendpulse.cli import cli


def _capture(headlines):
    return {
        "schema_version": 1,
        "source": "google_news_rss",
        "content_level": "rss_headline_only",
        "count": len(headlines),
        "headlines": headlines,
    }


def _headline(**overrides):
    value = {
        "title": "Topic A",
        "url": "https://news.google.com/rss/articles/example",
        "publisher": "Example News",
        "publish_date": "2026-11-19T10:00:00+00:00",
    }
    value.update(overrides)
    return value


def _run(tmp_path, capture, *flags):
    source = tmp_path / "headlines.json"
    source.write_text(json.dumps(capture), encoding="utf-8")
    with patch("mcp_trendpulse.cli.get_provider_set", side_effect=AssertionError("No provider I/O")):
        return CliRunner().invoke(cli, ["rss-review", "--evidence", str(source), *flags])


def test_rss_review_json_flags_duplicates_and_unknown_metadata_offline(tmp_path):
    headlines = [_headline(), _headline(title="Second capture"),
                 _headline(url="https://news.google.com/rss/articles/other", publisher=None, publish_date=None)]
    result = _run(tmp_path, _capture(headlines), "--format", "json")
    assert result.exit_code == 2, result.output
    report = json.loads(result.output)
    assert report["source_authenticated"] is False
    assert report["summary"] == {"headlines": 3, "unique_urls": 2, "duplicate_urls": 1,
                                  "missing_publishers": 1, "missing_dates": 1}
    assert len(report["headlines"]) == 2
    assert report["content_level"] == "rss_headline_only"


@pytest.mark.parametrize("change", [
    {"count": 2},
    {"source": "article_full"},
    {"content_level": "article_full"},
    {"schema_version": True},
    {"headlines": [_headline(url="javascript:alert(1)")]},
    {"headlines": [_headline(url="https://example.invalid/rss/articles/z")]},
    {"headlines": [_headline(url="http://news.google.com/rss/articles/x")]},
    {"headlines": [_headline(url="https://news.google.com:abc/rss/articles/x")]},
    {"headlines": [_headline(url="https://news.google.com:99999/rss/articles/x")]},
    {"headlines": [_headline(url="https://news.google.com:8080/rss/articles/x")]},
    {"headlines": [_headline(url="https://news.google.com/rss/articles/")]},
    {"headlines": [_headline(url="https://news.google.com/rss/articles/?hl=en")]},
    {"headlines": [_headline(url="https://news.google.com.evil.invalid/rss/articles/x")]},
    {"headlines": [_headline(url="https://news.google.com/news/x")]},
    {"headlines": [_headline(url="https://user:pass@news.google.com/rss/articles/x")]},
    {"headlines": [_headline(url="https://news.google.com/rss/articles/x#fragment")]},
    {"headlines": [_headline(url=" https://news.google.com/rss/articles/x")]},
    {"headlines": [_headline(title="")]},
])
def test_rss_review_rejects_malformed_source_without_report(tmp_path, change):
    result = _run(tmp_path, {**_capture([_headline()]), **change}, "--format", "json")
    assert result.exit_code == 1
    assert "review failed" in result.output.lower()
    assert '"summary"' not in result.output


def test_rss_review_accepts_canonical_google_news_443_and_keeps_source_unauthenticated(tmp_path):
    result = _run(
        tmp_path,
        _capture([_headline(url="https://news.google.com:443/rss/articles/explicit")]),
        "--format",
        "json",
    )
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["source_authenticated"] is False
    assert report["headlines"][0]["url"] == "https://news.google.com:443/rss/articles/explicit"


def test_rss_review_escapes_markdown_and_never_overwrites(tmp_path):
    result = _run(tmp_path, _capture([_headline(title="A | B [bad](https://evil.test)",
                                                     publisher="*Untrusted*")]))
    assert result.exit_code == 0, result.output
    assert "A \\| B" in result.output
    assert "\\[bad\\]" in result.output
    assert "\\*Untrusted\\*" in result.output
    destination = tmp_path / "report.md"
    destination.write_text("DO NOT TOUCH", encoding="utf-8")
    no_write = _run(tmp_path, _capture([_headline()]), "--output-file", str(destination))
    assert no_write.exit_code != 0
    assert destination.read_text(encoding="utf-8") == "DO NOT TOUCH"


def test_rss_review_empty_is_review_required_and_saved_output_is_inert(tmp_path):
    destination = tmp_path / "report.json"
    result = _run(tmp_path, _capture([]), "--format", "json", "--output-file", str(destination))
    assert result.exit_code == 2, result.output
    report = json.loads(destination.read_text(encoding="utf-8"))
    assert report["summary"]["unique_urls"] == 0
    assert report["source_authenticated"] is False


def test_rss_review_contains_filters_titles_offline_without_changing_source_counts(tmp_path):
    entries = [_headline(title="AI agents release", url="https://news.google.com/rss/articles/a"),
               _headline(title="Energy transition", url="https://news.google.com/rss/articles/b"),
               _headline(title="Agentic systems", url="https://news.google.com/rss/articles/c")]
    result = _run(tmp_path, _capture(entries), "--format", "json", "--contains", "AGENT")
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["filter"] == {"contains": "AGENT", "method": "casefold_literal_substring",
                                "matched_headlines": 2}
    assert report["summary"]["headlines"] == 3
    assert report["summary"]["unique_urls"] == 3
    assert [entry["title"] for entry in report["headlines"]] == ["AI agents release", "Agentic systems"]
    assert report["source_authenticated"] is False


def test_rss_review_contains_no_match_requires_review_not_a_market_claim(tmp_path):
    result = _run(tmp_path, _capture([_headline()]), "--contains", "unseen", "--format", "json")
    assert result.exit_code == 2, result.output
    report = json.loads(result.output)
    assert report["filter"]["matched_headlines"] == 0
    assert report["summary"]["headlines"] == 1
    assert "not evidence of" in " ".join(report["caveats"]).lower()


@pytest.mark.parametrize("query", ["", "   ", "bad\nvalue", "x" * 121])
def test_rss_review_rejects_invalid_contains_before_output(tmp_path, query):
    result = _run(tmp_path, _capture([_headline()]), "--contains", query, "--format", "json")
    assert result.exit_code == 1
    assert "review failed" in result.output.lower()
    assert '"summary"' not in result.output


def test_rss_review_contains_markdown_escapes_untrusted_filter(tmp_path):
    result = _run(tmp_path, _capture([_headline(title="A [topic](bad) | item")]),
                  "--contains", "[topic](bad) |")
    assert result.exit_code == 0, result.output
    assert "\\[topic\\]" in result.output
    assert "\\|" in result.output


def test_rss_review_without_contains_keeps_existing_shape(tmp_path):
    result = _run(tmp_path, _capture([_headline()]), "--format", "json")
    assert result.exit_code == 0, result.output
    assert "filter" not in json.loads(result.output)
    assert "publisher_breakdown" not in json.loads(result.output)


def test_rss_review_publisher_breakdown_deduplicates_and_groups_labels_offline(tmp_path):
    entries = [
        _headline(url="https://news.google.com/rss/articles/a", publisher="Example News"),
        _headline(url="https://news.google.com/rss/articles/a", publisher="OTHER LABEL"),
        _headline(url="https://news.google.com/rss/articles/b", publisher=" example news "),
        _headline(url="https://news.google.com/rss/articles/c", publisher="Other News"),
        _headline(url="https://news.google.com/rss/articles/d", publisher=None),
    ]
    result = _run(tmp_path, _capture(entries), "--format", "json", "--publisher-breakdown")
    assert result.exit_code == 2, result.output
    report = json.loads(result.output)
    assert report["summary"]["headlines"] == 5
    assert report["summary"]["duplicate_urls"] == 1
    assert report["publisher_breakdown"] == {
        "scope": "all_unique_urls",
        "total_unique_urls": 4,
        "unknown_publisher_count": 1,
        "distinct_named_publisher_labels": 2,
        "largest_named_label_share_pct": 50.0,
        "publishers": [
            {"publisher": "Example News", "headlines": 2},
            {"publisher": "Other News", "headlines": 1},
        ],
    }
    assert any("not independent" in caveat.lower() for caveat in report["caveats"])


def test_rss_review_publisher_breakdown_respects_title_filter_scope(tmp_path):
    entries = [
        _headline(title="Agent launch", url="https://news.google.com/rss/articles/a", publisher="Wire"),
        _headline(title="Energy update", url="https://news.google.com/rss/articles/b", publisher="Wire"),
        _headline(title="Agent systems", url="https://news.google.com/rss/articles/c", publisher="Other"),
    ]
    result = _run(tmp_path, _capture(entries), "--format", "json", "--contains", "agent",
                  "--publisher-breakdown")
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["summary"]["unique_urls"] == 3
    assert report["publisher_breakdown"]["scope"] == "matched_headlines"
    assert report["publisher_breakdown"]["total_unique_urls"] == 2
    assert report["publisher_breakdown"]["largest_named_label_share_pct"] == 50.0
    assert [entry["publisher"] for entry in report["publisher_breakdown"]["publishers"]] == ["Other", "Wire"]


def test_rss_review_publisher_breakdown_empty_capture_is_not_divided_by_zero(tmp_path):
    result = _run(tmp_path, _capture([]), "--format", "json", "--publisher-breakdown")
    assert result.exit_code == 2, result.output
    breakdown = json.loads(result.output)["publisher_breakdown"]
    assert breakdown["total_unique_urls"] == 0
    assert breakdown["largest_named_label_share_pct"] is None
    assert breakdown["publishers"] == []


def test_rss_review_publisher_breakdown_markdown_escapes_untrusted_labels(tmp_path):
    result = _run(tmp_path, _capture([_headline(publisher="A | [x](https://invalid.test)")]),
                  "--publisher-breakdown")
    assert result.exit_code == 0, result.output
    assert "## Saved publisher label concentration" in result.output
    assert "A \\| \\[x\\]" in result.output
    assert "unverified" in result.output.lower()


def test_rss_review_csv_exports_summary_and_safe_unique_headlines_offline(tmp_path):
    entries = [
        _headline(title="=1+1", publisher="@News", url="https://news.google.com/rss/articles/a"),
        _headline(title="Duplicate", publisher="Different", url="https://news.google.com/rss/articles/a"),
        _headline(title="Valid", publisher=None, publish_date=None,
                  url="https://news.google.com/rss/articles/b"),
    ]
    result = _run(tmp_path, _capture(entries), "--format", "csv")
    assert result.exit_code == 2, result.output
    rows = list(csv.DictReader(io.StringIO(result.output)))
    assert [row["record_type"] for row in rows] == ["summary", "headline", "headline"]
    assert rows[0]["headlines"] == "3"
    assert rows[0]["unique_urls"] == "2"
    assert rows[0]["duplicate_urls"] == "1"
    assert rows[0]["source_authenticated"] == "false"
    assert "not verified full articles" in rows[0]["limitations"]
    assert rows[1]["title"].startswith("'=1+1")
    assert rows[1]["publisher"] == "'@News"
    assert rows[2]["publisher"] == ""


def test_rss_review_csv_filter_and_optional_publisher_rows_have_scoped_counts(tmp_path):
    entries = [
        _headline(title="Agent tool", publisher="+Wire",
                  url="https://news.google.com/rss/articles/a"),
        _headline(title="Energy tool", publisher="+Wire",
                  url="https://news.google.com/rss/articles/b"),
        _headline(title="Agent kit", publisher=None,
                  url="https://news.google.com/rss/articles/c"),
    ]
    result = _run(tmp_path, _capture(entries), "--format", "csv", "--contains", "agent",
                  "--publisher-breakdown")
    assert result.exit_code == 2, result.output
    rows = list(csv.DictReader(io.StringIO(result.output)))
    assert [row["record_type"] for row in rows] == ["summary", "headline", "headline", "publisher"]
    assert rows[0]["headlines"] == "3"
    assert rows[0]["matched_headlines"] == "2"
    assert rows[0]["scope"] == "matched_headlines"
    assert rows[0]["unknown_publisher_count"] == "1"
    assert rows[0]["largest_named_label_share_pct"] == "50.0"
    assert rows[0]["filter_contains"] == "agent"
    assert rows[3]["publisher"] == "'+Wire"
    assert rows[3]["publisher_headline_count"] == "1"


def test_rss_review_csv_empty_evidence_and_no_overwrite(tmp_path):
    destination = tmp_path / "review.csv"
    result = _run(tmp_path, _capture([]), "--format", "csv", "--output-file", str(destination))
    assert result.exit_code == 2, result.output
    rows = list(csv.DictReader(io.StringIO(destination.read_text(encoding="utf-8"))))
    assert len(rows) == 1
    assert rows[0]["record_type"] == "summary"
    assert rows[0]["headlines"] == "0"
    original = destination.read_text(encoding="utf-8")
    blocked = _run(tmp_path, _capture([_headline()]), "--format", "csv", "--output-file",
                   str(destination))
    assert blocked.exit_code != 0
    assert destination.read_text(encoding="utf-8") == original
