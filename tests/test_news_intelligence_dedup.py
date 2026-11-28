"""Synthetic, offline V4.04 duplicate-evidence regressions."""
import hashlib
import json

import pytest

from mcp_trendpulse.news_intelligence_dedup import (
    MAX_OBSERVATIONS, analyze_news_duplicates,
)
from mcp_trendpulse.news_intelligence_extract import ArticleExtraction
from mcp_trendpulse.news_intelligence_schema import NewsArticle, TimeEvidence

CAPTURE = "2026-11-28T12:00:00Z"
HEADLINE = "Researchers announce a new renewable energy storage system for rural communities"


def obs(key, title=HEADLINE, *, url=None, language="English", seen="2026-11-28T11:00:00Z"):
    return NewsArticle(
        discovery_provider="gdelt_doc", link_type="publisher_candidate",
        reported_url=url or f"https://example.org/story/{key}", title=title,
        reported_language=language, capture_mode="legacy_import", captured_at=CAPTURE,
        provider_seen_at=TimeEvidence(value=seen, precision="second", basis="provider_seen") if seen else None,
    )


def receipt(row, *, resolved=None, canonical=None, body=None):
    return ArticleExtraction(
        discovery=row, status="extracted", started_at=CAPTURE, completed_at=CAPTURE,
        content_level="extracted_text", http_status=200, resolved_url=resolved or row.reported_url,
        canonical_url_candidate=canonical,
        body_sha256=hashlib.sha256(body.encode()).hexdigest() if body is not None else None,
        body_digest_policy="operator_permitted" if body is not None else "not_retained",
        warnings=("cross_host_canonical_candidate",) if canonical and "other.org" in canonical else (),
    )


def relations(result):
    return result["pairs"][0]["relations"]


def test_exact_replay_is_only_automatic_collapse():
    a = obs("a")
    b = obs("b", "A different headline about a revised report from researchers", url=a.reported_url)
    result = analyze_news_duplicates([a, a, b])
    assert result["input_observation_count"] == 3
    assert result["unique_observation_count"] == 2 and result["exact_replays_removed"] == 1
    assert relations(result) == ["same_reported_url"]
    assert not result["pairs"][0]["automatic_merge"]


def test_canonical_hints_and_resolved_links_distinct():
    a, b = obs("a"), obs("b", "A separate topic for a canonical-link test")
    ra = receipt(a, canonical=b.reported_url)
    rb = receipt(b)
    result = analyze_news_duplicates([a, b], extractions=[ra, rb])
    assert relations(result) == ["canonical_candidate_match"]
    assert not result["pairs"][0]["shared_text_candidate"]
    ra = receipt(a, resolved=b.reported_url)
    result = analyze_news_duplicates([a, b], extractions=[ra, rb])
    assert "same_resolved_url" in relations(result)
    assert "resolved_reported_url_match" in relations(result)


def test_arbitrary_query_parameters_are_not_stripped():
    a = obs("a", "First unrelated news story", url="https://example.org/story?id=1")
    b = obs("b", "Second unrelated news story", url="https://example.org/story?id=2")
    assert not analyze_news_duplicates([a, b])["pairs"]


def test_exact_and_near_headlines_are_candidates_not_syndication():
    a = obs("a")
    b = obs("b", HEADLINE.upper())
    result = analyze_news_duplicates([a, b])
    assert relations(result) == ["headline_exact_candidate"]
    assert not result["pairs"][0]["shared_text_candidate"]
    b = obs("b", HEADLINE.replace("communities", "community"))
    result = analyze_news_duplicates([a, b])
    assert "headline_near_candidate" in relations(result)
    assert result["pairs"][0]["source_independence"] == "unknown"


@pytest.mark.parametrize("left,right", [
    ("Government announces funding of 100 million euros for the national transport programme",
     "Government announces funding of 900 million euros for the national transport programme"),
    ("Government approves a major renewable energy proposal in the regional development programme",
     "Government disapproves a major renewable energy proposal in the regional development programme"),
    ("Researchers confirm the new treatment is safe in the larger clinical study announced today",
     "Researchers confirm the new treatment is not safe in the larger clinical study announced today"),
    ("Company reports a 12.5 percent improvement in quarterly output across all factories",
     "Company reports a 12.6 percent improvement in quarterly output across all factories"),
    ("Company reports +10 percent improvement in quarterly output across all factories",
     "Company reports -10 percent improvement in quarterly output across all factories"),
])
def test_changed_facts_do_not_become_headline_matches(left, right):
    result = analyze_news_duplicates([obs("a", left), obs("b", right)])
    assert not any(
        "headline_exact_candidate" in p["relations"] or "headline_near_candidate" in p["relations"]
        for p in result["pairs"]
    )


def test_language_and_time_guards():
    a = obs("a")
    for b, guard in (
        (obs("b", language="German"), "different_language_labels"),
        (obs("b", seen="2026-11-20T11:00:00Z"), "reported_dates_apart"),
    ):
        pair = analyze_news_duplicates([a, b])["pairs"][0]
        assert "headline_similarity_blocked" in pair["relations"] and guard in pair["guards"]
    pair = analyze_news_duplicates([a, obs("b", seen=None)])["pairs"][0]
    assert "comparable_date_unknown" in pair["guards"]
    assert not pair["shared_text_candidate"]


def body_text():
    # Artificial text only. Distinct sentences avoid inflating overlap via boilerplate.
    return (
        "A regional research team presented a prototype battery during a public meeting. "
        "Engineers described the testing procedure and explained the limitations of their measurements. "
        "The project connects rural settlements through an experimental distribution network. "
        "Independent laboratories examined the materials using several temperature and humidity settings. "
        "Local residents contributed suggestions about safe installation and routine maintenance. "
        "University staff recorded observations in an accessible repository for subsequent analysis. "
        "The council discussed funding arrangements during its regularly scheduled planning session. "
        "An industry partner demonstrated modular assembly and compared alternative packaging methods. "
        "Participants identified unresolved questions about long term reliability and environmental impacts. "
        "Future workshops will explore additional applications in farming and forestry."
    )


def with_bodies(a, b, x, y):
    ra, rb = receipt(a, body=x), receipt(b, body=y)
    return analyze_news_duplicates([a, b], extractions=[ra, rb],
                                   ephemeral_bodies={ra.extraction_id: x, rb.extraction_id: y})


def test_exact_digest_is_shared_text_candidate_only():
    a, b = obs("a"), obs("b", "Unrelated headline on the second publisher")
    x = body_text()
    result = analyze_news_duplicates([a, b], extractions=[receipt(a, body=x), receipt(b, body=x)])
    assert "matching_extracted_digest" in relations(result)
    assert not result["pairs"][0]["shared_text_candidate"]
    assert "body_substance_unverified" in result["pairs"][0]["guards"]
    assert result["pairs"][0]["source_independence"] == "unknown"
    assert not result["pairs"][0]["automatic_merge"]


def test_normalized_and_near_body_evidence_not_returned():
    a, b = obs("a"), obs("b")
    x = body_text()
    for y, kind in ((x.upper(), "normalized_body_match"),
                    (x.replace("forestry", "conservation"), "near_body_match_candidate")):
        result = with_bodies(a, b, x, y)
        assert kind in relations(result)
        assert result["pairs"][0]["body_shingle_jaccard"] >= .90
        wire = json.dumps(result)
        assert x not in wire and y not in wire
        assert "shingles" not in result


def test_factual_change_blocks_near_body_even_with_high_overlap():
    a, b = obs("a"), obs("b")
    x = body_text() + " The report estimates 100 units."
    y = x.replace("100 units", "900 units")
    result = with_bodies(a, b, x, y)
    assert "body_similarity_blocked" in relations(result)
    assert not result["pairs"][0]["shared_text_candidate"]


def test_short_or_boilerplate_bodies_abstain():
    a, b = obs("a"), obs("b")
    x = "Privacy policy cookies."
    y = x.upper()
    result = with_bodies(a, b, x, y)
    assert result["body_inputs_with_sufficient_features"] == 0
    assert not result["pairs"][0]["shared_text_candidate"]
    result = with_bodies(a, b, x, x)
    assert "matching_extracted_digest" in relations(result)
    assert not result["pairs"][0]["shared_text_candidate"]


def test_body_receipt_scope_and_digest_validation():
    a, b = obs("a"), obs("b")
    ra = receipt(a, body=body_text())
    with pytest.raises(ValueError, match="outside"):
        analyze_news_duplicates([b], extractions=[ra])
    with pytest.raises(ValueError, match="does not match"):
        analyze_news_duplicates([a], extractions=[ra], ephemeral_bodies={ra.extraction_id: "SECRET"})
    no_digest = receipt(a)
    with pytest.raises(ValueError, match="permitted"):
        analyze_news_duplicates([a], extractions=[no_digest],
                                ephemeral_bodies={no_digest.extraction_id: body_text()})
    with pytest.raises(ValueError, match="revision"):
        analyze_news_duplicates([a], extractions=[ra, no_digest])


def test_deterministic_pairwise_output_without_chaining():
    a = obs("a", url="https://example.org/story/a")
    b = obs("b", "An unrelated source headline", url=a.reported_url)
    c = obs("c", "Another completely different source headline")
    rb = receipt(b, resolved=c.reported_url)
    rc = receipt(c)
    first = analyze_news_duplicates([a, b, c], extractions=[rb, rc])
    second = analyze_news_duplicates([c, a, b], extractions=[rc, rb])
    assert first == second
    pairs = {frozenset((p["left_observation_id"], p["right_observation_id"])) for p in first["pairs"]}
    assert frozenset((a.observation_id, b.observation_id)) in pairs
    assert frozenset((b.observation_id, c.observation_id)) in pairs
    assert frozenset((a.observation_id, c.observation_id)) not in pairs
    assert first["unique_observation_count"] == 3 and first["comparisons"] == 3


def test_bounded_snapshot_and_forged_inputs():
    with pytest.raises(ValueError, match="bounded"):
        analyze_news_duplicates([obs("a")] * (MAX_OBSERVATIONS + 1))
    forged = obs("a").model_copy(update={"reported_url": "https://127.0.0.1/"})
    with pytest.raises(ValueError, match="Invalid news observation"):
        analyze_news_duplicates([forged])
    result = analyze_news_duplicates([obs(i) for i in range(MAX_OBSERVATIONS)])
    assert result["comparisons"] == MAX_OBSERVATIONS * (MAX_OBSERVATIONS - 1) // 2
    assert result["unique_observation_count"] == MAX_OBSERVATIONS
    assert not result["source_independence_established"] and not result["network_performed"]

def test_cross_host_copy_candidate_requires_substantive_matching_text():
    a, b = obs("a"), obs("b", url="https://other.org/story/b")
    x = body_text()
    result = with_bodies(a, b, x, x)
    pair = result["pairs"][0]
    assert pair["shared_text_candidate"] and pair["cross_host_copy_candidate"]
    assert pair["source_independence"] == "unknown"
    assert not pair["automatic_merge"]


def test_contraction_and_word_order_do_not_create_shared_copy():
    a = obs("a", "The government says the new national research facility can open in spring")
    b = obs("b", "The government says the new national research facility can't open in spring")
    result = analyze_news_duplicates([a, b])
    assert not any("headline_near_candidate" in p["relations"] for p in result["pairs"])
    a = obs("a", "The court ordered the company to pay the local authority for damages")
    b = obs("b", "The court ordered the local authority to pay the company for damages")
    assert not any("headline_near_candidate" in p["relations"] for p in analyze_news_duplicates([a, b])["pairs"])


def test_empty_and_short_headline_snapshots():
    assert analyze_news_duplicates([])["comparisons"] == 0
    result = analyze_news_duplicates([obs("a", "Market update"), obs("b", "Market update")])
    assert result["pairs"] == []
