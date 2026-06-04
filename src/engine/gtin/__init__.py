"""GTIN validation primitives vendored from gtin-validator."""

from src.engine.gtin.gtin_core import (
    GTINResult,
    GTINType,
    Issue,
    Severity,
    analyze_hierarchy,
    calculate_check_digit,
    identify_gtin_type,
    validate_single_gtin,
)

__all__ = [
    "GTINResult",
    "GTINType",
    "Issue",
    "Severity",
    "analyze_hierarchy",
    "calculate_check_digit",
    "identify_gtin_type",
    "validate_single_gtin",
]
