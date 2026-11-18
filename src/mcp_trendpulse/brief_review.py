"""Provider-free readiness review of saved Demand Brief schema-v1 JSON."""

import csv
import io
import json
import math
import re
from datetime import datetime

MAX_EVIDENCE_BYTES = 1024 * 1024
_MARKET = re.compile(r"[A-Z]{2}(?:-[A-Z0-9]{1,6}){0,2}\Z")


def _unique_keys(pairs):
    data = {}
    for key, value in pairs:
        if key in data:
            raise ValueError("Duplicate JSON key")
        data[key] = value
    return data


def _invalid_constant(value):
    raise ValueError(f"Invalid JSON numeric constant: {value}")


def _date_label(value):
    if value is None:
        return "n/a"
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[T ].+)?", value):
        raise ValueError("Invalid evidence observation date")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid evidence observation date") from exc
    return value


def _is_number(value, *, interest=False):
    if value is None:
        return False
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Non-finite or nonnumeric evidence value")
    if interest and not 0 <= value <= 100:
        raise ValueError("Out-of-range relative-interest index")
    return True


def review_saved_brief(raw, *, output_format="text"):
    """Return (formatted review, needs_attention), without network or file mutations."""
    if output_format not in ("text", "json"):
        raise ValueError("Unsupported Demand Brief review format")
    if len(raw) > MAX_EVIDENCE_BYTES:
        raise ValueError("Demand Brief evidence exceeds 1 MiB")
    try:
        evidence = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_keys,
                              parse_constant=_invalid_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Demand Brief evidence is not valid UTF-8 JSON") from exc
    if not isinstance(evidence, dict) or type(evidence.get("schema_version")) is not int or evidence["schema_version"] != 1:
        raise ValueError("Unsupported Demand Brief schema (expected v1)")
    if (evidence.get("source"), evidence.get("source_url"), evidence.get("property")) != (
        "Google Trends", "https://trends.google.com/trends/", "Google Search"
    ):
        raise ValueError("Unrecognized Demand Brief source metadata")
    timeframe = evidence.get("timeframe")
    if not isinstance(timeframe, str) or not 0 < len(timeframe.strip()) <= 128 or not timeframe.isprintable():
        raise ValueError("Missing or invalid timeframe")
    markets = evidence.get("markets")
    failures = evidence.get("failed_markets", [])
    if not isinstance(markets, list) or not isinstance(failures, list) or not markets and not failures:
        raise ValueError("Missing Demand Brief market records")
    if len(markets) > 2 or len(failures) > 2:
        raise ValueError("Demand Brief exceeds two-market scope")
    incomplete = evidence.get("incomplete", False)
    if type(incomplete) is not bool or incomplete != bool(failures):
        raise ValueError("Incomplete flag disagrees with failures")
    errors = {}
    for failure in failures:
        if not isinstance(failure, dict):
            raise ValueError("Malformed market failure")
        name, code = failure.get("market"), failure.get("code")
        if not isinstance(name, str) or not _MARKET.fullmatch(name) or name in errors:
            raise ValueError("Invalid or duplicate failed market")
        if not isinstance(code, str) or not re.fullmatch(r"[a-z0-9_]{1,64}", code):
            raise ValueError("Invalid failure code")
        if failure.get("component") not in (None, "growth"):
            raise ValueError("Unsupported failure component")
        if type(failure.get("retryable")) is not bool or not isinstance(failure.get("message"), str):
            raise ValueError("Malformed failure details")
        errors[name] = failure
    lines = [
        "TrendPulse saved Demand Brief evidence review (offline; schema v1)",
        f"Timeframe: {timeframe.strip()}",
        "Source: Google Trends / Google Search (declared by file, not authenticated)",
    ]
    seen = set()
    market_reviews = []
    expected_keywords = None
    needs_attention = incomplete
    for market in markets:
        if not isinstance(market, dict):
            raise ValueError("Malformed market record")
        name = market.get("market")
        if not isinstance(name, str) or not _MARKET.fullmatch(name) or name in seen:
            raise ValueError("Invalid or duplicate market")
        seen.add(name)
        if not {"market", "keywords", "warnings", "growth_basis", "latest_complete_trends_point"} <= set(market):
            raise ValueError("Missing market evidence fields")
        if market["growth_basis"] not in ("selected_timeframe", "separate_lookback_requests"):
            raise ValueError("Invalid growth basis")
        keywords, warnings = market.get("keywords"), market.get("warnings")
        if not isinstance(keywords, list) or not 1 <= len(keywords) <= 5:
            raise ValueError("Invalid market keyword records")
        if not isinstance(warnings, list) or any(not isinstance(w, str) for w in warnings):
            raise ValueError("Invalid evidence warnings")
        names, observed = [], 0
        for item in keywords:
            if not isinstance(item, dict) or not isinstance(item.get("keyword"), str):
                raise ValueError("Malformed keyword record")
            if not {"keyword", "latest_index", "latest_observation", "growth_3m_pct", "growth_1y_pct"} <= set(item):
                raise ValueError("Missing keyword evidence fields")
            keyword = item["keyword"].strip()
            if not keyword or len(keyword) > 200:
                raise ValueError("Invalid keyword label")
            names.append(keyword.casefold())
            valid = _is_number(item.get("latest_index"), interest=True)
            last = _date_label(item.get("latest_observation"))
            if valid and last == "n/a":
                raise ValueError("Observed keyword has no date")
            _is_number(item.get("growth_3m_pct"))
            _is_number(item.get("growth_1y_pct"))
            observed += int(valid)
        if len(set(names)) != len(names):
            raise ValueError("Duplicate keywords")
        if expected_keywords is not None and expected_keywords != set(names):
            raise ValueError("Inconsistent keywords between markets")
        expected_keywords = set(names)
        latest = _date_label(market.get("latest_complete_trends_point"))
        if observed and latest == "n/a":
            raise ValueError("Observed market has no latest date")
        failure = errors.get(name)
        if failure and failure.get("component") != "growth":
            raise ValueError("Market includes observations and a primary-provider failure")
        status = "observed" if observed == len(keywords) else "missing primary evidence"
        if failure:
            status += "; growth unavailable"
        if observed < len(keywords):
            needs_attention = True
        market_reviews.append({
            "market": name,
            "observed_keywords": observed,
            "total_keywords": len(keywords),
            "latest_market_observation": None if latest == "n/a" else latest,
            "status": "observed" if observed == len(keywords) else "missing_primary_evidence",
            "growth_unavailable": bool(failure),
            "warning_count": len(warnings),
        })
        lines.append(
            f"{name}: {observed}/{len(keywords)} keywords with primary evidence; "
            f"latest market observation {latest}; {status}; {len(warnings)} warning(s)"
        )
    for name, failure in errors.items():
        if name not in seen:
            lines.append(f"{name}: no market evidence; failure {failure['code']} (not ready)")
    if len(seen | set(errors)) > 2:
        raise ValueError("Demand Brief exceeds two-market scope")
    caveats = [
        "Normalized interest is not search volume; do not rank indices across markets.",
        "This checks saved fields only, not whether the provider supplied the data.",
    ]
    if output_format == "json":
        report = {
            "schema_version": 1,
            "assessment": "needs_human_review" if needs_attention else "structurally_complete",
            "needs_human_review": needs_attention,
            "source_authenticated": False,
            "timeframe": timeframe.strip(),
            "markets": market_reviews,
            "failed_markets": [
                {"market": name, "component": failure.get("component"), "code": failure["code"]}
                for name, failure in errors.items()
            ],
            "caveats": caveats,
        }
        return json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n", needs_attention
    lines += [
        "Assessment: NEEDS HUMAN REVIEW" if needs_attention else "Assessment: structurally complete; review warnings",
        *caveats,
    ]
    return "\n".join(lines) + "\n", needs_attention


def compare_saved_briefs(before_raw, after_raw, *, output_format="text"):
    """Compare saved evidence *coverage*, never normalized interest indices."""
    if output_format not in ("text", "json", "csv", "keyword-csv"):
        raise ValueError("Unsupported Demand Brief comparison format")
    before_text, _ = review_saved_brief(before_raw, output_format="json")
    after_text, needs_review = review_saved_brief(after_raw, output_format="json")
    before_report, after_report = json.loads(before_text), json.loads(after_text)
    if before_report["timeframe"] != after_report["timeframe"]:
        raise ValueError("Snapshots not comparable: timeframe differs")

    # Both inputs are already fully validated by review_saved_brief above.
    before_data = json.loads(before_raw.decode("utf-8-sig"))
    after_data = json.loads(after_raw.decode("utf-8-sig"))
    before_markets = {m["market"]: m for m in before_report["markets"]}
    after_markets = {m["market"]: m for m in after_report["markets"]}
    before_failures = {m["market"]: m["code"] for m in before_report["failed_markets"]}
    after_failures = {m["market"]: m["code"] for m in after_report["failed_markets"]}
    before_scope = set(before_markets) | set(before_failures)
    after_scope = set(after_markets) | set(after_failures)
    if before_scope != after_scope:
        raise ValueError("Snapshots not comparable: market scope differs")

    def keywords_by_market(document):
        return {
            market["market"]: {word["keyword"].strip().casefold() for word in market["keywords"]}
            for market in document["markets"]
        }

    before_keywords = keywords_by_market(before_data)
    after_keywords = keywords_by_market(after_data)
    for market in before_scope:
        if market in before_keywords and market in after_keywords:
            if before_keywords[market] != after_keywords[market]:
                raise ValueError(f"Snapshots not comparable: keyword scope differs in {market}")

    def snapshot(market, records, failures):
        item = records.get(market)
        return {
            "observed_keywords": item["observed_keywords"] if item else None,
            "total_keywords": item["total_keywords"] if item else None,
            "latest_market_observation": item["latest_market_observation"] if item else None,
            "warning_count": item["warning_count"] if item else None,
            "growth_unavailable": item["growth_unavailable"] if item else None,
            "failure_code": failures.get(market),
        }

    comparisons = []
    for market in sorted(before_scope):
        earlier = snapshot(market, before_markets, before_failures)
        later = snapshot(market, after_markets, after_failures)
        delta = None
        if earlier["observed_keywords"] is not None and later["observed_keywords"] is not None:
            delta = later["observed_keywords"] - earlier["observed_keywords"]
        comparisons.append({
            "market": market,
            "before": earlier,
            "after": later,
            "primary_coverage_change": delta,
        })

    caveats = [
        "Do not compare normalized relative-interest indices across captures or markets.",
        "File order is user-declared; capture chronology and provider provenance are not authenticated.",
        "Missing market records do not establish an identical keyword scope; coverage delta is unknown.",
    ]
    report = {
        "schema_version": 1,
        "comparison": "coverage_only",
        "source_authenticated": False,
        "timeframe": before_report["timeframe"],
        "needs_human_review": needs_review,
        "markets": comparisons,
        "caveats": caveats,
    }
    if output_format == "json":
        return json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n", needs_review
    if output_format == "keyword-csv":
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow([
            "market", "keyword", "timeframe", "before_primary_available",
            "after_primary_available", "primary_availability_change",
            "before_latest_observation", "after_latest_observation",
            "before_failure_code", "after_failure_code", "source_authenticated",
            "needs_human_review", "caveats",
        ])
        source_markets = [
            {market["market"]: market for market in document["markets"]}
            for document in (before_data, after_data)
        ]
        timeframe = report["timeframe"]
        if timeframe.lstrip().startswith(("=", "+", "-", "@")):
            timeframe = "'" + timeframe.lstrip()
        for market in sorted(before_scope):
            snapshots = [
                {word["keyword"].strip().casefold(): word for word in source.get(market, {}).get("keywords", [])}
                for source in source_markets
            ]
            # A completely unavailable market needs a visible row, not an empty CSV.
            for keyword_key in sorted(set(snapshots[0]) | set(snapshots[1])) or [None]:
                earlier = snapshots[0].get(keyword_key)
                later = snapshots[1].get(keyword_key)
                label = (later or earlier or {}).get("keyword", "").strip()
                if label.lstrip().startswith(("=", "+", "-", "@")):
                    label = "'" + label.lstrip()
                before_valid = _is_number(earlier["latest_index"], interest=True) if earlier else None
                after_valid = _is_number(later["latest_index"], interest=True) if later else None
                if before_valid is None or after_valid is None:
                    change = "unknown"
                elif before_valid == after_valid:
                    change = "unchanged"
                else:
                    change = "gained" if after_valid else "lost"
                writer.writerow([
                    market, label, timeframe,
                    str(before_valid).lower() if before_valid is not None else "",
                    str(after_valid).lower() if after_valid is not None else "",
                    change,
                    earlier["latest_observation"] if before_valid else "",
                    later["latest_observation"] if after_valid else "",
                    before_failures.get(market), after_failures.get(market),
                    "false", str(needs_review).lower(), "; ".join(caveats),
                ])
        return buffer.getvalue(), needs_review
    if output_format == "csv":
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow([
            "market", "timeframe", "before_observed_keywords", "before_total_keywords",
            "after_observed_keywords", "after_total_keywords", "primary_coverage_change",
            "before_latest_observation", "after_latest_observation", "before_failure_code",
            "after_failure_code", "before_growth_unavailable", "after_growth_unavailable",
            "before_warning_count", "after_warning_count", "source_authenticated",
            "needs_human_review", "caveats",
        ])
        # A timeframe is declared by the input file. Prevent spreadsheet formula execution.
        timeframe = report["timeframe"]
        if timeframe.lstrip().startswith(("=", "+", "-", "@")):
            timeframe = "'" + timeframe.lstrip()
        for item in comparisons:
            earlier, later = item["before"], item["after"]
            writer.writerow([
                item["market"], timeframe,
                earlier["observed_keywords"], earlier["total_keywords"],
                later["observed_keywords"], later["total_keywords"],
                item["primary_coverage_change"],
                earlier["latest_market_observation"], later["latest_market_observation"],
                earlier["failure_code"], later["failure_code"],
                earlier["growth_unavailable"], later["growth_unavailable"],
                earlier["warning_count"], later["warning_count"],
                "false", str(needs_review).lower(), "; ".join(caveats),
            ])
        return buffer.getvalue(), needs_review

    lines = [
        "TrendPulse saved Demand Brief evidence coverage comparison (offline)",
        f"Timeframe: {report['timeframe']}",
    ]
    for item in comparisons:
        def count(data):
            observed, total = data["observed_keywords"], data["total_keywords"]
            return "unavailable" if observed is None else f"{observed}/{total}"

        lines.append(f"{item['market']}: {count(item['before'])} -> {count(item['after'])} "
                     f"(primary coverage delta: {item['primary_coverage_change']})")
        lines.append(f"  Latest observations: {item['before']['latest_market_observation'] or 'n/a'} "
                     f"-> {item['after']['latest_market_observation'] or 'n/a'}; "
                     f"failure codes: {item['before']['failure_code'] or 'none'} "
                     f"-> {item['after']['failure_code'] or 'none'}")
    lines.append("Assessment: current snapshot needs human review" if needs_review else
                 "Assessment: current snapshot structurally complete; review warnings")
    return "\n".join([*lines, *caveats]) + "\n", needs_review
