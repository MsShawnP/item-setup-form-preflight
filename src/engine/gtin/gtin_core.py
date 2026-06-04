"""
GTIN Validator — Core Validation Primitives

Vendored from gtin-validator for use in the pre-flight engine.
Stripped of pandas, batch processing, retailer profiles, and scoring —
this file contains only the GS1 validation logic needed for single-GTIN
and hierarchy checks.

References:
    - GS1 General Specifications S7.9 (check digit algorithm)
    - GS1 US GTIN Allocation Rules
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severity(Enum):
    """Issue severity levels, ordered by impact on retailer submissions."""
    CRITICAL = "Critical"
    WARNING = "Warning"
    INFO = "Info"


class GTINType(Enum):
    """Standard GTIN formats recognized by GS1."""
    GTIN_8 = "GTIN-8"
    GTIN_12 = "GTIN-12 (UPC-A)"
    GTIN_13 = "GTIN-13 (EAN)"
    GTIN_14 = "GTIN-14 (ITF-14)"
    UNKNOWN = "Unknown"


@dataclass
class Issue:
    """A single validation issue found on a GTIN."""
    severity: Severity
    code: str
    message: str
    recommendation: str
    retailer_impact: str


@dataclass
class GTINResult:
    """Complete validation result for a single GTIN."""
    raw_input: str
    cleaned: str
    row_number: int
    is_valid: bool
    gtin_type: GTINType
    issues: list[Issue] = field(default_factory=list)
    corrected_value: str | None = None
    company_prefix: str | None = None
    indicator_digit: str | None = None
    check_digit_expected: str | None = None

    @property
    def has_critical(self) -> bool:
        """True if any issue is severity CRITICAL."""
        return any(i.severity == Severity.CRITICAL for i in self.issues)

    @property
    def has_warning(self) -> bool:
        """True if any issue is severity WARNING."""
        return any(i.severity == Severity.WARNING for i in self.issues)


def calculate_check_digit(digits: str) -> int:
    """
    Calculate a GS1 standard check digit using the mod-10 algorithm.

    Works for GTIN-8, GTIN-12, GTIN-13, and GTIN-14.

    Args:
        digits: All digits EXCEPT the check digit (i.e., N-1 digits).

    Returns:
        The expected check digit (0-9).

    Reference:
        GS1 General Specifications S7.9.1
    """
    total = sum(
        int(d) * (3 if i % 2 == 0 else 1)
        for i, d in enumerate(reversed(digits))
    )
    return (10 - total % 10) % 10


def identify_gtin_type(length: int) -> GTINType:
    """Map a digit count to the corresponding GTIN format."""
    return {
        8: GTINType.GTIN_8,
        12: GTINType.GTIN_12,
        13: GTINType.GTIN_13,
        14: GTINType.GTIN_14,
    }.get(length, GTINType.UNKNOWN)


def validate_single_gtin(raw: str, row_number: int) -> GTINResult:
    """
    Validate a single GTIN string against GS1 standards.

    Checks performed (in order):
        1. Empty / blank
        2. Non-numeric characters
        3. Valid length (8, 12, 13, or 14 digits)
        4. Check digit (mod-10)
        5. GTIN-14 indicator digit rules
        6. All-zeros placeholder detection
        7. UPC-A -> GTIN-13 format advisory

    Args:
        raw: The raw GTIN string as entered by the user.
        row_number: 1-based row position in the input file.

    Returns:
        A GTINResult with all issues found.
    """
    if not isinstance(raw, str):
        raw = "" if raw is None or (isinstance(raw, float) and raw != raw) else str(raw)
    cleaned = raw.strip().replace("-", "").replace(" ", "")
    result = GTINResult(
        raw_input=raw.strip(),
        cleaned=cleaned,
        row_number=row_number,
        is_valid=True,
        gtin_type=GTINType.UNKNOWN,
    )

    if not cleaned:
        result.is_valid = False
        result.issues.append(Issue(
            severity=Severity.CRITICAL,
            code="EMPTY",
            message="GTIN is empty or blank.",
            recommendation="Provide a valid GTIN for this item.",
            retailer_impact="No retailer will accept an item without a GTIN.",
        ))
        return result

    if not cleaned.isdigit():
        result.is_valid = False
        result.issues.append(Issue(
            severity=Severity.CRITICAL,
            code="NON_NUMERIC",
            message=f"GTIN contains non-numeric characters: '{cleaned}'.",
            recommendation=(
                "Remove all letters, symbols, and spaces. "
                "GTINs are numeric only."
            ),
            retailer_impact="All retailer systems will reject a non-numeric GTIN.",
        ))
        return result

    gtin_type = identify_gtin_type(len(cleaned))
    result.gtin_type = gtin_type

    if gtin_type == GTINType.UNKNOWN:
        result.is_valid = False
        result.issues.append(Issue(
            severity=Severity.CRITICAL,
            code="INVALID_LENGTH",
            message=(
                f"GTIN has {len(cleaned)} digits. "
                "Valid lengths are 8, 12, 13, or 14."
            ),
            recommendation=(
                "Check if digits were truncated or extra digits added. "
                "UPC-A is 12 digits, EAN is 13 digits, ITF-14 is 14 digits."
            ),
            retailer_impact=(
                "No retailer system will recognize "
                "a GTIN with this length."
            ),
        ))
        return result

    payload = cleaned[:-1]
    actual_check = int(cleaned[-1])
    expected_check = calculate_check_digit(payload)
    result.check_digit_expected = str(expected_check)

    if actual_check != expected_check:
        result.is_valid = False
        corrected = payload + str(expected_check)
        result.corrected_value = corrected
        result.issues.append(Issue(
            severity=Severity.CRITICAL,
            code="BAD_CHECK_DIGIT",
            message=(
                f"Check digit is {actual_check}, but should be {expected_check}. "
                f"Corrected GTIN would be {corrected}."
            ),
            recommendation=(
                "This usually means a digit was mistyped or the GTIN was "
                "manually constructed incorrectly. Verify against the original "
                "barcode or GS1 registration."
            ),
            retailer_impact=(
                "Walmart, Costco, and 1WorldSync all validate check digits. "
                "This GTIN will be rejected on submission."
            ),
        ))

    if gtin_type == GTINType.GTIN_14:
        indicator = cleaned[0]
        result.indicator_digit = indicator
        if indicator == "0":
            result.issues.append(Issue(
                severity=Severity.INFO,
                code="INDICATOR_ZERO",
                message=(
                    "GTIN-14 has indicator digit 0, which means this is a "
                    "base unit (each) expressed in 14-digit format."
                ),
                recommendation=(
                    "This is valid but confirm it's not "
                    "meant to be a case-level GTIN."
                ),
                retailer_impact=(
                    "Some systems may expect "
                    "GTIN-12 or GTIN-13 for eaches."
                ),
            ))
        elif indicator == "9":
            result.issues.append(Issue(
                severity=Severity.WARNING,
                code="INDICATOR_NINE",
                message=(
                    "GTIN-14 has indicator digit 9, "
                    "reserved for variable measure items."
                ),
                recommendation=(
                    "Variable measure GTINs are for items sold by weight or volume. "
                    "If this is a fixed-weight consumer product, "
                    "the indicator digit is wrong."
                ),
                retailer_impact=(
                    "Retailers handle variable measure items differently. "
                    "Using indicator 9 on a fixed item will cause processing errors."
                ),
            ))
        elif indicator in "12345678":
            result.issues.append(Issue(
                severity=Severity.INFO,
                code="CASE_LEVEL",
                message=(
                    f"GTIN-14 with indicator digit {indicator} — this identifies "
                    f"a packaging level (case/inner pack/pallet)."
                ),
                recommendation=(
                    "Verify this GTIN corresponds to the correct "
                    "packaging level in your hierarchy."
                ),
                retailer_impact=(
                    "Walmart requires unique GTINs "
                    "at each packaging level."
                ),
            ))

    if cleaned == "0" * len(cleaned):
        result.is_valid = False
        result.issues.append(Issue(
            severity=Severity.CRITICAL,
            code="ALL_ZEROS",
            message="GTIN is all zeros — this is a placeholder, not a real GTIN.",
            recommendation="Replace with a valid GTIN from your GS1 registration.",
            retailer_impact="No retailer will accept an all-zero GTIN.",
        ))

    if gtin_type == GTINType.GTIN_12:
        result.issues.append(Issue(
            severity=Severity.INFO,
            code="UPC_NOT_GTIN13",
            message=(
                "This is a 12-digit UPC-A. Some systems require the 13-digit "
                "GTIN-13 format (with a leading zero). Your GTIN-13 equivalent "
                f"would be 0{cleaned}."
            ),
            recommendation=(
                "1WorldSync, European retailers, and some data pools expect "
                "GTIN-13 format. Verify which format your trading partner "
                "requires. To convert, add a leading zero."
            ),
            retailer_impact=(
                "1WorldSync GDSN requires GTIN-13 or GTIN-14 format. Submitting "
                "a 12-digit UPC may be rejected or require manual conversion. "
                "Costco's international operations also expect GTIN-13."
            ),
        ))

    if gtin_type in (GTINType.GTIN_12, GTINType.GTIN_13):
        result.company_prefix = cleaned[:7]
    elif gtin_type == GTINType.GTIN_14:
        result.company_prefix = cleaned[1:8]
    elif gtin_type == GTINType.GTIN_8:
        result.company_prefix = cleaned[:4]

    return result


def analyze_hierarchy(results: list[GTINResult]) -> dict:
    """
    Detect unit-to-case GTIN relationships via GTIN-14 indicator digits.

    A GTIN-14 with indicator 1-8 should share the same item reference
    as a corresponding GTIN-12 or GTIN-13 in the dataset.

    Returns:
        Dict with matched_pairs, orphan_cases, units_without_cases,
        has_hierarchy, and hierarchy_complete flags.
    """
    unit_gtins: dict[str, GTINResult] = {}
    case_gtins: list[GTINResult] = []

    for r in results:
        if r.gtin_type in (GTINType.GTIN_12, GTINType.GTIN_13):
            normalized = r.cleaned.zfill(13)
            unit_gtins[normalized[:-1]] = r
        elif (
            r.gtin_type == GTINType.GTIN_14
            and r.indicator_digit
            and r.indicator_digit in "12345678"
        ):
            case_gtins.append(r)

    matched_pairs = []
    orphan_cases = []

    for case_r in case_gtins:
        inner = case_r.cleaned[1:-1]
        if inner in unit_gtins:
            matched_pairs.append({
                "case_gtin": case_r.cleaned,
                "case_row": case_r.row_number,
                "unit_gtin": unit_gtins[inner].cleaned,
                "unit_row": unit_gtins[inner].row_number,
                "indicator": case_r.indicator_digit,
            })
        else:
            orphan_cases.append(case_r)
            case_r.issues.append(Issue(
                severity=Severity.WARNING,
                code="ORPHAN_CASE_GTIN",
                message=(
                    "This case-level GTIN-14 does not have a matching unit-level "
                    "GTIN (GTIN-12 or GTIN-13) in your file."
                ),
                recommendation=(
                    "Every case GTIN should correspond to a "
                    "unit GTIN in your product master. "
                    "Either the unit GTIN is missing from "
                    "your file, or this case GTIN's "
                    "item reference doesn't match any unit."
                ),
                retailer_impact=(
                    "Walmart requires a complete hierarchy (each -> case -> pallet). "
                    "A case GTIN without a matching unit will fail Item 360 setup."
                ),
            ))

    units_with_cases = {pair["unit_gtin"] for pair in matched_pairs}
    units_without_cases = [
        r for r in unit_gtins.values()
        if r.cleaned not in units_with_cases
    ]

    return {
        "matched_pairs": matched_pairs,
        "orphan_cases": orphan_cases,
        "units_without_cases": units_without_cases,
        "has_hierarchy": len(matched_pairs) > 0,
        "hierarchy_complete": len(orphan_cases) == 0 and len(units_without_cases) == 0,
    }
