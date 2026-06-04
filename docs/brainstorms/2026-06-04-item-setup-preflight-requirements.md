---
date: 2026-06-04
topic: item-setup-preflight
---

# Item Setup Form Pre-flight

## Summary

A client-side readiness tool that validates product master data against codified retailer/distributor schemas, surfaces rejection risks in plain English, and frames the analytical finding through paired channel-type comparisons. Six deliverables ship as a unit — YAML schema library, Pydantic validation engine, browser-based readiness tool (Pyodide), paired schema-diff view, audit CLI, and Cinderhaven case study — with the readiness tool as the centerpiece.

---

## Problem Frame

To get a new product onto a retailer's shelf, a specialty food brand fills out that retailer's item setup form — Walmart's Item 360, Costco's item setup workbook, UNFI's and KeHE's new item forms. Each demands dozens to hundreds of attributes per SKU in different formats, different required-field sets, and different GTIN hierarchy expectations.

The data to fill them is scattered across the ERP, nutritional spreadsheets, artwork files, and tribal knowledge. The form gets filled by hand, submitted, and bounces: a missing field, a GTIN at the wrong hierarchy level, dimensions in the wrong format. The item doesn't go live. The launch slips.

The cost isn't delay — it's forfeit. Retailers set items during category-review windows. Miss the window because the form bounced and you wait 6-12 months for the next reset. The slot may go to a competitor. Slotting fees paid for shelf space the item isn't generating revenue on. At $25M heading toward $50M, the growth plan depends on new retailer wins and new item launches. Form friction throttles exactly the thing the brand is betting on.

---

## Actors

- A1. **Portfolio visitor (prospect):** A CEO, COO, broker, or ops person exploring the Lailara portfolio. Drops their product master into the readiness tool or browses the schema-diff view. May have no technical background.
- A2. **Ops/data person:** The person who actually fills retailer forms. Uses the readiness tool or audit CLI to check their master before submitting. Understands the fields but not the cross-retailer differences.
- A3. **CEO/founder:** Sees the case study and readiness verdict as a growth-plan story. Forwards to ops with "we cannot miss the next reset."

---

## Key Flows

- F1. **Readiness check (browser)**
  - **Trigger:** Visitor drops an Excel or CSV product master file into the readiness tool
  - **Actors:** A1, A2
  - **Steps:**
    1. Tool accepts the file (Excel or CSV) and parses column headers
    2. Fuzzy column matcher auto-maps known aliases; surfaces unmatched columns for manual correction
    3. User picks a target partner (Walmart, Costco, UNFI, or KeHE)
    4. Tool explains both output views (per-SKU verdicts vs aggregate summary) and why each is useful
    5. Validation engine runs four-tier checks in browser via Pyodide Web Worker
    6. Results display in chosen view with plain-English error messages, severity levels, and actionable fix guidance
  - **Outcome:** User sees exactly which fields will bounce for the chosen partner and what to fix
  - **Covered by:** R1, R2, R3, R4, R5, R6, R7, R8

- F2. **Schema comparison (browser)**
  - **Trigger:** Visitor navigates to the schema-diff view
  - **Actors:** A1, A2
  - **Steps:**
    1. Paired comparisons load: retailer-vs-retailer (Walmart vs Costco) and distributor-vs-distributor (UNFI vs KeHE)
    2. Differences highlighted: required fields, format expectations, GTIN hierarchy rules, conditional triggers
    3. Whatever channel-type pattern honestly emerges is called out
  - **Outcome:** Visitor understands the structural differences between partners and why the same product can be "ready" for one and "not ready" for another
  - **Covered by:** R9, R10, R11

- F3. **Local audit (CLI)**
  - **Trigger:** User runs the audit CLI against a master export file
  - **Actors:** A2
  - **Steps:**
    1. CLI accepts a standardized master export or generic draft sheet (Excel or CSV)
    2. Same validation engine runs locally (no browser, no Pyodide)
    3. Results print to terminal as a structured report
  - **Outcome:** Per-partner readiness verdict from the command line
  - **Covered by:** R12, R13

---

## Requirements

**File input and column matching**

- R1. Accept Excel (.xlsx) and CSV file uploads via browser drag-and-drop or file picker. No other formats.
- R2. Auto-match uploaded column headers to expected schema fields using a fuzzy alias map (e.g., "Item Width", "width_inches", "W (in)" all resolve to the width field).
- R3. When columns cannot be auto-matched, surface them in a mapping confirmation step where the user can manually assign or skip them. Never silently ignore unmatched columns.

**Validation engine**

- R4. Run validation in a fixed four-tier order: (1) presence — mandatory fields for the category; (2) format — regex/mask checks; (3) conditional — cross-field logic (e.g., storage_type == "Refrigerated" triggers temperature-zone fields); (4) GTIN hierarchy — identifier resolves to the correct unit class per partner.
- R5. Each validation failure returns a structured record with field, error type, trigger condition, and severity level (CRITICAL — form bounces; WARNING — may cause issues; INFO — suggestion).
- R6. GTIN hierarchy validation explicitly checks that the identifier resolves to the right unit class per partner (Costco expects case/pallet GTIN-14, Walmart expects consumer-unit UPC-12). A wrong-level GTIN that "fills the field" still fails.
- R7. Reuse GTIN Validator core logic (vendored from the published portfolio project) for check-digit and format validation.

**Readiness tool UX**

- R8. Display results in two switchable views: per-SKU verdicts (each SKU gets pass/fail with typed gaps) and aggregate summary (batch totals with drill-down). Explain to the user why they might want each view before they choose.
- R9. All user-facing error messages are plain English. The structured error contract (field/error_type/trigger/rejection_risk) is internal only — never shown raw in the UI.
- R10. Product master data is validated entirely in browser memory via Pyodide running in a Web Worker. No data is uploaded to any server.

**Schema-diff view**

- R11. Display paired comparisons: retailer-vs-retailer (Walmart vs Costco) and distributor-vs-distributor (UNFI vs KeHE). Not a flat four-way comparison.
- R12. Highlight differences in required fields, format expectations, GTIN hierarchy rules, and conditional triggers across each pair.
- R13. Surface whatever channel-type pattern honestly emerges from the codified schemas. Do not manufacture or force a specific finding.

**Partner schema library**

- R14. Codify each partner's item-setup spec as structured YAML config: required fields, formats, GTIN-hierarchy rules, allowed values, and conditional triggers.
- R15. Schemas must be directionally faithful to the real shape of each partner's form — the known gotchas (GTIN hierarchy differences, conditional requirements) must ring true to someone who has filled these forms.
- R16. The YAML config itself is a portfolio artifact — readable by a practitioner, not just machine-parseable.

**Audit CLI**

- R17. CLI accepts a standardized master export or generic draft sheet (Excel or CSV) and runs the same validation engine used by the browser tool.
- R18. CLI is a repo-only utility (not hosted). Uses click for the interface and openpyxl for Excel parsing.

**Case study**

- R19. Standalone narrative page using Cinderhaven data: a new-product launch scenario run through the pre-flight against all four partners.
- R20. Quantify the cost of submitting errors uncaught (lost launch velocity, missed category-review windows, slotting paid for empty shelf, rework labor).
- R21. Show before/after: scattered-source manual process vs clean per-partner readiness verdict.

**Visual design**

- R22. All visual output follows the Lailara design system (Playfair Display + Source Sans 3 typography, Economist-style charts, city-named color palette, Canvas background).
- R23. Self-hosted woff2 fonts. No Google Fonts CDN.

---

## Acceptance Examples

- AE1. **Covers R2, R3.** Given an Excel file with columns "Item Width (in)", "Gross Wt", and "UPC Number", when the file is dropped into the readiness tool, "Item Width (in)" and "UPC Number" auto-match to width and GTIN fields, "Gross Wt" auto-matches to weight, and any truly unrecognizable columns appear in the mapping step for manual assignment.

- AE2. **Covers R4, R6.** Given a Cinderhaven SKU with a valid UPC-12 in the GTIN field, when validated against Costco's schema (which expects a case/pallet GTIN-14), the tool returns a CRITICAL failure on GTIN hierarchy even though the GTIN itself is format-valid and the field is not empty.

- AE3. **Covers R4, R5.** Given a product with storage_type "Refrigerated" but no temperature-zone fields filled, when validated against any partner schema requiring conditional temperature fields, the tool returns a structured error with error_type "CONDITIONAL_REQUIREMENT_MISSING", the trigger condition, and severity CRITICAL.

- AE4. **Covers R8.** Given a master with 20 SKUs validated against Walmart, when the user switches to aggregate view, they see "14 of 20 SKUs ready for Walmart" with a summary of the most common failure types and a drill-down to individual SKU issues.

- AE5. **Covers R10.** Given a user on a slow network, when they drop a file into the readiness tool, validation completes even if the network connection is lost — all processing happens in browser memory via the Pyodide Web Worker.

---

## Success Criteria

- A portfolio visitor with no data background can drop a file, pick a partner, and understand the readiness verdict without help
- The GTIN hierarchy check catches the Walmart-vs-Costco unit-level mismatch — the single most credible detail in the piece
- A broker or ops person reading the schema-diff view recognizes the partner requirements as directionally real
- The case study quantifies the cost of a bounced setup form in terms a CEO cares about (missed resets, lost velocity, wasted slotting)
- Planning (ce-plan) can execute from this doc without inventing product behavior, UX flow, or scope boundaries

---

## Scope Boundaries

- Not a PIM — this is a pre-flight check, not a system of record or syndication platform
- No auto-submission to retailer portals — produces submission-ready output and a readiness verdict only
- No re-deciding physical field values — weight/cube/dims SSOT belongs to Dimension & Weight Integrity; this validates presence and format only
- No general product-data completeness scoring — that's PDH; this is retailer-specific submission readiness
- No parsing of each partner's completed proprietary workbook — cell-coordinate tar pit, and PDF-to-structured is carried by the remittance parser
- No real-time portal integration or API connections
- No user accounts, saved sessions, or persistence between visits

---

## Key Decisions

- **Pyodide in Web Worker for browser runtime:** Single Python codebase for CLI and browser. Web Worker keeps UI responsive during cold start. Airtight privacy story. Accepted cost: multi-MB payload, few seconds cold start.
- **Both output views with user guidance:** Per-SKU verdicts and aggregate summary both available, with the tool explaining when each is useful. User picks; both are always accessible.
- **Fuzzy column matching with confirmation step:** Auto-match common aliases, surface unmatched columns for manual correction. Never silently ignore. Treats the user as a non-technical visitor.
- **Honest analytical finding:** Whatever pattern emerges from the four honestly-codified schemas becomes the story. The paired comparison structure (retailer-vs-retailer, distributor-vs-distributor) is the analytical frame, but the specific finding is not predetermined.
- **GTIN Validator vendored:** Core logic copied from the published project since it's not on PyPI. Visible portfolio reuse.
- **Severity tiers in error contract:** CRITICAL (form bounces), WARNING (may cause issues), INFO (suggestion). UI shows critical items first and most prominent.
- **Schema-diff and readiness tool are separate pages:** The diff is the forward-worthy shareability artifact; the readiness tool is the lead-gen utility. Same site, different entry points.

---

## Dependencies / Assumptions

- **Dimension & Weight Integrity physical fields:** Schema-stable (types and contracts locked in dbt/TypeScript) but implementation not complete. Field names: `case_gross_weight_lb`, `case_length_in`, `case_width_in`, `case_height_in`, `case_pack_qty`. Safe to consume type definitions now; reconcile data once D&W implementation completes.
- **GTIN Validator core logic:** Available in `gtin_core.py` with `validate_single_gtin()`, `validate_batch()`, `check_digit_calculation()`. Supports GTIN-8/12/13/14.
- **Cinderhaven product master:** 90 SKUs, 26 columns, CSV/Excel/SQLite. Has gtin14, upc, dimensions, weights, case_pack_qty, nutritional data. ~30% incomplete dimensions, no allergen column — realistic gaps the pre-flight should catch.
- **Pydantic v2 + Pyodide compatibility:** Pydantic v2 uses a Rust core (pydantic-core). Must verify it compiles for Emscripten/WASM before committing to the browser architecture. Fallback: Pydantic v1 (pure Python, works in Pyodide) or a pure-Python validator for the browser side.

---

## Outstanding Questions

### Deferred to Planning

- [Affects R14][Needs research] Verify Pydantic v2 runs in Pyodide. If pydantic-core doesn't compile for WASM, determine the best fallback (Pydantic v1, pure-Python validators, or a shim).
- [Affects R2][Technical] Define the full fuzzy alias map for column matching — which common aliases map to which schema fields across all four partners.
- [Affects R14][Needs research] Codify the four partner schemas from real-world form shapes. Determine what level of fidelity is achievable and where to draw the "directionally real" line.
- [Affects R13][Technical] Whether the channel-pattern finding (distributors more alike than retailers) is strong enough to headline the piece or sits as a mid-piece reveal — decide during build once schemas are codified.
