"""Generate a 50-SKU product master CSV from the canonical defect profile.

Reads the reference CSV (50 SKUs with physical attributes) and applies
the deterministic defect profile from seed_config.py: ~20% corrupted
GTIN check digits and field-level missingness per MISSING_RATES.

Also adds columns required by the validation schemas that aren't in
the reference CSV (nutrition, pricing, pallet, shelf life).
"""
from __future__ import annotations

import csv
import random
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
REFERENCE_CSV = Path(r"C:\Users\mssha\projects\reference\lailara-data-assay\fixtures\cinderhaven\product_master.csv")
OUTPUT_CSV = PROJECT_ROOT / "data" / "cinderhaven" / "product_master.csv"

DEFECT_SEED = 300
GTIN_INVALID_RATE = 0.20

MISSING_RATES = {
    "case_length_in": 0.12,
    "case_width_in": 0.12,
    "case_height_in": 0.12,
    "unit_weight_lbs": 0.08,
    "case_weight_lbs": 0.08,
    "brand_owner": 0.02,
    "country_of_origin": 0.03,
    "subcategory": 0.10,
}

# Columns the preflight schemas validate but the reference CSV doesn't have.
# Values are realistic defaults for a specialty food brand.
EXTRA_COLUMNS = {
    "serving_size": "2 tbsp (30g)",
    "calories_per_serving": "80",
    "total_fat_g": "3.5",
    "sodium_mg": "210",
    "total_carb_g": "9.0",
    "protein_g": "1.5",
    "product_description": None,  # derived from product_name
    "category": None,  # derived from product_line
    "wholesale_price": None,  # derived from msrp
    "list_price": None,  # derived from msrp
    "map_price": None,  # derived from msrp
    "shelf_life_days": "365",
    "inner_pack_count": None,  # derived from case_pack_qty
    "club_pack_length_in": None,  # derived from case dims
    "club_pack_width_in": None,
    "club_pack_height_in": None,
    "ti": "8",
    "hi": "5",
    "cases_per_layer": "8",
    "layers_per_pallet": "5",
    "pallet_weight_lb": None,  # derived from case_weight
    "active_retailers": None,  # assigned per SKU
    "oneworldsync_status": "Not Registered",
    "updated_by": "inventory_admin",
}

# Retailer assignments by product line
RETAILER_ASSIGNMENTS = {
    "Artisan Sauces": [
        "UNFI; Whole Foods; Walmart; DTC",
        "UNFI; Whole Foods; Walmart; Costco; Regional; DTC",
        "Whole Foods; DTC",
        "Whole Foods; DTC",
        "UNFI; Whole Foods; Walmart; DTC",
        "Sprouts; Whole Foods; DTC",
        "UNFI; KeHE; Whole Foods; DTC",
        "UNFI; Whole Foods; Walmart; DTC",
        "Whole Foods; Sprouts; DTC",
        "UNFI; Walmart; Costco; DTC",
    ],
    "Pantry Staples": [
        "UNFI; KeHE; Walmart; DTC",
        "Whole Foods; Sprouts; DTC",
        "UNFI; Walmart; Kroger; DTC",
        "Whole Foods; Sprouts; DTC",
        "UNFI; KeHE; Walmart; Kroger; DTC",
        "UNFI; Walmart; DTC",
        "UNFI; KeHE; Whole Foods; DTC",
        "UNFI; KeHE; Walmart; DTC",
        "Whole Foods; Sprouts; DTC",
        "UNFI; KeHE; Walmart; DTC",
    ],
    "Specialty Condiments": [
        "UNFI; Whole Foods; Sprouts; DTC",
        "Whole Foods; DTC",
        "UNFI; KeHE; Walmart; DTC",
        "Whole Foods; Sprouts; DTC",
        "UNFI; KeHE; Walmart; Costco; DTC",
        "Whole Foods; DTC",
        "UNFI; KeHE; Walmart; DTC",
        "Whole Foods; Sprouts; DTC",
        "UNFI; Whole Foods; DTC",
        "Whole Foods; DTC",
    ],
    "Dried Goods": [
        "UNFI; KeHE; Walmart; DTC",
        "Whole Foods; Sprouts; DTC",
        "UNFI; Walmart; Kroger; DTC",
        "UNFI; KeHE; Walmart; DTC",
        "Whole Foods; Sprouts; DTC",
        "UNFI; KeHE; Walmart; DTC",
        "Whole Foods; Sprouts; DTC",
        "UNFI; Walmart; DTC",
        "UNFI; KeHE; Whole Foods; DTC",
        "UNFI; KeHE; Walmart; DTC",
    ],
    "Snack Bites": [
        "UNFI; KeHE; Walmart; Costco; DTC",
        "UNFI; KeHE; Walmart; DTC",
        "Whole Foods; Sprouts; DTC",
        "UNFI; Walmart; Kroger; DTC",
        "UNFI; KeHE; Walmart; DTC",
        "Whole Foods; Sprouts; DTC",
        "UNFI; KeHE; Walmart; DTC",
        "Whole Foods; Sprouts; DTC",
        "UNFI; KeHE; Walmart; DTC",
        "UNFI; KeHE; Walmart; Costco; DTC",
    ],
}


def _gtin14_check_digit(digits_13: str) -> str:
    total = 0
    for i, d in enumerate(digits_13):
        weight = 3 if i % 2 == 0 else 1
        total += int(d) * weight
    return str((10 - total % 10) % 10)


def _upc12_check_digit(digits_11: str) -> str:
    total = 0
    for i, d in enumerate(digits_11):
        weight = 3 if i % 2 == 0 else 1
        total += int(d) * weight
    return str((10 - total % 10) % 10)


def compute_defect_profile(n_skus: int = 50) -> dict:
    """Match the canonical compute_defect_profile() RNG sequence exactly.

    Uses the same seed, same draws in the same order as seed_config.py.
    UPC-12 values are generated with a separate RNG to avoid disturbing
    the canonical sequence.
    """
    rng = random.Random(DEFECT_SEED)
    upc_rng = random.Random(DEFECT_SEED + 1)  # separate stream for UPC-12
    profile = {}

    for i in range(n_skus):
        # GTIN-14: matches seed_config.py exactly
        prefix_13 = f"0061414{i:06d}"
        check14 = _gtin14_check_digit(prefix_13)
        valid_gtin = prefix_13 + check14

        is_gtin_valid = rng.random() >= GTIN_INVALID_RATE
        if is_gtin_valid:
            gtin14 = valid_gtin
        else:
            bad_check = str((int(check14) + rng.randint(1, 9)) % 10)
            gtin14 = prefix_13 + bad_check

        # seed_config does upc = gtin14[1:] here (13 digits) — we skip that
        # and generate proper 12-digit UPC-12 with a separate RNG

        # Field missingness: same draws as seed_config.py
        missing_fields = {}
        for field, rate in MISSING_RATES.items():
            missing_fields[field] = rng.random() < rate

        # UPC-12 on separate RNG stream (doesn't affect canonical sequence)
        upc_prefix_11 = f"61414{i:06d}"
        check12 = _upc12_check_digit(upc_prefix_11)
        valid_upc = upc_prefix_11 + check12

        is_upc_valid = upc_rng.random() >= GTIN_INVALID_RATE
        if is_upc_valid:
            upc = valid_upc
        else:
            bad_upc_check = str((int(check12) + upc_rng.randint(1, 9)) % 10)
            upc = upc_prefix_11 + bad_upc_check

        profile[i] = {
            "gtin14": gtin14,
            "upc": upc,
            "gtin14_valid": is_gtin_valid,
            "upc_valid": is_upc_valid,
            "missing_fields": missing_fields,
        }

    return profile


def main():
    if not REFERENCE_CSV.exists():
        print(f"ERROR: Reference CSV not found: {REFERENCE_CSV}", file=sys.stderr)
        sys.exit(1)

    # Read reference CSV
    with open(REFERENCE_CSV, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if len(rows) != 50:
        print(f"ERROR: Expected 50 rows, got {len(rows)}", file=sys.stderr)
        sys.exit(1)

    # Compute defect profile
    profile = compute_defect_profile(len(rows))

    # Build output rows
    output_headers = [
        "sku", "product_name", "product_line", "subcategory",
        "gtin14", "upc", "case_pack_qty", "unit_weight_lbs",
        "case_weight_lbs", "case_length_in", "case_width_in",
        "case_height_in", "msrp", "serving_size", "calories_per_serving",
        "total_fat_g", "sodium_mg", "total_carb_g", "protein_g",
        "brand_owner", "country_of_origin",
        "product_description", "category",
        "wholesale_price", "list_price", "map_price",
        "shelf_life_days",
        "inner_pack_count",
        "club_pack_length_in", "club_pack_width_in", "club_pack_height_in",
        "ti", "hi", "cases_per_layer", "layers_per_pallet",
        "pallet_weight_lb",
        "active_retailers", "oneworldsync_status",
        "last_updated", "updated_by",
    ]

    output_rows = []
    line_counters: dict[str, int] = {}
    rng_extra = random.Random(42)

    for i, row in enumerate(rows):
        defects = profile[i]
        missing = defects["missing_fields"]
        product_line = row["product_line"]

        # Track index within product line for retailer assignment
        line_counters.setdefault(product_line, 0)
        line_idx = line_counters[product_line]
        line_counters[product_line] += 1

        out = {}
        out["sku"] = row["sku"]
        out["product_name"] = row["product_name"]
        out["product_line"] = row["product_line"]
        out["subcategory"] = "" if missing.get("subcategory") else row.get("subcategory", row["product_line"])
        out["gtin14"] = defects["gtin14"]
        out["upc"] = defects["upc"]
        out["case_pack_qty"] = row["case_pack_qty"]
        out["unit_weight_lbs"] = "" if missing.get("unit_weight_lbs") else row["unit_weight_lbs"]
        out["case_weight_lbs"] = "" if missing.get("case_weight_lbs") else row["case_weight_lbs"]
        out["case_length_in"] = "" if missing.get("case_length_in") else row["case_length_in"]
        out["case_width_in"] = "" if missing.get("case_width_in") else row["case_width_in"]
        out["case_height_in"] = "" if missing.get("case_height_in") else row["case_height_in"]
        out["msrp"] = row["msrp"]

        # Nutrition: vary by product line
        nutrition_variance = {
            "Artisan Sauces": ("2 tbsp (30g)", 65, 3.0, 280, 8, 1.5),
            "Pantry Staples": ("1 tbsp (15g)", 45, 1.5, 150, 6, 0.5),
            "Specialty Condiments": ("2 tbsp (30g)", 80, 4.5, 310, 7, 2.0),
            "Dried Goods": ("1/4 cup (40g)", 160, 5.0, 120, 24, 6.0),
            "Snack Bites": ("1 oz (28g)", 140, 7.0, 180, 16, 4.0),
        }
        nut = nutrition_variance.get(product_line, ("30g", 80, 3.5, 210, 9, 1.5))
        base_cal, base_fat, base_sod, base_carb, base_prot = nut[1], nut[2], nut[3], nut[4], nut[5]
        out["serving_size"] = nut[0]
        out["calories_per_serving"] = str(round(base_cal + rng_extra.uniform(-20, 40)))
        out["total_fat_g"] = str(round(base_fat + rng_extra.uniform(-1, 3), 1))
        out["sodium_mg"] = str(round(base_sod + rng_extra.uniform(-80, 120)))
        out["total_carb_g"] = str(round(base_carb + rng_extra.uniform(-3, 8), 1))
        out["protein_g"] = str(round(base_prot + rng_extra.uniform(-0.5, 3), 1))

        out["brand_owner"] = "" if missing.get("brand_owner") else row.get("brand_owner", "Cinderhaven Provisions")
        out["country_of_origin"] = "" if missing.get("country_of_origin") else row.get("country_of_origin", "USA")

        out["product_description"] = f"{row['product_name']} - {product_line} by Cinderhaven Provisions"
        out["category"] = row.get("subcategory", product_line)

        # Pricing: derive from MSRP
        msrp = float(row["msrp"])
        wholesale = round(msrp * 0.45 + rng_extra.uniform(-0.20, 0.20), 2)
        list_price = round(msrp * 0.85 + rng_extra.uniform(-0.30, 0.30), 2)
        map_price = round(msrp * 0.80 + rng_extra.uniform(-0.20, 0.20), 2)
        out["wholesale_price"] = f"{wholesale:.2f}"
        out["list_price"] = f"{list_price:.2f}"
        out["map_price"] = f"{map_price:.2f}"

        out["shelf_life_days"] = str(rng_extra.choice([180, 270, 365, 365, 365, 540, 730]))

        case_pack = int(row["case_pack_qty"])
        out["inner_pack_count"] = str(max(1, case_pack // rng_extra.choice([2, 3, 4, 6])))

        # Club pack dims: slightly smaller than case dims
        if out["case_length_in"] and out["case_width_in"] and out["case_height_in"]:
            out["club_pack_length_in"] = str(round(float(out["case_length_in"]) * 0.7, 2))
            out["club_pack_width_in"] = str(round(float(out["case_width_in"]) * 0.7, 2))
            out["club_pack_height_in"] = str(round(float(out["case_height_in"]) * 0.7, 2))
        else:
            out["club_pack_length_in"] = ""
            out["club_pack_width_in"] = ""
            out["club_pack_height_in"] = ""

        out["ti"] = str(rng_extra.choice([6, 8, 10, 12]))
        out["hi"] = str(rng_extra.choice([4, 5, 6]))
        out["cases_per_layer"] = out["ti"]
        out["layers_per_pallet"] = out["hi"]

        if out["case_weight_lbs"]:
            case_wt = float(out["case_weight_lbs"])
            ti_val = int(out["ti"])
            hi_val = int(out["hi"])
            out["pallet_weight_lb"] = str(round(case_wt * ti_val * hi_val + 45, 2))
        else:
            out["pallet_weight_lb"] = ""

        # Retailer assignments
        assignments = RETAILER_ASSIGNMENTS.get(product_line, ["DTC"] * 10)
        out["active_retailers"] = assignments[line_idx] if line_idx < len(assignments) else "DTC"

        out["oneworldsync_status"] = rng_extra.choice([
            "Registered - Complete", "Registered - Incomplete",
            "Not Registered", "Not Registered",
        ])
        out["last_updated"] = f"2026-{rng_extra.randint(1,6):02d}-{rng_extra.randint(1,28):02d}"
        out["updated_by"] = rng_extra.choice(["inventory_admin", "production_admin", "ops_lead"])

        output_rows.append(out)

    # Write output
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=output_headers)
        writer.writeheader()
        writer.writerows(output_rows)

    # Print summary
    n_gtin_valid = sum(1 for p in profile.values() if p["gtin14_valid"])
    n_upc_valid = sum(1 for p in profile.values() if p["upc_valid"])
    n_missing_dims = sum(1 for p in profile.values() if p["missing_fields"].get("case_length_in"))
    n_missing_weight = sum(1 for p in profile.values() if p["missing_fields"].get("case_weight_lbs"))
    n_missing_brand = sum(1 for p in profile.values() if p["missing_fields"].get("brand_owner"))
    n_missing_coo = sum(1 for p in profile.values() if p["missing_fields"].get("country_of_origin"))
    n_missing_subcat = sum(1 for p in profile.values() if p["missing_fields"].get("subcategory"))

    print(f"Generated {len(output_rows)} SKUs to {OUTPUT_CSV}")
    print(f"  GTIN-14 valid: {n_gtin_valid}/50 ({n_gtin_valid*2}%)")
    print(f"  UPC-12 valid:  {n_upc_valid}/50 ({n_upc_valid*2}%)")
    print(f"  Missing case dims: {n_missing_dims}/50")
    print(f"  Missing case weight: {n_missing_weight}/50")
    print(f"  Missing brand owner: {n_missing_brand}/50")
    print(f"  Missing country of origin: {n_missing_coo}/50")
    print(f"  Missing subcategory: {n_missing_subcat}/50")


if __name__ == "__main__":
    main()
