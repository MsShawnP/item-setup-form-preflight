/**
 * column-mapper — Mapping confirmation UI.
 *
 * Shows the proposed column mapping from the match step. Users can:
 * - Accept matched columns (green, confidence >= 0.8)
 * - Resolve ambiguous matches (yellow, dropdown of candidates)
 * - Acknowledge unmatched schema fields (red)
 * - Adjust any mapping via dropdown of all uploaded headers
 *
 * Confirming sends the parsed data + mapping to the Pyodide worker
 * for four-tier validation.
 */

import { validateData } from '../worker-api.js'

export default () => ({
  // Local copy of mapping that the user can edit
  editableMapping: [],

  init() {
    this.$watch('$store.app.columnMapping', (val) => {
      const mapping = val?.mapping || []
      this.editableMapping = mapping.map((m) => ({ ...m }))
    })
    const mapping = this.$store.app.columnMapping?.mapping || []
    this.editableMapping = mapping.map((m) => ({ ...m }))
  },

  /** All uploaded headers, for the dropdown selectors. */
  get allHeaders() {
    return this.$store.app.columnMapping?.headers || []
  },

  get unmatchedHeaders() {
    return this.$store.app.columnMapping?.unmatchedHeaders || []
  },

  get rowCount() {
    return this.$store.app.columnMapping?.rowCount || 0
  },

  /** Count of fields in each status bucket. */
  get statusCounts() {
    const counts = { matched: 0, ambiguous: 0, unmatched: 0 }
    for (const m of this.editableMapping) {
      if (m.uploadedHeader) {
        counts.matched++
      } else if (m.status === 'ambiguous') {
        counts.ambiguous++
      } else {
        counts.unmatched++
      }
    }
    return counts
  },

  /** CSS class for a mapping row's status indicator. */
  statusStyle(entry) {
    if (entry.uploadedHeader && entry.confidence >= 0.8) {
      return {
        bg: 'var(--color-status-pass-bg)',
        text: 'var(--color-status-pass-text)',
        label: 'Matched',
      }
    }
    if (entry.uploadedHeader && entry.confidence < 0.8) {
      return {
        bg: 'var(--color-status-warn-bg)',
        text: 'var(--color-status-warn-text)',
        label: 'Review',
      }
    }
    if (entry.status === 'ambiguous') {
      return {
        bg: 'var(--color-status-warn-bg)',
        text: 'var(--color-status-warn-text)',
        label: 'Ambiguous',
      }
    }
    return {
      bg: 'var(--color-status-fail-bg)',
      text: 'var(--color-status-fail-text)',
      label: 'Unmatched',
    }
  },

  /** User selects a header from a dropdown for a specific field. */
  assignHeader(fieldIndex, headerValue) {
    const entry = this.editableMapping[fieldIndex]
    if (headerValue === '') {
      entry.uploadedHeader = null
      entry.confidence = 0
      entry.status = 'unmatched'
    } else {
      entry.uploadedHeader = headerValue
      entry.confidence = 1.0
      entry.status = 'matched'
    }
  },

  /** Build the confirmed mapping and kick off validation. */
  async confirmMapping() {
    const store = this.$store.app

    // Build mapping: schemaField -> uploadedHeader
    const confirmed = {}
    for (const entry of this.editableMapping) {
      if (entry.uploadedHeader) {
        confirmed[entry.schemaField] = entry.uploadedHeader
      }
    }

    store.confirmedMapping = confirmed
    store.validationError = null

    // Check if validation engine is ready
    if (!store.engineReady) {
      store.setStep(4) // Show loading/progress state
      // Wait for engine to become ready
      await new Promise((resolve) => {
        if (store.engineReady) {
          resolve()
          return
        }
        const check = setInterval(() => {
          if (store.engineReady) {
            clearInterval(check)
            resolve()
          } else if (store.engineError) {
            clearInterval(check)
            resolve()
          }
        }, 200)
      })

      if (store.engineError) {
        store.validationError = `Validation engine failed to load: ${store.engineError}`
        store.setStep(3)
        return
      }
    }

    store.setStep(4) // Show "validating" spinner

    try {
      const result = await validateData(
        store.parsedData.rows,
        confirmed,
        store.selectedPartner,
      )
      store.results = result
      store.setStep(5)
    } catch (err) {
      store.validationError = `Validation failed: ${err.message}`
      store.setStep(3)
    }
  },
})
