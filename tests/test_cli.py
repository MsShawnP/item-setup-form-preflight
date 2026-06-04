"""Tests for the audit CLI.

Uses click's CliRunner to invoke the CLI without spawning a subprocess.
Test CSV fixtures are created inline via tmp_path.
"""

from __future__ import annotations

import json
import pathlib
import textwrap

from click.testing import CliRunner

from src.cli.audit import cli


def _valid_walmart_csv() -> str:
    """CSV with rows that pass all Walmart validation tiers."""
    return textwrap.dedent("""\
        product_name,brand,upc,case_gross_weight_lb,case_length_in,case_width_in,case_height_in,case_pack_qty,country_of_origin,category,product_description,serving_size,calories,total_fat_g,sodium_mg
        Cinderhaven Reserve Hot Sauce,Cinderhaven,049000004502,12.5,15.0,10.0,8.0,12,USA,Condiments,Small-batch fermented hot sauce,1 tsp (5mL),5,0,110
        Cinderhaven Mild Salsa,Cinderhaven,012345678905,8.0,12.0,9.0,7.0,6,USA,Condiments,Mild garden salsa,2 tbsp (30mL),10,0,95
    """)


def _failing_walmart_csv() -> str:
    """CSV with rows that have validation errors."""
    return textwrap.dedent("""\
        product_name,brand,upc,case_gross_weight_lb,case_length_in,case_width_in,case_height_in,case_pack_qty,country_of_origin,category,product_description,serving_size,calories,total_fat_g,sodium_mg,storage_type
        Artisan Preserves 12oz,Cinderhaven,049000004509,twelve,15.0,10.0,8.0,12,USA,Condiments,Artisan fruit preserves,1 tbsp (15mL),50,0,5,
        Heritage Jam 8oz,Cinderhaven,012345678905,8.0,12.0,9.0,7.0,6,USA,Condiments,Heritage recipe jam,2 tbsp (30mL),60,0.5,10,Refrigerated
    """)


def _mixed_walmart_csv() -> str:
    """CSV with one passing and one failing row."""
    return textwrap.dedent("""\
        product_name,brand,upc,case_gross_weight_lb,case_length_in,case_width_in,case_height_in,case_pack_qty,country_of_origin,category,product_description,serving_size,calories,total_fat_g,sodium_mg
        Cinderhaven Reserve Hot Sauce,Cinderhaven,049000004502,12.5,15.0,10.0,8.0,12,USA,Condiments,Small-batch fermented hot sauce,1 tsp (5mL),5,0,110
        Missing Fields Product,Cinderhaven,,8.0,12.0,9.0,7.0,6,USA,Condiments,Something,,,,
    """)


def _aliased_header_csv() -> str:
    """CSV using common aliases instead of exact schema field names."""
    return textwrap.dedent("""\
        Item Description,Brand Name,UPC Number,Gross Weight,Length,Width,Height,Pack Qty,Country,Department,Long Description,Serving Size,Calories,Total Fat,Sodium
        Cinderhaven Reserve Hot Sauce,Cinderhaven,049000004502,12.5,15.0,10.0,8.0,12,USA,Condiments,Small-batch fermented hot sauce,1 tsp (5mL),5,0,110
    """)


def _write_csv(tmp_path: pathlib.Path, content: str, name: str = "master.csv") -> pathlib.Path:
    """Write CSV content to a temp file and return the path."""
    csv_file = tmp_path / name
    csv_file.write_text(content, encoding="utf-8")
    return csv_file


class TestHappyPath:
    """Tests for successful audit runs."""

    def test_valid_file_exits_zero(self, tmp_path: pathlib.Path) -> None:
        """Valid file against walmart schema exits 0 with all-ready message."""
        csv_file = _write_csv(tmp_path, _valid_walmart_csv())
        runner = CliRunner()
        result = runner.invoke(cli, [
            "audit", str(csv_file),
            "--partner", "walmart",
            "--accept-mapping",
        ])

        assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}.\nOutput:\n{result.output}"
        assert "2 of 2 SKUs ready" in result.output

    def test_json_format_outputs_valid_json(self, tmp_path: pathlib.Path) -> None:
        """--format json outputs valid JSON matching the error contract."""
        csv_file = _write_csv(tmp_path, _valid_walmart_csv())
        runner = CliRunner()
        result = runner.invoke(cli, [
            "audit", str(csv_file),
            "--partner", "walmart",
            "--format", "json",
            "--accept-mapping",
        ])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2
        for row_result in data:
            assert "verdict" in row_result
            assert "errors" in row_result
            assert "tier_summary" in row_result
            assert row_result["verdict"] == "PASS"

    def test_accept_mapping_skips_prompt(self, tmp_path: pathlib.Path) -> None:
        """--accept-mapping flag skips the confirmation prompt."""
        csv_file = _write_csv(tmp_path, _valid_walmart_csv())
        runner = CliRunner()
        result = runner.invoke(cli, [
            "audit", str(csv_file),
            "--partner", "walmart",
            "--accept-mapping",
        ])

        # Should not contain the prompt text
        assert "Accept this mapping?" not in result.output
        assert result.exit_code == 0


class TestValidationFailures:
    """Tests for files with validation errors."""

    def test_failing_file_exits_two(self, tmp_path: pathlib.Path) -> None:
        """File with validation errors exits 2."""
        csv_file = _write_csv(tmp_path, _failing_walmart_csv())
        runner = CliRunner()
        result = runner.invoke(cli, [
            "audit", str(csv_file),
            "--partner", "walmart",
            "--accept-mapping",
        ])

        assert result.exit_code == 2, f"Expected exit 2, got {result.exit_code}.\nOutput:\n{result.output}"
        assert "SKUs with issues" in result.output

    def test_failing_json_shows_errors(self, tmp_path: pathlib.Path) -> None:
        """JSON output for failing file includes error details."""
        csv_file = _write_csv(tmp_path, _failing_walmart_csv())
        runner = CliRunner()
        result = runner.invoke(cli, [
            "audit", str(csv_file),
            "--partner", "walmart",
            "--format", "json",
            "--accept-mapping",
        ])

        assert result.exit_code == 2
        data = json.loads(result.output)
        assert any(row["verdict"] == "FAIL" for row in data)
        # At least one error should exist
        all_errors = [e for row in data for e in row["errors"]]
        assert len(all_errors) > 0

    def test_mixed_file_shows_pass_and_fail_counts(self, tmp_path: pathlib.Path) -> None:
        """File with mixed results shows both pass and fail counts."""
        csv_file = _write_csv(tmp_path, _mixed_walmart_csv())
        runner = CliRunner()
        result = runner.invoke(cli, [
            "audit", str(csv_file),
            "--partner", "walmart",
            "--accept-mapping",
        ])

        assert result.exit_code == 2
        assert "1 of 2 SKUs ready" in result.output
        assert "1 SKUs with issues" in result.output


class TestErrorHandling:
    """Tests for error conditions."""

    def test_file_not_found_exits_two(self) -> None:
        """Non-existent file path produces clear error from click."""
        runner = CliRunner()
        result = runner.invoke(cli, [
            "audit", "nonexistent_file.csv",
            "--partner", "walmart",
            "--accept-mapping",
        ])

        # click.Path(exists=True) catches this before our code runs,
        # producing exit code 2
        assert result.exit_code == 2
        assert "does not exist" in result.output or "Error" in result.output

    def test_unknown_partner_exits_two(self, tmp_path: pathlib.Path) -> None:
        """Unknown partner name produces error exit from click."""
        csv_file = _write_csv(tmp_path, _valid_walmart_csv())
        runner = CliRunner()
        result = runner.invoke(cli, [
            "audit", str(csv_file),
            "--partner", "target",
            "--accept-mapping",
        ])

        # click.Choice catches this before our code runs, exit code 2
        assert result.exit_code == 2
        assert "Invalid value" in result.output or "target" in result.output


class TestColumnMapping:
    """Tests for column mapping behavior."""

    def test_mapping_prompt_shown_without_accept_flag(self, tmp_path: pathlib.Path) -> None:
        """Without --accept-mapping, the mapping is shown and user is prompted."""
        csv_file = _write_csv(tmp_path, _valid_walmart_csv())
        runner = CliRunner()
        # Provide 'y' as input to confirm the mapping
        result = runner.invoke(cli, [
            "audit", str(csv_file),
            "--partner", "walmart",
        ], input="y\n")

        assert result.exit_code == 0
        assert "Column Mapping:" in result.output
        assert "Accept this mapping?" in result.output

    def test_mapping_rejected_exits_one(self, tmp_path: pathlib.Path) -> None:
        """Rejecting the mapping prompt exits with message."""
        csv_file = _write_csv(tmp_path, _valid_walmart_csv())
        runner = CliRunner()
        result = runner.invoke(cli, [
            "audit", str(csv_file),
            "--partner", "walmart",
        ], input="n\n")

        assert result.exit_code == 1
        assert "rejected" in result.output.lower() or "Review" in result.output

    def test_aliased_headers_are_matched(self, tmp_path: pathlib.Path) -> None:
        """Aliased column headers are matched to schema fields."""
        csv_file = _write_csv(tmp_path, _aliased_header_csv())
        runner = CliRunner()
        result = runner.invoke(cli, [
            "audit", str(csv_file),
            "--partner", "walmart",
            "--accept-mapping",
        ])

        # The fuzzy matcher should pick up the aliases. The row has
        # valid data, so if matching works, most fields pass.
        # We verify the mapping section shows matched status.
        assert "Column Mapping:" in result.output
        assert "matched" in result.output.lower()


class TestPartnerSchemas:
    """Verify the CLI works with each partner schema."""

    def test_costco_partner_loads(self, tmp_path: pathlib.Path) -> None:
        """Costco schema loads without error (exit may be non-zero due to data mismatch)."""
        csv_file = _write_csv(tmp_path, _valid_walmart_csv())
        runner = CliRunner()
        result = runner.invoke(cli, [
            "audit", str(csv_file),
            "--partner", "costco",
            "--accept-mapping",
        ])

        # Should not exit 1 (runtime error); exit 0 or 2 are both valid
        assert result.exit_code in (0, 2), f"Unexpected exit {result.exit_code}.\nOutput:\n{result.output}"
        assert "Partner: Costco" in result.output

    def test_unfi_partner_loads(self, tmp_path: pathlib.Path) -> None:
        """UNFI schema loads without error."""
        csv_file = _write_csv(tmp_path, _valid_walmart_csv())
        runner = CliRunner()
        result = runner.invoke(cli, [
            "audit", str(csv_file),
            "--partner", "unfi",
            "--accept-mapping",
        ])

        assert result.exit_code in (0, 2)
        assert "Partner: UNFI" in result.output

    def test_kehe_partner_loads(self, tmp_path: pathlib.Path) -> None:
        """KeHE schema loads without error."""
        csv_file = _write_csv(tmp_path, _valid_walmart_csv())
        runner = CliRunner()
        result = runner.invoke(cli, [
            "audit", str(csv_file),
            "--partner", "kehe",
            "--accept-mapping",
        ])

        assert result.exit_code in (0, 2)
        assert "Partner: KeHE" in result.output
