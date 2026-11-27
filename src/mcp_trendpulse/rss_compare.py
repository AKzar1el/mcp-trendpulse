"""Provider-free exact-URL comparison of two saved Google News RSS captures."""

import csv
import io
import json

from mcp_trendpulse.brief_audit import _csv_safe
from mcp_trendpulse.brief_review import _markdown_safe
from mcp_trendpulse.rss_review import _publisher_breakdown, _validate_headline_filter, review_saved_rss_headlines


def compare_saved_rss_headlines(
    older_raw, newer_raw, *, output_format="markdown", contains=None, sort_url=False, show_retitles=False,
    publisher_breakdown=False,
):
    """Compare declared old/new capture membership, not article or demand changes."""
    if output_format not in ("markdown", "json", "csv"):
        raise ValueError("Unsupported RSS comparison format")
    contains = _validate_headline_filter(contains)
    older_text, older_attention = review_saved_rss_headlines(older_raw, output_format="json")
    newer_text, newer_attention = review_saved_rss_headlines(newer_raw, output_format="json")
    older = json.loads(older_text)
    newer = json.loads(newer_text)
    old_rows = {row["url"]: row for row in older["headlines"]}
    new_rows = {row["url"]: row for row in newer["headlines"]}
    source_quality = {"older": older["summary"], "newer": newer["summary"]}
    filter_info = None
    if contains is not None:
        needle = contains.casefold()
        old_matches = {url for url, row in old_rows.items() if needle in row["title"].casefold()}
        new_matches = {url for url, row in new_rows.items() if needle in row["title"].casefold()}
        selected = old_matches | new_matches
        filter_info = {
            "contains": contains, "method": "casefold_literal_substring_url_union",
            "older_matched_urls": len(old_matches), "newer_matched_urls": len(new_matches),
            "selected_unique_urls": len(selected),
        }
        # Select membership by either capture's title, then retain both sides of a matching URL.
        old_rows = {url: row for url, row in old_rows.items() if url in selected}
        new_rows = {url: row for url, row in new_rows.items() if url in selected}

    newly_seen = [row for url, row in new_rows.items() if url not in old_rows]
    still_seen = [row for url, row in new_rows.items() if url in old_rows]
    not_seen = [row for url, row in old_rows.items() if url not in new_rows]
    if sort_url:
        # Order only after first-record deduplication, membership and topic selection.
        for rows in (newly_seen, still_seen, not_seen):
            rows.sort(key=lambda row: row["url"])
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
        "older_empty": not older["headlines"],
        "newer_empty": not newer["headlines"],
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
    if sort_url:
        result["row_order"] = "exact_url_ascending_within_status"
        result["caveats"].append(
            "URL order: exact URL ascending within each status, not chronology or RSS rank. "
            "Conflicting duplicate URLs still use the first validated record."
        )
    if filter_info is not None:
        result["filter"] = filter_info
        result["source_capture_quality"] = source_quality
        result["caveats"].extend([
            "Membership counts are for the union of URLs with a literal title match in either capture; "
            "duplicate and missing metadata counts and empty flags describe the original captures.",
            "No matching saved headline is not evidence of absent articles or market demand.",
        ])
        needs_attention = needs_attention or not filter_info["selected_unique_urls"]
    if show_retitles and output_format != "csv":
        result["retitled_urls"] = [
            {"url": row["url"], "older_title": old_rows[row["url"]]["title"], "newer_title": row["title"]}
            for row in still_seen if old_rows[row["url"]]["title"] != row["title"]
        ]
    if publisher_breakdown:
        scope = "selected_url_union" if filter_info is not None else "all_unique_urls"
        result["publisher_breakdown"] = {
            capture: _publisher_breakdown(list(rows.values()), scope=scope)
            for capture, rows in (("older", old_rows), ("newer", new_rows))
        }
        result["caveats"].append(
            "Saved publisher labels are unverified and not independent corroboration or demand evidence. "
            "Each capture counts its own deduplicated URLs in scope, including both sides of selected retained URLs."
        )
    if output_format == "json":
        return json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n", needs_attention

    if output_format == "csv":
        buffer = io.StringIO(newline="")
        fields = [
            "record_type", "status", "url", "old_title", "new_title", "old_publisher",
            "new_publisher", "old_publish_date", "new_publish_date", "title_changed",
            *summary.keys(), "comparison_method", "source_authenticated", "limitations",
        ]
        filter_fields = {}
        source_fields = {}
        if filter_info is not None:
            filter_fields = {
                "filter_contains": _csv_safe(contains), "filter_method": filter_info["method"],
                **{key: filter_info[key] for key in (
                    "older_matched_urls", "newer_matched_urls", "selected_unique_urls")},
            }
            source_fields = {f"{capture}_source_{key}": value
                             for capture, quality in source_quality.items() for key, value in quality.items()}
            fields.extend([*filter_fields, *source_fields])
        if sort_url:
            fields.append("row_order")
        if publisher_breakdown:
            fields.extend([
                "publisher_capture", "publisher_scope", "publisher_label", "publisher_headline_count",
                "publisher_unique_urls", "publisher_unknown_count", "publisher_distinct_named_labels",
                "publisher_largest_named_label_share_pct",
            ])
        writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        common = {"comparison_method": "exact_url_membership", "source_authenticated": "false"}
        if sort_url:
            common["row_order"] = result["row_order"]
        writer.writerow({
            "record_type": "summary", **summary, **common,
            **filter_fields, **source_fields,
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
        if publisher_breakdown:
            for capture, breakdown in result["publisher_breakdown"].items():
                publisher_context = {
                    **common, "publisher_capture": capture, "publisher_scope": breakdown["scope"],
                }
                writer.writerow({
                    **publisher_context, "record_type": "publisher_summary",
                    "publisher_unique_urls": breakdown["total_unique_urls"],
                    "publisher_unknown_count": breakdown["unknown_publisher_count"],
                    "publisher_distinct_named_labels": breakdown["distinct_named_publisher_labels"],
                    "publisher_largest_named_label_share_pct": breakdown["largest_named_label_share_pct"],
                })
                for entry in breakdown["publishers"]:
                    writer.writerow({
                        **publisher_context, "record_type": "publisher",
                        "publisher_label": _csv_safe(entry["publisher"]),
                        "publisher_headline_count": entry["headlines"],
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
    if filter_info is not None:
        lines[4:4] = [
            f"**Literal headline filter:** {_markdown_safe(contains)} (case-insensitive; either capture)",
            (f"**Older title matches:** {filter_info['older_matched_urls']}; "
             f"**newer title matches:** {filter_info['newer_matched_urls']}; "
             f"**selected unique URLs:** {filter_info['selected_unique_urls']}"),
            (f"**Source-wide unique URLs:** older {source_quality['older']['unique_urls']}; "
             f"newer {source_quality['newer']['unique_urls']}. "
             "Membership totals below are selected-scope; quality warnings remain source-wide."), "",
        ]
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
    if show_retitles:
        lines.extend(["## Retitled URLs", "", "| Older saved headline | Newer saved headline | Google News URL |",
                      "| --- | --- | --- |"])
        for row in result["retitled_urls"]:
            cells = (row["older_title"], row["newer_title"], row["url"])
            lines.append("| " + " | ".join(_markdown_safe(cell) for cell in cells) + " |")
        if not result["retitled_urls"]:
            lines.append("| none | - | - |")
        lines.append("")
    if publisher_breakdown:
        for capture, breakdown in result["publisher_breakdown"].items():
            share = breakdown["largest_named_label_share_pct"]
            share_text = f"{share}%" if share is not None else "unavailable (no headlines)"
            lines.extend([
                f"## {capture.capitalize()} saved publisher labels", "",
                f"**Scope:** {breakdown['scope']}; **unique URLs:** {breakdown['total_unique_urls']}; "
                f"**unknown labels:** {breakdown['unknown_publisher_count']}",
                f"**Largest named label share of all URLs in scope:** {share_text}", "",
                "| Unverified publisher label | Headlines |", "| --- | ---: |",
            ])
            for entry in breakdown["publishers"]:
                lines.append(f"| {_markdown_safe(entry['publisher'])} | {entry['headlines']} |")
            if not breakdown["publishers"]:
                lines.append("| none | - |")
            lines.append("")
    lines.extend(["## Evidence limitations", "", *[f"- {caveat}" for caveat in result["caveats"]]])
    return "\n".join(lines) + "\n", needs_attention
