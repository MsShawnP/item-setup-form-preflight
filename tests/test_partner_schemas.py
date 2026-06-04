"""Tests for partner schema loading, GTIN hierarchy divergence, and structural similarity."""

import os

import pytest

from src.engine.models import ErrorType, SchemaConfig, Severity
from src.engine.schema_loader import load_schema
from src.engine.validators import validate_product


# ---------------------------------------------------------------------------
# Paths to YAML schema files
# ---------------------------------------------------------------------------

_SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "schemas")

WALMART_YAML = os.path.join(_SCHEMA_DIR, "walmart.yaml")
COSTCO_YAML = os.path.join(_SCHEMA_DIR, "costco.yaml")
UNFI_YAML = os.path.join(_SCHEMA_DIR, "unfi.yaml")
KEHE_YAML = os.path.join(_SCHEMA_DIR, "kehe.yaml")


# ---------------------------------------------------------------------------
# Helpers: inline schemas for isolated validation tests
# ---------------------------------------------------------------------------

def _walmart_schema() -> SchemaConfig:
    """Minimal Walmart schema for validation tests."""
    return SchemaConfig.model_validate({
        "partner": "walmart",
        "display_name": "Walmart",
        "description": "Walmart Item 360 item setup requirements",
        "required_fields": [
            {"name": "product_name", "required": True},
            {"name": "brand", "required": True},
            {"name": "upc", "required": True,
             "format_pattern": r"^\d{12}$",
             "format_description": "12-digit UPC-A"},
            {"name": "case_gross_weight_lb", "required": True,
             "format_pattern": r"^\d+\.?\d*$"},
            {"name": "case_length_in", "required": True,
             "format_pattern": r"^\d+\.?\d*$"},
            {"name": "case_width_in", "required": True},
            {"name": "case_height_in", "required": True},
            {"name": "case_pack_qty", "required": True,
             "format_pattern": r"^\d+$"},
            {"name": "country_of_origin", "required": True},
            {"name": "category", "required": True},
            {"name": "product_description", "required": True},
            {"name": "serving_size", "required": True},
            {"name": "calories", "required": True},
            {"name": "total_fat_g", "required": True},
            {"name": "sodium_mg", "required": True},
        ],
        "conditional_rules": [],
        "gtin_hierarchy": {
            "expected_level": "consumer_unit",
            "expected_formats": ["GTIN-12", "UPC-A"],
        },
    })


def _costco_schema() -> SchemaConfig:
    """Minimal Costco schema for validation tests."""
    return SchemaConfig.model_validate({
        "partner": "costco",
        "display_name": "Costco",
        "description": "Costco item setup workbook requirements",
        "required_fields": [
            {"name": "product_name", "required": True},
            {"name": "brand", "required": True},
            {"name": "upc", "required": True,
             "format_pattern": r"^\d{14}$",
             "format_description": "14-digit case-level GTIN"},
            {"name": "case_gross_weight_lb", "required": True,
             "format_pattern": r"^\d+\.?\d*$"},
            {"name": "case_length_in", "required": True,
             "format_pattern": r"^\d+\.?\d*$"},
            {"name": "case_width_in", "required": True},
            {"name": "case_height_in", "required": True},
            {"name": "case_pack_qty", "required": True,
             "format_pattern": r"^\d+$"},
            {"name": "inner_pack_count", "required": True,
             "format_pattern": r"^\d+$"},
            {"name": "club_pack_length_in", "required": True,
             "format_pattern": r"^\d+\.?\d*$"},
            {"name": "club_pack_width_in", "required": True,
             "format_pattern": r"^\d+\.?\d*$"},
            {"name": "club_pack_height_in", "required": True,
             "format_pattern": r"^\d+\.?\d*$"},
            {"name": "country_of_origin", "required": True},
            {"name": "category", "required": True},
            {"name": "product_description", "required": True},
            {"name": "shelf_life_days", "required": True,
             "format_pattern": r"^\d+$"},
        ],
        "conditional_rules": [
            {
                "trigger_field": "club_membership_tier",
                "trigger_value": "Executive",
                "required_fields": [
                    "executive_member_price",
                    "executive_discount_pct",
                ],
            },
        ],
        "gtin_hierarchy": {
            "expected_level": "case",
            "expected_formats": ["GTIN-14", "ITF-14"],
        },
    })


def _valid_walmart_product() -> dict:
    """Product that passes Walmart validation (consumer-unit UPC-12)."""
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


def _valid_costco_product() -> dict:
    """Product that passes Costco validation (case-level GTIN-14)."""
    return {
        "product_name": "Cinderhaven Reserve Hot Sauce 12-Pack",
        "brand": "Cinderhaven",
        "upc": "10049000004509",
        "case_gross_weight_lb": "14.8",
        "case_length_in": "16.0",
        "case_width_in": "12.0",
        "case_height_in": "9.0",
        "case_pack_qty": "12",
        "inner_pack_count": "4",
        "club_pack_length_in": "8.0",
        "club_pack_width_in": "6.0",
        "club_pack_height_in": "4.5",
        "country_of_origin": "USA",
        "category": "Condiments",
        "product_description": "Small-batch fermented hot sauce club pack",
        "shelf_life_days": "365",
    }


def _valid_unfi_product() -> dict:
    """Product that passes UNFI validation (case-level GTIN-14)."""
    return {
        "product_name": "Cinderhaven Reserve Hot Sauce",
        "brand": "Cinderhaven",
        "upc": "10049000004509",
        "case_gross_weight_lb": "12.5",
        "case_length_in": "15.0",
        "case_width_in": "10.0",
        "case_height_in": "8.0",
        "case_pack_qty": "12",
        "country_of_origin": "USA",
        "category": "Condiments",
        "product_description": "Small-batch fermented hot sauce",
        "wholesale_price": "42.00",
        "list_price": "59.99",
        "map_price": "49.99",
        "ti": "8",
        "hi": "5",
        "pallet_weight_lb": "1680.0",
        "shelf_life_days": "365",
    }


def _valid_kehe_product() -> dict:
    """Product that passes KeHE validation (case-level GTIN-14)."""
    return {
        "product_name": "Cinderhaven Reserve Hot Sauce",
        "brand": "Cinderhaven",
        "upc": "10049000004509",
        "case_gross_weight_lb": "12.5",
        "case_length_in": "15.0",
        "case_width_in": "10.0",
        "case_height_in": "8.0",
        "case_pack_qty": "12",
        "country_of_origin": "USA",
        "category": "Condiments",
        "product_description": "Small-batch fermented hot sauce",
        "wholesale_price": "42.00",
        "list_price": "59.99",
        "cases_per_layer": "8",
        "layers_per_pallet": "5",
        "pallet_weight_lb": "1680.0",
        "shelf_life_days": "365",
    }


# ---------------------------------------------------------------------------
# Test: All four schemas load via schema_loader
# ---------------------------------------------------------------------------

class TestAllSchemasLoad:
    """Every YAML schema file must load and produce a valid SchemaConfig."""

    def test_walmart_loads(self):
        schema = load_schema(WALMART_YAML)
        assert schema.partner == "walmart"
        assert schema.display_name == "Walmart"
        assert len(schema.required_fields) > 0
        assert schema.gtin_hierarchy.expected_level == "consumer_unit"

    def test_costco_loads(self):
        schema = load_schema(COSTCO_YAML)
        assert schema.partner == "costco"
        assert schema.display_name == "Costco"
        assert len(schema.required_fields) > 0
        assert schema.gtin_hierarchy.expected_level == "case"

    def test_unfi_loads(self):
        schema = load_schema(UNFI_YAML)
        assert schema.partner == "unfi"
        assert schema.display_name == "UNFI"
        assert len(schema.required_fields) > 0
        assert schema.gtin_hierarchy.expected_level == "case"

    def test_kehe_loads(self):
        schema = load_schema(KEHE_YAML)
        assert schema.partner == "kehe"
        assert schema.display_name == "KeHE"
        assert len(schema.required_fields) > 0
        assert schema.gtin_hierarchy.expected_level == "case"


# ---------------------------------------------------------------------------
# Test: GTIN hierarchy divergence (the credibility marker)
# ---------------------------------------------------------------------------

class TestGTINHierarchyDivergence:
    """The core insight: Walmart expects consumer-unit UPC-12, Costco
    expects case-level GTIN-14. The same product cannot pass both
    without the right GTIN for each.

    The divergence surfaces at two tiers:
    - Tier 2 (format): UPC-12 is 12 digits, fails Costco's 14-digit pattern
    - Tier 4 (GTIN hierarchy): catches wrong GTIN type when format passes

    Tier 2 fires first and prevents Tier 4 from cascading (by design).
    The format pattern IS the primary enforcement mechanism.
    """

    def test_upc12_passes_walmart_fails_costco(self):
        """Same SKU with UPC-12: PASS Walmart, FAIL Costco on format."""
        walmart = _walmart_schema()
        costco = _costco_schema()
        product = _valid_walmart_product()

        # Walmart: UPC-12 passes everything
        walmart_result = validate_product(product, walmart)
        assert walmart_result.verdict == "PASS"
        upc_errors = [e for e in walmart_result.errors if e.field == "upc"]
        assert len(upc_errors) == 0

        # Costco: UPC-12 fails format (12 digits vs. expected 14)
        # Also missing Costco-specific required fields, but the UPC failure
        # is what matters for the GTIN divergence demonstration.
        costco_result = validate_product(product, costco)
        assert costco_result.verdict == "FAIL"
        upc_format_errors = [
            e for e in costco_result.errors
            if e.field == "upc" and e.error_type == ErrorType.FORMAT_INVALID
        ]
        assert len(upc_format_errors) == 1
        assert "14-digit" in upc_format_errors[0].message

    def test_gtin14_passes_costco_fails_walmart(self):
        """Same SKU with GTIN-14: PASS Costco, FAIL Walmart on format."""
        walmart = _walmart_schema()
        costco = _costco_schema()
        costco_product = _valid_costco_product()

        # Costco: GTIN-14 passes everything
        costco_result = validate_product(costco_product, costco)
        upc_errors = [e for e in costco_result.errors if e.field == "upc"]
        assert len(upc_errors) == 0

        # Create a Walmart-shaped product but with the GTIN-14
        walmart_product = _valid_walmart_product()
        walmart_product["upc"] = "10049000004509"

        # Walmart: GTIN-14 fails format (14 digits vs. expected 12)
        walmart_result = validate_product(walmart_product, walmart)
        assert walmart_result.verdict == "FAIL"
        upc_format_errors = [
            e for e in walmart_result.errors
            if e.field == "upc" and e.error_type == ErrorType.FORMAT_INVALID
        ]
        assert len(upc_format_errors) == 1
        assert "12-digit" in upc_format_errors[0].message

    def test_gtin_hierarchy_tier_catches_wrong_type_when_format_unset(self):
        """When format_pattern is absent, Tier 4 GTIN hierarchy check
        catches the type mismatch directly. This tests the expected_formats
        mechanism independently of Tier 2.
        """
        # Schema expects GTIN-14 but has no format_pattern on upc
        costco_no_format = SchemaConfig.model_validate({
            "partner": "costco",
            "display_name": "Costco",
            "description": "test",
            "required_fields": [
                {"name": "product_name", "required": True},
                {"name": "upc", "required": True},
            ],
            "conditional_rules": [],
            "gtin_hierarchy": {
                "expected_level": "case",
                "expected_formats": ["GTIN-14", "ITF-14"],
            },
        })

        # UPC-12 product passes format (no pattern) but fails GTIN hierarchy
        product = {"product_name": "Test", "upc": "049000004502"}
        result = validate_product(product, costco_no_format)

        gtin_errors = [
            e for e in result.errors
            if e.error_type == ErrorType.GTIN_HIERARCHY_WRONG
        ]
        assert len(gtin_errors) == 1
        assert "GTIN-12" in gtin_errors[0].message
        assert "Costco" in gtin_errors[0].message

    def test_gtin14_expected_formats_match(self):
        """Costco and UNFI both expect GTIN-14/ITF-14, and these formats
        resolve to the same GTINType in the validator.
        """
        costco = load_schema(COSTCO_YAML)
        unfi = load_schema(UNFI_YAML)
        kehe = load_schema(KEHE_YAML)

        for schema in (costco, unfi, kehe):
            assert "GTIN-14" in schema.gtin_hierarchy.expected_formats
            assert "ITF-14" in schema.gtin_hierarchy.expected_formats

        walmart = load_schema(WALMART_YAML)
        assert "GTIN-12" in walmart.gtin_hierarchy.expected_formats
        assert "GTIN-14" not in walmart.gtin_hierarchy.expected_formats


# ---------------------------------------------------------------------------
# Test: Costco conditional rules
# ---------------------------------------------------------------------------

class TestCostcoConditionalRules:
    """Costco club membership tier triggers additional fields."""

    def test_executive_tier_triggers_extra_fields(self):
        """Setting club_membership_tier=Executive requires price and discount."""
        costco = _costco_schema()
        product = _valid_costco_product()
        product["club_membership_tier"] = "Executive"
        # executive_member_price and executive_discount_pct missing

        result = validate_product(product, costco)

        conditional_errors = [
            e for e in result.errors
            if e.error_type == ErrorType.CONDITIONAL_REQUIREMENT_MISSING
        ]
        missing_fields = {e.field for e in conditional_errors}
        assert "executive_member_price" in missing_fields
        assert "executive_discount_pct" in missing_fields

    def test_non_executive_tier_skips_extra_fields(self):
        """Non-Executive membership does not trigger extra fields."""
        costco = _costco_schema()
        product = _valid_costco_product()
        product["club_membership_tier"] = "Gold Star"

        result = validate_product(product, costco)

        conditional_errors = [
            e for e in result.errors
            if e.error_type == ErrorType.CONDITIONAL_REQUIREMENT_MISSING
        ]
        assert len(conditional_errors) == 0

    def test_executive_fields_present_passes(self):
        """Executive tier with all required fields present passes."""
        costco = _costco_schema()
        product = _valid_costco_product()
        product["club_membership_tier"] = "Executive"
        product["executive_member_price"] = "45.99"
        product["executive_discount_pct"] = "10"

        result = validate_product(product, costco)

        conditional_errors = [
            e for e in result.errors
            if e.error_type == ErrorType.CONDITIONAL_REQUIREMENT_MISSING
        ]
        assert len(conditional_errors) == 0


# ---------------------------------------------------------------------------
# Test: UNFI and KeHE validation
# ---------------------------------------------------------------------------

class TestUNFIAndKeHEValidation:
    """UNFI and KeHE schemas validate without errors on well-formed products."""

    def test_valid_unfi_product_passes(self):
        unfi = load_schema(UNFI_YAML)
        product = _valid_unfi_product()
        result = validate_product(product, unfi)
        assert result.verdict == "PASS"
        assert len(result.errors) == 0

    def test_valid_kehe_product_passes(self):
        kehe = load_schema(KEHE_YAML)
        product = _valid_kehe_product()
        result = validate_product(product, kehe)
        assert result.verdict == "PASS"
        assert len(result.errors) == 0

    def test_unfi_product_passes_kehe_with_minor_gaps(self):
        """A product prepared for UNFI should need only minor additions
        for KeHE — demonstrating the structural similarity.

        The UNFI product has ti/hi; KeHE wants cases_per_layer/layers_per_pallet.
        The UNFI product has map_price; KeHE does not require it.
        """
        kehe = load_schema(KEHE_YAML)
        unfi_product = _valid_unfi_product()

        # Validate UNFI product against KeHE without any changes
        result = validate_product(unfi_product, kehe)

        # Should fail only on fields named differently between the two
        missing_fields = {
            e.field for e in result.errors
            if e.error_type == ErrorType.PRESENCE_MISSING
        }
        # KeHE uses cases_per_layer and layers_per_pallet instead of ti/hi
        assert "cases_per_layer" in missing_fields
        assert "layers_per_pallet" in missing_fields

        # Shared fields should all pass — no presence errors on these
        shared_should_pass = {
            "product_name", "brand", "upc", "case_gross_weight_lb",
            "case_length_in", "case_width_in", "case_height_in",
            "case_pack_qty", "country_of_origin", "category",
            "product_description", "wholesale_price", "list_price",
            "pallet_weight_lb", "shelf_life_days",
        }
        for field in shared_should_pass:
            assert field not in missing_fields, (
                f"'{field}' should be present in UNFI product and pass KeHE"
            )


# ---------------------------------------------------------------------------
# Test: Structural similarity between UNFI and KeHE
# ---------------------------------------------------------------------------

class TestStructuralSimilarity:
    """UNFI and KeHE are broadline distributors with very similar schemas.
    The structural overlap should be visible in the YAML.
    """

    def test_shared_required_field_names(self):
        """UNFI and KeHE share a high percentage of required field names."""
        unfi = load_schema(UNFI_YAML)
        kehe = load_schema(KEHE_YAML)

        unfi_fields = {f.name for f in unfi.required_fields}
        kehe_fields = {f.name for f in kehe.required_fields}

        shared = unfi_fields & kehe_fields
        total_unique = unfi_fields | kehe_fields

        overlap_pct = len(shared) / len(total_unique)

        # At least 70% field name overlap — these are structurally similar
        assert overlap_pct >= 0.70, (
            f"Expected >= 70% field overlap between UNFI and KeHE, "
            f"got {overlap_pct:.0%}. "
            f"Shared: {sorted(shared)}, "
            f"UNFI-only: {sorted(unfi_fields - kehe_fields)}, "
            f"KeHE-only: {sorted(kehe_fields - unfi_fields)}"
        )

    def test_gtin_hierarchy_matches(self):
        """UNFI and KeHE both expect case-level GTIN-14/ITF-14."""
        unfi = load_schema(UNFI_YAML)
        kehe = load_schema(KEHE_YAML)

        assert unfi.gtin_hierarchy.expected_level == kehe.gtin_hierarchy.expected_level
        assert set(unfi.gtin_hierarchy.expected_formats) == set(kehe.gtin_hierarchy.expected_formats)

    def test_conditional_rules_structurally_similar(self):
        """UNFI and KeHE share storage-type and promo conditional triggers."""
        unfi = load_schema(UNFI_YAML)
        kehe = load_schema(KEHE_YAML)

        unfi_triggers = {
            (r.trigger_field, r.trigger_value) for r in unfi.conditional_rules
        }
        kehe_triggers = {
            (r.trigger_field, r.trigger_value) for r in kehe.conditional_rules
        }

        # Both should have storage_type conditionals
        assert ("storage_type", "Refrigerated") in unfi_triggers
        assert ("storage_type", "Refrigerated") in kehe_triggers

        # Both should have promo deal conditionals
        assert ("has_promo_deal", "true") in unfi_triggers
        assert ("has_promo_deal", "true") in kehe_triggers

    def test_naming_divergence_is_the_main_difference(self):
        """The divergence between UNFI and KeHE is mainly naming:
        ti vs cases_per_layer, hi vs layers_per_pallet.
        """
        unfi = load_schema(UNFI_YAML)
        kehe = load_schema(KEHE_YAML)

        unfi_fields = {f.name for f in unfi.required_fields}
        kehe_fields = {f.name for f in kehe.required_fields}

        unfi_only = unfi_fields - kehe_fields
        kehe_only = kehe_fields - unfi_fields

        # UNFI has ti, hi, map_price; KeHE has cases_per_layer, layers_per_pallet
        assert "ti" in unfi_only
        assert "hi" in unfi_only
        assert "cases_per_layer" in kehe_only
        assert "layers_per_pallet" in kehe_only
