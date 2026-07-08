"""Four-tier validation topology for partner item-setup schemas.

Tiers run in order. Fields that fail an earlier tier are skipped in
later tiers to avoid cascading noise. The result is a flat error list
plus a summary.
"""

from __future__ import annotations

import re

from src.engine.gtin.gtin_core import (
    GTINType,
    validate_single_gtin,
)
from src.engine.gtin.gtin_core import (
    Severity as GTINSeverity,
)
from src.engine.models import (
    ErrorType,
    SchemaConfig,
    Severity,
    ValidationError,
    ValidationResult,
)

# Maps GTIN schema format names to the GTINType enum values the vendored
# validator uses. Both "GTIN-12" and "UPC-A" resolve to the same type.
_FORMAT_TO_GTIN_TYPE: dict[str, GTINType] = {
    "GTIN-8": GTINType.GTIN_8,
    "GTIN-12": GTINType.GTIN_12,
    "UPC-A": GTINType.GTIN_12,
    "GTIN-13": GTINType.GTIN_13,
    "EAN": GTINType.GTIN_13,
    "GTIN-14": GTINType.GTIN_14,
    "ITF-14": GTINType.GTIN_14,
}

# GTIN core issues carry their own severity scale; map it onto the engine's
# severity enum so an INFO advisory is reported as INFO rather than being
# forced to CRITICAL.
_GTIN_SEVERITY_TO_MODEL: dict[GTINSeverity, Severity] = {
    GTINSeverity.CRITICAL: Severity.CRITICAL,
    GTINSeverity.WARNING: Severity.WARNING,
    GTINSeverity.INFO: Severity.INFO,
}


def _is_blank(value: object) -> bool:
    """True if value is None, empty string, or whitespace-only."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _tier1_presence(
    product: dict,
    schema: SchemaConfig,
) -> tuple[list[ValidationError], set[str]]:
    """Tier 1: Check that every required field is populated."""
    errors: list[ValidationError] = []
    failed_fields: set[str] = set()

    for field_spec in schema.required_fields:
        if not field_spec.required:
            continue

        value = product.get(field_spec.name)
        if _is_blank(value):
            failed_fields.add(field_spec.name)
            errors.append(ValidationError(
                field=field_spec.name,
                error_type=ErrorType.PRESENCE_MISSING,
                severity=Severity.CRITICAL,
                message=f"'{field_spec.name}' is required but missing or empty.",
            ))

    return errors, failed_fields


def _tier2_format(
    product: dict,
    schema: SchemaConfig,
    skip_fields: set[str],
) -> tuple[list[ValidationError], set[str]]:
    """Tier 2: Validate field values against format patterns."""
    errors: list[ValidationError] = []
    failed_fields: set[str] = set()

    for field_spec in schema.required_fields:
        if field_spec.name in skip_fields:
            continue
        if field_spec.format_pattern is None:
            continue

        value = product.get(field_spec.name)
        if _is_blank(value):
            continue

        value_str = str(value).strip()
        if not re.match(field_spec.format_pattern, value_str):
            failed_fields.add(field_spec.name)
            description = field_spec.format_description or field_spec.format_pattern
            errors.append(ValidationError(
                field=field_spec.name,
                error_type=ErrorType.FORMAT_INVALID,
                severity=Severity.WARNING,
                message=(
                    f"'{field_spec.name}' value '{value_str}' does not match "
                    f"expected format: {description}."
                ),
            ))

    return errors, failed_fields


def _tier3_conditional(
    product: dict,
    schema: SchemaConfig,
    skip_fields: set[str],
) -> tuple[list[ValidationError], set[str], set[str]]:
    """Tier 3: Cross-field conditional requirement checks.

    Also returns the set of conditionally-triggered fields that were
    evaluated, so the caller can count them toward fields_checked (they
    are only checked when their trigger fires).
    """
    errors: list[ValidationError] = []
    failed_fields: set[str] = set()
    checked_fields: set[str] = set()

    for rule in schema.conditional_rules:
        trigger_value = product.get(rule.trigger_field)
        if _is_blank(trigger_value):
            continue

        if str(trigger_value).strip().lower() != rule.trigger_value.lower():
            continue

        # Trigger matches — check that all required_fields are present
        trigger_desc = f"{rule.trigger_field}={rule.trigger_value}"
        for req_field in rule.required_fields:
            if req_field in skip_fields:
                continue
            checked_fields.add(req_field)
            value = product.get(req_field)
            if _is_blank(value):
                failed_fields.add(req_field)
                errors.append(ValidationError(
                    field=req_field,
                    error_type=ErrorType.CONDITIONAL_REQUIREMENT_MISSING,
                    trigger=trigger_desc,
                    severity=Severity.CRITICAL,
                    message=(
                        f"'{req_field}' is required when {trigger_desc}, "
                        f"but is missing or empty."
                    ),
                ))

    return errors, failed_fields, checked_fields


def _tier4_gtin(
    product: dict,
    schema: SchemaConfig,
    skip_fields: set[str],
) -> tuple[list[ValidationError], set[str]]:
    """Tier 4: GTIN hierarchy validation using vendored gtin_core.

    Returns the errors plus the set of GTIN fields that failed, so the
    caller folds them into the row's failed-field count (a GTIN failure
    is a field failure like any other tier's).
    """
    errors: list[ValidationError] = []
    failed_fields: set[str] = set()

    # Find the UPC/GTIN field — check common field names
    gtin_field = None
    gtin_value = None
    for candidate in ("upc", "gtin", "gtin_12", "gtin_14", "ean"):
        if candidate in skip_fields:
            continue
        val = product.get(candidate)
        if not _is_blank(val):
            gtin_field = candidate
            gtin_value = str(val).strip()
            break

    if gtin_field is None or gtin_value is None:
        return errors, failed_fields

    result = validate_single_gtin(gtin_value, row_number=1)

    if not result.is_valid:
        # An invalid GTIN carries one blocking issue (e.g. BAD_CHECK_DIGIT)
        # plus optional advisories that merely ride along (e.g. the
        # UPC_NOT_GTIN13 INFO note). Surface only the blocking issue(s) at
        # their real severity: stamping the advisory CRITICAL both mislabels
        # it and double-counts the GTIN in the aggregate (20 for 10 bad UPCs).
        for issue in result.issues:
            if issue.severity is not GTINSeverity.CRITICAL:
                continue
            errors.append(ValidationError(
                field=gtin_field,
                error_type=ErrorType.GTIN_HIERARCHY_WRONG,
                severity=_GTIN_SEVERITY_TO_MODEL[issue.severity],
                message=f"GTIN check failed: {issue.message}",
            ))
        failed_fields.add(gtin_field)
        return errors, failed_fields

    # Check that the GTIN type matches what the schema expects
    expected_types = set()
    for fmt in schema.gtin_hierarchy.expected_formats:
        mapped = _FORMAT_TO_GTIN_TYPE.get(fmt)
        if mapped is not None:
            expected_types.add(mapped)

    if expected_types and result.gtin_type not in expected_types:
        expected_names = ", ".join(schema.gtin_hierarchy.expected_formats)
        errors.append(ValidationError(
            field=gtin_field,
            error_type=ErrorType.GTIN_HIERARCHY_WRONG,
            severity=Severity.WARNING,
            message=(
                f"GTIN is type {result.gtin_type.value}, "
                f"but {schema.display_name} expects "
                f"{expected_names} for "
                f"{schema.gtin_hierarchy.expected_level} "
                "submissions."
            ),
        ))
        failed_fields.add(gtin_field)

    return errors, failed_fields


def validate_product(product: dict, schema: SchemaConfig) -> ValidationResult:
    """Run four-tier validation against a partner schema.

    Tiers execute in order. Fields that fail an earlier tier are
    skipped in subsequent tiers to avoid cascading noise.

    Args:
        product: Dict of field_name -> value from the product master.
        schema: Validated partner schema config.

    Returns:
        ValidationResult with flat error list and summary counts.
    """
    all_errors: list[ValidationError] = []
    failed_fields: set[str] = set()
    # Fields we actually evaluated: every required field, plus any
    # conditionally-triggered field. pass/fail counts are derived from
    # this set so they always foot to fields_checked.
    checked_fields: set[str] = {f.name for f in schema.required_fields}
    tier_summary = {"presence": 0, "format": 0, "conditional": 0, "gtin": 0}

    # Tier 1: Presence
    t1_errors, t1_failed = _tier1_presence(product, schema)
    all_errors.extend(t1_errors)
    failed_fields.update(t1_failed)
    tier_summary["presence"] = len(t1_errors)

    # Tier 2: Format
    t2_errors, t2_failed = _tier2_format(product, schema, failed_fields)
    all_errors.extend(t2_errors)
    failed_fields.update(t2_failed)
    tier_summary["format"] = len(t2_errors)

    # Tier 3: Conditional
    t3_errors, t3_failed, t3_checked = _tier3_conditional(
        product, schema, failed_fields
    )
    all_errors.extend(t3_errors)
    failed_fields.update(t3_failed)
    checked_fields.update(t3_checked)
    tier_summary["conditional"] = len(t3_errors)

    # Tier 4: GTIN hierarchy
    t4_errors, t4_failed = _tier4_gtin(product, schema, failed_fields)
    all_errors.extend(t4_errors)
    failed_fields.update(t4_failed)
    checked_fields.update(t4_failed)
    tier_summary["gtin"] = len(t4_errors)

    # Counts foot: pass_count + fail_count == fields_checked, and every
    # failed field is a checked field, so a FAIL row can never report
    # "all fields pass".
    fields_checked = len(checked_fields)
    fail_count = len(failed_fields)
    pass_count = max(0, fields_checked - fail_count)

    # Verdict is severity-aware rather than "any error fails": a row bounces
    # on a blocking issue (CRITICAL missing/invalid, or WARNING format/type
    # mismatch — both reject on submission), but an INFO-level advisory does
    # not fail the row on its own.
    has_blocking = any(
        e.severity in (Severity.CRITICAL, Severity.WARNING) for e in all_errors
    )
    verdict = "FAIL" if has_blocking else "PASS"

    return ValidationResult(
        errors=all_errors,
        fields_checked=fields_checked,
        pass_count=pass_count,
        fail_count=fail_count,
        verdict=verdict,
        tier_summary=tier_summary,
    )
