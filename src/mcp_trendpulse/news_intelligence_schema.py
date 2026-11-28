"""Offline-only news observations and bounded GDELT DOC response projections.

These records describe what a source reported, never whether a claim is true.
No network client, tool registration, persistent cache, or article fetch is added.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Annotated, Literal
from urllib.parse import urlencode, urlsplit
from xml.etree import ElementTree

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from mcp_trendpulse.intelligence_signal import validate_public_source_url
from mcp_trendpulse.rss_url_validation import is_google_news_rss_url

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_ATTRIBUTION = "The GDELT Project (https://www.gdeltproject.org/)"
NASA_RSS_URL = "https://www.nasa.gov/feed/"
NASA_ATTRIBUTION = "NASA (https://www.nasa.gov/)"
_NASA_LINK_HOSTS = frozenset({"www.nasa.gov", "science.nasa.gov"})
_SOURCE_ATTRIBUTION = {
    "google_news_rss": "Google News RSS (https://news.google.com/)",
    "gdelt_doc": GDELT_ATTRIBUTION,
    "nasa_rss": NASA_ATTRIBUTION,
}
MAX_BYTES = 256 * 1024
MAX_ARTICLES = 20
MAX_POINTS = 500
Provider = Literal["google_news_rss", "gdelt_doc", "nasa_rss"]
Status = Literal["observed", "partial", "empty", "invalid", "unavailable"]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Count = Annotated[int, Field(strict=True, ge=0, le=2**53 - 1)]


def _text(value: object, maximum: int) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValueError("Invalid bounded text")
    if value != value.strip() or any(unicodedata.category(c) in {"Cc", "Cf", "Cs"} for c in value):
        raise ValueError("Unsafe text")
    return value


def _url(value: str) -> str:
    _text(value, 8192)
    if any(c.isspace() for c in value) or "\\" in value or re.search(r"%(?:00|0a|0d|5c)", value, re.I):
        raise ValueError("Unsafe citation URL")
    validate_public_source_url(value)
    return value


def _utc(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", value
    ):
        raise ValueError("Explicit-offset ISO timestamp required")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
    except (ValueError, OverflowError) as exc:
        raise ValueError("Invalid timestamp") from exc


def _digest(value: object) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)

    @field_validator("schema_version", mode="before", check_fields=False)
    @classmethod
    def _version(cls, value: object) -> object:
        if type(value) is not int or value != 1:
            raise ValueError("Unsupported schema version")
        return value


class TimeEvidence(FrozenModel):
    value: str = Field(max_length=64)
    precision: Literal["day", "second", "subsecond"]
    basis: Literal["feed", "legacy_normalized", "publisher", "provider_seen"]

    @model_validator(mode="after")
    def _check(self) -> TimeEvidence:
        if self.precision == "day":
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", self.value):
                raise ValueError("Date precision mismatch")
            date.fromisoformat(self.value)
        else:
            if ("." in self.value) != (self.precision == "subsecond"):
                raise ValueError("Timestamp precision mismatch")
            _utc(self.value)
        # Preserve the original offset and fractional representation.
        return self


class NewsArticle(FrozenModel):
    schema_version: Literal[1] = 1
    article_id: Digest | None = None
    observation_id: Digest | None = None
    discovery_provider: Provider
    reported_url: str
    link_type: Literal["google_news_rss", "publisher_candidate"]
    title: str
    publisher_label: str | None = None
    reported_language: str | None = None
    reported_source_country: str | None = None
    published_at: TimeEvidence | None = None
    provider_seen_at: TimeEvidence | None = None
    captured_at: str | None = None
    capture_mode: Literal["live", "legacy_import"]
    content_level: Literal["headline_only"] = "headline_only"
    retention_scope: Literal["metadata_only"] = "metadata_only"
    warnings: tuple[Literal["legacy_date_provenance", "invalid_source_date", "source_date_unknown"], ...] = ()

    @field_validator("reported_url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        return _url(value)

    @field_validator("title", "publisher_label", "reported_language", "reported_source_country")
    @classmethod
    def _validate_text(cls, value: str | None, info) -> str | None:
        return None if value is None else _text(value, 512 if info.field_name == "title" else 160)

    @field_validator("captured_at")
    @classmethod
    def _capture(cls, value: str | None) -> str | None:
        return _utc(value) if value is not None else None

    @model_validator(mode="after")
    def _validate_identity(self) -> NewsArticle:
        rss = self.discovery_provider == "google_news_rss"
        nasa = self.discovery_provider == "nasa_rss"
        if rss != (self.link_type == "google_news_rss") or rss != is_google_news_rss_url(self.reported_url):
            raise ValueError("Source/link type mismatch")
        if self.capture_mode == "live" and self.captured_at is None:
            raise ValueError("Live observation needs capture time")
        if (rss or nasa) and (self.provider_seen_at is not None or self.reported_source_country is not None
                             or self.reported_language is not None):
            raise ValueError("RSS metadata does not establish provider seen time or original locale")
        if nasa and (self.publisher_label != "NASA" or urlsplit(self.reported_url).hostname not in _NASA_LINK_HOSTS):
            raise ValueError("NASA feed link is outside its supported publisher scope")
        if self.published_at is not None:
            expected_basis = "legacy_normalized" if rss else "feed" if nasa else None
            if self.published_at.basis != expected_basis:
                raise ValueError("Unverified publication timestamp")
        if (self.published_at is not None and self.captured_at is not None
                and self.published_at.precision != "day"
                and datetime.fromisoformat(_utc(self.published_at.value)) > datetime.fromisoformat(self.captured_at)):
            raise ValueError("Publication date after capture")
        if self.provider_seen_at is not None:
            if rss or self.provider_seen_at.basis != "provider_seen" or self.provider_seen_at.precision == "day":
                raise ValueError("Invalid provider seen time")
            if self.captured_at and datetime.fromisoformat(_utc(self.provider_seen_at.value)) > datetime.fromisoformat(self.captured_at):
                raise ValueError("Source observation after capture")
        if len(self.warnings) != len(set(self.warnings)) or len(self.warnings) > 3:
            raise ValueError("Invalid warnings")
        article_id = _digest([1, self.discovery_provider, self.reported_url])
        observation_id = _digest(self.model_dump(mode="json", exclude={"article_id", "observation_id"}))
        if self.article_id not in (None, article_id) or self.observation_id not in (None, observation_id):
            raise ValueError("Observation identity mismatch")
        object.__setattr__(self, "article_id", article_id)
        object.__setattr__(self, "observation_id", observation_id)
        return self


class NewsBatch(FrozenModel):
    schema_version: Literal[1] = 1
    provider: Provider
    status: Status
    captured_at: str | None
    attribution: str
    source_count: Count | None = None
    invalid_count: Count | None = None
    duplicate_count: Count | None = None
    truncated_count: Count | None = None
    possibly_capped: bool = False
    rejected_row_reasons: tuple[Literal[
        "invalid_row_shape", "unsafe_or_unsupported_url", "invalid_article_metadata"
    ], ...] = Field(default=(), max_length=MAX_ARTICLES)
    articles: tuple[NewsArticle, ...] = Field(default=(), max_length=MAX_ARTICLES)
    reason: Literal["invalid_payload", "all_rows_invalid", "provider_unavailable"] | None = None

    @model_validator(mode="after")
    def _check(self) -> NewsBatch:
        if self.captured_at is not None:
            object.__setattr__(self, "captured_at", _utc(self.captured_at))
        expected_attribution = _SOURCE_ATTRIBUTION[self.provider]
        if self.attribution != expected_attribution:
            raise ValueError("Missing source attribution")
        counts = (self.source_count, self.invalid_count, self.duplicate_count, self.truncated_count)
        if self.source_count is None:
            if any(c is not None for c in counts) or self.articles or self.status not in ("invalid", "unavailable"):
                raise ValueError("Unknown source coverage cannot have measurements")
        elif (any(c is None for c in counts)
              or self.source_count != len(self.articles) + sum(c for c in counts[1:] if c is not None)):
            raise ValueError("Inconsistent source counts")
        if len(self.rejected_row_reasons) != (self.invalid_count or 0):
            raise ValueError("Inconsistent rejected row diagnostics")
        if self.source_count is None:
            expected_status = "unavailable" if self.reason == "provider_unavailable" else "invalid"
            expected_reason = "provider_unavailable" if expected_status == "unavailable" else "invalid_payload"
        else:
            expected_status = ("empty" if self.source_count == 0 else "invalid" if not self.articles
                               else "partial" if self.invalid_count or self.truncated_count else "observed")
            expected_reason = "all_rows_invalid" if expected_status == "invalid" else None
        if self.status != expected_status or self.reason != expected_reason:
            raise ValueError("Inconsistent batch status")
        if any(a.discovery_provider != self.provider or a.captured_at != self.captured_at for a in self.articles):
            raise ValueError("Batch provenance mismatch")
        if len({a.observation_id for a in self.articles}) != len(self.articles):
            raise ValueError("Duplicate observation")
        return self


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("Nonfinite JSON constant")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Nonfinite JSON number")
    return number


def _decode(raw: bytes) -> object:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("Invalid payload size")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=_reject_constant, parse_float=_finite_float)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("Invalid JSON payload") from exc


def _reject_source_error(payload: object) -> None:
    """A successful HTTP status and an empty array can still hide a provider error."""
    if not isinstance(payload, dict):
        return
    status = payload.get("status")
    if ((isinstance(status, str) and status.strip().casefold() in {"error", "failed", "failure"})
            or any(payload.get(key) for key in ("error", "errors", "fault"))):
        raise ValueError("Provider returned an error envelope")


def _date_evidence(value: object, *, gdelt: bool) -> tuple[TimeEvidence | None, tuple]:
    if value is None or value == "":
        return None, ("source_date_unknown",)
    try:
        if gdelt:
            if not isinstance(value, str) or not re.fullmatch(r"\d{8}T\d{6}Z", value):
                raise ValueError("Invalid seen date")
            stamp = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat()
            return TimeEvidence(value=stamp, precision="second", basis="provider_seen"), ()
        raw = _text(value, 64)
        precision = "day" if len(raw) == 10 else "subsecond" if "." in raw else "second"
        return TimeEvidence(value=raw, precision=precision, basis="legacy_normalized"), ("legacy_date_provenance",)
    except ValueError:
        return None, ("invalid_source_date",)


def _label(value: object) -> str | None:
    return _text(value, 160) if value is not None and value != "" else None


def _element_text(parent: ElementTree.Element, name: str, *, optional: bool = False) -> str | None:
    nodes = parent.findall(name)
    if optional and not nodes:
        return None
    if len(nodes) != 1 or len(nodes[0]) != 0:
        raise ValueError("Missing or ambiguous feed metadata")
    return (nodes[0].text or "").strip()


def _nasa_row(row: object, captured_at: str | None) -> NewsArticle:
    if not isinstance(row, ElementTree.Element):
        raise ValueError("Invalid RSS item")
    published = _element_text(row, "pubDate", optional=True)
    stamp = None
    warnings = ("source_date_unknown",)
    if published:
        try:
            value = parsedate_to_datetime(_text(published, 128))
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("RSS date has no explicit offset")
            stamp = TimeEvidence(value=value.isoformat(), precision="second", basis="feed")
            warnings = ()
        except (ValueError, TypeError, OverflowError):
            warnings = ("invalid_source_date",)
    return NewsArticle(
        discovery_provider="nasa_rss", reported_url=_element_text(row, "link"),
        link_type="publisher_candidate", title=_element_text(row, "title"),
        publisher_label="NASA", published_at=stamp, captured_at=captured_at,
        capture_mode="legacy_import", warnings=warnings,
    )


def _map_row(row: object, provider: Provider, captured_at: str | None) -> NewsArticle:
    if provider == "nasa_rss":
        return _nasa_row(row, captured_at)
    if not isinstance(row, dict):
        raise ValueError("Invalid row")
    gdelt = provider == "gdelt_doc"
    if not gdelt:
        meta = row.get("meta_data")
        if not isinstance(meta, dict) or meta.get("content_level") != "rss_headline_only" or meta.get("source") != "google_news_rss":
            raise ValueError("RSS evidence level missing")
    stamp, warnings = _date_evidence(row.get("seendate" if gdelt else "publish_date"), gdelt=gdelt)
    return NewsArticle(
        discovery_provider=provider, reported_url=row.get("url"), title=row.get("title"),
        link_type="publisher_candidate" if gdelt else "google_news_rss",
        publisher_label=_label(row.get("domain" if gdelt else "meta_site_name")),
        reported_language=_label(row.get("language")) if gdelt else None,
        reported_source_country=_label(row.get("sourcecountry")) if gdelt else None,
        published_at=None if gdelt else stamp, provider_seen_at=stamp if gdelt else None,
        captured_at=captured_at, capture_mode="legacy_import", warnings=warnings,
    )


def parse_news_capture(raw: bytes, *, provider: Provider, captured_at: str | None, limit: int = MAX_ARTICLES) -> NewsBatch:
    """Project explicitly supplied JSON bytes; no fetch or authenticity assertion."""
    if provider not in ("gdelt_doc", "google_news_rss") or type(limit) is not int or not 1 <= limit <= MAX_ARTICLES:
        raise ValueError("Unsupported provider or limit")
    if captured_at is not None:
        captured_at = _utc(captured_at)
    common = dict(provider=provider, captured_at=captured_at, attribution=_SOURCE_ATTRIBUTION[provider])
    try:
        payload = _decode(raw)
        _reject_source_error(payload)
        rows = payload.get("articles") if provider == "gdelt_doc" and isinstance(payload, dict) else payload if provider == "google_news_rss" else None
        if not isinstance(rows, list):
            raise ValueError("Invalid source shape")
    except ValueError:
        return NewsBatch(**common, status="invalid", reason="invalid_payload")
    return _project_rows(rows, provider=provider, captured_at=captured_at, limit=limit)


def _project_rows(rows: list, *, provider: Provider, captured_at: str | None, limit: int) -> NewsBatch:
    common = dict(provider=provider, captured_at=captured_at, attribution=_SOURCE_ATTRIBUTION[provider])
    articles = []
    seen = set()
    invalid = duplicates = 0
    rejected = []
    for row in rows[:limit]:
        if not isinstance(row, ElementTree.Element if provider == "nasa_rss" else dict):
            invalid += 1
            rejected.append("invalid_row_shape")
            continue
        try:
            link = _element_text(row, "link") if provider == "nasa_rss" else row.get("url")
            _url(link)
            if provider == "nasa_rss" and urlsplit(link).hostname not in _NASA_LINK_HOSTS:
                raise ValueError("Unsupported NASA link")
        except ValueError:
            invalid += 1
            rejected.append("unsafe_or_unsupported_url")
            continue
        try:
            article = _map_row(row, provider, captured_at)
        except ValueError:
            invalid += 1
            rejected.append("invalid_article_metadata")
            continue
        if article.observation_id in seen:
            duplicates += 1
            continue
        seen.add(article.observation_id)
        articles.append(article)
    truncated = max(0, len(rows) - limit)
    status = "empty" if not rows else "invalid" if not articles else "partial" if invalid or truncated else "observed"
    return NewsBatch(
        **common, status=status, source_count=len(rows), invalid_count=invalid,
        duplicate_count=duplicates, truncated_count=truncated, possibly_capped=len(rows) >= limit,
        articles=tuple(articles), rejected_row_reasons=tuple(rejected),
        reason="all_rows_invalid" if status == "invalid" else None,
    )


def nasa_rss_request() -> dict:
    """Plan the official NASA recent-content feed; no network I/O or user URL."""
    return {
        "url": NASA_RSS_URL, "method": "GET", "status": "planned",
        "network_performed": False, "attribution": NASA_ATTRIBUTION,
        "scope": "recent NASA-published content; not a complete news archive",
    }


def parse_nasa_rss_capture(raw: bytes, *, captured_at: str | None, limit: int = MAX_ARTICLES) -> NewsBatch:
    """Project metadata from a supplied NASA RSS 2.0 capture, not publisher text."""
    if type(limit) is not int or not 1 <= limit <= MAX_ARTICLES:
        raise ValueError("Unsupported limit")
    if captured_at is not None:
        captured_at = _utc(captured_at)
    common = dict(provider="nasa_rss", captured_at=captured_at, attribution=NASA_ATTRIBUTION)
    try:
        if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
            raise ValueError("Invalid payload size")
        text = raw.decode("utf-8-sig", "strict")
        if "\x00" in text or "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            raise ValueError("DTD and entity declarations are prohibited")
        root = ElementTree.fromstring(text)
        channels = root.findall("channel")
        if root.tag != "rss" or root.attrib.get("version") != "2.0" or len(channels) != 1:
            raise ValueError("Expected one RSS 2.0 channel")
        channel = channels[0]
        _text(_element_text(channel, "title"), 512)
        link = _url(_element_text(channel, "link"))
        if urlsplit(link).hostname not in _NASA_LINK_HOSTS:
            raise ValueError("Unsupported feed channel")
        rows = channel.findall("item")
    except (ValueError, ElementTree.ParseError):
        return NewsBatch(**common, status="invalid", reason="invalid_payload")
    return _project_rows(rows, provider="nasa_rss", captured_at=captured_at, limit=limit)


def gdelt_doc_request(phrase: str, *, as_of: str, days: int = 3, limit: int = 10,
                      mode: Literal["artlist", "timelinevolraw"] = "artlist") -> dict:
    """Build a fixed-origin request plan only. Never performs network I/O."""
    phrase = _text(phrase, 120)
    if not all(c.isalnum() or c in " -" for c in phrase) or not any(c.isalpha() for c in phrase):
        raise ValueError("Only a literal news search phrase is accepted")
    if type(days) is not int or not 1 <= days <= 30 or type(limit) is not int or not 1 <= limit <= MAX_ARTICLES:
        raise ValueError("Invalid request bounds")
    if mode not in ("artlist", "timelinevolraw"):
        raise ValueError("Unsupported request mode")
    end = datetime.fromisoformat(_utc(as_of))
    if end.microsecond:
        raise ValueError("GDELT plan requires whole seconds")
    try:
        start = end - timedelta(days=days)
    except OverflowError as exc:
        raise ValueError("Invalid time window") from exc
    params = {"query": '"' + phrase + '"', "mode": mode, "format": "json",
              "startdatetime": start.strftime("%Y%m%d%H%M%S"), "enddatetime": end.strftime("%Y%m%d%H%M%S")}
    if mode == "artlist":
        params.update(maxrecords=str(limit), sort="datedesc")
    else:
        # A moving average cannot be compared to GDELT's unsmoothed norm.
        params["timelinesmooth"] = "1"
    return {"url": GDELT_URL + "?" + urlencode(params), "method": "GET", "status": "planned",
            "network_performed": False, "attribution": GDELT_ATTRIBUTION}


class CoveragePoint(FrozenModel):
    interval_at: str
    matched: Count
    monitored: Count

    @model_validator(mode="after")
    def _check(self) -> CoveragePoint:
        object.__setattr__(self, "interval_at", _utc(self.interval_at))
        if self.matched > self.monitored:
            raise ValueError("Matched count exceeds monitored count")
        return self


class GdeltCoverage(FrozenModel):
    schema_version: Literal[1] = 1
    provider: Literal["gdelt_doc"] = "gdelt_doc"
    attribution: Literal["The GDELT Project (https://www.gdeltproject.org/)"] = GDELT_ATTRIBUTION
    metric: Literal["matched_and_monitored_articles"] = "matched_and_monitored_articles"
    status: Literal["observed", "empty"]
    points: tuple[CoveragePoint, ...] = Field(max_length=MAX_POINTS)

    @model_validator(mode="after")
    def _check(self) -> GdeltCoverage:
        dates = [p.interval_at for p in self.points]
        if self.status != ("observed" if dates else "empty") or dates != sorted(set(dates)):
            raise ValueError("Invalid coverage sequence")
        return self


def parse_gdelt_raw_timeline(raw: bytes) -> GdeltCoverage:
    """Strict unsmoothed count projection; absent/malformed timelines are not zeros."""
    payload = _decode(raw)
    _reject_source_error(payload)
    if not isinstance(payload, dict) or not isinstance(payload.get("timeline"), list):
        raise ValueError("Missing timeline")
    series = payload["timeline"]
    if not series:
        return GdeltCoverage(status="empty", points=())
    if len(series) != 1 or not isinstance(series[0], dict):
        raise ValueError("Expected one raw-volume series")
    data = series[0].get("data")
    if not isinstance(data, list) or len(data) > MAX_POINTS:
        raise ValueError("Invalid timeline bounds")
    points = []
    for row in data:
        if not isinstance(row, dict):
            raise ValueError("Invalid timeline row")
        stamp, _ = _date_evidence(row.get("date"), gdelt=True)
        if stamp is None:
            raise ValueError("Invalid interval timestamp")
        points.append(CoveragePoint(interval_at=stamp.value, matched=row.get("value"), monitored=row.get("norm")))
    points.sort(key=lambda p: p.interval_at)
    if len({p.interval_at for p in points}) != len(points):
        raise ValueError("Duplicate interval")
    return GdeltCoverage(status="observed" if points else "empty", points=tuple(points))
