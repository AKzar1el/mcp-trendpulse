"""Offline synthetic regressions for conservative event candidates."""
import pytest

from mcp_trendpulse.news_intelligence_events import (
    EventCandidate, EventHint, cluster_news_events,
)
from mcp_trendpulse.news_intelligence_schema import NewsArticle, TimeEvidence

CUT = "2026-11-28T12:00:00Z"
HEAD = "Researchers announce a new renewable energy project for regional communities"


def row(key, title=HEAD, *, seen="2026-11-28T10:00:00Z", capture=CUT, language="English",
        country=None):
    return NewsArticle(
        discovery_provider="gdelt_doc", link_type="publisher_candidate",
        reported_url=f"https://example.org/news/{key}", title=title,
        reported_language=language, reported_source_country=country,
        provider_seen_at=TimeEvidence(value=seen, precision="second", basis="provider_seen") if seen else None,
        captured_at=capture, capture_mode="legacy_import",
    )


def run(rows, **kwargs):
    return cluster_news_events(rows, as_of=CUT, **kwargs)


def prior(result):
    import json
    return [EventCandidate.model_validate_json(json.dumps(e)) for e in result["events"]]


def hint(r, span=None, entities=(), locations=()):
    return EventHint(observation_id=r.observation_id, span=span or r.title,
                     entities=entities, locations=locations)


def test_exact_headlines_group_with_direct_pairs_and_no_identity_claim():
    a, b, c = row("a"), row("b", HEAD.upper()), row("c")
    out = run([c, a, b, a])
    assert out["input_observation_count"] == 4 and out["unique_observation_count"] == 3
    assert out["candidate_count"] == 1 and out["mention_count"] == 3
    event = out["events"][0]
    assert len(event["pair_evidence"]) == 3
    assert event["occurrence_status"] == "unknown" and not out["event_identity_verified"]
    assert out["coverage"][0]["event_day_candidate"] is None
    assert out["coverage"][0]["original_reporting"] == "unknown"
    assert out["coverage"][0]["earliest_supplied_capture"].startswith("2026-11-28")
    assert run([a, b, c, a]) == out
    assert prior(out)[0].event_id == event["event_id"]


@pytest.mark.parametrize("title", [
    "Researchers reject a new renewable energy project for regional communities",
    "Researchers announce a new renewable energy project for distant communities",
    "Researchers announce a new renewable energy project for regional communities?",
    "Researchers announce a new renewable energy project for regional communities and report another result",
])
def test_similar_but_distinct_headlines_not_automatically_merged(title):
    # A question is deliberately not treated as equivalent to an assertion.
    assert run([row("a"), row("b", title)])["candidate_count"] == 2


@pytest.mark.parametrize("other", [
    {"seen": "2026-11-25T10:00:00Z"}, {"seen": None},
    {"language": "German"}, {"title": "Market update"},
])
def test_unknown_or_incompatible_report_time_and_language(other):
    b = row("b", **other)
    assert run([row("a"), b])["candidate_count"] == 2


def test_provider_seen_is_not_publication_or_occurrence():
    a = row("a", country="United States")
    b = NewsArticle(
        discovery_provider="google_news_rss", link_type="google_news_rss",
        reported_url="https://news.google.com/rss/articles/abc", title=HEAD,
        published_at=TimeEvidence(value="2026-11-28T10:00:00Z", precision="second", basis="legacy_normalized"),
        captured_at=CUT, capture_mode="legacy_import",
    )
    out = run([a, b])
    assert out["candidate_count"] == 2
    assert all(x["event_day_candidate"] is None for x in out["coverage"])
    assert not any(m["locations"] for e in out["events"] for m in e["members"])


def test_anchored_multilingual_candidates_are_not_translated_identity():
    a = row("a", "Acme announces a research facility in Ljubljana on 2026-11-28", language="English")
    b = row("b", "Acme meldet ein neues Forschungszentrum in Ljubljana am 2026-11-28", language="German")
    c = row("c", "Acme napoveduje novo raziskovalno središče v Ljubljana dne 2026-11-28", language="Slovenian")
    hints = [hint(x, entities=("Acme",), locations=("Ljubljana",)) for x in (a, b, c)]
    out = run([a, b, c], hints=hints)
    assert out["candidate_count"] == 1
    assert {p["basis"] for p in out["events"][0]["pair_evidence"]} == {"anchored_event_metadata"}
    assert out["coverage"][0]["event_day_candidate"] == "2026-11-28"
    assert len(out["coverage"][0]["event_day_refs"]) == 3
    assert run([a, b, c])["candidate_count"] == 3


def test_different_event_locations_dates_and_actors_stay_separate():
    a = row("a", "Acme announces a research facility in Ljubljana on 2026-11-28")
    for title, ent, place in (
        ("Acme announces a research facility in Maribor on 2026-11-28", "Acme", "Maribor"),
        ("Acme announces a research facility in Ljubljana on 2026-11-27", "Acme", "Ljubljana"),
        ("Beta announces a research facility in Ljubljana on 2026-11-28", "Beta", "Ljubljana"),
    ):
        b = row("b", title)
        assert run([a, b], hints=[hint(a, entities=("Acme",), locations=("Ljubljana",)),
                                   hint(b, entities=(ent,), locations=(place,))])["candidate_count"] == 2


def test_one_article_can_supply_two_mentions_without_merging_them():
    x = "Acme announces a research facility in Ljubljana on 2026-11-28"
    y = "Beta opens a new distribution facility in Maribor on 2026-11-28"
    a = row("a", x + "; " + y)
    b = row("b", x)
    c = row("c", y)
    out = run([a, b, c], hints=[
        hint(a, x, ("Acme",), ("Ljubljana",)), hint(a, y, ("Beta",), ("Maribor",)),
        hint(b, entities=("Acme",), locations=("Ljubljana",)),
        hint(c, entities=("Beta",), locations=("Maribor",)),
    ])
    assert out["mention_count"] == 4 and out["candidate_count"] == 2
    assert sum(any(m["observation_id"] == a.observation_id for m in e["members"]) for e in out["events"]) == 2


def test_hint_scope_and_literal_anchors():
    a = row("a")
    with pytest.raises(ValueError, match="anchored"):
        hint(a, entities=("Invented entity",))
    with pytest.raises(ValueError, match="exactly once"):
        run([a], hints=[hint(a, "Imaginary source text")])
    with pytest.raises(ValueError, match="unknown observation"):
        run([a], hints=[hint(row("b"))])
    with pytest.raises(ValueError, match="Overlapping"):
        run([a], hints=[hint(a), hint(a, "Researchers announce a new renewable energy project")])


def test_stable_growth_and_revision_lineage():
    a, b, c = row("a"), row("b"), row("c")
    old = prior(run([a, b]))
    new = run([a, b, c], previous=old)
    assert new["events"][0]["event_id"] == old[0].event_id
    assert new["events"][0]["revision_id"] != old[0].revision_id
    assert new["lineage"][0]["state"] == "continued"
    assert new["events"][0]["previous_revision_ids"] == [old[0].revision_id]


def test_split_and_merge_do_not_silently_reassign_ids():
    a, b = row("a"), row("b")
    # Same exact title initially clusters. Explicit conflicting caller labels
    # are both literal source spans but make the new pair incompatible.
    old = prior(run([a, b]))
    split = run([a, b], previous=old, hints=[
        hint(a, entities=("Researchers",)), hint(b, entities=("communities",)),
    ])
    assert split["candidate_count"] == 2 and split["lineage"][0]["state"] == "split_candidate"
    assert all(e["event_id"] != old[0].event_id for e in split["events"])
    merged = run([a, b], previous=prior(split))
    assert merged["candidate_count"] == 1
    assert {x["state"] for x in merged["lineage"]} == {"merge_candidate"}
    assert merged["events"][0]["event_id"] not in {e["event_id"] for e in split["events"]}


def test_prior_event_absent_is_not_deletion():
    old = prior(run([row("a")]))
    out = run([], previous=old)
    assert out["candidate_count"] == 0
    assert out["lineage"][0]["state"] == "not_in_current_snapshot"


def test_future_capture_and_forged_inputs_rejected():
    with pytest.raises(ValueError, match="after cutoff"):
        run([row("a", capture="2026-11-29T12:00:00Z")])
    with pytest.raises(ValueError, match="Invalid input"):
        run([row("a").model_copy(update={"reported_url": "https://127.0.0.1/"})])
    with pytest.raises(ValueError, match="after cutoff"):
        cluster_news_events([row("a", capture=None)], as_of="2026-11-27T12:00:00Z")


def test_unknown_capture_not_replaced_with_replay_time():
    out = run([row("a", capture=None)])
    assert out["coverage"][0]["earliest_supplied_capture"] is None
    assert "capture_time_unknown" in out["coverage"][0]["warnings"]


def test_complete_link_pairs_are_not_transitive():
    # A and C have conflicting annotations; B has neither.
    a, b, c = row("a"), row("b"), row("c")
    out = run([a, b, c], hints=[hint(a, entities=("Researchers",)), hint(c, entities=("communities",))])
    assert out["candidate_count"] == 2
    assert all(len(e["pair_evidence"]) == len(e["members"]) * (len(e["members"]) - 1) // 2
               for e in out["events"])
