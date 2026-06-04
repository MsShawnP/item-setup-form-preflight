# Code conventions for item-setup-form-preflight `src/`

This file applies when Claude is working in `src/`.

## Style

- Match the existing code style. If there's a linter config, follow it strictly.
- New files mirror the structure of nearby existing files.
- No mixing of paradigms inside a module without a reason worth stating in DECISIONS.md.
- Python: follow Ruff defaults. Type hints on all public functions.

## Naming

- Functions: verbs (`validate_field`, `parse_master`, `check_hierarchy`)
- Variables: nouns (`schema_config`, `validation_result`)
- Booleans: predicates (`is_required`, `has_gtin`)
- Avoid abbreviations unless they're standard in this codebase.

## Imports

- Sort imports: external first, then internal absolute, then relative.
- No unused imports left in code.

## Comments

- Comment why, not what. The code already says what.
- TODO comments include a date or issue reference.

## Tests

- Each new non-trivial function gets at least one test in `tests/`.
- Test names describe behavior in plain English.
- Avoid testing implementation details — test inputs and outputs.

## Error handling

- Don't swallow errors. If you catch one, log or rethrow with context.
- No bare `except:` blocks without comment explaining why.
- Validation errors return the structured error contract (`field / error_type / trigger / rejection_risk`), not exceptions.

## Don't invent

- Before adding a new utility, check if a similar one already exists.
- Before adding a dependency, ask the user (and log to DECISIONS.md).
- Before refactoring an existing pattern, surface it as a question, not a fait accompli.

## When stuck

- Smallest reproducer.
- One change at a time.
- Run the test, read the actual output (not what you expected).
