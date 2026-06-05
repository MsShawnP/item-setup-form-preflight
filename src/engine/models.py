"""Pydantic v2 models for the four-tier validation engine."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class ErrorType(StrEnum):
    PRESENCE_MISSING = "PRESENCE_MISSING"
    FORMAT_INVALID = "FORMAT_INVALID"
    CONDITIONAL_REQUIREMENT_MISSING = "CONDITIONAL_REQUIREMENT_MISSING"
    GTIN_HIERARCHY_WRONG = "GTIN_HIERARCHY_WRONG"


class ValidationError(BaseModel):
    field: str
    error_type: ErrorType
    trigger: str | None = None
    severity: Severity
    message: str


class FieldSpec(BaseModel):
    name: str
    required: bool = True
    format_pattern: str | None = None
    format_description: str | None = None


class ConditionalRule(BaseModel):
    trigger_field: str
    trigger_value: str
    required_fields: list[str]


class GTINExpectation(BaseModel):
    expected_level: str
    expected_formats: list[str]


class SchemaConfig(BaseModel):
    partner: str
    display_name: str
    description: str
    required_fields: list[FieldSpec]
    conditional_rules: list[ConditionalRule] = []
    gtin_hierarchy: GTINExpectation


class ValidationResult(BaseModel):
    errors: list[ValidationError]
    fields_checked: int
    pass_count: int
    fail_count: int
    verdict: str
    tier_summary: dict[str, int]
