"""Offline, bounded review of several independently saved Demand Brief files.

This is an evidence-quality inventory, not a comparison of cross-capture Trends indices.
"""

import csv
import io
import json
from pathlib import Path

from mcp_trendpulse.brief_review import (
    MAX_EVIDENCE_BYTES,
    _markdown_safe,
    review_saved_brief,
)

MAX_AUDIT_FILES = 12
_CAVEATS = [
    "Saved source metadata and observation dates are declared by files, not authenticated.",
    "Normalized Google Trends interest is not search volume or comparable across captures.",
    "Primary coverage counts only responding markets; failed-only market coverage is unknown.",
    "Structurally complete evidence still requires human relevance and provenance review.",
]


def _csv_safe(value):
    text = str(value).replace("\r", " ").replace("\n", " ")
    if text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text.lstrip()
    return text


def audit_saved_briefs(paths, *, output_format="markdown", as_of=None, max_age_days=None):
    """Return (rendered batch review, needs_attention) without provider I/O."""
    if output_format not in ("json", "csv", "markdown"):
        raise ValueError("Unsupported batch audit format")
    if not 1 <= len(paths) <= MAX_AUDIT_FILES:
        raise ValueError(f"Provide between 1 and {MAX_AUDIT_FILES} evidence files")
    # All inputs must be explicit; never recursively discover files or cross file boundaries.
    seen = set()
    files = []
    needs_attention = False
    for number, path in enumerate(paths, 1):
        path = Path(path)
        try:
            if path.is_symlink():
                raise ValueError("Symbolic-link evidence is not supported")
            identity = str(path.resolve(strict=True)).casefold()
            if identity in seen:
                raise ValueError("Duplicate evidence file")
            seen.add(identity)
            with path.open("rb") as handle:
                raw = handle.read(MAX_EVIDENCE_BYTES + 1)
            review_text, review_required = review_saved_brief(
                raw, output_format="json", as_of=as_of, max_age_days=max_age_days,
            )
        except (OSError, ValueError) as exc:
            raise ValueError(f"Invalid evidence #{number}: {exc}") from exc
        review = json.loads(review_text)
        responded = review["markets"]
        responding_names = {market["market"] for market in responded}
        failed_only = {
            failure["market"] for failure in review["failed_markets"]
            if failure["market"] not in responding_names
        }
        observed = sum(market["observed_keywords"] for market in responded)
        expected = sum(market["total_keywords"] for market in responded)
        item = {
            "file_name": path.name,
            "timeframe": review["timeframe"],
            "assessment": review["assessment"],
            "primary_responded_coverage": f"{observed}/{expected}" if responded else "unknown",
            "market_coverage": "partial_unknown" if failed_only else "responded",
            "failed_market_count": len(failed_only),
            "growth_unavailable_count": sum(bool(market["growth_unavailable"]) for market in responded),
            "warning_count": sum(market["warning_count"] for market in responded),
        }
        if as_of is not None or max_age_days is not None:
            item["freshness_exceptions"] = sum(
                market["stale_keywords"] + market["future_keywords"] for market in responded
            )
        files.append(item)
        needs_attention = needs_attention or review_required

    result = {
        "schema_version": 1,
        "source_authenticated": False,
        "summary": {
            "files": len(files),
            "structurally_complete": sum(item["assessment"] == "structurally_complete" for item in files),
            "needs_human_review": sum(item["assessment"] == "needs_human_review" for item in files),
        },
        "files": files,
        "caveats": _CAVEATS,
    }
    if as_of is not None or max_age_days is not None:
        result["freshness_policy"] = {"as_of": as_of, "max_age_days": max_age_days}
    if output_format == "json":
        return json.dumps(result, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n", needs_attention
    if output_format == "csv":
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, lineterminator="\n")
        fields = [
            "file_name", "timeframe", "assessment", "primary_responded_coverage",
            "market_coverage", "failed_market_count", "growth_unavailable_count",
            "warning_count",
        ]
        if "freshness_policy" in result:
            fields.append("freshness_exceptions")
        fields.extend(["source_authenticated", "caveats"])
        writer.writerow(fields)
        for item in files:
            values = [_csv_safe(item[field]) for field in fields[:-2]]
            values.extend(["false", " ".join(_CAVEATS)])
            writer.writerow(values)
        return buffer.getvalue(), needs_attention
    lines = [
        "# Demand Brief batch evidence audit (offline)",
        "",
        f"**Files:** {len(files)}; **needs review:** {result['summary']['needs_human_review']}",
        "**Source:** Google Trends / Google Search (file-declared; not authenticated)",
        "",
        "| Evidence file | Timeframe | Assessment | Responded primary coverage | Failed-only markets | Warnings |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for item in files:
        lines.append(
            f"| {_markdown_safe(item['file_name'])} | {_markdown_safe(item['timeframe'])} | "
            f"{item['assessment'].replace('_', ' ')} | {item['primary_responded_coverage']} | "
            f"{item['failed_market_count']} | {item['warning_count']} |"
        )
    if "freshness_policy" in result:
        lines.extend([
            "",
            f"**Freshness policy:** as of {as_of}, max {max_age_days} day(s)",
        ])
        for item in files:
            if item["freshness_exceptions"]:
                lines.append(
                    f"- {_markdown_safe(item['file_name'])}: {item['freshness_exceptions']} "
                    "stale/future primary observations require review"
                )
    lines.extend(["", "## Evidence limitations", *[f"- {c}" for c in _CAVEATS]])
    return "\n".join(lines) + "\n", needs_attention
