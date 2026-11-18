"""Provider-free readiness review of saved Demand Brief schema-v1 JSON."""

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
