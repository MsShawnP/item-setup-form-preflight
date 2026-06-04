"""Tests for column_matcher.py — fuzzy alias matching engine."""

from src.engine.column_matcher import (
    MatchStatus,
    get_alias_map,
    match_columns,
)
from src.engine.models import SchemaConfig


def _walmart_schema() -> SchemaConfig:
    """Minimal Walmart-like schema for column matching tests."""
    return SchemaConfig.model_validate({
        "partner": "walmart",
        "display_name": "Walmart",
        "description": "Walmart Item 360 item setup requirements",
        "required_fields": [
            {"name": "product_name", "required": True},
            {"name": "brand", "required": True},
            {"name": "upc", "required": True},
            {"name": "case_gross_weight_lb", "required": True},
            {"name": "case_length_in", "required": True},
            {"name": "case_width_in", "required": True},
            {"name": "case_height_in", "required": True},
            {"name": "case_pack_qty", "required": True},
            {"name": "country_of_origin", "required": True},
            {"name": "category", "required": True},
        ],
        "conditional_rules": [],
        "gtin_hierarchy": {
            "expected_level": "consumer_unit",
            "expected_formats": ["GTIN-12"],
        },
    })


class TestFuzzyAliasMatching:
    def test_matches_common_aliases_to_schema_fields(self):
        """AE1: File with 'Item Width (in)', 'Gross Wt', 'UPC Number'
        matches to width, weight, GTIN fields."""
        schema = _walmart_schema()
        headers = [
            "Product Name",
            "Brand",
            "UPC Number",
            "Gross Wt",
            "Case Length",
            "Item Width (in)",
            "Case Height",
            "Pack Qty",
            "Country",
            "Category",
        ]

        result = match_columns(headers, schema)

        # Build lookup by schema field
        match_map = {m.schema_field: m for m in result.matches}

        # UPC Number -> upc
        assert match_map["upc"].status == MatchStatus.MATCHED
        assert match_map["upc"].uploaded_header == "UPC Number"
        assert match_map["upc"].confidence > 0.0

        # Gross Wt -> case_gross_weight_lb
        assert match_map["case_gross_weight_lb"].status == MatchStatus.MATCHED
        assert match_map["case_gross_weight_lb"].uploaded_header == "Gross Wt"

        # Item Width (in) -> case_width_in
        assert match_map["case_width_in"].status == MatchStatus.MATCHED
        assert match_map["case_width_in"].uploaded_header == "Item Width (in)"


class TestExactMatch:
    def test_matches_exact_schema_field_names(self):
        """Happy path: file with exact schema field names -> all matched
        with high confidence."""
        schema = _walmart_schema()
        headers = [
            "product_name", "brand", "upc",
            "case_gross_weight_lb", "case_length_in",
            "case_width_in", "case_height_in",
            "case_pack_qty", "country_of_origin", "category",
        ]

        result = match_columns(headers, schema)

        for match in result.matches:
            assert match.status == MatchStatus.MATCHED, (
                f"Expected {match.schema_field} to be MATCHED, "
                f"got {match.status}"
            )
            assert match.confidence == 1.0
            assert match.uploaded_header is not None

        assert result.unmatched_fields == []
        assert result.unmatched_headers == []


class TestCaseInsensitiveMatching:
    def test_matches_despite_case_mismatch(self):
        """Case mismatch ('ITEM WIDTH' vs 'item_width') still matches
        after normalization."""
        schema = _walmart_schema()
        headers = [
            "PRODUCT_NAME", "BRAND", "UPC",
            "CASE_GROSS_WEIGHT_LB", "CASE_LENGTH_IN",
            "CASE_WIDTH_IN", "CASE_HEIGHT_IN",
            "CASE_PACK_QTY", "COUNTRY_OF_ORIGIN", "CATEGORY",
        ]

        result = match_columns(headers, schema)

        for match in result.matches:
            assert match.status == MatchStatus.MATCHED, (
                f"Expected {match.schema_field} to be MATCHED "
                f"despite case, got {match.status}"
            )


class TestZeroMatchableColumns:
    def test_reports_all_fields_unmatched_when_no_overlap(self):
        """Edge case: file with zero matchable columns -> all fields
        unmatched, all headers in unmatched_headers."""
        schema = _walmart_schema()
        # Use names with no resemblance to any alias to avoid
        # false-positive fuzzy matches
        headers = ["zzz_alpha", "zzz_beta", "zzz_gamma", "zzz_delta"]

        result = match_columns(headers, schema)

        # Every schema field should be unmatched
        assert len(result.unmatched_fields) == len(schema.required_fields)

        # Every uploaded header should be unmatched
        assert set(result.unmatched_headers) == {
            "zzz_alpha", "zzz_beta", "zzz_gamma", "zzz_delta",
        }


class TestNoSilentDrops:
    def test_every_header_and_field_appears_in_result(self):
        """No silent drops: every uploaded column and every schema field
        appears in the result."""
        schema = _walmart_schema()
        headers = [
            "Product Name", "Brand", "UPC",
            "Gross Weight", "Length", "Width", "Height",
            "Case Pack", "Country of Origin", "Category",
            "Extra Column 1", "Extra Column 2",
        ]

        result = match_columns(headers, schema)

        # Every schema field appears in matches
        matched_fields = {m.schema_field for m in result.matches}
        schema_fields = {f.name for f in schema.required_fields}
        assert matched_fields == schema_fields

        # Every uploaded header is either matched or in unmatched_headers
        matched_headers = {
            m.uploaded_header for m in result.matches
            if m.uploaded_header is not None
        }
        all_accounted = matched_headers | set(result.unmatched_headers)
        assert all_accounted == set(headers)

    def test_extra_headers_appear_in_unmatched(self):
        """Headers that don't match any schema field show up in
        unmatched_headers."""
        schema = _walmart_schema()
        headers = [
            "product_name", "brand", "upc",
            "case_gross_weight_lb", "case_length_in",
            "case_width_in", "case_height_in",
            "case_pack_qty", "country_of_origin", "category",
            "internal_sku", "notes",
        ]

        result = match_columns(headers, schema)

        assert "internal_sku" in result.unmatched_headers
        assert "notes" in result.unmatched_headers


class TestDuplicateHeaders:
    def test_duplicate_header_not_matched_twice(self):
        """Edge case: duplicate column names in uploaded file are
        flagged — one matches, the duplicate ends up in unmatched."""
        schema = _walmart_schema()
        headers = [
            "product_name", "brand", "upc",
            "case_gross_weight_lb", "case_length_in",
            "case_width_in", "case_height_in",
            "case_pack_qty", "country_of_origin", "category",
            "upc",  # duplicate
        ]

        result = match_columns(headers, schema)

        # The upc field should be matched once
        upc_matches = [
            m for m in result.matches
            if m.schema_field == "upc" and m.status == MatchStatus.MATCHED
        ]
        assert len(upc_matches) == 1

        # The duplicate "upc" should appear in unmatched_headers
        # (since the field was already claimed by the first one)
        assert "upc" in result.unmatched_headers


class TestGetAliasMap:
    def test_returns_expected_keys(self):
        """get_alias_map returns a dict with known schema field keys."""
        alias_map = get_alias_map()

        assert "upc" in alias_map
        assert "case_gross_weight_lb" in alias_map
        assert "product_name" in alias_map

    def test_returns_copy_not_reference(self):
        """Modifying the returned map does not affect the internal map."""
        map1 = get_alias_map()
        map1["upc"].append("test_mutation")

        map2 = get_alias_map()
        assert "test_mutation" not in map2["upc"]
