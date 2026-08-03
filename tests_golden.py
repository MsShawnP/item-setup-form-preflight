"""Demo golden-file lock + P1 regression tests for item-setup-form-preflight.

The golden test pins the shipped Cinderhaven demo dataset's per-partner bounce
counts so the deployed demo experience and the case-study figures (29/26/26/26)
cannot drift during the client-mode conversion. It runs the real audit pipeline
(parse_file -> match_columns -> validate_product), the same engine the browser
tool and CLI use.

The regression tests lock the 07-31 P1: INFO advisories are surfaced per row but
must NEVER flip a clean file to failing — neither the per-row verdict nor the
aggregate summary (both orchestrator blocks: do_validate and do_validate_rows).
"""

import json
import pathlib
import sys

REPO = pathlib.Path(__file__).parent
# The Pyodide orchestrator imports `engine.*` (no `src.` prefix); make that
# resolvable without disturbing the `src.engine.*` imports the rest use.
sys.path.insert(0, str(REPO / "src"))

from src.engine.column_matcher import MatchStatus, match_columns  # noqa: E402
from src.engine.file_parser import parse_file  # noqa: E402
from src.engine.schema_loader import load_schema  # noqa: E402
from src.engine.validators import validate_product  # noqa: E402

_MASTER = REPO / "data" / "cinderhaven" / "product_master.csv"
_PARTNERS = ("walmart", "costco", "unfi", "kehe")


def _schema(partner):
    return load_schema(str(REPO / "src" / "schemas" / f"{partner}.yaml"))


def _remap(row, mapping):
    remapped = {}
    for m in mapping.matches:
        if m.status == MatchStatus.MATCHED and m.uploaded_header is not None:
            remapped[m.schema_field] = row.get(m.uploaded_header)
    return remapped


def _partner_counts(partner):
    schema = _schema(partner)
    parsed = parse_file(_MASTER.read_bytes(), "product_master.csv")
    mapping = match_columns(parsed.headers, schema, parsed.rows)
    verdicts = [
        validate_product(_remap(r, mapping), schema).verdict for r in parsed.rows
    ]
    passing = sum(1 for v in verdicts if v == "PASS")
    return passing, len(verdicts) - passing


class TestDemoGolden:
    """Locks the shipped demo output. If this changes, the case-study numbers change."""

    def test_partner_bounce_counts_are_locked(self):
        # Regenerated against the current single-count engine (scripts/results/).
        # These are the published case-study figures.
        expected = {
            "walmart": (21, 29),
            "costco": (24, 26),
            "unfi": (24, 26),
            "kehe": (24, 26),
        }
        got = {p: _partner_counts(p) for p in _PARTNERS}
        assert got == expected

    def test_master_has_fifty_skus(self):
        parsed = parse_file(_MASTER.read_bytes(), "product_master.csv")
        assert parsed.row_count == 50


# --- P1 regression: INFO advisories must not flip clean -> failing --------------

# A fully-populated Walmart row with a VALID 12-digit UPC-A. It passes all four
# tiers but carries one INFO UPC_NOT_GTIN13 advisory (a 12-digit UPC that some
# systems prefer expressed as GTIN-13). This is the exact clean-file-with-INFO
# shape that the 07-31 bug rendered as failing.
_VALID_UPCS = ["614141000012", "614141000029", "614141000036"]


def _clean_walmart_row(upc):
    return {
        "product_name": "Habanero Hot Sauce",
        "brand": "Cinderhaven",
        "upc": upc,
        "case_gross_weight_lb": "12.5",
        "case_length_in": "10",
        "case_width_in": "8",
        "case_height_in": "6",
        "case_pack_qty": "12",
        "country_of_origin": "USA",
        "category": "Condiments",
        "product_description": "A small-batch hot sauce",
        "serving_size": "1 tbsp",
        "calories": "10",
        "total_fat_g": "0",
        "sodium_mg": "120",
    }


class TestCleanCountRegression:
    """07-31 P1: an INFO-only row is clean, in the engine and in both aggregates."""

    def test_valid_upc_row_passes_with_info_advisory_only(self):
        schema = _schema("walmart")
        for upc in _VALID_UPCS:
            result = validate_product(_clean_walmart_row(upc), schema)
            assert result.verdict == "PASS", f"{upc} wrongly failed"
            assert result.errors, "expected the INFO advisory to be surfaced"
            assert all(e.severity.value == "INFO" for e in result.errors)

    def test_do_validate_rows_aggregate_ignores_info(self):
        # The JS-side worker entry point. A file of clean-but-INFO rows must
        # aggregate as all-pass with no issue-type counts and no red bar.
        import engine.orchestrator as orch

        orch.load_schema = lambda _path: _schema("walmart")
        rows = [_clean_walmart_row(u) for u in _VALID_UPCS]
        mapping = {k: k for k in rows[0]}
        out = json.loads(
            orch.do_validate_rows(json.dumps(rows), json.dumps(mapping), "walmart")
        )
        s = out["summary"]
        assert s["totalRows"] == 3
        assert s["passing"] == 3
        assert s["failing"] == 0
        assert s["errorTypeCounts"] == {}
        assert s["topFailingFields"] == []

    def test_do_validate_aggregate_ignores_info(self):
        # The Pyodide-FS entry point (do_validate) has a duplicate aggregate
        # block; lock it too via the module-level parse cache.
        import types

        import engine.orchestrator as orch

        orch.load_schema = lambda _path: _schema("walmart")
        rows = [_clean_walmart_row(u) for u in _VALID_UPCS]
        orch._cached_parse = types.SimpleNamespace(rows=rows)
        mapping = {k: k for k in rows[0]}
        out = json.loads(orch.do_validate(json.dumps(mapping), "walmart"))
        s = out["summary"]
        assert s["passing"] == 3
        assert s["failing"] == 0
        assert s["errorTypeCounts"] == {}
        assert s["topFailingFields"] == []

    def test_real_failures_still_count_in_aggregate(self):
        # Negative control: a genuine CRITICAL (missing required field) must
        # still register, so the INFO skip is severity-specific, not a blanket
        # "drop all errors from the aggregate".
        import engine.orchestrator as orch

        orch.load_schema = lambda _path: _schema("walmart")
        bad = _clean_walmart_row("614141000012")
        bad["brand"] = ""  # a required field -> CRITICAL presence error
        rows = [bad]
        mapping = {k: k for k in rows[0]}
        out = json.loads(
            orch.do_validate_rows(json.dumps(rows), json.dumps(mapping), "walmart")
        )
        s = out["summary"]
        assert s["failing"] == 1
        assert s["errorTypeCounts"].get("PRESENCE_MISSING") == 1
