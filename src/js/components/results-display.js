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

  /**
   * Prefilled mailto for the results CTA. Summary metrics only — the file
   * itself never leaves the browser; the user attaches it from their own mail
   * client, keeping the "the file never leaves this page" promise literally true.
   */
  get mailtoLink() {
    const s = this.summary
    const partner = this.partnerName || 'my retailer'
    const subject = `Item setup pre-flight — ${partner}`
    const body =
      'Hi Shawn,\r\n\r\n' +
      `I ran my product master through your ${partner} item-setup pre-flight and got:\r\n\r\n` +
      `Partner: ${partner}\r\n` +
      ` Rows checked: ${s.totalRows || 0}\r\n` +
      ` Rows passing: ${s.passing || 0}\r\n` +
      ` Rows with issues: ${s.failing || 0}\r\n\r\n` +
      'My file is attached. Which of these will actually cost me?\r\n\r\n' +
      'Thanks,\r\n'
    return `mailto:shawn@lailarallc.com?subject=${encodeURIComponent(
      subject,
    )}&body=${encodeURIComponent(body)}`
  },

  /**
   * Clean-case variant of mailtoLink — same mechanism, adapted body for a
   * 0-failing result. Summary metrics only; nothing uploaded.
   */
  get cleanMailtoLink() {
    const s = this.summary
    const partner = this.partnerName || 'my retailer'
    const subject = `Item setup pre-flight — ${partner}`
    const body =
      'Hi Shawn,\r\n\r\n' +
      `My product master passed your ${partner} item-setup pre-flight:\r\n\r\n` +
      `Partner: ${partner}\r\n` +
      ` Rows checked: ${s.totalRows || 0}\r\n` +
      ` Rows passing: ${s.passing || 0}\r\n\r\n` +
      'My file is attached — can you run the same check against my other retailers and my full product master?\r\n\r\n' +
      'Thanks,\r\n'
    return `mailto:shawn@lailarallc.com?subject=${encodeURIComponent(
      subject,
    )}&body=${encodeURIComponent(body)}`
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
