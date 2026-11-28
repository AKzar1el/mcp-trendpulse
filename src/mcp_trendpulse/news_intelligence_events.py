"""V4.05: deterministic, bounded, offline event candidates.

The unit is a source-grounded headline mention, not a verified event. Complete-
link grouping prevents transitive similarity merges. Explicit annotations are
caller-supplied hypotheses; no network, translation service or identity oracle.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from itertools import combinations
from typing import Literal

from pydantic import Field, field_validator, model_validator
from rapidfuzz import fuzz

from mcp_trendpulse.news_intelligence_dedup import MAX_OBSERVATIONS, _date_distance, _markers, _normalized
from mcp_trendpulse.news_intelligence_schema import Digest, FrozenModel, NewsArticle, TimeEvidence, _digest, _text, _utc

ALGORITHM = "news_event_candidates_v1"
MAX_MENTIONS = 100
MAX_HINTS_PER_ARTICLE = 4
MAX_EVENT_MEMBERS = 20
_ACTIONS = {
    "announce": frozenset({"announces", "announced", "announce", "kündigt", "ankündigung", "meldet", "napoveduje", "napovedal", "napovedala", "objavlja", "objavil", "objavila"}),
    "launch": frozenset({"launches", "launched", "launch", "startet", "gestartet", "lanciert", "začenja", "začel", "začela", "predstavlja", "predstavil", "predstavila"}),
    "approve": frozenset({"approves", "approved", "approve", "genehmigt", "billigt", "odobri", "odobril", "odobrila"}),
    "reject": frozenset({"rejects", "rejected", "reject", "lehnt", "abgelehnt", "zavrača", "zavrnil", "zavrnila"}),
    "report": frozenset({"reports", "reported", "report", "berichtet", "poroča", "poročal", "poročala"}),
    "open": frozenset({"opens", "opened", "eröffnet", "öffnet", "odpira", "odprl", "odprla"}),
    "close": frozenset({"closes", "closed", "schließt", "geschlossen", "zapira", "zaprl", "zaprla"}),
}
Action = Literal["announce", "launch", "approve", "reject", "report", "open", "close", "unknown"]
Basis = Literal["exact_headline_and_report_time", "anchored_event_metadata"]
_WARNINGS = ("candidate_not_verified", "source_independence_unknown")
_DATE = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")
_NEGATIVE = frozenset({"no", "not", "never", "without", "kein", "keine", "nicht", "ohne", "nie", "nein", "ne", "ni", "niso", "brez", "nikoli"})


def _fold(value):
    return unicodedata.normalize("NFC", value).casefold()


def _contains(span, label):
    return bool(re.search(r"(?<!\w)" + re.escape(_fold(label)) + r"(?!\w)", _fold(span)))


def _action(span):
    words = set(re.findall(r"\w+", _fold(span)))
    found = [name for name, terms in _ACTIONS.items() if words & terms]
    return found[0] if len(found) == 1 else "unknown"


def _event_day(span):
    days = set()
    for raw in _DATE.findall(span):
        try:
            days.add(date.fromisoformat(raw).isoformat())
        except ValueError:
            return None
    return next(iter(days)) if len(days) == 1 else None


def _labels(values, span):
    if len({_fold(x) for x in values}) != len(values):
        raise ValueError("Duplicate annotation labels")
    for value in values:
        _text(value, 120)
        if not _contains(span, value):
            raise ValueError("Annotation is not anchored in the source span")
    return tuple(sorted(values, key=lambda x: (_fold(x), x)))


def _topics(values, span, entities, locations):
    values = _labels(values, span)
    reserved = {_fold(x) for x in (*entities, *locations)}
    if any(_fold(x) in reserved or _DATE.fullmatch(x) or _action(x) != "unknown" for x in values):
        raise ValueError("Topic must be a separate source-anchored label")
    return values


class EventHint(FrozenModel):
    """Optional caller annotations grounded in one exact headline span."""

    observation_id: Digest
    span: str = Field(min_length=1, max_length=512)
    entities: tuple[str, ...] = Field(default=(), max_length=16)
    locations: tuple[str, ...] = Field(default=(), max_length=8)
    topics: tuple[str, ...] = Field(default=(), max_length=8)

    @model_validator(mode="after")
    def _check(self):
        _text(self.span, 512)
        object.__setattr__(self, "entities", _labels(self.entities, self.span))
        object.__setattr__(self, "locations", _labels(self.locations, self.span))
        object.__setattr__(self, "topics", _topics(self.topics, self.span, self.entities, self.locations))
        return self


class EventMention(FrozenModel):
    mention_id: Digest | None = None
    observation_id: Digest
    span: str = Field(min_length=1, max_length=512)
    action: Action
    entities: tuple[str, ...] = Field(default=(), max_length=16)
    locations: tuple[str, ...] = Field(default=(), max_length=8)
    topics: tuple[str, ...] = Field(default=(), max_length=8)
    annotation_basis: Literal["headline_rule", "caller_anchored_hint"]
    event_day_candidate: str | None = None
    captured_at: str | None = None
    reported_publication: TimeEvidence | None = None
    provider_seen_at: TimeEvidence | None = None

    @field_validator("captured_at")
    @classmethod
    def _capture(cls, value):
        return _utc(value) if value is not None else None

    @model_validator(mode="after")
    def _check(self):
        _text(self.span, 512)
        if self.action != _action(self.span) or self.event_day_candidate != _event_day(self.span):
            raise ValueError("Mention features must match the source span")
        if self.annotation_basis == "headline_rule" and (self.entities or self.locations or self.topics):
            raise ValueError("Automatic rules do not assert entity or location identity")
        object.__setattr__(self, "entities", _labels(self.entities, self.span))
        object.__setattr__(self, "locations", _labels(self.locations, self.span))
        object.__setattr__(self, "topics", _topics(self.topics, self.span, self.entities, self.locations))
        expected = _digest([ALGORITHM, self.observation_id, self.span])
        if self.mention_id not in (None, expected):
            raise ValueError("Mention identity mismatch")
        object.__setattr__(self, "mention_id", expected)
        return self


class EventPair(FrozenModel):
    left: Digest
    right: Digest
    basis: Basis
    headline_ratio: float = Field(ge=0, le=100)
    comparable_report_distance_seconds: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _check(self):
        if self.left >= self.right:
            raise ValueError("Pair order must be canonical")
        return self


class EventCandidate(FrozenModel):
    schema_version: Literal[1] = 1
    algorithm_version: Literal["news_event_candidates_v1"] = ALGORITHM
    event_id: Digest | None = None
    revision_id: Digest | None = None
    seed_mention_ids: tuple[Digest, ...] = Field(min_length=1, max_length=MAX_EVENT_MEMBERS)
    origin_revision_ids: tuple[Digest, ...] = Field(default=(), max_length=MAX_MENTIONS)
    previous_revision_ids: tuple[Digest, ...] = Field(default=(), max_length=MAX_MENTIONS)
    as_of: str
    members: tuple[EventMention, ...] = Field(min_length=1, max_length=MAX_EVENT_MEMBERS)
    pair_evidence: tuple[EventPair, ...] = Field(default=(), max_length=190)
    occurrence_status: Literal["unknown"] = "unknown"

    @field_validator("as_of")
    @classmethod
    def _cutoff(cls, value):
        return _utc(value)

    @model_validator(mode="after")
    def _check(self):
        ids = tuple(m.mention_id for m in self.members)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("Members must be unique and sorted")
        for values in (self.seed_mention_ids, self.origin_revision_ids, self.previous_revision_ids):
            if values != tuple(sorted(set(values))):
                raise ValueError("Identity references must be unique and sorted")
        if not set(self.seed_mention_ids).issubset(ids):
            raise ValueError("Seed mentions must remain in the current event")
        if len({m.observation_id for m in self.members}) != len(ids):
            raise ValueError("One event cannot group separate mentions of the same observation")
        expected_pairs = tuple(combinations(ids, 2))
        if tuple((p.left, p.right) for p in self.pair_evidence) != expected_pairs:
            raise ValueError("Every pair needs direct membership evidence")
        cutoff = datetime.fromisoformat(self.as_of)
        for m in self.members:
            if m.captured_at and datetime.fromisoformat(m.captured_at) > cutoff:
                raise ValueError("Observation after cutoff")
            for stamp in (m.reported_publication, m.provider_seen_at):
                if stamp and stamp.precision != "day" and datetime.fromisoformat(_utc(stamp.value)) > cutoff:
                    raise ValueError("Reported timestamp after cutoff")
        event_id = _digest([ALGORITHM, self.seed_mention_ids, self.origin_revision_ids])
        if self.event_id not in (None, event_id):
            raise ValueError("Event identity mismatch")
        object.__setattr__(self, "event_id", event_id)
        revision_id = _digest(self.model_dump(mode="json", exclude={"revision_id"}))
        if self.revision_id not in (None, revision_id):
            raise ValueError("Event revision mismatch")
        object.__setattr__(self, "revision_id", revision_id)
        return self


def _validate_list(items, expected, maximum):
    if not isinstance(items, (list, tuple)) or len(items) > maximum:
        raise ValueError("Input collection exceeds the bounded scope")
    clean = []
    for item in items:
        if not isinstance(item, expected):
            raise ValueError("Expected a typed input record")
        try:
            clean.append(expected.model_validate_json(item.model_dump_json()))
        except (ValueError, TypeError):
            raise ValueError("Invalid input record") from None
    return clean


def _make_mentions(rows, hints):
    by_row = {}
    for hint in hints:
        if hint.observation_id not in rows:
            raise ValueError("Hint refers to an unknown observation")
        by_row.setdefault(hint.observation_id, []).append(hint)
    mentions = []
    for oid, row in rows.items():
        supplied = by_row.get(oid, [])
        if len(supplied) > MAX_HINTS_PER_ARTICLE:
            raise ValueError("Too many mentions for one observation")
        spans = []
        for hint in supplied:
            if row.title.count(hint.span) != 1:
                raise ValueError("Hint span must occur exactly once in the source headline")
            start = row.title.index(hint.span)
            end = start + len(hint.span)
            if any(start < e and s < end for s, e in spans):
                raise ValueError("Overlapping mention spans")
            spans.append((start, end))
        if not supplied:
            supplied = [EventHint(observation_id=oid, span=row.title)]
        for hint in supplied:
            mentions.append(EventMention(
                observation_id=oid, span=hint.span, action=_action(hint.span),
                entities=hint.entities, locations=hint.locations, topics=hint.topics,
                annotation_basis="caller_anchored_hint" if oid in by_row else "headline_rule",
                event_day_candidate=_event_day(hint.span), captured_at=row.captured_at,
                reported_publication=row.published_at, provider_seen_at=row.provider_seen_at,
            ))
    if len(mentions) > MAX_MENTIONS:
        raise ValueError("Mention budget exceeded")
    return sorted(mentions, key=lambda m: m.mention_id)


def _pair(a, b, rows):
    if a.observation_id == b.observation_id or a.action == "unknown" or a.action != b.action:
        return None
    left, right = rows[a.observation_id], rows[b.observation_id]
    ln, rn = _normalized(a.span), _normalized(b.span)
    if min(len(ln), len(rn)) < 30 or min(len(ln.split()), len(rn.split())) < 6:
        return None
    lm, rm = _markers(a.span), _markers(b.span)
    if ("?" in a.span) != ("?" in b.span) or lm != rm:
        return None
    # A known explicit date conflict is disqualifying. Multiple dates are
    # ambiguous and never provide a positive date anchor.
    if len(set(_DATE.findall(a.span))) > 1 or len(set(_DATE.findall(b.span))) > 1:
        return None
    if a.event_day_candidate and b.event_day_candidate and a.event_day_candidate != b.event_day_candidate:
        return None
    entities_a, entities_b = {_fold(x) for x in a.entities}, {_fold(x) for x in b.entities}
    places_a, places_b = {_fold(x) for x in a.locations}, {_fold(x) for x in b.locations}
    topics_a, topics_b = {_fold(x) for x in a.topics}, {_fold(x) for x in b.topics}
    if ((entities_a and entities_b and entities_a != entities_b)
            or (places_a and places_b and places_a != places_b)
            or (topics_a and topics_b and topics_a != topics_b)):
        return None
    distance = _date_distance(left, right)
    if distance is not None and distance > 24 * 3600:
        return None
    explicit_day = bool(a.event_day_candidate and a.event_day_candidate == b.event_day_candidate)
    if distance is None and not explicit_day:
        return None
    lang_a = _fold(left.reported_language) if left.reported_language else None
    lang_b = _fold(right.reported_language) if right.reported_language else None
    cross_language = bool(lang_a and lang_b and lang_a != lang_b)
    ratio = float(fuzz.ratio(ln, rn))
    basis = None
    if ln == rn and not cross_language:
        basis = "exact_headline_and_report_time"
    elif (explicit_day and entities_a and entities_a == entities_b and places_a and places_a == places_b
          and topics_a and topics_a == topics_b):
        # Cross-language requires explicit matching literal entity/place anchors,
        # date, action and a separate literal topic. No translated-name inference or unsupported language
        # equivalence. A negative statement remains separate.
        if cross_language:
            if any(x in _NEGATIVE or x.endswith("n't") for x in lm[1] + rm[1]):
                return None
            basis = "anchored_event_metadata"
        else:
            tokens_a, tokens_b = set(ln.split()), set(rn.split())
            if len(tokens_a & tokens_b) / len(tokens_a | tokens_b) >= 0.50:
                basis = "anchored_event_metadata"
    if basis is None:
        return None
    return EventPair(left=a.mention_id, right=b.mention_id, basis=basis,
                     headline_ratio=round(ratio, 3), comparable_report_distance_seconds=distance)


def _coverage(event):
    timeline = sorted(event.members, key=lambda m: (m.captured_at is None, m.captured_at or "", m.mention_id))
    known = [m.captured_at for m in timeline if m.captured_at is not None]
    days = sorted({m.event_day_candidate for m in timeline if m.event_day_candidate is not None})
    return {
        "event_id": event.event_id, "label": event.members[0].span, "label_basis": "source_headline_span",
        "event_day_candidate": days[0] if len(days) == 1 else None,
        "event_day_refs": [m.mention_id for m in timeline if len(days) == 1 and m.event_day_candidate == days[0]],
        "earliest_supplied_capture": min(known) if known else None,
        "latest_supplied_capture": max(known) if known else None,
        "unknown_capture_count": sum(m.captured_at is None for m in timeline),
        "original_reporting": "unknown",
        "timeline": [{"mention_id": m.mention_id, "observation_id": m.observation_id,
                      "captured_at": m.captured_at,
                      "reported_publication": m.reported_publication.model_dump(mode="json") if m.reported_publication else None,
                      "provider_seen_at": m.provider_seen_at.model_dump(mode="json") if m.provider_seen_at else None}
                     for m in timeline],
        "warnings": list(_WARNINGS) + (["capture_time_unknown"] if len(known) != len(timeline) else []),
    }


def cluster_news_events(observations, *, as_of, hints=(), previous=()):
    """Return candidates and explicit predecessor/successor relationships.

    A caller supplies the historical snapshot and optional earlier revisions.
    No claim of persistence or authenticated origin. Unobserved prior events
    are retained in the lineage report; they are never called deleted.
    """
    cutoff = _utc(as_of)
    end = datetime.fromisoformat(cutoff)
    validated = _validate_list(observations, NewsArticle, MAX_OBSERVATIONS)
    rows = {r.observation_id: r for r in validated}
    for row in rows.values():
        if row.captured_at and datetime.fromisoformat(row.captured_at) > end:
            raise ValueError("Observation after cutoff")
        for stamp in (row.published_at, row.provider_seen_at):
            if stamp and stamp.precision != "day" and datetime.fromisoformat(_utc(stamp.value)) > end:
                raise ValueError("Reported timestamp after cutoff")
    hints = _validate_list(hints, EventHint, MAX_MENTIONS)
    prev = _validate_list(previous, EventCandidate, MAX_MENTIONS)
    prior_members = {}
    prior_ids = set()
    for event in prev:
        if event.event_id in prior_ids or datetime.fromisoformat(event.as_of) > end:
            raise ValueError("Invalid previous event snapshot")
        prior_ids.add(event.event_id)
        for member in event.members:
            if member.mention_id in prior_members:
                raise ValueError("Previous events must have disjoint mention membership")
            prior_members[member.mention_id] = event
    if len(prior_members) > MAX_MENTIONS:
        raise ValueError("Previous snapshot exceeds mention budget")
    mentions = _make_mentions(rows, hints)
    pairs = {}
    for a, b in combinations(mentions, 2):
        relation = _pair(a, b, rows)
        if relation is not None:
            pairs[(a.mention_id, b.mention_id)] = relation

    groups = []
    ambiguous = set()
    for mention in mentions:
        possible = [group for group in groups if len(group) < MAX_EVENT_MEMBERS and all(
            (other.mention_id, mention.mention_id) in pairs for other in group
        )]
        if len(possible) == 1:
            possible[0].append(mention)
        else:
            if len(possible) > 1:
                ambiguous.add(mention.mention_id)
            groups.append([mention])

    overlaps = []
    successors = {event.event_id: [] for event in prev}
    for i, group in enumerate(groups):
        matches = {prior_members[m.mention_id].event_id: prior_members[m.mention_id]
                   for m in group if m.mention_id in prior_members}
        overlaps.append(matches)
        for eid in matches:
            successors[eid].append(i)

    events = []
    for i, group in enumerate(groups):
        ids = tuple(m.mention_id for m in group)
        predecessors = sorted(overlaps[i].values(), key=lambda event: event.event_id)
        previous_revisions = tuple(sorted(event.revision_id for event in predecessors))
        old = predecessors[0] if len(predecessors) == 1 else None
        reuse = (old is not None and len(successors[old.event_id]) == 1
                 and {m.mention_id for m in old.members}.issubset(ids))
        member_pairs = tuple(pairs[key] for key in combinations(ids, 2))
        # Replaying an identical as-of snapshot must not manufacture a revision.
        if reuse and old.as_of == cutoff and old.members == tuple(group) and old.pair_evidence == member_pairs:
            events.append(old)
            continue
        event = EventCandidate(
            seed_mention_ids=old.seed_mention_ids if reuse else ids,
            origin_revision_ids=old.origin_revision_ids if reuse else previous_revisions,
            previous_revision_ids=previous_revisions,
            as_of=cutoff, members=tuple(group),
            pair_evidence=member_pairs,
        )
        events.append(event)

    lineage = []
    for old in sorted(prev, key=lambda event: event.event_id):
        new = [events[i] for i in successors[old.event_id]]
        if not new:
            state = "not_in_current_snapshot"
        elif len(new) > 1:
            state = "split_candidate"
        elif new[0].event_id == old.event_id:
            state = "continued"
        elif len(overlaps[successors[old.event_id][0]]) > 1:
            state = "merge_candidate"
        else:
            state = "membership_changed"
        lineage.append({"previous_event_id": old.event_id, "previous_revision_id": old.revision_id,
                        "state": state, "successors": sorted(e.event_id for e in new)})
    return {
        "schema_version": 1, "algorithm_version": ALGORITHM, "as_of": cutoff,
        "network_performed": False, "event_identity_verified": False, "independent_sources_counted": False,
        "input_observation_count": len(validated), "unique_observation_count": len(rows),
        "mention_count": len(mentions), "candidate_count": len(events),
        "pair_comparisons": len(mentions) * (len(mentions) - 1) // 2,
        "compatible_pair_count": len(pairs), "ambiguous_mentions": sorted(ambiguous),
        "observations": [rows[key].model_dump(mode="json") for key in sorted(rows)],
        "events": [e.model_dump(mode="json") for e in events],
        "coverage": [_coverage(e) for e in events], "lineage": lineage,
        "limitations": [
            "Event candidates are not verified occurrences or independently corroborated facts.",
            "Automatic grouping is deliberately narrow; anchored hints are caller-supplied hypotheses.",
            "Publication and provider-seen time are not occurrence time; earliest supplied capture is not first reporting.",
            "No persistent history, semantic translation, identity resolution or real-world accuracy claim.",
        ],
    }
