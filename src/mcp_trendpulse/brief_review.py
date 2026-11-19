"""Provider-free readiness review of saved Demand Brief schema-v1 JSON."""

import csv
import html
import io
import json
import math
import re
from datetime import date, datetime

MAX_EVIDENCE_BYTES = 1024 * 1024
_MARKET = re.compile(r"[A-Z]{2}(?:-[A-Z0-9]{1,6}){0,2}\Z")


def _markdown_safe(value):
    """Render saved, unauthenticated labels as literal Markdown text."""
    text = html.escape(str(value).replace("\r", " ").replace("\n", " "), quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+.!|~>-])", r"\\\1", text)


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


def _observation_date_change(earlier, later):
    """Classify only comparable primary date-only observations, not timestamps."""
    if not earlier or not later:
        return "unknown"
    if not _is_number(earlier.get("latest_index"), interest=True) or not _is_number(
        later.get("latest_index"), interest=True
    ):
        return "unknown"
    before_date, after_date = earlier.get("latest_observation"), later.get("latest_observation")
    if not all(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
               for value in (before_date, after_date)):
        return "unknown"
    if after_date < before_date:
        return "older_after"
    if after_date > before_date:
        return "newer_after"
    return "unchanged"


def review_saved_brief(raw, *, output_format="text", as_of=None, max_age_days=None):
    """Return (formatted review, needs_attention), without network or file mutations."""
    if output_format not in ("text", "json", "csv", "markdown", "checklist"):
        raise ValueError("Unsupported Demand Brief review format")
    freshness_enabled = as_of is not None or max_age_days is not None
    if freshness_enabled:
        if as_of is None or max_age_days is None:
            raise ValueError("Freshness review requires both --as-of and --max-age-days")
        if not isinstance(as_of, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of):
            raise ValueError("Freshness --as-of must be YYYY-MM-DD")
        try:
            reference_date = date.fromisoformat(as_of)
        except ValueError as exc:
            raise ValueError("Invalid freshness --as-of date") from exc
        if type(max_age_days) is not int or not 0 <= max_age_days <= 3650:
            raise ValueError("Freshness --max-age-days must be between 0 and 3650")
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
    missing_by_market = {}
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
        freshness_exceptions = []
        stale_count = future_count = 0
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
            if not valid:
                missing_by_market.setdefault(name, []).append(keyword)
            if freshness_enabled and valid:
                observed_date = datetime.fromisoformat(last.replace("Z", "+00:00")).date()
                age_days = (reference_date - observed_date).days
                if age_days < 0:
                    future_count += 1
                    freshness_exceptions.append((keyword, last, "future", age_days))
                elif age_days > max_age_days:
                    stale_count += 1
                    freshness_exceptions.append((keyword, last, "stale", age_days))
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
        if freshness_exceptions:
            needs_attention = True
        market_review = {
            "market": name,
            "observed_keywords": observed,
            "total_keywords": len(keywords),
            "latest_market_observation": None if latest == "n/a" else latest,
            "status": "observed" if observed == len(keywords) else "missing_primary_evidence",
            "growth_unavailable": bool(failure),
            "warning_count": len(warnings),
        }
        if freshness_enabled:
            market_review["stale_keywords"] = stale_count
            market_review["future_keywords"] = future_count
            market_review["freshness_exceptions"] = [
                {"keyword": keyword, "latest_observation": observed_at,
                 "status": status, "age_days": days}
                for keyword, observed_at, status, days in freshness_exceptions
            ]
        market_reviews.append(market_review)
        lines.append(
            f"{name}: {observed}/{len(keywords)} keywords with primary evidence; "
            f"latest market observation {latest}; {status}; {len(warnings)} warning(s)"
        )
        for keyword, observed_at, status, days in freshness_exceptions:
            label = keyword.replace("\r", " ").replace("\n", " ")
            lines.append(f"  {label}: {status} primary observation {observed_at} (age {days} day(s))")
    for name, failure in errors.items():
        if name not in seen:
            lines.append(f"{name}: no market evidence; failure {failure['code']} (not ready)")
    if len(seen | set(errors)) > 2:
        raise ValueError("Demand Brief exceeds two-market scope")
    caveats = [
        "Normalized interest is not search volume; do not rank indices across markets.",
        "This checks saved fields only, not whether the provider supplied the data.",
    ]
    if freshness_enabled:
        caveats.append("Freshness uses file-declared observation dates and a user-declared as-of date; neither is authenticated.")
    if output_format == "checklist":
        # Only render validated file metadata and safe keyword labels; provider
        # errors and warning bodies may contain sensitive, untrusted text.
        rows = [
            "# Demand Brief evidence-gap checklist",
            "",
            f"**Timeframe:** {_markdown_safe(timeframe.strip())}",
            "**Source:** Google Trends / Google Search (declared by file, not authenticated)",
            "**Assessment:** NEEDS HUMAN REVIEW" if needs_attention else
            "**Assessment:** structurally complete; still requires human review",
            "",
        ]
        primary_gaps = False
        for item in market_reviews:
            name = item["market"]
            for keyword in missing_by_market.get(name, []):
                primary_gaps = True
                rows.append(
                    f"- [ ] {name} / {_markdown_safe(keyword)}: Missing primary observation; "
                    "inspect the saved source and collect new evidence only through an authorized, bounded request."
                )
            if item["growth_unavailable"]:
                code = errors[name]["code"]
                rows.append(
                    f"- [ ] {name}: Growth unavailable ({code}); review the saved failure "
                    "and leave growth conclusions undetermined."
                )
            if freshness_enabled:
                for issue in item["freshness_exceptions"]:
                    rows.append(
                        f"- [ ] {name} / {_markdown_safe(issue['keyword'])}: "
                        f"{issue['status']} primary observation {_markdown_safe(issue['latest_observation'])} "
                        f"(age {issue['age_days']} day(s) as of {as_of}); review before using the brief."
                    )
            if item["warning_count"]:
                rows.append(
                    f"- [ ] {name}: Review {item['warning_count']} saved warning(s); "
                    "the checklist does not validate or reproduce their text."
                )
        for name, failure in errors.items():
            if name not in seen:
                primary_gaps = True
                direction = (
                    "Do not bypass provider rate limits; wait for an authorized refresh."
                    if failure["code"] == "rate_limited"
                    else "Investigate the saved failure before any authorized refresh."
                )
                rows.append(
                    f"- [ ] {name}: no primary market evidence ({failure['code']}); "
                    f"coverage unknown, not zero. {direction}"
                )
        if not primary_gaps:
            rows.append("- [ ] No primary-evidence gaps detected; confirm relevance and comparability manually.")
        rows.extend([
            "- [ ] Independently verify provider provenance, market scope, "
            "timeframe, and relevant warnings before a buyer-facing interpretation.",
            "",
            "## Evidence limitations",
            *[f"- {caveat}" for caveat in caveats],
        ])
        return "\n".join(rows) + "\n", needs_attention
    if output_format == "markdown":
        rows = [
            "# Saved Demand Brief readiness review",
            "",
            f"**Timeframe:** {_markdown_safe(timeframe.strip())}",
            "**Source:** Google Trends / Google Search (declared by file, not authenticated)",
            "",
            "| Market | Primary coverage | Latest observation | Status | Warnings |",
            "| --- | ---: | --- | --- | ---: |",
        ]
        for item in market_reviews:
            status = item["status"].replace("_", " ")
            if item["growth_unavailable"]:
                status += "; growth unavailable"
            rows.append(
                f"| {item['market']} | {item['observed_keywords']}/{item['total_keywords']} | "
                f"{item['latest_market_observation'] or 'n/a'} | {status} | {item['warning_count']} |"
            )
        for name, failure in errors.items():
            if name not in seen:
                # No primary response means unknown coverage, not zero keywords.
                rows.append(f"| {name} | unknown | n/a | no market evidence ({failure['code']}) | unknown |")
        if freshness_enabled:
            rows.extend(["", f"**Freshness policy:** as of {as_of}, maximum age {max_age_days} day(s)", ""])
            rows.append("### Freshness exceptions")
            has_exceptions = False
            for market in market_reviews:
                for issue in market["freshness_exceptions"]:
                    has_exceptions = True
                    rows.append(
                        f"- {market['market']} / {_markdown_safe(issue['keyword'])}: "
                        f"{issue['status']} primary observation {_markdown_safe(issue['latest_observation'])} "
                        f"(age {issue['age_days']} day(s)); human review required"
                    )
            if not has_exceptions:
                rows.append("- None among observed primary evidence; missing primary evidence remains unknown")
        rows.extend([
            "",
            "**Assessment:** NEEDS HUMAN REVIEW" if needs_attention else
            "**Assessment:** structurally complete; review warnings",
            "",
            "## Evidence limitations",
            *[f"- {caveat}" for caveat in caveats],
        ])
        return "\n".join(rows) + "\n", needs_attention
    if output_format in ("json", "csv"):
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
        if freshness_enabled:
            report["freshness_policy"] = {"as_of": as_of, "max_age_days": max_age_days}
        if output_format == "json":
            return json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n", needs_attention
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, lineterminator="\n")
        header = [
            "market", "timeframe", "status", "assessment", "observed_keywords", "total_keywords",
            "latest_market_observation", "growth_unavailable", "warning_count", "failure_code",
            "source_authenticated", "needs_human_review", "caveats",
        ]
        if freshness_enabled:
            header.extend(["freshness_as_of", "freshness_max_age_days", "stale_keywords", "future_keywords"])
        writer.writerow(header)
        # The timeframe is declared by the file and may contain a spreadsheet formula.
        csv_timeframe = report["timeframe"]
        if csv_timeframe.lstrip().startswith(("=", "+", "-", "@")):
            csv_timeframe = "'" + csv_timeframe.lstrip()
        for item in market_reviews:
            fields = [
                item["market"], csv_timeframe, item["status"], report["assessment"],
                item["observed_keywords"], item["total_keywords"], item["latest_market_observation"],
                str(item["growth_unavailable"]).lower(), item["warning_count"],
                errors.get(item["market"], {}).get("code"), "false", str(needs_attention).lower(),
                "; ".join(caveats),
            ]
            if freshness_enabled:
                fields.extend([as_of, max_age_days, item["stale_keywords"], item["future_keywords"]])
            writer.writerow(fields)
        for name, failure in errors.items():
            if name not in seen:
                # Missing primary market data is unknown, never equivalent to zero coverage.
                fields = [
                    name, csv_timeframe, "no_market_evidence", report["assessment"],
                    None, None, None, None, None, failure["code"], "false",
                    str(needs_attention).lower(), "; ".join(caveats),
                ]
                if freshness_enabled:
                    fields.extend([as_of, max_age_days, None, None])
                writer.writerow(fields)
        return buffer.getvalue(), needs_attention
    lines += [
        "Assessment: NEEDS HUMAN REVIEW" if needs_attention else "Assessment: structurally complete; review warnings",
        *caveats,
    ]
    return "\n".join(lines) + "\n", needs_attention


def compare_saved_briefs(before_raw, after_raw, *, output_format="text", as_of=None, max_age_days=None):
    """Compare saved evidence *coverage*, never normalized interest indices."""
    if output_format not in ("text", "json", "csv", "keyword-csv", "markdown", "checklist"):
        raise ValueError("Unsupported Demand Brief comparison format")
    before_text, _ = review_saved_brief(before_raw, output_format="json")
    after_text, needs_review = review_saved_brief(
        after_raw, output_format="json", as_of=as_of, max_age_days=max_age_days
    )
    before_report, after_report = json.loads(before_text), json.loads(after_text)
    freshness_enabled = "freshness_policy" in after_report
    if before_report["timeframe"] != after_report["timeframe"]:
        raise ValueError("Snapshots not comparable: timeframe differs")

    # Both inputs are already fully validated by review_saved_brief above.
    before_data = json.loads(before_raw.decode("utf-8-sig"))
    after_data = json.loads(after_raw.decode("utf-8-sig"))
    before_markets = {m["market"]: m for m in before_report["markets"]}
    after_markets = {m["market"]: m for m in after_report["markets"]}
    before_failures = {m["market"]: m["code"] for m in before_report["failed_markets"]}
    after_failures = {m["market"]: m["code"] for m in after_report["failed_markets"]}
    after_freshness = {
        m["market"]: m["freshness_exceptions"]
        for m in after_report["markets"]
    } if freshness_enabled else {}
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

    source_markets = [
        {market["market"]: market for market in document["markets"]}
        for document in (before_data, after_data)
    ]

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
    date_regression = False
    for market in sorted(before_scope):
        earlier = snapshot(market, before_markets, before_failures)
        later = snapshot(market, after_markets, after_failures)
        delta = None
        if earlier["observed_keywords"] is not None and later["observed_keywords"] is not None:
            delta = later["observed_keywords"] - earlier["observed_keywords"]
        older = None
        if market in source_markets[0] and market in source_markets[1]:
            before_words = {
                word["keyword"].strip().casefold(): word
                for word in source_markets[0][market]["keywords"]
            }
            after_words = {
                word["keyword"].strip().casefold(): word
                for word in source_markets[1][market]["keywords"]
            }
            older = []
            for key in sorted(before_words):
                first, second = before_words[key], after_words[key]
                if _observation_date_change(first, second) == "older_after":
                    older.append({
                        "keyword": second["keyword"].strip(),
                        "before_date": first["latest_observation"],
                        "after_date": second["latest_observation"],
                    })
            if older:
                date_regression = True
                needs_review = True
        comparison = {
            "market": market,
            "before": earlier,
            "after": later,
            "primary_coverage_change": delta,
            "older_observations": older,
        }
        if freshness_enabled:
            comparison["after_freshness_exceptions"] = after_freshness.get(market, [])
        comparisons.append(comparison)

    caveats = [
        "Do not compare normalized relative-interest indices across captures or markets.",
        "File order is user-declared; capture chronology and provider provenance are not authenticated.",
        "Missing market records do not establish an identical keyword scope; coverage delta is unknown.",
        "Only date-only primary observations are compared for earlier after-file dates; timestamps are unclassified.",
    ]
    if freshness_enabled:
        caveats.append(
            "After-file freshness checks use file-declared observation dates and user-declared as-of; "
            "neither provenance nor capture date is authenticated."
        )
    report = {
        "schema_version": 1,
        "comparison": "coverage_only",
        "source_authenticated": False,
        "timeframe": before_report["timeframe"],
        "needs_human_review": needs_review,
        "markets": comparisons,
        "caveats": caveats,
    }
    if freshness_enabled:
        report["freshness_policy"] = after_report["freshness_policy"]
    if output_format == "json":
        return json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n", needs_review
    if output_format == "checklist":
        rows = [
            "# Demand Brief comparison action checklist",
            "",
            f"**Timeframe:** {_markdown_safe(report['timeframe'])}",
            "**Source:** Saved Google Trends / Google Search labels (not authenticated)",
            "**Assessment:** NEEDS HUMAN REVIEW" if needs_review else
            "**Assessment:** current snapshot structurally complete; review provenance",
            *([f"**After-file freshness policy:** as of {as_of}, maximum age {max_age_days} day(s)"]
              if freshness_enabled else []),
            "",
            "## Follow-up actions",
        ]
        primary_actions = 0
        for item in comparisons:
            market = item["market"]
            before_source = source_markets[0].get(market)
            after_source = source_markets[1].get(market)
            if after_source is None:
                # A failed provider market has unknown coverage, never a measured loss.
                code = after_failures.get(market, "unknown")
                advice = (
                    "Do not bypass provider rate limits; only retry under approved quotas."
                    if code == "rate_limited"
                    else "Investigate the saved failure before an authorized refresh."
                )
                rows.append(
                    f"- [ ] {market}: After-file primary coverage unknown, not zero "
                    f"({code}). {advice}"
                )
                primary_actions += 1
                continue
            if before_source is None:
                rows.append(
                    f"- [ ] {market}: Before-file primary coverage unknown; "
                    "inspect the after-file evidence without claiming a measured gain."
                )
                primary_actions += 1
            else:
                earlier_words = {
                    word["keyword"].strip().casefold(): word
                    for word in before_source["keywords"]
                }
                later_words = {
                    word["keyword"].strip().casefold(): word
                    for word in after_source["keywords"]
                }
                for key in sorted(later_words):
                    first, second = earlier_words[key], later_words[key]
                    label = _markdown_safe(second["keyword"].strip())
                    earlier_valid = _is_number(first["latest_index"], interest=True)
                    later_valid = _is_number(second["latest_index"], interest=True)
                    if earlier_valid and not later_valid:
                        rows.append(
                            f"- [ ] {market} / {label}: Primary evidence lost in the "
                            "declared after-file; verify the source and recover evidence "
                            "only through an authorized, bounded query."
                        )
                        primary_actions += 1
                    elif not earlier_valid and later_valid:
                        rows.append(
                            f"- [ ] {market} / {label}: Primary evidence gained in the "
                            "declared after-file; independently verify provenance."
                        )
                    elif not earlier_valid:
                        rows.append(
                            f"- [ ] {market} / {label}: Primary evidence still missing "
                            "in both files; investigate the gap before interpretation."
                        )
                        primary_actions += 1
            for older in item["older_observations"] or []:
                rows.append(
                    f"- [ ] {market} / {_markdown_safe(older['keyword'])}: "
                    "Review older primary observation in declared after-file "
                    f"({_markdown_safe(older['before_date'])} -> "
                    f"{_markdown_safe(older['after_date'])}); file order is not "
                    "verified capture chronology."
                )
            if item["after"]["growth_unavailable"]:
                rows.append(
                    f"- [ ] {market}: Growth unavailable "
                    f"({after_failures.get(market, 'unknown')}); "
                    "do not infer a trend direction."
                )
            warning_count = item["after"]["warning_count"]
            if warning_count:
                rows.append(
                    f"- [ ] {market}: Review {warning_count} saved warning(s) "
                    "without treating warning text as verified evidence."
                )
            if freshness_enabled:
                for issue in item["after_freshness_exceptions"]:
                    rows.append(
                        f"- [ ] {market} / {_markdown_safe(issue['keyword'])}: "
                        f"{issue['status']} primary observation "
                        f"{_markdown_safe(issue['latest_observation'])} "
                        f"(age {issue['age_days']} day(s) as of {as_of}); "
                        "review before use."
                    )
        if primary_actions == 0:
            rows.append(
                "- [ ] No primary availability regressions or continuing gaps "
                "detected in comparable saved records; confirm relevance manually."
            )
        rows.extend([
            "- [ ] Independently verify source provenance, keyword and market scope, "
            "file ordering and warnings before buyer-facing conclusions.",
            "",
            "## Evidence limitations",
            *[f"- {caveat}" for caveat in caveats],
        ])
        return "\n".join(rows) + "\n", needs_review
    if output_format == "markdown":
        rows = [
            "# Saved Demand Brief evidence comparison",
            "",
            f"**Timeframe:** {_markdown_safe(report['timeframe'])}",
            "**Source:** Saved Google Trends / Google Search labels (not authenticated)",
            *([f"**After-file freshness policy:** as of {as_of}, maximum age {max_age_days} day(s)"]
              if freshness_enabled else []),
            "",
            "| Market | Before primary coverage | After primary coverage | Coverage delta |",
            "| --- | ---: | ---: | ---: |",
        ]
        for item in comparisons:
            def coverage(snapshot):
                observed = snapshot["observed_keywords"]
                return "unknown" if observed is None else f"{observed}/{snapshot['total_keywords']}"

            delta = item["primary_coverage_change"]
            rows.append(
                f"| {item['market']} | {coverage(item['before'])} | {coverage(item['after'])} | "
                f"{'unknown' if delta is None else f'{delta:+d}'} |"
            )
        for item in comparisons:
            rows.append("")
            rows.append(f"### {item['market']} observation details")
            rows.append(
                f"- Latest market observation (before -> after): "
                f"{item['before']['latest_market_observation'] or 'n/a'} -> "
                f"{item['after']['latest_market_observation'] or 'n/a'}"
            )
            rows.append(
                f"- Failure codes (before -> after): "
                f"{item['before']['failure_code'] or 'none'} -> "
                f"{item['after']['failure_code'] or 'none'}"
            )
            for older in item["older_observations"] or []:
                rows.append(
                    f"- Primary observation older in declared after-file: "
                    f"{_markdown_safe(older['keyword'])} "
                    f"({_markdown_safe(older['before_date'])} -> {_markdown_safe(older['after_date'])}); "
                    "human review required"
                )
            if freshness_enabled:
                for issue in item["after_freshness_exceptions"]:
                    rows.append(
                        f"- After-file freshness exception: {_markdown_safe(issue['keyword'])}: "
                        f"{issue['status']} observation {_markdown_safe(issue['latest_observation'])} "
                        f"(age {issue['age_days']} day(s)); human review required"
                    )
        rows.extend([
            "",
            "**Assessment:** NEEDS HUMAN REVIEW" if needs_review else
            "**Assessment:** current snapshot structurally complete; review warnings",
            "",
            "## Evidence limitations",
            *[f"- {caveat}" for caveat in caveats],
        ])
        return "\n".join(rows) + "\n", needs_review
    if output_format == "keyword-csv":
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, lineterminator="\n")
        header = [
            "market", "keyword", "timeframe", "before_primary_available",
            "after_primary_available", "primary_availability_change",
            "before_latest_observation", "after_latest_observation",
            "observation_date_change",
            "before_failure_code", "after_failure_code", "source_authenticated",
            "needs_human_review", "caveats",
        ]
        if freshness_enabled:
            header.extend(["freshness_as_of", "freshness_max_age_days", "after_freshness_status"])
        writer.writerow(header)
        timeframe = report["timeframe"]
        if timeframe.lstrip().startswith(("=", "+", "-", "@")):
            timeframe = "'" + timeframe.lstrip()
        for market in sorted(before_scope):
            snapshots = [
                {word["keyword"].strip().casefold(): word for word in source.get(market, {}).get("keywords", [])}
                for source in source_markets
            ]
            freshness_by_keyword = {
                issue["keyword"].strip().casefold(): issue["status"]
                for item in comparisons if item["market"] == market
                for issue in item.get("after_freshness_exceptions", [])
            }
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
                fields = [
                    market, label, timeframe,
                    str(before_valid).lower() if before_valid is not None else "",
                    str(after_valid).lower() if after_valid is not None else "",
                    change,
                    earlier["latest_observation"] if before_valid else "",
                    later["latest_observation"] if after_valid else "",
                    _observation_date_change(earlier, later),
                    before_failures.get(market), after_failures.get(market),
                    "false", str(needs_review).lower(), "; ".join(caveats),
                ]
                if freshness_enabled:
                    status = (
                        freshness_by_keyword.get(keyword_key, "within_policy")
                        if after_valid else "unknown"
                    )
                    fields.extend([as_of, max_age_days, status])
                writer.writerow(fields)
        return buffer.getvalue(), needs_review
    if output_format == "csv":
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, lineterminator="\n")
        header = [
            "market", "timeframe", "before_observed_keywords", "before_total_keywords",
            "after_observed_keywords", "after_total_keywords", "primary_coverage_change",
            "older_observation_keyword_count",
            "before_latest_observation", "after_latest_observation", "before_failure_code",
            "after_failure_code", "before_growth_unavailable", "after_growth_unavailable",
            "before_warning_count", "after_warning_count", "source_authenticated",
            "needs_human_review", "caveats",
        ]
        if freshness_enabled:
            header.extend([
                "freshness_as_of", "freshness_max_age_days",
                "after_stale_keywords", "after_future_keywords",
            ])
        writer.writerow(header)
        # A timeframe is declared by the input file. Prevent spreadsheet formula execution.
        timeframe = report["timeframe"]
        if timeframe.lstrip().startswith(("=", "+", "-", "@")):
            timeframe = "'" + timeframe.lstrip()
        for item in comparisons:
            earlier, later = item["before"], item["after"]
            fields = [
                item["market"], timeframe,
                earlier["observed_keywords"], earlier["total_keywords"],
                later["observed_keywords"], later["total_keywords"],
                item["primary_coverage_change"],
                len(item["older_observations"]) if item["older_observations"] is not None else None,
                earlier["latest_market_observation"], later["latest_market_observation"],
                earlier["failure_code"], later["failure_code"],
                earlier["growth_unavailable"], later["growth_unavailable"],
                earlier["warning_count"], later["warning_count"],
                "false", str(needs_review).lower(), "; ".join(caveats),
            ]
            if freshness_enabled:
                issues = item["after_freshness_exceptions"]
                fields.extend([
                    as_of, max_age_days,
                    sum(issue["status"] == "stale" for issue in issues)
                    if later["observed_keywords"] is not None else None,
                    sum(issue["status"] == "future" for issue in issues)
                    if later["observed_keywords"] is not None else None,
                ])
            writer.writerow(fields)
        return buffer.getvalue(), needs_review

    lines = [
        "TrendPulse saved Demand Brief evidence coverage comparison (offline)",
        f"Timeframe: {report['timeframe']}",
    ]
    if freshness_enabled:
        lines.append(f"After-file freshness policy: as of {as_of}; maximum age {max_age_days} day(s)")
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
        for older in item["older_observations"] or []:
            lines.append(f"  Earlier observation in declared after-file: {older['keyword']} "
                         f"{older['before_date']} -> {older['after_date']} (review)")
        if freshness_enabled:
            for issue in item["after_freshness_exceptions"]:
                lines.append(
                    f"  After-file freshness exception: {issue['keyword']}: {issue['status']} "
                    f"observation {issue['latest_observation']} (age {issue['age_days']} day(s); review)"
                )
    lines.append("Assessment: declared observation dates regressed; human review required" if date_regression else
                 "Assessment: current snapshot needs human review" if needs_review else
                 "Assessment: current snapshot structurally complete; review warnings")
    return "\n".join([*lines, *caveats]) + "\n", needs_review
