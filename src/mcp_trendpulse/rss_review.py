"""Offline provenance and completeness review of saved RSS headline-only JSON."""

import json
from datetime import datetime
from urllib.parse import urlsplit

from mcp_trendpulse.brief_review import _invalid_constant, _markdown_safe, _unique_keys

MAX_RSS_EVIDENCE_BYTES = 1024 * 1024
MAX_RSS_HEADLINES = 100


def _text(value, field, *, max_length, optional=False):
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise ValueError(f"Invalid saved RSS headline {field}")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(f"Invalid saved RSS headline {field}")
    return value


def _date(value):
    if value is None or value == "":
        return None
    value = _text(value, "publish_date", max_length=64)
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid saved RSS headline publish_date") from exc
    return value


def review_saved_rss_headlines(raw, *, output_format="markdown"):
    """Return a validated offline report and whether manual review is needed."""
    if output_format not in ("markdown", "json"):
        raise ValueError("Unsupported RSS review format")
    if len(raw) > MAX_RSS_EVIDENCE_BYTES:
        raise ValueError("Saved RSS evidence exceeds 1 MiB")
    try:
        payload = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_keys,
                             parse_constant=_invalid_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Saved RSS evidence is not UTF-8 JSON") from exc
    if not isinstance(payload, dict) or type(payload.get("schema_version")) is not int or payload["schema_version"] != 1:
        raise ValueError("Unsupported saved RSS headline schema")
    if payload.get("source") != "google_news_rss" or payload.get("content_level") != "rss_headline_only":
        raise ValueError("Saved RSS evidence is not headline-only Google News metadata")
    headlines = payload.get("headlines")
    if not isinstance(headlines, list) or len(headlines) > MAX_RSS_HEADLINES:
        raise ValueError("Invalid saved RSS headline list")
    if type(payload.get("count")) is not int or payload["count"] != len(headlines):
        raise ValueError("Saved RSS headline count does not match records")

    seen_urls = set()
    unique = []
    missing_publishers = missing_dates = duplicate_urls = 0
    for position, item in enumerate(headlines, 1):
        if not isinstance(item, dict):
            raise ValueError(f"Invalid saved RSS headline #{position}")
        title = _text(item.get("title"), "title", max_length=500)
        url = _text(item.get("url"), "url", max_length=2048)
        try:
            parsed = urlsplit(url)
            valid_url = (parsed.scheme.lower() in ("http", "https") and bool(parsed.hostname)
                         and parsed.username is None and parsed.password is None)
        except ValueError:
            valid_url = False
        if not valid_url:
            raise ValueError(f"Invalid saved RSS headline URL #{position}")
        publisher = item.get("publisher")
        if publisher == "":
            publisher = None
        else:
            publisher = _text(publisher, "publisher", max_length=200, optional=True)
        publish_date = _date(item.get("publish_date"))
        missing_publishers += publisher is None
        missing_dates += publish_date is None
        if url in seen_urls:
            duplicate_urls += 1
            continue
        seen_urls.add(url)
        unique.append({"title": title, "url": url, "publisher": publisher,
                       "publish_date": publish_date})

    result = {
        "schema_version": 1,
        "source": "google_news_rss",
        "content_level": "rss_headline_only",
        "source_authenticated": False,
        "summary": {"headlines": len(headlines), "unique_urls": len(unique),
                    "duplicate_urls": duplicate_urls, "missing_publishers": missing_publishers,
                    "missing_dates": missing_dates},
        "headlines": unique,
        "caveats": [
            "The source label and dates are supplied by the saved file, not authenticated.",
            "Exact duplicate Google News URLs are not independent evidence of demand.",
            "RSS headlines are metadata, not verified full articles or market trend scores.",
        ],
    }
    needs_attention = not unique or duplicate_urls > 0 or missing_publishers > 0 or missing_dates > 0
    if output_format == "json":
        return json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n", needs_attention
    lines = ["# Saved Google News RSS headline review (offline)", "",
             f"**Headlines:** {len(headlines)}; **unique URLs:** {len(unique)}; "
             f"**exact URL duplicates:** {duplicate_urls}",
             f"**Missing publisher:** {missing_publishers}; **missing date:** {missing_dates}",
             "", "| Headline | Publisher | Saved date | Google News URL |",
             "| --- | --- | --- | --- |"]
    for item in unique:
        cells = [item["title"], item["publisher"] or "unknown",
                 item["publish_date"] or "unknown", item["url"]]
        lines.append("| " + " | ".join(_markdown_safe(value) for value in cells) + " |")
    lines.extend(["", "## Evidence limitations",
                  *[f"- {caveat}" for caveat in result["caveats"]]])
    return "\n".join(lines) + "\n", needs_attention
