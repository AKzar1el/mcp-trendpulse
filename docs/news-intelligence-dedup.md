# News duplicate evidence (V4.04)

Experimental internal API, no registry or public runtime change. Free-only, fully offline.

`analyze_news_duplicates(observations, extractions=(), ephemeral_bodies=None)` accepts up to 80 typed NewsArticle observations and up to 80 typed ArticleExtraction receipts (one selected revision per observation). It validates IDs and scope; the result is independent of input order. Only exact repeated observation IDs are collapsed. Different records at the same URL remain distinct, including changed titles, dates and bodies.

| Relation | What it means |
| --- | --- |
| same_reported_url | Exact reported URL string equality, not a guarantee of same revision |
| same_resolved_url | Same transport-recorded response URL |
| resolved_reported_url_match | One recorded response URL matches the other's reported URL |
| canonical_candidate_match | A publisher/extractor canonical hint matches another reference; not a verified alias |
| matching_extracted_digest | Exact equality of supplied extraction digests; no body-length or originality proof |
| headline_exact_candidate / headline_near_candidate | Lexical title similarity with conservative factual-marker, date and language guards; not syndication evidence |
| normalized_body_match / near_body_match_candidate | Substantial permitted ephemeral bodies with identical normalized text or high five-token shingle resemblance |
| headline_similarity_blocked / body_similarity_blocked | Similarity observed, but guard disallows a positive candidate |

The headline path reuses the existing keyword normalizer and RapidFuzz full-string ratio, not partial or token-set similarity. It preserves signs, numbers, currency, percentages and selected negations/polarity markers as guards. Title threshold 96/100 and token Jaccard >=0.80; six words and 30 normalized characters minimum. Known comparable reported dates more than 72 hours apart and explicit differing language labels block headline candidates. Unknown dates remain unknown, and seen time is never compared to publication time. This is not a multilingual semantic classifier.

Optional body analysis requires an explicit matching operator-permitted SHA-256 extraction receipt for each supplied body. Up to 16 bodies, 512 KiB per body, 2 MiB total, 30,000 tokens per body; 80 tokens and 40 distinct five-token shingles minimum. Normalized text and shingles stay in memory only; neither they nor source body text are returned or persisted. Jaccard >=0.90, length ratio >=0.95 and factual-marker guards are required for a shared-text candidate. Matching digests alone do not establish substantial text (a short boilerplate shell can repeat). A cross-host shared-copy candidate requires actual recorded response hosts to differ. Rights and receipt authenticity are the caller's responsibility; hashes do not prove origin.

Direct pair relations are deterministic, not transitive equivalence classes. No automatic URL rewriting, canonical fetching, full article merging, event grouping, lineage attribution, source-independence scoring, or metric aggregation. No network, new dependencies, persistent body store or paid service.

## Evaluation and limits

Synthetic tests exercise repeated IDs, different revisions at one link, URL parameters, aliases/canonical hints, matching digests, changed numbers and negation, dates, languages, word order, short boilerplate, substantial body matches, body integrity, deterministic ordering, chaining and input bounds. These are regression fixtures, not an independently labeled real-world evaluation. The roadmap's held-out duplicate precision/recall and multilingual evaluation gates remain outstanding; do not advertise a measured accuracy percentage from these fixtures.

Design references:
- RapidFuzz full-string ratio and subset pitfalls: https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html
- Rodier and Carter (2020), Online Near-Duplicate Detection of News Articles: https://aclanthology.org/2020.lrec-1.156/
- Existing M02 keyword normalization: src/mcp_trendpulse/intelligence_keywords.py.
