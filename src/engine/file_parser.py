"""Parse Excel (.xlsx) and CSV files into headers + row dicts.

Accepts raw file bytes and returns a ParseResult with column headers
and data rows as list-of-dicts, ready for the column matcher and
validation engine.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ParseResult:
    """Output of a file parse operation."""

    headers: list[str]
    rows: list[dict[str, str | None]]
    row_count: int
    format: str  # "csv" or "xlsx"


class ParseError(Exception):
    """Raised when a file cannot be parsed."""


def parse_file(file_bytes: bytes, filename: str) -> ParseResult:
    """Auto-detect format from filename extension and parse.

    Args:
        file_bytes: Raw file content.
        filename: Original filename (used for extension detection).

    Returns:
        ParseResult with headers and rows.

    Raises:
        ParseError: If the file is empty, unreadable, or has an
            unsupported extension.
    """
    lower = filename.lower().strip()
    if lower.endswith(".xlsx"):
        return parse_excel(file_bytes)
    if lower.endswith(".csv"):
        return parse_csv(file_bytes)
    raise ParseError(
        f"Unsupported file extension: '{filename}'. "
        "Expected .csv or .xlsx."
    )


def parse_csv(file_bytes: bytes) -> ParseResult:
    """Parse CSV bytes into headers and row dicts.

    Handles utf-8-sig encoding (BOM from Excel exports) and falls
    back to latin-1 for non-UTF8 files.

    Args:
        file_bytes: Raw CSV file content.

    Returns:
        ParseResult with format="csv".

    Raises:
        ParseError: If the file is empty or contains no headers.
    """
    if not file_bytes or file_bytes.strip() == b"":
        raise ParseError("File is empty.")

    text = _decode_bytes(file_bytes)
    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None:
        raise ParseError("CSV file contains no headers.")

    headers = [h.strip() for h in reader.fieldnames]

    rows: list[dict[str, str | None]] = []
    for row in reader:
        cleaned: dict[str, str | None] = {}
        for header in headers:
            raw_val = row.get(header)
            if raw_val is None or raw_val.strip() == "":
                cleaned[header] = None
            else:
                cleaned[header] = raw_val.strip()
        rows.append(cleaned)

    return ParseResult(
        headers=headers,
        rows=rows,
        row_count=len(rows),
        format="csv",
    )


def parse_excel(file_bytes: bytes) -> ParseResult:
    """Parse Excel (.xlsx) bytes into headers and row dicts.

    Reads the first sheet only. First row is treated as headers.
    Date cells are converted to ISO-format strings.

    Args:
        file_bytes: Raw .xlsx file content.

    Returns:
        ParseResult with format="xlsx".

    Raises:
        ParseError: If the file is empty, unreadable, or has no
            header row.
    """
    import openpyxl

    if not file_bytes:
        raise ParseError("File is empty.")

    try:
        wb = openpyxl.load_workbook(
            io.BytesIO(file_bytes),
            read_only=True,
            data_only=True,
        )
    except Exception as exc:
        raise ParseError(f"Cannot read Excel file: {exc}") from exc

    ws = wb.active
    if ws is None:
        wb.close()
        raise ParseError("Excel workbook has no active sheet.")

    row_iter = ws.iter_rows()

    # First row = headers
    try:
        header_row = next(row_iter)
    except StopIteration:
        wb.close()
        raise ParseError("Excel file contains no data.")

    headers: list[str] = []
    for cell in header_row:
        val = cell.value
        if val is None:
            # Stop at first blank header — trailing empty columns are noise
            break
        headers.append(str(val).strip())

    if not headers:
        wb.close()
        raise ParseError("Excel file contains no headers in the first row.")

    # Remaining rows = data (skip trailing blank rows)
    rows: list[dict[str, str | None]] = []
    for row in row_iter:
        record: dict[str, str | None] = {}
        has_data = False
        for idx, header in enumerate(headers):
            if idx < len(row):
                val = _cell_to_string(row[idx].value)
                record[header] = val
                if val is not None:
                    has_data = True
            else:
                record[header] = None
        if has_data:
            rows.append(record)

    wb.close()

    return ParseResult(
        headers=headers,
        rows=rows,
        row_count=len(rows),
        format="xlsx",
    )


def _decode_bytes(raw: bytes) -> str:
    """Decode file bytes, handling BOM and non-UTF8 gracefully."""
    # Try utf-8-sig first (handles BOM if present, works for plain UTF-8 too)
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass

    # Fall back to latin-1 which never throws (every byte is valid)
    return raw.decode("latin-1")


def _cell_to_string(value: object) -> str | None:
    """Convert an openpyxl cell value to a string.

    Dates become ISO-format strings. None stays None. Everything
    else becomes str().strip().
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.isoformat()

    text = str(value).strip()
    if text == "":
        return None
    return text
