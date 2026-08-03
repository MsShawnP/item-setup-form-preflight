"""Client-mode tests for item-setup-form-preflight: intake, preflight, report.

Adversarial fixtures per checklist §6: a clean file (which must render clean —
the 07-31 INFO-counting P1), missing identifier column (blocked path), empty
file, headers-only, duplicate headers, BOM+semicolon with the identifier kept as
text, and the --final watermark drop. Skipped if lailara_engagement isn't
installed.
"""

import pytest

pytest.importorskip("lailara_engagement")

from lailara_engagement.errors import ReadError  # noqa: E402

import client_mode  # noqa: E402

# Headers that already equal the canonical Walmart field names, so only `upc`
# needs an explicit mapping (identity handles the rest).
_CLEAN_HEADERS = (
    "product_name,brand,upc,case_gross_weight_lb,case_length_in,case_width_in,"
    "case_height_in,case_pack_qty,country_of_origin,category,product_description,"
    "serving_size,calories,total_fat_g,sodium_mg"
)


def _clean_row(upc):
    return (f"Hot Sauce,Cinderhaven,{upc},12.5,10,8,6,12,USA,Condiments,"
            f"A sauce,1 tbsp,10,0,120")


_CONFIG = """
client: {name: Meridian Farms}
engagement: {id: MER-2026-08}
as_of_date: 2026-07-31
partner: walmart
demo: true
columns: {upc: "upc"}
"""


@pytest.fixture
def cfg(tmp_path):
    p = tmp_path / "engagement.demo.yml"
    p.write_text(_CONFIG, encoding="utf-8")
    return str(p)


def _write(tmp_path, name, text, encoding="utf-8"):
    p = tmp_path / name
    p.write_bytes(text.encode(encoding) if isinstance(text, str) else text)
    return str(p)


def test_clean_file_renders_clean(cfg, tmp_path):
    # Every valid UPC-A carries an INFO UPC_NOT_GTIN13 advisory; the file must
    # still read as all-ready — no bounces, no issue-by-type counts, no red bar.
    body = "\n".join([_CLEAN_HEADERS,
                      _clean_row("614141000012"),
                      _clean_row("614141000029"),
                      _clean_row("614141000036")]) + "\n"
    src = _write(tmp_path, "master.csv", body)
    out = str(tmp_path / "client-output")
    result = client_mode.run(cfg, src, out)
    assert result["status"] == "ok"
    assert result["total"] == 3
    assert result["passing"] == 3
    assert result["failing"] == 0            # INFO advisories do NOT bounce a SKU
    html = open(result["report"], encoding="utf-8").read()
    assert "Meridian Farms" in html
    assert "#f5f3ee" in html                 # branded canvas
    assert "SHA-256" in html                 # provenance footer
    assert "DRAFT" in html
    assert "submission-ready" in html        # clean banner, not a bounce banner
    assert "No blocking issues." in html     # aggregate carries no INFO-as-failure


def test_missing_identifier_column_is_blocked(cfg, tmp_path):
    # No column maps to upc -> Data Readiness Report, no results.
    src = _write(tmp_path, "bad.csv", "product,price\nA,1\nB,2\n")
    out = str(tmp_path / "out")
    result = client_mode.run(cfg, src, out)
    assert result["status"] == "blocked"
    html = open(result["readiness_report"], encoding="utf-8").read()
    assert "upc" in html.lower()


def test_bom_semicolon_and_identifier_as_text(cfg, tmp_path):
    # BOM + semicolon delimiter; leading-zero identifier kept as text.
    body = "﻿upc;product_name\n0614141000012;A\n614141000029;B\n"
    src = _write(tmp_path, "bom.csv", body)
    out = str(tmp_path / "out")
    result = client_mode.run(cfg, src, out)
    assert result["status"] == "ok"
    assert result["total"] == 2              # semicolon parsed, 2 SKUs
    csv_text = open(result["csv"], encoding="utf-8").read()
    assert "0614141000012" in csv_text       # leading zero survived (not coerced)


def test_empty_file_raises(cfg, tmp_path):
    src = _write(tmp_path, "empty.csv", "")
    out = str(tmp_path / "out")
    with pytest.raises(ReadError):
        client_mode.run(cfg, src, out)


def test_headers_only_reports_zero_skus(cfg, tmp_path):
    src = _write(tmp_path, "headers.csv", _CLEAN_HEADERS + "\n")
    out = str(tmp_path / "out")
    result = client_mode.run(cfg, src, out)
    assert result["status"] == "ok"
    assert result["total"] == 0

def test_duplicate_headers_still_runs(cfg, tmp_path):
    # Duplicate columns are de-duplicated by the reader; the run still produces
    # a report rather than crashing.
    body = "upc,upc,product_name\n614141000012,614141000012,A\n"
    src = _write(tmp_path, "dup.csv", body)
    out = str(tmp_path / "out")
    result = client_mode.run(cfg, src, out)
    assert result["status"] == "ok"
    assert result["total"] == 1


def test_final_flag_drops_watermark(cfg, tmp_path):
    body = _CLEAN_HEADERS + "\n" + _clean_row("614141000012") + "\n"
    src = _write(tmp_path, "master.csv", body)
    out = str(tmp_path / "out")
    result = client_mode.run(cfg, src, out, final=True)
    html = open(result["report"], encoding="utf-8").read()
    assert "ll-draft" not in html


def test_partner_from_config_used(cfg, tmp_path):
    # partner is read from the config when not passed on the CLI.
    body = _CLEAN_HEADERS + "\n" + _clean_row("614141000012") + "\n"
    src = _write(tmp_path, "master.csv", body)
    out = str(tmp_path / "out")
    result = client_mode.run(cfg, src, out)
    assert result["partner"] == "walmart"
