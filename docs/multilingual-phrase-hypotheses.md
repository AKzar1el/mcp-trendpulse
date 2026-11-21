# MJAU M12 — Offline multilingual keyword and phrase hypotheses

M12 converts typed TrendPulse source signals and operator-supplied public titles into **lexical phrase hypotheses**, conservative near-duplicate families and explainable intent heuristics. It makes **no outbound requests**, creates no background work, uses no paid API, and downloads no model or NLTK corpus. It reuses the existing `nltk.util.ngrams`, M02 lexical normalization and RapidFuzz near-duplicate safeguards.

## Run locally

Preview a bounded example, with no provider credentials or network use:

    uv run --locked mcp-trendpulse-cli intelligence phrase-hypotheses --input docs/examples/mjau-m12-evidence.json --format text

For inspectable provenance and full results:

    uv run --locked mcp-trendpulse-cli intelligence phrase-hypotheses --input docs/examples/mjau-m12-evidence.json --format json

The input is local JSON, at most 128 KiB, containing a list of at most 80 evidence objects, or an object with exactly one key, `evidence`, whose value is such a list. The CLI never opens the SQLite quota database, refreshes an upstream source, guesses credentials, fetches public titles or accesses the Internet.

There are three accepted evidence kinds:

- **`{"kind":"signal","signal":{...}}`** — a complete M00 `TrendSignal` version 1 object validated against its existing Pydantic source schema. Only observed or partially observed source records are eligible. A search query enters `observed_query_terms` only when the typed provenance explicitly attests `is_observed_search_query=true`, the provenance method is a public/official/community source rather than operator-supplied or derived, and its metric is a recognized search metric. Search terms remain **source-attested**, not independently validated by the M12 offline step. Signals from nonsearch metrics such as HN stories, GitHub issues, Stack Overflow questions, Wikimedia pageviews, news or npm/PyPI downloads go to `source_topics_not_queries`, never the observed-query array. Unavailable/no-data signals are skipped, not interpreted as zero demand. Derived `generated_keyword_candidate` signals remain generated hypotheses.
- **`{"kind":"public_title", ...}`** — one public-title text field plus source ID, HTTPS URL, optional stable source record ID, observation timestamp with timezone, explicit language and optional country. It produces **generated_phrase_hypotheses only** and is labeled as operator-provided title metadata, not a verified source query. Source reference, country, language and UTC observation timestamp are retained per phrase; the title text itself is not recopied as a whole.
- **`{"kind":"manual_note","text":"...","language":"sl","country":"SI"}`** — a clearly unverified manual note, with no fabricated source URL, record ID or observation date. It never contributes to observed-query counts.

Untrusted extra fields, unsafe private/credential URLs, suspicious API key patterns, email addresses, invalid source IDs, path-traversal record IDs, controls and oversized text fail closed without echoing submitted data in errors.

## Supported language-specific lexical processing

M12 provides built-in minimalist stopwords and literal intent lexicons for **English (en), German (de), Spanish (es), French (fr), Slovenian (sl) and Croatian Latin (hr)**. Tokenization is Unicode-aware, preserving accents and C++/C# markers. It does not use remote translation, semantic embeddings, language guesses, NLTK corpora, stemming, pretrained POS tagging or a paid model. Titles with missing/unsupported language explicitly abstain from phrase generation. A typed, source-attested term in another language may be retained verbatim with `intent=unknown`.

Each public title yields up to 16 short unigram/bigram/trigram lexical hypotheses; the entire output is capped at 160 candidate terms. Under truncation, source-attested observed queries have priority over source topics and generated phrases, and `candidates_dropped_by_output_cap` discloses the omitted count.

The inspectable heuristic intent labels are `informational`, `problem`, `commercial`, `mixed` or `unknown`. Each candidate has actual matched cues and a readable explanation. A term triggering multiple classes becomes `mixed`; an unsupported language or unmatched cue becomes `unknown`. These are **keyword-pattern labels**, not human-labeled buyer intent or independently verified semantic meanings.

The bounded lexical relevance score uses only phrase length (capped at three tokens), distinct supplied source-observation references (capped at five) and matched intent cues (capped at two). Source-provided pageview counts, rank, interest indices, download totals, impressions and other unrelated units are **never** aggregated or used for scoring. These scores cannot be converted to search volume, SEO difficulty, market demand, sales opportunities or independent customer estimates.

## Duplicates, families and provenance

Exact candidate deduplication is scoped to evidence class, language, country and normalized phrase. Duplicate references are counted only once, and result ordering is deterministic even when input records are reversed. M02's conservative RapidFuzz complete-link test at 95/100 may group safe near-duplicates **only within identical evidence class, language, country and heuristic intent label**. Separate candidate terms and original references remain inspectable. No cross-language translation or semantic equivalence is asserted; accented/unaccented forms, C++ versus C#, negations and free-versus-paid qualifiers are not silently joined.

The result includes three separate arrays—`observed_query_terms`, `source_topics_not_queries` and `generated_phrase_hypotheses`—plus `lexical_keyword_families`. Per-candidate provenance references include source ID, HTTPS URL where available, source record ID, UTC observation timestamp where available, original language/country, source metric type and coverage class. No measured numeric values or unknown upstream payload fields are copied. An unspecified country does **not** imply global coverage.

## Offline acceptance evidence

Deterministic tests cover six languages across informational/problem/commercial examples, Unicode accents, C++/C#, manual versus source-query separation, absent-source abstention, duplicate input and stable ordering, unsupported languages, multilingual cue explanation, strict URL/key validation, cache-free CLI, output caps and source-evidence priority under truncation. No data-collection quota or source request is consumed by this milestone.

`docs/examples/mjau-m12-evidence.json` is a strictly offline illustration. Two source-linked public-title references originate from the prior bounded M07 Hacker News and M11 Stack Exchange observations, alongside **explicitly manual** Slovenian, German and French examples. These are not new M12 live provider requests and are not evidence that the generated phrase candidates have real search demand.

M04's live Google Trends Explore source check remains subject to the previously documented upstream 429 gate. M08's original GitHub request-lock ACL gate is independent. Draft PRs for M09–M11 are not merged or overwritten by this M12 implementation. M13 historical lifecycle analysis and M14 cross-source recommendations require separate, later verification.
