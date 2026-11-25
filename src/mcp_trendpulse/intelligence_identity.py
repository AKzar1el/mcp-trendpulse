"""Conservative exact bibliographic identifiers; never fuzzy entity joins."""
from __future__ import annotations

import re

_DOI = re.compile(r"10\.[0-9]{4,9}/[a-z0-9._;()/:-]{1,110}", re.ASCII)


def canonical_doi(value: object) -> str | None:
    """Normalize a bounded, common DOI subset without following any URLs."""
    if not isinstance(value, str) or len(value) > 160:
        return None
    doi = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
            break
    return doi if _DOI.fullmatch(doi) else None
