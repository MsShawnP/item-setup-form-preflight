"""Dataclass models for the four-tier validation engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class ErrorType(StrEnum):
    PRESENCE_MISSING = "PRESENCE_MISSING"
    FORMAT_INVALID = "FORMAT_INVALID"
    CONDITIONAL_REQUIREMENT_MISSING = "CONDITIONAL_REQUIREMENT_MISSING"
    GTIN_HIERARCHY_WRONG = "GTIN_HIERARCHY_WRONG"


@dataclass
class ValidationError:
    field: str
    error_type: ErrorType
    severity: Severity
    message: str
    trigger: str | None = None


@dataclass
class FieldSpec:
    name: str
    required: bool = True
    format_pattern: str | None = None
    format_description: str | None = None


@dataclass
class ConditionalRule:
    trigger_field: str
    trigger_value: str
    required_fields: list[str] = field(default_factory=list)


@dataclass
class GTINExpectation:
    expected_level: str
    expected_formats: list[str] = field(default_factory=list)


@dataclass
class SchemaConfig:
    partner: str
    display_name: str
    description: str
    required_fields: list[FieldSpec]
    gtin_hierarchy: GTINExpectation
    conditional_rules: list[ConditionalRule] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> SchemaConfig:
        return cls(
            partner=data["partner"],
            display_name=data["display_name"],
            description=data["description"],
            required_fields=[
                FieldSpec(**f) for f in data["required_fields"]
            ],
            gtin_hierarchy=GTINExpectation(**data["gtin_hierarchy"]),
            conditional_rules=[
                ConditionalRule(**r) for r in data.get("conditional_rules", [])
            ],
        )


@dataclass
class ValidationResult:
    errors: list[ValidationError]
    fields_checked: int
    pass_count: int
    fail_count: int
    verdict: str
    tier_summary: dict[str, int]
