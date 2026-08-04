# INPUT-SPEC — item-setup-form-preflight (client mode)

What to hand the pre-flight engine in a client engagement. Written so a client's IT
person can produce the file without a call. The tool checks a product master against
one retailer/distributor item-setup schema (Walmart, Costco, UNFI, or KeHE) and reports
which SKUs would bounce and why.

## The file

- **CSV or XLSX.** Read via `lailara_engagement`'s tolerant reader: UTF-8 / UTF-8-BOM /
  latin-1; comma / semicolon / tab; leading blank rows and trailing junk dropped; header
  whitespace trimmed; Excel dates rendered as ISO text; Excel float-widened numbers
  recovered as integer text. Nothing is silently coerced — any assumption is disclosed.
- One row per SKU (product/pack). Extra columns are ignored.

## §1 One partner per run

Pick the target partner: `walmart`, `costco`, `unfi`, or `kehe` — on the CLI (`--partner`)
or as `partner:` in `engagement.yml`. Each partner has its own required-field set and GTIN
expectation (below). Run the tool once per partner you are submitting to.

## §2 Required identifier column

| Canonical | Type | Required | Used for |
|---|---|---|---|
| `upc` | identifier (text) | yes | The barcode the engine keys each SKU on and runs GTIN-hierarchy checks against. |

- **Read as text.** Leading zeros survive; `0614141000012` is never parsed to a number.
- **What `upc` points at depends on the partner's GTIN level:**
  - Walmart — the **consumer unit** UPC-A / GTIN-12 (12 digits). Map `upc: "<your UPC column>"`.
  - Costco / UNFI / KeHE — the **case** GTIN-14 / ITF-14 (14 digits). Map `upc: "<your GTIN-14 column>"`.
- If no column resolves to `upc`, the run produces a **Data Readiness Report** naming the
  missing column instead of results.

## §3 Partner-required fields

The engine validates presence, then format, then conditional requirements, then the GTIN.
Fields below are **required** for that partner; a missing or empty one bounces the SKU
(CRITICAL). A present-but-malformed value bounces on format (WARNING). Fields your file
does not carry are reported per-SKU as missing — that is the deliverable, not an error.

**All partners require:** `product_name`, `brand`, `upc`, `case_gross_weight_lb`,
`case_length_in`, `case_width_in`, `case_height_in`, `case_pack_qty`, `country_of_origin`,
`category`, `product_description`.

**Additionally by partner:**

| Partner | Extra required fields | GTIN expected |
|---|---|---|
| Walmart | `serving_size`, `calories`, `total_fat_g`, `sodium_mg` | GTIN-12 / UPC-A (consumer unit) |
| Costco | `inner_pack_count`, `club_pack_length_in`, `club_pack_width_in`, `club_pack_height_in`, `shelf_life_days` | GTIN-14 / ITF-14 (case) |
| UNFI | `wholesale_price`, `list_price`, `map_price`, `ti`, `hi`, `pallet_weight_lb`, `shelf_life_days` | GTIN-14 / ITF-14 (case) |
| KeHE | `wholesale_price`, `list_price`, `cases_per_layer`, `layers_per_pallet`, `pallet_weight_lb`, `shelf_life_days` | GTIN-14 / ITF-14 (case) |

**Formats.** Weights and dimensions are numeric (`^\d+\.?\d*$`); `case_pack_qty` is a whole
number; `upc` must be a valid GTIN of the expected length with a correct check digit. A
12-digit UPC-A also raises an INFO advisory (`UPC_NOT_GTIN13`) — informational only, it
never bounces a SKU.

**Conditional rules** (Tier 3) fire only when a trigger field is present, e.g. Walmart
requires `temp_min`/`temp_max` when `storage_type` is `Refrigerated` or `Frozen`, and
`hazmat_class`/`un_number` when `is_hazmat` is `true`.

## Column mapping (engagement.yml)

Map each client header that differs from the canonical field name; identity matches
(header already equal to the canonical name) are implicit.

```yaml
client:
  name: "Meridian Farms"
engagement:
  id: "MER-2026-08"
as_of_date: "2026-07-31"
partner: "walmart"
columns:
  upc: "UPC / Barcode"           # client header -> canonical
  brand: "Brand Owner"
  case_gross_weight_lb: "Case Wt (lb)"
  calories: "Calories per serving"
```

Mapping is confirmed via config, never fuzzy-guessed silently. A case/whitespace-
insensitive exact match on a canonical name is auto-applied and disclosed.

## Run

```bash
# with lailara_engagement installed: pip install -e ../engagement-template/lib
python client_mode.py --config engagement.yml --partner walmart \
    --input client-data/master.csv --out client-output [--final]
```

Outputs to `client-output/` (gitignored):
- `item-setup-readiness-summary.html` — branded, provenance-footed (input SHA-256, row
  counts, `as_of_date`, config hash), DRAFT-watermarked until `--final`.
- `item-setup-preflight.csv` — the full per-SKU report (row, sku, verdict, field, severity,
  error type, message).
- or `data-readiness-report.html` if the `upc` identifier column is missing.
