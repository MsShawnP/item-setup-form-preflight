# Item Setup Form Pre-flight — Project Context for Claude

## What this project is

A retailer/distributor item-setup pre-flight engine that codifies partner
schemas (Walmart Item 360, Costco item setup workbook, UNFI and KeHE new
item forms) as structured YAML config, then runs a four-tier validation
engine against a product master to flag rejection risks before submission.
Runs entirely client-side via Pyodide — the product master never leaves
browser memory. Includes an audit CLI for local master exports.

**Business question this project answers:** Is this product actually ready
to submit to this specific retailer, and if not, exactly which fields will
bounce and why?

## Tier

Medium

## Stack and tools

- Primary language: Python 3.12+
- Validation framework: Pydantic v2
- Schema library: YAML (per-partner item-setup specs — the core reusable asset)
- Browser runtime: Pyodide/WASM (Web Worker for non-blocking UI)
- Build tool: Vite
- Frontend: Alpine.js + Tailwind CSS
- CLI: click + openpyxl (audit utility, repo-only)
- Data store: SQLite (Cinderhaven case-study data)
- Testing: pytest
- Linting: Ruff
- Fonts: Self-hosted woff2 (Playfair Display, Source Sans 3)
- Reused dependency: GTIN Validator (from portfolio)

## Project files

- CLAUDE.md (this file) — permanent rules and facts
- DECISIONS.md — durable choices and reasoning
- HANDOFF.md — current session state
- PLAN.md — current work arc
- FAILURES.md — things tried that didn't work

Read PLAN.md and HANDOFF.md at session start. DECISIONS.md and
FAILURES.md as relevant.

## Voice and standards

- Economist style for all written output: sober, declarative, data-forward
- No marketing voice or consultant filler ("leverage," "synergy,"
  "best-in-class," "unlock," "drive value")
- No hedging that softens a real finding
- Charts must be readable by non-data-scientist audiences
- Follow Lailara design system for all visual output

## Rules

### Honesty and judgment

- Say "I don't know" or "I can't verify this" instead of guessing.
  This applies to industry context, technical claims, what code did,
  and anything else.
- Tell me what I need to hear, not what I want to hear. If a decision
  looks wrong, say so. If code I wrote has problems, say so. Honest
  assessment, not validation.
- If a rule in this file is too vague to verify whether you're
  following it, flag it for revision rather than guessing at compliance.

### Building and proposing

- No speculative abstractions. If something isn't needed right now,
  don't build it. Helper functions get added when called by real code,
  not in anticipation. Parameters get added when there's a second use
  case, not the first.
- When proposing a tool, library, or approach, present at least two
  alternatives with tradeoffs, even if one is clearly preferred. Do
  not propose a single solution and move on. The default failure mode
  is taking the route with less friction instead of the route that
  best fits the project — challenge yourself before proposing.
- Tie proposals back to the business question this project is
  answering. If you can't connect a proposal to that question, the
  proposal is probably fluff and should be reconsidered.

### How to work the project

- Work in vertical slices, not horizontal phases. Build one feature
  end-to-end (working from input to output) before moving to the
  next. Don't build all the backend, then all the frontend — build
  one complete piece at a time.
- When a feature is working, suggest a simple test to verify it stays
  working: "This works now — want to add a quick test so it doesn't
  break later?" Don't force testing, but make it easy to say yes.
- Do not start tasks outside the current PLAN.md arc without flagging
  it to the user first.
- Do not refactor unrelated code unprompted.
- Do not rename things unless asked.

### Domain boundaries (critical)

- This piece validates presence + format + conditional requirements +
  GTIN hierarchy for each retailer's specific form. It does NOT
  re-decide which weight/dimension value is correct (that's Dimension
  & Weight Integrity's job).
- This piece checks retailer-specific submission readiness. It does
  NOT do general product-data completeness scoring (that's PDH).
- The launch SKU's physical fields must match whatever Dimension &
  Weight Integrity establishes — no drift.

### Git branching

- Before risky or experimental changes, suggest creating a branch.
- Keep it simple: `git checkout -b experiment/short-description`
  before the change, merge back to main if it works.
- Don't require branches for small, safe changes.

### Scope creep detection

- Periodically check whether the current work matches PLAN.md.
  If the user has been building something not in the plan for more
  than ~15 minutes, flag it.
- Also flag if the user keeps adding tasks to PLAN.md without
  completing existing ones.

## Working with PLAN.md

PLAN.md defines the current arc of work. Read it at session start.

- Mark tasks complete as they're finished, in the same commit as the
  work
- If a task is wrong-sized, in the wrong order, or no longer relevant,
  flag it rather than silently restructuring
- "Out of scope" items are decisions, not suggestions — do not pull
  them into the current arc without explicit user approval

## Session reminders

### Session start protocol

1. Read CLAUDE.md, PLAN.md, and HANDOFF.md
2. If HANDOFF.md's most recent entry is more than 24 hours old AND
   there are uncommitted changes, flag this
3. Briefly state the starting point from HANDOFF.md
4. Confirm the current PLAN.md arc is still active
5. Check the Improvement History section of PLAN.md

## Defaults

- Default to flagging gaps rather than filling with plausible-sounding
  but unverified content
- Default to short responses unless the task is substantive
- Default to asking before promoting a log entry to a DECISIONS.md
  entry
- Default to answering, not offering to answer
