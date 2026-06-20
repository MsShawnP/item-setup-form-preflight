"""Analyze validation results from all 4 partners."""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
from collections import Counter, defaultdict
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "results"
PARTNERS = ["walmart", "costco", "unfi", "kehe"]

# Load product master for SKU lookup
import csv
MASTER = Path(__file__).parent.parent / "data" / "cinderhaven" / "product_master.csv"
with open(MASTER, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    skus = {i+2: row for i, row in enumerate(reader)}


def analyze():
    all_results = {}
    for partner in PARTNERS:
        with open(RESULTS_DIR / f"{partner}.json") as f:
            all_results[partner] = json.load(f)

    print("=" * 70)
    print("VALIDATION RESULTS SUMMARY — 50 SKUs × 4 Partners")
    print("=" * 70)

    # Per-partner bounce counts
    print("\n── Per-partner bounce counts ──")
    bounce_counts = {}
    for partner in PARTNERS:
        results = all_results[partner]
        fails = sum(1 for r in results if r["verdict"] == "FAIL")
        passes = sum(1 for r in results if r["verdict"] == "PASS")
        bounce_counts[partner] = fails
        print(f"  {partner:>8}: {fails} of 50 would bounce ({passes} pass)")

    # Per-partner error breakdown by tier
    print("\n── Error breakdown by tier ──")
    for partner in PARTNERS:
        results = all_results[partner]
        tier_totals = Counter()
        tier_skus = defaultdict(set)
        for r in results:
            for tier, count in r["tier_summary"].items():
                tier_totals[tier] += count
                if count > 0:
                    tier_skus[tier].add(r["row"])
        print(f"\n  {partner.upper()}:")
        for tier in ["presence", "format", "conditional", "gtin"]:
            print(f"    {tier:>12}: {tier_totals[tier]:>3} errors across {len(tier_skus[tier]):>2} SKUs")

    # Gap table: which fields are failing and how many SKUs
    print("\n── Gap table (all partners combined) ──")
    field_failures = defaultdict(lambda: defaultdict(set))  # field -> error_type -> set of rows
    for partner in PARTNERS:
        for r in all_results[partner]:
            for err in r["errors"]:
                field_failures[err["field"]][err["error_type"]].add(r["row"])

    print(f"\n  {'Field':<30} {'Error Type':<30} {'SKUs':>5} {'Share':>6}")
    print(f"  {'-'*30} {'-'*30} {'-'*5} {'-'*6}")
    for field in sorted(field_failures.keys()):
        for etype in sorted(field_failures[field].keys()):
            n = len(field_failures[field][etype])
            pct = f"{n/50*100:.0f}%"
            print(f"  {field:<30} {etype:<30} {n:>5} {pct:>6}")

    # Per-partner field gap table
    print("\n── Per-partner gap detail ──")
    for partner in PARTNERS:
        results = all_results[partner]
        field_errs = defaultdict(lambda: defaultdict(set))
        for r in results:
            for err in r["errors"]:
                field_errs[err["field"]][err["error_type"]].add(r["row"])

        print(f"\n  {partner.upper()}:")
        print(f"    {'Field':<30} {'Error Type':<25} {'SKUs':>5} {'Share':>6}")
        for field in sorted(field_errs.keys()):
            for etype in sorted(field_errs[field].keys()):
                n = len(field_errs[field][etype])
                pct = f"{n/50*100:.0f}%"
                print(f"    {field:<30} {etype:<25} {n:>5} {pct:>6}")

    # Correlation check: are any gap patterns perfectly correlated?
    print("\n── Correlation patterns ──")
    for partner in PARTNERS:
        results = all_results[partner]
        # Build sets of failing rows per field
        fail_sets = defaultdict(set)
        for r in results:
            for err in r["errors"]:
                fail_sets[f"{err['field']}:{err['error_type']}"].add(r["row"])

        fields_list = sorted(fail_sets.keys())
        for i, f1 in enumerate(fields_list):
            for f2 in fields_list[i+1:]:
                if fail_sets[f1] == fail_sets[f2] and len(fail_sets[f1]) > 1:
                    print(f"  [{partner}] {f1} == {f2} (same {len(fail_sets[f1])} SKUs)")

    # Cross-partner patterns
    print("\n── Cross-partner bounce count comparison ──")
    for i, p1 in enumerate(PARTNERS):
        for p2 in PARTNERS[i+1:]:
            if bounce_counts[p1] == bounce_counts[p2]:
                # Check if same SKUs
                fails_p1 = {r["row"] for r in all_results[p1] if r["verdict"] == "FAIL"}
                fails_p2 = {r["row"] for r in all_results[p2] if r["verdict"] == "FAIL"}
                overlap = len(fails_p1 & fails_p2)
                print(f"  {p1} == {p2}: both {bounce_counts[p1]} bounces "
                      f"(overlap: {overlap} same SKUs)")

    # GTIN hierarchy analysis
    print("\n── GTIN/UPC analysis ──")
    gtin_format_fail = defaultdict(set)
    gtin_tier4_fail = defaultdict(set)
    for partner in PARTNERS:
        for r in all_results[partner]:
            for err in r["errors"]:
                if err["field"] == "upc" and err["error_type"] == "FORMAT_INVALID":
                    gtin_format_fail[partner].add(r["row"])
                if err["error_type"] == "GTIN_HIERARCHY_WRONG":
                    gtin_tier4_fail[partner].add(r["row"])

    for partner in PARTNERS:
        fmt = len(gtin_format_fail.get(partner, set()))
        gtin = len(gtin_tier4_fail.get(partner, set()))
        print(f"  {partner:>8}: {fmt} UPC format failures, {gtin} GTIN hierarchy failures")

    # Hero SKU candidates
    print("\n── Hero SKU candidates (pass some, fail others) ──")
    sku_verdicts = defaultdict(dict)  # row -> {partner: verdict}
    for partner in PARTNERS:
        for r in all_results[partner]:
            sku_verdicts[r["row"]][partner] = r["verdict"]

    for row in sorted(sku_verdicts.keys()):
        verdicts = sku_verdicts[row]
        passes = [p for p, v in verdicts.items() if v == "PASS"]
        fails = [p for p, v in verdicts.items() if v == "FAIL"]
        if passes and fails:
            sku_info = skus.get(row, {})
            sku_id = sku_info.get("sku", f"row-{row}")
            name = sku_info.get("product_name", "?")
            print(f"  {sku_id} ({name}):")
            print(f"    PASS: {', '.join(passes)}")
            print(f"    FAIL: {', '.join(fails)}")
            # Show why it fails
            for partner in fails:
                errs = [e for r in all_results[partner] if r["row"] == row for e in r["errors"]]
                err_strs = [f"{e['field']}:{e['error_type']}" for e in errs]
                print(f"    [{partner}] {', '.join(err_strs)}")

    # If no hero candidates, note it
    hero_rows = [row for row, v in sku_verdicts.items()
                 if any(vv == "PASS" for vv in v.values()) and any(vv == "FAIL" for vv in v.values())]
    if not hero_rows:
        print("  (No SKUs pass some partners and fail others)")

    # Column mapping diagnostic
    print("\n── Column mapping note ──")
    print("  Partner-aware column matcher routes:")
    print("  - Walmart 'upc' → CSV 'upc' column (12-digit UPC-A)")
    print("  - Costco/UNFI/KeHE 'upc' → CSV 'gtin14' column (14-digit GTIN-14)")


if __name__ == "__main__":
    analyze()
