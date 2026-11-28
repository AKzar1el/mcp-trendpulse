"""V4.03: additive extraction receipts; discovery is never overwritten.

Uses the existing connection-pinned downloader. No new fetcher, browser,
retry, NLP, persistent body store, MCP registration or paid dependency.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timezone
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator

from mcp_trendpulse.news_intelligence_schema import Digest, FrozenModel, NewsArticle, _digest, _text, _url, _utc

_MAX_BODY_BYTES = 5 * 1024 * 1024
Reason = Literal[
    "download_unavailable", "download_rejected", "download_timeout",
    "download_failed", "invalid_extracted_text", "missing_transport_receipt",
    "unsafe_resolved_url", "unexpected_http_status",
]
Warning = Literal[
    "invalid_canonical_candidate", "cross_host_canonical_candidate",
    "invalid_extractor_title", "invalid_extractor_publisher",
    "invalid_extractor_language", "invalid_extractor_date", "future_extractor_date",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ExtractorDate(FrozenModel):
    """A library-reported date, not a confirmed publisher date or event time."""

    value: str = Field(max_length=64)
    representation: Literal["calendar_day", "offset_timestamp"]
    basis: Literal["extractor_reported"] = "extractor_reported"
    source_precision: Literal["unknown"] = "unknown"

    @model_validator(mode="after")
    def _validate(self):
        if self.representation == "calendar_day":
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", self.value):
                raise ValueError("Expected calendar day")
            date.fromisoformat(self.value)
        else:
            _utc(self.value)
        return self


def _date_relation(discovery: NewsArticle, candidate: ExtractorDate | None):
    original = discovery.published_at
    if original is None or candidate is None:
        return "not_comparable"
    original_day = original.precision == "day"
    if original_day != (candidate.representation == "calendar_day"):
        return "not_comparable"
    if original_day:
        same = original.value == candidate.value
    else:
        same = _utc(original.value) == _utc(candidate.value)
    return "same_reported_value" if same else "different_reported_values"


class ArticleExtraction(FrozenModel):
    schema_version: Literal[1] = 1
    extraction_id: Digest | None = None
    discovery: NewsArticle
    method: Literal["existing_pinned_article_downloader"] = "existing_pinned_article_downloader"
    status: Literal["planned", "extracted", "unavailable", "rejected"]
    reason: Reason | None = None
    started_at: str | None = None
    completed_at: str | None = None
    content_level: Literal["headline_only", "extracted_text"] = "headline_only"
    resolved_url: str | None = None
    canonical_url_candidate: str | None = None
    extractor_title: str | None = None
    extractor_publisher: str | None = None
    extractor_language: str | None = None
    extractor_date: ExtractorDate | None = None
    date_relation: Literal["not_comparable", "same_reported_value", "different_reported_values"] = "not_comparable"
    body_sha256: Digest | None = None
    body_digest_policy: Literal["not_retained", "operator_permitted"] = "not_retained"
    warnings: tuple[Warning, ...] = Field(default=(), max_length=7)
    # A successful extraction is not a fact check or proof of publisher identity.
    claim_verification: Literal["not_performed"] = "not_performed"
    retry_automatically: Literal[False] = False

    @field_validator("started_at", "completed_at")
    @classmethod
    def _timestamp(cls, value):
        return _utc(value) if value is not None else None

    @field_validator("resolved_url", "canonical_url_candidate")
    @classmethod
    def _citation(cls, value):
        return _url(value) if value is not None else None

    @field_validator("extractor_title", "extractor_publisher", "extractor_language")
    @classmethod
    def _label(cls, value, info):
        return _text(value, 512 if info.field_name == "extractor_title" else 160) if value is not None else None

    @model_validator(mode="after")
    def _validate(self):
        derived = (
            self.resolved_url, self.canonical_url_candidate, self.extractor_title,
            self.extractor_publisher, self.extractor_language, self.extractor_date, self.body_sha256,
        )
        if self.status == "planned":
            if self.started_at is not None or self.completed_at is not None or self.reason is not None:
                raise ValueError("A plan has no execution evidence")
        else:
            if self.started_at is None or self.completed_at is None:
                raise ValueError("Attempt requires timestamps")
            if datetime.fromisoformat(self.completed_at) < datetime.fromisoformat(self.started_at):
                raise ValueError("Completion precedes attempt")
            if self.discovery.captured_at and datetime.fromisoformat(self.started_at) < datetime.fromisoformat(
                self.discovery.captured_at
            ):
                raise ValueError("Attempt precedes discovery capture")
        if self.status == "extracted":
            if self.content_level != "extracted_text" or self.reason is not None or not self.resolved_url:
                raise ValueError("Extraction lacks safe transport evidence")
        else:
            if any(x is not None for x in derived) or self.content_level != "headline_only" or self.warnings:
                raise ValueError("No extracted fields on a non-success outcome")
            if self.status != "planned" and self.reason is None:
                raise ValueError("Failed extraction requires a controlled reason")
        if (self.body_sha256 is not None) != (self.body_digest_policy == "operator_permitted"):
            raise ValueError("Body digest retention requires explicit permission")
        if len(self.warnings) != len(set(self.warnings)):
            raise ValueError("Duplicate warning")
        if self.date_relation != _date_relation(self.discovery, self.extractor_date):
            raise ValueError("Date comparison mismatch")
        if self.extractor_date and self.extractor_date.representation == "offset_timestamp":
            if datetime.fromisoformat(_utc(self.extractor_date.value)) > datetime.fromisoformat(self.completed_at):
                raise ValueError("Extractor date exceeds capture")
        cross_host = bool(self.canonical_url_candidate and self.resolved_url and
                          urlsplit(self.canonical_url_candidate).hostname != urlsplit(self.resolved_url).hostname)
        if cross_host != ("cross_host_canonical_candidate" in self.warnings):
            raise ValueError("Canonical host warning mismatch")
        expected = _digest(self.model_dump(mode="json", exclude={"extraction_id"}))
        if self.extraction_id not in (None, expected):
            raise ValueError("Extraction identity mismatch")
        object.__setattr__(self, "extraction_id", expected)
        return self


def _candidate_url(value, warnings):
    if value is None or value == "":
        return None
    try:
        return _url(value)
    except ValueError:
        warnings.append("invalid_canonical_candidate")
        return None


def _candidate_text(value, maximum, warning, warnings):
    if value is None or value == "":
        return None
    try:
        if not isinstance(value, str):
            raise ValueError("Invalid extracted label")
        return _text(value.strip(), maximum)
    except ValueError:
        warnings.append(warning)
        return None


def _candidate_date(value, completed_at, warnings):
    if value is None or value == "":
        return None
    try:
        if isinstance(value, datetime):
            # A naive parser timestamp does not establish a timezone.
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Unknown source offset")
            raw = value.isoformat()
        elif isinstance(value, date):
            raw = value.isoformat()
        elif isinstance(value, str):
            raw = value
        else:
            raise ValueError("Unknown date representation")
        candidate = ExtractorDate(
            value=raw, representation="calendar_day" if len(raw) == 10 else "offset_timestamp",
        )
        if candidate.representation == "offset_timestamp" and datetime.fromisoformat(
            _utc(candidate.value)
        ) > datetime.fromisoformat(completed_at):
            warnings.append("future_extractor_date")
            return None
        return candidate
    except (ValueError, TypeError, OverflowError):
        warnings.append("invalid_extractor_date")
        return None


def _failed(discovery, started, completed, status, reason):
    return ArticleExtraction(
        discovery=discovery, status=status, reason=reason, started_at=started, completed_at=completed,
    )


def _project(discovery, article, started, completed, permit_body_digest):
    if article is None:
        return _failed(discovery, started, completed, "unavailable", "download_unavailable")
    receipt = getattr(article, "_trendpulse_transport_receipt", None)
    if not isinstance(receipt, tuple) or len(receipt) != 2 or type(receipt[0]) is not int:
        return _failed(discovery, started, completed, "rejected", "missing_transport_receipt")
    status, resolved = receipt
    if status != 200:
        return _failed(discovery, started, completed, "rejected", "unexpected_http_status")
    try:
        resolved = _url(resolved)
        if resolved.startswith("https://news.google.com/"):
            raise ValueError("Aggregator response is not publisher extraction")
    except ValueError:
        return _failed(discovery, started, completed, "rejected", "unsafe_resolved_url")

    from mcp_trendpulse import news

    body = getattr(article, "text", None)
    if (not isinstance(body, str) or not body.strip() or len(body) > _MAX_BODY_BYTES
            or news._is_unusable_article_page(article)):
        return _failed(discovery, started, completed, "rejected", "invalid_extracted_text")
    try:
        raw = body.encode("utf-8", "strict")
        if len(raw) > _MAX_BODY_BYTES:
            raise ValueError("Extracted text exceeds limit")
    except ValueError:
        return _failed(discovery, started, completed, "rejected", "invalid_extracted_text")
    warnings = []
    canonical = _candidate_url(getattr(article, "canonical_link", None), warnings)
    if canonical and urlsplit(canonical).hostname != urlsplit(resolved).hostname:
        warnings.append("cross_host_canonical_candidate")
    title = _candidate_text(getattr(article, "title", None), 512, "invalid_extractor_title", warnings)
    publisher = _candidate_text(getattr(article, "meta_site_name", None), 160, "invalid_extractor_publisher", warnings)
    language = _candidate_text(getattr(article, "meta_lang", None), 160, "invalid_extractor_language", warnings)
    published = _candidate_date(getattr(article, "publish_date", None), completed, warnings)
    return ArticleExtraction(
        discovery=discovery, status="extracted", started_at=started, completed_at=completed,
        content_level="extracted_text", resolved_url=resolved, canonical_url_candidate=canonical,
        extractor_title=title, extractor_publisher=publisher, extractor_language=language,
        extractor_date=published, date_relation=_date_relation(discovery, published),
        body_sha256=hashlib.sha256(raw).hexdigest() if permit_body_digest else None,
        body_digest_policy="operator_permitted" if permit_body_digest else "not_retained",
        warnings=tuple(warnings),
    )


async def extract_article(discovery: NewsArticle, *, execute: bool = False,
                          permit_body_digest: bool = False) -> ArticleExtraction:
    """One explicit bounded downloader operation; always retain discovery evidence.

    Canonicals are candidates, never fetch targets. No article text, HTML, summary,
    image or arbitrary metadata is returned or persisted by this module.
    An optional digest requires the caller to establish the relevant rights.
    """
    if not isinstance(discovery, NewsArticle) or type(execute) is not bool or type(permit_body_digest) is not bool:
        raise ValueError("Invalid extraction input")
    # Revalidate even an existing instance (e.g. a model_copy with unsafe updates).
    discovery = NewsArticle.model_validate_json(discovery.model_dump_json())
    if not execute:
        return ArticleExtraction(discovery=discovery, status="planned")
    started = _now().isoformat()
    if discovery.captured_at and datetime.fromisoformat(discovery.captured_at) > datetime.fromisoformat(started):
        raise ValueError("Discovery capture is in the future")

    from mcp_trendpulse import news

    try:
        article = await news.download_article(discovery.reported_url)
    except TimeoutError:
        return _failed(discovery, started, _now().isoformat(), "unavailable", "download_timeout")
    except ValueError:
        return _failed(discovery, started, _now().isoformat(), "rejected", "download_rejected")
    except Exception:
        # Preserve the original observation; never expose raw transport errors.
        return _failed(discovery, started, _now().isoformat(), "unavailable", "download_failed")
    completed = _now().isoformat()
    return _project(discovery, article, started, completed, permit_body_digest)
