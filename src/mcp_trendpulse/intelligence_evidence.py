"""Source-shape verification and comparable, attributable evidence extracts.

A successful HTTP response is *not* automatically valid evidence: upstreams
can return error envelopes or change schemas while still replying 200.
All projections are observational; no record is treated as purchasing intent.
"""

from __future__ import annotations

from typing import Any


class UnexpectedSourceShape(ValueError):
    """Provider changed its response contract or did not return expected data."""


def _objects(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise UnexpectedSourceShape("Expected a list of records")
    return [row for row in rows[:20] if isinstance(row, dict)]


def evidence_projection(source: str, payload: Any) -> dict[str, Any]:
    """Validate distinctive source envelopes, then extract a small source sample."""
    if source in {"cordis", "cellar"}:
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), dict):
            raise UnexpectedSourceShape("Expected SPARQL results object")
        bindings = _objects(payload["results"].get("bindings"))
        rows = [{k: v.get("value") for k, v in row.items()
                 if isinstance(v, dict) and "value" in v} for row in bindings]
        return {"record_count": len(rows), "sample": rows, "unit": "SPARQL bindings"}
    if source == "cfpb":
        if not isinstance(payload, dict) or not isinstance(payload.get("hits"), dict):
            raise UnexpectedSourceShape("Expected CFPB OpenSearch hits")
        hits = _objects(payload["hits"].get("hits"))
        rows = []
        for hit in hits:
            entry = hit.get("_source", {})
            if not isinstance(entry, dict):
                continue
            # Never project removed complaint narratives, or sensitive personal details.
            rows.append({k: entry.get(k) for k in (
                "date_received", "product", "sub_product",
                "issue", "sub_issue", "company", "state"
            ) if k in entry})
        return {"record_count": len(rows), "sample": rows, "unit": "published complaints"}
    if source == "opsi_slovenia":
        if not isinstance(payload, dict) or payload.get("success") is not True:
            raise UnexpectedSourceShape("Expected successful CKAN action response")
        result = payload.get("result", {})
        if not isinstance(result, dict):
            raise UnexpectedSourceShape("CKAN result was not an object")
        rows = _objects(result.get("results"))
        return {
            "record_count": result.get("count", len(rows)),
            "sample": [{k: r.get(k) for k in ("id", "name", "title", "license_id", "metadata_modified")
                        if k in r} for r in rows],
            "unit": "public dataset metadata",
        }
    if source == "copernicus":
        if not isinstance(payload, dict):
            raise UnexpectedSourceShape("Expected STAC catalog JSON")
        rows = _objects(payload.get("collections"))
        return {
            "record_count": len(rows),
            "sample": [{k: r.get(k) for k in ("id", "title", "description") if k in r} for r in rows],
            "unit": "satellite data collections (not climate-model observations)",
        }
    if source == "worldbank":
        if not isinstance(payload, list) or len(payload) != 2 or not isinstance(payload[1], list):
            raise UnexpectedSourceShape("Expected [pagination, values] from World Bank")
        rows = _objects(payload[1])
        return {"record_count": len(rows), "sample": rows, "unit": "official indicator observations"}
    if source in {"gdelt", "github_issues", "usaspending", "openalex", "gleif", "ted",
                  "greenhouse", "ashby", "smartrecruiters", "sec_companyfacts",
                  "sec_companyconcept", "companies_house"}:
        if not isinstance(payload, dict):
            raise UnexpectedSourceShape("Expected JSON object from provider")
        fields = {
            "gdelt": "articles", "github_issues": "items", "usaspending": "results",
            "openalex": "results", "gleif": "data", "ted": "notices",
            "greenhouse": "jobs", "ashby": "jobs", "smartrecruiters": "content",
            "companies_house": "items",
        }
        if source in {"sec_companyfacts", "sec_companyconcept"}:
            if not payload.get("cik") or "entityName" not in payload:
                raise UnexpectedSourceShape("Expected SEC XBRL company identifier and entityName")
            rows = [{"cik": payload["cik"], "entity_name": payload["entityName"]}]
        else:
            rows = _objects(payload.get(fields[source]))
        return {"record_count": len(rows), "sample": rows[:10],
                "unit": "public provider records; no demand validation"}
    if source == "lever":
        rows = _objects(payload)
        return {"record_count": len(rows), "sample": rows[:10], "unit": "public job postings"}
    if source == "eurostat":
        if not isinstance(payload, dict) or not all(k in payload for k in ("id", "value", "size")):
            raise UnexpectedSourceShape("Expected Eurostat JSON-stat dataset")
        return {"record_count": len(payload["value"]) if isinstance(payload["value"], dict) else 0,
                "sample": [{"dataset_dimensions": payload["id"], "size": payload["size"]}],
                "unit": "JSON-stat observations; dimension indexes must be decoded"}
    if source in {"ecb", "epo", "entsoe", "rsshub_local"}:
        if not isinstance(payload, dict) or not (
            ("columns" in payload and "rows" in payload)
            or ("root" in payload and "observations" in payload)
        ):
            raise UnexpectedSourceShape("Expected parsed CSV or XML")
        items = payload.get("rows", payload.get("observations", []))
        return {"record_count": len(items), "sample": items[:10],
                "unit": "provider XML/CSV evidence; no causal claims"}
    if source == "changedetection_local":
        if not isinstance(payload, dict):
            raise UnexpectedSourceShape("Expected local change monitor JSON")
        return {"record_count": len(payload),
                "sample": [{"watch_id": x} for x in list(payload)[:20]],
                "unit": "local watch configurations"}
    raise UnexpectedSourceShape("No validated response schema for source")
