# Item Setup Form Pre-flight — Current Work Plan

The current arc of work. Updated when the arc changes, not every
session. For session-by-session state, see HANDOFF.md.

---

## Goal

Build a client-side readiness tool where a user drops a product master
(Excel or CSV), picks a retailer/distributor, and gets a plain-English
verdict on exactly which fields will bounce and why — powered by codified
partner schemas and a four-tier validation engine, all running in-browser
via Pyodide. All six deliverables (schema library, validation engine,
readiness tool, paired schema-diff view, audit CLI, case study) ship
together, with the readiness tool as the centerpiece.

## Why this arc, why now

The published portfolio proves data analysis and document extraction but
does not yet show the discipline that prevents the most expensive failure
in specialty food: a blown product launch. Item setup is where clean
product data either pays off or fails publicly, in front of the retailer,
on a deadline. Built in parallel with other active projects; no deadline.

## Business question this arc answers

Is this product actually ready to submit to this specific retailer,
and if not, exactly which fields will bounce and why?

## Key constraints (from /clarify — 2026-06-04)

- **UX bar:** Assume the user is an idiot. Fuzzy column matching,
  guided experience, plain-English error messages. Structured error
  contract is internal only.
- **Input formats:** Excel (.xlsx) and CSV — two options, explicitly
  stated in the UI.
- **Analytical integrity:** Four partner schemas codified honestly.
  Whatever pattern emerges is the story. No manufactured narrative.
- **Dependency risk:** Dimension & Weight Integrity fields must be
  checked before consuming physical attributes. Pydantic v2 + Pyodide
  compatibility needs early technical verification.

## Tasks

Work in vertical slices — one section/feature end-to-end before moving
to the next.

- [x] Requirements doc written (docs/brainstorms/2026-06-04-item-setup-preflight-requirements.md)
- [x] Implementation plan written (docs/plans/2026-06-04-001-feat-item-setup-preflight-plan.md)
- [x] Headless doc review — 5 safe_auto fixes applied, 14 actionable findings noted for implementation
- [x] D&W Integrity dependency verified — field names match exactly
- [x] U1: Project foundation — Vite + Tailwind v4 + Alpine.js + Pyodide Worker scaffold
- [x] U2: Validation engine core + Walmart schema
- [x] U3: File input + fuzzy column matching
- [x] U4: Readiness tool UI + Pyodide integration
- [x] U5: Remaining partner schemas — Costco, UNFI, KeHE
- [x] U6: Paired schema-diff view
- [x] U7: Audit CLI
- [x] U8: Case study page + Cinderhaven data + final polish

## Out of scope for this arc

- Becoming a PIM — this is a pre-flight check, not a system of record
- Auto-submitting to retailer portals
- Re-deciding physical field values (Dimension & Weight Integrity owns that)
- General product-data completeness scoring (PDH owns that)
- Parsing each partner's completed proprietary workbook (cell-coordinate
  tar pit; PDF->structured is carried by the remittance parser)

## Definition of done for this arc

- [x] Partner schema library codified in YAML for all four (Walmart, Costco, UNFI, KeHE)
- [x] Four-tier validation engine (presence -> format -> conditional -> GTIN hierarchy) with typed error contract
- [x] Readiness tool runs in-browser via Pyodide — drop Excel/CSV, pick partner, get plain-English verdict
- [x] Fuzzy column matching handles common field name variants
- [x] Paired schema-diff view (retailer vs retailer, distributor vs distributor) with whatever pattern honestly emerges
- [x] Audit CLI parses standardized master export for local pre-flighting
- [x] Case study write-up with Cinderhaven launch scenario
- [x] All visual output follows Lailara design system
- [x] Portfolio-ready — linkable from site, shareable on LinkedIn

---

## Arc history

### 2026-06-04 — Foundation
- Outcome: Project scaffolded, brainstorm brief in place, tech stack decided
- Tag: v0.1-foundation

### 2026-06-04 — Planning complete
- Outcome: Full requirements doc (23 reqs), 8-unit implementation plan, headless doc review with 5 fixes applied, D&W dependency verified
- Tag: v0.2-planning

### 2026-06-05 — Arc complete
- Outcome: All 8 units built, reviewed, QA'd, deployed. Live at preflight.lailarallc.com. CI/CD on push to main. Every definition-of-done item checked.
- Tag: (pending user confirmation)

---

## Improvement history

<!-- Entries are added by /improve — don't delete this section -->
