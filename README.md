# Item Setup Form Pre-flight

Catch retailer item-setup rejections before you submit — a typed validation engine plus codified partner schemas, running entirely in the browser so your product master never leaves your machine.

**Live:** https://preflight.lailarallc.com

## What it does

- **Codifies retailer and distributor item-setup requirements** as a YAML schema library — the field-level rules each partner enforces on new-item forms
- **Validates your product data against those schemas** with a typed Pydantic v2 engine, flagging the errors that would cause a rejection: missing required fields, malformed identifiers, out-of-range values, format mismatches
- **Runs client-side via Pyodide (Python compiled to WebAssembly)** — you paste or upload product data in the browser and validation happens in browser memory; nothing is transmitted to a server
- **Ships an audit CLI** (click + openpyxl) for running the same checks against spreadsheets from the command line

## Why it matters

A rejected new-item form doesn't just bounce back — it resets the setup queue. For a specialty food brand, that can mean weeks of delay on a retail launch, a missed reset window, and burned goodwill with the buyer who championed the product. Most rejections trace to predictable, checkable data problems.

Pre-flighting the form converts a slow, opaque rejection loop into an immediate, itemized fix list — before the retailer ever sees the submission. Because validation is client-side, brands can check sensitive product and cost data without a vendor data-processing agreement.

## Quick start

```bash
npm install                   # frontend deps
pip install -e ".[dev,cli]"   # validation engine + CLI + dev tools
npm run dev                   # Vite dev server
```

Run the test suite:

```bash
pytest
```

Build for production:

```bash
npm run build
```

## Tech stack

- Python 3.12+ / Pydantic v2 (validation engine)
- YAML (partner schema library)
- Pyodide/WASM (browser runtime)
- Vite / Alpine.js / Tailwind CSS (frontend)
- click / openpyxl (audit CLI)
- SQLite (case-study data)
- pytest / Ruff (testing / linting)

## Project structure

- `src/` — Python validation engine and partner schemas
- `schema-diff/` — schema comparison tooling
- `case-study/` — worked case-study data
- `tests/` — pytest suite
- `index.html`, `vite.config.js`, `public/` — browser frontend

## License

MIT — see [LICENSE](LICENSE).

---

Built by [Lailara LLC](https://lailarallc.com) — data hygiene and analytics consulting for specialty food brands scaling into national retail.
