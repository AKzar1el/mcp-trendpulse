"""Provider-free exact-URL comparison of two saved Google News RSS captures."""

import csv
import io
import json

from mcp_trendpulse.brief_audit import _csv_safe
from mcp_trendpulse.brief_review import _markdown_safe
from mcp_trendpulse.rss_review import review_saved_rss_headlines


def compare_saved_rss_headlines(older_raw, newer_raw, *, output_format="markdown"):
    """Compare declared old/new capture membership, not article or demand changes."""
    if output_format not in ("markdown", "json", "csv"):
        raise ValueError("Unsupported RSS comparison format")
    older_text, older_attention = review_saved_rss_headlines(older_raw, output_format="json")
    newer_text, newer_attention = review_saved_rss_headlines(newer_raw, output_format="json")
    older = json.loads(older_text)
    newer = json.loads(newer_text)
    old_rows = {row["url"]: row for row in older["headlines"]}
    new_rows = {row["url"]: row for row in newer["headlines"]}

    newly_seen = [row for url, row in new_rows.items() if url not in old_rows]
    still_seen = [row for url, row in new_rows.items() if url in old_rows]
    not_seen = [row for url, row in old_rows.items() if url not in new_rows]
    changed_titles = sum(old_rows[row["url"]]["title"] != row["title"] for row in still_seen)
    summary = {
        "older_unique_urls": len(old_rows),
        "newer_unique_urls": len(new_rows),
        "newly_seen": len(newly_seen),
        "still_seen": len(still_seen),
        "not_seen_in_newer": len(not_seen),
        "retitled_same_url": changed_titles,
        "older_duplicate_urls": older["summary"]["duplicate_urls"],
        "newer_duplicate_urls": newer["summary"]["duplicate_urls"],
        "older_missing_metadata": (older["summary"]["missing_publishers"]
                                   + older["summary"]["missing_dates"]),
        "newer_missing_metadata": (newer["summary"]["missing_publishers"]
                                   + newer["summary"]["missing_dates"]),
        "older_empty": not old_rows,
        "newer_empty": not new_rows,
    }
    result = {
        "schema_version": 1,
        "source": "google_news_rss",
        "content_level": "rss_headline_only",
        "source_authenticated": False,
        "comparison_method": "exact_url_membership",
        "summary": summary,
        "newly_seen": newly_seen,
        "still_seen": still_seen,
        "not_seen_in_newer": not_seen,
        "caveats": [
            "Newly seen links are not evidence of demand growth or independent articles.",
            "Links not seen in newer evidence may have left the RSS feed window; this does not mean the article disappeared.",
            "Capture order, source labels and dates are supplied by files, not authenticated.",
            "Exact Google News URLs are compared without canonicalization; retitles do not prove editorial events.",
            "RSS headlines are metadata, not verified full articles, search volumes or trend scores.",
        ],
    }
    needs_attention = older_attention or newer_attention
    if output_format == "json":
        return json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n", needs_attention

    if output_format == "csv":
        buffer = io.StringIO(newline="")
        fields = [
            "record_type", "status", "url", "old_title", "new_title", "old_publisher",
            "new_publisher", "old_publish_date", "new_publish_date", "title_changed",
            *summary.keys(), "comparison_method", "source_authenticated", "limitations",
        ]
        writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        common = {"comparison_method": "exact_url_membership", "source_authenticated": "false"}
        writer.writerow({
            "record_type": "summary", **summary, **common,
            "limitations": " ".join(result["caveats"]),
        })
        for status, rows in (("newly_seen", newly_seen), ("still_seen", still_seen),
                             ("not_seen_in_newer", not_seen)):
            for row in rows:
                old = old_rows.get(row["url"]) or {}
                new = new_rows.get(row["url"]) or {}
                writer.writerow({
                    "record_type": "headline", "status": status,
                    "url": _csv_safe(row["url"]),
                    "old_title": _csv_safe(old.get("title") or ""),
                    "new_title": _csv_safe(new.get("title") or ""),
                    "old_publisher": _csv_safe(old.get("publisher") or ""),
                    "new_publisher": _csv_safe(new.get("publisher") or ""),
                    "old_publish_date": _csv_safe(old.get("publish_date") or ""),
                    "new_publish_date": _csv_safe(new.get("publish_date") or ""),
                    "title_changed": str(bool(old and new and old["title"] != new["title"])).lower(),
                    **common,
                })
        return buffer.getvalue(), needs_attention

    lines = ["# Saved Google News RSS headline comparison (offline)", "",
             "Two user-declared captures compared by exact Google News URL; not a growth score.", "",
             (f"**Older unique:** {len(old_rows)}; **newer unique:** {len(new_rows)}; "
              f"**newly seen:** {len(newly_seen)}; **still seen:** {len(still_seen)}; "
              f"**not seen in newer:** {len(not_seen)}; **retitled URL:** {changed_titles}"), "",
             (f"**Older duplicate URLs:** {summary['older_duplicate_urls']}; "
              f"**newer duplicate URLs:** {summary['newer_duplicate_urls']}; "
              f"**older missing fields:** {summary['older_missing_metadata']}; "
              f"**newer missing fields:** {summary['newer_missing_metadata']}"), ""]
    for heading, rows in (("Newly seen", newly_seen), ("Still seen (newer metadata)", still_seen),
                          ("Not seen in newer feed window", not_seen)):
        lines.extend([f"## {heading}", "", "| Headline | Publisher | Saved date | Google News URL |",
                      "| --- | --- | --- | --- |"])
        for row in rows:
            cells = (row["title"], row["publisher"] or "unknown",
                     row["publish_date"] or "unknown", row["url"])
            lines.append("| " + " | ".join(_markdown_safe(cell) for cell in cells) + " |")
        if not rows:
            lines.append("| none | - | - | - |")
        lines.append("")
    lines.extend(["## Evidence limitations", "", *[f"- {caveat}" for caveat in result["caveats"]]])
    return "\n".join(lines) + "\n", needs_attention
