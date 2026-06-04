/**
 * results-display — Two-view output for validation results.
 *
 * Per-SKU view: A card per row with pass/fail badge, expandable error
 * list grouped by severity.
 *
 * Aggregate view: Summary banner, most common failure types, top
 * failing fields.
 */

export default () => ({
  expandedRows: {},

  get results() {
    return this.$store.app.results?.results || []
  },

  get summary() {
    return this.$store.app.results?.summary || {}
  },

  get viewMode() {
    return this.$store.app.viewMode
  },

  get partnerName() {
    const map = {
      walmart: 'Walmart',
      costco: 'Costco',
      unfi: 'UNFI',
      kehe: 'KeHE',
    }
    return map[this.$store.app.selectedPartner] || this.$store.app.selectedPartner
  },

  get passingPct() {
    const s = this.summary
    if (!s.totalRows) return '0'
    return Math.round((s.passing / s.totalRows) * 100)
  },

  get summaryVerdict() {
    const s = this.summary
    if (s.passing === s.totalRows) return 'ALL PASS'
    if (s.passing === 0) return 'ALL FAIL'
    return 'MIXED'
  },

  get summaryVerdictStyle() {
    const v = this.summaryVerdict
    if (v === 'ALL PASS') {
      return { bg: 'var(--color-status-pass-bg)', text: 'var(--color-status-pass-text)' }
    }
    if (v === 'ALL FAIL') {
      return { bg: 'var(--color-status-fail-bg)', text: 'var(--color-status-fail-text)' }
    }
    return { bg: 'var(--color-status-warn-bg)', text: 'var(--color-status-warn-text)' }
  },

  setView(mode) {
    this.$store.app.viewMode = mode
  },

  toggleRow(index) {
    this.expandedRows[index] = !this.expandedRows[index]
  },

  isExpanded(index) {
    return !!this.expandedRows[index]
  },

  /** Group errors by severity for a single row result. */
  groupedErrors(rowResult) {
    const groups = { CRITICAL: [], WARNING: [], INFO: [] }
    for (const e of rowResult.errors) {
      if (groups[e.severity]) {
        groups[e.severity].push(e)
      }
    }
    return groups
  },

  severityStyle(severity) {
    if (severity === 'CRITICAL') {
      return { bg: 'var(--color-status-fail-bg)', text: 'var(--color-status-fail-text)' }
    }
    if (severity === 'WARNING') {
      return { bg: 'var(--color-status-warn-bg)', text: 'var(--color-status-warn-text)' }
    }
    return { bg: 'var(--color-status-info-bg)', text: 'var(--color-status-info-text)' }
  },

  /** Format error type enum for display. */
  formatErrorType(errorType) {
    const map = {
      PRESENCE_MISSING: 'Missing required field',
      FORMAT_INVALID: 'Format violation',
      CONDITIONAL_REQUIREMENT_MISSING: 'Conditional requirement',
      GTIN_HIERARCHY_WRONG: 'GTIN hierarchy error',
    }
    return map[errorType] || errorType
  },

  /** Start over from step 1. */
  startOver() {
    this.$store.app.reset()
  },
})
