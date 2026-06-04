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

[Decisions about data sources, schemas, transformations]

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
