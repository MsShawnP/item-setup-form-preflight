"""Orchestrator for Pyodide — glues file parsing, column matching, and validation.

This module is written to Pyodide's virtual filesystem and called from the
Web Worker. It bridges the JavaScript ↔ Python boundary by accepting and
returning JSON strings.

Note on imports: Inside Pyodide the engine package lives at /home/pyodide/engine/
with rewritten imports (no 'src.' prefix). The worker's FS-write step
patches __init__.py and other files accordingly before this module runs.
"""

from __future__ import annotations

import json

from engine.file_parser import parse_file
from engine.schema_loader import load_schema
from engine.column_matcher import match_columns
from engine.validators import validate_product

# Module-level cache: parsed rows survive between match and validate calls
# so the file doesn't need to be re-sent.
_cached_parse = None  # ParseResult from the match step


def do_match(file_path: str, filename: str, partner: str) -> str:
    """Parse a dropped file, load the partner schema, and run column matching.

    Args:
        file_path: Path to the file on Pyodide's virtual FS.
        filename: Original filename (for extension detection).
        partner: Partner key (walmart, costco, unfi, kehe).

    Returns:
        JSON string with keys: mapping, unmatchedHeaders, unmatchedFields,
        rowCount, headers.
    """
    global _cached_parse

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    parsed = parse_file(file_bytes, filename)
    _cached_parse = parsed

    schema_path = f"/home/pyodide/schemas/{partner}.yaml"
    schema = load_schema(schema_path)

    result = match_columns(parsed.headers, schema)

    mapping = []
    for m in result.matches:
        mapping.append({
            "schemaField": m.schema_field,
            "uploadedHeader": m.uploaded_header,
            "confidence": m.confidence,
            "status": m.status.value,
            "candidates": m.candidates,
        })

    return json.dumps({
        "mapping": mapping,
        "unmatchedHeaders": result.unmatched_headers,
        "unmatchedFields": result.unmatched_fields,
        "rowCount": parsed.row_count,
        "headers": parsed.headers,
    })


def do_validate(mapping_json: str, partner: str) -> str:
    """Apply confirmed column mapping and run four-tier validation.

    Uses the cached parse result from the most recent do_match call.

    Args:
        mapping_json: JSON string — dict mapping schema field names to
            uploaded header names. Example: {"upc": "UPC Code", "brand": "Brand Name"}
        partner: Partner key.

    Returns:
        JSON string with keys: results (per-row), summary.
    """
    if _cached_parse is None:
        return json.dumps({"error": "No file parsed yet. Run match first."})

    mapping = json.loads(mapping_json)

    schema_path = f"/home/pyodide/schemas/{partner}.yaml"
    schema = load_schema(schema_path)

    # Build reverse mapping: uploaded_header -> schema_field
    header_to_field = {v: k for k, v in mapping.items() if v is not None}

    per_row_results = []

    for row_idx, row in enumerate(_cached_parse.rows):
        # Remap the row: translate uploaded headers to schema field names
        remapped = {}
        for header, value in row.items():
            if header in header_to_field:
                remapped[header_to_field[header]] = value
            else:
                # Keep unmapped fields as-is (they won't match schema
                # fields, so the validator will just ignore them)
                remapped[header] = value

        result = validate_product(remapped, schema)

        errors = []
        for e in result.errors:
            errors.append({
                "field": e.field,
                "errorType": e.error_type.value,
                "trigger": e.trigger,
                "severity": e.severity.value,
                "message": e.message,
            })

        # Try to find an identifier for this row
        sku_label = _find_sku_label(remapped, row_idx)

        per_row_results.append({
            "rowIndex": row_idx,
            "skuLabel": sku_label,
            "verdict": result.verdict,
            "errors": errors,
            "fieldsChecked": result.fields_checked,
            "passCount": result.pass_count,
            "failCount": result.fail_count,
            "tierSummary": result.tier_summary,
        })

    # Aggregate summary
    total = len(per_row_results)
    passing = sum(1 for r in per_row_results if r["verdict"] == "PASS")
    failing = total - passing

    # Most common failure types
    error_type_counts: dict[str, int] = {}
    for r in per_row_results:
        for e in r["errors"]:
            key = e["errorType"]
            error_type_counts[key] = error_type_counts.get(key, 0) + 1

    # Most common failing fields
    field_counts: dict[str, int] = {}
    for r in per_row_results:
        for e in r["errors"]:
            key = e["field"]
            field_counts[key] = field_counts.get(key, 0) + 1

    top_failing_fields = sorted(
        field_counts.items(), key=lambda x: x[1], reverse=True
    )[:10]

    summary = {
        "totalRows": total,
        "passing": passing,
        "failing": failing,
        "errorTypeCounts": error_type_counts,
        "topFailingFields": [
            {"field": f, "count": c} for f, c in top_failing_fields
        ],
    }

    return json.dumps({"results": per_row_results, "summary": summary})


def _find_sku_label(row: dict, row_idx: int) -> str:
    """Find a human-readable identifier for a row.

    Tries common field names in priority order. Falls back to row number.
    """
    for candidate in (
        "product_name", "product_description", "upc", "gtin",
        "brand", "item_name", "description",
    ):
        val = row.get(candidate)
        if val is not None and str(val).strip():
            label = str(val).strip()
            # Truncate long names
            if len(label) > 60:
                label = label[:57] + "..."
            return label

    return f"Row {row_idx + 1}"
