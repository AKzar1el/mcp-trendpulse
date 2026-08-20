import json
import logging
from datetime import datetime
from types import SimpleNamespace

import pytest

from mcp_trendpulse.news import save_article_to_json


def _article(tags=None):
    return SimpleNamespace(
        title="Article title",
        authors=["Author"],
        publish_date=datetime(2026, 8, 20, 12, 0, 0),
        top_image="https://example.com/image.jpg",
        images=["https://example.com/image.jpg"],
        text="Article text",
        original_url="https://example.com/article",
        summary="Article summary",
        keywords=["article"],
        keyword_scores={"article": 1.0},
        tags={"b", "a"} if tags is None else tags,
        meta_keywords=["article"],
        meta_description="Article description",
        canonical_link="https://example.com/article",
        meta_data={"og": {"type": "article"}},
        meta_lang="en",
        source_url="https://example.com",
    )


@pytest.mark.parametrize("tags", [{"b", "a"}, frozenset({"b", "a"})])
def test_save_article_to_json_serializes_sorted_tags(tmp_path, tags):
    filename = tmp_path / "article.json"

    save_article_to_json(_article(tags), str(filename))

    article_data = json.loads(filename.read_text())
    assert article_data["tags"] == ["a", "b"]
    assert article_data["images"] == ["https://example.com/image.jpg"]
    assert article_data["meta_data"] == {"og": {"type": "article"}}
    assert article_data["publish_date"] == "2026-08-20 12:00:00"


def test_save_article_to_json_keeps_generated_filename(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    save_article_to_json(_article())

    assert (tmp_path / "Article_title.json").exists()


def test_save_article_to_json_handles_invalid_path(caplog, tmp_path):
    filename = tmp_path / "missing" / "article.json"
    caplog.set_level(logging.ERROR, logger="mcp_trendpulse.news")

    save_article_to_json(_article(), str(filename))

    assert not filename.exists()
    assert f"Failed to save article to {filename}" in caplog.text


def test_save_article_to_json_does_not_stringify_unsupported_values(tmp_path):
    article = _article()
    article.meta_data = {"unsupported": object()}

    with pytest.raises(TypeError, match="not JSON serializable"):
        save_article_to_json(article, str(tmp_path / "article.json"))
