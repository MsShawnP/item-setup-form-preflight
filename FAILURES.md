# Item Setup Form Pre-flight — Failure Log

What was attempted that didn't work, why it didn't work, and what was
tried next.

Lower bar than DECISIONS.md — capture failures even when they didn't
produce a durable rule. The whole point: future-you (or future-Claude)
shouldn't re-attempt dead ends because the lesson got lost.

---

## Format

### YYYY-MM-DD — [One-line failure description]

**Attempted:** [What was tried]

**Why it didn't work:** [Concrete reason, not "it broke."]

**What we tried instead:** [The next attempt]

**Status:** Resolved / open / abandoned

**Tags:** [keywords for future text-search]

---

## Entries

### 2026-06-05 — Preview screenshot timeout during QA

**Attempted:** Used Claude Preview `preview_screenshot` to visually QA the readiness tool page.

**Why it didn't work:** Pyodide WASM preload on the main page overwhelmed the preview renderer — the 30-second screenshot timeout expired while Pyodide was still downloading/initializing (~10MB payload).

**What we tried instead:** Used `preview_snapshot` (accessibility tree) as fallback. Confirmed all content, structure, nav links, and component hierarchy rendered correctly. Visual design compliance verified via `preview_inspect` on specific CSS properties.

**Status:** Resolved — accessibility snapshots are sufficient for structural QA; visual pixel-level QA can be done manually in a browser.

**Tags:** pyodide, preview, timeout, QA, screenshot
