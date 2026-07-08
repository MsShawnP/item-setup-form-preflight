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

from engine.schema_loader import load_schema
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
    from engine.file_parser import parse_file
    from engine.column_matcher import match_columns

    global _cached_parse

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    parsed = parse_file(file_bytes, filename)
    _cached_parse = parsed

    schema_path = f"/home/pyodide/schemas/{partner}.yaml"
    schema = load_schema(schema_path)

    result = match_columns(parsed.headers, schema, parsed.rows)

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
    mapped_fields = set(header_to_field.values())

    per_row_results = []

    for row_idx, row in enumerate(_cached_parse.rows):
        remapped = {}
        for header, value in row.items():
            if header in header_to_field:
                remapped[header_to_field[header]] = value
            elif header not in mapped_fields:
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


def do_diff() -> str:
    """Compare partner schemas pairwise and return structured diff data.

    Computes two comparisons:
    - Retailer pair: Walmart vs Costco
    - Distributor pair: UNFI vs KeHE

    For each pair, returns shared required fields (with format comparison),
    fields unique to each partner, GTIN hierarchy comparison, conditional
    rule comparison, and overlap percentage.

    Returns:
        JSON string with keys: retailer_pair, distributor_pair, annotation.
    """
    schemas = {}
    for partner in ("walmart", "costco", "unfi", "kehe"):
        schema_path = f"/home/pyodide/schemas/{partner}.yaml"
        schemas[partner] = load_schema(schema_path)

    retailer_pair = _compare_pair(schemas["walmart"], schemas["costco"])
    distributor_pair = _compare_pair(schemas["unfi"], schemas["kehe"])

    # Data-derived channel-type annotation
    annotation = _compute_channel_annotation(retailer_pair, distributor_pair)

    return json.dumps({
        "retailer_pair": retailer_pair,
        "distributor_pair": distributor_pair,
        "annotation": annotation,
    })


def _compare_pair(schema_a, schema_b) -> dict:
    """Compare two partner schemas and return structured diff data."""
    # Build field lookup dicts: field_name -> FieldSpec
    fields_a = {f.name: f for f in schema_a.required_fields}
    fields_b = {f.name: f for f in schema_b.required_fields}

    names_a = set(fields_a.keys())
    names_b = set(fields_b.keys())

    shared_names = names_a & names_b
    unique_a_names = names_a - names_b
    unique_b_names = names_b - names_a

    # Shared fields with format comparison
    shared_fields = []
    for name in sorted(shared_names):
        fa = fields_a[name]
        fb = fields_b[name]
        format_match = (fa.format_pattern == fb.format_pattern)
        entry = {
            "name": name,
            "format_a": fa.format_description or "(no format)",
            "format_b": fb.format_description or "(no format)",
            "pattern_a": fa.format_pattern,
            "pattern_b": fb.format_pattern,
            "format_match": format_match,
        }
        shared_fields.append(entry)

    # Unique fields
    unique_a = []
    for name in sorted(unique_a_names):
        f = fields_a[name]
        unique_a.append({
            "name": name,
            "format_description": f.format_description,
            "format_pattern": f.format_pattern,
        })

    unique_b = []
    for name in sorted(unique_b_names):
        f = fields_b[name]
        unique_b.append({
            "name": name,
            "format_description": f.format_description,
            "format_pattern": f.format_pattern,
        })

    # GTIN hierarchy comparison
    gtin_comparison = {
        "a_level": schema_a.gtin_hierarchy.expected_level,
        "a_formats": schema_a.gtin_hierarchy.expected_formats,
        "b_level": schema_b.gtin_hierarchy.expected_level,
        "b_formats": schema_b.gtin_hierarchy.expected_formats,
        "level_match": (
            schema_a.gtin_hierarchy.expected_level
            == schema_b.gtin_hierarchy.expected_level
        ),
        "formats_match": (
            set(schema_a.gtin_hierarchy.expected_formats)
            == set(schema_b.gtin_hierarchy.expected_formats)
        ),
    }

    # Conditional rule comparison
    def _rules_key(rule):
        return (rule.trigger_field, rule.trigger_value)

    rules_a = {_rules_key(r): r for r in schema_a.conditional_rules}
    rules_b = {_rules_key(r): r for r in schema_b.conditional_rules}

    rules_a_keys = set(rules_a.keys())
    rules_b_keys = set(rules_b.keys())

    shared_rules = []
    for key in sorted(rules_a_keys & rules_b_keys):
        ra = rules_a[key]
        rb = rules_b[key]
        shared_rules.append({
            "trigger_field": ra.trigger_field,
            "trigger_value": ra.trigger_value,
            "required_a": ra.required_fields,
            "required_b": rb.required_fields,
            "fields_match": (
                set(ra.required_fields) == set(rb.required_fields)
            ),
        })

    unique_rules_a = []
    for key in sorted(rules_a_keys - rules_b_keys):
        r = rules_a[key]
        unique_rules_a.append({
            "trigger_field": r.trigger_field,
            "trigger_value": r.trigger_value,
            "required_fields": r.required_fields,
        })

    unique_rules_b = []
    for key in sorted(rules_b_keys - rules_a_keys):
        r = rules_b[key]
        unique_rules_b.append({
            "trigger_field": r.trigger_field,
            "trigger_value": r.trigger_value,
            "required_fields": r.required_fields,
        })

    conditional_comparison = {
        "shared_rules": shared_rules,
        "unique_a": unique_rules_a,
        "unique_b": unique_rules_b,
    }

    # Overlap percentage
    total_unique_fields = len(names_a | names_b)
    overlap_pct = (
        round(len(shared_names) / total_unique_fields * 100, 1)
        if total_unique_fields > 0
        else 0.0
    )

    return {
        "partner_a": schema_a.display_name,
        "partner_b": schema_b.display_name,
        "partner_a_key": schema_a.partner,
        "partner_b_key": schema_b.partner,
        "total_a": len(names_a),
        "total_b": len(names_b),
        "shared_count": len(shared_names),
        "unique_a_count": len(unique_a_names),
        "unique_b_count": len(unique_b_names),
        "overlap_pct": overlap_pct,
        "shared_fields": shared_fields,
        "unique_a": unique_a,
        "unique_b": unique_b,
        "gtin_comparison": gtin_comparison,
        "conditional_comparison": conditional_comparison,
    }


def _compute_channel_annotation(
    retailer_pair: dict, distributor_pair: dict
) -> str:
    """Generate a data-derived annotation about channel-type patterns.

    Compares overlap percentages between the retailer and distributor
    pairs and describes whatever pattern actually emerges.
    """
    r_pct = retailer_pair["overlap_pct"]
    d_pct = distributor_pair["overlap_pct"]
    r_a = retailer_pair["partner_a"]
    r_b = retailer_pair["partner_b"]
    d_a = distributor_pair["partner_a"]
    d_b = distributor_pair["partner_b"]

    diff = d_pct - r_pct

    if diff > 10:
        return (
            f"{d_a} and {d_b} share {d_pct}% of their required fields "
            f"vs. {r_pct}% for {r_a} and {r_b} — a common pattern among "
            f"broadline distributors whose warehouse-receiving workflows "
            f"converge on similar data requirements."
        )
    elif diff < -10:
        return (
            f"{r_a} and {r_b} share {r_pct}% of their required fields "
            f"vs. {d_pct}% for {d_a} and {d_b}. Retailer schemas show "
            f"higher convergence here than the distributor pair."
        )
    else:
        return (
            f"Both pairs show similar overlap: {r_a}/{r_b} at {r_pct}% "
            f"and {d_a}/{d_b} at {d_pct}%. Neither channel type shows "
            f"markedly higher schema convergence in this sample."
        )


def do_validate_rows(rows_json: str, mapping_json: str, partner: str) -> str:
    """Validate pre-parsed rows against a partner schema.

    Called from the JS-side worker when file parsing and column matching
    are handled in JavaScript. Receives rows and mapping as JSON strings.

    Args:
        rows_json: JSON string — list of dicts (header -> value).
        mapping_json: JSON string — dict mapping schema field names to
            uploaded header names.
        partner: Partner key.

    Returns:
        JSON string with keys: results (per-row), summary.
    """
    rows = json.loads(rows_json)
    mapping = json.loads(mapping_json)

    schema_path = f"/home/pyodide/schemas/{partner}.yaml"
    schema = load_schema(schema_path)

    header_to_field = {v: k for k, v in mapping.items() if v is not None}

    per_row_results = []

    mapped_fields = set(header_to_field.values())

    for row_idx, row in enumerate(rows):
        remapped = {}
        for header, value in row.items():
            if header in header_to_field:
                remapped[header_to_field[header]] = value
            elif header not in mapped_fields:
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

    total = len(per_row_results)
    passing = sum(1 for r in per_row_results if r["verdict"] == "PASS")
    failing = total - passing

    error_type_counts: dict[str, int] = {}
    for r in per_row_results:
        for e in r["errors"]:
            key = e["errorType"]
            error_type_counts[key] = error_type_counts.get(key, 0) + 1

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
