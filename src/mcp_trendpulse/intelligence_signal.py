"""Typed, offline-only evidence contract for global trends and keyword signals.

This is a schema, not a provider, a search-volume estimator or a network client.
Source adapters in later mjau milestones explicitly map their bounded responses
into this contract. Missing, not-measured and zero are distinct states.
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime, timezone
from typing import Literal
from urllib.parse import parse_qsl, urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MetricType = Literal[
    "google_trends_normalized_interest",
    "google_trending_traffic_bucket",
    "google_bigquery_rank",
    "bing_keyword_impressions",
    "wikimedia_pageviews",
    "hacker_news_story_mentions",
    "github_issue_mentions",
    "npm_package_downloads",
    "pypi_package_downloads",
    "stackexchange_question_mentions",
    "news_mention_count",
    "generated_keyword_candidate",
]
MetricUnit = Literal[
    "relative_index_0_100", "approximate_search_bucket", "rank",
    "impressions", "pageviews", "stories", "issues", "downloads",
    "questions", "mentions", "none",
]
CoverageStatus = Literal["observed", "partial", "unavailable", "no_data", "not_measured"]
SourceMethod = Literal[
    "official_api", "public_rss", "public_dataset", "community_provider",
    "public_api", "derived", "operator_supplied",
]

# The source unit and evidence class are intrinsic to a metric.
# Different classes must never be summed or treated as a common demand score.
METRIC_DEFINITIONS: dict[str, tuple[str, str]] = {
    "google_trends_normalized_interest": ("relative_index_0_100", "search_interest"),
    "google_trending_traffic_bucket": ("approximate_search_bucket", "search_interest"),
    "google_bigquery_rank": ("rank", "search_interest"),
    "bing_keyword_impressions": ("impressions", "bing_search_volume"),
    "wikimedia_pageviews": ("pageviews", "public_attention"),
    "hacker_news_story_mentions": ("stories", "developer_discussion"),
    "github_issue_mentions": ("issues", "developer_discussion"),
    "npm_package_downloads": ("downloads", "package_adoption_proxy"),
    "pypi_package_downloads": ("downloads", "package_adoption_proxy"),
    "stackexchange_question_mentions": ("questions", "developer_discussion"),
    "news_mention_count": ("mentions", "news_attention"),
    "generated_keyword_candidate": ("none", "keyword_hypothesis"),
}
_COUNT_UNITS = {"rank", "impressions", "pageviews", "stories", "issues",
                "downloads", "questions", "mentions"}
_SECRET_QUERY_KEYS = {
    "key", "apikey", "api_key", "token", "access_token", "auth",
    "authorization", "password", "secret", "client_secret",
    "subscription-key", "subscription_key",
}


class SignalPeriod(BaseModel):
    """Inclusive source observation window; no inferred hourly granularity."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    start_date: date
    end_date: date
    granularity: Literal["point_in_time", "daily", "weekly", "monthly"]

    @model_validator(mode="after")
    def validate_window(self) -> SignalPeriod:
        if self.start_date > self.end_date:
            raise ValueError("Signal period start must not exceed end")
        return self


class SignalProvenance(BaseModel):
    """Source-observation metadata, not a free-form provider payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    method: SourceMethod
    source_record_id: str | None = Field(default=None, max_length=120)
    sampling_basis: str = Field(min_length=1, max_length=160)
    is_observed_search_query: bool = False

    @field_validator("source_record_id", "sampling_basis")
    @classmethod
    def reject_control_characters(cls, value: str | None) -> str | None:
        if value is not None and (any(ord(c) < 32 or ord(c) == 127 for c in value)
                                  or value.strip() != value):
            raise ValueError("Signal provenance must use bounded printable text")
        return value


class TrendSignal(BaseModel):
    """A single country/language-scoped, sourced observation or hypothesis.

    A null country means the source scope is not specified; it does not assert
    worldwide coverage. A null value is unknown/unmeasured, never numeric zero.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    source_id: str = Field(min_length=2, max_length=60, pattern=r"^[a-z][a-z0-9_]+$")
    source_url: str = Field(min_length=10, max_length=600)
    observed_at: datetime
    published_at: datetime | None = None
    country: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    language: str | None = Field(
        default=None, pattern=r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8}){0,2}$",
    )
    raw_term: str = Field(min_length=1, max_length=180)
    normalized_term: str = Field(min_length=1, max_length=180)
    metric_type: MetricType
    metric_unit: MetricUnit
    period: SignalPeriod
    value: float | None = None
    value_label: str | None = Field(default=None, min_length=1, max_length=48)
    sampling_scope: str = Field(min_length=1, max_length=180)
    coverage_status: CoverageStatus
    provenance: SignalProvenance

    @field_validator("source_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        try:
            parsed = urlsplit(value)
            query_keys = {k.casefold() for k, _ in parse_qsl(
                parsed.query, keep_blank_values=True,
            )}
            safe = (
                parsed.scheme == "https"
                and bool(parsed.hostname)
                and not parsed.username and not parsed.password
                and not parsed.fragment
                and not (_SECRET_QUERY_KEYS & query_keys)
            )
        except ValueError:
            safe = False
        if not safe:
            raise ValueError("Source URL must be a public HTTPS reference without credentials")
        return value

    @field_validator("raw_term", "normalized_term", "sampling_scope", "value_label")
    @classmethod
    def validate_printable(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or value.strip() != value
                                  or any(ord(c) < 32 or ord(c) == 127 for c in value)):
            raise ValueError("Signal text must be trimmed printable text")
        return value

    @field_validator("observed_at", "published_at")
    @classmethod
    def normalize_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Signal timestamps require explicit time zones")
            return value.astimezone(timezone.utc)
        return value

    @field_validator("value", mode="before")
    @classmethod
    def validate_numeric_input(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (float, int)):
            raise ValueError("Numeric signals require a finite numeric value, not text")
        if not math.isfinite(value) or value < 0:
            raise ValueError("Signal value must be finite and non-negative")
        return value

    @model_validator(mode="after")
    def validate_semantics(self) -> TrendSignal:
        expected_unit = METRIC_DEFINITIONS[self.metric_type][0]
        if self.metric_unit != expected_unit:
            raise ValueError("Metric unit does not match the named metric type")
        if self.published_at and self.published_at > self.observed_at:
            raise ValueError("Published time cannot follow observed time")

        if self.metric_type == "generated_keyword_candidate":
            if (self.coverage_status != "not_measured"
                    or self.value is not None or self.value_label is not None
                    or self.provenance.is_observed_search_query
                    or self.provenance.method != "derived"):
                raise ValueError("Generated keywords must remain unmeasured hypotheses")
            return self

        if self.coverage_status == "not_measured":
            raise ValueError("Source metrics must distinguish unavailable from observed")
        if self.coverage_status in {"unavailable", "no_data"}:
            if self.value is not None or self.value_label is not None:
                raise ValueError("Missing-source signals must not carry measurements")
            return self

        if self.metric_type == "google_trending_traffic_bucket":
            if self.value is not None or self.value_label is None:
                raise ValueError("Traffic buckets require a source label, never exact volume")
            return self

        if self.value is None or self.value_label is not None:
            raise ValueError("Observed numeric signals require only numeric values")
        if self.metric_unit == "relative_index_0_100" and self.value > 100:
            raise ValueError("Normalized interest must be within 0..100")
        if self.metric_unit in _COUNT_UNITS and not self.value.is_integer():
            raise ValueError("Counts and ranks must be whole numbers")
        if self.metric_unit == "rank" and self.value == 0:
            raise ValueError("Rank must start at one")
        return self


def signal_contract_spec() -> dict[str, object]:
    """Lightweight, no-network CLI discoverability of the stable schema."""
    return {
        "schema_version": 1,
        "status": "offline_schema_only",
        "network_performed": False,
        "new_provider_added": False,
        "site_property_required": False,
        "market_scope_note": "Country null is unknown scope, not worldwide search coverage.",
        "metric_comparability_note": (
            "Never sum source-specific indices, pageviews, issue counts, "
            "downloads, rank or Bing impressions as one volume."
        ),
        "missingness_note": "Unavailable or unmeasured values are null, not zero.",
        "metric_types": {
            metric: {"unit": unit, "evidence_class": evidence_class}
            for metric, (unit, evidence_class) in METRIC_DEFINITIONS.items()
        },
        "schema": TrendSignal.model_json_schema(),
    }
