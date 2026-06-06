# Item Setup Form Pre-flight

Codified retailer and distributor item-setup schemas plus a typed validation engine that flags new-item form rejection risks before submission. Runs client-side in the browser via Pyodide — the product master never leaves browser memory.

**Live:** https://preflight.lailarallc.com

## Status

Under development.

## Stack

- Python 3.12+ / Pydantic v2 (validation engine)
- YAML (partner schema library)
- Pyodide/WASM (browser runtime)
- Vite / Alpine.js / Tailwind CSS (frontend)
- click / openpyxl (audit CLI)
- SQLite (case-study data)
- pytest / Ruff (testing / linting)

---

Built by [Lailara LLC](https://lailarallc.com) — data hygiene and analytics consulting for specialty food brands scaling into national retail.
