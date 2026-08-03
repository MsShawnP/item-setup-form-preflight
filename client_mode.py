"""Client-mode CLI for the item-setup form pre-flight engine.

Wraps the existing four-tier validation engine (``src.engine``) with the shared
``lailara_engagement`` scaffold so a client's product master can be checked
locally against a retailer/distributor item-setup schema: tolerant CSV/XLSX
intake (UPC/GTIN read as text), a preflight that names the identifier column via
``engagement.yml`` (Data Readiness Report if it is missing), the engine run per
SKU, and a branded, provenance-footed, draft-watermarked readiness summary plus
a per-SKU CSV — all written to ``client-output/`` only.

Column mapping is driven entirely by ``engagement.yml`` (canonical field ->
client header); nothing is fuzzy-guessed. A client header that already equals a
canonical field name maps to itself. Any schema field with no column is reported
by the engine as a missing field on each SKU — that is the deliverable, not a
crash.

Usage:
    python client_mode.py --config engagement.yml --partner walmart \\
        --input client-data/master.csv --out client-output [--final]
"""

from __future__ import annotations

import argparse
import csv
import html
import io
from collections import Counter
from pathlib import Path

from lailara_engagement import (
    ColumnSpec,
    PreflightSpec,
    build_provenance,
    load_config,
    read_table,
    run_preflight,
    validation_status_label,
    write_report,
)
from lailara_engagement import palette as P
from lailara_engagement.provenance import Provenance

from src.engine.schema_loader import load_schema
from src.engine.validators import validate_product

TOOL = "item-setup-form-preflight"
TOOL_VERSION = "1.0"
PARTNERS = ("walmart", "costco", "unfi", "kehe")


def _schema_path(partner: str) -> Path:
    return Path(__file__).parent / "src" / "schemas" / f"{partner}.yaml"


def _preflight_spec() -> PreflightSpec:
    # Intake gate: require the identifier the engine keys each SKU on. Everything
    # else the schema validates is reported per-SKU by the engine, not gated here
    # (a raw client file missing dimensions must still produce a report, not a
    # block). The identifier is read as text so leading zeros survive.
    return PreflightSpec(
        tool=TOOL,
        version=TOOL_VERSION,
        columns=[
            ColumnSpec(
                name="upc",
                dtype="identifier",
                required=True,
                description="the product UPC/GTIN identifier each SKU is keyed on",
                spec_ref="INPUT-SPEC §2",
            )
        ],
    )


def _header_to_canonical(config, upc_col: str | None) -> dict[str, str]:
    """Client header -> canonical field, from engagement.yml columns.

    Identity (header already equals a canonical name) is handled at remap time as
    a fallback, so only explicit renames need to appear in the config.
    """
    mapping: dict[str, str] = {}
    for canon, client in (config.columns or {}).items():
        if isinstance(client, str):
            mapping[client] = canon
        elif isinstance(client, (list, tuple)):
            for c in client:
                mapping[str(c)] = canon
    if upc_col:
        mapping[upc_col] = "upc"
    return mapping


def _remap_rows(read, header_to_canon: dict[str, str]) -> list[dict]:
    frame = read.frame
    cols = list(frame.columns)
    remapped: list[dict] = []
    for _, row in frame.iterrows():
        d: dict[str, str] = {}
        for header in cols:
            canon = header_to_canon.get(header, header)  # identity fallback
            d[canon] = row[header]
        remapped.append(d)
    return remapped


def _sku_label(row: dict, idx: int) -> str:
    for candidate in ("product_name", "product_description", "upc", "brand"):
        val = row.get(candidate)
        if val is not None and str(val).strip():
            label = str(val).strip()
            return label if len(label) <= 60 else label[:57] + "..."
    return f"Row {idx + 1}"


def _run_engine(rows: list[dict], schema) -> dict:
    """Run the four-tier engine per SKU and aggregate.

    INFO advisories are surfaced per-SKU but never counted in the aggregate and
    never flip the verdict (the 07-31 clean-renders-clean rule).
    """
    per_row = []
    for idx, row in enumerate(rows):
        result = validate_product(row, schema)
        per_row.append({
            "label": _sku_label(row, idx),
            "verdict": result.verdict,
            "errors": [
                {"field": e.field, "error_type": e.error_type.value,
                 "severity": e.severity.value, "message": e.message}
                for e in result.errors
            ],
        })

    total = len(per_row)
    passing = sum(1 for r in per_row if r["verdict"] == "PASS")

    error_type_counts: Counter = Counter()
    field_counts: Counter = Counter()
    for r in per_row:
        for e in r["errors"]:
            if e["severity"] == "INFO":
                continue
            error_type_counts[e["error_type"]] += 1
            field_counts[e["field"]] += 1

    return {
        "per_row": per_row,
        "total": total,
        "passing": passing,
        "failing": total - passing,
        "error_type_counts": error_type_counts,
        "top_failing_fields": field_counts.most_common(10),
    }


def _csv_report(batch: dict, partner: str) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["row", "sku", "verdict", "field", "severity", "error_type", "message"])
    for i, r in enumerate(batch["per_row"], start=1):
        if not r["errors"]:
            w.writerow([i, r["label"], r["verdict"], "", "", "", "ready to submit"])
            continue
        for e in r["errors"]:
            w.writerow([i, r["label"], r["verdict"], e["field"],
                        e["severity"], e["error_type"], e["message"]])
    return buf.getvalue()


def _summary_html(config, partner: str, schema, batch: dict, report,
                  provenance: Provenance, *, draft: bool) -> str:
    esc = html.escape
    draft_class = " ll-draft" if draft else ""
    all_clean = batch["failing"] == 0

    fill = P.LL_HK_SURFACE if all_clean else P.LL_SG_SURFACE
    text = P.LL_HK_DARK if all_clean else P.LL_SG_DARK
    banner_msg = (
        f"All {batch['total']} SKUs are submission-ready for {esc(schema.display_name)}."
        if all_clean else
        f"{batch['failing']} of {batch['total']} SKUs would bounce at "
        f"{esc(schema.display_name)} item setup."
    )

    type_rows = "".join(
        f"<tr><td class=mono>{esc(code)}</td><td class=num>{n}</td></tr>"
        for code, n in batch["error_type_counts"].most_common(10)
    ) or "<tr><td colspan=2>No blocking issues.</td></tr>"

    field_rows = "".join(
        f"<tr><td class=mono>{esc(field)}</td><td class=num>{n}</td></tr>"
        for field, n in batch["top_failing_fields"]
    ) or "<tr><td colspan=2>No failing fields.</td></tr>"

    # Intake notes: preflight warnings/disclosures (blanks, coercions disclosed).
    intake_items = [f.message for f in report.findings if f.severity != "info"]
    intake_items += list(report.disclosures)
    intake_html = ""
    if intake_items:
        lis = "".join(f"<li>{esc(x)}</li>" for x in intake_items)
        intake_html = (
            '<section class=ll-section><h2 class=ll-h2>Intake notes</h2>'
            f'<ul class=ll-limitations>{lis}</ul></section>'
        )

    gtin = schema.gtin_hierarchy
    basis = (f"{esc(gtin.expected_level)} — {esc(', '.join(gtin.expected_formats))}")

    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width, initial-scale=1">
<title>Item-Setup Readiness — {esc(config.client_name)}</title>
<style>{_css(draft)}</style></head>
<body class="{draft_class.strip()}"><main class=ll-page>
<header class=ll-header>
  <div class=ll-eyebrow>Lailara LLC · Item-Setup Pre-flight</div>
  <h1 class=ll-title>Item-Setup Readiness Summary</h1>
  <div class=ll-client>
    <div><span class=ll-k>Client</span> {esc(config.client_name)}</div>
    <div><span class=ll-k>Engagement</span> {esc(config.engagement_id)}</div>
    <div><span class=ll-k>Partner</span> {esc(schema.display_name)}</div>
    <div><span class=ll-k>As of</span> {esc(config.as_of_date.isoformat())}</div>
    <div><span class=ll-k>Prepared by</span> {esc(config.prepared_by)}</div>
  </div>
</header>
<section class=ll-banner style="background:{fill};color:{text}">
  <div class=ll-score>{batch['passing']}/{batch['total']} SKUs ready</div>
  <div>{banner_msg}</div>
</section>
<section class=ll-section>
  <h2 class=ll-h2>Batch summary</h2>
  <table class=ll-table>
    <tr><td>Total SKUs</td><td class=num>{batch['total']:,}</td></tr>
    <tr><td>Submission-ready</td><td class=num>{batch['passing']:,}</td></tr>
    <tr><td>Would bounce</td><td class=num>{batch['failing']:,}</td></tr>
    <tr><td>GTIN basis</td><td>{basis}</td></tr>
  </table>
</section>
<section class=ll-section>
  <h2 class=ll-h2>Bounce reasons by type</h2>
  <table class=ll-table><thead><tr><th>Error type</th><th>Count</th></tr></thead>
  <tbody>{type_rows}</tbody></table>
</section>
<section class=ll-section>
  <h2 class=ll-h2>Top failing fields</h2>
  <table class=ll-table><thead><tr><th>Field</th><th>SKUs</th></tr></thead>
  <tbody>{field_rows}</tbody></table>
</section>
{intake_html}
{provenance.to_html()}
</main></body></html>"""


def _css(draft: bool) -> str:
    draft_css = (
        ".ll-draft::before{content:'DRAFT';position:fixed;top:50%;left:50%;"
        "transform:translate(-50%,-50%) rotate(-32deg);font-family:var(--s);"
        "font-size:22vw;font-weight:700;color:rgba(204,16,10,.06);z-index:0;"
        "pointer-events:none;white-space:nowrap}" if draft else ""
    )
    return f"""
:root{{--s:{P.LL_SERIF};--f:{P.LL_SANS}}}
*{{box-sizing:border-box}}
body{{margin:0;background:{P.LL_CANVAS};color:{P.LL_TEXT};font-family:var(--f);line-height:1.6}}
.ll-page{{position:relative;z-index:1;max-width:{P.LL_MAX_WIDTH};margin:0 auto;padding:48px 24px}}
.ll-header{{border-bottom:1px solid {P.LL_GRIDLINE};padding-bottom:24px;margin-bottom:24px}}
.ll-eyebrow{{font-size:12px;letter-spacing:.04em;text-transform:uppercase;color:{P.LL_RED};font-weight:600}}
.ll-title{{font-family:var(--s);font-weight:700;color:{P.LL_INK};font-size:34px;margin:8px 0 16px}}
.ll-client{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px 24px;font-size:14px}}
.ll-k{{display:block;color:{P.LL_TEXT_SEC};font-size:11px;text-transform:uppercase;letter-spacing:.04em}}
.ll-banner{{border-radius:2px;padding:16px 20px;margin-bottom:32px}}
.ll-score{{font-family:var(--s);font-weight:700;font-size:22px}}
.ll-h2{{font-family:var(--s);font-weight:700;color:{P.LL_INK};font-size:22px;margin:0 0 12px;padding-bottom:6px;border-bottom:1px solid {P.LL_GRIDLINE}}}
.ll-table{{width:100%;border-collapse:collapse;font-size:14px}}
.ll-table th{{text-align:left;background:{P.LL_CHICAGO};color:#fff;padding:8px 12px}}
.ll-table td{{padding:8px 12px;border-bottom:1px solid {P.LL_GRIDLINE}}}
.ll-section{{margin:0 0 32px}}
.ll-limitations{{margin:0;padding-left:20px}}
.ll-limitations li{{margin-bottom:6px}}
.mono{{font-family:ui-monospace,Consolas,monospace;font-size:12px}}
.num{{text-align:right;font-variant-numeric:tabular-nums}}
.ll-provenance{{margin-top:40px;background:{P.LL_CARD_BG};color:{P.LL_CARD_TEXT};padding:20px 24px;border-radius:2px;font-size:13px}}
.ll-prov-title{{font-family:var(--s);font-weight:700;font-size:16px;margin-bottom:8px}}
.ll-provenance div{{margin-bottom:4px;color:{P.LL_CARD_SUBTITLE}}}
.ll-provenance strong{{color:{P.LL_CARD_TEXT}}}
.ll-prov-inputs{{width:100%;border-collapse:collapse;margin-top:8px}}
.ll-prov-inputs th{{text-align:left;border-bottom:1px solid rgba(255,255,255,.12);padding:4px 8px;color:{P.LL_CARD_MUTED}}}
.ll-prov-inputs td{{padding:4px 8px;border-bottom:1px solid rgba(255,255,255,.08);color:{P.LL_CARD_SUBTITLE}}}
.ll-prov-brand{{margin-top:12px;font-family:var(--s);color:{P.LL_CARD_MUTED}}}
{draft_css}
@media print{{body{{background:#fff}}}}
"""


def _resolve_partner(config, partner_arg: str | None) -> str:
    partner = (partner_arg or config.raw.get("partner") or "").strip().lower()
    if partner not in PARTNERS:
        raise SystemExit(
            f"--partner is required and must be one of {', '.join(PARTNERS)} "
            f"(got {partner!r}; set it on the CLI or as `partner:` in the config)"
        )
    return partner


def run(config_path: str, input_path: str, out_dir: str, *,
        partner: str | None = None, final: bool = False) -> dict:
    config = load_config(config_path)
    partner = _resolve_partner(config, partner)
    read = read_table(input_path)
    spec = _preflight_spec()
    report = run_preflight(read, spec, config)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    provenance = build_provenance(
        tool=TOOL, tool_version=TOOL_VERSION, inputs=[read], config=config,
        validation_status=validation_status_label(report.status, report.n_warnings),
    )

    # Preflight gate: no identifier column -> Data Readiness Report, no results.
    if not report.passed:
        paths = write_report(report, config, str(out), provenance=provenance,
                             draft=not final, basename="data-readiness-report",
                             title="Item-Setup Data Readiness Report")
        return {"status": "blocked", "readiness_report": paths["html"],
                "report": paths["html"]}

    schema = load_schema(str(_schema_path(partner)))
    upc_col = report.column_mapping.get("upc")
    rows = _remap_rows(read, _header_to_canonical(config, upc_col))
    batch = _run_engine(rows, schema)

    csv_path = out / "item-setup-preflight.csv"
    csv_path.write_text(_csv_report(batch, partner), encoding="utf-8")

    summary_path = out / "item-setup-readiness-summary.html"
    summary_path.write_text(
        _summary_html(config, partner, schema, batch, report, provenance,
                      draft=not final),
        encoding="utf-8",
    )

    return {
        "status": "ok",
        "partner": partner,
        "passing": batch["passing"],
        "failing": batch["failing"],
        "total": batch["total"],
        "csv": str(csv_path),
        "report": str(summary_path),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="item-setup client mode",
        description="Pre-flight a client product master against a partner schema.")
    ap.add_argument("--config", required=True)
    ap.add_argument("--partner", choices=PARTNERS)
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", default="client-output")
    ap.add_argument("--final", action="store_true")
    args = ap.parse_args(argv)
    result = run(args.config, args.input, args.out, partner=args.partner,
                 final=args.final)
    if result["status"] == "blocked":
        print(f"BLOCKED — data not ready. See {result['readiness_report']}")
        return 3
    print(f"{result['partner']}: {result['passing']}/{result['total']} SKUs ready, "
          f"{result['failing']} would bounce")
    print(f"report -> {result['report']}\ncsv    -> {result['csv']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
