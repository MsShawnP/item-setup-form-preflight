"""Tests for the four-tier validation engine."""


from src.engine.gtin.gtin_core import calculate_check_digit
from src.engine.models import ErrorType, SchemaConfig, Severity
from src.engine.validators import validate_product


def _walmart_schema() -> SchemaConfig:
    """Minimal Walmart-like schema for testing."""
    return SchemaConfig.from_dict({
        "partner": "walmart",
        "display_name": "Walmart",
        "description": "Walmart Item 360 item setup requirements",
        "required_fields": [
            {"name": "product_name", "required": True},
            {"name": "brand", "required": True},
            {"name": "upc", "required": True, "format_pattern": r"^\d{12}$",
             "format_description": "12-digit UPC-A"},
            {"name": "case_gross_weight_lb", "required": True,
             "format_pattern": r"^\d+\.?\d*$",
             "format_description": "Numeric weight in pounds"},
            {"name": "case_length_in", "required": True,
             "format_pattern": r"^\d+\.?\d*$"},
            {"name": "case_width_in", "required": True},
            {"name": "case_height_in", "required": True},
            {"name": "case_pack_qty", "required": True,
             "format_pattern": r"^\d+$", "format_description": "Whole number"},
            {"name": "country_of_origin", "required": True},
            {"name": "category", "required": True},
            {"name": "product_description", "required": True},
            {"name": "serving_size", "required": True},
            {"name": "calories", "required": True},
            {"name": "total_fat_g", "required": True},
            {"name": "sodium_mg", "required": True},
        ],
        "conditional_rules": [
            {
                "trigger_field": "storage_type",
                "trigger_value": "Refrigerated",
                "required_fields": ["temp_min", "temp_max"],
            },
            {
                "trigger_field": "storage_type",
                "trigger_value": "Frozen",
                "required_fields": ["temp_min", "temp_max"],
            },
            {
                "trigger_field": "is_hazmat",
                "trigger_value": "true",
                "required_fields": ["hazmat_class", "un_number"],
            },
        ],
        "gtin_hierarchy": {
            "expected_level": "consumer_unit",
            "expected_formats": ["GTIN-12", "UPC-A"],
        },
    })


def _valid_product() -> dict:
    """A product record that passes all four tiers."""
    return {
        "product_name": "Cinderhaven Reserve Hot Sauce",
        "brand": "Cinderhaven",
        "upc": "049000004502",
        "case_gross_weight_lb": "12.5",
        "case_length_in": "15.0",
        "case_width_in": "10.0",
        "case_height_in": "8.0",
        "case_pack_qty": "12",
        "country_of_origin": "USA",
        "category": "Condiments",
        "product_description": "Small-batch fermented hot sauce",
        "serving_size": "1 tsp (5mL)",
        "calories": "5",
        "total_fat_g": "0",
        "sodium_mg": "110",
    }


def _bad_check_digit_upc(seed: int) -> str:
    """Build a distinct 12-digit UPC-A whose check digit is deliberately
    wrong (valid length, valid format, invalid check digit)."""
    payload = f"49000000{seed:03d}"  # 11 digits
    correct = calculate_check_digit(payload)
    wrong = (correct + 1) % 10
    return payload + str(wrong)


class TestHappyPath:
    def test_valid_product_passes_all_tiers(self):
        """AE1: Valid product passes all tiers, PASS verdict, no blocking errors.

        A valid 12-digit UPC carries a non-blocking INFO advisory
        (UPC_NOT_GTIN13), so the row still passes with zero blocking errors.
        """
        schema = _walmart_schema()
        product = _valid_product()
        result = validate_product(product, schema)

        assert result.verdict == "PASS"
        blocking = [
            e for e in result.errors
            if e.severity in (Severity.CRITICAL, Severity.WARNING)
        ]
        assert len(blocking) == 0
        assert result.fail_count == 0
        assert result.fields_checked > 0

    def test_valid_upc12_passes_gtin_check(self):
        """AE2: SKU with valid UPC-12 passes the GTIN check for Walmart — the
        only GTIN note is the non-blocking INFO advisory, no blocking failure.
        """
        schema = _walmart_schema()
        product = _valid_product()
        result = validate_product(product, schema)

        blocking_gtin_errors = [
            e for e in result.errors
            if e.error_type == ErrorType.GTIN_HIERARCHY_WRONG
            and e.severity in (Severity.CRITICAL, Severity.WARNING)
        ]
        assert len(blocking_gtin_errors) == 0


class TestConditionalRules:
    def test_refrigerated_missing_temps_fails(self):
        """AE3: Refrigerated product without temps triggers conditional error."""
        schema = _walmart_schema()
        product = _valid_product()
        product["storage_type"] = "Refrigerated"
        # temp_min and temp_max intentionally missing

        result = validate_product(product, schema)

        conditional_errors = [
            e for e in result.errors
            if e.error_type == ErrorType.CONDITIONAL_REQUIREMENT_MISSING
        ]
        assert len(conditional_errors) >= 1
        field_names = {e.field for e in conditional_errors}
        assert "temp_min" in field_names or "temp_max" in field_names

        # All should be CRITICAL
        for err in conditional_errors:
            assert err.severity == Severity.CRITICAL

    def test_non_refrigerated_skips_temp_check(self):
        """Non-refrigerated product does not trigger temp requirement."""
        schema = _walmart_schema()
        product = _valid_product()
        product["storage_type"] = "Ambient"

        result = validate_product(product, schema)

        conditional_errors = [
            e for e in result.errors
            if e.error_type == ErrorType.CONDITIONAL_REQUIREMENT_MISSING
        ]
        assert len(conditional_errors) == 0


class TestNoCascadingNoise:
    def test_tier1_failure_skips_later_tiers(self):
        """Field failing Tier 1 (missing) should NOT also fail at Tier 2/3/4."""
        schema = _walmart_schema()
        product = _valid_product()
        product["upc"] = ""  # Missing UPC — Tier 1 failure

        result = validate_product(product, schema)

        upc_errors = [e for e in result.errors if e.field == "upc"]
        error_types = {e.error_type for e in upc_errors}

        # Should have PRESENCE_MISSING but NOT FORMAT_INVALID or GTIN_HIERARCHY_WRONG
        assert ErrorType.PRESENCE_MISSING in error_types
        assert ErrorType.FORMAT_INVALID not in error_types
        assert ErrorType.GTIN_HIERARCHY_WRONG not in error_types


class TestEmptyProduct:
    def test_empty_product_presence_errors_only(self):
        """Empty product record -> presence errors only, no format/conditional/GTIN."""
        schema = _walmart_schema()
        product = {}  # All fields missing

        result = validate_product(product, schema)

        assert result.verdict == "FAIL"
        assert len(result.errors) > 0

        # Every error should be PRESENCE_MISSING
        for err in result.errors:
            assert err.error_type == ErrorType.PRESENCE_MISSING, (
                f"Expected only PRESENCE_MISSING errors for empty product, "
                f"got {err.error_type} on field '{err.field}'"
            )


class TestGTINValidation:
    def test_invalid_check_digit_detected(self):
        """Bad GTIN check digit yields GTIN_HIERARCHY_WRONG."""
        schema = _walmart_schema()
        product = _valid_product()
        product["upc"] = "049000004509"  # Valid format but wrong check digit

        result = validate_product(product, schema)

        gtin_errors = [
            e for e in result.errors
            if e.error_type == ErrorType.GTIN_HIERARCHY_WRONG
        ]
        assert len(gtin_errors) >= 1
        assert any("check digit" in e.message.lower() for e in gtin_errors)

    def test_bad_gtin_counted_once_at_true_severity(self):
        """A bad UPC surfaces exactly one GTIN error (the real check-digit
        failure) at CRITICAL — not the check-digit failure PLUS the
        UPC_NOT_GTIN13 advisory both stamped CRITICAL.

        Before the fix each bad UPC produced two GTIN_HIERARCHY_WRONG
        errors, so 10 bad UPCs aggregated to 20 and an INFO advisory was
        reported as CRITICAL.
        """
        schema = _walmart_schema()

        gtin_error_total = 0
        for seed in range(10):
            product = _valid_product()
            product["upc"] = _bad_check_digit_upc(seed)
            result = validate_product(product, schema)

            gtin_errors = [
                e for e in result.errors
                if e.error_type == ErrorType.GTIN_HIERARCHY_WRONG
            ]
            # Exactly one GTIN error per bad UPC — the advisory no longer
            # rides along as a second (mislabelled) critical.
            assert len(gtin_errors) == 1
            assert gtin_errors[0].severity == Severity.CRITICAL
            assert "check digit" in gtin_errors[0].message.lower()
            gtin_error_total += len(gtin_errors)

        # 10 bad UPCs -> 10 GTIN errors, not 20.
        assert gtin_error_total == 10


class TestGTINInfoAdvisory:
    """A GTIN INFO advisory (e.g. UPC_NOT_GTIN13) is surfaced for visibility
    at INFO severity, but is non-blocking: it stays out of the critical/fail
    aggregate and never flips the row verdict. The genuine blocking issue
    (BAD_CHECK_DIGIT) still surfaces at CRITICAL, counted once.
    """

    def test_valid_upc_surfaces_info_advisory_but_row_passes(self):
        """A 12-digit UPC with a valid check digit surfaces the UPC_NOT_GTIN13
        advisory at INFO — visible, but non-blocking. The row still PASSES and
        the advisory is excluded from the fail aggregate."""
        schema = _walmart_schema()
        product = _valid_product()  # upc 049000004502 is a valid 12-digit UPC

        result = validate_product(product, schema)

        gtin_errors = [
            e for e in result.errors
            if e.error_type == ErrorType.GTIN_HIERARCHY_WRONG
        ]
        # The advisory is surfaced (not suppressed)...
        assert len(gtin_errors) == 1
        advisory = gtin_errors[0]
        # ...at INFO severity, not stamped CRITICAL/WARNING...
        assert advisory.severity == Severity.INFO
        assert "gtin-13" in advisory.message.lower()

        # ...and it neither flips the verdict nor enters the fail aggregate.
        assert result.verdict == "PASS"
        assert result.fail_count == 0
        assert result.pass_count == result.fields_checked
        assert not any(
            e.severity in (Severity.CRITICAL, Severity.WARNING)
            for e in result.errors
        )

    def test_bad_check_digit_still_one_critical(self):
        """A bad-check-digit GTIN still surfaces exactly one CRITICAL blocking
        issue — the advisory does not ride along to double-count the GTIN."""
        schema = _walmart_schema()
        product = _valid_product()
        product["upc"] = _bad_check_digit_upc(1)

        result = validate_product(product, schema)

        gtin_errors = [
            e for e in result.errors
            if e.error_type == ErrorType.GTIN_HIERARCHY_WRONG
        ]
        critical = [e for e in gtin_errors if e.severity == Severity.CRITICAL]
        assert len(critical) == 1
        assert "check digit" in critical[0].message.lower()
        # Counted once: no second (advisory) GTIN error rides along.
        assert len(gtin_errors) == 1
        assert result.verdict == "FAIL"


class TestCountCoherence:
    def test_fail_row_does_not_report_all_fields_passing(self):
        """A row that fails only on the GTIN must not report that every
        field passed. Before the fix, GTIN failures were never added to
        failed_fields, so a FAIL row could show '15 of 15 fields pass'."""
        schema = _walmart_schema()
        product = _valid_product()
        product["upc"] = _bad_check_digit_upc(3)  # only defect is the GTIN

        result = validate_product(product, schema)

        assert result.verdict == "FAIL"
        assert result.fail_count >= 1
        assert result.pass_count < result.fields_checked
        # Counts foot.
        assert result.pass_count + result.fail_count == result.fields_checked

    def test_counts_foot_for_valid_product(self):
        """pass_count + fail_count == fields_checked, with zero failures."""
        schema = _walmart_schema()
        result = validate_product(_valid_product(), schema)

        assert result.fail_count == 0
        assert result.pass_count == result.fields_checked

    def test_triggered_conditional_fields_count_toward_total(self):
        """Conditionally-required fields are counted only when triggered,
        and still foot."""
        schema = _walmart_schema()
        product = _valid_product()
        product["storage_type"] = "Refrigerated"  # triggers temp_min/temp_max

        result = validate_product(product, schema)

        # 15 required + 2 triggered conditional fields.
        assert result.fields_checked == 17
        assert result.fail_count == 2  # temp_min, temp_max missing
        assert result.pass_count + result.fail_count == result.fields_checked


class TestSeverityAwareVerdict:
    """Verdict derives from severity, not from a raw error count. A blocking
    issue (CRITICAL or WARNING) bounces the row; an INFO advisory does not.
    """

    def test_clean_row_passes(self):
        schema = _walmart_schema()
        result = validate_product(_valid_product(), schema)
        assert result.verdict == "PASS"
        # A non-blocking GTIN INFO advisory may be present; no blocking errors.
        blocking = [
            e for e in result.errors
            if e.severity in (Severity.CRITICAL, Severity.WARNING)
        ]
        assert len(blocking) == 0

    def test_critical_issue_bounces(self):
        """A CRITICAL issue (missing required field) is a hard bounce."""
        schema = _walmart_schema()
        product = _valid_product()
        del product["brand"]  # PRESENCE_MISSING (CRITICAL)

        result = validate_product(product, schema)

        assert result.verdict == "FAIL"

    def test_warning_issue_bounces(self):
        """A WARNING-level format violation is a real bounce (it rejects on
        submission), so the row still fails."""
        schema = _walmart_schema()
        product = _valid_product()
        product["case_pack_qty"] = "not-a-number"  # FORMAT_INVALID (WARNING)

        result = validate_product(product, schema)

        severities = {e.severity for e in result.errors}
        assert Severity.CRITICAL not in severities
        assert Severity.WARNING in severities
        assert result.verdict == "FAIL"


class TestGracefulErrorHandling:
    def test_unknown_field_in_conditional_handled(self):
        """Unknown field in conditional rule -> handled without crashing."""
        schema = _walmart_schema()
        product = _valid_product()
        # Trigger a conditional whose required_fields reference fields
        # that don't exist in the product — engine should not crash
        product["is_hazmat"] = "true"
        # hazmat_class and un_number are not in product — conditional fires

        result = validate_product(product, schema)

        # Should produce CONDITIONAL_REQUIREMENT_MISSING, not an exception
        conditional_errors = [
            e for e in result.errors
            if e.error_type == ErrorType.CONDITIONAL_REQUIREMENT_MISSING
        ]
        assert len(conditional_errors) >= 1
