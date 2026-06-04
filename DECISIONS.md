# Item Setup Form Pre-flight — Decisions Log

Permanent record of choices that should survive session turnover.
If a decision is reversed, strike it through and add the replacement
below — don't delete.

---

## Format

Each entry:
- **Date** — when decided
- **Decision** — one sentence, imperative voice
- **Why** — the reasoning, including what was tried and rejected
- **Scope** — what this applies to (file, chunk, deliverable, or "global")
- **Do not** — explicit anti-instructions, if any

---

## Architecture & Pipeline

### 2026-06-04 — Use Pyodide in a Web Worker for browser-side validation
- **Why:** Single Python codebase for both CLI and browser. Web Worker keeps UI responsive during Pyodide cold start (~3-5s). Avoids maintaining a separate JS/TS copy of validation rules. Airtight privacy story — product master never leaves browser memory.
- **Scope:** Global — affects all browser-facing validation.
- **Do not:** Run Pyodide on the main thread. Do not create a JS/TS copy of validation logic.

### 2026-06-04 — Use Pydantic v2 for the four-tier validation topology
- **Why:** v2's Rust core is 5-17x faster than v1. Model validators map naturally to the four tiers (presence -> format -> conditional -> GTIN hierarchy). Structured error contract (field/error_type/trigger/rejection_risk) returns as typed dicts, not nested JSON-Schema if/then/else.
- **Scope:** Validation engine.
- **Do not:** Use JSON Schema for conditional validation rules.

### 2026-06-04 — Use Vite + Alpine.js + Tailwind CSS for the frontend
- **Why:** Vite handles Pyodide WASM loading cleanly, gives fast dev server + optimized static builds. Alpine.js provides lightweight reactivity for schema-diff toggling, file-drop, and result display without framework overhead. Tailwind config maps directly to Lailara design tokens.
- **Scope:** All frontend code.
- **Do not:** Use React, Vue, or Svelte — too heavy for a static portfolio piece.

### 2026-06-04 — YAML for the partner schema library
- **Why:** The schema config itself is a portfolio artifact — practitioners should be able to read and extend it. YAML is more readable than JSON for deeply nested conditional specs. Each partner gets its own file.
- **Scope:** Schema library.
- **Do not:** Use JSON Schema for the partner specs. Do not embed specs in Python code.

---

## Data & Schema

### 2026-06-04 — Pin Pyodide 0.29.4 + pydantic==2.10.5 for browser runtime
- **Why:** Official Emscripten wheels exist for pydantic-core at this version. Letting micropip resolve to latest pydantic from PyPI causes version skew with the bundled pydantic-core (pyodide-recipes#162). Fallback if v2 proves problematic: attrs + cattrs (pure Python).
- **Scope:** Browser runtime, Pyodide Web Worker.
- **Do not:** Let micropip install the latest pydantic. Do not assume pydantic-core wheels exist for arbitrary versions.

### 2026-06-04 — CDN loading for Pyodide, not self-hosted
- **Why:** Pyodide payload is ~10MB WASM. CDN (cdn.jsdelivr.net/pyodide/v0.29.4/full/) leverages browser caching for repeat visitors and keeps the build artifact small. Preload links for cold-start optimization.
- **Scope:** Browser runtime.
- **Do not:** Self-host the Pyodide WASM payload.

### 2026-06-04 — Tailwind CSS v4 with @theme directives for Lailara tokens
- **Why:** v4 replaces tailwind.config.js with CSS @theme blocks. All Lailara hex values go in one @theme declaration — single source of truth for design tokens. Prevents token drift (institutional learning from sku-rationalization-framework).
- **Scope:** All CSS.
- **Do not:** Use tailwind.config.js. Do not scatter raw hex values outside @theme.

### 2026-06-04 — Two-round-trip Worker flow for file validation
- **Why:** (1) File + partner → worker returns proposed column mapping → UI confirms. (2) Confirmed mapping → worker validates → results returned. Keeps all logic in Python/Pyodide; UI only handles display and user confirmation.
- **Scope:** Readiness tool browser flow.
- **Do not:** Implement column matching or validation in JavaScript.

### 2026-06-04 — D&W Integrity field names confirmed matching
- **Why:** D&W Integrity project completed building on 2026-06-04. All five physical attribute fields match exactly: case_gross_weight_lb, case_length_in, case_width_in, case_height_in, case_pack_qty. Verified across data gen, dbt staging/marts, TypeScript types, and frontend export. Dependency risk resolved.
- **Scope:** Partner schema library, validation engine (any field referencing physical attributes).
- **Do not:** Invent alternate field names. Consume these exact names from D&W.

---

## Visualization

[Chart conventions, palette decisions, interactivity choices]

---

## Output Formats

[Decisions about deliverable formats, structure, organization]

---

## Writing & Voice

[Voice, style, terminology decisions specific to this project]

---

## Reversed / Superseded

When a decision is overturned:
1. Strike through the original entry above (don't delete)
2. Add a new entry below with the replacement decision
3. Note the link in both directions
