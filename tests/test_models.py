"""Tests for Pydantic v2 validation models."""

import pytest

from src.engine.models import (
    ConditionalRule,
    ErrorType,
    FieldSpec,
    GTINExpectation,
    SchemaConfig,
    Severity,
    ValidationError,
    ValidationResult,
)


class TestSeverityEnum:
    def test_has_critical(self):
        assert Severity.CRITICAL == "CRITICAL"

    def test_has_warning(self):
        assert Severity.WARNING == "WARNING"

    def test_has_info(self):
        assert Severity.INFO == "INFO"


class TestErrorTypeEnum:
    def test_has_presence_missing(self):
        assert ErrorType.PRESENCE_MISSING == "PRESENCE_MISSING"

    def test_has_format_invalid(self):
        assert ErrorType.FORMAT_INVALID == "FORMAT_INVALID"

    def test_has_conditional_requirement_missing(self):
        expected = "CONDITIONAL_REQUIREMENT_MISSING"
        assert ErrorType.CONDITIONAL_REQUIREMENT_MISSING == expected

    def test_has_gtin_hierarchy_wrong(self):
        assert ErrorType.GTIN_HIERARCHY_WRONG == "GTIN_HIERARCHY_WRONG"


class TestValidationError:
    def test_creates_with_required_fields(self):
        err = ValidationError(
            field="product_name",
            error_type=ErrorType.PRESENCE_MISSING,
            severity=Severity.CRITICAL,
            message="Product name is required.",
        )
        assert err.field == "product_name"
        assert err.error_type == ErrorType.PRESENCE_MISSING
        assert err.severity == Severity.CRITICAL
        assert err.message == "Product name is required."
        assert err.trigger is None

    def test_creates_with_trigger(self):
        err = ValidationError(
            field="temp_min",
            error_type=ErrorType.CONDITIONAL_REQUIREMENT_MISSING,
            trigger="storage_type=Refrigerated",
            severity=Severity.CRITICAL,
            message="Minimum temperature is required for refrigerated items.",
        )
        assert err.trigger == "storage_type=Refrigerated"


class TestSchemaConfig:
    def test_loads_from_valid_dict(self):
        config = SchemaConfig(
            partner="walmart",
            display_name="Walmart",
            description="Walmart Item 360 item setup requirements",
            required_fields=[
                FieldSpec(name="product_name", required=True),
                FieldSpec(name="upc", required=True, format_pattern=r"^\d{12}$"),
            ],
            conditional_rules=[
                ConditionalRule(
                    trigger_field="storage_type",
                    trigger_value="Refrigerated",
                    required_fields=["temp_min", "temp_max"],
                ),
            ],
            gtin_hierarchy=GTINExpectation(
                expected_level="consumer_unit",
                expected_formats=["GTIN-12", "UPC-A"],
            ),
        )
        assert config.partner == "walmart"
        assert len(config.required_fields) == 2
        assert len(config.conditional_rules) == 1
        assert config.gtin_hierarchy.expected_level == "consumer_unit"

    def test_defaults_for_optional_fields(self):
        config = SchemaConfig(
            partner="test",
            display_name="Test",
            description="Test schema",
            required_fields=[],
            gtin_hierarchy=GTINExpectation(
                expected_level="consumer_unit",
                expected_formats=["GTIN-12"],
            ),
        )
        assert config.format_rules == {}
        assert config.conditional_rules == []

    def test_rejects_missing_required_fields(self):
        with pytest.raises(Exception):
            SchemaConfig(
                partner="test",
                display_name="Test",
                # missing description, required_fields, gtin_hierarchy
            )


class TestValidationResult:
    def test_pass_verdict(self):
        result = ValidationResult(
            errors=[],
            fields_checked=10,
            pass_count=10,
            fail_count=0,
            verdict="PASS",
            tier_summary={"presence": 0, "format": 0, "conditional": 0, "gtin": 0},
        )
        assert result.verdict == "PASS"
        assert result.fail_count == 0

    def test_fail_verdict(self):
        err = ValidationError(
            field="upc",
            error_type=ErrorType.PRESENCE_MISSING,
            severity=Severity.CRITICAL,
            message="UPC is required.",
        )
        result = ValidationResult(
            errors=[err],
            fields_checked=10,
            pass_count=9,
            fail_count=1,
            verdict="FAIL",
            tier_summary={"presence": 1, "format": 0, "conditional": 0, "gtin": 0},
        )
        assert result.verdict == "FAIL"
        assert result.fail_count == 1
        assert len(result.errors) == 1
