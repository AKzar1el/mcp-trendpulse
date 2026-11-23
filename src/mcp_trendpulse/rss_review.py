"""Offline provenance and completeness review of saved RSS headline-only JSON."""

import csv
import io
import json
from datetime import datetime

from mcp_trendpulse.brief_audit import _csv_safe
from mcp_trendpulse.brief_review import _invalid_constant, _markdown_safe, _unique_keys
from mcp_trendpulse.rss_url_validation import is_google_news_rss_url

MAX_RSS_EVIDENCE_BYTES = 1024 * 1024
MAX_RSS_HEADLINES = 100


def _text(value, field, *, max_length, optional=False):
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise ValueError(f"Invalid saved RSS headline {field}")
    # Escaped lone UTF-16 surrogates are valid JSON syntax but cannot be emitted as UTF-8.
    if any(ord(character) < 32 or ord(character) == 127
           or 0xD800 <= ord(character) <= 0xDFFF for character in value):
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


def _publisher_breakdown(headlines, *, scope):
    """Count unverified publisher labels on the visible, exact-URL-deduped rows."""
    publishers = {}
    unknown = 0
    for headline in headlines:
        publisher = headline["publisher"]
        if publisher is None:
            unknown += 1
            continue
        label = publisher.strip()
        key = label.casefold()
        if key not in publishers:
            publishers[key] = {"publisher": label, "headlines": 0}
        publishers[key]["headlines"] += 1
    ordered = sorted(publishers.values(), key=lambda item: (-item["headlines"],
                                                           item["publisher"].casefold()))
    total = len(headlines)
    largest = ordered[0]["headlines"] if ordered else 0
    return {
        "scope": scope,
        "total_unique_urls": total,
        "unknown_publisher_count": unknown,
        "distinct_named_publisher_labels": len(ordered),
        "largest_named_label_share_pct": round(100 * largest / total, 1) if total else None,
        "publishers": ordered,
    }


def review_saved_rss_headlines(raw, *, output_format="markdown", contains=None,
                               publisher_breakdown=False):
    """Return a validated offline report and whether manual review is needed."""
    if output_format not in ("markdown", "json", "csv"):
        raise ValueError("Unsupported RSS review format")
    if contains is not None:
        if not isinstance(contains, str) or not contains.strip() or len(contains) > 120 or not contains.isprintable():
            raise ValueError("RSS headline filter must be 1-120 printable characters")
        contains = contains.strip()
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
        if not is_google_news_rss_url(url):
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
    if contains is not None:
        matches = [item for item in unique if contains.casefold() in item["title"].casefold()]
        result["filter"] = {"contains": contains, "method": "casefold_literal_substring",
                            "matched_headlines": len(matches)}
        result["headlines"] = matches
        result["caveats"].append(
            "No matching saved headline is not evidence of absent articles or market demand.")
        needs_attention = needs_attention or not matches
    if publisher_breakdown:
        result["publisher_breakdown"] = _publisher_breakdown(
            result["headlines"],
            scope="matched_headlines" if contains is not None else "all_unique_urls",
        )
        result["caveats"].append(
            "Saved publisher labels are unverified and not independent corroboration or demand evidence.")
    if output_format == "json":
        return json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n", needs_attention
    if output_format == "csv":
        buffer = io.StringIO(newline="")
        fields = [
            "record_type", "scope", "filter_contains", "title", "publisher", "publish_date",
            "url", "publisher_headline_count", "headlines", "unique_urls", "duplicate_urls",
            "missing_publishers", "missing_dates", "matched_headlines",
            "unknown_publisher_count", "distinct_named_publisher_labels",
            "largest_named_label_share_pct", "source_authenticated", "limitations",
        ]
        writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        scope = "matched_headlines" if contains is not None else "all_unique_urls"
        summary = {"record_type": "summary", "scope": scope, "source_authenticated": "false",
                   "filter_contains": _csv_safe(contains) if contains is not None else "",
                   "matched_headlines": len(result["headlines"]) if contains is not None else "",
                   "limitations": " ".join(result["caveats"]), **result["summary"]}
        if publisher_breakdown:
            summary.update({key: result["publisher_breakdown"][key] for key in (
                "unknown_publisher_count", "distinct_named_publisher_labels",
                "largest_named_label_share_pct")})
        writer.writerow(summary)
        for item in result["headlines"]:
            writer.writerow({"record_type": "headline", "scope": scope,
                             "title": _csv_safe(item["title"]),
                             "publisher": _csv_safe(item["publisher"] or ""),
                             "publish_date": _csv_safe(item["publish_date"] or ""),
                             "url": _csv_safe(item["url"]), "source_authenticated": "false"})
        if publisher_breakdown:
            for item in result["publisher_breakdown"]["publishers"]:
                writer.writerow({"record_type": "publisher", "scope": scope,
                                 "publisher": _csv_safe(item["publisher"]),
                                 "publisher_headline_count": item["headlines"],
                                 "source_authenticated": "false"})
        return buffer.getvalue(), needs_attention
    lines = ["# Saved Google News RSS headline review (offline)", "",
             f"**Headlines:** {len(headlines)}; **unique URLs:** {len(unique)}; "
             f"**exact URL duplicates:** {duplicate_urls}",
             f"**Missing publisher:** {missing_publishers}; **missing date:** {missing_dates}",
             "", "| Headline | Publisher | Saved date | Google News URL |",
             "| --- | --- | --- | --- |"]
    if contains is not None:
        lines.insert(1, f"**Literal headline filter:** {_markdown_safe(contains)} "
                        f"({result['filter']['matched_headlines']} matches; case-insensitive)")
    for item in result["headlines"]:
        cells = [item["title"], item["publisher"] or "unknown",
                 item["publish_date"] or "unknown", item["url"]]
        lines.append("| " + " | ".join(_markdown_safe(value) for value in cells) + " |")
    if publisher_breakdown:
        breakdown = result["publisher_breakdown"]
        lines.extend([
            "", "## Saved publisher label concentration",
            f"**Scope:** {breakdown['scope']}; **unique URLs in scope:** {breakdown['total_unique_urls']}; "
            f"**unknown publisher labels:** {breakdown['unknown_publisher_count']}",
            f"**Largest named label share of all unique URLs in scope:** "
            f"{breakdown['largest_named_label_share_pct']}%"
            if breakdown["largest_named_label_share_pct"] is not None
            else "**Largest named label share:** unavailable (no headlines)",
            "", "| Unverified publisher label | Headlines |", "| --- | ---: |",
        ])
        for entry in breakdown["publishers"]:
            lines.append(f"| {_markdown_safe(entry['publisher'])} | {entry['headlines']} |")
    lines.extend(["", "## Evidence limitations",
                  *[f"- {caveat}" for caveat in result["caveats"]]])
    return "\n".join(lines) + "\n", needs_attention
