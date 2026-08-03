# Archived validation results

These per-partner JSON files (`walmart.json`, `costco.json`, `unfi.json`,
`kehe.json`) are the audit-CLI output for the 50-SKU Cinderhaven demo master
(`data/cinderhaven/product_master.csv`), one file per partner schema.

**Regenerated 2026-08-03 with the current single-count engine.** They no longer
carry the two artifacts of the pre-fix engine:

- Rows with an invalid GTIN now carry exactly **one** CRITICAL
  `GTIN_HIERARCHY_WRONG` entry (the INFO advisory is no longer stamped CRITICAL
  alongside the real failure), so raw error-entry counts are accurate.
- On every row, `pass_count + fail_count == fields_checked` (the counts foot by
  construction).

Bounce counts: walmart 29/50, costco 26/50, unfi 26/50, kehe 26/50 — locked by
`tests_golden.py`.

## Regenerate

```bash
for p in walmart costco unfi kehe; do
  python -c "from src.cli.audit import cli; cli()" audit \
    data/cinderhaven/product_master.csv -p $p -f json --accept-mapping \
    > scripts/results/$p.json
done
```
