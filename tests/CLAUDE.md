# Test conventions for item-setup-form-preflight `tests/`

This file applies when Claude is working in `tests/`.

## What gets tested

- Public-facing functions and behaviors.
- Edge cases the user surfaced during `/clarify`.
- Anything in FAILURES.md that has a corresponding fix in code.
- Each validation tier (presence, format, conditional, GTIN hierarchy).

## What doesn't need a test

- Glue code (one-line wrappers, trivial mappings).
- Configuration constants.
- Pure type definitions.

## Structure

- Mirror the source tree: `src/foo/bar.py` -> `tests/foo/test_bar.py`.
- One file per source module unless tests are huge.
- Group related tests by behavior, not by function name.

## Test names

- Describe what the test verifies, in plain English.
- Pattern: `test_<behavior>_when_<condition>`.
- Bad: `test_function_1`, `test_validate`.
- Good: `test_returns_critical_bounce_when_gtin_hierarchy_wrong`, `test_passes_when_all_required_fields_present`.

## Setup and teardown

- Prefer fresh state per test over shared mutable state.
- If setup is heavy (DB, network), pin it explicitly and document why.

## Assertions

- One concept per test. If a test asserts five unrelated things, split it.
- Assertions should print useful failure messages.

## Mocks and fakes

- Mock at the boundary (network, filesystem, time), not internal pure functions.
- If you mock a function, comment why.

## Running

- Tests must be runnable with a single command: `pytest`.
- A failing test is more useful than an unrun test.

## When a test fails

- Read the actual output, not what you expected to see.
- Bisect: which change broke it?
- Don't suppress with `skip` or `xfail` without an issue or PLAN item to come back.
