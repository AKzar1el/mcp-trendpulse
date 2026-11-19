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
        raise UnexpectedSourceShape("Expected provider record array, not an error or changed schema")
    if any(not isinstance(row, dict) for row in rows[:20]):
        raise UnexpectedSourceShape("Provider record array contains a malformed entry")
    return rows[:20]


def evidence_projection(source: str, payload: Any) -> dict[str, Any]:
    """Validate distinctive source envelopes, then extract a small source sample."""
    if isinstance(payload, dict):
        # Some upstreams reply 200 with both an empty collection and an error
        # envelope. Such a response must NEVER imply that demand is zero.
        status = payload.get("status")
        failed_status = isinstance(status, str) and status.lower() in {
            "error", "failed", "failure",
        }
        if failed_status or any(payload.get(key) for key in ("error", "errors", "fault")):
            raise UnexpectedSourceShape("Provider returned an error envelope")
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
            rows.append({
                **({"public_complaint_id": hit["_id"]}
                   if isinstance(hit.get("_id"), str) else {}),
                **{k: entry.get(k) for k in (
                    "date_received", "product", "sub_product",
                    "issue", "sub_issue", "company", "state",
                ) if k in entry},
            })
        return {"record_count": len(rows), "sample": rows, "unit": "published complaints"}
    if source == "copernicus":
        if not isinstance(payload, dict):
            raise UnexpectedSourceShape("Expected STAC collection JSON")
        rows = [payload] if isinstance(payload.get("id"), str) else _objects(payload.get("collections"))
        if not rows:
            raise UnexpectedSourceShape("Missing STAC collection identifier")
        return {"record_count": len(rows),
                "sample": [{k: r.get(k) for k in ("id", "title", "description") if k in r} for r in rows],
                "unit": "satellite data collection (not climate-model observations)"}
    if source == "gdelt_latest":
        if not isinstance(payload, dict) or not isinstance(payload.get("lines"), list):
            raise UnexpectedSourceShape("Expected GDELT batch manifest")
        rows = []
        for line in payload["lines"][:3]:
            if not isinstance(line, str):
                continue
            fields = line.strip().split()
            if len(fields) != 3 or not fields[0].isdigit() or not fields[2].startswith(
                ("http://data.gdeltproject.org/gdeltv2/", "https://data.gdeltproject.org/gdeltv2/")
            ):
                continue
            rows.append({"compressed_bytes": int(fields[0]), "filename": fields[2].rsplit("/", 1)[-1]})
        if not rows:
            raise UnexpectedSourceShape("No valid GDELT batch entries")
        return {"record_count": len(rows), "sample": rows,
                "unit": "15-minute event manifest, not topical news"}
    if source == "greenhouse_job":
        if not isinstance(payload, dict) or "id" not in payload or not payload.get("title"):
            raise UnexpectedSourceShape("Expected one public Greenhouse job description")
        return {"record_count": 1, "sample": [
            {"id": payload["id"], "title": payload["title"],
             "description_present": bool(payload.get("content"))}],
            "unit": "one public job; not purchasing evidence"}
    if source == "worldbank":
        if not isinstance(payload, list) or len(payload) != 2 or not isinstance(payload[1], list):
            raise UnexpectedSourceShape("Expected [pagination, values] from World Bank")
        rows = _objects(payload[1])
        return {"record_count": len(rows), "sample": rows, "unit": "official indicator observations"}
    if source in {"github_issues", "usaspending", "openalex", "gleif", "ted",
                  "greenhouse", "ashby", "smartrecruiters", "sec_companyfacts",
                  "sec_companyconcept", "companies_house"}:
        if not isinstance(payload, dict):
            raise UnexpectedSourceShape("Expected JSON object from provider")
        fields = {
            "github_issues": "items", "usaspending": "results",
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
    if source == "rsshub_local":
        if not isinstance(payload, dict) or payload.get("root") not in {"rss", "feed", "RDF"}:
            raise UnexpectedSourceShape("RSSHub did not return RSS/Atom feed XML")
        items = payload.get("observations")
        if not isinstance(items, list) or not any(
            isinstance(x, dict) and x.get("element") == "title" for x in items
        ):
            raise UnexpectedSourceShape("RSSHub feed has no validated title")
        return {"record_count": len(items), "sample": items[:10],
                "unit": "self-hosted RSS/Atom text observations; not demand evidence"}
    if source == "entsoe":
        # ENTSO-E can return a well-formed XML acknowledgement for invalid
        # requests or absent publication. It is NOT electricity-load data.
        if not isinstance(payload, dict) or payload.get("root") != "GL_MarketDocument":
            raise UnexpectedSourceShape(
                "ENTSO-E did not return a generation/load MarketDocument"
            )
        items = payload.get("observations")
        if (not isinstance(items, list)
                or not any(
                    isinstance(row, dict) and row.get("element") == "quantity"
                    and isinstance(row.get("text"), str)
                    for row in items
                )):
            raise UnexpectedSourceShape("ENTSO-E load document has no measured quantities")
        return {"record_count": len(items), "sample": items[:10],
                "unit": "actual electricity load XML text; not a business opportunity"}
    if source in {"ecb", "epo"}:
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
