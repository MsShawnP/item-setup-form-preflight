/**
 * schema-diff — Paired schema comparison view.
 *
 * Loads diff data directly in JS (no Pyodide needed) and displays
 * two comparison panels: retailers (Walmart vs Costco) and
 * distributors (UNFI vs KeHE).
 */

import { computeDiff } from '../schema-differ.js'

export default () => ({
  loading: true,
  error: null,
  diffData: null,
  pinnedField: null,

  init() {
    try {
      this.diffData = computeDiff()
      this.loading = false
    } catch (err) {
      this.error = err.message
      this.loading = false
    }
  },

  get retailerPair() {
    return this.diffData?.retailer_pair || null
  },

  get distributorPair() {
    return this.diffData?.distributor_pair || null
  },

  get annotation() {
    return this.diffData?.annotation || null
  },

  pinField(name, pairKey) {
    if (this.pinnedField?.name === name && this.pinnedField?.pairKey === pairKey) {
      this.pinnedField = null
      return
    }

    const pair = pairKey === 'retailer' ? this.retailerPair : this.distributorPair

    const shared = pair.shared_fields.find((f) => f.name === name)
    if (shared) {
      this.pinnedField = {
        name,
        pairKey,
        partnerA: pair.partner_a,
        partnerB: pair.partner_b,
        fieldA: {
          format: shared.format_a,
          pattern: shared.pattern_a,
          source: 'shared',
        },
        fieldB: {
          format: shared.format_b,
          pattern: shared.pattern_b,
          source: 'shared',
        },
      }
      return
    }

    const uniqueA = pair.unique_a.find((f) => f.name === name)
    if (uniqueA) {
      this.pinnedField = {
        name,
        pairKey,
        partnerA: pair.partner_a,
        partnerB: pair.partner_b,
        fieldA: {
          format: uniqueA.format_description || '(no format constraint)',
          pattern: uniqueA.format_pattern,
          source: 'unique',
        },
        fieldB: null,
      }
      return
    }

    const uniqueB = pair.unique_b.find((f) => f.name === name)
    if (uniqueB) {
      this.pinnedField = {
        name,
        pairKey,
        partnerA: pair.partner_a,
        partnerB: pair.partner_b,
        fieldA: null,
        fieldB: {
          format: uniqueB.format_description || '(no format constraint)',
          pattern: uniqueB.format_pattern,
          source: 'unique',
        },
      }
      return
    }
  },

  dismissPin() {
    this.pinnedField = null
  },

  isDimmed(name, pairKey) {
    if (!this.pinnedField) return false
    return !(this.pinnedField.name === name && this.pinnedField.pairKey === pairKey)
  },

  formatFieldName(name) {
    return name
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (c) => c.toUpperCase())
  },

  formatDivergenceCount(pair) {
    if (!pair) return 0
    return pair.shared_fields.filter((f) => !f.format_match).length
  },
})
