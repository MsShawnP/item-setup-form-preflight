"""Tests for vendored GTIN validation primitives."""

from src.engine.gtin.gtin_core import (
    GTINType,
    Severity,
    calculate_check_digit,
    identify_gtin_type,
    validate_single_gtin,
)


class TestCheckDigitCalculation:
    def test_valid_upc12_check_digit(self):
        # 04900000450 -> GS1 mod-10 yields check digit 2
        assert calculate_check_digit("04900000450") == 2

    def test_valid_gtin14_check_digit(self):
        # 1049000004500 -> GS1 mod-10 yields check digit 7
        assert calculate_check_digit("1049000004500") == 7


class TestIdentifyGTINType:
    def test_gtin_8(self):
        assert identify_gtin_type(8) == GTINType.GTIN_8

    def test_gtin_12(self):
        assert identify_gtin_type(12) == GTINType.GTIN_12

    def test_gtin_13(self):
        assert identify_gtin_type(13) == GTINType.GTIN_13

    def test_gtin_14(self):
        assert identify_gtin_type(14) == GTINType.GTIN_14

    def test_unknown_length(self):
        assert identify_gtin_type(10) == GTINType.UNKNOWN

    def test_gtin14_indicator_digit_identified(self):
        """GTIN-14 indicator digit is correctly extracted."""
        result = validate_single_gtin("10490000045007", row_number=1)
        assert result.indicator_digit == "1"


class TestValidateSingleGTIN:
    def test_valid_upc12_passes(self):
        result = validate_single_gtin("049000004502", row_number=1)
        assert result.is_valid is True
        assert result.gtin_type == GTINType.GTIN_12
        # Should only have INFO-level issues (UPC_NOT_GTIN13 advisory)
        assert all(i.severity == Severity.INFO for i in result.issues)

    def test_invalid_check_digit_detected(self):
        # Change last digit from 2 to 9
        result = validate_single_gtin("049000004509", row_number=1)
        assert result.is_valid is False
        critical_codes = [
            i.code for i in result.issues
            if i.severity == Severity.CRITICAL
        ]
        assert "BAD_CHECK_DIGIT" in critical_codes

    def test_empty_gtin_handled(self):
        result = validate_single_gtin("", row_number=1)
        assert result.is_valid is False
        assert result.issues[0].code == "EMPTY"

    def test_blank_gtin_handled(self):
        result = validate_single_gtin("   ", row_number=1)
        assert result.is_valid is False
        assert result.issues[0].code == "EMPTY"

    def test_none_gtin_handled(self):
        result = validate_single_gtin(None, row_number=1)
        assert result.is_valid is False
        assert result.issues[0].code == "EMPTY"

    def test_non_numeric_rejected(self):
        result = validate_single_gtin("04900ABC4508", row_number=1)
        assert result.is_valid is False
        assert result.issues[0].code == "NON_NUMERIC"

    def test_invalid_length_rejected(self):
        result = validate_single_gtin("12345", row_number=1)
        assert result.is_valid is False
        assert result.issues[0].code == "INVALID_LENGTH"
