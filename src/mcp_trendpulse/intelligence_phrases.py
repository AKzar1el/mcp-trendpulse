"""M12: bounded, offline, source-preserving multilingual phrase hypotheses.

Public titles produce lexical hypotheses, never observed search queries. A
typed provider TrendSignal can attest a query only when its provenance and
metric type explicitly support it. All intent and ranking is heuristic.
"""
from __future__ import annotations

import html
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from nltk.util import ngrams
from pydantic import ValidationError

from mcp_trendpulse.intelligence_keywords import (
    _safe_near_duplicate,
    normalize_keyword,
)
from mcp_trendpulse.intelligence_signal import TrendSignal

MAX_INPUT_RECORDS = 80
MAX_INPUT_BYTES = 128 * 1024
MAX_TITLE_CHARS = 280
MAX_PHRASE_CHARS = 90
MAX_PER_TITLE = 16
MAX_OUTPUT_TERMS = 160
MAX_FAMILIES = 160
SUPPORTED_LANGUAGES = frozenset({"en", "de", "es", "fr", "sl", "hr"})
_SOURCE_ID = re.compile(r"[a-z][a-z0-9_]{1,59}\Z")
_RECORD_ID = re.compile(r"[A-Za-z0-9_.:/-]{1,120}\Z")
_LANGUAGE = re.compile(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8}){0,2}\Z")
_COUNTRY = re.compile(r"[A-Z]{2}\Z")
_TOKEN = re.compile(r"(?u)[^\W_]+(?:\+\+|#)?")
_EMAIL = re.compile(r"(?i)\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_TOKEN_SECRET = re.compile(r"(?i)\b(?:sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9_]{16,}|AKIA[0-9A-Z]{16})\b")
_SECRET_QKEYS = frozenset({
    "key", "api_key", "apikey", "token", "access_token", "auth",
    "authorization", "password", "secret", "client_secret",
})
_SEARCH_METRICS = frozenset({
    "google_trends_normalized_interest",
    "google_trending_traffic_bucket",
    "google_bigquery_rank",
    "bing_keyword_impressions",
})
_NON_OPERATOR_METHODS = frozenset({
    "official_api", "public_rss", "public_dataset",
    "community_provider", "public_api",
})
# Minimal, curated, package-data-free stopwords. Intent-bearing negations
# and commercial qualifiers are deliberately NOT stopwords.
_STOPWORDS: dict[str, frozenset[str]] = {
    "en": frozenset(
        "a an the of to for in on at by with from as is are was were "
        "how what why who when where do does did i my me your our it "
        "this that and or can could should would a".split()
    ),
    "de": frozenset(
        "der die das den dem des ein eine einer einem und oder zu zur zum "
        "mit von vom im in auf bei für als wie was warum wieso ist sind "
        "ich mein meine es man".split()
    ),
    "es": frozenset(
        "el la los las un una unos unas de del a al en con por para y o "
        "como cómo que qué cuando cuándo donde dónde es son mi mis su".split()
    ),
    "fr": frozenset(
        "le la les un une des de du au aux à en avec par pour sur dans et ou "
        "comment pourquoi quel quelle est sont mon ma mes une".split()
    ),
    "sl": frozenset(
        "in ali za na pri iz od v s z po kako kaj zakaj kje kdaj je so "
        "sem si smo da kot ter moj moja moje".split()
    ),
    "hr": frozenset(
        "i ili za na u iz od sa s po kod kao kako što sta zasto zašto "
        "je su sam smo da koji koja koje moj moja moje".split()
    ),
}
_INTENT: dict[str, dict[str, tuple[str, ...]]] = {
    "en": {
        "problem": ("error", "errors", "bug", "bugs", "fail", "failure", "failed",
                    "timeout", "exception", "crash", "broken", "fix", "stuck",
                    "not working", "slow", "repair"),
        "informational": ("guide", "tutorial", "explain", "documentation",
                          "example", "examples", "setup", "configure", "learn",
                          "how to", "how", "what", "why"),
        "commercial": ("price", "pricing", "cost", "costs", "buy", "paid",
                       "subscription", "alternative", "alternatives",
                       "compare", "comparison", "versus", "vs", "best", "free"),
    },
    "de": {
        "problem": ("fehler", "absturz", "kaputt", "problem", "probleme",
                    "timeout", "ausfall", "beheben", "reparieren",
                    "funktioniert nicht"),
        "informational": ("anleitung", "erklärung", "erklarung", "beispiel",
                          "lernen", "einrichten", "konfigurieren", "wie", "warum"),
        "commercial": ("preis", "preise", "kosten", "kaufen", "günstig",
                       "guenstig", "vergleich", "alternativen", "abo",
                       "kostenlos"),
    },
    "es": {
        "problem": ("error", "errores", "fallo", "falla", "problema", "problemas",
                    "timeout", "solucionar", "arreglar", "no funciona"),
        "informational": ("guía", "guia", "tutorial", "ejemplo", "aprender",
                          "configurar", "explicar", "cómo", "como", "por qué"),
        "commercial": ("precio", "precios", "costo", "coste", "comprar",
                       "comparar", "alternativas", "suscripción", "gratis"),
    },
    "fr": {
        "problem": ("erreur", "erreurs", "panne", "bug", "problème", "problèmes",
                    "timeout", "réparer", "corriger", "ne fonctionne pas"),
        "informational": ("guide", "tutoriel", "exemple", "apprendre",
                          "configurer", "comment", "pourquoi"),
        "commercial": ("prix", "coût", "cout", "acheter", "comparer",
                       "comparaison", "alternatives", "abonnement", "gratuit"),
    },
    "sl": {
        "problem": ("napaka", "napake", "napako", "težava", "težave",
                    "težavo", "problem", "sesutje", "popraviti", "odpraviti",
                    "timeout", "ne deluje"),
        "informational": ("vodič", "vodic", "navodila", "primer", "primeri",
                          "razlaga", "nastavitev", "namestitev", "kako", "zakaj"),
        "commercial": ("cena", "cene", "stroški", "stroski", "kupiti",
                       "primerjava", "primerjati", "alternative",
                       "naročnina", "brezplačno"),
    },
    "hr": {
        "problem": ("greška", "greska", "greške", "greske", "grešku", "gresku", "problem",
                    "problemi", "pogreška", "pogreska", "popraviti",
                    "riješiti", "rijesiti", "timeout", "ne radi"),
        "informational": ("vodič", "vodic", "upute", "primjer", "primjeri",
                          "objašnjenje", "objasnjenje", "postavke", "kako", "zašto"),
        "commercial": ("cijena", "cijene", "trošak", "trosak", "kupiti",
                       "usporedba", "usporediti", "alternative",
                       "pretplata", "besplatno"),
    },
}
# Normalize the tiny curated lexicon ONCE, not on each candidate n-gram.
# This keeps the title extraction bound useful on slower Windows hosts.
_INTENT_MATCHERS = {
    lang: {
        label: tuple(
            (cue, " " + normalize_keyword(cue) + " ") for cue in cues
        )
        for label, cues in labels.items()
    }
    for lang, labels in _INTENT.items()
}


def _printable(text: Any, *, max_chars: int, label: str) -> str:
    if (
        not isinstance(text, str) or not 1 <= len(text) <= max_chars
        or text != text.strip()
        or any(ord(c) < 32 or ord(c) == 127 for c in text)
        or _EMAIL.search(text) or _TOKEN_SECRET.search(text)
    ):
        raise ValueError(f"Invalid, sensitive, or excessively long {label}")
    return unicodedata.normalize("NFC", text)


def _locale(language: Any, country: Any) -> tuple[str, str | None]:
    if language is None:
        lang = "und"
    elif isinstance(language, str) and _LANGUAGE.fullmatch(language):
        lang = language.split("-", 1)[0].lower()
    else:
        raise ValueError("Unsupported language tag syntax")
    if country is not None and (
        not isinstance(country, str) or _COUNTRY.fullmatch(country) is None
    ):
        raise ValueError("Country scope must be a two-letter uppercase ISO code")
    return lang, country


def _timestamp(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("Evidence timestamp must be an ISO string with a timezone")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None or dt.utcoffset() is None:
            raise ValueError("Missing time zone")
        return dt.astimezone(timezone.utc).isoformat()
    except (ValueError, OverflowError) as exc:
        raise ValueError("Invalid evidence observation time") from exc


def _source_url(value: Any) -> str:
    if not isinstance(value, str) or not 10 <= len(value) <= 600:
        raise ValueError("Invalid public evidence URL")
    try:
        parsed = urlsplit(value)
        _ = parsed.port
        from urllib.parse import parse_qsl

        query = {key.casefold() for key, _ in parse_qsl(
            parsed.query, keep_blank_values=True,
        )}
        if (
            parsed.scheme != "https" or not parsed.hostname
            or parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            or parsed.hostname.endswith((".internal", ".local"))
            or parsed.username or parsed.password or parsed.fragment
            or parsed.port not in (None, 443)
            or _SECRET_QKEYS & query
        ):
            raise ValueError("Unsafe evidence URL")
    except ValueError as exc:
        raise ValueError("Invalid or private evidence URL") from exc
    return value


def _evidence(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Each evidence item must be a JSON object")
    kind = raw.get("kind")
    if kind == "signal":
        if set(raw) != {"kind", "signal"}:
            raise ValueError("Typed signal wrapper must have exactly kind and signal")
        try:
            signal = TrendSignal.model_validate(raw["signal"])
        except (ValidationError, ValueError, TypeError) as exc:
            raise ValueError("Invalid typed TrendSignal") from exc
        language, country = _locale(signal.language, signal.country)
        coverage = signal.coverage_status
        if signal.metric_type == "generated_keyword_candidate":
            evidence_class = "generated_hypothesis"
        elif (
            signal.provenance.is_observed_search_query
            and signal.provenance.method in _NON_OPERATOR_METHODS
            and signal.metric_type in _SEARCH_METRICS
            and coverage in {"observed", "partial"}
        ):
            evidence_class = "observed_query"
        else:
            evidence_class = "source_topic_not_search_query"
        return {
            "kind": kind,
            "evidence_class": evidence_class,
            "text": _printable(signal.raw_term, max_chars=180, label="signal term"),
            "language": language,
            "country": country,
            "reference": {
                "source_id": signal.source_id,
                "source_url": signal.source_url,
                "source_record_id": signal.provenance.source_record_id,
                "observed_at": signal.observed_at.isoformat(),
                "language": signal.language,
                "country": signal.country,
                "metric_type": signal.metric_type,
                "coverage_status": coverage,
                "is_source_attested_search_query": (
                    evidence_class == "observed_query"
                ),
                "observation_kind": "validated_typed_signal",
            },
            "usable": coverage in {"observed", "partial"} or (
                signal.metric_type == "generated_keyword_candidate"
            ),
        }

    if kind == "public_title":
        allowed = {
            "kind", "source_id", "source_url", "source_record_id",
            "observed_at", "language", "country", "title",
        }
        required = allowed - {"source_record_id", "country"}
        if not required <= set(raw) or set(raw) - allowed:
            raise ValueError("Public-title evidence has missing or unknown fields")
        sid = raw["source_id"]
        if not isinstance(sid, str) or _SOURCE_ID.fullmatch(sid) is None:
            raise ValueError("Invalid source ID")
        rid = raw.get("source_record_id")
        if rid is not None and (
            not isinstance(rid, str) or _RECORD_ID.fullmatch(rid) is None
            or ".." in rid or rid.startswith(("/", ":", "-"))
        ):
            raise ValueError("Invalid public source record ID")
        language, country = _locale(raw["language"], raw.get("country"))
        return {
            "kind": kind, "evidence_class": "generated_hypothesis",
            "text": _printable(raw["title"], max_chars=MAX_TITLE_CHARS, label="title"),
            "language": language, "country": country, "usable": True,
            "reference": {
                "source_id": sid,
                "source_url": _source_url(raw["source_url"]),
                "source_record_id": rid,
                "observed_at": _timestamp(raw["observed_at"]),
                "language": raw["language"],
                "country": country,
                "metric_type": None,
                "coverage_status": "unverified_public_title",
                "is_source_attested_search_query": False,
                "observation_kind": "user_supplied_public_title",
            },
        }

    if kind == "manual_note":
        allowed = {"kind", "text", "language", "country"}
        if set(raw) - allowed or not {"kind", "text", "language"} <= set(raw):
            raise ValueError("Manual note has unknown or missing fields")
        language, country = _locale(raw["language"], raw.get("country"))
        return {
            "kind": kind, "evidence_class": "generated_hypothesis",
            "text": _printable(raw["text"], max_chars=MAX_TITLE_CHARS, label="note"),
            "language": language, "country": country, "usable": True,
            "reference": {
                "source_id": "operator_note",
                "source_url": None, "source_record_id": None,
                "observed_at": None, "language": raw["language"],
                "country": country,
                "metric_type": None,
                "coverage_status": "manual_unverified",
                "is_source_attested_search_query": False,
                "observation_kind": "manual_note_not_public_source",
            },
        }
    raise ValueError("Evidence kind must be signal, public_title or manual_note")


def _tokens(text: str) -> list[str]:
    # NLTK ngrams is corpus-independent; no network and no language packs.
    return [
        word
        for word in _TOKEN.findall(html.unescape(text))
        if len(word) >= 2 or word in {"c#", "c++"}
    ]


def _intent(phrase: str, language: str) -> dict[str, Any]:
    if language not in _INTENT:
        return {
            "label": "unknown", "matched_cues": [],
            "explanation": "No supported intent lexicon for this language; abstaining.",
            "method": "transparent_multilingual_lexical_heuristic",
        }
    normalized = normalize_keyword(phrase)
    text = " " + normalized + " "
    matches = {
        label: sorted({
            cue for cue, needle in cues if needle in text
        })
        for label, cues in _INTENT_MATCHERS[language].items()
    }
    found = {label: cues for label, cues in matches.items() if cues}
    if len(found) > 1:
        label = "mixed"
        reason = "Multiple intent cue classes matched; no single intent assumed."
    elif found:
        label = next(iter(found))
        reason = "Literal language-specific cue matched; not semantic classification."
    else:
        label = "unknown"
        reason = "No supported intent cue matched; abstaining."
    return {
        "label": label,
        "matched_cues": [
            {"category": category, "cue": cue}
            for category in sorted(found) for cue in found[category]
        ],
        "explanation": reason,
        "method": "transparent_multilingual_lexical_heuristic",
    }


def _title_phrases(text: str, lang: str) -> list[str]:
    if lang not in SUPPORTED_LANGUAGES:
        return []
    words = _tokens(text)
    meaningful = [
        w for w in words
        if w.casefold() not in _STOPWORDS[lang] and (
            len(w) > 2 or w.casefold() in {"c#", "c++", "ai", "api"}
        )
    ]
    if not meaningful:
        return []
    out: dict[str, str] = {}
    for n in (1, 2, 3):
        if len(meaningful) < n:
            continue
        for span in ngrams(meaningful, n):
            phrase = " ".join(span)
            norm = normalize_keyword(phrase)
            if (
                len(norm) < 4 or len(phrase) > MAX_PHRASE_CHARS
                or n == 1 and len(norm) < 5
            ):
                continue
            # Keep original-language casing only as a display label.
            out.setdefault(norm, phrase)
    ranked = sorted(
        out.values(),
        key=lambda phrase: (
            -int(_intent(phrase, lang)["label"] != "unknown"),
            -min(len(phrase.split()), 3), -min(len(phrase), 40),
            normalize_keyword(phrase),
        ),
    )
    return ranked[:MAX_PER_TITLE]


def _reference_id(ref: dict[str, Any]) -> tuple[Any, ...]:
    return (
        ref["source_id"], ref["source_url"], ref["source_record_id"],
        ref["observed_at"], ref["observation_kind"],
    )


def _score(phrase: str, evidence_count: int, intent: dict[str, Any]) -> tuple[int, list[str]]:
    # Pure ordinal lexical ranking within its own evidence class.
    words = len(_tokens(phrase))
    terms = min(3, words)
    distinct_sources = min(5, evidence_count)
    cues = min(2, len(intent["matched_cues"]))
    score = min(100, 18 + terms * 9 + distinct_sources * 8 + cues * 6)
    return score, [
        f"phrase_tokens_capped_at_3={terms}",
        f"distinct_source_observation_refs_capped_at_5={distinct_sources}",
        f"matched_lexical_intent_cues_capped_at_2={cues}",
        "no_source_metrics_or_keyword_volumes_aggregated",
    ]


def _families(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Conservative complete-link M02 near-duplicates, never semantic unions."""
    buckets: dict[tuple[str, str, str | None, str], list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        key = (
            item["evidence_class"], item["language"],
            item["country"], item["intent"]["label"],
        )
        buckets[key].append(item)
    result: list[dict[str, Any]] = []
    for bucket in sorted(buckets, key=lambda k: (k[0], k[1], k[2] or "", k[3])):
        groups: list[list[dict[str, Any]]] = []
        for candidate in sorted(buckets[bucket], key=lambda x: x["normalized"]):
            selected = None
            for group in groups:
                if all(
                    _safe_near_duplicate(
                        candidate["normalized"], item["normalized"], 95.0,
                    ) is not None for item in group
                ):
                    selected = group
                    break
            if selected is None:
                groups.append([candidate])
            else:
                selected.append(candidate)
        for group in groups:
            keys = sorted(item["normalized"] for item in group)
            result.append({
                "evidence_class": bucket[0], "language": bucket[1],
                "country": bucket[2], "intent_label": bucket[3],
                "representative_normalized": keys[0],
                "member_normalized": keys,
                "lexical_grouping": (
                    "conservative_rapidfuzz_complete_link"
                    if len(group) > 1 else "singleton"
                ),
                "semantic_equivalence_verified": False,
                "metrics_aggregated": False,
            })
    return result[:MAX_FAMILIES]


def extract_phrase_hypotheses(payload: Any) -> dict[str, Any]:
    """No disk/network/provider access. Exact source references are preserved."""
    if isinstance(payload, list):
        raw = payload
    elif isinstance(payload, dict) and set(payload) == {"evidence"}:
        raw = payload["evidence"]
    else:
        raise ValueError("Expected evidence list or object with only evidence")
    if not isinstance(raw, list) or len(raw) > MAX_INPUT_RECORDS:
        raise ValueError("M12 expects at most 80 evidence records")
    if not raw:
        raise ValueError("At least one source signal, public title or note is required")

    entries = [_evidence(item) for item in raw]
    normalized_entries = sorted(
        entries,
        key=lambda e: (
            e["language"], e["country"] or "", e["evidence_class"],
            e["text"].casefold(),
            tuple("" if x is None else str(x) for x in _reference_id(e["reference"])),
        ),
    )
    groups: dict[tuple[str, str, str | None, str], dict[str, Any]] = {}
    unavailable = 0
    unsupported = 0
    for entry in normalized_entries:
        if not entry["usable"]:
            unavailable += 1
            continue
        evidence_class = entry["evidence_class"]
        language, country = entry["language"], entry["country"]
        if entry["kind"] == "signal":
            phrases = [entry["text"]]
        else:
            phrases = _title_phrases(entry["text"], language)
            if not phrases and language not in SUPPORTED_LANGUAGES:
                unsupported += 1
                continue
        for phrase in phrases:
            normalized = normalize_keyword(phrase)
            if len(normalized) > MAX_PHRASE_CHARS:
                continue
            key = (evidence_class, language, country, normalized)
            if key not in groups:
                groups[key] = {
                    "evidence_class": evidence_class,
                    "phrase": phrase,
                    "normalized": normalized,
                    "language": language,
                    "country": country,
                    "provenance": {},
                }
            group = groups[key]
            if (phrase.casefold(), phrase) < (
                group["phrase"].casefold(), group["phrase"]
            ):
                group["phrase"] = phrase
            ref = entry["reference"]
            group["provenance"][_reference_id(ref)] = ref.copy()
    output: dict[str, list[dict[str, Any]]] = {
        "observed_query_terms": [],
        "source_topics_not_queries": [],
        "generated_phrase_hypotheses": [],
    }
    mapping = {
        "observed_query": "observed_query_terms",
        "source_topic_not_search_query": "source_topics_not_queries",
        "generated_hypothesis": "generated_phrase_hypotheses",
    }
    all_candidates = []
    for key in sorted(groups, key=lambda k: (k[0], k[1], k[2] or "", k[3])):
        entry = groups[key]
        intent = _intent(entry["phrase"], entry["language"])
        refs = sorted(
            entry["provenance"].values(),
            key=lambda ref: tuple(
                "" if part is None else str(part) for part in _reference_id(ref)
            ),
        )
        score, reasons = _score(entry["phrase"], len(refs), intent)
        candidate = {
            "evidence_class": entry["evidence_class"],
            "phrase": entry["phrase"],
            "normalized": entry["normalized"],
            "language": entry["language"],
            "country": entry["country"],
            "intent": intent,
            "lexical_relevance_score": score,
            "ranking_explanation": reasons,
            "independent_customers_verified": False,
            "search_volume_verified": False,
            "seo_competition_verified": False,
            "source_observations": refs,
        }
        all_candidates.append(candidate)
    source_evidence_priority = {
        "observed_query": 0, "source_topic_not_search_query": 1,
        "generated_hypothesis": 2,
    }
    for candidate in sorted(
        all_candidates,
        key=lambda c: (
            source_evidence_priority[c["evidence_class"]],
            -c["lexical_relevance_score"],
            c["language"], c["country"] or "", c["normalized"],
        ),
    )[:MAX_OUTPUT_TERMS]:
        output[mapping[candidate["evidence_class"]]].append(candidate)
    selected = [
        *output["observed_query_terms"],
        *output["source_topics_not_queries"],
        *output["generated_phrase_hypotheses"],
    ]
    families = _families(selected)
    return {
        "schema_version": 1,
        "mode": "offline_multilingual_source_preserving_phrase_hypotheses",
        "network_performed": False,
        "paid_services_used": False,
        "models_or_corpora_downloaded": False,
        "new_dependencies_installed": False,
        "input_records": len(raw),
        "unavailable_or_no_data_signals_skipped": unavailable,
        "unsupported_language_title_records_skipped": unsupported,
        "output_truncated": len(groups) > MAX_OUTPUT_TERMS,
        "candidates_dropped_by_output_cap": max(0, len(groups)-len(selected)),
        "input_candidate_families_truncated": (
            len(families) == MAX_FAMILIES and len(selected) > MAX_FAMILIES
        ),
        "output_candidates": len(selected),
        "intent_method": "multilingual_rule_based_heuristic_with_cue_explanations",
        "ranking_method": "bounded_lexical_relevance_no_provider_metric_weight",
        "observed_query_note": (
            "Source-attested typed query provenance, not independently "
            "verified search volume; public titles never become queries."
        ),
        "generated_keyword_note": (
            "Lexical phrase hypotheses only; no search volume, intent certainty,"
            " customer demand, SEO difficulty or competition measured."
        ),
        "no_cross_language_or_country_merges": True,
        "source_metrics_aggregated": False,
        **output,
        "lexical_keyword_families": families,
    }


def format_phrase_hypotheses(report: dict[str, Any]) -> str:
    lines = [
        "OFFLINE MULTILINGUAL KEYWORD & PHRASE HYPOTHESES",
        f"Evidence: {report['input_records']}; candidates: {report['output_candidates']}",
        "Generated phrases and intent are heuristics, not observed search volumes.",
    ]
    for field, title in (
        ("observed_query_terms", "Source-attested observed queries"),
        ("source_topics_not_queries", "Source topics (NOT observed queries)"),
        ("generated_phrase_hypotheses", "Generated phrase hypotheses"),
    ):
        lines.append(title + ":")
        for item in report[field][:12]:
            lines.append(
                f"  {item['phrase']} [{item['language']}/"
                f"{item['country'] or 'unspecified country'}] "
                f"{item['intent']['label']} "
                f"(lexical relevance {item['lexical_relevance_score']})"
            )
        if len(report[field]) > 12:
            lines.append("  ...more in JSON output")
    return "\n".join(lines)
