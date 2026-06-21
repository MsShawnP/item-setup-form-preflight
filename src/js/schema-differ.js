/**
 * schema-differ — Compare partner schemas pairwise (JS port).
 *
 * Port of orchestrator.py's do_diff / _compare_pair / _compute_channel_annotation.
 * Produces identical output shape — no Pyodide required.
 */

import { loadSchema } from './schema-loader.js'

/**
 * Compute schema diffs between the two standard partner pairs.
 *
 * @returns {{ retailer_pair: Object, distributor_pair: Object, annotation: string }}
 */
export function computeDiff() {
  const walmart = loadSchema('walmart')
  const costco = loadSchema('costco')
  const unfi = loadSchema('unfi')
  const kehe = loadSchema('kehe')

  const retailerPair = comparePair(walmart, costco)
  const distributorPair = comparePair(unfi, kehe)
  const annotation = computeChannelAnnotation(retailerPair, distributorPair)

  return {
    retailer_pair: retailerPair,
    distributor_pair: distributorPair,
    annotation,
  }
}

/**
 * Compare two partner schemas and return structured diff data.
 */
function comparePair(schemaA, schemaB) {
  const fieldsA = {}
  const fieldsB = {}

  for (const f of schemaA.required_fields) fieldsA[f.name] = f
  for (const f of schemaB.required_fields) fieldsB[f.name] = f

  const namesA = new Set(Object.keys(fieldsA))
  const namesB = new Set(Object.keys(fieldsB))

  const sharedNames = new Set([...namesA].filter((n) => namesB.has(n)))
  const uniqueANames = new Set([...namesA].filter((n) => !namesB.has(n)))
  const uniqueBNames = new Set([...namesB].filter((n) => !namesA.has(n)))

  // Shared fields with format comparison
  const sharedFields = [...sharedNames].sort().map((name) => {
    const fa = fieldsA[name]
    const fb = fieldsB[name]
    return {
      name,
      format_a: fa.format_description || '(no format)',
      format_b: fb.format_description || '(no format)',
      pattern_a: fa.format_pattern || null,
      pattern_b: fb.format_pattern || null,
      format_match: (fa.format_pattern || null) === (fb.format_pattern || null),
    }
  })

  // Unique fields
  const uniqueA = [...uniqueANames].sort().map((name) => ({
    name,
    format_description: fieldsA[name].format_description || null,
    format_pattern: fieldsA[name].format_pattern || null,
  }))

  const uniqueB = [...uniqueBNames].sort().map((name) => ({
    name,
    format_description: fieldsB[name].format_description || null,
    format_pattern: fieldsB[name].format_pattern || null,
  }))

  // GTIN hierarchy comparison
  const gtinComparison = {
    a_level: schemaA.gtin_hierarchy.expected_level,
    a_formats: schemaA.gtin_hierarchy.expected_formats,
    b_level: schemaB.gtin_hierarchy.expected_level,
    b_formats: schemaB.gtin_hierarchy.expected_formats,
    level_match:
      schemaA.gtin_hierarchy.expected_level === schemaB.gtin_hierarchy.expected_level,
    formats_match:
      setsEqual(
        new Set(schemaA.gtin_hierarchy.expected_formats),
        new Set(schemaB.gtin_hierarchy.expected_formats),
      ),
  }

  // Conditional rule comparison
  const rulesA = {}
  const rulesB = {}
  for (const r of schemaA.conditional_rules || []) {
    rulesA[`${r.trigger_field}|${r.trigger_value}`] = r
  }
  for (const r of schemaB.conditional_rules || []) {
    rulesB[`${r.trigger_field}|${r.trigger_value}`] = r
  }

  const rulesAKeys = new Set(Object.keys(rulesA))
  const rulesBKeys = new Set(Object.keys(rulesB))

  const sharedRules = [...rulesAKeys]
    .filter((k) => rulesBKeys.has(k))
    .sort()
    .map((key) => {
      const ra = rulesA[key]
      const rb = rulesB[key]
      return {
        trigger_field: ra.trigger_field,
        trigger_value: ra.trigger_value,
        required_a: ra.required_fields,
        required_b: rb.required_fields,
        fields_match: setsEqual(
          new Set(ra.required_fields),
          new Set(rb.required_fields),
        ),
      }
    })

  const uniqueRulesA = [...rulesAKeys]
    .filter((k) => !rulesBKeys.has(k))
    .sort()
    .map((key) => ({
      trigger_field: rulesA[key].trigger_field,
      trigger_value: rulesA[key].trigger_value,
      required_fields: rulesA[key].required_fields,
    }))

  const uniqueRulesB = [...rulesBKeys]
    .filter((k) => !rulesAKeys.has(k))
    .sort()
    .map((key) => ({
      trigger_field: rulesB[key].trigger_field,
      trigger_value: rulesB[key].trigger_value,
      required_fields: rulesB[key].required_fields,
    }))

  const conditionalComparison = {
    shared_rules: sharedRules,
    unique_a: uniqueRulesA,
    unique_b: uniqueRulesB,
  }

  // Overlap percentage
  const totalUniqueFields = new Set([...namesA, ...namesB]).size
  const overlapPct =
    totalUniqueFields > 0
      ? Math.round((sharedNames.size / totalUniqueFields) * 1000) / 10
      : 0

  return {
    partner_a: schemaA.display_name,
    partner_b: schemaB.display_name,
    partner_a_key: schemaA.partner,
    partner_b_key: schemaB.partner,
    total_a: namesA.size,
    total_b: namesB.size,
    shared_count: sharedNames.size,
    unique_a_count: uniqueANames.size,
    unique_b_count: uniqueBNames.size,
    overlap_pct: overlapPct,
    shared_fields: sharedFields,
    unique_a: uniqueA,
    unique_b: uniqueB,
    gtin_comparison: gtinComparison,
    conditional_comparison: conditionalComparison,
  }
}

function computeChannelAnnotation(retailerPair, distributorPair) {
  const rPct = retailerPair.overlap_pct
  const dPct = distributorPair.overlap_pct
  const rA = retailerPair.partner_a
  const rB = retailerPair.partner_b
  const dA = distributorPair.partner_a
  const dB = distributorPair.partner_b

  const diff = dPct - rPct

  if (diff > 10) {
    return (
      `${dA} and ${dB} share ${dPct}% of their required fields ` +
      `vs. ${rPct}% for ${rA} and ${rB} — a common pattern among ` +
      `broadline distributors whose warehouse-receiving workflows ` +
      `converge on similar data requirements.`
    )
  }
  if (diff < -10) {
    return (
      `${rA} and ${rB} share ${rPct}% of their required fields ` +
      `vs. ${dPct}% for ${dA} and ${dB}. Retailer schemas show ` +
      `higher convergence here than the distributor pair.`
    )
  }
  return (
    `Both pairs show similar overlap: ${rA}/${rB} at ${rPct}% ` +
    `and ${dA}/${dB} at ${dPct}%. Neither channel type shows ` +
    `markedly higher schema convergence in this sample.`
  )
}

function setsEqual(a, b) {
  if (a.size !== b.size) return false
  for (const item of a) {
    if (!b.has(item)) return false
  }
  return true
}
