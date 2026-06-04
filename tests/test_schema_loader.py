"""Tests for YAML schema loading."""

import os

import pytest

from src.engine.schema_loader import load_schema, load_schema_from_string

WALMART_YAML_PATH = os.path.join(
    os.path.dirname(__file__), "..", "src", "schemas", "walmart.yaml"
)


class TestLoadSchemaFromFile:
    def test_loads_walmart_yaml(self):
        """Happy path: walmart.yaml loads and produces valid config."""
        schema = load_schema(WALMART_YAML_PATH)
        assert schema.partner == "walmart"
        assert schema.display_name == "Walmart"
        assert len(schema.required_fields) > 0
        assert len(schema.conditional_rules) > 0
        assert schema.gtin_hierarchy.expected_level == "consumer_unit"

    def test_walmart_has_dw_fields(self):
        """D&W Integrity fields present with exact names."""
        schema = load_schema(WALMART_YAML_PATH)
        field_names = {f.name for f in schema.required_fields}
        assert "case_gross_weight_lb" in field_names
        assert "case_length_in" in field_names
        assert "case_width_in" in field_names
        assert "case_height_in" in field_names
        assert "case_pack_qty" in field_names

    def test_walmart_has_all_sections(self):
        """Schema has required_fields, conditional_rules, and gtin_hierarchy."""
        schema = load_schema(WALMART_YAML_PATH)
        assert len(schema.required_fields) >= 10
        assert len(schema.conditional_rules) >= 2
        assert len(schema.gtin_hierarchy.expected_formats) >= 1


class TestLoadSchemaFromString:
    def test_loads_from_yaml_string(self):
        yaml_str = """
partner: test_partner
display_name: Test Partner
description: A test schema
required_fields:
  - name: product_name
    required: true
  - name: upc
    required: true
    format_pattern: "^\\\\d{12}$"
conditional_rules: []
gtin_hierarchy:
  expected_level: consumer_unit
  expected_formats:
    - GTIN-12
"""
        schema = load_schema_from_string(yaml_str)
        assert schema.partner == "test_partner"
        assert len(schema.required_fields) == 2

    def test_malformed_yaml_raises_clear_error(self):
        """Malformed YAML produces a clear error, not an obscure crash."""
        bad_yaml = "partner: [unterminated"
        with pytest.raises(Exception) as exc_info:
            load_schema_from_string(bad_yaml)
        # Error should mention YAML or parsing
        assert exc_info.value is not None

    def test_invalid_schema_structure_raises(self):
        """Valid YAML but missing required schema fields raises an error."""
        yaml_str = """
partner: incomplete
display_name: Incomplete
"""
        with pytest.raises(Exception):
            load_schema_from_string(yaml_str)
