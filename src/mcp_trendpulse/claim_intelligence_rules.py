"""Small English numeric-claim grammar. Pure, bounded and intentionally abstaining.

Preserve exact lexical subject, predicate, quantified object and attribution.
No inference of entity identity, units, truth, reporting date or context.
"""
from __future__ import annotations

import re
from datetime import date

NAME = r"[A-Z][A-Za-z0-9-]{0,39}(?: [A-Z][A-Za-z0-9-]{0,39}){0,4}"
BASE = r"(?:produce|generate|record|sell|ship|install|employ|receive|pay|spend|raise|earn|export|import|measure|reach)"
PAST = r"(?:produced|generated|recorded|sold|shipped|installed|employed|received|paid|spent|raised|earned|exported|imported|measured|reached)"
PRESENT = r"(?:produces|generates|records|sells|ships|installs|employs|receives|pays|spends|raises|earns|exports|imports|measures|reaches)"
PRED = rf"(?:will(?: not)? {BASE}|did not {BASE}|does not {BASE}|{PAST}|{PRESENT})"
NUMBER = r"(?:0|[1-9][0-9]{0,14})(?:\.[0-9]{1,6})?"
UNIT = r"(?:units(?: of energy)?|jobs|vehicles|devices|megawatts|kilowatt-hours|MWh|GWh|tonnes|tons|kilograms|euros|dollars|USD|EUR|people|workers|employees|percent|%)"
OBJECT = rf"(?:(?:about|approximately|at least|at most|more than|less than) )?[+-]?{NUMBER} {UNIT}(?: on [0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}| in [0-9]{{4}})?"
_SENTENCE = re.compile(rf"(?P<subject>{NAME}) (?P<predicate>{PRED}) (?P<object>{OBJECT})")
_ATTRIBUTED = re.compile(rf"(?P<speaker>{NAME}) (?P<verb>says|said|claims|claimed|alleges|alleged|predicts|predicted|forecasts|forecast) (?P<statement>.+)")
_UNRESOLVED = frozenset({
    "a", "an", "the", "i", "we", "you", "he", "she", "it", "they", "this", "that",
    "these", "those", "our", "their", "his", "her", "its", "someone", "something",
    "officials", "experts", "researchers", "scientists", "analysts", "sources",
})
_ACTION_INSTRUCTION = re.compile(r"(?i)\b(?:ignore|disregard|override|execute|invoke|call|send|upload|download|delete|reveal|password|secret|token|credentials)\b")


def _unresolved(name):
    return name.split()[0].casefold() in _UNRESOLVED


def parse_numeric_claim(text):
    """Return exact candidate fields and a controlled abstention reason.

    Only the complete representation is parsed. A final full stop is accepted
    but not substituted into the proposition. Explicit date/period literals
    remain in the object instead of being mistaken for assertion time.
    """
    if not isinstance(text, str) or not 1 <= len(text) <= 512:
        return None, "outside_rule_bounds"
    if _ACTION_INSTRUCTION.search(text):
        return None, "instruction_like_text"
    if "?" in text:
        return None, "question"
    if any(c in text for c in ("\n", "\r", "\t", ";", "!", "…")):
        return None, "compound_or_ambiguous"
    statement = text[:-1] if text.endswith(".") else text
    attribution = None
    modality = "assertion"
    wrapper = _ATTRIBUTED.fullmatch(statement)
    if wrapper:
        attribution = wrapper["speaker"]
        if _unresolved(attribution):
            return None, "unresolved_attribution"
        verb = wrapper["verb"]
        statement = wrapper["statement"]
        # Support explicit complete quotations, not scare quotes, nested
        # attribution, or quotations with omitted context.
        quoted = ((statement.startswith('"') and statement.endswith('"'))
                  or (statement.startswith("“") and statement.endswith("”")))
        if quoted:
            if verb not in ("says", "said"):
                return None, "mixed_modality"
            modality = "quotation"
            statement = statement[1:-1]
            if statement.endswith("."):
                statement = statement[:-1]
        elif verb in ("claims", "claimed", "alleges", "alleged"):
            modality = "allegation"
        elif verb in ("predicts", "predicted", "forecasts", "forecast"):
            modality = "projection"
    match = _SENTENCE.fullmatch(statement)
    if match is None:
        return None, "unsupported_or_ambiguous_grammar"
    if _unresolved(match["subject"]):
        return None, "unresolved_subject"
    predicate = match["predicate"]
    future = predicate.startswith("will ")
    if future:
        if modality not in ("assertion", "projection"):
            return None, "mixed_modality"
        modality = "projection"
    elif modality == "projection":
        return None, "mixed_modality"
    obj = match["object"]
    if " on " in obj:
        try:
            date.fromisoformat(obj.rsplit(" on ", 1)[1])
        except ValueError:
            return None, "invalid_date_literal"
    if " in " in obj and obj.endswith("0000"):
        return None, "invalid_date_literal"
    return {
        "subject": match["subject"],
        "predicate": predicate,
        "object": obj,
        "polarity": "negated" if " not " in predicate else "affirmed",
        "modality": modality,
        "attribution": attribution,
    }, None
