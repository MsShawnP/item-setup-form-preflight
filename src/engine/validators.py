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

        # Category-conditional: only required when category matches
        if field_spec.category_condition is not None:
            product_category = product.get("category", "")
            cat_lower = field_spec.category_condition.lower()
            if str(product_category).strip().lower() != cat_lower:
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

    # Also check format_rules dict (for fields not in required_fields)
    for field_name, rule in schema.format_rules.items():
        if field_name in skip_fields:
            continue
        if rule.format_pattern is None:
            continue

        value = product.get(field_name)
        if _is_blank(value):
            continue

        value_str = str(value).strip()
        if not re.match(rule.format_pattern, value_str):
            failed_fields.add(field_name)
            description = rule.format_description or rule.format_pattern
            errors.append(ValidationError(
                field=field_name,
                error_type=ErrorType.FORMAT_INVALID,
                severity=Severity.WARNING,
                message=(
                    f"'{field_name}' value '{value_str}' does not match "
                    f"expected format: {description}."
                ),
            ))

    return errors, failed_fields


def _tier3_conditional(
    product: dict,
    schema: SchemaConfig,
    skip_fields: set[str],
) -> tuple[list[ValidationError], set[str]]:
    """Tier 3: Cross-field conditional requirement checks."""
    errors: list[ValidationError] = []
    failed_fields: set[str] = set()

    for rule in schema.conditional_rules:
        trigger_value = product.get(rule.trigger_field)
        if _is_blank(trigger_value):
            continue

        if str(trigger_value).strip() != rule.trigger_value:
            continue

        # Trigger matches — check that all required_fields are present
        trigger_desc = f"{rule.trigger_field}={rule.trigger_value}"
        for req_field in rule.required_fields:
            if req_field in skip_fields:
                continue
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

    return errors, failed_fields


def _tier4_gtin(
    product: dict,
    schema: SchemaConfig,
    skip_fields: set[str],
) -> list[ValidationError]:
    """Tier 4: GTIN hierarchy validation using vendored gtin_core."""
    errors: list[ValidationError] = []

    # Find the UPC/GTIN field — check common field names
    gtin_field = None
    gtin_value = None
    for candidate in ("upc", "gtin", "gtin_12", "gtin_14", "ean"):
        if candidate in skip_fields:
            return errors
        val = product.get(candidate)
        if not _is_blank(val):
            gtin_field = candidate
            gtin_value = str(val).strip()
            break

    if gtin_field is None or gtin_value is None:
        return errors

    result = validate_single_gtin(gtin_value, row_number=1)

    if not result.is_valid:
        for issue in result.issues:
            errors.append(ValidationError(
                field=gtin_field,
                error_type=ErrorType.GTIN_HIERARCHY_WRONG,
                severity=Severity.CRITICAL,
                message=f"GTIN check failed: {issue.message}",
            ))
        return errors

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

    return errors


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
    t3_errors, t3_failed = _tier3_conditional(product, schema, failed_fields)
    all_errors.extend(t3_errors)
    failed_fields.update(t3_failed)
    tier_summary["conditional"] = len(t3_errors)

    # Tier 4: GTIN hierarchy
    t4_errors = _tier4_gtin(product, schema, failed_fields)
    all_errors.extend(t4_errors)
    tier_summary["gtin"] = len(t4_errors)

    # Count fields checked: required fields + conditionally-triggered fields
    fields_checked = len(schema.required_fields)
    fail_count = len(all_errors)
    pass_count = fields_checked - len(failed_fields)

    verdict = "PASS" if fail_count == 0 else "FAIL"

    return ValidationResult(
        errors=all_errors,
        fields_checked=fields_checked,
        pass_count=max(0, pass_count),
        fail_count=fail_count,
        verdict=verdict,
        tier_summary=tier_summary,
    )
