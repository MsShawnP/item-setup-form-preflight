---
title: "Pyodide Web Worker Architecture: Running Python Validation Client-Side in a Vite Project"
date: 2026-06-05
category: architecture-patterns
module: item-setup-form-preflight
problem_type: architecture_pattern
component: tooling
severity: medium
applies_when:
  - "Running a Python validation or analysis engine client-side in the browser via Pyodide WASM"
  - "Sharing a single Python codebase between a CLI tool and a browser runtime"
  - "Privacy-sensitive data processing where files must never leave the browser"
  - "Building a Vite project that bundles Python source as strings for a Web Worker"
tags:
  - pyodide
  - web-worker
  - vite
  - wasm
  - pydantic-v2
  - client-side-validation
  - import-rewriting
  - security
---

# Pyodide Web Worker Architecture: Running Python Validation Client-Side in a Vite Project

## Context

Lailara LLC needed a retailer item-setup validation tool that runs entirely in the browser. The product master contains confidential pricing, dimensions, and GTIN data that cannot leave the client's machine. The validation logic is substantial: Pydantic v2 models, YAML-driven retailer schemas (Walmart Item 360, Costco, UNFI, KeHE), four-tier validation (presence, format, conditional rules, GTIN hierarchy), and Excel parsing via openpyxl. Rewriting this in JavaScript would have meant maintaining two implementations and abandoning the Python ecosystem.

The solution: run the same Python engine unchanged in the browser via Pyodide WASM, orchestrated through a Web Worker to keep the UI responsive during the 3-5 second cold start.

The Pydantic v2 + Pyodide compatibility was validated during planning research before any code was written. Official Emscripten wheels exist for pydantic-core at the pinned version.

A vendored dependency (`gtin_core.py`) originally imported pandas, which would break in the Pyodide browser context. This was caught during plan review (P0 finding) and resolved during implementation by stripping pandas-dependent functions from the vendored module, keeping only the core validation functions.

## Guidance

The pattern has four layers: Vite build-time bundling, Worker-based Pyodide initialization, virtual filesystem setup, and a two-round-trip message protocol.

### Layer 1: Vite bundles Python source as strings at build time

Use Vite's `?raw` import suffix to inline Python files as JavaScript string constants. No fetch calls at runtime; works with Vite's content hashing for cache busting.

```js
// pyodide-worker.mjs — top of file
import engineInit from '../engine/__init__.py?raw'
import modelsCode from '../engine/models.py?raw'
import validatorsCode from '../engine/validators.py?raw'
import schemaLoaderCode from '../engine/schema_loader.py?raw'
import columnMatcherCode from '../engine/column_matcher.py?raw'
import fileParserCode from '../engine/file_parser.py?raw'
import orchestratorCode from '../engine/orchestrator.py?raw'

// YAML schemas also bundled as strings
import walmartYaml from '../schemas/walmart.yaml?raw'
```

### Layer 2: Import path rewriting bridges local and Pyodide module resolution

Python source uses `from src.engine.models import ...` locally, but inside Pyodide the package lives at `/home/pyodide/engine/`. A single regex at load time fixes every import:

```js
function rewriteImports(source) {
  return source.replace(/from src\.engine\./g, 'from engine.')
}
```

### Layer 3: Pyodide virtual filesystem creates the package structure

After Pyodide loads and micropip installs dependencies, write the rewritten Python files into the virtual FS:

```js
async function initialize() {
  const { loadPyodide } = await import(`${PYODIDE_CDN}pyodide.mjs`)
  pyodide = await loadPyodide({ indexURL: PYODIDE_CDN })

  await pyodide.loadPackage('micropip')
  const micropip = pyodide.pyimport('micropip')
  await micropip.install('pydantic==2.10.5')  // pinned — see below
  await micropip.install('pyyaml')
  await micropip.install('openpyxl')

  pyodide.FS.mkdirTree('/home/pyodide/engine/gtin')
  pyodide.FS.writeFile('/home/pyodide/engine/__init__.py', rewriteImports(engineInit))
  pyodide.FS.writeFile('/home/pyodide/engine/models.py', rewriteImports(modelsCode))
  // ... remaining modules

  pyodide.runPython('import sys; sys.path.insert(0, "/home/pyodide")')
  pyodide.runPython('from engine.orchestrator import do_match, do_validate, do_diff')
}
```

**Pin `pydantic==2.10.5` explicitly.** Pyodide uses Emscripten-compiled wheels from its own registry. Not every Pydantic version has a compatible wheel. An unpinned `micropip.install('pydantic')` can pull a version without Emscripten wheels and fail silently.

### Layer 4: Two-round-trip Worker message protocol

Round 1 parses the uploaded file and returns a proposed column mapping. Round 2 takes the confirmed mapping and runs full validation. A module-level cache avoids re-parsing:

```python
# orchestrator.py (simplified — all functions return JSON strings)
_cached_parse = None

def do_match(file_path: str, filename: str, partner: str) -> str:
    global _cached_parse
    with open(file_path, "rb") as f:
        _cached_parse = parse_file(f.read(), filename)
    schema = load_schema(f"/home/pyodide/schemas/{partner}.yaml")
    mapping = match_columns(_cached_parse.headers, schema)
    return json.dumps(mapping)

def do_validate(mapping_json: str, partner: str) -> str:
    if _cached_parse is None:
        return json.dumps({"error": "No file parsed yet"})
    # Run four-tier validation using cached data + confirmed mapping
    ...
```

```js
// JavaScript Worker message handler
switch (action) {
  case 'match': {
    const safeName = data.filename.replace(/[/\\]/g, '_')
    pyodide.FS.writeFile(`/home/pyodide/upload/${safeName}`, fileBytes)
    const result = pyodide.runPython(`do_match(...)`)
    self.postMessage({ id, result: JSON.parse(result) })
    break
  }
  case 'validate': {
    const result = pyodide.runPython(`do_validate(...)`)
    self.postMessage({ id, result: JSON.parse(result) })
    break
  }
}
```

### CDN preload for cold start optimization

```html
<link rel="preload"
      href="https://cdn.jsdelivr.net/pyodide/v0.29.4/full/pyodide.asm.wasm"
      as="fetch" crossorigin>
```

## Why This Matters

Three properties make this pattern valuable:

1. **Zero-server architecture for sensitive data.** The product master never leaves the browser. No backend to secure, no data-processing agreement to negotiate, no server to maintain. For consulting firms handling confidential retail data, this eliminates the largest adoption friction.

2. **One codebase, two runtimes.** The same Python validation code runs locally via `pytest` and `click` CLI during development, and in-browser via Pyodide in production. When a validation rule changes, the fix is made once and works everywhere. This eliminates the formula-drift class of bugs documented in the [dual-engine cross-validation](../../retailer-scorecard-renegotiation-simulator/docs/solutions/architecture-patterns/dual-engine-cross-validation-2026-06-03.md) pattern.

3. **Build-time bundling eliminates runtime fetch chains.** Vite's `?raw` imports mean Python source is already in the Worker bundle. No waterfall of fetch requests for `.py` files, no CORS configuration, no cache invalidation strategy beyond Vite's content hashing. Compare with the [baked-data approach](../../where-the-money-comes-from/docs/solutions/architecture-patterns/interactive-analytics-deliverable-architecture-2026-05-26.md) when live computation is not needed.

### Security lessons specific to this pattern

The code review (4-agent ensemble) surfaced three security findings specific to the Pyodide-in-Worker pattern:

- **P0: Debug echo action.** A leftover `case 'echo'` in the Worker injected `data.value` directly into `pyodide.runPython()` with zero sanitization. Any same-origin code could execute arbitrary Python. **Removed entirely.** Never leave test actions in a production Worker.

- **P1: Unvalidated partner parameter.** The partner string was passed directly into a Python path construction (`/home/pyodide/schemas/{partner}.yaml`). A crafted partner like `../../upload/evil` could load arbitrary YAML as a schema. **Fixed with an allowlist:** `new Set(['walmart', 'costco', 'unfi', 'kehe'])`.

- **P1: Unsanitized filename.** The user-supplied filename was written directly to the Pyodide virtual FS. Path separators could escape the upload directory. **Fixed with:** `data.filename.replace(/[/\\]/g, '_')`.

These risks do not exist in traditional server-side Python. Any future project using this pattern should include allowlisting and sanitization from day one.

### Correctness lessons

- **Case-sensitive trigger matching.** YAML schemas define triggers as `Refrigerated`; CSV exports use `refrigerated`. The conditional validator compared with exact match, silently skipping rules. **Fix:** `.lower()` on both sides.

- **`return` vs `continue` in candidate loops.** The GTIN tier4 validator returned early when any candidate was in skip_fields, instead of continuing to the next candidate. Subtle: only surfaces when a product has multiple GTIN-like fields.

- **Trailing blank Excel rows.** openpyxl's `iter_rows()` includes trailing blank rows. These became all-None records that failed every presence check, inflating failure counts. **Fix:** skip rows where every cell is None.

### Dead code lesson

Three speculative features were built but never used by any consumer: `format_rules` (SchemaConfig field), `category_condition` (FieldSpec field), `analyze_hierarchy` (GTIN function). All had code paths in the validator but zero callers in any schema or test. Removed during code review. **Lesson:** do not build features before the first consumer exists.

## When to Apply

Use this pattern when **all** of these hold:

- Working Python logic complex enough that porting to JS would be a maintenance burden
- Sensitive data that must not leave the client machine
- Interactive application (user uploads, reviews, confirms) rather than batch processing
- Cold start of 3-5 seconds is acceptable
- Python dependencies have Pyodide-compatible wheels (check [Pyodide package list](https://pyodide.org/en/stable/usage/packages-in-pyodide.html))

Do **not** use when:

- Python logic is simple enough that a JS implementation would be shorter
- Sub-second startup is required
- Python code depends on packages without Emscripten wheels
- Server-side state is needed (database writes, external API auth)

## Related

- [Interactive Analytics Deliverable Architecture](../../where-the-money-comes-from/docs/solutions/architecture-patterns/interactive-analytics-deliverable-architecture-2026-05-26.md) — the "baked data" alternative when live computation is not needed
- [Dual-Engine Cross-Validation](../../retailer-scorecard-renegotiation-simulator/docs/solutions/architecture-patterns/dual-engine-cross-validation-2026-06-03.md) — the "dual implementation" alternative that Pyodide eliminates
