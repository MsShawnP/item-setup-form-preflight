"""Item Setup Pre-flight — CLI entry point.

Validates a product master CSV or Excel file against a partner schema
and reports which fields will bounce. Uses the same four-tier engine
as the browser tool.
"""

from __future__ import annotations

import json
import pathlib
import sys
from dataclasses import asdict

import click

from src.engine.column_matcher import MatchResult, MatchStatus, match_columns
from src.engine.file_parser import ParseError, parse_file
from src.engine.models import Severity, ValidationResult
from src.engine.schema_loader import load_schema
from src.engine.validators import validate_product

_PARTNERS = ["walmart", "costco", "unfi", "kehe"]


def _get_schema_path(partner: str) -> pathlib.Path:
    """Resolve schema path relative to the project root."""
    root = pathlib.Path(__file__).parent.parent.parent
    return root / "src" / "schemas" / f"{partner}.yaml"


def _print_mapping(mapping: MatchResult) -> None:
    """Print column mapping table with colored status."""
    click.echo()
    click.echo(click.style("Column Mapping:", bold=True))
    for m in mapping.matches:
        if m.status == MatchStatus.MATCHED:
            header_display = f'"{m.uploaded_header}"'
            conf_pct = f"{m.confidence * 100:.0f}%"
            line = f"  {m.schema_field:<25} <- {header_display:<30} ({m.status}, {conf_pct})"
            click.echo(line)
        elif m.status == MatchStatus.AMBIGUOUS:
            candidates_str = ", ".join(f'"{c}"' for c in m.candidates)
            line = f"  {m.schema_field:<25} <- {click.style('AMBIGUOUS', fg='yellow')} (candidates: {candidates_str})"
            click.echo(line)
        else:
            line = f"  {m.schema_field:<25} <- {click.style('---', fg='red'):<30} (UNMATCHED)"
            click.echo(line)


def _remap_row(row: dict[str, str | None], mapping: MatchResult) -> dict[str, str | None]:
    """Remap a data row from uploaded headers to schema field names.

    For each matched column, copies the value from the uploaded header
    key to the schema field name key so the validation engine sees
    the field names it expects.
    """
    remapped: dict[str, str | None] = {}
    for m in mapping.matches:
        if m.status == MatchStatus.MATCHED and m.uploaded_header is not None:
            remapped[m.schema_field] = row.get(m.uploaded_header)
    return remapped


def _severity_color(severity: Severity) -> str:
    """Map severity to a click color name."""
    if severity == Severity.CRITICAL:
        return "red"
    if severity == Severity.WARNING:
        return "yellow"
    return "blue"


def _identify_row(row: dict[str, str | None], row_num: int) -> str:
    """Build a display label for a row using product_name or row number."""
    # Try common name fields in order of preference
    for key in ("product_name", "brand", "product_description"):
        val = row.get(key)
        if val and str(val).strip():
            return f'"{val}" (row {row_num})'
    return f"Row {row_num}"


def _print_table_results(
    partner_display: str,
    filepath: str,
    row_count: int,
    mapping: MatchResult,
    results: list[tuple[int, dict[str, str | None], ValidationResult]],
) -> None:
    """Print validation results in human-readable table format."""
    click.echo()
    click.echo(click.style(f"Partner: {partner_display}", bold=True))
    click.echo(f"File: {filepath} ({row_count} rows)")

    _print_mapping(mapping)

    pass_count = sum(1 for _, _, r in results if r.verdict == "PASS")
    fail_count = row_count - pass_count

    click.echo()
    click.echo(click.style("Results:", bold=True))
    if pass_count > 0:
        click.echo(click.style(f"  + {pass_count} of {row_count} SKUs ready", fg="green"))
    if fail_count > 0:
        click.echo(click.style(f"  x {fail_count} SKUs with issues", fg="red"))

    # Print per-SKU errors
    for row_num, remapped_row, result in results:
        if result.verdict == "PASS":
            continue

        click.echo()
        label = _identify_row(remapped_row, row_num)
        click.echo(f"  SKU {label}:")
        for err in result.errors:
            color = _severity_color(err.severity)
            severity_tag = click.style(f"  {err.severity:<10}", fg=color)
            click.echo(f"  {severity_tag}{err.field}: {err.message}")

    # Summary by tier
    totals = {"presence": 0, "format": 0, "conditional": 0, "gtin": 0}
    skus_with = {"presence": set(), "format": set(), "conditional": set(), "gtin": set()}

    for row_num, _, result in results:
        for tier, count in result.tier_summary.items():
            totals[tier] += count
            if count > 0:
                skus_with[tier].add(row_num)

    click.echo()
    click.echo(click.style("Summary:", bold=True))
    click.echo(f"  Presence errors:    {totals['presence']:>4} (across {len(skus_with['presence'])} SKUs)")
    click.echo(f"  Format errors:      {totals['format']:>4} (across {len(skus_with['format'])} SKUs)")
    click.echo(f"  Conditional errors: {totals['conditional']:>4} (across {len(skus_with['conditional'])} SKUs)")
    click.echo(f"  GTIN errors:        {totals['gtin']:>4} (across {len(skus_with['gtin'])} SKUs)")
    click.echo()


def _print_json_results(
    results: list[tuple[int, dict[str, str | None], ValidationResult]],
) -> None:
    """Print validation results as JSON matching the engine error contract."""
    output = []
    for row_num, _, result in results:
        output.append({
            "row": row_num,
            "verdict": result.verdict,
            "fields_checked": result.fields_checked,
            "pass_count": result.pass_count,
            "fail_count": result.fail_count,
            "tier_summary": result.tier_summary,
            "errors": [asdict(e) for e in result.errors],
        })
    click.echo(json.dumps(output, indent=2))


@click.group()
def cli() -> None:
    """Item Setup Pre-flight -- validate product master data against retailer schemas."""


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option(
    "--partner", "-p",
    required=True,
    type=click.Choice(_PARTNERS, case_sensitive=False),
    help="Target partner schema.",
)
@click.option(
    "--format", "-f",
    "output_format",
    default="table",
    type=click.Choice(["table", "json"]),
    help="Output format (default: table).",
)
@click.option(
    "--accept-mapping",
    is_flag=True,
    help="Skip column mapping confirmation prompt.",
)
def audit(file: str, partner: str, output_format: str, accept_mapping: bool) -> None:
    """Validate a product master file against a partner schema."""
    # 1. Load the partner schema
    schema_path = _get_schema_path(partner.lower())
    if not schema_path.exists():
        click.echo(
            click.style(f"Error: Schema file not found: {schema_path}", fg="red"),
            err=True,
        )
        sys.exit(1)

    try:
        schema = load_schema(str(schema_path))
    except Exception as exc:
        click.echo(
            click.style(f"Error loading schema: {exc}", fg="red"),
            err=True,
        )
        sys.exit(1)

    # 2. Parse the input file
    filepath = pathlib.Path(file)
    try:
        file_bytes = filepath.read_bytes()
        parsed = parse_file(file_bytes, filepath.name)
    except ParseError as exc:
        click.echo(
            click.style(f"Error parsing file: {exc}", fg="red"),
            err=True,
        )
        sys.exit(1)
    except Exception as exc:
        click.echo(
            click.style(f"Error reading file: {exc}", fg="red"),
            err=True,
        )
        sys.exit(1)

    if parsed.row_count == 0:
        click.echo("File contains headers but no data rows.")
        sys.exit(1)

    # 3. Run column matching
    mapping = match_columns(parsed.headers, schema)

    # 4. Column mapping confirmation
    if not accept_mapping:
        _print_mapping(mapping)
        click.echo()
        if not click.confirm("Accept this mapping?", default=True):
            click.echo("Mapping rejected. Review your file headers and try again.")
            sys.exit(1)

    # 5. Validate each row
    results: list[tuple[int, dict[str, str | None], ValidationResult]] = []
    for idx, row in enumerate(parsed.rows):
        row_num = idx + 2  # 1-indexed, +1 for header row
        remapped = _remap_row(row, mapping)
        result = validate_product(remapped, schema)
        results.append((row_num, remapped, result))

    # 6. Output results
    has_failures = any(r.verdict == "FAIL" for _, _, r in results)

    if output_format == "json":
        _print_json_results(results)
    else:
        _print_table_results(
            partner_display=schema.display_name,
            filepath=str(filepath),
            row_count=parsed.row_count,
            mapping=mapping,
            results=results,
        )

    # Exit code: 0 = all pass, 2 = validation failures found
    sys.exit(2 if has_failures else 0)
