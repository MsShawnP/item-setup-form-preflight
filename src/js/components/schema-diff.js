/**
 * schema-diff — Paired schema comparison view.
 *
 * Loads diff data from the Pyodide worker and displays two comparison
 * panels: retailers (Walmart vs Costco) and distributors (UNFI vs KeHE).
 * Click-to-pin interaction shows full field spec on a dark callout card.
 */

import { computeDiff } from '../worker-api.js'

export default () => ({
  loading: true,
  error: null,
  diffData: null,
  pinnedField: null, // { name, pairKey, fieldA, fieldB }

  async init() {
    // Wait for Pyodide to become ready before requesting diff
    const store = this.$store.app
    if (store.pyodideReady) {
      await this.loadDiff()
      return
    }

    // Poll until ready (worker status updates are async)
    const check = setInterval(async () => {
      if (store.pyodideReady) {
        clearInterval(check)
        await this.loadDiff()
      } else if (store.loadingError) {
        clearInterval(check)
        this.loading = false
        this.error = store.loadingError
      }
    }, 200)
  },

  async loadDiff() {
    try {
      this.diffData = await computeDiff()
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

  /**
   * Pin or unpin a field for detail view.
   * Clicking the same field again unpins it.
   */
  pinField(name, pairKey) {
    if (this.pinnedField?.name === name && this.pinnedField?.pairKey === pairKey) {
      this.pinnedField = null
      return
    }

    const pair = pairKey === 'retailer' ? this.retailerPair : this.distributorPair

    // Look in shared fields first
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

    // Look in unique_a
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

    // Look in unique_b
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

  /**
   * Check if a field row should be dimmed (another field is pinned).
   */
  isDimmed(name, pairKey) {
    if (!this.pinnedField) return false
    return !(this.pinnedField.name === name && this.pinnedField.pairKey === pairKey)
  },

  /**
   * Format field name for display: underscores to spaces, title case.
   */
  formatFieldName(name) {
    return name
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (c) => c.toUpperCase())
  },

  /**
   * Count format divergences in shared fields.
   */
  formatDivergenceCount(pair) {
    if (!pair) return 0
    return pair.shared_fields.filter((f) => !f.format_match).length
  },
})
